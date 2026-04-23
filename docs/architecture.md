# Architecture

This document describes the current architectural shape of Memory Graph, why
it exists in this form, and which boundaries are now implemented versus still
evolving.

Use this file for the current-state architecture narrative.
Use `docs/vision.md` for the overall system vision including Claude's role.
Use `docs/deep-dive/` for subsystem-level implementation state and invariants.
Use the ADRs in `docs/adr/` for durable decision records.
Use `docs/roadmap.md` for implementation status.

## Why This Document Exists

The repository already has strong phase summaries, backlog notes, and an
outcomes ledger, but it was missing a single document that answered these
questions clearly:

- What is the service, architecturally?
- What are the main runtime and code boundaries?
- Why is it one service instead of multiple targeted services?
- How should future work preserve or evolve those boundaries?

This file is the answer to those questions.

## Current System Role

Memory Graph is a **local-first persistence substrate** for Claude Code-based
agent workflows.

The cognitive runtime is Claude Code itself — a long-running session that
plans, decides, and acts. Memory Graph holds the durable state that must
survive beyond a single session: memories, goals, action logs, autonomy
checkpoints, conversation history, and embeddings.

The service has two client modes:

- an **autonomous Claude Code agent** that benefits from conservative,
  low-noise retrieval and restart-safe write discipline
- **general local agents** that benefit from broader shared recall and lighter
  operational constraints

These use cases share the same storage, indexing, and lifecycle primitives.
The divergence is in **retrieval policy**, not in persistence model or
deployment topology.

## Architectural Position

The service is **one deployable local service with one database**. Retrieval
and write policy are made explicit through profiles and service-layer rules
rather than through a deployment split.

The current architectural direction:

- one shared SQLite-backed store
- one HTTP service surface
- explicit retrieval profiles for different client modes
- clean layer boundaries between transport, domain, and storage concerns

## Core Building Blocks

### 1. Transport Layer

Flask blueprints provide the HTTP surface for:

- conversations
- memory CRUD and lifecycle
- search and embeddings
- KV and utility endpoints
- goals, action logs, and autonomy checkpoints (bridge primitives)

These handlers are intentionally thin transport adapters. Shared request
parsing lives in `blueprints/_params.py`. Lifecycle, retrieval, write
orchestration, and hybrid ranking live in the service layer.

### 2. Storage Layer

SQLite is the source of truth for:

- conversations
- memories and memory relations
- entities
- embeddings
- key-value state
- goals, goal status history, action logs, and autonomy checkpoints (bridge primitives)

FTS5 and embedding-based retrieval are both implemented on top of this local
store. Repository modules under `storage/` own SQL construction, row mapping,
and table-specific persistence helpers.

### 3. Retrieval Layer

The system supports:

- lexical recall through FTS5
- semantic search through embeddings
- hybrid ranking (RRF)
- memory filters for visibility, ownership, lifecycle status, task/run
  context, recency, confidence, and metadata
- explicit retrieval profiles (`profile=general|autonomous`)

Retrieval orchestration lives in `services/`. The storage layer owns raw
queries; the service layer owns profile dispatch, scoping rules, and ranking
behavior.

### 4. Lifecycle and Trust Layer

Memory rows carry operational semantics beyond simple CRUD:

- visibility (shared/private)
- ownership (`owner_agent_id`)
- lifecycle status (active/archived/invalidated)
- verification status (unverified/verified/disputed)
- run tracking (`run_id`)
- idempotency keys
- tags and metadata

Goal, action-log, and autonomy-checkpoint records extend this with
structured lifecycle semantics for auditable agent operations.

## Retrieval Modes

### Autonomous Mode

For the long-running Claude Code agent.

Defaults:

- `status=active`
- stronger recency and confidence bias
- preference for run/task-local memories when available
- smaller result sets
- safer defaults that reduce accidental broad recall

### General Mode

For exploratory or operator-driven Claude Code sessions.

Defaults:

- broader shared recall
- looser filtering
- less aggressive narrowing
- useful for ad hoc lookup and discovery

These are retrieval profiles, not separate services.

## Why Not Split Into Two Services

One service remains the right call because both client modes rely on:

- shared schema evolution
- shared indexing and embeddings
- shared lifecycle state transitions
- shared memory ranking logic
- shared compaction and deduplication behavior
- shared observability and maintenance tooling

The use cases do not justify separate persistence, availability, or trust
boundaries. The divergence is in how clients retrieve data, which is cheaper
to express as retrieval policy within one service.

If the system later needs two surfaces, the safer path is:

- one shared core library
- one shared datastore
- two thin API surfaces or endpoint families

That is a code-boundary refactor, not a storage or deployment split.

## Current Code Boundaries

### Transport Adapters

Blueprints own:

- request parsing
- response formatting
- HTTP status selection

Implemented in `blueprints/`, with repeated query-parameter parsing
consolidated into `blueprints/_params.py`.

### Domain Services

Service modules own:

- retrieval policy selection
- lifecycle rules
- ranking behavior
- authorization and visibility semantics
- idempotency and batch-write orchestration
- ownership validation for goal/action/checkpoint resources

Implemented in `services/`.

### Repository / Query Helpers

Storage modules own:

- SQL construction
- row mapping
- transaction boundaries

Implemented in `storage/`. Connection acquisition flows through
`db_utils.get_db()`. Schema and migration ownership stays in `db_schema.py`.

The architectural work is no longer to create these layers. It is to keep
them narrow, preserve dependency direction, and avoid policy drift back into
the blueprints.

## Documentation Strategy

- `docs/vision.md` explains the overall system goal including Claude's role.
- `docs/architecture.md` (this file) explains the service shape and design intent.
- `docs/deep-dive/` captures subsystem-level implemented behavior and invariants.
- `docs/adr/` captures durable architecture decisions.
- `docs/conversation-outcomes.md` is the discussion outcome ledger.
- `docs/roadmap.md` is the implementation status tracker.
- `docs/plans/` is for active implementation planning only; once complete,
  durable details should be promoted into `docs/deep-dive/` or other
  canonical docs.

## Near-Term Architectural Priorities

1. Keep retrieval profile behavior stable and explicit across memory read
   endpoints as additional read surfaces evolve.
2. Keep service-owned transaction boundaries consistent for multi-step write
   flows and avoid reintroducing repository-level implicit commits.
3. Keep bridge primitive surfaces (goals, action logs, autonomy checkpoints)
   stable; extend only when the autonomous agent demonstrates a concrete gap.
4. Keep broader runtime concerns — planning, scheduling, skill execution,
   autonomy policy — in Claude Code rather than absorbing them into the service.
