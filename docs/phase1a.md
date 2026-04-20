# Phase 1A — Infrastructure & Schema: Code Review and Module Reference

## Module Reference

---

### `config.py`

Centralizes runtime configuration via a plain class with class-level attributes. All sensitive values are read from environment variables; no secrets are hardcoded.

| Symbol                      | Signature     | Purpose                                                                                                      |
| --------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------ |
| `Config.DB_PATH`            | `str`         | Absolute path to the SQLite database file. Defaults to `~/.claude/memory.db`. Override via `MEMORY_DB_PATH`. |
| `Config.HOST`               | `str`         | Bind address for the Flask server. Hardcoded to `"0.0.0.0"`.                                                 |
| `Config.PORT`               | `int`         | Listen port. Hardcoded to `7777`.                                                                            |
| `Config.OPENAI_API_KEY`     | `str \| None` | Read from `OPENAI_API_KEY` env var.                                                                          |
| `Config.GOOGLE_API_KEY`     | `str \| None` | Read from `GOOGLE_API_KEY` env var.                                                                          |
| `Config.EMBEDDING_PROVIDER` | `str \| None` | `"openai"` if `OPENAI_API_KEY` is set, else `"gemini"` if `GOOGLE_API_KEY` is set, else `None`.              |

**Caveats.** `EMBEDDING_PROVIDER` is evaluated once at class definition time (module import), not on each access. If env vars are mutated after import (common in test harnesses), `Config.EMBEDDING_PROVIDER` will not reflect the change, while `embeddings.get_provider()` — which reads the env at call time — will diverge. `HOST` and `PORT` have no env-var overrides, preventing deployment-time reconfiguration without code changes.

---

### `db_schema.py`

Declares the full SQLite schema and initializes the database. The module exposes a single public function; all DDL lives in the private `_DDL` string and seed data in `_SEED_KEYWORDS`.

| Symbol | Signature                | Purpose                                                                                                                         |
| ------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `init` | `(db_path: str) -> None` | Creates all tables, virtual FTS5 tables, and INSERT triggers; seeds `importance_keywords`. Opens and closes its own connection. |

**Tables created:** `conversations`, `memories`, `entities`, `embeddings`, `importance_keywords`, `kv_store`, `fts_conversations` (FTS5 virtual), `fts_memories` (FTS5 virtual).

**Triggers created:** `trg_fts_conversations_insert` (AFTER INSERT on `conversations`), `trg_fts_memories_insert` (AFTER INSERT on `memories`).

**Caveats.** The FTS sync triggers cover INSERT only. UPDATE and DELETE operations on `conversations` and `memories` will silently desync the FTS index from the base tables — a correctness issue detailed in the section below. The FTS virtual tables do not store the `rowid` of the originating base-table row, making it impossible to join FTS results back to retrieve `id`, `importance`, `embedding_id`, or `confidence`. `init()` is fully idempotent: every DDL statement uses `IF NOT EXISTS`, and seed insertion uses `INSERT OR IGNORE`.

---

### `db_operations.py`

Stateless helper functions that accept an open `sqlite3.Connection` and execute parameterized queries. No module-level state is maintained; all functions are pure with respect to module globals.

| Symbol                     | Signature                                                       | Purpose                                                                                        |
| -------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `upsert_kv`                | `(db, key: str, value: Any) -> None`                            | JSON-serializes `value` and upserts into `kv_store`.                                           |
| `get_kv`                   | `(db, key: str) -> Any \| None`                                 | Retrieves and JSON-deserializes a value from `kv_store`.                                       |
| `fts_search_conversations` | `(db, query: str) -> list[dict]`                                | FTS5 full-text search over conversations; returns `content`, `role`, `channel`.                |
| `fts_search_memories`      | `(db, query: str) -> list[dict]`                                | FTS5 full-text search over memories; returns `name`, `content`, `description`.                 |
| `insert_conversation`      | `(db, role, content, channel, importance, embedding_id) -> int` | Inserts a conversation row; returns the new row `id`.                                          |
| `insert_memory`            | `(db, name, type_, content, description, confidence) -> int`    | Inserts a memory row; returns the new row `id`.                                                |
| `insert_entity`            | `(db, name, type_, details, tags) -> int`                       | Inserts an entity row; returns the new row `id`.                                               |
| `insert_embedding`         | `(db, text, vector: list, model_version: str) -> int`           | JSON-serializes `vector` and inserts into `embeddings`; returns the new row `id`.              |
| `compute_importance`       | `(db, text: str) -> float`                                      | Keyword scan against `importance_keywords`; sums scores, clamps to `[0.0, 1.0]`.               |
| `cosine_similarity`        | `(v1: list, v2: list) -> float`                                 | Pure-Python cosine similarity; returns `0.0` for zero-magnitude vectors.                       |
| `semantic_search`          | `(db, query_vector: list, top_k: int = 10) -> list[dict]`       | Full table scan of `embeddings`, scores by cosine similarity, returns top-k sorted descending. |

