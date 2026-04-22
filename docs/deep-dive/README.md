# System Deep Dive

This directory is the companion to `docs/architecture.md`.

Use these files for durable, implementation-state context that should remain
useful after a feature plan is complete. The goal is to describe what the
system is and which invariants clients can rely on, not how implementation was
sequenced.

## Reading Map

- `write-atomicity.md` - transaction ownership, atomic write guarantees, and
  idempotency behavior.
- `retrieval-contracts.md` - retrieval profiles, read filters, ranking
  semantics, and guardrails.
- `lifecycle-and-trust.md` - lifecycle transitions, relation semantics,
  visibility/ownership rules, and verification model.
- `operations-and-maintenance.md` - operational metrics, integrity checks,
  SQLite maintenance helpers, and cleanup flows.
- `bridge-primitives.md` - goals, action logs, and autonomy checkpoints:
  schemas, endpoints, invariants, and transaction guarantees.

## Relationship To Plans

`docs/plans/` is for active implementation planning. Once a plan is
implemented, durable outcomes should be captured here and completed plan
documents should usually be removed. A completed plan may be retained when it
is intentionally serving as a concise implementation record referenced by
`docs/roadmap.md`.
