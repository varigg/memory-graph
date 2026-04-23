# Vision

## The End Goal

An autonomous Claude Code agent with persistent memory across sessions,
self-improvement over time, and the ability to receive and respond to
messages continuously — while remaining usable as a shared memory substrate
for unrelated agents that simply need reliable fact recall.

## The Runtime

Claude Code is the cognitive runtime. There is no separate harness process.

A long-running Claude Code session with `--channels` configured for Discord
acts as the autonomous agent. It receives messages, executes work, schedules
its own recurring tasks via `CronCreate`, and maintains continuity across
restarts through the memory-graph service.

The session is launched with `--dangerously-skip-permissions` so it can
operate without blocking on tool-use approval prompts. This is required for
unattended 24/7 operation — a session that halts waiting for permission
confirmation is not autonomous.

The session is the planner, the decision-maker, and the executor. Memory
Graph is where it externalizes state that must survive beyond a single
session.

## Bootstrap Contract

`CLAUDE.md` is the invariant startup specification. On every session start it
instructs Claude to:

1. Query the memory API for the last session snapshot (scoped by `run_id`)
   to recover working context
2. List running cron jobs and reconcile against the canonical specs in
   `~/.claude/prompts/` — recreating any that are missing
3. Resume any open goals recorded in the service from the previous session

This makes restart recovery declarative and self-healing. The service holds
the state; CLAUDE.md holds the recovery procedure.

## What Lives Where

### In Claude Code (the runtime)

- Active reasoning, planning, and decision-making
- Conversational context within the session window
- Skill execution and tool use
- Autonomy judgments and risk assessment
- Cron job scheduling and management
- Discord channel interaction

Claude Code writes the *outcomes* of these activities to memory-graph so
they are durable and auditable. It does not delegate the reasoning itself
to the service.

### In Memory Graph (the substrate)

**Implemented:**
- Episodic memory: what happened, when, with what outcome
- Semantic memory: stable facts and validated beliefs
- Goal records: active intentions with status, owner, and lifecycle history
- Action logs: executed steps with mode (dry-run/live/rollback) and result
- Autonomy checkpoints: gate decisions with rationale and reviewer type
- Entity and relation graph
- Key-value operational state
- Conversation history and embeddings for semantic recall

**Planned — safety tier** (gates correct behavior before it accumulates history):
- Plan nodes: executable goal decompositions with type, tool, expected result,
  exit condition, and rollback; node status updated as work progresses
- Sandbox records: dry-run execution results for irreversible actions; Claude
  only proceeds to live if the verdict is ok
- Verification records: claim assessments with sources and confidence score;
  if confidence < 0.5 Claude stops and says so

**Planned — self-improvement tier** (compounds in value as history accumulates):
- Capability records: per-skill outcome tracking for Bayesian confidence
  calibration (success/failure counts, cost, time, autonomy max)
- World model predictions: testable future claims; resolved on outcome arrival
  to build calibration gap metrics
- Experiment records: approach comparisons with observations and
  auto-concluded winners when delta and sample thresholds are met
- Metric records: daily KPI write path (hallucination rate, goal throughput,
  calibration gap, skill success rate, cost per useful task, etc.)
- Skill records: recurring patterns with maturity lifecycle
  (draft → beta → stable → deprecated) and per-use outcome tracking
- Memory decay: weekly confidence reduction on unverified memories; resets
  on verification

## Self-Improvement Loop

Each session reads prior context from memory-graph, acts, then writes back:

- memories capturing what was learned or validated
- goal and plan-node status updates reflecting work completed
- action log entries recording what was executed and how it went
- autonomy checkpoint records for any risky actions taken
- capability records updated with task outcome, cost, and time
- verification records for factual claims the user relies on
- predictions logged when making testable future claims

Future sessions read these records to understand what was tried before, what
worked, and what the current open obligations are. Over time this produces
an accumulated operational history that the agent can reason over — and the
self-improvement tier surfaces give it structured signal to improve from.

## Two Client Modes

**Autonomous agent**: The long-running Claude Code session. Reads with the
`autonomous` retrieval profile (high-confidence, low-noise, run-scoped).
Writes goals, action logs, autonomy checkpoints, and episodic memories.
Depends on restart-safe write discipline and strong recall fidelity.

**General agents**: Other Claude Code sessions or tools that need fact
recall from previous work. Read with the `general` retrieval profile (broader
recall, lighter filtering). Write shared memories. Do not need goal or
action-log surfaces.

Both clients share the same service and datastore. The difference is in
retrieval policy and which endpoint families each client uses — not in
deployment topology.

## System Cron Jobs

