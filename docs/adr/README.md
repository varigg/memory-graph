# ADR Index

This directory contains **Architecture Decision Records** for Memory Graph.

Use ADRs for decisions that should remain understandable months later even if
the surrounding code changes. An ADR should explain:

- the context that made the decision necessary
- the decision itself
- the consequences and tradeoffs

## How ADRs Relate To Other Docs

- `docs/architecture.md` explains the current system shape.
- `docs/roadmap.md` tracks what is implemented, planned, or deferred.
- `docs/conversation-outcomes.md` records broader discussion outcomes.

Use an ADR when the question is: "Why is the system shaped this way?"

## Numbering

ADRs use zero-padded numeric prefixes in creation order.

## Current ADRs

- `0001` Keep Memory Graph as one local service with a shared core
- `0002` Treat Memory Graph as a substrate, not the harness runtime

## Guidance For Future ADRs

Prefer creating an ADR for decisions such as:

- splitting or not splitting major runtime boundaries
- changing the persistence model
- changing retrieval policy defaults in a durable way
- introducing a new subsystem with long-term maintenance cost

Do not create ADRs for every minor refactor or implementation detail.
