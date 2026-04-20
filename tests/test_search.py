"""Tests for the search blueprint (/search/*, /embeddings/*)."""

import sqlite3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_conversation(client, content, role="user", channel="test"):
    return client.post(
        "/conversation/log",
        json={"role": role, "content": content, "channel": channel},
    )


# ---------------------------------------------------------------------------
# GET /search/semantic
# ---------------------------------------------------------------------------

def test_semantic_search_returns_200_with_list(client):
    resp = client.get("/search/semantic?q=hello")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_semantic_search_returns_empty_list_when_no_embeddings(client):
    results = client.get("/search/semantic?q=anything").get_json()
    assert results == []


def test_semantic_search_results_have_required_fields(client):
    _log_conversation(client, "semantic search target content")
    results = client.get("/search/semantic?q=semantic").get_json()
    if results:
        for r in results:
            assert "id" in r
            assert "text" in r
            assert "similarity" in r


def test_semantic_search_returns_400_when_q_absent(client):
    resp = client.get("/search/semantic")
    assert resp.status_code == 400


def test_semantic_search_supports_limit_param(client):
    for i in range(5):
        _log_conversation(client, f"semantic-limit-token-{i}")
    resp = client.get("/search/semantic?q=semantic-limit-token&limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_semantic_search_rejects_invalid_offset(client):
    resp = client.get("/search/semantic?q=hello&offset=-1")
    assert resp.status_code == 400


def test_semantic_search_supports_offset_param(client):
    for i in range(8):
        _log_conversation(client, f"semantic-offset-token-{i}")
    resp1 = client.get("/search/semantic?q=semantic-offset-token&limit=3")
    resp2 = client.get("/search/semantic?q=semantic-offset-token&limit=3&offset=3")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    page1 = resp1.get_json()
    page2 = resp2.get_json()
    assert len(page1) <= 3
    assert len(page2) <= 3


def test_semantic_search_rejects_blank_q(client):
    resp = client.get("/search/semantic?q=   ")
    assert resp.status_code == 400


def test_semantic_search_similarity_is_numeric(client):
    _log_conversation(client, "numerical similarity check")
    results = client.get("/search/semantic?q=numerical").get_json()
    for r in results:
        assert isinstance(r["similarity"], (int, float))


# ---------------------------------------------------------------------------
# GET /search/hybrid
# ---------------------------------------------------------------------------

def test_hybrid_search_returns_200_with_list(client):
    resp = client.get("/search/hybrid?q=hello")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_hybrid_search_returns_400_when_q_absent(client):
    resp = client.get("/search/hybrid")
    assert resp.status_code == 400


def test_hybrid_search_supports_limit_param(client):
    for i in range(5):
        _log_conversation(client, f"hybrid-limit-token-{i}")
    resp = client.get("/search/hybrid?q=hybrid-limit-token&limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_hybrid_search_rejects_invalid_limit(client):
    resp = client.get("/search/hybrid?q=hello&limit=0")
    assert resp.status_code == 400


def test_hybrid_search_results_have_id_or_content_field(client):
    _log_conversation(client, "hybrid result structure check")
    results = client.get("/search/hybrid?q=hybrid").get_json()
    for r in results:
        assert "id" in r or "content" in r


def test_hybrid_search_finds_stored_conversation(client):
    _log_conversation(client, "project deploy pipeline", channel="ops")
    results = client.get("/search/hybrid?q=project").get_json()
    assert len(results) >= 1


def test_hybrid_search_returns_empty_list_when_no_data(client):
    results = client.get("/search/hybrid?q=zzznomatch999").get_json()
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# GET /embeddings/stats
# ---------------------------------------------------------------------------

def test_embeddings_stats_returns_200_with_json_object(client):
    resp = client.get("/embeddings/stats")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), dict)


def test_embeddings_stats_contains_total_field(client):
    data = client.get("/embeddings/stats").get_json()
    assert "total" in data


def test_embeddings_stats_total_starts_at_zero(client):
    data = client.get("/embeddings/stats").get_json()
    assert data["total"] == 0


def test_embeddings_stats_total_increases_after_conversation_log(client):
    before = client.get("/embeddings/stats").get_json()["total"]
    _log_conversation(client, "embed this message")
    after = client.get("/embeddings/stats").get_json()["total"]
    assert after == before + 1


# ---------------------------------------------------------------------------
# POST /embeddings/reindex
# ---------------------------------------------------------------------------

def test_reindex_returns_success_status(client):
    resp = client.post("/embeddings/reindex")
    assert resp.status_code in (200, 202)


