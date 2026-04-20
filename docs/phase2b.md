# Phase 2B — FTS Index Correctness

## Goal

Guarantee FTS tables stay synchronized with base tables across insert, update,
and delete operations.

## Implemented

- Added `AFTER UPDATE` and `AFTER DELETE` triggers for:
  - `conversations` -> `fts_conversations`
  - `memories` -> `fts_memories`
- Kept existing insert triggers.
- Trigger writes use `COALESCE` for NULL-safe index entries.

## Why this matters

Before this phase, updates/deletes could leave stale FTS rows and produce false
or missing search results.

## Validation

- Added tests that mutate/deletes base rows and assert FTS search consistency.
- Added NULL-handling test coverage for trigger flows.
- Full suite passed after phase completion.
