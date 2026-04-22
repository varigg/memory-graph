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

- Episodic memory: what happened, when, with what outcome
- Semantic memory: stable facts and validated beliefs
- Goal records: active intentions with status, owner, and lifecycle history
- Action logs: executed steps with mode (dry-run/live/rollback) and result
- Autonomy checkpoints: gate decisions with rationale and reviewer type
- Entity and relation graph
- Key-value operational state
- Conversation history and embeddings for semantic recall

## Self-Improvement Loop

Each session reads prior context from memory-graph, acts, then writes back:

- memories capturing what was learned or validated
- goal status updates reflecting work completed
- action log entries recording what was executed and how it went
- autonomy checkpoint records for any risky actions taken

Future sessions read these records to understand what was tried before, what
worked, and what the current open obligations are. Over time this produces
an accumulated operational history that the agent can reason over.

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

## What Memory Graph Is Not

Memory Graph is not a planner, a scheduler, a goal engine, or a world
model runtime. It does not decide what to do next. It does not execute
actions. It does not enforce autonomy policy at runtime.

Those responsibilities belong to Claude. Memory Graph's job is to make
Claude's decisions and actions durable, queryable, and auditable so that
each session can build on the work of prior sessions.
