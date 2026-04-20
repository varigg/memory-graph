# Phase 1b — Code Review & API Reference

## 1. API Reference

All routes are served by a Flask application created via `create_app()`. The base URL is
`http://localhost:<port>` unless otherwise configured.

---

### Conversations

#### `POST /conversation/log`

Appends a conversation turn, optionally computing and storing an embedding.

**Request body** (JSON):

| Field     | Type   | Required | Default     | Description                             |
| --------- | ------ | -------- | ----------- | --------------------------------------- |
| `role`    | string | yes      | —           | Speaker role (e.g. `user`, `assistant`) |
| `content` | string | yes      | —           | Message text                            |
| `channel` | string | no       | `"default"` | Logical grouping channel                |

**Response** `201`:

```json
{ "id": 42 }
```

**Error responses**: `400` if `role` or `content` are absent.

---

#### `GET /conversation/recent`

Returns the most-recent conversations in reverse chronological order.

**Query params**:

| Param   | Type | Default | Description        |
| ------- | ---- | ------- | ------------------ |
| `limit` | int  | `20`    | Max rows to return |

**Response** `200` — array of:

```json
{
  "id": 1,
  "role": "user",
  "content": "...",
  "channel": "default",
  "timestamp": "2026-04-18 10:00:00",
  "importance": 0.0
}
```

---

#### `GET /conversation/search`

Full-text search over conversations using SQLite FTS5.

**Query params**: `q` (required) — search query string.

**Response** `200` — array of:

```json
{ "content": "...", "role": "user", "channel": "default", "conversation_id": 1 }
```

Returns `[]` silently on FTS parse errors (see correctness findings).

**Error**: `400` if `q` is absent.

---

#### `GET /conversation/stats`

Aggregate counts.

**Response** `200`:

```json
{ "total": 150, "by_role": { "user": 80, "assistant": 70 } }
```

---

### Memory

#### `POST /memory`

Creates a memory entry.

**Request body** (JSON):

| Field         | Type   | Required | Default  |
| ------------- | ------ | -------- | -------- |
| `name`        | string | yes      | —        |
| `content`     | string | yes      | —        |
| `type`        | string | no       | `"note"` |
| `description` | string | no       | `""`     |

**Response** `201`: `{ "id": 7 }`

---

#### `GET /memory/list`

Returns all memories.

**Response** `200` — array of:

```json
{
  "id": 1,
  "name": "...",
  "type": "note",
  "content": "...",
  "description": "",
  "timestamp": "...",
  "confidence": 1.0
}
```

---

#### `GET /memory/recall`

Full-text search over memories by topic. Functionally identical to `/memory/search`.

**Query params**: `topic` (required).

**Response** `200` — array of:

```json
{ "name": "...", "content": "...", "description": "...", "memory_id": 3 }
```

**Error**: `400` if `topic` is absent.

---

#### `GET /memory/search`

Full-text search over memories by query term.

**Query params**: `q` (required).

**Response** `200` — same shape as `/memory/recall`.

**Error**: `400` if `q` is absent.

---

#### `DELETE /memory/<id>`

Deletes a memory by integer ID.

**Response** `200`: `{ "deleted": 7 }`
**Error** `404` if ID not found.

---

### Entity

#### `POST /entity`

Creates an entity record.

**Request body** (JSON):

| Field     | Type   | Required | Default |
| --------- | ------ | -------- | ------- |
| `name`    | string | yes      | —       |
| `type`    | string | no       | `""`    |
| `details` | string | no       | `""`    |
| `tags`    | string | no       | `""`    |

**Response** `201`: `{ "id": 12 }`

---

#### `GET /entity/search`

LIKE-based substring search across `name`, `type`, `details`, `tags`.

**Query params**: `q` (required).

**Response** `200` — array of:

```json
{ "id": 1, "name": "...", "type": "...", "details": "...", "tags": "..." }
```

**Error**: `400` if `q` is absent.

---

### Search

#### `GET /search/semantic`

Embeds the query and performs cosine-similarity ranking across all stored embeddings.

**Query params**: `q` (required).

**Response** `200` — array of:

