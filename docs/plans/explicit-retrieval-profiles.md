# Explicit Retrieval Profiles

## Problem

Every retrieval call to `/memory/list`, `/memory/recall`, and `/memory/search` accepts
around fifteen query parameters. The current contract is implicit: callers must know which
combination of filters produces stable, correct results for their use case. There are two
meaningfully different client types in practice:

- **Autonomous clients** (the harness): need only active, scoped, ranked results; retrieve
  memory on behalf of a specific agent; care about recency-weighted ranking; must not silently
  receive stale or invalidated rows.
- **General clients** (debugging, the web UI, operational queries): need flexible access to
  any status, any visibility, without opinionated ranking applied by default.

Without declared profiles the harness must re-specify the same filter bundle on every call. If
any default changes — or if a new filter is added with a permissive default — the harness
silently gets different results. This breaks the substrate-stability promise that harness v2
depends on.

## What a Profile Is

A **retrieval profile** is a named, server-declared set of default filter values applied before
any caller-supplied overrides. Callers opt in by name. Profiles are thin documentation of
intent, not a new query language.

Two profiles for the initial slice:

| Profile name | Target caller                 | Key defaults                                                                                         |
| ------------ | ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| `autonomous` | harness, agent-driven scripts | `status=active`, `min_confidence=0.7`, `recency_half_life_hours=168` (one week), requires `agent_id` |
| `general`    | UI, ops queries, debugging    | all current defaults (no imposed filters)                                                            |

The `general` profile is the current behavior and requires no code change — it is simply named
explicitly so the contrast with `autonomous` is declared rather than implicit.

## Scope

This feature is intentionally narrow. A profile sets defaults; it does not change endpoint
shapes and does not alter service/repository behavior.

### In scope

- Optional `profile` query parameter on retrieval endpoints.
- Server-declared profile names with explicit validation.
- Default injection only when a caller did not supply a value.
- One profile-oriented guardrail: `autonomous` requires `agent_id`.

### Out of scope

- New endpoints.
- Response shape changes.
- Auth or caller identity redesign.
- Service-layer ranking algorithm changes.
- Repository SQL changes.

## Why `profile=` as a Query Parameter

A query parameter is the lowest-friction option: no header negotiation, works with `curl`,
visible in logs, testable with existing test client patterns. A custom header (`X-Retrieval-Profile`)
is cleaner for programmatic clients but adds friction for debugging and is unnecessary at this
scale.

## Delivery Slices

The original draft bundled multiple endpoint and validation changes into one pass. The revised
plan below breaks work into narrow, independently shippable slices.

### Slice 1: Profile registry and parser only

Goal: introduce profile naming and validation without changing retrieval behavior.

Changes:

- Add a `RETRIEVAL_PROFILES` dict in `blueprints/_params.py` (or a new `blueprints/_profiles.py`
  if it grows). Example:

```python
RETRIEVAL_PROFILES = {
    "general": {},   # no overrides; all defaults remain as-is
    "autonomous": {
        "status": "active",
        "min_confidence": 0.7,
        "recency_half_life_hours": 168.0,
        "_require_agent_id": True,
    },
}
```

- Add a `parse_profile()` helper that reads `profile` from `request.args`, validates it against
  `RETRIEVAL_PROFILES`, and returns a defaults dict (or a 400 error tuple).

Acceptance criteria:

- Unknown profile name returns 400.
- Missing profile is treated as current behavior.
- No retrieval endpoint behavior changes yet.

### Slice 2: Apply profile defaults to `/memory/list` only

Goal: prove the default-injection model on one endpoint before expanding.

Changes:

- In `blueprints/memory.py`, apply `parse_profile()` to `list_memories()`.
- Merge defaults so explicit caller params always win.

Reference merge pattern:

```python
profile_defaults, err_resp, err_status = parse_profile()
if err_resp is not None:
    return err_resp, err_status

# ... existing param parsing ...

# Apply profile defaults only for params the caller left unset:
if status is None:
    status = profile_defaults.get("status")
# etc.
```

Acceptance criteria:

- `profile=autonomous` with no explicit `status` applies `status=active` on list calls.
- Explicit query params override profile defaults.
- Existing non-profile list calls are unchanged.

### Slice 3: Expand to `/memory/recall` and `/memory/search`

Goal: align the other read endpoints after list behavior is stable.

Changes:

- Reuse the same parser and merge pattern in `recall_memory()` and `search_memory()`.

Acceptance criteria:

- Recall/search behavior matches list profile semantics.
- Existing tests for non-profile recall/search remain green.

### Slice 4: Add `autonomous` guardrail (`agent_id` required)

Goal: add the only profile-specific validation rule.

Changes:

- If `_require_agent_id` is set in selected profile and `agent_id` is empty, return 400:
  `"agent_id is required for the autonomous profile"`.

Acceptance criteria:

- Guardrail enforced on list/recall/search when `profile=autonomous`.
- `profile=general` keeps current permissive behavior.

### Stability constraint

Service layer remains unchanged for all slices. Profiles are blueprint-layer default injection
only.

## File-Level Change Map (By Slice)

| Slice | File                    | Change                                                                     |
| ----- | ----------------------- | -------------------------------------------------------------------------- |
| 1     | `blueprints/_params.py` | Add `RETRIEVAL_PROFILES` and `parse_profile()` helper                      |
| 1     | `tests/test_memory.py`  | Add parser/validation tests for unknown profile and no-profile passthrough |
| 2     | `blueprints/memory.py`  | Add profile default merge to `list_memories()`                             |
| 2     | `tests/test_memory.py`  | Add list-specific profile default and override tests                       |
| 3     | `blueprints/memory.py`  | Add profile default merge to `recall_memory()` and `search_memory()`       |
| 3     | `tests/test_memory.py`  | Add recall/search profile behavior tests                                   |
| 4     | `blueprints/memory.py`  | Enforce `_require_agent_id` for `autonomous` profile                       |
| 4     | `tests/test_memory.py`  | Add guardrail tests (`autonomous` without `agent_id` => 400)               |

## PR strategy

- Preferred: one slice per PR.
- Acceptable: combine slices 1+2 only if review overhead is high.
- Avoid: shipping slices 1 through 4 in a single PR.

## Precondition

Transactional write guarantees (roadmap item 1) must be complete before this work begins, so
that any writes triggered during retrieval-path testing are atomic. **That precondition is met
as of 2026-04-21.**

## What This Unlocks

Once `profile=autonomous` is stable, the harness can call retrieval endpoints with a single
parameter instead of a filter bundle, and the substrate can evolve its internal defaults without
silently breaking the harness. This is the minimum stable contract needed before implementing
harness bridge primitives (roadmap item 3).
