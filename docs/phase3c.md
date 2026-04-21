# Phase 3C — Remaining Scale and Operations Follow-On

This file now summarizes the still-open Phase 3C themes at a high level.

For active planning and ticket-ready work, use `docs/phase3-backlog.md`.
`docs/roadmap.md` remains the canonical source for priority and status.

## Goal

Track the remaining operational resilience and maintenance work that still makes
sense for a local-first deployment after the initial observability slice landed.

## Still-Relevant Follow-On Areas

### 1) Maintenance Jobs

- stale private memory cleanup is now implemented (`POST /memory/cleanup-private`, Sprint B)
- integrity checks such as orphan detection and duplicate-candidate scans remain optional follow-on work
- optional SQLite maintenance routines can be added later if they solve a concrete local-ops problem

### 2) Additional Observability

- deeper counters around retrieval result quality, lock retries, and dedupe behavior may still be useful
- trend/history views are a follow-on to the currently implemented metrics endpoints rather than a prerequisite for local use

### 3) Deferred Scale Work

- async enrichment queues remain deferred
- cursor pagination remains deferred unless offset pagination becomes a real bottleneck
- bulk mutation APIs remain demand-driven rather than phase-defining

## Deployment Fit (Local, <= 12 Agents, Low Concurrency)

- **Still needed**:
  - enough observability to debug normal local failures and usage patterns
- **Useful but optional**:
  - integrity checks and maintenance helpers
  - deeper metrics and trend reporting
- **Deferred**:
  - queue architectures
  - advanced alerting/SLO tooling
  - scale-first pagination changes without evidence of need

## Planning Note

Treat this document as a high-level Phase 3C summary.

- Use `docs/phase3-backlog.md` for the active item list.
- Use `docs/roadmap.md` for ordering and status.
