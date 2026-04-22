# ADR 0002: Memory Graph Is The Persistence Substrate; Claude Code Is The Runtime

## Status

Accepted

## Date

2026-04-21 (updated 2026-04-22)

## Context

As features were added for long-running autonomous sessions, the boundary
between "memory substrate" and "autonomous runtime" became easier to blur.
Without a clear decision, the service could accumulate planner, scheduler,
and world-model responsibilities before its storage and retrieval contracts
are stable.

The intended runtime for the autonomous agent is a long-running Claude Code
session, not a separate harness process. Claude Code handles reasoning,
planning, scheduling, and execution. Memory Graph holds the durable state
those sessions depend on.

## Decision

Memory Graph is the **persistence substrate** for Claude Code-based agent
workflows. Claude Code is the cognitive runtime.

The service owns:

- durable storage and retrieval of memories, goals, action logs, and
  autonomy checkpoints
- lifecycle and trust semantics (ownership, verification, idempotency)
- retrieval profiles for different client modes
- lightweight observability

The service does not own:

- goal engines or planning loops
- scheduling or cron management
- world-model reasoning
- autonomy policy enforcement at runtime
- skill execution or tool orchestration

Those responsibilities belong to Claude Code. The service's job is to make
Claude's decisions and actions durable and queryable across sessions.

## Consequences

### Positive

- preserves a stable architectural boundary
- keeps the service focused on durable storage and retrieval
- reduces premature coupling between memory management and orchestration
- Claude Code gains full cognitive flexibility without service-side constraints

### Negative

- some state that feels "cognitive" (goals, skills, reflections) lives in
  the service as durable records rather than in a purpose-built planner —
  that is intentional but requires discipline to maintain the boundary
- clients must write structured records to the service rather than assuming
  the service tracks their intent automatically

## Follow-On Direction

Additions to the service should be durable record surfaces with explicit
justification — not runtime orchestration logic. The goal/action-log/
autonomy-checkpoint bridge primitives are the current example of this
pattern done correctly.
