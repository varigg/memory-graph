# Roadmap

This is the canonical living feature tracker for the repository.

Use this file when you want the current state of the project in one place:

- what major feature areas exist
- what is implemented vs planned
- which document is authoritative for details
- what should happen next

## How This Relates To Other Docs

- `plan-memoryGraphFlaskApi.prompt.md` is the original feature/spec prompt.
- `docs/phase1-2-consolidated.md` is the retrospective summary of early review and implementation work.
- `docs/phase3-backlog.md` is the detailed Phase 3 task breakdown.
- `docs/conversation-outcomes.md` records major discussion outcomes and rationale.
- `harness.md` is the target-state autonomous-agent vision.

If those documents disagree, treat current code and `README.md` as authoritative,
then update this roadmap and the stale doc.

## Status Legend

- Implemented
- In progress
- Planned
- Deferred

## Feature Matrix

| Feature Area | Status | Scope Summary | Primary Source of Truth | Implemented Surface | Next Step |
| --- | --- | --- | --- | --- | --- |
| Core Flask service foundation | Implemented | App factory, SQLite init, blueprints, JSON error handling, CORS, local-first runtime | `README.md`, `docs/phase1-2-consolidated.md` | `api_server.py`, `config.py`, `db_schema.py`, `blueprints/*` | Maintain as baseline; no structural gap |
| Conversations | Implemented | Log, recent retrieval, FTS search, stats | `README.md`, `docs/phase1-2-consolidated.md` | `/conversation/log`, `/conversation/recent`, `/conversation/search`, `/conversation/stats` | Add correlation IDs if ops tracing becomes necessary |
| Memory CRUD and scoped access | Implemented | Memory create/list/search/recall/delete with shared/private scope semantics | `README.md`, `docs/phase3a.md` | `/memory`, `/memory/list`, `/memory/recall`, `/memory/search`, `/memory/<id>`, `/memory/<id>/promote` | Keep docs and tests aligned with current API |
| Memory lifecycle operations | Implemented | Archive, invalidate, merge, supersede, promote, verification status updates | `README.md`, `docs/phase3-backlog.md` | `/memory/archive`, `/memory/invalidate`, `/memory/merge`, `/memory/supersede`, `/memory/verify` | Add richer evidence model for verification |
| Autonomous-session write discipline | Implemented | Batch write, idempotency, run tracking, tags, restart-safe checkpoint conventions | `docs/agent-memory-ops.md`, `.github/copilot-instructions.md` | `/memory/batch`, `idempotency_key`, `run_id`, `tags` | Increase real usage so usefulness metrics become informative |
| Retrieval quality controls | Implemented | Visibility/owner/status filters plus `run_id`, `tag`, `min_confidence`, `updated_since`, `recency_half_life_hours` | `README.md`, `docs/phase3-backlog.md` | memory list/search/recall query params | Consider typed metadata filters instead of string-only tags |
| Semantic and hybrid search | Implemented | Embedding-backed semantic search plus hybrid RRF retrieval | `README.md`, `docs/phase1-2-consolidated.md` | `/search/semantic`, `/search/hybrid`, `/embeddings/stats`, `/embeddings/reindex` | Consider async enrichment if request-path latency becomes a problem |
| Embedding correctness and dedup | Implemented | Reindex updates FKs, dedups duplicate text, repairs legacy rows, unique text index | `docs/phase1-2-consolidated.md` | `db_schema.py`, `db_operations.py`, `/embeddings/reindex` | Monitor only; no urgent gap |
| Entity and KV support | Implemented | Basic entity insert/search and KV reads/writes | `README.md` | `/entity`, `/entity/search`, `/kv/<key>` | Expand only if harness or UI starts depending on richer state |
| Web UI | Implemented baseline | D3-based local UI for graph/log/rag/crons navigation | `README.md`, `docs/phase1-2-consolidated.md` | `/graph`, `static/index.html` | Accessibility and browser hardening remain deferred |
| Documentation hub and outcomes tracking | Implemented | README as doc hub, outcomes ledger, roadmap, consolidated summaries | `README.md`, `docs/conversation-outcomes.md`, `docs/roadmap.md` | repo docs | Keep this roadmap current when features shift |
| Memory usefulness observability | Implemented initial slice | Current-state counts, adoption signals, trust signals, coverage percentages | `README.md`, `docs/phase3-backlog.md` | `/metrics/memory-usefulness` | Add history/trends and correlate to task runs |
| Request correlation and broader ops visibility | Planned | Request IDs, latency/error counters, stronger operational tracing | `docs/phase3-backlog.md` | none yet | Implement Phase 3C request correlation ID support |
| Stale private memory cleanup | Planned | Cleanup command/job with dry-run and summary | `docs/phase3-backlog.md` | none yet | Implement retention-aware cleanup flow |
| Typed metadata and richer verifier evidence | Planned | JSON metadata filters and explicit verification evidence/check records | `docs/phase3-backlog.md`, `docs/conversation-outcomes.md` | none yet beyond current verification status fields | Add evidence model without overcomplicating current API |
| Harness bridge primitives | Planned | Thin goal/autonomy/action-log primitives that start closing the gap to harness.md | `harness.md`, `docs/conversation-outcomes.md` | none yet | Add minimal `/goal/next` and `/autonomy/check` only if harness work starts |
| Full harness runtime | Deferred | Goal engine, plan trees, world model, experiments, metrics engine, skill compiler, autonomy ladder runtime | `harness.md` | not implemented | Decide whether to grow this repo into the harness backend or keep it as the memory substrate |

## Current Priorities

1. Keep the implemented API and docs synchronized.
2. Increase actual use of `run_id`, `idempotency_key`, `tags`, and verification so the usefulness scorecard becomes meaningful.
3. Finish the smallest useful Phase 3C slice: request correlation and better ops visibility.
4. Defer full harness runtime work until there is a clear decision to turn this service from substrate into orchestrator.

## Maintenance Rule

When a feature changes status, update this file in the same change set as the
code or documentation change that caused the status change.