The autonomous agent maintains a set of standing cron jobs that constitute
its operational loop. These are defined as prompt files in `~/.claude/prompts/`
and recreated on session start if missing. The heartbeat cron (every hour)
verifies all others are active and recreates any that have lapsed.

Jobs marked **current** run against the implemented service surface. Jobs
marked **planned** depend on surfaces not yet built.

### Infrastructure and self-monitoring

| # | Name | Schedule | What it does |
|---|------|----------|--------------|
| 2 | Cron watchdog | Every 6h (:23) | Verify no crons are within 24h of their 7-day TTL; alert if any are about to expire |
| 4 | Heartbeat | Every 1h (:43) | System state check; verify all crons active and recreate missing; send one social message per day (50/50) if no alerts; silent 00:00–08:00 |
| 9 | Memory API health | Every 3h (:33) | Check service health endpoint; auto-restart if down; notify user of failures |

### Memory and knowledge maintenance

| # | Name | Schedule | What it does |
|---|------|----------|--------------|
| 10 | Weekly summarization | Sundays 4:47 | Compress old conversation logs into weekly summaries; originals preserved |
| 12 | Memory decay | Sundays 5:17 | `POST /memory/decay` with `halflife_days=60`; reduces confidence on unverified beliefs (**planned**) |

### Reflection and learning

| # | Name | Schedule | What it does |
|---|------|----------|--------------|
| 5 | Monthly usage | Days 28–31, 10:03 | Run usage report script; remind user to send stats from other machines |
| 6 | Reflection | Every 12h (11:27, 23:27) | Review logs for patterns, mistakes, and insights; save to `/reflection` |
| 7 | Preference learning | Daily 3:07 | Analyze feedback patterns; generate preference rules; propose code changes |

### Goal and plan management (planned)

| # | Name | Schedule | What it does |
|---|------|----------|--------------|
| 11 | Goal prioritizer | Daily 9:37 | Flag goals with deadline < 3 days or no progress > 5 days via `GET /goal/active` and `GET /goal/next` |

### Self-improvement surfaces (planned)

| # | Name | Schedule | What it does |
|---|------|----------|--------------|
| 13 | Daily metrics | Daily 22:23 | Compute `hallucination_rate`, `calibration_gap`, `world_model_precision`, `goals_completed_today`; write via `POST /metric` |
| 14 | Predictions resolver | Daily 21:53 | Resolve predictions with `due_at` in the past where evidence is clear |
| 15 | Skill promotion | Daily 2:37 | Auto-promote: `draft→beta` (≥ 1 run), `beta→stable` (≥ 3 runs and ≥ 66% success), `stable→deprecated` (< 50% in last 10) |
| 16 | Experiments runner | Every 6h (:17) | For running experiments below `min_samples`: pick variant with fewest observations, dry-run via `POST /sandbox/execute`, record observation; auto-conclude when threshold reached |
| 17 | World model grower | Daily 6:53 | Scan `GET /conversation/recent?hours=24`; detect 2+ mentions of same topic/entity/behavior; `POST /worldmodel`; auto-insert entity rows for people, projects, and places |
| 18 | Auto-audit | 3×/day (8:19, 14:19, 20:19) | Integrity scan: empty reflections, worldmodel with zero occurrences, memories without description, core tables stale > 7 days, capabilities with fail rate > 50%, overdue predictions; error → alert user; improvement opportunity → proposal |

## Planned Surface Design Notes

Concrete design decisions from the Friday reference implementation worth
adopting when these surfaces are implemented. Treat as a starting point, not
a constraint.

### Plan nodes

Flat table ordered by `(depth, order_idx)` rather than adjacency list or
recursive CTE. Root node has empty `parent_node`. Each node carries: `title`,
`description`, `tool`, `expected_result`, `exit_condition`, `rollback`,
`status` (pending/running/success/failed), `result` (populated on completion),
`depth`, `order_idx`, and FKs to both `goal_id` and `plan_id`.

### Sandbox

Three modes: `dry-run`, `simulation`, `live`. Verdict is a text enum:
`pending`, `pass`, `fail`. The `promoted_to_live` boolean flag tracks
in-place whether a dry-run execution was promoted rather than using a
separate live-execution table. Linked optionally to `plan_id`, `goal_id`,
and `skill_id`.

### Verification records

`check_type` enum: `factual`, `consistency`, `goal_alignment`, `hallucination`,
`uncertainty`, `evidence`. Two separate confidence fields: `confidence` (how
sure the verifier is about the verdict) and `halluc_risk` (estimated
probability the subject is a hallucination). `evidence` is opaque JSON;
`sources` is a JSON array of identifiers or URLs.

### Capability records