**Caveats.** Every insert function calls `db.commit()` immediately, making each operation auto-commit. Callers that need multi-step atomicity (e.g., `insert_embedding` followed by `insert_conversation` with the resulting `embedding_id`) cannot wrap both in a single transaction because the first commit will release any outer savepoint. `compute_importance` issues a full-table SELECT on `importance_keywords` on every invocation; for the current seed size of 10 rows this is negligible, but it does not scale. `semantic_search` performs a full deserialize-and-score scan in Python with O(n) complexity; there is no approximate-nearest-neighbor index.

---

### `embeddings.py`

Provider-agnostic embedding facade. At call time, inspects env vars to select between OpenAI and Gemini REST APIs; falls back to `None` if neither key is present.

| Symbol          | Signature                            | Purpose                                                                                       |
| --------------- | ------------------------------------ | --------------------------------------------------------------------------------------------- |
| `get_provider`  | `() -> str \| None`                  | Returns `"openai"`, `"gemini"`, or `None` based on env vars at call time.                     |
| `embed`         | `(text: str) -> list[float] \| None` | Dispatches to the appropriate backend; returns the embedding vector or `None` on any failure. |
| `_embed_openai` | `(text: str) -> list[float] \| None` | Calls `POST /v1/embeddings` with model `text-embedding-ada-002`.                              |
| `_embed_gemini` | `(text: str) -> list[float] \| None` | Calls `POST /v1beta/models/embedding-001:embedContent`.                                       |

**Caveats.** Both private functions swallow `RequestException` and return `None`. The public `embed()` function also returns `None` when no provider is configured. Callers cannot distinguish a configuration error from a transient API failure without additional context. No HTTP timeout is set on either `requests.post()` call.

---

## Security Findings

### Medium — Gemini API key in URL query string

**Location:** `embeddings._embed_gemini`, line constructing the URL  
`f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={key}"`

The API key is appended as a URL query parameter. Any HTTP access log, reverse proxy log, or exception trace that captures the full request URL will contain the credential in plaintext. `requests` includes the URL in `RequestException` messages, so the key can leak into application logs whenever the call fails.

**Remediation:** Pass the key in the `x-goog-api-key` request header instead of the query string. The Gemini REST API supports this pattern. Example:

```python
resp = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent",
    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    json={...},
    timeout=10,
)
```

---

### Low — No HTTP timeout on embedding API calls

**Location:** `embeddings._embed_openai` and `embeddings._embed_gemini`

Neither call passes a `timeout` argument to `requests.post()`. A slow or unresponsive upstream will block the calling thread indefinitely, tying up a Flask worker in a synchronous deployment.

**Remediation:** Add `timeout=(5, 30)` (connect timeout, read timeout) to both calls.

---

### Low — `HOST = "0.0.0.0"` with no env override

**Location:** `config.Config.HOST`

Binding to all interfaces is appropriate for development and container deployments, but there is no mechanism to restrict the bind address without modifying the source. In a multi-tenant or shared-host environment this exposes the service on all network interfaces.

**Remediation:** Read from an env var: `HOST = os.environ.get("MEMORY_HOST", "127.0.0.1")`, with `"0.0.0.0"` as the default only in explicitly development contexts.

---

## Correctness Issues

### FTS index desync on UPDATE and DELETE

The triggers `trg_fts_conversations_insert` and `trg_fts_memories_insert` fire only on INSERT. If any blueprint route updates or deletes a row in `conversations` or `memories`, the FTS5 virtual tables will not reflect the change. Subsequent full-text searches will return stale or ghost results.

FTS5 requires explicit content-delete or content-update triggers (or use of `content=` and `content_rowid=` in the virtual table definition) to stay synchronized. Because the current FTS tables use no `content=` option, three additional trigger pairs are needed: AFTER UPDATE and AFTER DELETE for each base table, the DELETE trigger using `fts_conversations_config` or the `fts_conversations` DELETE syntax.

### FTS results carry no base-table row ID

The FTS virtual tables store only the indexed text columns; they do not include the `rowid` of the originating `conversations` or `memories` row. The search functions in `db_operations.py` therefore return dictionaries containing only text fields. Blueprint code that needs to join these results with importance scores, timestamps, or embedding references has no key to query on.

**Remediation:** Add `rowid` to the FTS table projections in `_DDL` and to the INSERT trigger `VALUES` clause (using `NEW.rowid`), and include it in the SELECT lists of `fts_search_conversations` and `fts_search_memories`.

### `Config.EMBEDDING_PROVIDER` evaluated at module import

`EMBEDDING_PROVIDER` is a class-level expression computed once when Python evaluates the `Config` class body. Code that reads `Config.EMBEDDING_PROVIDER` after patching env vars (e.g., in tests using `monkeypatch` or `unittest.mock.patch.dict`) will observe the stale value. `embeddings.get_provider()`, by contrast, reads env vars at call time and will see the patched state. The two mechanisms are semantically inconsistent.

