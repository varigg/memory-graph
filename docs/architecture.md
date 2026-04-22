# Architecture

This document describes the current architectural shape of Memory Graph, why it
exists in this form, and which boundaries are now implemented versus still
evolving.

Use this file for the current-state architecture narrative.
Use the ADRs in `docs/adr/` for durable decision records.
Use `docs/roadmap.md` for implementation status.

## Why This Document Exists

The repository already has strong phase summaries, backlog notes, and an
outcomes ledger, but it was missing a single document that answered these
questions clearly:

- What is the system, architecturally?
- What are the main runtime and code boundaries?
- Why is it one service instead of multiple targeted services?
- How should future work preserve or evolve those boundaries?

This file is the answer to those questions.

## Current System Role

Memory Graph is currently a **local-first memory substrate** for agentic
workflows.

It is not yet the full harness runtime described in `harness.md`.
It is also no longer only a single-agent backend.
It now serves two closely related usage modes:

- a **continuously running autonomous agent** that benefits from conservative,
  low-noise retrieval and restart-safe write discipline
- **general local agents** that benefit from broader shared recall and lighter
  operational constraints

The important architectural conclusion is that these use cases still share the
same storage, indexing, and lifecycle primitives. The divergence is primarily in
**retrieval policy**, not in persistence model or deployment topology.

For harness v2, this repository should move as quickly as possible toward the
durable substrate that the harness depends on, without prematurely absorbing the
goal engine, planner, world model, experiment system, or other cognition-layer
subsystems described in `harness.md`.

## Architectural Position

The service should remain **one deployable local service with one database**,
while making retrieval and write policy more explicit.

The current architectural direction is:

- one shared SQLite-backed memory engine
- one HTTP service surface
- explicit retrieval profiles for different agent modes
- a clean separation between current substrate responsibilities and deferred
  harness runtime responsibilities

This keeps the core durable and simple while preventing client behavior from
implicitly defining the system contract.

The fastest non-shortcut path to harness v2 is therefore:

- finish the substrate invariants the harness will rely on
- make retrieval behavior explicit for autonomous versus general clients
- add only the smallest harness-facing primitives that need to live beside the
  memory substrate

## Core Building Blocks

### 1. Transport Layer

Flask blueprints provide the HTTP surface for:

- conversations
- memory CRUD and lifecycle
- search and embeddings
- KV and utility endpoints

After the service-layer refactor, these handlers are intentionally thin
transport adapters. Shared request parsing lives in `blueprints/_params.py`,
while lifecycle, retrieval, write orchestration, and hybrid ranking behavior
live outside the blueprints.

### 2. Storage Layer

SQLite is the source of truth for:

- conversations
- memories
- entities
- embeddings
- key-value state
- lifecycle relations

FTS5 and embedding-based retrieval are both implemented on top of this local
store.

Repository modules under `storage/` now own SQL construction, row mapping, and
table-specific persistence helpers.

### 3. Retrieval Layer

The system currently supports:

- lexical recall through FTS
- semantic search through embeddings
- hybrid ranking
- memory filters for visibility, ownership, lifecycle status, task/run context,
  recency, confidence, and metadata

This is the main area where the architecture needs clearer policy boundaries.
The system has enough primitives, but the default retrieval contract is still
too implicit.

Retrieval orchestration is now separated from raw SQL. `services/` owns scoped
versus unscoped dispatch, hybrid-ranking orchestration, lifecycle rules, and
write-path normalization, while `storage/` owns the underlying queries.

### 4. Lifecycle and Trust Layer

Memory rows carry operational semantics beyond simple CRUD:

- visibility
- ownership
- lifecycle status
- verification status
- run tracking
- idempotency keys
- tags and metadata

This is what makes the service useful for long-running agent workflows rather
than only as a generic note store.

Near-term harness v2 work should prefer extending this layer with auditable
bridge records and stable write semantics before adding broader runtime control
surfaces.

## Intended Retrieval Modes

The current code evolved from a single-agent design toward shared usage by
multiple local agents. The recommended model is to formalize that evolution into
two retrieval modes.

### Autonomous Mode

Use when the client is a continuously running or restart-sensitive agent.

Desired defaults:

