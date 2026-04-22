# Retrieval Contracts

This document defines the current read-path contract for memory retrieval.

## Retrieval Endpoints

The profile and filter contract applies to:

- `GET /memory/list`
- `GET /memory/recall`
- `GET /memory/search`

All three return a bare JSON array, but the item shape differs by endpoint:

- `GET /memory/list` returns full memory objects.
- `GET /memory/recall` returns recall/FTS result objects keyed by
  `memory_id` with a subset of memory fields.
- `GET /memory/search` returns search/FTS result objects keyed by
  `memory_id` with a subset of memory fields.

## Retrieval Profiles

`profile` is an optional query parameter with server-declared values:

- `general`: baseline/default retrieval behavior
- `autonomous`: conservative defaults for restart-sensitive agents

Baseline retrieval behavior defaults to `status=active` unless the caller
explicitly overrides `status`.

`profile=autonomous` adds the following defaults only when the caller does not
provide explicit values:

- `status=active`
- `min_confidence=0.7`
- `recency_half_life_hours=168`

Guardrail:

- `profile=autonomous` requires non-empty `agent_id`

Unknown or empty profile values return `400`.

## Scope And Visibility

When `agent_id` is present and no scope flags are set, retrieval scope is:

- shared memories + caller-owned private memories

Scope flags:

- `shared_only=true` -> shared only
- `private_only=true` -> caller-owned private only

Setting both flags is rejected with `400`.

## Filter Surface

Supported filters include:

- lifecycle/status: `status`
- ownership and visibility: `visibility`, `owner_agent_id`
- run/task context: `run_id`, `tag`
- quality and freshness: `min_confidence`, `updated_since`,
  `recency_half_life_hours`
- typed metadata constraints: `metadata_key`, `metadata_value`,
  `metadata_value_type`

Validation errors return `400` with parameter-specific error messages.

## Ranking Semantics

Ordering behavior is shared across list/search/recall paths:

- shared rows rank ahead of private rows
- then by confidence
- then by recency (`updated_at` fallback `timestamp`)

When `recency_half_life_hours` is provided, ranking applies a recency-weighted
bias before the final timestamp tie-break.

## Service Boundaries

Blueprints own profile parsing and default injection. Service and repository
layers own scoped dispatch, query execution, and ranking implementation.
