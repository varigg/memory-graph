# Refactor Map: Storage and Service Layers

This document maps every function in the current oversized modules to its target
location in the proposed `storage/` and `services/` packages. It is the
implementation plan for the refactor described in `docs/architecture.md` under
"Code Boundary Direction."

## Status

This refactor is implemented.

The checklist below is retained as an execution record and has been updated to
reflect the completed migration that introduced `storage/`, `services/`,
shared blueprint parameter parsing, thin transport adapters, and removal of
`db_operations.py`.

## Target Module Structure

```
storage/
  __init__.py
  memory_repository.py
  conversation_repository.py
  embedding_repository.py
  entity_repository.py
  kv_repository.py
  metrics_repository.py

services/
  __init__.py
  memory_write_service.py
  memory_lifecycle_service.py
  memory_retrieval_service.py
  hybrid_search_service.py

blueprints/
  _params.py                  ← new: shared request parsing helpers
  conversations.py            ← thin adapter only
  memory.py                   ← thin adapter only
  search.py                   ← thin adapter only
  kv.py                       ← already thin, no change needed
  utility.py                  ← already thin, no change needed
```

These files do not move and require no structural change:

- `db_schema.py` — schema initialization and migration, stays as infrastructure
- `db_utils.py` — connection management, stays as infrastructure
- `config.py` — environment configuration, stays as is
- `embeddings.py` — provider abstraction, stays as is
- `api_server.py` — app factory, stays as is

---

## Function Mapping

### `db_operations.py` → storage and services

| Current function                 | Target module                          | Notes                                      |
| -------------------------------- | -------------------------------------- | ------------------------------------------ |
| `_deserialize_metadata`          | `storage/memory_repository.py`         | stays private to the module                |
| `_build_scope_predicate`         | `storage/memory_repository.py`         | stays private, used only by query builders |
| `_build_memory_filter_predicate` | `storage/memory_repository.py`         | stays private, used only by query builders |
| `_memory_order_by_clause`        | `storage/memory_repository.py`         | stays private, used only by query builders |
| `list_memories`                  | `storage/memory_repository.py`         | rename: `list_memories`                    |
| `list_memories_scoped`           | `storage/memory_repository.py`         | rename: `list_memories_scoped`             |
| `fts_search_memories`            | `storage/memory_repository.py`         | rename: `fts_search_memories`              |
| `fts_search_memories_scoped`     | `storage/memory_repository.py`         | rename: `fts_search_memories_scoped`       |
| `insert_memory`                  | `storage/memory_repository.py`         | rename: `insert_memory`                    |
| `get_memory_by_idempotency_key`  | `storage/memory_repository.py`         | rename: `get_memory_by_idempotency_key`    |
| `set_memory_verification`        | `services/memory_lifecycle_service.py` | contains ownership check + business rules  |
| `promote_memory_to_shared`       | `services/memory_lifecycle_service.py` | contains ownership check + business rules  |
| `transition_memory_status`       | `services/memory_lifecycle_service.py` | contains state-machine logic               |
| `relate_memory_lifecycle`        | `services/memory_lifecycle_service.py` | contains multi-row orchestration           |
| `insert_conversation`            | `storage/conversation_repository.py`   |                                            |
| `fts_search_conversations`       | `storage/conversation_repository.py`   |                                            |
| `insert_entity`                  | `storage/entity_repository.py`         |                                            |
| `insert_embedding`               | `storage/embedding_repository.py`      |                                            |
| `cosine_similarity`              | `storage/embedding_repository.py`      | pure math, private to module               |
| `semantic_search`                | `storage/embedding_repository.py`      | cursor-based search over embedding rows    |
| `compute_importance`             | `storage/conversation_repository.py`   | reads importance_keywords table            |
| `upsert_kv`                      | `storage/kv_repository.py`             |                                            |
| `get_kv`                         | `storage/kv_repository.py`             |                                            |
| `get_memory_usefulness_metrics`  | `storage/metrics_repository.py`        | read-only analytics SQL                    |