Bayesian confidence with Beta prior:
```
prior = 0.5, prior_weight = 5.0
new_confidence = (prior × prior_weight + observed_rate × total_runs)
                 / (prior_weight + total_runs)
```
Rolling averages for cost and time updated as:
`new_avg = (old_avg × prev_total + new_value) / total`. Last 20 error
types retained as a FIFO JSON array. `autonomy_max` (0–5) and
`max_risk_tier` are capability properties, not goal-specific.

### World model predictions

Resolution computes a Brier-score-style calibration gap:
`calibration = confidence − (1.0 if correct else 0.0)`. Near zero means
well-calibrated. Fields: `hypothesis`, `condition`, `predicted_outcome`,
`counterfactual`, `confidence`, `due_at`, `resolved`, `actual_outcome`,
`calibration`.

### Experiments

Observations are append-only records of `{variant, value, context, at}`.
Auto-conclude logic: rank variants by mean value; if the top two variants
both have `>= min_samples` (default 10) observations and their mean delta
`>= min_delta` (default 0.05), declare the top variant the winner.
Otherwise: inconclusive. No t-test or statistical significance; purely
mean-rank with thresholds.

### Metrics

KPI names as a validated set (unknown names accepted but warned):
`tasks_solved_no_correction_pct`, `hallucination_rate`,
`time_to_complete_goal_sec`, `skill_reuse_rate`, `skill_success_rate`,
`world_model_precision`, `calibration_gap`, `actions_reverted_pct`,
`cost_per_useful_task`, `goals_completed_per_week`,
`approved_improvements_effective_pct`. Stored as per-event rows; summary
endpoint aggregates over a 7-day window (latest, count, avg, min, max).

### Skills

Maturity states: `draft → beta → stable → deprecated`. Promotion guards:
`draft → beta` requires ≥ 1 recorded run; `beta → stable` requires ≥ 3 runs
AND ≥ 66% success rate. `trigger_pattern` is a free-text regex for
auto-invocation matching. Last 20 failure domains retained as FIFO JSON.
Success rate uses simple ratio (no Bayesian smoothing; unlike capabilities).

### Memory decay

Exponential decay applied when age exceeds the half-life:
```
factor = 0.5 ^ ((age_days − halflife_days) / halflife_days)
new_confidence = max(0.05, old_confidence × factor)
```
Default half-life: 60 days. Minimum floor: 0.05. Only applied when delta
≥ 0.01 (efficiency threshold). Decay clock resets on `POST /memory/<id>/verify`
which also boosts confidence by +0.1 (capped at 1.0). Decay runs across
memories, entities, and world model rows using `last_verified` timestamp,
falling back to `updated_at`.

### Soft world model and graduation flow

Soft observations land in `world_model` via `POST /worldmodel` with
`{category, pattern, evidence, confidence}`. When a row's pattern and
category match an existing row, occurrences increments and confidence
gets a small boost rather than inserting a duplicate. Query active
observations via `GET /worldmodel/active` (non-expired, confidence ≥ 0.4,
not yet promoted).

When a soft observation earns structure — causality, testability, or
S-P-O form — promote it via `POST /worldmodel/<id>/promote`. The source
row is retained as an audit chain; the structured record is written to
the appropriate `wm_*` table. This is the graduation flow:

```
world_model (soft) → promote → wm_events / wm_relations / wm_predictions
```

### Structured world model

Four tables for typed world-model facts, all distinct from the soft
`world_model` layer:

- **`wm_entities`** — current state of a thing (decays); fields: `name`,
  `type`, `state`, `attributes` (JSON), `confidence`. Distinguished from
  `entities` (which records stable identity) by mutability and decay.
- **`wm_relations`** — subject-predicate-object facts; fields: `subject`,
  `predicate`, `object`, `confidence`, `evidence`.
- **`wm_events`** — causal events; fields: `event_type`, `actor`, `target`,
  `payload` (JSON), `causes` (JSON array), `effects` (JSON array), `occurred_at`.
- **`wm_predictions`** — see World model predictions section above.

### Table ownership decision matrix

| Need to record...                              | Table            | Endpoint            |
|------------------------------------------------|------------------|---------------------|
| Who/what something IS (stable identity)        | `entities`       | `/entity`           |
| Current STATE of something (decays over time)  | `wm_entities`    | `/wm/entity`        |
| Loose pattern just noticed                     | `world_model`    | `/worldmodel`       |
| Testable future claim                          | `wm_predictions` | `/wm/prediction`    |
| Subject-predicate-object knowledge             | `wm_relations`   | `/wm/relation`      |
| Causal event (with causes/effects)             | `wm_events`      | `/wm/event`         |

### Three-layer memory views