### Overloaded `None` sentinel in `embeddings.embed()`

`embed()` returns `None` for three distinct situations: no provider configured, network error, and API error response. Callers cannot take differentiated action (e.g., retry a transient failure vs. skip embedding because no provider is configured). A structured result type or distinct exception would allow callers to make this distinction.

### Eager per-operation commit prevents multi-step atomicity

Each insert helper in `db_operations.py` calls `db.commit()` before returning. The intended workflow for `POST /conversation/log` requires inserting an embedding row first, then inserting the conversation row with the resulting `embedding_id`. Because both inserts commit independently, there is no way to make the two-row write atomic. A crash between the two commits will leave an orphan embedding with no referencing conversation.

---

## Design Notes

**FTS5 trigger-based indexing.** Using SQLite triggers to maintain the FTS5 index is a sound approach for a single-writer SQLite deployment: it eliminates the need for application code to manage index updates, and `IF NOT EXISTS` on both the trigger and the virtual table definition makes the schema fully idempotent. The limitation is that FTS5 trigger management is verbose — sync correctness requires all three DML operations (INSERT, UPDATE, DELETE) to be covered.

**Cosine similarity in Python.** The decision to compute cosine similarity in Python rather than in SQL is justified at Phase 1 scale. SQLite has no native vector type and no approximate-nearest-neighbor index; a SQL-side implementation would require a user-defined function anyway. The current approach is transparent, testable, and avoids a C extension dependency. At the scale where this becomes a bottleneck, the right move is sqlite-vec or a dedicated vector store, not optimization of the Python loop.

**Embedding abstraction.** `embeddings.py` deliberately avoids provider-specific SDKs, using only `requests`. This keeps the dependency footprint minimal (no `openai` or `google-generativeai` packages in requirements) and makes the abstraction boundary explicit. The trade-off is that SDK-level retry logic, token refresh, and structured error types are not available.

**Stateless operation helpers.** Passing `sqlite3.Connection` explicitly into every function in `db_operations.py` rather than maintaining a module-level connection is the correct design for a Flask application where connections should be request-scoped. It enables straightforward unit testing with in-memory databases and avoids cross-request state contamination.

**Keyword-based importance scoring.** The additive scoring model in `compute_importance` — sum of keyword scores, clamped to 1.0 — is intentionally simple. It serves as a bootstrapping heuristic until a learned classifier can replace it. The `hit_count` column on `importance_keywords` suggests future intent to track keyword signal strength, though nothing increments it yet.

---

## Post-review fixes applied

The following issues identified during this review were remediated before Phase 1 was closed:

- **Gemini API key moved from URL query string to `x-goog-api-key` header.** `_embed_gemini` previously appended the key as `?key=<value>` in the request URL. Any HTTP access log, reverse-proxy log, or `RequestException` message captured the credential in plaintext. The key is now passed as the `x-goog-api-key` request header, which is not included in URL-based access logs.

- **HTTP timeout (30 s) added to both embedding providers.** `_embed_openai` and `_embed_gemini` previously called `requests.post` with no `timeout` argument, leaving Flask workers vulnerable to indefinite blocking on a slow or unresponsive provider. Both calls now pass `timeout=30`.

- **FTS tables now include `conversation_id` / `memory_id` unindexed columns for base-table joins.** The original `fts_conversations` and `fts_memories` virtual-table DDL stored only the indexed text columns, making it impossible to join FTS results back to the base table to retrieve `id`, `importance`, `embedding_id`, or `confidence`. Both virtual tables now carry `conversation_id UNINDEXED` and `memory_id UNINDEXED` columns respectively, populated by the INSERT triggers and returned by the search helper functions.

## Known Limitations (Deferred to Phase 2)

- **No vector index.** `semantic_search` is a full table scan. Scalable ANN search (e.g., sqlite-vec, FAISS, or an external vector store) is a Phase 2 concern.
- **No FTS UPDATE/DELETE triggers.** Only INSERT is handled. Mutation of existing rows will desync the index.
- **No base-table `rowid` in FTS results.** Join-back to `conversations` or `memories` is not possible from FTS search results alone.
- **No embedding model configurability.** Model names (`text-embedding-ada-002`, `embedding-001`) are hardcoded. Switching models requires a code change and invalidates all stored vectors (no version-gated migration).
- **No `hit_count` increment.** The `hit_count` column on `importance_keywords` is defined but never written, deferring signal-tracking to a later phase.
- **No importance update after insert.** `insert_conversation` accepts `importance` as a parameter but there is no function to recompute and update importance after the fact (e.g., when new keywords are added).
- **Single-process SQLite.** The architecture is designed for a single Flask process. Horizontal scaling would require moving to a network-accessible database.