### `blueprints/memory.py` → services and `blueprints/_params.py`

| Current function                                                                                                                                                                                                                                                            | Target module                          | Notes                                                              |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| `_parse_limit_offset`                                                                                                                                                                                                                                                       | `blueprints/_params.py`                | currently duplicated in 3 blueprints; consolidate here             |
| `_parse_scope_flags`                                                                                                                                                                                                                                                        | `blueprints/_params.py`                |                                                                    |
| `_parse_read_filters`                                                                                                                                                                                                                                                       | `blueprints/_params.py`                |                                                                    |
| `_normalize_memory_payload`                                                                                                                                                                                                                                                 | `services/memory_write_service.py`     | rename: `parse_memory_payload`; HTTP-neutral validation            |
| `_create_or_get_memory`                                                                                                                                                                                                                                                     | `services/memory_write_service.py`     | rename: `create_or_get_memory`; orchestrates idempotency           |
| `_transition_memory_lifecycle`                                                                                                                                                                                                                                              | removed                                | its logic collapses into a thin call to `memory_lifecycle_service` |
| `_relate_memory_lifecycle`                                                                                                                                                                                                                                                  | removed                                | its logic collapses into a thin call to `memory_lifecycle_service` |
| list/recall/search branching logic                                                                                                                                                                                                                                          | `services/memory_retrieval_service.py` | the `if agent_id:` scoped vs unscoped dispatch                     |
| route handlers (`create_memory`, `create_memory_batch`, `promote_memory`, `archive_memory`, `invalidate_memory`, `verify_memory`, `merge_memory`, `supersede_memory`, `list_memories`, `recall_memory`, `search_memory`, `delete_memory`, `create_entity`, `search_entity`) | `blueprints/memory.py`                 | stay in place; become thin adapters calling service layer          |

### `blueprints/search.py` → services

| Current function                                                                | Target module                       | Notes                                                          |
| ------------------------------------------------------------------------------- | ----------------------------------- | -------------------------------------------------------------- |
| `_parse_limit_offset`                                                           | `blueprints/_params.py`             | consolidate with the other two copies                          |
| hybrid RRF scoring and orchestration inside `hybrid()`                          | `services/hybrid_search_service.py` | extracts the ranking logic into a testable service function    |
| reindex batch logic inside `embeddings_reindex()`                               | `storage/embedding_repository.py`   | moves the batch-insert and FK-repair logic into the repository |
| route handlers (`semantic`, `hybrid`, `embeddings_stats`, `embeddings_reindex`) | `blueprints/search.py`              | stay in place; become thin adapters                            |

### `blueprints/conversations.py`

| Current function                                                 | Target module                 | Notes                                         |
| ---------------------------------------------------------------- | ----------------------------- | --------------------------------------------- |
| `_parse_limit_offset`                                            | `blueprints/_params.py`       | consolidate                                   |
| route handlers (`log_conversation`, `recent`, `search`, `stats`) | `blueprints/conversations.py` | stay in place; already close to thin adapters |

---

## Responsibility Summary By Target Module

### `storage/memory_repository.py`

All primitive SQL operations on the `memories` table and `fts_memories` virtual
table. Private query-builder helpers. No business rules. Returns raw dicts or
None.

### `storage/conversation_repository.py`

Insert, FTS search, and importance scoring for the `conversations` table.

### `storage/embedding_repository.py`

Insert, deduplication, semantic search, and reindex batch logic for the
`embeddings` table.

### `storage/entity_repository.py`

Insert and LIKE search for the `entities` table.

### `storage/kv_repository.py`

Upsert and get for the `kv_store` table.

### `storage/metrics_repository.py`

Read-only analytics queries for the memory usefulness scorecard.

### `services/memory_write_service.py`

Payload validation and normalization (HTTP-neutral). Idempotency check and
create-or-get orchestration. Batch write loop.

### `services/memory_lifecycle_service.py`

