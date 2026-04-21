# Copilot Instructions — memory-graph

## Service

The memory-graph REST API runs locally on **http://localhost:7777**.
DB: `~/.claude/memory.db`.
Start command: `MEMORY_DB_PATH=~/.claude/memory.db /home/varigg/code/memory-graph/.venv/bin/python /home/varigg/code/memory-graph/api_server.py`

When asked to store, retrieve, archive, or search memories in the shared store, curl the service directly. Always check `/health` first; if the service is down, inform the user rather than silently failing.

## Agent identity

Use `owner_agent_id=copilot` for all writes. This is the Copilot agent's namespace in the shared store.

## Visibility model

- `shared` — visible to all agents and the user. Default for facts worth sharing.
- `private` — visible only to the owning agent. Use for draft or agent-internal notes.

## Key endpoints

**Store a memory**

```
POST /memory
Content-Type: application/json
{"name": "<slug>", "content": "<text>", "owner_agent_id": "copilot", "visibility": "shared", "type": "note"}
```

Returns `{"id": <int>}`.

**Recall (FTS search within agent's visible set)**

```
GET /memory/recall?agent_id=copilot&topic=<term>
```

**Semantic search (embedding-based)**

```
GET /search/semantic?q=<phrase>&agent_id=copilot
```

**List memories**

```
GET /memory/list?agent_id=copilot&status=active
```

Optional filters: `visibility=shared|private`, `owner_agent_id=copilot`, `limit=N`, `offset=N`.

Additional retrieval filters: `run_id=<id>`, `tag=<token>`, `min_confidence=<0..1>`, `updated_since=<timestamp>`, `recency_half_life_hours=<positive>`.

**Memory usefulness scorecard**

```
GET /metrics/memory-usefulness
```

Use this to monitor current adoption of `run_id`, `idempotency_key`, `tags`, and verification coverage.

**Batch write**

```
POST /memory/batch
{"memories": [{...}, {...}]}
```

**Verification state update**

```
POST /memory/verify
{"memory_id": <int>, "agent_id": "copilot", "verification_status": "verified|unverified|disputed", "verification_source": "..."}
```

**Archive (soft-delete, keep for history)**

```
POST /memory/archive
{"memory_id": <int>, "agent_id": "copilot"}
```

**Supersede (mark old memory replaced by a new one)**

```
POST /memory/supersede
{"memory_id": <int>, "replacement_memory_id": <int>, "agent_id": "copilot"}
```

**Promote private → shared**

```
POST /memory/<id>/promote?agent_id=copilot
```

## When to use this service vs. built-in memory

Use built-in `/memories/repo/` for Copilot-private project conventions, build commands, and learnings — these persist across sessions at zero cost and are always available offline.

Use this service when:

- Recording a decision, invariant, or fact that other agents or the user should read back
- Performing semantic search across a large fact base
- Managing fact lifecycle (supersede stale facts, archive resolved issues)
- The user explicitly asks to store or retrieve from the memory graph

Do not write to the service speculatively or on every turn. Write only when there is clear durable value in the shared store.

## Session continuity hints

- At the start of substantial work or resumed sessions, read context first with:
  - `GET /memory/list?agent_id=copilot&status=active&limit=20`
  - and targeted `GET /memory/recall?...` for the active topic/run.
- Also check `GET /metrics/memory-usefulness` at session start or milestone boundaries to see whether memory workflow conventions are actually being followed.
- During substantial work, write durable checkpoints (decision, implementation milestone, verification outcome), not chat transcripts.
- For substantial work, prefer checkpoint writes that include `run_id`, `idempotency_key`, and `tags` so the usefulness scorecard becomes meaningful over time.
- Prefer `idempotency_key` and `run_id` for restart-safe writes and deterministic replays.
- Use `visibility=private` for draft/internal checkpoints; promote to `shared` when validated.
- Archive/invalidate/supersede outdated memories to keep recall quality high.

## Required planning policy

- `docs/roadmap.md` is the canonical living feature tracker.
- Whenever development changes a feature's status, scope, or canonical source of
  truth, update `docs/roadmap.md` in the same change set as the code/doc change.
