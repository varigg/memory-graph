# Memory Graph

Memory Graph is a local-first Flask REST API for persistent agent memory.
It stores conversations, memories, entities, embeddings, and key-value state in
SQLite, supports FTS5 and semantic retrieval, and exposes a small web UI.

## Documentation Guide

Use these documents as the canonical reading path for the project:

- `README.md` — current API surface, runtime workflow, and project status
- `docs/architecture.md` — current architectural shape, system boundaries, and why the service remains one substrate
- `docs/deep-dive/README.md` — targeted deep-dive docs for implemented subsystem behavior
- `docs/adr/README.md` — architecture decision record index
- `docs/roadmap.md` — canonical living feature tracker across implemented, planned, and deferred work
- `docs/conversation-outcomes.md` — durable summary of design-discussion outcomes and where they landed
- `docs/phase1-2-consolidated.md` — consolidated review and implementation summary for the original backend foundation and hardening work
- `docs/phase3-consolidated.md` — consolidated retrospective summary of Phase 3 implementation and rationale
- `docs/plans/README.md` — active implementation plans and plan lifecycle rules
- `docs/agent-memory-ops.md` — restart-safe autonomous-agent operating conventions for this service
- `harness.md` — target autonomous-agent harness vision that this backend is intended to support over time
- `.github/copilot-instructions.md` — Copilot-specific session continuity and shared-memory usage hints for this repo

If you want the shortest end-to-end overview, read this file first, then `docs/architecture.md`, then `docs/deep-dive/README.md`, then `docs/adr/README.md`, then `docs/roadmap.md`, then `docs/conversation-outcomes.md`, then `docs/phase1-2-consolidated.md`, then `docs/phase3-consolidated.md`, then `docs/agent-memory-ops.md`, and finally `harness.md`.

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
  - Verification defaults: new memories are created with `verification_status=unverified`
  - Verification fields are managed via `POST /memory/verify` (not as write-time controls)
- `POST /memory/batch`
  - Body: `{"memories": [ ... ]}` where each item follows `POST /memory`
  - Response: `201 {"results": [{"id": <int>, "created": <bool>}, ...]}`
  - Response/results are positionally aligned with request `memories`
  - Batch writes default every row to `verification_status=unverified`; callers should follow with `POST /memory/verify` for confirmed memories
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
- `POST /memory/merge`
  - Body: `memory_id` (required int), `target_memory_id` (required int), `agent_id` (required)
  - Alias: `replacement_memory_id` is accepted as an alternative to `target_memory_id`
  - Effect: relates source as `merged_into` target and archives the source memory
- `POST /memory/supersede`
  - Body: `memory_id` (required int), `target_memory_id` (required int), `agent_id` (required)
  - Alias: `replacement_memory_id` is accepted as an alternative to `target_memory_id`
  - Effect: relates source as `superseded_by` target and invalidates the source memory
- `POST /memory/cleanup-private`
  - Body: `retention_days` (required int > 0), `dry_run` (optional bool, default `true`),
    `owner_agent_id` (optional string), `status` (optional: `active|archived|invalidated|all`, default `active`)
  - Response summary: `candidate_count`, `deleted_count`, `candidate_ids`, `cutoff_timestamp`
- `GET /memory/list?limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>&profile=<p>`
- `GET /memory/recall?topic=<topic>&limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>&profile=<p>`
- `GET /memory/search?q=<query>&limit=<int>&offset=<int>&agent_id=<id>&shared_only=<bool>&private_only=<bool>&visibility=<v>&owner_agent_id=<id>&status=<s>&profile=<p>`
- `DELETE /memory/<id>`

Memory read response shape:

- `GET /memory/list`, `GET /memory/recall`, and `GET /memory/search` return a bare JSON array (`[{...}, ...]`)

Additional memory retrieval filters (for `list`, `recall`, and `search`):

- `profile=general|autonomous`
- `run_id=<id>`
- `tag=<token>`
- `min_confidence=<0..1>`
- `updated_since=<timestamp>`
- `recency_half_life_hours=<positive_number>`
- `metadata_key=<key>`
- `metadata_value=<value>`
- `metadata_value_type=string|number|boolean|null`

Retrieval profile behavior:

