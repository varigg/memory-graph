# Sprint C: Additional Operational Maintenance Follow-Ons (P3C-4)

## Sprint Status

- **Status:** Complete
- **Started:** 2026-04-21
- **Completed:** 2026-04-21

## Goal

Start Sprint C by scoping and implementing only the operational maintenance
follow-ons that solve concrete local-first issues, avoiding speculative
maintenance features.

## Scope

1. Implement integrity check endpoint for orphan references and duplicate candidates
2. Implement SQLite maintenance helper endpoint with safe dry-run and controlled execution mode
3. Expand ops metrics with retrieval result, lock-event, and dedupe signals
4. Add tests that cover these maintenance and observability paths
5. Update README and planning docs to reflect Sprint C completion

## Candidate Follow-Ons (P3C-4)

1. Integrity checks for orphan references and duplicate candidates
2. Optional SQLite maintenance helper only when tied to an observed local issue
3. Deeper operational metrics where current visibility is insufficient

## Entry Criteria

1. At least one concrete local ops gap is identified and documented
2. The selected follow-on has a bounded API contract and test plan

## Definition of Done

1. Chosen follow-on is implemented and documented
2. Tests verify behavior and safety (including non-destructive paths when applicable)
3. `docs/roadmap.md` and `docs/phase3-backlog.md` are synchronized with resulting status
4. Full `uv run pytest` remains green after implementation

## Initial Sprint Tasks

1. ✅ Added `GET /maintenance/integrity` for orphan + duplicate-candidate checks
2. ✅ Added `POST /maintenance/sqlite` with dry-run default and checkpoint mode control
3. ✅ Added deeper `GET /metrics/ops` signal sections (retrieval/db-lock/dedupe)
4. ✅ Added/updated integration tests for maintenance and ops metrics
5. ✅ Full `uv run pytest` remained green after implementation

## Notes

- Sprint C remains optional by design and should advance only where local
  operational value is clear.