Ownership checks, state-machine rules, and multi-row orchestration for
verification, promotion, archive, invalidate, merge, and supersede operations.
Calls memory_repository for raw writes; owns the lifecycle rules.

### `services/memory_retrieval_service.py`

Scoped vs unscoped dispatch, retrieval profile selection, and result shaping for
list, recall, and search operations. This is where autonomous vs general
retrieval policy should eventually live explicitly.

### `services/hybrid_search_service.py`

RRF scoring, FTS and semantic result merging, and importance weighting for
hybrid search queries.

### `blueprints/_params.py`

Shared request-parsing helpers: `parse_limit_offset`, `parse_scope_flags`,
`parse_read_filters`. No business logic.

---

## Migration Order

The order is chosen to give structural wins early with minimal disruption.

**Step 1 — Shared request parsing**
Extract `_parse_limit_offset`, `_parse_scope_flags`, and `_parse_read_filters`
into `blueprints/_params.py`. Update all three blueprints to import from there.
Tests require no change.

**Step 2 — Storage repositories**
Create `storage/` package. Extract `storage/memory_repository.py` first (largest
gain). Then `storage/conversation_repository.py`, `storage/embedding_repository.py`,
`storage/entity_repository.py`, `storage/kv_repository.py`, and
`storage/metrics_repository.py`. `db_operations.py` becomes a thin re-export
shim during this step to avoid breaking imports in one go.

**Step 3 — Lifecycle service**
Create `services/memory_lifecycle_service.py`. Move the four lifecycle functions
(`set_memory_verification`, `promote_memory_to_shared`, `transition_memory_status`,
`relate_memory_lifecycle`) from `db_operations.py` into it. Collapse the
`_transition_memory_lifecycle` and `_relate_memory_lifecycle` blueprint helpers
into direct service calls.

**Step 4 — Write service**
Create `services/memory_write_service.py`. Move `_normalize_memory_payload` and
`_create_or_get_memory` out of the blueprint. Blueprint handlers become two-line
callers.

**Step 5 — Retrieval service**
Create `services/memory_retrieval_service.py`. Move the scoped vs unscoped
branching logic for list, recall, and search into it. This is the right point to
formalize retrieval profiles.

**Step 6 — Hybrid search service**
Create `services/hybrid_search_service.py`. Extract RRF and scoring from the
`hybrid()` route handler. Route handler becomes a thin adapter.

**Step 7 — Remove `db_operations.py` re-export shim**
Once all consumers import from `storage/` and `services/`, delete the shim and
remove `db_operations.py` from `pyproject.toml`'s `py-modules`.

---

## What Does Not Change

- The public HTTP API surface. No endpoint changes.
- `db_utils.py` and `db_schema.py` are infrastructure and stay as is.
- `db_utils.get_db` continues to be the connection accessor inside services and
  blueprints.
- Test structure stays the same. Tests exercise blueprints, so internal module
  moves do not break them unless imports inside tests reference `db_operations`
  directly.

---

## Test Coverage Note

A small number of tests import from `db_utils` or `db_operations` directly.
Those imports will need updating in step 7 but can be left until the shim is
removed. Use `grep -rn "from db_operations\|import db_operations"` across
`tests/` to find them before step 7.

---

## Detailed Implementation Plan

Each step below is self-contained. Complete the verification checklist before
starting the next step. All tasks assume the project venv is active and tests
are run with `python -m pytest`.

---

### Step 1 — Shared request parsing

**Goal:** eliminate the three identical copies of `_parse_limit_offset`,
`_parse_scope_flags`, and `_parse_read_filters` by moving them to a single
shared module.

**Tasks:**

- [x] Create `blueprints/_params.py` as an empty module with an `__init__` comment.
- [x] Copy `_parse_limit_offset` from `blueprints/memory.py` into `_params.py`
      and make it public by renaming to `parse_limit_offset`.
