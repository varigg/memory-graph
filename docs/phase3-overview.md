# Phase 3 Overview — Deployment-Fit Prioritization

This file maps Phase 3 work to the intended deployment profile:

- local-only instances
- <= 12 agents
- very low concurrency
- no authentication requirement

## Priority Matrix

### Phase 3A — Agent Memory Scopes

- **Status**: Implemented
- **Fit**: **Required**
- **Why**: Needed to safely combine shared and private agent memory without
  project-level partitioning.
- **Minimum deliverable**:
  - `owner_agent_id`
  - `visibility` (`shared`/`private`)
  - promote-to-shared flow
  - default read scope (`shared + own private`)

### Phase 3B — Retrieval Quality + Lifecycle

- **Status**: In Progress
- **Fit**: **Partially required**
- **Why**: Utility gains are significant even at low scale, but scope can be
  intentionally trimmed.
- **Minimum deliverable**:
  - confidence + recency ranking hints
  - visibility/owner/status filters
  - archive/invalidate endpoints
- **Implemented so far**:
  - visibility/owner/status filters
  - archive/invalidate endpoints
- **Can defer**:
  - full merge/supersede automation
  - heavy explanation payloads

### Phase 3C — Scale + Ops

- **Status**: Planned
- **Fit**: **Mostly optional/defer**
- **Why**: local, low-concurrency usage does not need queue architectures yet.
- **Minimum deliverable**:
  - basic metrics and correlation IDs
  - stale-private-memory cleanup job
- **Can defer**:
  - async worker queues
  - bulk mutation APIs
  - enterprise-grade alerting/SLO stack

## Recommended Execution Order

1. 3B minimum deliverable (high utility)
2. 3C minimum deliverable (ops visibility)
3. remaining 3B/3C optional items on demand

## Implementation Packaging

- PR-chunk implementation plan for 3A:
  - `docs/phase3a-pr-chunks.md`
