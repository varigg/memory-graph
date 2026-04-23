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
| `status` | TEXT | `active`, `blocked`, `completed`, `abandoned` |
| `utility` | REAL | Agent-assigned priority weight |
| `deadline` | TEXT | ISO-8601 or NULL |
| `constraints_json` | TEXT | Deserialized to `constraints` dict in responses |
| `success_criteria_json` | TEXT | Deserialized to `success_criteria` dict in responses |
| `risk_tier` | TEXT | `low`, `medium`, `high`, `critical` |
| `autonomy_level_requested` | INTEGER | 0–5 |
| `autonomy_level_effective` | INTEGER | 0–5 |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | Session identifier |
| `idempotency_key` | TEXT | Unique per owner when set |
| `created_at` | TEXT | ISO-8601 |
| `updated_at` | TEXT | ISO-8601 |

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
| `created_at` | TEXT | |

### Invariants

- `POST /goal/<id>/status` rejects same-status transitions — they do not
  write a history row.
- `idempotency_key` is unique per `owner_agent_id`; a duplicate key
  returns the existing goal without creating a new one.
- `constraints_json` and `success_criteria_json` are stored as JSON
  strings but deserialized to dicts in all response payloads.

## Action Logs

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/action-log` | Create an action log entry |
| GET | `/action-log/list` | List entries (filterable by `goal_id`, `run_id`, `status`) |
| POST | `/action-log/<id>/complete` | Mark an entry complete with outcome |

### Schema

Action logs are stored in the `action_logs` table. They are
append-only; completion updates the `status`, `observed_result`, and
`completed_at` fields in-place rather than inserting a new row.

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `goal_id` | INTEGER FK | Cascades on goal delete |
| `parent_action_id` | INTEGER FK | NULL for root actions |
| `action_type` | TEXT NOT NULL | |
| `tool_name` | TEXT | |
| `mode` | TEXT | `plan`, `dry_run`, `live`, `rollback` |
| `status` | TEXT | `queued`, `running`, `succeeded`, `failed`, `rolled_back` |
| `input_summary` | TEXT | |
| `expected_result` | TEXT | |
| `observed_result` | TEXT | Populated on completion |
| `result_summary` | TEXT | Short completion note |
| `rollback_action_id` | INTEGER FK | Links to compensating action |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | |
| `created_at` | TEXT | |
| `completed_at` | TEXT | Populated on completion |

### Invariants

- Action logs are the primary write trail for the "no unrecorded
  autonomy" rule. Every significant step taken by the autonomous agent
  should produce a row.
- `POST /action-log/<id>/complete` accepts `outcome` (success/failure)
  and `result_summary`; it sets `completed_at` and updates `status`.

## Autonomy Checkpoints

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/autonomy/check` | Record a gate decision |
| GET | `/autonomy/check/list` | List checkpoints (filterable by `run_id`, `verdict`) |

### Schema

Checkpoints are stored in the `autonomy_checkpoints` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `goal_id` | INTEGER FK | NULL for non-goal actions |
| `action_id` | INTEGER FK | NULL if not linked to an action log |
| `requested_level` | INTEGER | 0–5 |
| `approved_level` | INTEGER | 0–5 |
| `verdict` | TEXT | `approved`, `denied`, `sandbox_only` |
| `rationale` | TEXT | |
| `stop_conditions_json` | TEXT | |
| `rollback_required` | INTEGER | Boolean (0/1) |
| `reviewer_type` | TEXT | `policy`, `human`, `system` |
| `owner_agent_id` | TEXT NOT NULL | |
| `run_id` | TEXT | |
| `created_at` | TEXT | |

### Invariants

- Checkpoints are write-and-audit-only. They do not enforce policy at
  runtime — the Claude Code runtime evaluates the verdict and decides
  whether to proceed. The checkpoint records that the decision was made
  and what the rationale was.
- `verdict=denied` does not prevent the action at the service layer.
  The agent is responsible for respecting the verdict.

## Transaction Guarantees

Goal creation and its initial status-history row are written atomically.
Action completion and any rollback linkage updates are written atomically.
Autonomy checkpoint creation is a single-row write with no dependent
state, so no explicit transaction is needed beyond the implicit row
insert.

All multi-step write flows use the `write_transaction` context manager
from `db_utils.py`. See `docs/deep-dive/write-atomicity.md` for the
full transaction model.

## Ownership and Scoping

All three surfaces require `owner_agent_id` on write. `run_id` is
optional but strongly recommended — it enables session-scoped queries
and is the primary recovery signal used by the `SessionStart` hook and
bootstrap procedure.

Read endpoints support filtering by `owner_agent_id` and `run_id`.
There is no cross-owner read restriction at the service layer; the
autonomous agent is expected to scope its own queries.
