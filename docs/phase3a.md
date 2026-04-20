# Phase 3A — Agent Memory Scopes (Implemented)

## Goal

Support multiple local trusted agents with two memory scopes:

- `shared`: visible to all agents
- `private`: visible only to the owning agent

Authentication is intentionally out of scope for this phase.

## Product Constraints

- Deployment is local/trusted; auth is unnecessary.
- Some memories should be shared across agents.
- Project-level scope partitioning is not required at this time.

## Implemented Contract

### 1) Memory Ownership + Visibility

Ownership and visibility metadata are now part of memory records.

Schema additions to `memories`:

- `owner_agent_id TEXT NOT NULL DEFAULT 'unknown'`
- `visibility TEXT NOT NULL DEFAULT 'shared' CHECK (visibility IN ('shared','private'))`
- `updated_at DATETIME`

Behavior:

- All writes must include `owner_agent_id`.
- Visibility defaults to `shared` when omitted.
- Legacy rows are migrated to `visibility='shared'`.

### 2) Read Semantics

For memory recall/search/list:

- Default mode: `shared + own private`
- Optional mode: `shared_only=true`
- Optional mode: `private_only=true` (owner only)

Required request parameter/header for scoped reads:

- `agent_id` (query param initially, header support can follow)

### 3) Write Semantics

`POST /memory` accepts:

- `owner_agent_id` (required)
- `visibility` (`shared` or `private`)

Validation:

- reject unknown visibility values
- reject missing/blank owner id

### 4) Promote-to-Shared Operation

Implemented endpoint:

- `POST /memory/<id>/promote`

Rules:

- requester `agent_id` must match `owner_agent_id`
- sets `visibility='shared'`
- updates `updated_at`

### 5) Filtering + Ranking Hooks

Visibility-aware filtering is implemented; ranking expansion stays in 3B.

- Memory endpoints enforce visibility clause before text search criteria.
- Keep pagination and query validation from Phase 2C.

## API Contract

### Request additions

- Memory write: include `owner_agent_id`, optional `visibility`
- Memory read/search/recall/list: include `agent_id`

### Response additions

- Memory records include `owner_agent_id` and `visibility`

## Migration Notes

1. Add new columns with safe defaults.
2. Backfill `updated_at` for existing rows.
3. Existing read behavior remains backward-compatible:
   - if `agent_id` is missing, reads stay unscoped (legacy behavior)
4. Clients that require scoped reads should always provide `agent_id`.

## Test Plan

### Unit/API tests

- create memory with shared/private visibility
- reject invalid visibility
- reject missing owner on create
- list/search/recall returns:
  - shared + own-private (default)
  - shared only
  - private only (owner)
- private records from other agents are excluded
- promote endpoint owner check

### Regression tests

- pagination and query validation continue to pass under visibility filters
- existing shared-memory behavior unchanged for legacy clients

## Dependencies from Earlier Phases

- Phase 2C pagination/validation is reused for scoped reads.
- Phase 2D performance changes reduce overhead from new visibility predicates.

## Exit Criteria

- Two-scope model is implemented and documented.
- Memory retrieval endpoints enforce visibility semantics when `agent_id` is provided.
- Promote flow is implemented with owner checks.
- Full suite is green after migration and API updates.