- `profile=general` keeps current permissive retrieval behavior (same as omitting `profile`)
- `profile=autonomous` applies defaults when caller does not provide explicit values:
  `status=active`, `min_confidence=0.7`, `recency_half_life_hours=168`
- explicit query parameters always override profile defaults
- `profile=autonomous` requires `agent_id`; missing or blank `agent_id` returns `400`
- unknown `profile` values return `400`

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

Stale private cleanup behavior:

- cleanup only considers `visibility=private` memories that are older than the
  computed cutoff (`now - retention_days`)
- `dry_run=true` reports candidates without deleting anything
- `dry_run=false` permanently deletes matching private memories and returns a
  deterministic deletion summary
- optional `owner_agent_id` narrows cleanup to one owner's private memories

### Goals + Action Logs + Autonomy Checks (Harness Bridge Primitives M1-M3)

- `POST /goal`
  - Body: `title` (required), `owner_agent_id` (required)
  - Optional: `status` (`active|blocked|completed|abandoned`), `utility`,
    `deadline`, `constraints` (JSON object), `success_criteria` (JSON object),
    `risk_tier` (`low|medium|high|critical`), `autonomy_level_requested`,
    `autonomy_level_effective`, `run_id`, `idempotency_key`
  - Response: `201 {"id": <int>}`; idempotent replay returns `200` with
    `{"id": <int>, "idempotent_replay": true}`
- `GET /goal/<id>`
- `GET /goal/list?limit=<int>&offset=<int>&owner_agent_id=<id>&status=<status>&run_id=<id>`
- `POST /goal/<id>/status`
  - Body: `owner_agent_id` (required), `status` (required), `reason` (optional)

Bridge response-shape note for goals:

- `GET /goal/<id>` and `GET /goal/list` include parsed `constraints` and
  `success_criteria` objects for read/write symmetry
- raw `constraints_json` and `success_criteria_json` fields remain in responses
  for backward compatibility

- `POST /action-log`
  - Body: `goal_id` (required), `action_type` (required), `mode` (required),
    `status` (required), `owner_agent_id` (required)
  - Optional: `parent_action_id`, `tool_name`, `input_summary`,
    `expected_result`, `observed_result`, `rollback_action_id`, `run_id`,
    `idempotency_key`
  - Response: `201 {"id": <int>}`; idempotent replay returns `200` with
    `{"id": <int>, "idempotent_replay": true}`
- `GET /action-log/list?limit=<int>&offset=<int>&owner_agent_id=<id>&goal_id=<id>&status=<status>&run_id=<id>`
- `POST /action-log/<id>/complete`
  - Body: `owner_agent_id` (required),
    `status` (`succeeded|failed|rolled_back`),
    `observed_result` (optional), `rollback_action_id` (optional)

- `POST /autonomy/check`
  - Body: `requested_level` (required int), `approved_level` (required int),
    `verdict` (`approved|denied|sandbox_only`), `owner_agent_id` (required)
  - Optional: `goal_id`, `action_id`, `rationale`,
    `stop_conditions` (JSON object), `rollback_required` (bool),
    `reviewer_type` (`policy|human|system`, default `system`),
    `run_id`, `idempotency_key`
  - Response: `201 {"id": <int>}`; idempotent replay returns `200` with
    `{"id": <int>, "idempotent_replay": true}`
- `GET /autonomy/check/list?limit=<int>&offset=<int>&owner_agent_id=<id>&goal_id=<id>&action_id=<id>&verdict=<v>&reviewer_type=<t>&run_id=<id>`

Bridge response-shape note for autonomy checkpoints:

- `GET /autonomy/check/list` includes parsed `stop_conditions` object in
  addition to `stop_conditions_json`

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
- `GET /maintenance/integrity`
- `POST /maintenance/sqlite`
- `GET /graph`

Request correlation behavior:

- every response includes `X-Request-Id`
- clients may provide `X-Request-Id`; otherwise the server generates one
- global error responses include `request_id` in the JSON body

`GET /metrics/ops` returns per-route request counts, error counts, average
latency, and total latency accumulated since the last server start. It also
returns deeper signal sections for retrieval-result behavior, database-lock
events, and dedupe indicators. These counters are in-memory only and reset on
restart.

Maintenance endpoints:

