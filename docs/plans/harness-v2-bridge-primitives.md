# Plan: Harness V2 Bridge Primitives

## Plan Status

- **Status:** Planned
- **Created:** 2026-04-21

## Goal

Define the smallest set of new substrate capabilities Memory Graph should add so
the harness v2 runtime can move quickly while keeping goal selection, planning,
learning, and broader cognition logic in the harness process.

## Why This Plan Exists

`harness.md` describes a broad target-state runtime with goals, plan trees,
autonomy checks, verification, learning, metrics, and a world model. Not all of
that belongs in Memory Graph.

The fastest non-shortcut path is:

1. finish substrate invariants already on the roadmap
2. add only the bridge records the harness needs for durable auditability and
   restart-safe execution
3. keep runtime policy and cognition-layer behavior in the harness until there
   is repeated evidence that a concern is truly shared substrate

## Boundary Classification

### Belongs In Memory Graph First

These are durable, audit-oriented, restart-safe records that fit the current
memory-substrate role.

1. **Goal records**
   - persistent goal metadata such as status, utility, deadline, constraints,
     success criteria, risk tier, and current autonomy level
   - reason: goals need durable identity, lifecycle, and auditability across
     harness restarts
2. **Action log records**
   - append-only records for planned action attempts, dry-runs, live execution,
     outcomes, and rollback links
   - reason: this is the minimum durable event trail behind the “no unrecorded
     autonomy” rule
3. **Autonomy checkpoint records**
   - explicit gate decisions for risky actions, including requested level,
     verdict, rationale, and any required stop conditions or rollback
   - reason: this is a narrow trust/audit concern that naturally sits beside
     memory lifecycle and verification semantics

### Stays In The Harness For V2

These are runtime policy or cognition concerns and should remain outside Memory
Graph in the first harness v2 integration.

1. goal ranking and scheduling policy
2. hierarchical plan generation and execution control
3. world-model reasoning and prediction resolution policy
4. learning experiments and skill promotion policy
5. KPI interpretation and improvement decisions
6. UI/dashboard orchestration beyond reading substrate records

### Conditional Later Additions

These should only move into Memory Graph if the first bridge slice proves too
thin for real harness operation.

1. richer verifier evidence records
2. prediction/event ledgers for world-model auditability
3. skill run ledgers if procedural memory needs first-class shared storage
4. persisted operational history beyond current local in-memory metrics

## Proposed Initial Slice

### Slice A: Goal Records

Add a first-class durable goal resource with:

- `goal_id`
- `title`
- `status` (`active`, `blocked`, `completed`, `abandoned`)
- `utility`
- `deadline`
- `constraints_json`
- `success_criteria_json`
- `risk_tier`
- `autonomy_level_requested`
- `autonomy_level_effective`
- `owner_agent_id`
- `run_id`
- `created_at`, `updated_at`

Initial endpoints should be minimal:

- `POST /goal`
- `GET /goal/<id>`
- `GET /goal/list`
- `POST /goal/<id>/status`

### Slice B: Action Log

Add an append-only action log tied to goals:

- `action_id`
- `goal_id`
- `parent_action_id` (nullable)
- `action_type`
- `tool_name`
- `mode` (`plan`, `dry_run`, `live`, `rollback`)
- `status` (`queued`, `running`, `succeeded`, `failed`, `rolled_back`)
- `input_summary`
- `expected_result`
- `observed_result`
- `rollback_action_id` (nullable)
- `owner_agent_id`
- `run_id`
- `created_at`

Initial endpoints:

- `POST /action-log`
- `GET /action-log/list`
- `POST /action-log/<id>/complete`

### Slice C: Autonomy Checkpoints

Add explicit autonomy gate records:

- `checkpoint_id`
- `goal_id` (nullable)
- `action_id` (nullable)
- `requested_level`
- `approved_level`
- `verdict` (`approved`, `denied`, `sandbox_only`)
- `rationale`
- `stop_conditions_json`
- `rollback_required`
- `reviewer_type` (`policy`, `human`, `system`)
- `owner_agent_id`
- `run_id`
- `created_at`

Initial endpoint:

- `POST /autonomy/check`

The first version can be write-first and audit-first. It does not need to own
goal ranking, plan execution, or scheduler behavior.

## Concrete Schema Sketch

The first bridge slice should use new goal-specific tables rather than trying to
hide these records inside the existing generic entity layer. The bridge records
have clearer lifecycle, ownership, and audit semantics than the current entity
surface exposes.

### Table 1: `goals`

Purpose: one durable row per harness-level intention.

Suggested columns:

- `id INTEGER PRIMARY KEY`
- `title TEXT NOT NULL`
- `status TEXT NOT NULL DEFAULT 'active'`
- `utility REAL NOT NULL DEFAULT 0`
- `deadline TEXT NULL`
- `constraints_json TEXT NOT NULL DEFAULT '{}'`
- `success_criteria_json TEXT NOT NULL DEFAULT '{}'`
- `risk_tier TEXT NOT NULL DEFAULT 'low'`
- `autonomy_level_requested INTEGER NOT NULL DEFAULT 0`
- `autonomy_level_effective INTEGER NOT NULL DEFAULT 0`
- `owner_agent_id TEXT NOT NULL`
- `run_id TEXT NULL`
- `idempotency_key TEXT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Suggested indexes:

- `(owner_agent_id, status, updated_at DESC)`
- `(run_id, created_at DESC)`
- unique `(owner_agent_id, idempotency_key)` when `idempotency_key IS NOT NULL`

### Table 2: `goal_status_history`

Purpose: optional append-only audit for status transitions without forcing the
main `goals` row to carry the full history.

Suggested columns:

- `id INTEGER PRIMARY KEY`
- `goal_id INTEGER NOT NULL`
- `old_status TEXT NULL`
- `new_status TEXT NOT NULL`
- `changed_by_agent_id TEXT NOT NULL`
- `reason TEXT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Suggested foreign key:

