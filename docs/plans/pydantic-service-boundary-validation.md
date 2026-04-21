# Plan: Add Pydantic Validation

## Plan Status

- **Status:** Planned
- **Created:** 2026-04-21

## Goal

Replace ad-hoc request parsing at service boundaries with typed Pydantic models
so the API has a consistent validation layer, clearer error semantics, and
safer inputs for future transactional and verification-related work.

## Why This Next

1. The codebase already has thin blueprints and service-layer boundaries, which
   makes typed request models the natural next hardening step.
2. Current request parsing is spread across blueprints and service helpers,
   which increases the risk of inconsistent validation and error messages.
3. This work improves correctness without forcing a product-direction choice
   about harness/autonomy scope.
4. Typed contracts will make later work on transactions, richer verifier
   evidence, and any future harness bridge primitives safer to implement.

## Current State

**In place:**

- thin HTTP adapters in `blueprints/`
- service-layer modules in `services/`
- repository isolation in `storage/`
- broad endpoint and integration test coverage

**Gap:**

- request parsing still relies heavily on manual `request.args`,
  `request.get_json()`, and repeated `isinstance` / `.strip()` validation
- error payloads are broadly consistent but not driven by one typed schema layer
- list/search/filter endpoints accept many optional inputs that would benefit
  from central type coercion and constraint enforcement

## Scope

1. Introduce Pydantic models for the highest-value request payloads and query
   contracts at the service boundary
2. Unify validation and normalization for create/write/lifecycle flows first
3. Extend typed validation to list/search/read filter parsing
4. Preserve existing public API behavior unless a change is explicitly chosen
5. Add focused tests for invalid payloads, coercion, and error consistency

## Out of Scope

1. Changing endpoint paths or major response shapes
2. Broad auth redesign
3. Full transaction orchestration work
4. Harness/autonomy bridge implementation

## Definition of Done

1. Core request payloads are validated by Pydantic models instead of ad-hoc
   parsing logic
2. Query/filter parsing for memory read flows uses typed validation where it is
   practical and reduces duplication
3. Existing happy-path API behavior remains compatible unless intentionally
   documented otherwise
4. Invalid inputs return clear and consistent `400` responses
5. Existing tests remain green and new validation tests cover the migrated paths
6. `README.md` and `docs/roadmap.md` reflect the chosen validation approach

## Implementation Plan

### Step 1: Choose Validation Boundary

**Deliverable:** documented boundary choice and initial model set

1. Confirm whether Pydantic models live in `services/` or a small shared
   schemas module
2. Define initial model set for:
   - memory create
   - memory batch write items
   - lifecycle actions (`archive`, `invalidate`, `verify`, `merge`, `supersede`)
   - cleanup/private maintenance actions where beneficial
3. Preserve current field names and semantics to avoid unnecessary API churn

### Step 2: Migrate Write and Lifecycle Paths

**Deliverable:** typed validation for highest-risk mutation endpoints

1. Replace manual payload checks in memory mutation routes with Pydantic-backed
   parsing
2. Centralize normalization rules currently spread across helper functions
3. Ensure validation errors map to stable `400` responses with useful messages
4. Keep service-layer call signatures explicit and typed where practical

### Step 3: Migrate Read and Filter Parsing

**Deliverable:** typed parsing for list/search/recall filters

1. Introduce typed models or parsing objects for query parameters used by:
   - `/memory/list`
   - `/memory/search`
   - `/memory/recall`
   - search endpoints where beneficial
2. Reduce duplication in filter parsing and coercion
3. Validate enums and numeric bounds in one place

### Step 4: Error Semantics and Documentation

**Deliverable:** consistent validation behavior and docs

1. Decide how Pydantic validation errors are rendered in API responses
2. Keep error responses readable and aligned with existing conventions
3. Update `README.md` if any validation semantics become more explicit
4. Update roadmap language to reference the completed typed-validation layer

### Step 5: Test Coverage and Regression Validation

**Deliverable:** focused validation coverage and full regression confidence

1. Add tests for invalid payloads and invalid query parameters on migrated paths
2. Add tests for normalization/coercion behavior where the API depends on it
3. Run focused suites first, then full `uv run pytest`

## Initial Target Endpoints

1. `POST /memory`
2. `POST /memory/batch`
3. `POST /memory/archive`
4. `POST /memory/invalidate`
5. `POST /memory/verify`
6. `POST /memory/merge`
7. `POST /memory/supersede`
8. `GET /memory/list`
9. `GET /memory/search`
10. `GET /memory/recall`

## Testing Strategy

- Focused endpoint validation tests for migrated routes
- Regression tests for existing success-path behavior
- Full-suite run after the migration set is complete

## Risks and Mitigation

| Risk                                                          | Mitigation                                                                                   |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Validation refactor changes current API behavior unexpectedly | Preserve field names and response semantics first; tighten only with explicit doc updates    |
| Pydantic error output is too verbose or unstable for clients  | Normalize error responses before returning them from blueprints                              |
| Query parameter parsing becomes harder to read                | Introduce small typed parsing objects rather than one overly large schema                    |
| Migration scope expands too far                               | Start with write/lifecycle paths and only extend read/filter flows where duplication is real |

## Suggested Follow-Ons After This Plan

1. Transactional write guarantees for composite mutation flows
2. Richer verifier evidence model
3. SQLite runtime hardening
4. Harness bridge primitives only when autonomy work is explicitly scoped