- `GET /maintenance/integrity`
  - checks orphan references and duplicate embedding-text candidates
  - supports `sample_limit` query param for bounded sample output
- `POST /maintenance/sqlite`
  - runs SQLite housekeeping commands with `dry_run=true` by default
  - supports configurable checkpoint mode (`PASSIVE`, `FULL`, `RESTART`, `TRUNCATE`)

Memory usefulness metrics expose a lightweight scorecard for current memory
usage quality, including:

- active/shared/private memory counts
- adoption signals for `run_id`, `idempotency_key`, and `tags`
- trust signals for reviewed and verified memories
- run-level signals (`distinct_runs`, active run-tracked count, top run IDs)
- freshness signals for recent vs stale memory updates
- coverage percentages showing how much of the memory corpus uses these
  conventions

### Memory Signals and Adoption Tracking

Use these write fields consistently so usefulness coverage metrics are meaningful:

| Field                 | Semantic meaning                                 | Typical value pattern                             |
| --------------------- | ------------------------------------------------ | ------------------------------------------------- |
| `run_id`              | Correlates memories produced by one task/session | `run-<date>-<topic>`                              |
| `idempotency_key`     | Prevents duplicate writes on retries             | `<agent>:<run_id>:<stable-step-id>`               |
| `tags`                | Retrieval facets for topic/type filtering        | `decision,phase3,sprint-a`                        |
| `verification_status` | Trust state after review                         | `verified`, `unverified`, `disputed`              |
| `verification_source` | Provenance of trust update                       | `integration test`, `user review`, `policy check` |

Recommended autonomous-agent workflow:

- keep detailed in-flight context in `/memories/session/` during the task
- proactively batch-write durable findings and decisions at task end
- follow batch writes with `POST /memory/verify` for findings already confirmed during the task
- leave decisions or findings needing external review as `unverified`
- recover from prior work using `run_id`-scoped reads instead of old scratch notes

See `docs/agent-memory-ops.md` for worked write/read patterns.

Example usefulness scorecard shape after signal-aware writes:

```json
{
  "coverage_pct": {
    "run_tracked": 66.7,
    "idempotent": 66.7,
    "tagged": 100.0,
    "verified": 33.3
  },
  "run_signals": {
    "distinct_runs": 1,
    "active_run_tracked": 2
  }
}
```

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
- **3C Scale + Ops (implemented)**
  - request correlation IDs (`X-Request-Id`) and memory usefulness observability
  - broader request latency/error counters and deeper ops signals
  - maintenance endpoints for integrity checks and SQLite housekeeping

See:

- `docs/phase3-consolidated.md`
- `docs/deep-dive/lifecycle-and-trust.md`
- `docs/deep-dive/retrieval-contracts.md`
- `docs/deep-dive/operations-and-maintenance.md`
- `docs/agent-memory-ops.md` (autonomous-agent operational usage and restart guide)
- `harness.md` (target harness design this service is expected to support)

## Testing

Run all tests:

```bash
uv run pytest -q --tb=no
```

Current status:

- `434 passed, 14 skipped`

## Project Layout

```text
memory-graph/
├── api_server.py
├── config.py
├── db_schema.py
├── db_utils.py
├── embeddings.py
├── harness.md
├── pyproject.toml
├── requirements.txt
├── blueprints/
│   ├── _params.py
│   ├── conversations.py
│   ├── kv.py
│   ├── memory.py
│   ├── search.py
│   └── utility.py
├── docs/
│   ├── adr/
│   ├── agent-memory-ops.md
│   ├── architecture.md
│   ├── conversation-outcomes.md
│   ├── deep-dive/
│   ├── phase1-2-consolidated.md
│   ├── phase3-consolidated.md
│   ├── roadmap.md
│   ├── refactor-service-layer.md
│   └── plans/
├── services/
│   ├── hybrid_search_service.py
│   ├── memory_lifecycle_service.py
│   ├── memory_retrieval_service.py
│   └── memory_write_service.py
├── static/
│   └── index.html
├── storage/
│   ├── conversation_repository.py
│   ├── embedding_repository.py
│   ├── entity_repository.py
│   ├── kv_repository.py
│   ├── memory_repository.py
│   └── metrics_repository.py
└── tests/
    └── ...
```