- `goal_id -> goals(id) ON DELETE CASCADE`

This can be deferred if the first slice wants to keep status history in the
action log only, but it is the cleanest audit shape if goal lifecycle changes
become important quickly.

### Table 3: `action_logs`

Purpose: append-only execution trail tied to a goal.

Suggested columns:

- `id INTEGER PRIMARY KEY`
- `goal_id INTEGER NOT NULL`
- `parent_action_id INTEGER NULL`
- `action_type TEXT NOT NULL`
- `tool_name TEXT NULL`
- `mode TEXT NOT NULL`
- `status TEXT NOT NULL`
- `input_summary TEXT NULL`
- `expected_result TEXT NULL`
- `observed_result TEXT NULL`
- `rollback_action_id INTEGER NULL`
- `owner_agent_id TEXT NOT NULL`
- `run_id TEXT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `completed_at TEXT NULL`

Suggested indexes:

- `(goal_id, created_at ASC)`
- `(owner_agent_id, run_id, created_at DESC)`
- `(status, created_at DESC)`

Suggested foreign keys:

- `goal_id -> goals(id) ON DELETE CASCADE`
- `parent_action_id -> action_logs(id) ON DELETE SET NULL`
- `rollback_action_id -> action_logs(id) ON DELETE SET NULL`

### Table 4: `autonomy_checkpoints`

Purpose: explicit gate decisions for risky actions.

Suggested columns:

- `id INTEGER PRIMARY KEY`
- `goal_id INTEGER NULL`
- `action_id INTEGER NULL`
- `requested_level INTEGER NOT NULL`
- `approved_level INTEGER NOT NULL`
- `verdict TEXT NOT NULL`
- `rationale TEXT NULL`
- `stop_conditions_json TEXT NOT NULL DEFAULT '{}'`
- `rollback_required INTEGER NOT NULL DEFAULT 0`
- `reviewer_type TEXT NOT NULL DEFAULT 'system'`
- `owner_agent_id TEXT NOT NULL`
- `run_id TEXT NULL`
- `created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP`

Suggested indexes:

- `(owner_agent_id, run_id, created_at DESC)`
- `(goal_id, created_at DESC)`
- `(action_id, created_at DESC)`

Suggested foreign keys:

- `goal_id -> goals(id) ON DELETE SET NULL`
- `action_id -> action_logs(id) ON DELETE SET NULL`

## Endpoint Sketch

The first bridge slice should stay narrow and write-focused.

### Goals

- `POST /goal`
- `GET /goal/<id>`
- `GET /goal/list`
- `POST /goal/<id>/status`

### Action Logs

- `POST /action-log`
- `GET /action-log/list`
- `POST /action-log/<id>/complete`

### Autonomy Checkpoints

- `POST /autonomy/check`
- `GET /autonomy/check/list`

## Transaction Expectations

These bridge surfaces depend on the transactional write plan.

The first implementation should guarantee at least these atomic units:

1. goal creation plus initial status-history row, if status history is enabled
2. action completion plus any rollback linkage updates
3. autonomy checkpoint creation plus any linked action status transition when
   the checkpoint blocks or forces sandbox-only behavior

## Preconditions

This plan is intentionally sequenced after two substrate hardening items already
called out in the roadmap:

1. transactional write guarantees for multi-step mutations
2. explicit retrieval profiles for autonomous versus general clients

Without those, the harness bridge would be built on unstable write semantics and
implicit recall behavior.

## Out Of Scope

1. embedding or retrieval changes unrelated to harness integration
2. executing plans inside Memory Graph
3. world-model inference logic
4. experiment orchestration and skill compiler policies
5. full dashboard/UI implementation
6. replacing the harness runtime with this service

## Definition Of Done

1. goal, action-log, and autonomy-checkpoint records have schema, storage,
   service, and HTTP boundaries consistent with the existing architecture
2. writes are restart-safe and auditable
3. records can be queried by `owner_agent_id`, `run_id`, and status where
   applicable
4. the harness can use these surfaces without depending on Memory Graph for
   ranking, planning, or learning policy
5. docs clearly distinguish bridge primitives from full harness-runtime scope

## Implementation Steps

### Step 1: Confirm Record Shapes

Document the minimum fields needed for goal, action-log, and autonomy-checkpoint
rows. Prefer additive schemas and avoid premature support for nested plan trees.

### Step 2: Add Schema And Storage

Implement SQLite tables and repository helpers for the three record families.
Keep transaction ownership explicit.

### Step 3: Add Service-Layer Validation

Use typed request models and service methods that normalize and validate bridge
payloads in the same style as current memory lifecycle work.

### Step 4: Add Thin HTTP Surfaces

Expose only the minimal create/read/status-update endpoints needed for the first
harness v2 integration.

### Step 5: Validate With Focused Tests

Add schema, repository, service, and integration tests for lifecycle, ownership,
and audit semantics. Run focused tests first, then the full suite.

## Open Questions

1. Should goals be stored in new goal-specific tables or as typed entities with
   dedicated metadata and service wrappers?
2. Should action logs be fully append-only from day one, or can completion be a
   status update on a single row for the first slice?
3. Is `POST /autonomy/check` purely a recorder in v2, or does it need minimal
   rule evaluation before returning a verdict?
4. Does the harness need plan-node persistence in v2, or is goal-plus-action-log
   enough for the first usable integration?

## Recommended Next Step After This Plan

After this plan, the next concrete planning artifact should be a transactional
write implementation plan, because it is the highest-leverage prerequisite for
the bridge work.