- [x] Copy `_parse_scope_flags` from `blueprints/memory.py` into `_params.py`
      and rename to `parse_scope_flags`.
- [x] Copy `_parse_read_filters` from `blueprints/memory.py` into `_params.py`
      and rename to `parse_read_filters`.
- [x] In `blueprints/memory.py`: replace the three function definitions with
      imports from `._params` and update all call sites to use the new names.
- [x] In `blueprints/conversations.py`: replace its `_parse_limit_offset`
      definition with an import of `parse_limit_offset` from `._params` and
      update the two call sites.
- [x] In `blueprints/search.py`: replace its `_parse_limit_offset` definition
      with an import of `parse_limit_offset` from `._params` and update call
      sites.
- [x] Delete the now-unused private function bodies in all three blueprints.

**Verification:**

- [x] `python -m pytest` passes with no failures or new warnings.
- [x] `grep -rn "_parse_limit_offset\|_parse_scope_flags\|_parse_read_filters" blueprints/`
      returns zero matches (the underscore-prefixed originals are gone).
- [x] `grep -rn "from \._params import\|from blueprints._params import" blueprints/`
      shows three import lines, one per blueprint that uses them.
- [x] Manual smoke: `GET /memory/list?limit=5` returns a valid JSON list.

---

### Step 2 — Storage repositories

**Goal:** create the `storage/` package and move all raw SQL out of
`db_operations.py` into focused repository modules. Introduce a re-export shim
in `db_operations.py` so no other import sites break yet.

**Tasks:**

- [x] Create `storage/__init__.py` (empty).
- [x] Create `storage/memory_repository.py`. Move into it:
  - `_deserialize_metadata`
  - `_build_scope_predicate`
  - `_build_memory_filter_predicate`
  - `_memory_order_by_clause`
  - `list_memories`
  - `list_memories_scoped`
  - `fts_search_memories`
  - `fts_search_memories_scoped`
    - `insert_memory`
    - `get_memory_by_idempotency_key`
- [x] Create `storage/conversation_repository.py`. Move into it:
  - `insert_conversation`
  - `fts_search_conversations`
  - `compute_importance`
- [x] Create `storage/embedding_repository.py`. Move into it:
  - `insert_embedding`
  - `cosine_similarity` (keep private)
  - `semantic_search`
    - The batch-insert and FK-repair logic currently inside
      `blueprints/search.py::embeddings_reindex` — extract it into a function
      named `reindex_embeddings(db, embed_fn)` and call it from the route handler.
- [x] Create `storage/entity_repository.py`. Move into it:
  - `insert_entity`
  - The LIKE-search SQL currently inline in `blueprints/memory.py::search_entity`
    — extract it into `search_entities(db, query, limit, offset)`.
- [x] Create `storage/kv_repository.py`. Move into it:
  - `upsert_kv`
  - `get_kv`
- [x] Create `storage/metrics_repository.py`. Move into it:
  - `get_memory_usefulness_metrics`
- [x] Update `db_operations.py` to become a shim: replace each moved function
      body with a re-export import from the appropriate `storage/` module.
      Example pattern:
      `python
  from storage.memory_repository import (
      list_memories,
      list_memories_scoped,
      ...
  )
  `
- [x] Update `blueprints/kv.py` to import `upsert_kv` and `get_kv` from
      `storage.kv_repository` directly (it is already thin).
- [x] Update `blueprints/utility.py` to import `get_memory_usefulness_metrics`
      from `storage.metrics_repository` directly.
- [x] Update `blueprints/search.py` to call `storage.embedding_repository.reindex_embeddings`
      from `embeddings_reindex()` and `storage.embedding_repository.semantic_search`
      from `semantic()`.
- [x] Update `blueprints/memory.py` to call `storage.entity_repository.search_entities`
      from `search_entity()`.

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `python -c "import storage.memory_repository; print('ok')"` succeeds.
- [x] `python -c "import db_operations; print('ok')"` still succeeds (shim works).
- [x] `wc -l db_operations.py` is now significantly smaller (mostly re-exports
      and the four lifecycle functions not yet moved).