- `status=active`
- stronger recency and confidence bias
- preference for run/task-local memories when available
- smaller result sets
- optional duplicate/result collapse to reduce prompt pollution
- safer defaults that reduce accidental broad recall

### General Mode

Use when the client is a local exploratory agent or operator-driven workflow.

Desired defaults:

- broader shared recall
- looser filtering
- less aggressive narrowing
- useful for ad hoc lookup and discovery

These are **retrieval profiles**, not separate systems.

## Why Not Split Into Two Services Now

The codebase should not be split into separate autonomous-agent and general-agent
services yet.

That split would currently duplicate or entangle:

- schema evolution
- indexing and embeddings
- lifecycle state transitions
- memory ranking logic
- compaction and deduplication behavior
- observability and maintenance tooling

The use cases do not yet justify separate persistence, availability, or trust
boundaries. The divergence is mainly in **how clients should retrieve and rank
data**, which is cheaper and cleaner to express as policy within one service.

If the system later needs two surfaces, the safer path is:

- one shared core library
- one shared datastore
- two thin API surfaces or endpoint families

That is a code-boundary refactor first, not a storage or deployment split.

## Current Code Boundaries

The service-layer refactor is now in place. The current internal boundary model
is:

### Transport Adapters

Blueprints should focus on:

- request parsing
- response formatting
- HTTP status selection

This boundary is implemented in `blueprints/`, with repeated query-parameter
parsing consolidated into `blueprints/_params.py`.

### Domain Services

Service modules should own:

- retrieval policy selection
- lifecycle rules
- ranking behavior
- authorization and visibility semantics
- idempotency and batch-write orchestration

This boundary is implemented in `services/` via dedicated modules for memory
write, lifecycle, retrieval, and hybrid search behavior.

### Repository / Query Helpers

Database modules should own:

- SQL construction
- row mapping
- transaction boundaries
- connection/session initialization

This boundary is implemented primarily in `storage/`. Connection acquisition
still flows through `db_utils.get_db()`, and schema/migration ownership remains
in `db_schema.py`.

The remaining architectural work is no longer to create these layers. It is to
keep them narrow, preserve dependency direction, and avoid policy drift back
into the blueprints.

## Relationship To Harness

`harness.md` remains the target-state design for a broader autonomous runtime.

Memory Graph should currently be treated as:

- the memory substrate
- a partial lifecycle and trust substrate
- a useful local retrieval service

It should not yet be treated as the full orchestrator or runtime controller.

That boundary matters because it prevents premature growth of this service into a
planner, scheduler, world model, or autonomy engine before the memory substrate
is fully stable.

The practical implication is that harness v2 should first consume Memory Graph as
an audited storage and retrieval backend. The first integration steps should be
minimal bridge primitives such as goal/action-log/autonomy-checkpoint records or
other narrow surfaces that are clearly shared substrate concerns. Goal ranking,
plan execution, learning loops, experiments, and broader runtime policy should
remain in the harness unless repeated usage proves they belong here.

The concrete implementation plan for that first bridge slice lives in
`docs/plans/harness-v2-bridge-primitives.md`.

## Documentation Strategy

The recommended documentation model is a **mix**, not a single monolithic file
and not a retroactive ADR for every historical detail.

- `docs/architecture.md` explains the current system shape and design intent.
- `docs/adr/` captures durable architecture decisions that should remain stable
  over time.
- `docs/conversation-outcomes.md` remains the discussion outcome ledger.
- `docs/roadmap.md` remains the status tracker.

This avoids two failure modes:

- one document that becomes a catch-all dumping ground
- a large set of backfilled ADRs that read like reconstructed history rather
  than real decisions

## Near-Term Architectural Priorities

1. Keep retrieval profile behavior stable and explicit across memory read
  endpoints (`profile=general|autonomous`) as additional read surfaces evolve.
2. Keep service-owned transaction boundaries consistent for multi-step write
  flows and avoid reintroducing repository-level implicit commits.
3. Add the minimum harness-facing bridge primitives needed for v2 integration
   only after retrieval and write invariants are reliable.
4. Add stronger isolation-friendly seams and focused unit tests around service
   modules where they directly improve harness integration safety.
5. Keep broader harness runtime concerns out of this service unless there is a
   deliberate decision to expand beyond the substrate role.
