# Memory Graph

Memory Graph is a local-first Flask REST API for persistent agent memory.
It stores conversations, memories, entities, embeddings, and key-value state in
SQLite, supports FTS5 and semantic retrieval, and exposes a small web UI.

## Quick Start

```bash
# 1) Clone and enter repo
git clone <repo-url> memory-graph
cd memory-graph

# 2) Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Configure environment
export MEMORY_DB_PATH=/path/to/memory.db

# Optional runtime overrides
export MEMORY_HOST=0.0.0.0
export MEMORY_PORT=7777
export MEMORY_MAX_CONTENT_LENGTH=1048576
export MEMORY_CORS_ORIGINS='http://localhost:3000,http://localhost:7777'

# Embeddings provider (set one)
export OPENAI_API_KEY=sk-...
# or
export GOOGLE_API_KEY=AIza...

# 5) Run server
python api_server.py
```

Server: http://localhost:7777
UI: http://localhost:7777/graph

## Configuration

`config.py` reads these settings:

- `MEMORY_DB_PATH` (fallback: `~/.claude/memory.db`)
- `MEMORY_HOST` (fallback: `HOST`, default `0.0.0.0`)
- `MEMORY_PORT` (fallback: `PORT`, default `7777`)
- `MEMORY_MAX_CONTENT_LENGTH` (fallback: `MAX_CONTENT_LENGTH`, default `1048576`)
- `MEMORY_CORS_ORIGINS` (fallback: `CORS_ORIGINS`, default `*`)
- `OPENAI_API_KEY` and `GOOGLE_API_KEY`

## API Overview

All endpoints return JSON. Error responses use `{"error": "..."}`.
Application-level handlers are registered for `404`, `405`, `413`, and `500`.

### Conversations

- `POST /conversation/log`
  - Body: `role` (required), `content` (required), `channel` (optional)
  - Response: `201 {"id": <int>}`
- `GET /conversation/recent?limit=<int>&offset=<int>`
  - Default `limit=20`, max `100`, default `offset=0`
- `GET /conversation/search?q=<query>&limit=<int>&offset=<int>`
- `GET /conversation/stats`

### Memory

- `POST /memory`
- `GET /memory/list?limit=<int>&offset=<int>`
- `GET /memory/recall?topic=<topic>&limit=<int>&offset=<int>`
- `GET /memory/search?q=<query>&limit=<int>&offset=<int>`
- `DELETE /memory/<id>`

### Entities

- `POST /entity`
- `GET /entity/search?q=<query>&limit=<int>&offset=<int>`

### Search

- `GET /search/semantic?q=<query>&limit=<int>&offset=<int>`
- `GET /search/hybrid?q=<query>&limit=<int>&offset=<int>`

### Embeddings

- `GET /embeddings/stats`
- `POST /embeddings/reindex`

### KV + Utility

- `GET /kv/<key>`
- `PUT /kv/<key>` with body `{"value": ...}`
- `GET /health`
- `GET /version`
- `GET /graph`

## Phase 2 Summary

Phase 2 is implemented in four subphases:

- **2A Hardening**
  - Environment-driven host/port/body/CORS config
  - JSON handlers for `404/405/413`
  - Gemini API key moved from URL query param to `x-goog-api-key` header
- **2B FTS Correctness**
  - Added FTS `UPDATE` and `DELETE` triggers for conversations and memories
  - Added `COALESCE` trigger writes for NULL-safe indexing
- **2C Pagination + Query Hygiene**
  - Added strict `limit/offset` validation across search-style endpoints
  - Added blank-query rejection and safer query handling
- **2D Performance + Embedding Dedup**
  - Removed hybrid-search N+1 lookup patterns via batched queries
  - Reindex uses batched write flow and transaction rollback on DB errors
  - Reindex dedupes identical content in-run
  - Schema init enforces unique `embeddings.text` via index and repairs legacy duplicates

See:

- `docs/phase2a.md`
- `docs/phase2b.md`
- `docs/phase2c.md`
- `docs/phase2d.md`

## Phase 3 Plan

Phase 3 starts with multi-agent memory usability for local trusted agents
(no authentication), while preserving shared memory where useful.

- **3A Agent Memory Scopes (planned, required for this deployment)**
  - Two-scope memory model: `shared` and `private`
  - Required writer identity: `owner_agent_id`
  - Read semantics: default to `shared + own-private`
  - Promote flow: private memory can be promoted to shared
  - API and schema additions for visibility filtering and lifecycle controls
- **3B Retrieval Quality + Lifecycle (planned, partially required)**
  - Ranking with confidence/recency/visibility weighting
  - Merge/supersede/archive/invalidate operations
- **3C Scale + Ops (planned, mostly optional/defer for current scale)**
  - Async enrichment pipeline and queueing
  - Cursor pagination for larger recall workloads
  - Observability and maintenance jobs

See:

- `docs/phase3a.md`
- `docs/phase3a-pr-chunks.md`
- `docs/phase3b.md`
- `docs/phase3c.md`
- `docs/phase3-overview.md`
- `docs/phase3-backlog.md`

## Testing

Run all tests:

```bash
venv/bin/python -m pytest -q --tb=no
```

Current status:

- `329 passed, 4 skipped`

## Project Layout

```text
memory-graph/
├── api_server.py
├── config.py
├── db_operations.py
├── db_schema.py
├── db_utils.py
├── embeddings.py
├── requirements.txt
├── blueprints/
│   ├── conversations.py
│   ├── kv.py
│   ├── memory.py
│   ├── search.py
│   └── utility.py
├── docs/
│   ├── phase1a.md
│   ├── phase1b.md
│   ├── phase1c.md
│   ├── phase1d.md
│   ├── phase2a.md
│   ├── phase2b.md
│   ├── phase2c.md
│   ├── phase2d.md
│   ├── phase3a.md
│   ├── phase3a-pr-chunks.md
│   ├── phase3b.md
│   ├── phase3c.md
│   ├── phase3-overview.md
│   └── phase3-backlog.md
├── static/
│   └── index.html
└── tests/
    └── ...
```
