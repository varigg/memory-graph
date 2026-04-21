# Memory Graph

Memory Graph is a local-first Flask REST API for persistent agent memory.
It stores conversations, memories, entities, embeddings, and key-value state in
SQLite, supports FTS5 and semantic retrieval, and exposes a small web UI.

## Documentation Guide

Use these documents as the canonical reading path for the project:

- `README.md` — current API surface, runtime workflow, and project status
- `docs/roadmap.md` — canonical living feature tracker across implemented, planned, and deferred work
- `docs/conversation-outcomes.md` — durable summary of design-discussion outcomes and where they landed
- `docs/phase1-2-consolidated.md` — consolidated review and implementation summary for the original backend foundation and hardening work
- `docs/phase3-overview.md` — Phase 3 direction and multi-agent memory evolution
- `docs/phase3a.md` — shared/private memory scopes and read semantics
- `docs/phase3b.md` — retrieval quality and lifecycle operations
- `docs/phase3c.md` — planned scale and ops follow-on work
- `docs/phase3-backlog.md` — deferred and future work inventory
- `docs/agent-memory-ops.md` — restart-safe autonomous-agent operating conventions for this service
- `harness.md` — target autonomous-agent harness vision that this backend is intended to support over time
- `.github/copilot-instructions.md` — Copilot-specific session continuity and shared-memory usage hints for this repo

If you want the shortest end-to-end overview, read this file first, then `docs/roadmap.md`, then `docs/conversation-outcomes.md`, then `docs/phase1-2-consolidated.md`, then `docs/phase3-overview.md`, then `docs/agent-memory-ops.md`, and finally `harness.md`.

## Quick Start

### Using uv (recommended)

```bash
# 1) Clone and enter repo
git clone <repo-url> memory-graph
cd memory-graph

# 2) Sync dependencies (creates venv automatically)
uv sync

# 3) Configure environment
export MEMORY_DB_PATH=/path/to/memory.db
export OPENAI_API_KEY=sk-...  # or GOOGLE_API_KEY=AIza...

# 4) Run server
uv run python api_server.py
```

Environment note:

- `uv` manages the project environment in `.venv`.
- If you see a warning about `VIRTUAL_ENV` pointing elsewhere, clear it with
  `unset VIRTUAL_ENV` in your shell and continue using `uv run ...`.
- Avoid keeping both `.venv` and a second project-local `venv` directory to
  prevent interpreter drift.

### Using pip + venv (alternative)

```bash
# 1) Clone and enter repo
git clone <repo-url> memory-graph
cd memory-graph

# 2) Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # or: .\\venv\\Scripts\\activate (Windows)

# 3) Install dependencies
pip install -r requirements.txt

# 4) Configure environment
export MEMORY_DB_PATH=/path/to/memory.db
export OPENAI_API_KEY=sk-...  # or GOOGLE_API_KEY=AIza...

# 5) Run server
python api_server.py
```

### Configuration

**Environment variables** (see `config.py`):

- `MEMORY_DB_PATH` — database path (fallback: `~/.claude/memory.db`)
- `MEMORY_HOST` — bind address (default: `0.0.0.0`)
- `MEMORY_PORT` — port (default: `7777`)
- `MEMORY_MAX_CONTENT_LENGTH` — request size limit (default: 1 MB)
- `MEMORY_CORS_ORIGINS` — CORS allowed origins (default: `*`)
- `OPENAI_API_KEY` or `GOOGLE_API_KEY` — embeddings provider

**Server endpoints:**

- API: http://localhost:7777
- UI: http://localhost:7777/graph
- Health check: http://localhost:7777/health

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run only unit tests (skip integration/e2e)
uv run pytest -m "not e2e"

# Run e2e tests (requires embeddings API key)
uv run pytest -m e2e -v

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

### Linting and Formatting

```bash
# Check code style with ruff
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format (ruff includes formatter)
uv run ruff format .
```

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
  - Body: `name` (required), `content` (required), `owner_agent_id` (required),
    `visibility` (optional: `shared` or `private`, default `shared`)
  - Optional write controls: `tags`, `run_id`, `idempotency_key`,
    `metadata` (JSON object)
- `POST /memory/batch`
  - Body: `{"memories": [ ... ]}` where each item follows `POST /memory`
- `POST /memory/<id>/promote?agent_id=<id>`
  - Owner-only promote of private memory to shared
- `POST /memory/archive`
  - Body: `memory_id` (required int), `agent_id` (required)
- `POST /memory/invalidate`
  - Body: `memory_id` (required int), `agent_id` (required)
