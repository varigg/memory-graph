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

| Profile name | Target caller | Key defaults |
|---|---|---|
| `autonomous` | harness, agent-driven scripts | `status=active`, `min_confidence=0.7`, `recency_half_life_hours=168` (one week), requires `agent_id` |
| `general` | UI, ops queries, debugging | all current defaults (no imposed filters) |

The `general` profile is the current behavior and requires no code change — it is simply named
explicitly so the contrast with `autonomous` is declared rather than implicit.

## Scope

This feature is intentionally narrow. A profile sets defaults; it does not change the API
surface, add new endpoints, or prevent callers from overriding individual parameters.

**What changes:**

- `GET /memory/list`, `/memory/recall`, `/memory/search` accept an optional `profile` query
  parameter.
- If `profile=autonomous`: apply the `autonomous` defaults for any parameter the caller did not
  supply, and return 400 if `agent_id` is absent.
- If `profile=general` or no `profile` param: existing behavior, unchanged.
- Unknown profile name → 400 with a clear error message listing valid profiles.

**What does not change:**

- No new endpoints.
- No change to response shape.
- No new authentication or caller identity mechanism.
- Parameters explicitly supplied by the caller always take precedence over profile defaults.

## Why `profile=` as a Query Parameter

A query parameter is the lowest-friction option: no header negotiation, works with `curl`,
visible in logs, testable with existing test client patterns. A custom header (`X-Retrieval-Profile`)
is cleaner for programmatic clients but adds friction for debugging and is unnecessary at this
scale.

## Implementation Approach

### 1. Define profiles in a single location

Add a `RETRIEVAL_PROFILES` dict in `blueprints/_params.py` (or a new `blueprints/_profiles.py`
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

### 2. Parse the profile parameter in `_params.py`

Add a `parse_profile()` helper that reads `profile` from `request.args`, validates it against
`RETRIEVAL_PROFILES`, and returns the defaults dict (or a 400 error tuple). Return `None` for
absent profile (caller gets general behavior transparently).

### 3. Apply profile defaults in the blueprint before parameter parsing

For each retrieval route, call `parse_profile()` first. Merge its defaults into the parameter
resolution so that an explicit caller value always wins:

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

### 4. Guard `autonomous` profile on `agent_id`

If `_require_agent_id` is set in the profile and `agent_id` is absent or empty, return 400:
`"agent_id is required for the autonomous profile"`.

### 5. Service layer stays unchanged

No changes to `memory_retrieval_service.py` or any repository. Profiles are pure blueprint-layer
default injection.

## File-Level Change Map

| File | Change |
|---|---|
| `blueprints/_params.py` | Add `RETRIEVAL_PROFILES` dict and `parse_profile()` helper |
| `blueprints/memory.py` | Call `parse_profile()` at top of list/recall/search routes; merge defaults |
| `tests/test_memory.py` | Add profile parameter tests: unknown name → 400; `autonomous` without `agent_id` → 400; `autonomous` applies default filters; explicit param overrides profile default |

## Precondition

Transactional write guarantees (roadmap item 1) must be complete before this work begins, so
that any writes triggered during retrieval-path testing are atomic. **That precondition is met
as of 2026-04-21.**

## What This Unlocks

Once `profile=autonomous` is stable, the harness can call retrieval endpoints with a single
parameter instead of a filter bundle, and the substrate can evolve its internal defaults without
silently breaking the harness. This is the minimum stable contract needed before implementing
harness bridge primitives (roadmap item 3).