Read-only projection endpoints over existing tables — not new storage:

- **`GET /memory/episodic?hours=`** — what happened, when; joins
  conversations and `wm_events` windowed by recency.
- **`GET /memory/semantic?type=`** — stable facts; joins memories and
  entities with provenance and confidence.
- **`GET /memory/procedural`** — skills with preconditions, tools,
  maturity state, and success rate.

### Self-evolving surfaces (reflections, preferences, insights, proposals)

These surfaces predate the v2 harness and support the agent's ongoing
operational self-improvement:

- **Reflections** — structured summaries of patterns, mistakes, and
  insights written by the reflection cron. Fields: `content`, `patterns`,
  `mistakes`, `insights`. Read via `GET /reflection/recent` and
  `/reflection/list`.
- **Preferences** — inferred behavioral rules with `rule`, `source_count`,
  and `confidence`. Active preferences (confidence ≥ 0.7) are loaded at
  session start and shape behavior. Written by the preference learning cron.
- **Insights** — typed observations (`type`, `pattern`, `evidence`,
  `confidence`) derived from reflections and world model analysis. Active
  insights are surfaced via `GET /insight/active`.
- **Proposals** — code or configuration improvement suggestions created by
  the agent via `POST /proposal` with `{file_path, change_type, description,
  diff_preview}`. The agent never applies changes directly; it proposes and
  waits for user approval. `GET /proposal/pending` surfaces the review queue.
  Approved proposals drive the preference learning and self-improvement loop.

### Cron snapshot endpoints

Two endpoints support the Crons dashboard tab and bootstrap reconciliation:

- **`POST /cron/active`** — replaces the runtime cron snapshot with the
  current job list `{crons: [{job_id, label, cron_expr, prompt_preview}]}`.
  Called at session start after all crons are created so the dashboard can
  show live countdowns.
- **`GET /cron/active`** — returns the current snapshot.
- **`GET /cron/prompts`** — parses `~/.claude/cron-prompts.md` (where
  cron prompt files persist across restarts) into labeled sections.

### Autonomy levels

`GET /autonomy/levels` returns the 6-rung autonomy ladder used by
capability and autonomy-check records:

| Level | Label       | Description                                    |
|-------|-------------|------------------------------------------------|
| L0    | suggest     | Proposes actions; human executes               |
| L1    | draft       | Produces artifacts; human reviews before use   |
| L2    | execute     | Executes reversible actions autonomously       |
| L3    | manage      | Manages multi-step workflows with checkpoints  |
| L4    | operate     | Operates systems with post-hoc audit           |
| L5    | self-modify | Modifies own code/prompts (requires approval)  |

`autonomy_max` on a capability record is the highest level the agent is
cleared to operate at for that capability. `POST /autonomy/check` gates
any action above the recorded level.

### Backup and restore

Disaster recovery endpoints for the SQLite datastore:

- **`GET /backup/info`** — DB path, size, last modified, disk free space,
  list of pre-import backup files.
- **`GET /backup/export`** — consistent snapshot via `VACUUM INTO`,
  streamed as a file attachment. `?format=dump` returns a portable SQL dump.
- **`POST /backup/import`** (form field `file`) — validates the uploaded
  SQLite file for schema integrity, backs up the current DB as
  `memory.db.pre-import-<timestamp>`, then swaps in the new file. Server
  restart required to reload connections.

### Importance keywords

Dynamic keyword scoring drives automatic importance classification on
conversation insert. Keywords and scores are managed via API:
`GET /keywords`, `POST /keywords` with `{keyword, score}`,
`DELETE /keywords/<id>`. Default scores: 1.0 (notes, saves), 0.8
(project, deploy, commit), 0.6 (search, URLs), 0.4 (user), 0.2
(assistant), 0.1 (system). Hit counts are tracked per keyword; the
preference learning cron uses them to adjust scores over time.

## Deployment

`BOOTSTRAP.md` in the repository root is the executable deployment
artifact derived from this document. It contains the exact `CLAUDE.md`
text to write, the 15 cron prompt files verbatim, and the verification
steps needed to bring up a fresh autonomous agent instance against the
already-running service. When the cron specs, operational rules, or
bootstrap contract in this document change, update `BOOTSTRAP.md` to
match. Do not edit `BOOTSTRAP.md` directly.

## What Memory Graph Is Not

Memory Graph is not a planner, a scheduler, a goal engine, or a world
model runtime. It does not decide what to do next. It does not execute
actions. It does not enforce autonomy policy at runtime.

Those responsibilities belong to Claude. Memory Graph's job is to make
Claude's decisions and actions durable, queryable, and auditable so that
each session can build on the work of prior sessions.