- `POST /memory/verify`
  - Body: `memory_id` (required int), `agent_id` (required),
    `verification_status` (`unverified|verified|disputed`),
    `verification_source` (optional)
- `GET /memory/list?limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>`
- `GET /memory/recall?topic=<topic>&limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>`
- `GET /memory/search?q=<query>&limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>`
- `DELETE /memory/<id>`

Additional memory retrieval filters (for `list`, `recall`, and `search`):

- `run_id=<id>`
- `tag=<token>`
- `min_confidence=<0..1>`
- `updated_since=<timestamp>`
- `recency_half_life_hours=<positive_number>`
- `metadata_key=<key>`
- `metadata_value=<value>`
- `metadata_value_type=string|number|boolean|null`

Read-scope behavior when `agent_id` is provided:

- default: `shared + own private`
- `shared_only=true`: shared only
- `private_only=true`: own private only
- `shared_only=true` + `private_only=true`: rejected with `400`

Status behavior:

- default read filter is `status=active`
- use `status=archived` or `status=invalidated` to inspect lifecycle states

Ranking behavior for memory retrieval:

- shared memories are preferred ahead of private ones
- higher-confidence memories rank ahead of lower-confidence ones
- newer memories break ties using `updated_at` / `timestamp`
- optional recency weighting can bias results toward fresher memories via
  `recency_half_life_hours`

Idempotency behavior for memory writes:

- when `idempotency_key` is provided, duplicate writes by the same
  `owner_agent_id` return the existing memory id instead of creating a new row

Memory response metadata behavior:

- list/search/recall responses include both `metadata_json` (raw stored JSON)
  and `metadata` (parsed object) fields

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
- `GET /metrics/memory-usefulness`
- `GET /metrics/ops`
- `GET /graph`

Request correlation behavior:

- every response includes `X-Request-Id`
- clients may provide `X-Request-Id`; otherwise the server generates one
- global error responses include `request_id` in the JSON body

`GET /metrics/ops` returns per-route request counts, error counts, average
latency, and total latency accumulated since the last server start. The
counters are in-memory only and reset on restart.

Memory usefulness metrics expose a lightweight scorecard for current memory
usage quality, including:

- active/shared/private memory counts
- adoption signals for `run_id`, `idempotency_key`, and `tags`
- trust signals for reviewed and verified memories
- run-level signals (`distinct_runs`, active run-tracked count, top run IDs)
- freshness signals for recent vs stale memory updates
- coverage percentages showing how much of the memory corpus uses these
  conventions

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

- `docs/phase1-2-consolidated.md`

## Phase 3 Status

Phase 3 starts with multi-agent memory usability for local trusted agents
(no authentication), while preserving shared memory where useful.

- **3A Agent Memory Scopes (implemented, required for this deployment)**
  - Two-scope memory model: `shared` and `private`
  - Required writer identity: `owner_agent_id`
  - Read semantics: default to `shared + own-private`
  - Promote flow: private memory can be promoted to shared
  - API and schema additions for visibility filtering now active
- **3B Retrieval Quality + Lifecycle (implemented)**
  - Visibility/owner/status filters, archive/invalidate/merge/supersede lifecycle operations, and memory ranking hints
- **3C Scale + Ops (implemented initial slice + planned follow-ups)**
  - Implemented initial slice: request correlation IDs (`X-Request-Id`) and
    memory usefulness observability
  - Planned follow-ups: broader request latency/error counters and
    maintenance/cleanup jobs

See:

- `docs/phase3a.md`
- `docs/phase3a-pr-chunks.md`
- `docs/phase3b.md`
- `docs/phase3c.md`
- `docs/phase3-overview.md`
- `docs/phase3-backlog.md`
- `docs/agent-memory-ops.md` (autonomous-agent operational usage and restart guide)
- `harness.md` (target harness design this service is expected to support)

## Testing

Run all tests:

```bash
uv run pytest -q --tb=no
```

Current status:

- `373 passed, 14 skipped`

## Project Layout

```text
memory-graph/
├── api_server.py
├── config.py
├── db_operations.py
├── db_schema.py
├── db_utils.py
├── embeddings.py
├── harness.md
├── requirements.txt
├── blueprints/
│   ├── conversations.py
│   ├── kv.py
│   ├── memory.py
│   ├── search.py
│   └── utility.py
├── docs/
│   ├── agent-memory-ops.md
│   ├── conversation-outcomes.md
│   ├── phase1-2-consolidated.md
│   ├── roadmap.md
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