- [x] Manual smoke: `POST /memory` creates a memory, `GET /memory/list` returns
      it, `GET /embeddings/stats` returns `{"total": ...}`.

---

### Step 3 — Lifecycle service

**Goal:** move the four lifecycle functions with business rules out of
`db_operations.py` into a dedicated service module. Simplify the two blueprint
helper wrappers that currently duplicate their error-mapping logic.

**Tasks:**

- [x] Create `services/__init__.py` (empty).
- [x] Create `services/memory_lifecycle_service.py`. Move into it:
  - `set_memory_verification`
  - `promote_memory_to_shared`
  - `transition_memory_status`
  - `relate_memory_lifecycle`
- [x] Each of these functions currently accepts a raw `db` connection. Keep that
      signature unchanged for now; services receive `db` from the blueprint via
      `get_db()`.
- [x] In `db_operations.py` shim: add re-exports for these four functions from
      `services.memory_lifecycle_service`.
- [x] In `blueprints/memory.py`: replace the bodies of `_transition_memory_lifecycle`
      and `_relate_memory_lifecycle` with direct calls to
      `memory_lifecycle_service.transition_memory_status` and
      `memory_lifecycle_service.relate_memory_lifecycle`. These helpers can be
      removed entirely if the call sites are simple enough after extraction.
- [x] Update all imports in `blueprints/memory.py` that referenced these
      functions from `db_operations` to import from
      `services.memory_lifecycle_service`.

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `grep -n "set_memory_verification\|promote_memory_to_shared\|transition_memory_status\|relate_memory_lifecycle" db_operations.py`
      shows only re-export lines, no function definitions.
- [x] Manual smoke: `POST /memory/archive` archives a memory and returns 200;
      `POST /memory/supersede` supersedes a memory correctly.
- [x] Manual smoke: `POST /memory/verify` sets verification status correctly.

---

### Step 4 — Write service

**Goal:** move payload validation and idempotent-write orchestration out of the
blueprint into a testable service module.

**Tasks:**

- [x] Create `services/memory_write_service.py`.
- [x] Move `_normalize_memory_payload` from `blueprints/memory.py` into it,
      renamed to `parse_memory_payload(data: dict) -> tuple[dict | None, ...]`.
      The function should remain HTTP-neutral: no Flask imports, no `jsonify`
      calls. Return the parsed payload dict on success or raise a
      `ValueError` with a descriptive message on failure. The blueprint will
      catch `ValueError` and convert to a 400 response.
- [x] Move `_create_or_get_memory` from `blueprints/memory.py` into it,
      renamed to `create_or_get_memory(db, payload: dict) -> dict`.
- [x] Update `blueprints/memory.py::create_memory` to call
      `memory_write_service.parse_memory_payload` and
      `memory_write_service.create_or_get_memory`.
- [x] Update `blueprints/memory.py::create_memory_batch` similarly.
- [x] Remove the now-empty private functions from `blueprints/memory.py`.

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `grep -n "_normalize_memory_payload\|_create_or_get_memory" blueprints/memory.py`
      returns zero matches.
- [x] `python -c "from services.memory_write_service import parse_memory_payload, create_or_get_memory; print('ok')"` succeeds.
- [x] Manual smoke: `POST /memory` with valid payload returns 201 with `id`.
- [x] Manual smoke: `POST /memory/batch` with two items returns 201 with
      `results` list.
- [x] Manual smoke: `POST /memory` with duplicate `idempotency_key` returns 200
      with `idempotent_replay: true`.

---

### Step 5 — Retrieval service

**Goal:** consolidate the scoped-vs-unscoped branching logic for list, recall,
and search into a single service that owns retrieval policy. Blueprint handlers
become pure HTTP adapters.

**Tasks:**

