# Phase 3 Backlog — Ticket-Ready Plan

This backlog converts the Phase 3 minimum deliverables into implementable work
items for the target deployment profile:

- local-only
- <= 12 agents
- low concurrency
- no authentication

Related implementation breakdown:

- `docs/phase3a-pr-chunks.md`

## Milestone M1 — Phase 3A Core (Required)

### P3A-1 Schema: ownership + visibility columns

- **Priority**: P0
- **Depends on**: none
- **Scope**:
  - Add `owner_agent_id` to `memories`
  - Add `visibility` (`shared`/`private`) with check constraint
  - Add `updated_at`
  - Backfill legacy rows to `visibility='shared'`
- **Acceptance criteria**:
  - schema init/migration is idempotent
  - existing DBs migrate without data loss
  - tests cover defaults and constraints

### P3A-2 API: scoped write semantics

- **Priority**: P0
- **Depends on**: P3A-1
- **Scope**:
  - `POST /memory` requires `owner_agent_id`
  - `POST /memory` accepts optional `visibility`
  - reject missing/blank owner and invalid visibility
- **Acceptance criteria**:
  - create succeeds with valid owner/visibility
  - invalid payloads return `400` with clear errors

### P3A-3 API: scoped read semantics

- **Priority**: P0
- **Depends on**: P3A-1
- **Scope**:
  - memory list/search/recall accept `agent_id`
  - default read set: shared + own-private
  - support `shared_only=true` and `private_only=true`
- **Acceptance criteria**:
  - other-agent private records are never returned
  - shared records always visible
  - pagination/query validation remain intact

### P3A-4 API: promote-to-shared flow

- **Priority**: P1
- **Depends on**: P3A-1, P3A-3
- **Scope**:
  - add `POST /memory/<id>/promote`
  - enforce requester owner check via `agent_id`
  - update `updated_at`
- **Acceptance criteria**:
  - owner can promote private memory
  - non-owner promotion rejected (`403` or `404` per chosen policy)

### P3A-5 Test coverage + docs refresh

- **Priority**: P0
- **Depends on**: P3A-2, P3A-3, P3A-4
- **Scope**:
  - unit/integration tests for scoped writes and reads
  - regression tests for pagination and search behavior
  - update README/API docs with new fields/params
- **Acceptance criteria**:
  - full suite green
  - docs reflect final API contract

## Milestone M2 — Phase 3B Minimum Slice (Partially Required)

Current status note:

- The repository is ahead of this original minimum slice in a few areas.
- Retrieval controls now also include `run_id`, `tag`, `min_confidence`,
  `updated_since`, and `recency_half_life_hours`.
- Typed metadata support is implemented for both storage (`metadata`) and
  retrieval (`metadata_key`, `metadata_value`, `metadata_value_type`).
- Memory list/search/recall responses now include parsed `metadata` in
  addition to raw `metadata_json` for client compatibility and ergonomics.
- Lifecycle support now includes merge/supersede operations and verification
  state updates in addition to archive/invalidate.
- Batch write support (`POST /memory/batch`) is implemented even though earlier
  planning treated bulk mutation APIs as deferrable.

### P3B-1 Retrieval filters (visibility/owner/status)

- **Status**: Implemented and exceeded

- **Priority**: P1
- **Depends on**: M1
- **Scope**:
  - add optional read filters:
    - `visibility`
    - `owner_agent_id`
    - `status` (when status is introduced)
- **Acceptance criteria**:
  - filters compose correctly with scoped defaults
  - invalid filter values return `400`

### P3B-2 Archive/invalidate lifecycle endpoints

- **Status**: Implemented and exceeded

- **Priority**: P1
- **Depends on**: M1
- **Scope**:
  - add `POST /memory/archive`
  - add `POST /memory/invalidate`
  - status transitions with audit-friendly timestamps
- **Acceptance criteria**:
  - transitions are validated and tested
  - archived/invalidated records obey retrieval filters

### P3B-3 Lightweight ranking enhancement

- **Status**: Implemented minimum slice and extended

- **Priority**: P2
- **Depends on**: P3B-1
- **Scope**:
  - recency and confidence hints in ranking order
  - preserve existing FTS/semantic behavior as baseline
- **Acceptance criteria**:
  - ranking tests with deterministic fixtures
  - no significant latency regression at local scale

## Milestone M3 — Phase 3C Minimum Slice (Ops Visibility)

### P3C-1 Request correlation id

- **Status**: Initial slice implemented

- **Priority**: P2
- **Depends on**: none
- **Scope**:
  - attach/request `X-Request-Id`
  - include in logs and error responses where applicable
- **Acceptance criteria**:
  - request id is present across logs for traced requests

### P3C-2 Basic service metrics

- **Status**: Implemented

- **Priority**: P2
- **Depends on**: none
- **Scope**:
  - endpoint latency and error counters
  - memory-scope usage counters (shared vs private)
  - memory usefulness scorecard for adoption/trust coverage
- **Acceptance criteria**:
  - metrics endpoint or log summaries documented
  - smoke tests verify instrumentation paths

### P3C-3 Stale private memory cleanup job

- **Priority**: P2
- **Depends on**: M1
- **Scope**:
  - periodic cleanup command for old private memories
  - dry-run mode and deletion summary
- **Acceptance criteria**:
  - cleanup respects visibility and retention config
  - integration test verifies expected removals

## Deferred Items (Not Needed Now)

- async queue architecture for embedding/enrichment
- cursor pagination migration
- enterprise auth/tenant controls
- ranking explainability fields in search results (`rank_components`, `match_reasons`)
- formal verifier evidence model beyond the current verification status fields

## Implemented Beyond Original Backlog Text

These items were originally absent from the backlog or described as future work,
but are now present in the codebase:

- `POST /memory/batch` for grouped writes
- write idempotency via `idempotency_key`
- retrieval filters for `run_id`, `tag`, `min_confidence`, `updated_since`, and
  `recency_half_life_hours`
- typed metadata write support (`metadata`) and typed metadata read filters
  (`metadata_key`, `metadata_value`, `metadata_value_type`)
- parsed metadata response field (`metadata`) alongside `metadata_json` in
  memory list/search/recall results
- verification state updates via `POST /memory/verify`
- merge/supersede lifecycle operations
- restart-safe autonomous-agent operating guidance in `docs/agent-memory-ops.md`

## Suggested Sprint Order

1. Sprint A: P3C-1 request correlation id support
2. Sprint B: deepen P3C-2 metrics beyond initial usefulness slice
3. Sprint C: P3C-3 stale private memory cleanup
4. Sprint D: harness-bridge primitives if/when goal/autonomy work begins

## Definition of Done (Phase 3 minimum)

- M1 complete (required)
- M2 complete for P3B-1 and P3B-2 at minimum
- M3 complete for P3C-1 and P3C-2 at minimum
- documentation updated and full suite green

Current interpretation:

- M1 is complete.
- M2 is complete and exceeded.
- M3 is complete: request correlation (P3C-1) and route-level latency/error
  counters (P3C-2) are both implemented. P3C-3 stale private cleanup remains
  the next open item.
