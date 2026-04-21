# Conversation Outcomes

This document captures the durable outcomes from plan and design discussions so
they are not left implicit in chat history alone. It complements the phase
documents by answering a different question: what decisions were made, what did
they change, and where should a future session look next?

## How To Read This File

- Use this file as the decision/outcome index.
- Use `README.md` as the documentation hub.
- Use the linked docs below for implementation detail.

## Outcome Ledger

| Decision / Topic                                                                                   | Outcome                                                                                                                                       | Status                                  | Primary References                                                      | Next Step                                                            |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Phase 1 and 2 review output was fragmented across multiple files                                   | Review and implementation notes were consolidated into one canonical document                                                                 | Implemented                             | `docs/phase1-2-consolidated.md`                                         | Keep it updated instead of restoring split phase 1/2 review docs     |
| The backend should support autonomous-agent usage patterns even before full harness support exists | Added restart-safe operating guidance for agents using the service                                                                            | Implemented                             | `docs/agent-memory-ops.md`, `.github/copilot-instructions.md`           | Add observability for whether recalled memories were actually useful |
| The memory API needed better support for long-running autonomous sessions                          | Added batch writes, idempotency keys, typed metadata write/filter support, retrieval controls, and verification state updates                 | Implemented                             | `README.md`, `blueprints/memory.py`, `db_schema.py`, `db_operations.py` | Add evidence-oriented verification records                            |
| The repo needed consistent environment conventions for repeatable local work                       | Standardized on `uv` + `.venv` and documented cleanup guidance for stale `VIRTUAL_ENV` and duplicate local envs                               | Implemented                             | `README.md`, `docs/agent-memory-ops.md`                                 | Keep shell/session setup aligned with `uv run ...`                   |
| The service should be used actively during sessions, not just documented                           | Copilot instructions now explicitly tell future sessions to recall context first and write durable checkpoints during substantial work        | Implemented                             | `.github/copilot-instructions.md`                                       | Evaluate usefulness with metrics instead of anecdotal recall         |
| The README did not act as a coherent documentation hub                                             | Added a documentation guide and reading path tying together README, phase docs, agent ops, harness vision, and Copilot instructions           | Implemented                             | `README.md`                                                             | Keep new docs linked here when they become canonical                 |
| The autonomous harness vision needed to be kept separate from currently implemented backend scope  | `harness.md` remains the target-state design, while current implemented scope is documented separately                                        | Implemented as documentation boundary   | `harness.md`, `README.md`, `docs/phase3-overview.md`                    | Add a feature matrix for implemented-vs-target harness capabilities  |
| The current API is a foundation for the harness, not the full harness runtime                      | Established a working interpretation: strong data substrate, partial lifecycle support, limited autonomy/control-loop support                 | Implemented as documented understanding | `README.md`, `harness.md`, `docs/agent-memory-ops.md`                   | Add minimal goal/autonomy primitives if harness work begins          |
| Some older planning assumptions were superseded by later implementation                            | Earlier backlog assumptions such as deferring bulk mutation APIs and retrieval filters are no longer fully current after recent API additions | Partially documented                    | `docs/phase3-backlog.md`, `README.md`, `docs/agent-memory-ops.md`       | Reconcile phase 3 backlog docs with current implementation state     |

## Current High-Signal Themes

### 1. Memory service usage is now part of the workflow

The service is no longer just the product under development. It is also part of
the development loop for autonomous sessions through checkpoint writes, restart
recovery, and verification state tracking.

### 2. Current implementation is ahead of some planning docs

The codebase now includes behavior that older backlog text still describes as
future work. Future planning should treat the README and current API behavior as
authoritative unless and until the backlog is reconciled.

### 3. Harness alignment is still architectural, not feature-complete

The repository now better supports harness-style operation, but it does not yet
implement the goal engine, autonomy checks, world-model tables, metrics engine,
or skill compiler described in `harness.md`.

## Recommended Maintenance Rule

Whenever a significant design discussion changes implementation priorities,
workflow conventions, or the interpretation of existing plans, update this file
in the same change set as the code or doc edits that implement the decision.
