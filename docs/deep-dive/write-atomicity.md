# Write Atomicity

This document captures the current write-path invariants that callers and
maintainers can rely on.

## Transaction Ownership Model

Write transactions are service-owned.

- Blueprints parse requests and map service outcomes to HTTP responses.
- Services define the logical mutation boundary.
- Repository helpers execute SQL and return values without committing.

The shared transaction primitive is `write_transaction(db)` in `db_utils.py`.
On success it commits once; on any exception it rolls back the full unit.

## Endpoint-Level Atomicity

The following mutation flows are atomic at the logical operation level:

- `POST /memory`
- `POST /memory/batch`
- `POST /memory/archive`
- `POST /memory/invalidate`
- `POST /memory/verify`
- `POST /memory/<id>/promote`
- `POST /memory/merge`
- `POST /memory/supersede`
- `POST /memory/cleanup-private` when `dry_run=false`
- `DELETE /memory/<id>`

For batch writes, all items succeed or the database remains unchanged.

## Idempotency Semantics

When `idempotency_key` is provided, `owner_agent_id + idempotency_key` defines
the replay identity for memory creation.

- first write: creates a memory row and returns `created=true`
- replay with same key and owner: returns existing id and `created=false`

In `POST /memory/batch`, idempotency checks occur inside the same transaction
as writes, so partial replay artifacts are avoided.

## Repository Constraints

`storage/memory_repository.py` intentionally keeps composable helpers
non-committing (`insert_memory`, `delete_memories_by_ids`). This prevents
repository-level implicit commits from breaking service-owned atomicity.

## Stability Notes

Any future bridge primitives should reuse the same transaction ownership model:
logical units should commit once at the service boundary and rollback as a
whole on failure.