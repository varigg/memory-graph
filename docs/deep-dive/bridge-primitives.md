# Bridge Primitives

This document describes the implemented behavior and invariants of the
three bridge primitive surfaces: goals, action logs, and autonomy
checkpoints.

Use `docs/architecture.md` for the system boundary narrative.
Use `docs/roadmap.md` for implementation status.
Use `docs/adr/` for durable boundary decisions.

## Purpose

Bridge primitives are the minimal durable record surfaces the autonomous
Claude Code agent needs for auditable, restart-safe operation. They are
intentionally narrow: they record what the agent decided and did, but
they do not own goal ranking, plan execution, or autonomy policy logic.
Those responsibilities remain in the Claude Code runtime.

## Goals

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/goal` | Create a goal |
| GET | `/goal/list` | List goals (filterable by `status`, `owner_agent_id`, `run_id`) |
| GET | `/goal/<id>` | Get one goal |
| POST | `/goal/<id>/status` | Transition goal status |

### Schema

Goals are stored in the `goals` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `title` | TEXT NOT NULL | |
| `status` | TEXT | `active`, `blocked`, `completed`, `abandoned`; default `active` |
| `utility` | REAL | Agent-assigned priority weight; default `0` |
| `deadline` | TEXT | ISO-8601 or NULL |
| `constraints_json` | TEXT | Deserialized to `constraints` dict in responses |
| `success_criteria_json` | TEXT | Deserialized to `success_criteria` dict in responses |
| `risk_tier` | TEXT | `low`, `medium`, `high`, `critical`; default `low` |
| `autonomy_level_requested` | INTEGER | 0–5; default `0` |
| `autonomy_level_effective` | INTEGER | 0–5; default `0` |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | Session identifier |
| `idempotency_key` | TEXT | Unique per owner when set |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Status history

Every status transition writes a row to `goal_status_history`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `goal_id` | INTEGER FK | Cascades on goal delete |
| `old_status` | TEXT | NULL on creation |
| `new_status` | TEXT NOT NULL | |
| `changed_by_agent_id` | TEXT NOT NULL | |
| `reason` | TEXT | |
| `created_at` | DATETIME | |

### Invariants

- `POST /goal/<id>/status` rejects same-status transitions — they do not
  write a history row.
- `idempotency_key` is unique per `owner_agent_id`; a duplicate key
  returns the existing goal without creating a new one.
- `constraints_json` and `success_criteria_json` are stored as JSON
  strings and deserialized to dicts in all response payloads.
- Goal deletion cascades to `goal_status_history` and `action_logs`
  rows that reference the goal.

## Action Logs

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/action-log` | Create an action log entry |
| GET | `/action-log/list` | List entries (filterable by `goal_id`, `run_id`, `status`, `owner_agent_id`) |
| POST | `/action-log/<id>/complete` | Mark an entry complete with outcome |

### Schema

Action logs are stored in the `action_logs` table. Completion updates
`status`, `observed_result`, `rollback_action_id`, and `completed_at`
in-place rather than inserting a new row.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `goal_id` | INTEGER FK | Cascades on goal delete |
| `parent_action_id` | INTEGER FK | NULL for root actions; SET NULL on parent delete |
| `action_type` | TEXT NOT NULL | |
| `tool_name` | TEXT | |
| `mode` | TEXT | `plan`, `dry_run`, `live`, `rollback` |
| `status` | TEXT | `queued`, `running`, `succeeded`, `failed`, `rolled_back` |
| `input_summary` | TEXT | |
| `expected_result` | TEXT | |
| `observed_result` | TEXT | Populated on completion |
| `rollback_action_id` | INTEGER FK | Links to compensating action; SET NULL on referenced delete |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | |
| `idempotency_key` | TEXT | Unique per owner when set |
| `created_at` | DATETIME | |
| `completed_at` | DATETIME | Populated on completion |

### Invariants

- Action logs are the primary write trail for the "no unrecorded
  autonomy" rule. Every significant step taken by the autonomous agent
  should produce a row.
- `POST /action-log/<id>/complete` accepts `status` (one of the three
  terminal values), `observed_result`, and `rollback_action_id`.
- Cross-status terminal transitions are rejected: an entry that
  completed as `succeeded` cannot be re-completed as `failed`.
- `idempotency_key` is unique per `owner_agent_id`; a duplicate create
  returns the existing record without inserting a new row.

## Autonomy Checkpoints

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/autonomy/check` | Record a gate decision |
| GET | `/autonomy/check/list` | List checkpoints (filterable by `run_id`, `verdict`, `owner_agent_id`, `goal_id`, `action_id`, `reviewer_type`) |

### Schema

Checkpoints are stored in the `autonomy_checkpoints` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `goal_id` | INTEGER FK | NULL for non-goal actions; SET NULL on goal delete |
| `action_id` | INTEGER FK | NULL if not linked to an action log; SET NULL on action delete |
| `requested_level` | INTEGER | 0–5 |
| `approved_level` | INTEGER | 0–5; must not exceed `requested_level` |
| `verdict` | TEXT | `approved`, `denied`, `sandbox_only` |
| `rationale` | TEXT | |
| `stop_conditions_json` | TEXT | Deserialized to dict in responses |
| `rollback_required` | INTEGER | Boolean (0/1) |
| `reviewer_type` | TEXT | `policy`, `human`, `system`; default `system` |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | |
| `idempotency_key` | TEXT | Unique per owner when set |
| `created_at` | DATETIME | |

### Invariants

- Checkpoints record gate decisions for audit; they do not own policy
  enforcement. The Claude Code runtime is responsible for acting on the
  verdict.
- When `verdict=denied` and the checkpoint is linked to an action that is
  not yet in a terminal state, the service atomically marks that action
  as `failed` in the same write. This is the one side-effect the service
  applies on a blocking verdict.
- `approved_level` must not exceed `requested_level`; the service
  rejects invalid combinations.
- `stop_conditions_json` is stored as a JSON string and deserialized to
  a dict in all response payloads.

## Transaction Guarantees

Goal creation and its initial status-history row are written atomically.
Action completion is a single UPDATE operation on the action log row.
Autonomy checkpoint creation is a single-row write with no dependent
state, so no explicit transaction is needed beyond the implicit row
insert.

All multi-step write flows use the `write_transaction` context manager
from `db_utils.py`. See `docs/deep-dive/write-atomicity.md` for the
full transaction model.

## Ownership and Scoping

All three surfaces require `owner_agent_id` on write. `run_id` is
optional but strongly recommended — it enables session-scoped queries
and is the primary recovery signal used during bootstrap.

Read endpoints support filtering by `owner_agent_id` and `run_id`.
There is no cross-owner read restriction at the service layer; the
autonomous agent is expected to scope its own queries.

## Service Boundary

Bridge primitives are durable substrate records. Goal ranking, plan
execution control, world-model reasoning, skill promotion, and
autonomy-level policy all remain outside this service in the Claude Code
runtime. Bridge primitives grow only when the runtime demonstrates a
concrete need for a durable audit or recovery record that the current
surfaces cannot satisfy.
