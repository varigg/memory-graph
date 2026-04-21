# Sprint A: Operational Adoption of Memory Signals

## Sprint Status

- **Status:** Complete
- **Started:** 2026-04-21
- **Completed:** 2026-04-21

## Goal

Drive consistent real-world use of `run_id`, `idempotency_key`, `tags`, and verification updates across agent/client write flows so the memory usefulness scorecard (`/metrics/memory-usefulness`) reflects meaningful adoption metrics.

## Current State

**API Support (Complete):**

- `POST /memory` and `POST /memory/batch` accept optional `run_id`, `idempotency_key`, `tags`
- `POST /memory/verify` accepts `verification_status` and `verification_source`
- `/metrics/memory-usefulness` endpoint aggregates coverage statistics

**Adoption Gap:**

- API fields exist but are not systematically used in real write flows
- Scorecard metrics are low/zero because client code does not populate these fields
- No guidance on how to integrate these fields into common agent patterns

## Definition of Done

1. Identify 2–3 primary agent/client write flow patterns in the documentation and examples
2. Create or update example code showing idiomatic use of `run_id`, `idempotency_key`, `tags`, `verification_status`
3. Update `docs/agent-memory-ops.md` with concrete patterns for each write flow type
4. Update `.github/copilot-instructions.md` to include worked examples of memory signal usage
5. Add integration tests that exercise the scorecard metrics with realistic signal patterns
6. Verify `/metrics/memory-usefulness` returns non-trivial coverage percentages after test execution
7. Document the expected behavior and limitations in `README.md`

## Implementation Plan

### Phase A.1: Identify and Document Client Patterns

**Deliverable:** Documented write flow patterns

**Tasks:**

1. **Map existing client patterns** (e.g., from `docs/agent-memory-ops.md` and `.github/copilot-instructions.md`)
   - Autonomous agent batch writes (e.g., session-level checkpoints)
   - Single-memory writes from within a task/run (e.g., fact storage)
   - Post-execution verification and lifecycle updates (e.g., archive old signal)

2. **Define signal semantics for each pattern**
   - Pattern 1 (Session Checkpoint): `run_id=<session_id>`, `idempotency_key=<checkpoint_hash>`, `tags=['checkpoint']`
   - Pattern 2 (Fact Write): `run_id=<task_id>`, `tags=['fact', 'domain']`, optional `idempotency_key` for dedup
   - Pattern 3 (Lifecycle Update): `verification_status='verified'|'unverified'`, `verification_source='user'|'agent_policy'`, optional `run_id` for correlation

3. **Update `docs/agent-memory-ops.md`**
   - Add a "Signal Best Practices" section with code snippets for each pattern
   - Include example payloads showing field values and naming conventions
   - Explain trade-offs (when to use run_id vs. tags, idempotency_key cost/benefit)

### Phase A.2: Create Example Implementation

**Deliverable:** Runnable example code

**Tasks:**

1. **Create a reference agent flow** in `tests/integration/` that demonstrates signal adoption
   - Simulates a multi-step agent task (e.g., research → write → verify)
   - Issues writes with all signal fields populated consistently
   - Verifies that `/metrics/memory-usefulness` reflects non-zero adoption after execution

2. **Add code examples to `.github/copilot-instructions.md`**
   - Worked example of batch write with `run_id` and `idempotency_key`
   - Worked example of single write with `tags`
   - Worked example of verification update flow
   - Explain when and why to use each field

3. **Add code examples to `README.md`**
   - Quick-start section: "Using Memory Signals for Adoption Tracking"
   - Link to full guidance in `docs/agent-memory-ops.md`

### Phase A.3: Test Coverage and Validation

**Deliverable:** Integration tests + scorecard validation

**Tasks:**

