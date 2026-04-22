# Copilot Instructions — memory-graph

## Service

The memory-graph REST API runs locally on **http://localhost:7777**.
DB: `~/.claude/memory.db`.
Start command: `MEMORY_DB_PATH=~/.claude/memory.db /home/varigg/code/memory-graph/.venv/bin/python /home/varigg/code/memory-graph/api_server.py`

For substantial tasks, proactively store durable checkpoints and important findings in the shared store at task end using the wrapper (`agent_memory_client.py`). Use direct curl for quick/manual checks and one-off debugging. Always check `/health` first; if the service is down, inform the user rather than silently failing.

## Agent identity

Use `owner_agent_id=copilot` for all writes. This is the Copilot agent's namespace in the shared store.

## Visibility model

- `shared` — visible to all agents and the user. Default for facts worth sharing.
- `private` — visible only to the owning agent. Use for draft or agent-internal notes.

## Key endpoints

Prefer the wrapper for substantial tasks. Keep this list as a quick reference for
manual checks and debugging.

**Health check**

```
GET /health
```

**Run-scoped recovery / listing**

```
GET /memory/list?agent_id=copilot&status=active&run_id=<id>
```

Common filters: `tag=<token>`, `limit=N`, `offset=N`, `updated_since=<timestamp>`,
`recency_half_life_hours=<positive>`.

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

**Semantic retrieval**

```
GET /search/semantic?q=<phrase>&agent_id=copilot
```

**Memory usefulness scorecard**

```
GET /metrics/memory-usefulness
```

Use this to monitor adoption of `run_id`, `idempotency_key`, `tags`, and verification coverage.

## Memory policy (authoritative defaults)

Use a three-tier hybrid model:

- `/memories/session/` is ephemeral task journal context.
- `/memories/repo/` holds durable repo conventions and constants.
- memory-graph API stores curated, durable findings/decisions.

Operational execution details are defined in the skill at:
`/home/varigg/.claude/skills/memory-graph-ops/SKILL.md`

Wrapper for API operations:
`/home/varigg/code/memory-graph/agent_memory_client.py`

### Required execution behavior

- For substantial tasks, use the wrapper for writes and restart queries.
- Proactively capture important checkpoints, validated findings, and durable decisions at task end even when the user did not explicitly ask for a memory write.
- Do not store chat transcripts or speculative notes; promote only durable, high-signal task outcomes.
- Always health-check before writes (`GET /health`), and report outage instead of silently failing.
- Write durable memories at task end (not every turn), with `run_id`, `tags`, and deterministic `idempotency_key`.
- Verification is two-pass: batch-write first, then verify confirmed findings with `POST /memory/verify`.
- Keep uncertain findings `unverified` until external review.
- At restart, recover via `run_id`-scoped reads from the API; do not rely on prior session scratch notes.

### Documentation caveats

- Known API response/behavior gaps are tracked in `docs/api-gaps.md`.
- If runtime behavior differs from README examples, follow observed API behavior and update `docs/api-gaps.md`.

## Required planning policy

- `docs/roadmap.md` is the canonical living feature tracker.
- Whenever development changes a feature's status, scope, or canonical source of
  truth, update `docs/roadmap.md` in the same change set as the code/doc change.
- Significant architectural or system-boundary decisions require an ADR in
  `docs/adr/` in the same change set as the code/doc change that establishes the
  decision.
- Use `docs/architecture.md` for the current system narrative and `docs/adr/`
  for durable decisions with long-term maintenance impact.
