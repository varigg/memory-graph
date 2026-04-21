# ADR 0002: Treat Memory Graph As A Substrate, Not The Harness Runtime

## Status

Accepted

## Date

2026-04-21

## Context

The repository contains both an implemented local memory service and a broader
target-state harness vision in `harness.md`.

As features were added for long-running autonomous sessions, the boundary between
"memory substrate" and "autonomous runtime" became easier to blur. Without a
clear decision, the service could accumulate planner, scheduler, and world-model
responsibilities before its storage and retrieval contracts are stable.

## Decision

Memory Graph is currently the **memory substrate** for agent workflows, not the
full harness runtime.

The service may support autonomous-friendly primitives such as:

- restart-safe writes
- retrieval controls
- lifecycle status
- verification state
- lightweight observability

But it should not yet absorb the full harness responsibilities described in
`harness.md`, such as:

- goal engines
- planning trees
- world-model management
- autonomy control loops
- full runtime orchestration

## Consequences

### Positive

- preserves a stable architectural boundary
- keeps the current service focused on durable storage and retrieval concerns
- reduces premature coupling between memory management and orchestration logic

### Negative

- some harness-facing needs will remain intentionally deferred
- future clients must bridge to the service rather than assuming the service is
  already the harness backend

## Follow-On Direction

If harness work begins in earnest, the first additions should be thin bridge
primitives with explicit justification, not an immediate expansion into a full
runtime platform.
