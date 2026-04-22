# Plan: Transactional Write Guarantees

## Plan Status

- **Status:** Planned
- **Created:** 2026-04-21

## Goal

Make multi-step write flows atomic and predictable so Memory Graph can safely
support batch writes, lifecycle mutations, and the first harness v2 bridge
primitives without partial commits or ambiguous recovery behavior.

## Why This Is Next

The current write path still mixes orchestration in `services/` with implicit
commit points inside repository helpers.

Examples in the current code:

1. `storage/memory_repository.py::insert_memory()` commits immediately, which
   means `POST /memory/batch` can partially succeed item-by-item.
2. `services/memory_lifecycle_service.py` owns multi-statement lifecycle flows,
   but transaction ownership is not yet standardized across write operations.
3. future harness v2 bridge records will need goal/action/autonomy writes that
   can be grouped safely with strong audit semantics.

This makes transactional hardening the highest-leverage prerequisite for the
bridge work.

## Current Problems To Fix

### Problem 1: Repository Helpers Commit Too Early

Several repository helpers call `db.commit()` directly. That prevents service
or blueprint code from treating a logical write flow as one atomic unit.

Immediate consequence:

- a batch request can commit some rows before a later item fails validation or
  persistence

### Problem 2: Transaction Ownership Is Inconsistent

Some multi-step operations are grouped in service functions, but the codebase
does not yet have one clear rule for which layer owns `BEGIN`, `COMMIT`, and
`ROLLBACK`.

### Problem 3: Failure Semantics Are Too Implicit

The API should make a clearer promise for mutation endpoints: either the entire
logical operation succeeds, or the database remains unchanged.

## Scope

1. define a consistent transaction-ownership rule
2. remove repository-level commits from multi-step write helpers where service
   orchestration needs atomicity
3. add explicit transaction wrappers for batch and lifecycle mutation flows
4. document endpoint-level atomicity guarantees
5. add focused tests that prove rollback behavior

## Out Of Scope

1. distributed transactions or multi-database coordination
2. concurrency architecture beyond local SQLite-safe usage
3. harness bridge schema work except where it depends on transaction patterns
4. broad changes to read paths

## Proposed Transaction Boundary Rule

Use this ownership model:

1. **Blueprints** own request parsing and HTTP response selection only.
2. **Services** own logical mutation boundaries and transaction scope.
3. **Repositories** execute SQL and never call `commit()` for flows that may be
   composed into larger service operations.

That rule keeps atomicity decisions at the same layer that already owns
idempotency, lifecycle rules, and bridge-write orchestration.

## Initial Target Flows

### Tier 1: Must Be Atomic

1. `POST /memory/batch`
2. `POST /memory/merge`
3. `POST /memory/supersede`
4. any future goal/action-log/autonomy-checkpoint composite write flows

### Tier 2: Standardize For Consistency

1. `POST /memory`
2. `POST /memory/archive`
3. `POST /memory/invalidate`
4. `POST /memory/verify`
5. `POST /memory/<id>/promote`
6. `POST /memory/cleanup-private`

Tier 2 flows are often single logical mutations today, but they should still
use the same service-owned transaction pattern so future expansion stays safe.

## Proposed Implementation Approach

### Step 1: Inventory And Reclassify Commit Points

Identify repository helpers that currently commit directly and classify them as:

1. safe to remain self-committing because they are isolated local utilities
2. must become non-committing because they participate in service-level flows

Expected first changes include memory write and delete helpers.

### Step 2: Add Transaction Helper(s)

Introduce one explicit transaction utility in `db_utils.py` or a closely
related service helper, for example a context manager that:

1. begins a transaction
2. yields control to the service operation
3. commits on success
4. rolls back on exception

Keep the abstraction small and SQLite-specific.

### Step 3: Refactor Tier 1 Flows First

Convert batch and lifecycle relation flows to use explicit service-owned
transactions.

Desired behavior:

1. batch write inserts all validated items or none
2. merge/supersede relation row plus status updates succeed together or fail
   together

### Step 4: Standardize Tier 2 Flows

Move the rest of the mutation endpoints onto the same transaction pattern so
the codebase has one mental model for writes.

### Step 5: Document Guarantees

Update `README.md`, `docs/roadmap.md`, and any relevant plan docs so the API
contract states which endpoints are atomic and what idempotency does and does
not guarantee.

## Concrete Design Direction

### Recommended Utility Shape

Prefer a small context manager such as:

- `with write_transaction(db): ...`

Service functions should use it around logical write units.

### Recommended Repository Rule

Repositories should return row IDs, row counts, or result objects, but not
commit. If a repository function must remain self-committing for an isolated
maintenance case, that exception should be explicit and documented.

### Idempotency Interaction

For idempotent create flows:

1. check for an existing row inside the same transaction boundary when possible
2. rely on deterministic keys and database constraints where appropriate
3. document replay behavior clearly so “already exists” does not look like a
   partial failure

## Concrete Refactor Sequence

This is the recommended implementation order for the current codebase.

### Stage 1: Move Batch Orchestration Out Of The Blueprint

Current seam:

- `blueprints/memory.py::create_memory_batch()` loops over items and calls the
  service once per element

Refactor goal:

1. keep the blueprint responsible only for request parsing and HTTP response
   formatting
2. move the full batch operation into a dedicated service function such as
   `create_memory_batch(db, items)`
3. make the service own validation ordering, idempotency checks, inserts, and
   transaction scope for the whole batch

Why first:

