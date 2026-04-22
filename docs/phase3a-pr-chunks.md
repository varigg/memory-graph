# Phase 3A PR Chunks — Historical Implementation Plan

This document is retained as a historical record of how the Phase 3A rollout
was originally decomposed into reviewable PRs.

It is no longer an active plan. For current planning, use `docs/roadmap.md`
and `docs/phase3-backlog.md`.

Assumptions:

- local deployment only
- no authentication
- <= 12 agents
- low concurrency

## PR-1: Schema Migration and Data Backfill

## Objective

Introduce ownership and visibility metadata on memories with safe defaults for
existing databases.

## Proposed SQL Migration

```sql
-- 1) Add new columns (safe defaults for legacy rows)
ALTER TABLE memories ADD COLUMN owner_agent_id TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE memories ADD COLUMN visibility TEXT NOT NULL DEFAULT 'shared'
  CHECK (visibility IN ('shared', 'private'));
ALTER TABLE memories ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- 2) Backfill updated_at where NULL (defensive)
UPDATE memories
SET updated_at = COALESCE(updated_at, timestamp, CURRENT_TIMESTAMP)
WHERE updated_at IS NULL;

-- 3) Helpful read-path indexes
CREATE INDEX IF NOT EXISTS idx_memories_visibility_owner
  ON memories (visibility, owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_memories_updated_at
  ON memories (updated_at);
```

## DDL/Init Integration

- Apply migration logic in `db_schema.init()` in an idempotent way.
- Keep compatibility for new DB creation and existing DB upgrades.

## Acceptance Criteria

- Existing DBs upgrade without data loss.
- New columns present and queryable.
- New writes can target `shared` and `private` visibility.
- Tests pass for schema idempotency and defaults.

---

## PR-2: API Write Contract + Promote Endpoint

## Objective

Enforce ownership on writes and add explicit promote-to-shared workflow.

## Endpoint Contract: `POST /memory`

Request body (JSON):

```json
{
  "name": "deploy-runbook",
  "content": "restart service then verify health",
  "type": "note",
  "description": "ops memory",
  "owner_agent_id": "agent-alpha",
  "visibility": "private"
}
```

Validation rules:

- `name` required (existing)
- `content` required (existing)
- `owner_agent_id` required and non-empty (new)
- `visibility` optional; default `shared`; allowed values: `shared`, `private`

Response (`201`):

```json
{ "id": 123 }
```

Error cases (`400`):

- missing/blank `owner_agent_id`
- invalid `visibility`

## Endpoint Contract: `POST /memory/<id>/promote`

Query params:

- `agent_id` (required)

Behavior:

- verify memory exists
- verify `agent_id == owner_agent_id`
- set `visibility='shared'`
- set `updated_at=CURRENT_TIMESTAMP`

Response (`200`):

```json
{ "id": 123, "visibility": "shared" }
```

Errors:

- `400` if `agent_id` missing
- `404` if memory not found
- `403` (preferred) if requester does not own memory

---

## PR-3: API Read Scoping (list/search/recall)

## Objective

Apply two-scope read behavior: shared + own-private by default.

## Read Inputs

All three endpoints accept:

- `agent_id` (required for scoped modes)
- `shared_only=true|false` (optional)
- `private_only=true|false` (optional)

Conflict rule:

- reject when both `shared_only=true` and `private_only=true`

## Scope Semantics

Default (no mode flags):

- return records where `visibility='shared'`
- plus records where `visibility='private' AND owner_agent_id=<agent_id>`

`shared_only=true`:

- return only `visibility='shared'`

`private_only=true`:

- return only `visibility='private' AND owner_agent_id=<agent_id>`

## SQL Predicate Template

```sql
-- Default scope
(visibility = 'shared' OR (visibility = 'private' AND owner_agent_id = ?))

-- Shared only
(visibility = 'shared')

-- Private only
(visibility = 'private' AND owner_agent_id = ?)
```

## Endpoint Notes

- `GET /memory/list`: apply scope + existing pagination
- `GET /memory/search`: scope + FTS query + pagination
- `GET /memory/recall`: scope + FTS topic query + pagination

---

## PR-4: Tests and Docs Finalization

## Test Matrix

### Schema tests

- new columns exist
- defaults applied to legacy rows
- migration idempotency

### API write tests

- create shared/private memories
- reject invalid visibility
- reject missing owner

### API read tests

- default scope returns shared + own-private
- no cross-agent private leakage
- shared_only and private_only behavior
- conflicting scope flags rejected

### Promote tests

- owner can promote
- non-owner blocked

### Regression tests

- existing pagination and query validation still pass

## Documentation updates

- README Phase 3 section (status + contract notes)
- phase3a.md and backlog references
- example payloads and query usage

---

## Suggested Merge Sequence

1. PR-1 Schema migration + minimal schema tests
2. PR-2 Write contract + promote endpoint + tests
3. PR-3 Read scoping + tests
4. PR-4 Docs cleanup + final regression sweep

## Rollout Note

During transition, a compatibility window can treat missing `agent_id` on reads
as `shared_only=true` to avoid breaking older local clients. Remove this
fallback after agents are updated.
