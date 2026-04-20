# Phase 3B — Retrieval Quality and Memory Lifecycle (Partially Implemented)

## Goal

Improve utility of retrieved context and keep memory quality high over time.

## Scope

### 1) Retrieval Quality

- Add ranking inputs beyond lexical/semantic match:
  - visibility (`shared` preferred when cross-agent utility is likely)
  - confidence score
  - recency (`updated_at` decay)
  - optional memory status weighting
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
- Remaining for full 3B:
  - recency/confidence-aware ranking changes
  - merge/supersede lifecycle operations