- this is the clearest existing example where logical orchestration lives in the
  wrong layer and where partial commits are easiest to trigger

### Stage 2: Stop Repository Helpers From Committing In Composable Flows

Current seam:

- `storage/memory_repository.py::insert_memory()` commits immediately
- `storage/memory_repository.py::delete_memories_by_ids()` commits immediately

Refactor goal:

1. remove `db.commit()` from helpers that participate in service-owned mutation
   flows
2. keep repository helpers limited to SQL execution plus result return values
3. add a short docstring or code comment only where a helper intentionally
   remains self-committing as an exception

Why second:

- service-owned transactions are not real until repository helpers stop
  finalizing writes behind the service layer’s back

### Stage 3: Introduce A Single Write Transaction Utility

Current seam:

- `db_utils.get_db()` returns a raw connection, but the codebase has no shared
  write-transaction abstraction

Refactor goal:

1. add a small utility such as `write_transaction(db)` in `db_utils.py`
2. use it as the only standard path for grouped mutations
3. keep the helper SQLite-specific and minimal: begin, commit, rollback

Why third:

- once commit points move upward, the code needs one canonical way to express a
  service-owned mutation boundary

### Stage 4: Rebuild The Memory Write Service Around Logical Mutation Units

Current seam:

- `services/memory_write_service.py::create_or_get_memory()` is service-shaped,
  but its transaction outcome is still controlled by repository commit behavior

Refactor goal:

1. keep `create_or_get_memory()` as the single-memory logical mutation unit
2. add a batch-oriented companion that validates all items, then performs all
   lookups and inserts inside one transaction
3. make idempotent replay handling explicit inside the service-owned
   transaction, not as an accidental side effect of repository behavior

Why fourth:

- after stages 1 to 3, this is where the codebase actually gains a clean write
  orchestration model for memory creation

### Stage 5: Standardize Lifecycle Services On The Same Pattern

Current seam:

- `services/memory_lifecycle_service.py` already owns most lifecycle logic, but
  each function commits directly

Refactor goal:

1. remove direct commits from lifecycle functions that may be composed later
2. wrap merge/supersede first, since they already span multiple SQL statements
3. then move verify, promote, archive, invalidate, and cleanup onto the same
   service-owned transaction style for consistency

Why fifth:

- merge/supersede are already multi-step logical mutations and are the closest
  analog to future harness bridge writes

### Stage 6: Add Failure-Scoped Tests Before Broad Cleanup

Current seam:

- existing tests cover happy-path behavior, but the critical transactional risk
  is partial success during mid-flow failure

Refactor goal:

1. add a batch test that proves zero rows persist if one later item fails
2. add a merge/supersede test that proves relation and status writes roll back
   together on failure
3. add a cleanup failure test only if cleanup is moved under explicit
   transaction orchestration

Why sixth:

- this gives a falsifiable check for the refactor before expanding the same
  pattern across the rest of the write surface

## File-Level Change Map

Start here when implementing:

1. `blueprints/memory.py`
   - shrink `create_memory_batch()` to input parsing plus one service call
2. `services/memory_write_service.py`
   - add service-owned batch orchestration
   - keep single-create and batch-create transaction boundaries explicit
3. `storage/memory_repository.py`
   - remove commits from composable helpers such as insert and delete
4. `db_utils.py`
   - add the shared write-transaction helper
5. `services/memory_lifecycle_service.py`
   - migrate merge/supersede first, then normalize the rest of the lifecycle
     write functions
6. `tests/test_memory.py`
   - add endpoint-level rollback assertions
7. `tests/test_db_operations.py`
   - add lower-level lifecycle rollback assertions where needed

## Lowest-Risk Implementation Order

If this is executed as code rather than planning only, the safest incremental
order is:

1. add transaction helper
2. stop repository auto-commit for memory write/delete helpers
3. move batch orchestration into the service layer
4. add one failing batch rollback test
5. make that test pass
6. migrate merge/supersede to the same transaction model
7. add lifecycle rollback tests
8. standardize the remaining write endpoints only after Tier 1 is stable

## Definition Of Done

1. Tier 1 mutation flows are atomic under test
2. repository helpers no longer commit in ways that break service composition
3. service code clearly owns transaction boundaries
4. rollback behavior is tested for mid-flow failures
5. docs state the intended atomicity contract

## Testing Strategy

Add focused tests that deliberately fail mid-operation and prove the database is
unchanged.

Priority tests:

1. batch write with one invalid item after one valid item leaves zero inserted
   rows
2. merge/supersede failure after relation insert does not leave half-applied
   lifecycle state
3. cleanup failure does not partially delete targeted rows
4. idempotent replay still behaves correctly inside the transaction model

Run focused tests first, then the full `uv run pytest` suite.

## Relationship To Harness V2

This plan is the main prerequisite for the bridge-primitives plan in
`docs/plans/harness-v2-bridge-primitives.md`.

Without transaction ownership discipline, the harness cannot rely on goal,
action-log, or autonomy-checkpoint writes as auditable durable state.

## Open Questions

1. Should `get_db()` stay as the connection factory while transaction helpers
   layer on top, or is a small write-oriented connection wrapper worth it?
2. Are there any repository helpers outside memory flows that should remain
   self-committing for simplicity?
3. Do we want explicit savepoint support now, or only after the first bridge
   implementation proves a need?

## Recommended Next Step After This Plan

Implement Tier 1 transaction refactors first, starting with `POST /memory/batch`
and the lifecycle relation flows.
