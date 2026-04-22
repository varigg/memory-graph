# ADR 0001: Keep Memory Graph As One Local Service With A Shared Core

## Status

Accepted

## Date

2026-04-21

## Context

Memory Graph started from an autonomous-agent-oriented design, but the memory
and recall capabilities later proved useful for general local agents as well.
That introduced a design question: should the repository grow into two services,
one for autonomous use and one for broader local-agent use?

The pressure toward a split came from different retrieval needs:

- autonomous usage wants low-noise, continuity-oriented retrieval
- general usage wants broader and more exploratory recall

At the same time, both use cases still rely on the same core capabilities:

- local SQLite persistence
- FTS and embedding-backed retrieval
- lifecycle transitions
- idempotent writes
- run tracking, tags, and metadata
- embedding deduplication and reindexing

## Decision

Memory Graph will remain **one local service with one shared datastore**.

The system will not be split into separate autonomous-agent and general-agent
services at this stage.

Instead, the architecture should evolve toward:

- one shared storage and indexing core
- explicit retrieval profiles or endpoint families
- clearer internal service-layer boundaries for policy and ranking behavior

## Consequences

### Positive

- avoids duplicating schema, indexing, and lifecycle logic
- preserves a single operational surface for local use
- keeps embeddings and deduplication logic centralized
- allows retrieval behavior to diverge without forcing infrastructure splits

### Negative

- the API must carry clearer retrieval-policy semantics
- code boundaries must improve so that one service does not become one large
  undifferentiated module set
- client behavior cannot be allowed to define the contract implicitly

## Follow-On Direction

The next architectural step is not a deployment split. It is to make retrieval
profiles explicit and extract policy logic from transport-layer handlers.