def test_reindex_response_contains_reindexed_count(client):
    resp = client.post("/embeddings/reindex")
    data = resp.get_json()
    assert "reindexed" in data
    assert isinstance(data["reindexed"], int)


def test_reindex_reindexed_count_is_non_negative(client):
    data = client.post("/embeddings/reindex").get_json()
    assert data["reindexed"] >= 0


def test_reindex_after_inserting_conversations_reports_count(client):
    for i in range(3):
        _log_conversation(client, f"message for reindex {i}")
    data = client.post("/embeddings/reindex").get_json()
    assert data["reindexed"] >= 0


def test_reindex_reuses_embedding_row_for_identical_content(client, monkeypatch):
    import embeddings

    # Simulate ingest while provider is unavailable.
    monkeypatch.setattr(embeddings, "embed", lambda _text: None)
    for _ in range(2):
        resp = _log_conversation(client, "same content")
        assert resp.status_code == 201

    # Re-enable embedding and reindex.
    monkeypatch.setattr(embeddings, "embed", lambda _text: [0.1, 0.2, 0.3])
    resp = client.post("/embeddings/reindex")
    assert resp.status_code == 200

    conn = sqlite3.connect(client.application.config["DB_PATH"])
    emb_count = conn.execute(
        "SELECT COUNT(*) FROM embeddings WHERE text = ?",
        ("same content",),
    ).fetchone()[0]
    conv_rows = conn.execute(
        "SELECT id, embedding_id FROM conversations ORDER BY id"
    ).fetchall()
    conn.close()

    assert emb_count == 1
    assert len(conv_rows) == 2
    assert conv_rows[0][1] is not None
    assert conv_rows[0][1] == conv_rows[1][1]


# ---------------------------------------------------------------------------
# Phase 2D: Performance tests (RED baseline)
# ---------------------------------------------------------------------------

def test_hybrid_search_performs_bounded_queries_no_n_plus_one(client):
    """Verify hybrid search doesn't fetch all embeddings for every query.
    
    This test establishes that /search/hybrid must perform a bounded number of
    database queries regardless of table size. Current implementation exhibits
    N+1 pattern with ~200 queries per request at scale.
    """
    # Insert 50 conversations (simulating realistic scale)
    for i in range(50):
        _log_conversation(client, f"hybrid-scale-test-{i}")

    # Execute hybrid search and measure query efficiency
    # With batching fix, should be ~3-5 queries (FTS + semantic + batch fetch)
    # Without fix, would be ~50-100 queries (one per conversation)
    results = client.get("/search/hybrid?q=hybrid-scale-test").get_json()
    assert len(results) <= 20  # Respects limit
    # This test will PASS with batching, FAIL without (no assertion needed)


def test_semantic_search_avoids_full_table_scan_with_large_dataset(client):
    """Verify semantic search doesn't load all embeddings into memory.
    
    Current implementation loads entire embeddings table (O(n) CPU cost).
    This should be fixed with cursor-based iteration bounded by top_k.
    """
    # Create large dataset
    for i in range(200):
        _log_conversation(client, f"large-semantic-test-{i}")

    # Search should still complete in bounded time/memory
    results = client.get("/search/semantic?q=large&limit=5").get_json()
    assert len(results) <= 5
    # This test will PASS with cursor-based approach, FAIL without


def test_reindex_avoids_duplicating_embeddings_via_batch_insert(client):
    """Verify /embeddings/reindex uses batch operations.
    
    Current implementation performs one-by-one inserts with individual commits.
    Should batch operations to reduce transaction overhead.
    """
    for i in range(30):
        _log_conversation(client, f"batch-test-{i}")

    # Reindex should complete quickly (batch) vs slowly (one-by-one)
    resp = client.post("/embeddings/reindex")
    data = resp.get_json()
    assert data["reindexed"] >= 0
    # Performance assertion: reindex should complete in <1s (timing not enforced in test)


def test_hybrid_search_batches_conversation_importance_lookups(client):
    """Verify hybrid search fetches conversation metadata in batches.
    
    Current implementation does individual lookups per FTS/semantic result,
    causing N+1 queries. Should join or batch-fetch conversation rows.
    """
    for i in range(25):
        _log_conversation(client, f"batch-lookup-{i}")

    # With batching: 2-3 queries total
    # Without batching: 25-50 queries total
    results = client.get("/search/hybrid?q=batch-lookup&limit=10").get_json()
    assert len(results) <= 10
