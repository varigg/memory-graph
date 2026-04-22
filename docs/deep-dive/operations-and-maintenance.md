# Operations And Maintenance

This document captures the current operational surfaces used to inspect and
maintain a local Memory Graph deployment.

## Metrics Surfaces

### Memory Usefulness

`GET /metrics/memory-usefulness` returns aggregated adoption and trust coverage
signals derived from memory rows.

Primary groups:

- `memory_counts`
- `adoption_signals` (`run_tracked`, `idempotent`, `tagged`; derived from
  `run_id`, `idempotency_key`, and `tags`)
- `trust_signals` (response keys: `verified`, `disputed`, `reviewed`)
- `run_signals` (distinct runs, top run ids)
- `freshness_signals`
- `coverage_pct`

### Operational Route And Runtime Signals

`GET /metrics/ops` returns:

- per-route request/error/latency counters
- retrieval result signals (calls, zero-result rate, average results)
- DB lock event counters
- dedupe and reindex signals

These counters are local-process runtime metrics, not persisted historical
timeseries.

## Integrity And Maintenance Endpoints

### Integrity Snapshot

`GET /maintenance/integrity` reports:

- orphan reference counts and samples
- duplicate embedding candidate counts and samples
- clean/unclean summary flag

`sample_limit` controls sample payload size and must be a positive integer.

### SQLite Maintenance Helper

`POST /maintenance/sqlite` executes lightweight maintenance primitives.

- `dry_run` defaults to `true`
- `checkpoint_mode` supports `PASSIVE|FULL|RESTART|TRUNCATE`
- destructive-risk behavior is minimized by dry-run-first contract

Execution mode runs `PRAGMA optimize` and `PRAGMA wal_checkpoint(...)` and
returns structured checkpoint counters.

## Operating Principle

Operational features are intentionally bounded to concrete local-first needs:

- expose enough visibility for safe substrate operation
- avoid speculative long-horizon observability systems unless a concrete usage
  requirement emerges