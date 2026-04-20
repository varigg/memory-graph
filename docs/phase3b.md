# Phase 3B — Retrieval Quality and Memory Lifecycle (Partially Implemented)

## Goal

Improve utility of retrieved context and keep memory quality high over time.

## Scope

### 1) Retrieval Quality

Implemented ranking inputs for memory retrieval:

- visibility (`shared` preferred ahead of private)
- confidence score
- recency (`updated_at` fallback to `timestamp`)

Still planned:

- optional memory status weighting beyond filtering
- Add explainability fields in search results:
  - `rank_components`
  - `match_reasons`

### 2) Lifecycle Operations

Implemented lifecycle APIs:

- `POST /memory/archive`
- `POST /memory/invalidate`

Still planned:

- `POST /memory/merge`
- `POST /memory/supersede`

These prevent memory sprawl and preserve high-signal shared memory.

### 3) Retrieval Filters

Implemented optional filters on memory list/search/recall:

- `visibility`
- `owner_agent_id`
- `status`

Still planned:

- `min_confidence`
- `updated_since`
- `tags` (if tags are introduced)

## Deployment Fit (Local, <= 12 Agents, Low Concurrency)

- **Needed now**:
  - lightweight lifecycle operations (`archive`/`invalidate` at minimum)
  - confidence/recency-aware ranking
  - visibility and owner filters
- **Optional now**:
  - full merge/supersede workflows
  - rich ranking explanation payloads
- **Defer**:
  - heavyweight ranking pipelines or model-based rerankers

## Test Plan

- Ranking regression tests with fixed fixtures.
- Lifecycle transition tests (`active -> archived`, etc.).
- Filter correctness tests for scope + owner behavior.
- Backward compatibility tests for clients not using optional filters.

## Exit Criteria

- Scoped retrieval produces measurably higher-quality context.
- Lifecycle controls prevent duplicate/stale shared memories from accumulating.
- Full test suite remains green.

## Current Phase State

- Done in this phase so far:
  - lifecycle transitions: `active -> archived|invalidated`
  - owner-checked `archive` and `invalidate` endpoints
  - retrieval status filter with default `active`
  - ranking hints using visibility, confidence, and recency ordering
- Remaining for full 3B:
  - merge/supersede lifecycle operations
  - optional ranking explanation payloads
