# Plan: Memory Graph Flask API (Phase 1)

## TL;DR

Build a modularized Flask + SQLite server with blueprints for conversation logging, memory/entity storage, semantic RAG search, and utility endpoints. Phase 1 focuses on ~25 core endpoints (omitting v2 harness). Auto-initialize schema on startup. Embeddings via pluggable external API (OpenAI or Gemini). Web UI with 4 tabs (Graph, Logs, RAG, Crons) using D3.js and D3-based architecture visualization.

---

## Architecture Overview

**Directory Structure:**

```
~/projects/memory-graph/
├── api_server.py              # Flask app + initialization
├── config.py                  # Config (DB path, embedding API, CORS)
├── db_schema.py               # Auto-init tables + seed keywords
├── blueprints/
│   ├── __init__.py
│   ├── conversations.py       # /conversation/* routes
│   ├── memory.py              # /memory/*, /entity/* routes
│   ├── search.py              # /search/*, /embeddings/* routes
│   ├── kv.py                  # GET/PUT /kv/* (key-value store)
│   └── utility.py             # /health, /version, /graph
├── embeddings.py              # OpenAI/Gemini abstraction layer
├── db_operations.py           # SQLite helpers (FTS5, UPSERT, etc.)
├── importance_classifier.py   # Auto-compute importance scores
└── static/
    └── index.html             # SPA: Graph, Logs, RAG, Crons tabs + D3.js
└── requirements.txt           # Flask, sqlite-utils, requests, etc.

venv/
```

---

## Database Schema

**Core Tables:**

1. `conversations` — role, content, channel, timestamp, importance, embedding_id (FK)
2. `memories` — name, type, content, description, timestamp, confidence
3. `entities` — name, type, details, created_at, tags
4. `embeddings` — id, text, vector (JSON array), model_version, created_at
5. `importance_keywords` — keyword, score, hit_count, updated_at
6. `fts_conversations` — FTS5 virtual table (content, role, channel)
7. `fts_memories` — FTS5 virtual table (name, content, description)
8. `kv_store` — key (PK), value (JSON), updated_at

**No v2 harness tables in Phase 1.**

---

## Steps

### Phase 1A: Infrastructure & Schema

1. **Create project structure & requirements.txt** _(no dependencies on other steps)_
   - Dependencies: flask, sqlite-utils, requests, python-dotenv, flask-cors
   - Embedding library: None in Phase 1 (use external APIs via requests)

2. **Implement config.py & db_schema.py** _(depends on 1)_
   - Config: DB path (~/.claude/memory.db), API keys (OPENAI_API_KEY or GOOGLE_API_KEY), port (0.0.0.0:7777)
   - db_schema.py: Auto-create tables on startup, seed 10 importance keywords (notes=1.0, project=0.8, deploy=0.8, etc.)
   - Ensure idempotent (no errors if tables exist)

3. **Implement embeddings.py abstraction** _(depends on 1)_
   - Detect API choice from env (OPENAI_API_KEY → OpenAI; GOOGLE_API_KEY → Gemini)
   - embed(text) → 768-dim vector (or auto-detect model dims)
   - Handle API errors gracefully (log, return None)

4. **Implement db_operations.py** _(depends on 2, 3)_
   - SQLite helpers: upsert, fts_search, semantic_search (cosine via SQL)
   - Importance classification (keyword matching via importance_keywords table)

### Phase 1B: Core Blueprints

5. **Implement conversations blueprint** _(depends on 4)_
   - POST /conversation/log — insert message, auto-classify importance, embed, index FTS
   - GET /conversation/recent?limit=N — latest N messages
   - GET /conversation/search?q=QUERY — FTS search
   - GET /conversation/stats — counts by role/importance
   - POST /conversation/summarize — stub (deferred to Phase 2)
   - Error handling: 400 on missing fields, 500 on DB errors

6. **Implement memory blueprint** _(depends on 4)_
   - POST /memory — insert memory (name, type, content, description)
   - GET /memory/list — all memories
   - GET /memory/recall?topic=TOPIC — FTS search by topic
   - GET /memory/search?q=QUERY — FTS search
   - DELETE /memory/<id> — delete
   - POST /entity — insert entity
   - GET /entity/search?q=QUERY — FTS search entities
   - Error handling: 404 on missing ID, 400 on validation failure

7. **Implement search blueprint** _(depends on 4, 3)_
   - GET /search/semantic?q=QUERY — embed query, cosine-sim against conversation embeddings, return top-k
   - GET /search/hybrid?q=QUERY — combine FTS (full-text) + semantic via RRF (reciprocal rank fusion), weight by importance. Return matches enriched with stub summary (Phase 2 defers summaries)
   - GET /embeddings/stats — count embeddings by type (conversations, memories, etc.)
   - POST /embeddings/reindex — rebuild all embeddings (iterate conversations, re-embed, update DB)
   - Error handling: 400 if embedding API fails

