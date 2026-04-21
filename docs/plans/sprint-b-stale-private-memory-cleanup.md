# Sprint B: Stale Private Memory Cleanup

## Sprint Status

- **Status:** Complete
- **Started:** 2026-04-21
- **Completed:** 2026-04-21

## Goal

Implement P3C-3 by adding a stale private memory cleanup flow with retention-aware selection, dry-run support, and a deletion summary suitable for local operations.

## Scope

1. Define retention-driven stale selection for private memories only
2. Implement cleanup execution path with dry-run mode
3. Return clear deletion summary output for operational visibility
4. Add integration coverage for dry-run and destructive modes
5. Document usage in README and planning docs where applicable

## Definition of Done

1. Cleanup endpoint or command supports retention configuration and only targets private memories
2. Dry-run mode returns candidate counts/details without mutating records
3. Non-dry-run mode performs removals/archives according to final policy and returns deterministic summary fields
4. Integration tests validate both dry-run and execution behavior, including scope safety
5. Existing test suite remains green after adding the cleanup flow
6. `docs/roadmap.md` and `docs/phase3-backlog.md` remain synchronized with implementation status

## Implementation Plan

### Phase B.1: Policy and Interface

- Finalize stale criteria using existing fields (`visibility`, timestamps, and status where applicable)
- Confirm cleanup semantics (delete vs archive) and retention config shape
- Define API/command request and response contract, including dry-run summary fields

### Phase B.2: Service and Storage Changes

- Add service-layer cleanup orchestration in `services/` aligned with current thin-blueprint boundaries
- Add repository query/mutation support for stale private-memory targeting
- Ensure request-path safety checks enforce private-only cleanup scope

### Phase B.3: Endpoint and Validation

- Wire cleanup route/command to service layer
- Validate retention and dry-run parameters with clear `400` errors for invalid input
- Emit operation summary fields for both dry-run and execution paths

### Phase B.4: Testing and Docs

- Add integration tests covering:
  - dry-run no-mutation behavior
  - execution path mutation behavior
  - visibility safety (shared memories are not affected)
  - retention boundary behavior
- Update README with usage examples and expected summary payload shape
- Keep roadmap/backlog statuses current

## Success Criteria

1. ✅ Cleanup flow is callable through a stable interface and handles dry-run plus execution modes
2. ✅ Cleanup never mutates shared memories
3. ✅ Summary output is operationally useful (counts and outcome details)
4. ✅ Integration tests pass and prevent regressions in scope safety
5. ✅ Full `uv run pytest` remains green

## Risks and Mitigation

| Risk                                      | Mitigation                                                                             |
| ----------------------------------------- | -------------------------------------------------------------------------------------- |
| Over-broad cleanup selection              | Enforce `visibility='private'` in repository queries and verify with integration tests |
| Ambiguous retention semantics             | Document retention policy with concrete examples and explicit defaults                 |
| Operational confusion from summary output | Keep response fields deterministic and document dry-run vs execution differences       |
| Regressions in existing retrieval flows   | Run full suite and keep changes isolated to service/repository/route surfaces          |

## Sprint Exit Artifacts

- Implemented cleanup flow (service + repository + route/command)
- Integration tests for dry-run/execution/scope safety
- Updated README usage guidance
- Updated roadmap and backlog status
