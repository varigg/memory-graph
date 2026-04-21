# Phase 3 Overview — Historical Deployment-Fit Context

This file is retained as historical context for how Phase 3 was originally
scoped against the intended deployment profile.

For active planning, use `docs/roadmap.md` for current priorities and
`docs/phase3-backlog.md` for the remaining ticket-ready work.

Original deployment assumptions:

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

- **Status**: Implemented
- **Fit**: **Partially required**
- **Why**: Utility gains are significant even at low scale, but scope was worth completing because it materially improves retrieval quality and memory hygiene.
- **Implemented outcome**:
  - confidence + recency ranking hints
  - visibility/owner/status filters
  - archive/invalidate endpoints
  - merge/supersede and verification-related lifecycle support beyond the original minimum slice

### Phase 3C — Scale + Ops

- **Status**: Partially implemented; remaining follow-on work is tracked in `docs/phase3-backlog.md`
- **Fit**: **Mostly optional/defer**
- **Why**: local, low-concurrency usage does not need queue architectures yet.
- **Implemented so far**:
  - basic metrics and correlation IDs
- **Remaining useful work**:
  - stale-private-memory cleanup job
  - optional integrity checks and deeper operational metrics
- **Can defer**:
  - async worker queues
  - bulk mutation APIs
  - enterprise-grade alerting/SLO stack

## Current Use Of This File

Treat this document as historical framing only.

- Use `docs/roadmap.md` for what is next.
- Use `docs/phase3-backlog.md` for active Phase 3-style execution planning.
- Use `docs/phase3a-pr-chunks.md` only as a record of how the original 3A rollout was decomposed.