```json
{ "id": 5, "text": "...", "similarity": 0.92 }
```

Returns `[]` if no embedding provider is configured.

---

#### `GET /search/hybrid`

Reciprocal Rank Fusion (RRF, k=60) combining FTS and semantic results,
weighted by conversation `importance`.

**Query params**: `q` (required).

**Response** `200` — array of, sorted by descending RRF score:

```json
{
  "id": 1,
  "content": "...",
  "role": "user",
  "channel": "default",
  "importance": 0.5,
  "score": 0.017
}
```

---

#### `GET /embeddings/stats`

**Response** `200`: `{ "total": 200 }`

---

#### `POST /embeddings/reindex`

Iterates all conversations, obtains embeddings from the configured provider,
and inserts any that are not already present in the `embeddings` table
(deduplication by exact `text` match).

**Response** `200`: `{ "reindexed": 45 }`

Note: `reindexed` counts conversations for which an embedding was obtained,
not the number of new rows inserted (see correctness findings).

---

### Key-Value Store

#### `GET /kv/<key>`

**Response** `200`: `{ "key": "setting", "value": <any JSON value> }`
**Error** `404` if key not found.

---

#### `PUT /kv/<key>`

**Request body** (JSON): `{ "value": <any JSON value> }`

**Response** `200`: `{ "key": "setting" }`

**Error** `400` if body is not valid JSON or `value` field is absent.

---

### Utility

#### `GET /health`

**Response** `200`: `{ "status": "ok", "version": "0.1.0" }`

#### `GET /version`

**Response** `200`: `{ "version": "0.1.0" }`

#### `GET /graph`

Serves `static/index.html` as `text/html`. Falls back to a stub HTML page if the file
is absent.

---

## 2. Security Findings

### MEDIUM — Wildcard CORS policy

**Location**: `api_server.py` line 17 — `CORS(app)` with no `origins` restriction.

**Description**: `flask-cors` defaults to `Access-Control-Allow-Origin: *`, permitting any
web origin to make cross-site requests. For a service that is only ever accessed from a
known local or trusted origin this is safe, but it becomes a credential-exfiltration risk
if session cookies or Authorization headers are ever added.

**Remediation**: Restrict to the actual consumer origin:

```python
CORS(app, origins=["http://localhost:3000"])
```

---

### MEDIUM — Synchronous external HTTP call in request path

**Location**: `embeddings.py`, called from `blueprints/conversations.py` and
`blueprints/search.py`.

**Description**: `embed()` performs a blocking `requests.post` to OpenAI or Gemini with a
30-second timeout. A slow or unreachable provider stalls every `POST /conversation/log` and
every search request for up to 30 seconds, creating a denial-of-service surface against
availability. The API key is read from environment variables on every call rather than
cached at startup.

**Remediation**: Move embedding to a background task (Celery, asyncio, or a simple
thread pool). For searches, handle the `vector is None` path gracefully (as already done).

---

### LOW — FTS user input not sanitised before query construction

**Location**: `blueprints/conversations.py` line 54, `blueprints/memory.py` lines 42, 55,
`blueprints/search.py` lines 45, 55.

**Description**: User-supplied query strings are wrapped in double-quotes and passed as the
FTS MATCH argument, e.g. `f'"{q}"'`. Because the outer binding is still a parameterized
placeholder (`?`), there is no SQL injection. However, if `q` itself contains a
double-quote, the resulting FTS query string is malformed. SQLite raises an exception that
is caught silently, and the endpoint returns `[]` with no error message to the client.

**Remediation**: Either escape or strip `"` from the query before wrapping, or catch the
exception and return a `400` with an informative message rather than a silent empty result.

---

### LOW — No request body size limit

**Description**: Flask/Werkzeug defaults allow arbitrarily large POST bodies. A client
can send a multi-megabyte JSON body to any POST endpoint, consuming memory proportional
to body size before validation runs.

**Remediation**: Set `app.config["MAX_CONTENT_LENGTH"]` (e.g. `1 * 1024 * 1024` for 1 MB).

---

### LOW — Error handler covers only HTTP 500

