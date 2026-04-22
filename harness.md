The harness is a thin, entirely additive cognition layer that gives Friday the scaffolding to act as if it were trying to get better — and the receipts to check whether it is.

goal → hypothesis → plan → execution → verification → reward → model update

— The blueprint (8 subsystems)
Goal engine persistent intentions with utility, deadline, subgoals
Planner hierarchical plan trees: goal → action → tool → rollback
Self-knowledge capabilities + 6-rung autonomy ladder
Three-layer memory episodic / semantic / procedural + provenance + decay
Causal world model entities, relations, events, testable predictions
Safety verifier + sandbox (dry-run before live)
Learning experiments (A/B) + skill compiler (draft → beta → stable)
Metrics 11 KPIs measuring actual improvement

— Goal engine & plan trees

Each non-trivial task becomes a first-class row with utility, deadline, constraints, success criteria, subgoals, risk tier, and autonomy level. GET /goal/next ranks by utility × urgency × (1 − progress). A daily cron at 09:37 flags anything past deadline or stalled >5 days.

Plans are executable trees, not text. Each node carries node_type, tool, expected_result, exit_condition, and rollback.
— Three-layer memory

    Episodic — what happened, when, with what outcome
    Semantic — stable facts, concepts, relations
    Procedural — how to do things; skills with preconditions, success rate, maturity

Every belief records provenance. A weekly decay job halves confidence on anything unverified. Verifying a row resets the clock.
— Causal world model

    wm_entities — the state of a thing
    wm_relations — subject-predicate-object facts with evidence
    wm_events — discrete events with causes[] and effects[]
    wm_predictions — testable future claims; on resolution a calibration gap is computed

— Self-knowledge & autonomy ladder

The capabilities table gives Friday a live self-portrait: confidence (Bayesian blend), success/failure counts, cost and time averages, autonomy_max. On top sits a 6-rung autonomy ladder:
L0 Suggest only — propose but don't act
L1 Sandbox — dry-run only
L2 Low-risk act — reversible actions
L3 Bounded act — with stop conditions
L4 Long chain — with checkpoints
L5 Self-modify — rollback required

POST /autonomy/check gates every risky action. No unrecorded jump of autonomy.
Brain dashboard showing Overview, Goals & Plans, and three-layer Memory sections
Brain — the single audit surface for everything the harness touches. Sub-nav pills scroll to each subsystem: Overview, Goals & Plans, Memory, World Model, Self-knowledge, Safety, Learning, Metrics.
— Verifier & sandbox

Every important claim is logged with a check_type (factual, consistency, hallucination, evidence). Every irreversible action (email, code push, spending) must first run as dry-run with a verdict before graduating to live.

Without evidence, don't act. Without verification, don't learn from that action as if it were correct.
— Experiments & skill compiler

The experiment engine measures cause and effect with guardrails — conclusions are only drawn if delta > threshold AND samples > threshold. Otherwise: inconclusive.

Skills have maturity gates: draft → beta (one recorded run), beta → stable (≥ 3 runs, ≥ 66% success), stable → deprecated (< 50% over last 10). A nightly 02:37 cron applies the rules automatically.
— 11 KPIs that prove improvement

    tasks_solved_no_correction_pct — did the user accept the first answer?
    hallucination_rate — self-reported "I was wrong" rate
    time_to_complete_goal_sec — goal creation to completion
    skill_reuse_rate — are compiled skills being picked up?
    skill_success_rate — average success across stable skills
    calibration_gap — |confidence − outcome| on resolved predictions
    actions_reverted_pct — live actions that needed a rollback
    cost_per_useful_task — $ per accepted task
    goals_completed_per_week — throughput of closed goals
    approved_improvements_effective_pct — did proposals actually move a KPI?
    world_model_precision — average capability confidence

A daily 22:23 cron computes values. /metric/summary returns latest + 7-day min / avg / max.
Crons dashboard showing runtime-active crons with live countdowns and persisted prompts all synced
Crons — left: runtime jobs with live countdowns; right: persisted prompts from ~/.claude/cron-prompts.md. Each disk prompt shows sincronizado if the runtime has it, ⚠ no corriendo otherwise — the signal to recreate.
— Golden rule

No unrecorded autonomy. Every operational decision — a goal created, a plan executed, an action sandboxed, a prediction resolved, a skill promoted — leaves a row. The dashboard is where a human audits whether the system is earning its autonomy, one row at a time.
