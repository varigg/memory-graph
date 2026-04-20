# Phase 2D — Performance and Embedding Deduplication

## Goal

Reduce query amplification in hybrid retrieval and make embedding reindexing
correct, resilient, and deduplicated.

## Implemented

### 1) Hybrid Search Query Batching

- Replaced per-row metadata lookups with batched `IN (...)` queries for:
  - FTS-side conversation importance
  - Semantic-side embedding-to-conversation mapping
  - Final conversation payload materialization
- Removed major N+1 query patterns from `/search/hybrid`.

### 2) Semantic Search Robustness

- `semantic_search` now keeps only top-k candidates with a min-heap.
- Handles `top_k <= 0` by returning empty list.
- Skips malformed embedding vectors during scoring.
- Returns `0.0` for vector-dimension mismatch in cosine similarity.

### 3) Reindex Transaction Hardening

- Reindex writes are grouped and committed once.
- Added rollback + `500` JSON error response on SQLite errors.

### 4) Identical Content Dedup in Reindex

- Within one reindex run, repeated conversation content reuses one embedding row.
- Multiple conversations with the same content are mapped to one `embedding_id`.

### 5) DB-Level Uniqueness Safety Net

- `db_schema.init()` now:
  - dedupes legacy duplicate `embeddings.text` rows,
  - rewires conversation references to the retained row,
  - creates unique index `idx_embeddings_text_unique` on `embeddings(text)`.

## Why this matters

- Lower query overhead on hybrid retrieval.
- Safer, deterministic embedding backfill.
- Prevents storage bloat and duplicate-vector drift for identical content.

## Validation

- Added regression tests for duplicate-content reindex behavior.
- Added schema tests for unique index creation and legacy dedupe repair.
- Final test status after Phase 2D docs-aligned implementation:
  - `329 passed, 4 skipped`

## Handoff to Phase 3A

Phase 2D completed deduplication and retrieval performance primitives that
Phase 3A will build on for multi-agent memory scopes:

- Shared-memory hygiene baseline: duplicate embedding suppression and stable
  text-to-embedding reuse.
- Search-path scalability baseline: batched hybrid query flow suitable for
  additional visibility filters.
- Data-repair baseline: schema init already performs safe dedupe/repair, a
  pattern reused by future scope/lifecycle migrations.

Phase 3A adds agent-facing scoping semantics (`shared` vs `private`) without
introducing authentication, matching local trusted multi-agent operation.
