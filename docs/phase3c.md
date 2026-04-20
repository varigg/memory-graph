# Phase 3C — Scale and Operations (Planned)

## Goal

Add operational resilience and maintainability guardrails as usage grows.

## Scope

### 1) Async/Queue Enrichment (Optional)

- Move embedding/enrichment writes to background workers.
- Add retry and dead-letter handling.
- Add idempotency keys on enrichment jobs.

### 2) Pagination and Bulk Operations

- Cursor pagination for high-cardinality endpoints.
- Bulk memory mutation endpoints where needed.

### 3) Observability

- Request correlation IDs.
- Metrics for:
  - endpoint latency
  - write conflicts/lock retries
  - retrieval result counts
  - dedupe rates

### 4) Maintenance Jobs

- Periodic cleanup for stale private memories.
- Integrity checks (orphan references, duplicate candidates).
- Optional SQLite maintenance jobs.

## Deployment Fit (Local, <= 12 Agents, Low Concurrency)

- **Needed now**:
  - basic observability and error metrics
  - lightweight cleanup routines for stale private memories
- **Optional now**:
  - cursor pagination (offset likely sufficient at current scale)
  - bulk APIs
- **Defer**:
  - full async queue architecture
  - advanced SLO/alerting stack

## Test Plan

- Integration tests for maintenance job behavior.
- Lock/contention tests for representative local concurrency.
- Smoke tests for observability instrumentation.

## Exit Criteria

- Operations are visible and debuggable under normal local load.
- Memory hygiene remains stable without manual cleanup burden.
- No regressions in existing API contracts.