8. **Implement kv blueprint** _(depends on 4)_
   - GET /kv/<key> — retrieve value (JSON)
   - PUT /kv/<key> — store value (JSON body)
   - Error handling: 404 if key missing

9. **Implement utility blueprint** _(depends on 2)_
   - GET /health — {"status": "ok", "version": "0.1.0"}
   - GET /version — {"version": "0.1.0"}
   - GET /graph — serve index.html (SPA root)

### Phase 1C: Web UI

10. **Create static/index.html** _(depends on 5, 6, 7, 9)_
    - SPA with 4 tabs: Graph, Logs, RAG, Crons
    - **Graph tab**: D3.js force-directed graph; nodes for conversations, memories, entities; color-coded by type; draggable, zoomable
    - **Logs tab**: Chronological view, collapsible by date, searchable
    - **RAG tab**: Semantic search interface, hybrid search toggle, result previews, embedding stats
    - **Crons tab**: Static view of cron list (placeholder for Phase 2); shows "no crons running"
    - CSS variable --topbar-h synced with actual topbar height
    - Responsive grid layout (mobile-friendly)

### Phase 1D: Flask App & Init

11. **Implement api_server.py** _(depends on 2, 5-9)_
    - Initialize Flask app
    - Register blueprints (conversations, memory, search, kv, utility)
    - Enable CORS (all origins)
    - Auto-call db_schema.init() on startup
    - Listen on 0.0.0.0:7777
    - Graceful error handlers (500 → JSON)

12. **Create requirements.txt** _(finalize from step 1)_

### Phase 1E: Testing & Validation

13. **Manual testing checklist** _(after 11)_
    - POST /conversation/log with various role/channel combos
    - GET /conversation/recent confirms ordering
    - POST /memory and GET /memory/list
    - GET /search/semantic?q=test (embedding API works)
    - GET /search/hybrid?q=test (RRF + importance weighting)
    - GET /kv/test_key → 404, then PUT, then GET → success
    - GET /health → 200 OK
    - GET /graph → index.html served
    - Web UI: Graph tab renders nodes, Logs tab shows entries, RAG tab searches

---

## Relevant Files to Create

- [api_server.py](api_server.py) — Flask app entry point
- [config.py](config.py) — Configuration (DB path, API keys, port)
- [db_schema.py](db_schema.py) — Auto-init schema + seed keywords
- [db_operations.py](db_operations.py) — SQLite & FTS helpers
- [embeddings.py](embeddings.py) — OpenAI/Gemini abstraction
- [blueprints/conversations.py](blueprints/conversations.py) — Conversation routes
- [blueprints/memory.py](blueprints/memory.py) — Memory & entity routes
- [blueprints/search.py](blueprints/search.py) — Semantic + hybrid search routes
- [blueprints/kv.py](blueprints/kv.py) — Key-value store routes
- [blueprints/utility.py](blueprints/utility.py) — Health, version, graph routes
- [blueprints/**init**.py](blueprints/__init__.py) — Empty (blueprint package marker)
- [static/index.html](static/index.html) — SPA with 4 tabs
- [requirements.txt](requirements.txt) — Python dependencies

---

## Verification

1. **Schema initialization**: Start server, check `~/.claude/memory.db` for 8 tables + 10 keywords
2. **CRUD endpoints**: POST /conversation/log, GET /conversation/recent, DELETE /memory/<id>, etc. return correct status codes
3. **Search**: POST /conversation/log with "project deploy" → GET /search/hybrid?q=project returns it with high importance
4. **Embeddings**: POST /conversation/log stores embedding, GET /embeddings/stats shows count > 0
5. **FTS**: POST /memory with name="Python Tips" + GET /memory/search?q=Python returns it
6. **Web UI**: GET /graph serves HTML, browser can load, Graph/Logs/RAG tabs render API data

---

## Decisions

- **Omit v2 harness**: Goals, plans, capabilities, world model, verifications, sandbox, experiments, metrics, crons endpoints deferred to Phase 2. Keeps Phase 1 focused and deliverable.
- **External embeddings**: Using OpenAI or Gemini API (configurable via env) rather than local model for simplicity and flexibility. No model training required.
- **Modular blueprints**: Easier to test, extend, and maintain than monolithic app.
- **Auto-init schema**: Server handles DB creation on first start (idempotent).
- **FTS5 + cosine similarity**: Hybrid search via RRF combines keyword matching + semantic ranking.
- **Importance keywords seeded**: Auto-loaded on startup; can be updated dynamically via API in Phase 2.

---

## Further Considerations

1. **Embedding latency**: POST /conversation/log will call embedding API synchronously. For high throughput, consider async/queue (Phase 2 improvement).
2. **Cosine similarity in SQL**: Using JSON vector storage + Python-side calculation. For production scale, consider pgvector or dedicated embedding index (Phase 2).
3. **Web UI capacity**: 4 tabs planned for Phase 1. Phase 2 will add Brain (v2 audit surface) and deepen Crons with live countdowns and sync validation.
