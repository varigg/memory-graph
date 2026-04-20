# Agent Memory Ops Guide (Restart-Safe)

This document describes how autonomous agents should use the memory-graph API in long-running sessions, and how to recover quickly after server/session restarts.

## Goals

- Keep memory retrieval high-signal over long sessions.
- Avoid duplicate writes during retries.
- Make runs auditable by run identifier.
- Add a lightweight verification loop for memory trust.

## Runtime Health Check

Always verify API availability before writes:

```bash
curl -s http://localhost:7777/health
```

Expected: `{"status":"ok", ...}`.

## Python Environment Baseline

- This repo should run with `uv` and the project-local `.venv`.
- If a shell exports `VIRTUAL_ENV` from an older path, clear it:

```bash
unset VIRTUAL_ENV
```

- Verify interpreter target quickly:

```bash
uv run python -c "import sys; print(sys.executable)"
```

## Recommended Write Pattern

### 1) Write decision records with idempotency

Use `idempotency_key` so retries do not create duplicates.

```bash
curl -s -X POST http://localhost:7777/memory \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "decision/deploy-strategy/2026-04-20",
    "type": "decision",
    "content": "Use blue-green deploy for service X",
    "description": "Rationale: minimize rollback time",
    "owner_agent_id": "copilot",
    "visibility": "shared",
    "tags": "decision,deploy,ops",
    "run_id": "run-2026-04-20-deploy",
    "idempotency_key": "copilot:run-2026-04-20-deploy:decision-1"
  }'
```

- First request returns `201` and new `id`.
- Replay with same idempotency key returns `200` and existing `id`.

### 2) Batch writes for task checkpoints

```bash
curl -s -X POST http://localhost:7777/memory/batch \
  -H 'Content-Type: application/json' \
  -d '{
    "memories": [
      {
        "name": "trace/checkpoint-1",
        "type": "trace",
        "content": "Collected API constraints",
        "owner_agent_id": "copilot",
        "visibility": "private",
        "tags": "trace,analysis",
        "run_id": "run-2026-04-20-deploy",
        "idempotency_key": "copilot:run-2026-04-20-deploy:cp-1"
      },
      {
        "name": "trace/checkpoint-2",
        "type": "trace",
        "content": "Implemented schema migration",
        "owner_agent_id": "copilot",
        "visibility": "private",
        "tags": "trace,implementation",
        "run_id": "run-2026-04-20-deploy",
        "idempotency_key": "copilot:run-2026-04-20-deploy:cp-2"
      }
    ]
  }'
```

## Recommended Read Pattern

### 1) Targeted recall by run and tag

```bash
curl -s "http://localhost:7777/memory/recall?topic=deploy&agent_id=copilot&run_id=run-2026-04-20-deploy&tag=decision"
```

### 2) Confidence floor + recency weighting

```bash
curl -s "http://localhost:7777/memory/list?agent_id=copilot&min_confidence=0.6&recency_half_life_hours=72"
```

### 3) Time-bounded reads

```bash
curl -s "http://localhost:7777/memory/search?q=deploy&agent_id=copilot&updated_since=2026-04-18 00:00:00"
```

## Verification Loop

Mark memory trust state using `/memory/verify`.

```bash
curl -s -X POST http://localhost:7777/memory/verify \
  -H 'Content-Type: application/json' \
  -d '{
    "memory_id": 123,
    "agent_id": "copilot",
    "verification_status": "verified",
    "verification_source": "integration test run #1842"
  }'
```

Allowed status values:

- `unverified`
- `verified`
- `disputed`

## Restart Checklist

After a server restart:

1. Check `/health`.
2. Validate expected API shape quickly:
   - `GET /memory/list?limit=1`
   - `POST /memory/batch` with one private throwaway row
   - `POST /memory/verify` against that row
3. If schema errors appear, restart server once after confirming DB path is correct.
4. Resume runs by querying prior `run_id`.

After a session restart:

1. Read this file.
2. Use `run_id` to reconstruct active task state.
3. Continue writes with the same idempotency key namespace.

## Naming Conventions

- `name`: `<domain>/<topic>/<artifact>/<date or seq>`
- `idempotency_key`: `<agent>:<run_id>:<stable-step-id>`
- `tags`: comma-separated lowercase tokens
- `run_id`: stable identifier for one autonomous task thread

## Current Scope and Gaps

Implemented now:

- Batch create (`POST /memory/batch`)
- Idempotency keys (`POST /memory` + batch item support)
- Metadata filters (`run_id`, `tag`)
- Retrieval controls (`min_confidence`, `updated_since`, `recency_half_life_hours`)
- Verification endpoint (`POST /memory/verify`)

Still future work:

- Server-side typed metadata document and JSON filtering
- Formal verifier checks and evidence model
- Goal/plan/autonomy world-model endpoints from harness