**Location**: `api_server.py` lines 26–28.

**Description**: The JSON error handler is registered only for 500. Flask/Werkzeug will
return HTML for 404, 405, and other framework-generated errors, breaking API clients that
expect JSON. Under the current code there are no `abort()` calls, but future additions
could expose this gap.

**Remediation**: Register JSON handlers for at minimum 400, 404, and 405.

---

## 3. Correctness Findings

### BUG — `/embeddings/reindex` does not update `conversations.embedding_id`

**Severity**: High.

**Location**: `blueprints/search.py` lines 94–116.

**Description**: When `reindex` creates a new embedding for a conversation that was logged
without one (because `embed()` returned `None` at log time), it inserts the embedding row
but never executes `UPDATE conversations SET embedding_id = ? WHERE id = ?`. As a result,
the hybrid search join `WHERE embedding_id = ?` can never find that conversation via the
semantic leg, even after a successful reindex.

**Remediation**:

```python
new_id = db.execute(
    "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
    (content, json.dumps(vector), "auto"),
).lastrowid
db.execute(
    "UPDATE conversations SET embedding_id = ? WHERE id = ? AND embedding_id IS NULL",
    (new_id, conv_id),
)
db.commit()
```

---

### BUG — `/embeddings/reindex` `reindexed` count is misleading

**Severity**: Low.

**Location**: `blueprints/search.py` line 115 — `count += 1` runs regardless of whether a
new embedding was inserted or an existing one was skipped.

**Description**: The response `{ "reindexed": count }` signals the number of conversations
for which an embedding was _obtainable_, not the number of new rows actually written.

**Remediation**: Increment `count` only inside the `if existing is None` branch, or return
two separate counters: `{ "inserted": n, "skipped": m }`.

---

### BUG — `POST /conversation/log` creates duplicate embeddings

**Severity**: Low.

**Location**: `blueprints/conversations.py` line 31 — `insert_embedding` is called
unconditionally (when `vector is not None`) with no prior existence check.

**Description**: If the same `content` is logged multiple times, a new row is inserted into
`embeddings` each time. The `reindex` endpoint guards against duplicates, but the log path
does not. Over time this inflates the `embeddings` table and makes semantic search slower
(full-table scan).

**Remediation**: Check for an existing embedding before inserting, mirroring the pattern
used in `reindex`.

---

### BEHAVIOUR GAP — Semantic search has no similarity threshold

**Severity**: Low.

**Location**: `db_operations.py` — `semantic_search` returns the top-`k` embeddings
regardless of their cosine similarity to the query.

**Description**: If the corpus contains embeddings that are entirely unrelated to the query,
they will appear in the results with low-but-non-zero similarity scores. The hybrid
endpoint will incorporate these low-signal scores into the RRF fusion, degrading result
quality.

**Remediation**: Apply a minimum similarity threshold (e.g. 0.5) before including results,
or expose `threshold` as a configurable parameter.

---

### BEHAVIOUR GAP — `/memory/recall` and `/memory/search` are identical

**Severity**: Low.

**Description**: Both endpoints call `fts_search_memories(db, f'"{param}"')` with the same
logic; only the query parameter name differs (`topic` vs `q`). They are functionally
equivalent. This is redundant surface area.

**Remediation**: Deprecate one or differentiate them (e.g. recall could also perform a
semantic similarity pass).

---

### VERIFIED CORRECT — `/search/hybrid` asymmetric legs

The RRF loop processes only the items present in each result list. If the FTS leg returns
results but the semantic leg returns none (e.g., no embedding provider configured), only
FTS scores are accumulated. If both legs return no results, `scores` is empty and `[]` is
returned. Both asymmetric cases are handled correctly.

---

### VERIFIED CORRECT — `/conversation/stats` `by_role`

`GROUP BY role` followed by dict comprehension correctly produces `{ role: count }` per
distinct role. No bug.

---

### VERIFIED CORRECT — `embed() returns None` in `/conversation/log`

When `embed()` returns `None`, `embedding_id` is kept as `None` and the `INSERT INTO
conversations` still proceeds with `embedding_id = NULL`. The conversation is stored;
it simply lacks a vector reference. Correct and intentional.

