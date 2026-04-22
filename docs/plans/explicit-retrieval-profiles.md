# Plan: Explicit Retrieval Profiles (Historical)

## Status

- Implemented: 2026-04-22

## Implemented Outcome

Retrieval profiles are implemented on:

- `GET /memory/list`
- `GET /memory/recall`
- `GET /memory/search`

Implemented profile behavior:

- `profile=general` uses permissive defaults
- `profile=autonomous` injects defaults (`status=active`,
  `min_confidence=0.7`, `recency_half_life_hours=168`) when caller omits them
- explicit query parameters always override profile defaults
- `profile=autonomous` requires non-empty `agent_id`

## Durable References

- `docs/deep-dive/retrieval-contracts.md`
- `docs/roadmap.md`
- `README.md`

## Historical Notes

This file is intentionally concise. It remains as an implementation pointer.
Durable system-state documentation moved to `docs/deep-dive/`.