1. **Add integration test** `test_memory_usefulness_adoption_patterns`
   - Execute reference agent flow (Phase A.2)
   - Assert that `/metrics/memory-usefulness` returns non-zero percentages for:
     - `run_id_coverage` (ratio of writes with run_id)
     - `idempotency_key_coverage` (ratio of writes with idempotency_key)
     - `tag_coverage` (ratio of writes with tags)
     - `verification_coverage` (ratio of lifecycle updates with verification status)
   - Acceptance: each metric > 0 and represents the expected signal adoption from the flow

2. **Add scorecard documentation**
   - Explain each metric in `/metrics/memory-usefulness` response structure
   - Document how coverage percentages are calculated
   - Add example response payload to README

3. **Validation test: restart-safety with idempotency**
   - Execute same batch write twice with same `idempotency_key`
   - Verify second write returns same memory IDs (no duplicates)
   - Verify metrics reflect only one logical write event

### Phase A.4: Documentation Refresh

**Deliverable:** Updated guidance and examples

**Tasks:**

1. **Refactor `docs/agent-memory-ops.md`**
   - Rename/reorganize section: "Write Discipline and Signal Adoption"
   - Add "Signal Best Practices" subsection with concrete patterns
   - Add "Scorecard Interpretation" subsection explaining coverage metrics
   - Link to example code

2. **Update `.github/copilot-instructions.md`**
   - Add "Memory Signal Patterns" section with worked examples
   - Include before/after comparison (write without signals vs. with signals)
   - Note: "After completion of Sprint A adoption work, update your write flows to include these fields"

3. **Update `README.md`**
   - Add "Memory Signals and Adoption Tracking" section
   - Quick reference table: field name → semantic meaning → typical values
   - Link to full guidance
   - Example: `/metrics/memory-usefulness` response with real non-zero metrics

## Success Criteria

1. ✅ `docs/agent-memory-ops.md` has concrete, runnable examples for all three write patterns
2. ✅ `.github/copilot-instructions.md` includes worked code examples
3. ✅ `README.md` includes "Memory Signals" quick reference
4. ✅ Integration test `test_memory_usefulness_adoption_patterns` passes with non-zero coverage
5. ✅ All 145+ existing tests still pass
6. ✅ Manual curl/example shows `/metrics/memory-usefulness` returns non-zero percentages after agent-like writes

## Testing Strategy

- **Unit tests:** Not required; signal fields are already validated by existing endpoint tests
- **Integration tests:** New test exercises reference agent flow and validates scorecard metrics
- **Manual validation:** Curl `/metrics/memory-usefulness` before and after populating signals to visually confirm adoption
- **Regression:** Ensure all existing tests pass; signal adoption is additive, not breaking

## Effort Estimate

- Phase A.1 (Patterns): 2–3 hours (documentation + analysis)
- Phase A.2 (Examples): 2–3 hours (code + examples)
- Phase A.3 (Tests): 2–3 hours (integration test + validation)
- Phase A.4 (Docs): 1–2 hours (consolidation + links)
- **Total: ~8–11 hours**

## Risks and Mitigation

| Risk                                                          | Mitigation                                                                                                    |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Scorecard metrics show zero even after writes populate fields | Debug: verify writes are committing signal fields to DB; check `/metrics/memory-usefulness` aggregation logic |
| Coverage percentages are low (e.g., < 50%)                    | Expected for Phase A; Sprint B (cleanup) will drive higher adoption as real workflows mature                  |
| Agent code is in separate repos and hard to update            | Create standalone example in this repo and document the pattern; agents can adopt asynchronously              |
| Idempotency semantics unclear                                 | Document in `docs/agent-memory-ops.md` with worked examples of retry scenarios                                |

## Next Steps (After Sprint A)

1. Measure baseline scorecard metrics in production-like workloads (real agent usage)
2. Sprint B: Implement P3C-3 (stale private memory cleanup)
3. Sprint C: Optional P3C-4 (additional maintenance follow-ons)
4. Plan Phase 4 once Phase 3 is complete