---

## 4. Architectural Notes

### `get_db` / `g` pattern

`db_utils.get_db()` lazily opens a `sqlite3.Connection` on the first call within a
request and stores it on Flask's application-context-local `g` object. Because SQLite
connections are not thread-safe for concurrent writes, each request gets its own
connection. The `@app.teardown_appcontext` hook in `create_app` closes `g.db` at
request teardown, ensuring no connection leaks. The `sqlite3.Row` factory is set so
that rows support dict-style column access, enabling `dict(r)` serialisation without
manually naming fields.

### Blueprint registration

| Blueprint       | `url_prefix`    | Key routes                                             |
| --------------- | --------------- | ------------------------------------------------------ |
| `conversations` | `/conversation` | `/log`, `/recent`, `/search`, `/stats`                 |
| `memory`        | _(none)_        | `/memory`, `/memory/list`, `/memory/recall`, `/entity` |
| `search`        | _(none)_        | `/search/semantic`, `/search/hybrid`, `/embeddings/*`  |
| `kv`            | `/kv`           | `/<key>` (GET/PUT)                                     |
| `utility`       | _(none)_        | `/health`, `/version`, `/graph`                        |

`memory` and `search` are registered at root with no prefix. Their route paths are
self-prefixed (e.g. `/memory/...`, `/search/...`) but this is a naming convention, not
enforced by Flask's `url_prefix`. Adding a third blueprint with overlapping paths at root
would silently shadow one of them.

### Synchronous embedding in request body

Embeddings are computed inline during `POST /conversation/log` by calling the external
provider API over HTTP before the insert. This couples request latency directly to the
embedding provider's response time. The pattern is simple and debuggable, but under load
or provider instability every write request will block. The `reindex` endpoint exists as
a recovery mechanism for conversations logged with `embedding_id = NULL`, but it only
inserts embeddings — it does not back-fill `conversations.embedding_id` (see correctness
finding above).

### FTS query construction

All FTS searches wrap the user query in outer double-quotes (`f'"{q}"'`) to pass it to
SQLite FTS5 as a phrase query. This is the correct SQLite FTS5 idiom for exact phrase
matching, but the wrapping happens in the blueprint layer rather than inside
`db_operations`, meaning the calling convention leaks an implementation detail (FTS5
phrase syntax) into route handlers. Centralising the quoting/escaping inside
`fts_search_conversations` / `fts_search_memories` would be cleaner.

---

## Post-review fixes applied

The following bugs identified during this review were remediated before Phase 1 was closed:

- **Reindex endpoint now back-fills `conversations.embedding_id`.** The original implementation of `POST /embeddings/reindex` inserted a new embedding row when a conversation lacked one but never executed the corresponding `UPDATE conversations SET embedding_id = ?`. As a result, conversations reindexed after the fact were still invisible to the hybrid search's semantic leg, which joins on `conversations.embedding_id`. The fix adds an `UPDATE conversations SET embedding_id = ? WHERE id = ? AND embedding_id IS NULL` immediately after the insert, with a conditional commit.

- **FTS query input sanitized (double-quotes stripped) before binding to MATCH.** `GET /conversation/search` and `GET /search/hybrid` passed user input directly into an FTS5 phrase query of the form `f'"{q}"'`. If `q` itself contained a double-quote, SQLite raised a parse exception that was caught silently and caused the endpoint to return an empty result with no indication of the error. The input is now stripped of double-quote characters before wrapping, ensuring the MATCH expression is always well-formed.

- **Duplicate embedding prevention added in `POST /conversation/log`.** The log path called `insert_embedding` unconditionally whenever `embed()` returned a non-`None` vector, regardless of whether an embedding for that exact text already existed in the `embeddings` table. Repeated logging of the same content would therefore grow the `embeddings` table unboundedly and degrade semantic search performance (full-table scan). The fix adds a prior `SELECT id FROM embeddings WHERE text = ?` check and reuses the existing row's ID rather than inserting a new one, mirroring the deduplication logic already present in the reindex endpoint.