- [x] Create `services/memory_retrieval_service.py`.
- [x] Extract the `if agent_id:` branching and all keyword-argument forwarding
      from `blueprints/memory.py::list_memories` into a function
      `list_memories(db, *, agent_id, limit, offset, shared_only, private_only,
  visibility, owner_agent_id, status, run_id, tag, min_confidence,
  updated_since, recency_half_life_hours, metadata_key, metadata_value,
  metadata_value_type) -> list`.
- [x] Do the same for `recall_memory` → service function `recall_memories(db, *, topic, ...)`.
- [x] Do the same for `search_memory` → service function `search_memories(db, *, q, ...)`.
- [x] Update the three blueprint route handlers to parse request params via
      `_params`, then call the corresponding service function, then return
      `jsonify(result)`.
- [x] Remove the now-unused branching code from the blueprints.

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `wc -l blueprints/memory.py` is noticeably smaller than 723.
- [x] `python -c "from services.memory_retrieval_service import list_memories, recall_memories, search_memories; print('ok')"` succeeds.
- [x] Manual smoke: `GET /memory/list?agent_id=copilot` returns scoped results.
- [x] Manual smoke: `GET /memory/recall?topic=test&agent_id=copilot` returns results.
- [x] Manual smoke: `GET /memory/search?q=test` returns results (unscoped path).

---

### Step 6 — Hybrid search service

**Goal:** extract the RRF ranking and multi-leg result merging logic from the
`hybrid()` route handler into a testable service function.

**Tasks:**

- [x] Create `services/hybrid_search_service.py`.
- [x] Extract from `blueprints/search.py::hybrid` into a function
      `hybrid_search(db, embed_fn, query: str, limit: int, offset: int) -> list`.
      This function owns: - calling `fts_search_conversations` - calling `semantic_search` - batch-fetching importance scores - RRF scoring and merging - result ordering and slicing
- [x] `embed_fn` is passed in rather than imported directly inside the function
      so the service is testable without a live embedding provider.
- [x] Update `blueprints/search.py::hybrid` to call
      `hybrid_search_service.hybrid_search(db, embeddings.embed, cleaned_q, limit, offset)`.
- [x] The `semantic()` route handler can remain as-is; its logic is already
      simple enough (embed, call `semantic_search`, slice).

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `python -c "from services.hybrid_search_service import hybrid_search; print('ok')"` succeeds.
- [x] `grep -n "RRF\|scores\[conv_id\]\|fts_importance" blueprints/search.py`
      returns zero matches (scoring logic is gone from the blueprint).
- [x] Manual smoke: `GET /search/hybrid?q=test` returns a valid JSON list.
- [x] Manual smoke: `GET /search/semantic?q=test` still returns a valid JSON list.

---

### Step 7 — Remove `db_operations.py` shim

**Goal:** delete the now-empty shim file, update all remaining import sites, and
remove `db_operations` from `pyproject.toml`.

**Tasks:**

- [x] Run `grep -rn "from db_operations\|import db_operations" .` and record
      every match outside `db_operations.py` itself.
- [x] For each match, update the import to point at the correct `storage/` or
      `services/` module.
- [x] Run `grep -rn "from db_operations\|import db_operations" tests/` separately
      and update any direct test imports.
- [x] Confirm `db_operations.py` contains nothing but re-exports (no function
      definitions remain).
- [x] Delete `db_operations.py`.
- [x] In `pyproject.toml`, remove `db_operations` from the `py-modules` list
      under `[tool.setuptools]`.

**Verification:**

- [x] `python -m pytest` passes with no failures.
- [x] `python -c "import db_operations"` raises `ModuleNotFoundError` (file is
      gone).
- [x] `grep -rn "db_operations" . --include="*.py"` returns zero matches.
- [x] `python -m pytest --tb=short -q` produces the same pass count as before
      step 1 (no tests were silently dropped).
- [x] Run `ruff check .` — no new lint errors introduced by the refactor.
- [x] Manual smoke: full API round-trip — create memory, list, recall, search,
      archive, supersede, hybrid search — all return expected responses.
