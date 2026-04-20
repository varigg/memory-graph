"""Tests for the memory blueprint (/memory/*, /entity/*)."""


# ---------------------------------------------------------------------------
# POST /memory
# ---------------------------------------------------------------------------

def test_create_memory_returns_201_on_valid_payload(client):
    resp = client.post(
        "/memory",
        json={"name": "foo", "type": "note", "content": "bar", "description": "baz"},
    )
    assert resp.status_code == 201


def test_create_memory_response_contains_id(client):
    resp = client.post(
        "/memory",
        json={"name": "foo", "type": "note", "content": "bar", "description": "baz"},
    )
    data = resp.get_json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_create_memory_returns_400_when_name_missing(client):
    resp = client.post(
        "/memory",
        json={"type": "note", "content": "bar", "description": "baz"},
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_when_content_missing(client):
    resp = client.post(
        "/memory",
        json={"name": "foo", "type": "note", "description": "baz"},
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_on_non_json_body(client):
    resp = client.post(
        "/memory",
        data="not json",
        content_type="text/plain",
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /memory/list
# ---------------------------------------------------------------------------

def test_list_memories_returns_200_with_list(client):
    resp = client.get("/memory/list")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_list_memories_returns_empty_list_when_none_exist(client):
    assert client.get("/memory/list").get_json() == []


def test_list_memories_contains_inserted_memory(client):
    client.post(
        "/memory",
        json={"name": "my-memory", "type": "note", "content": "some content", "description": "desc"},
    )
    items = client.get("/memory/list").get_json()
    assert any(item["name"] == "my-memory" for item in items)


def test_list_memories_grows_with_each_insert(client):
    for i in range(3):
        client.post(
            "/memory",
            json={"name": f"mem-{i}", "type": "note", "content": f"content {i}", "description": ""},
        )
    assert len(client.get("/memory/list").get_json()) == 3


# ---------------------------------------------------------------------------
# GET /memory/recall
# ---------------------------------------------------------------------------

def test_recall_returns_200_with_list(client):
    resp = client.get("/memory/recall?topic=anything")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_recall_finds_matching_memory_by_name(client):
    client.post(
        "/memory",
        json={"name": "deployment-checklist", "type": "note", "content": "run migrations", "description": ""},
    )
    results = client.get("/memory/recall?topic=deployment").get_json()
    assert any("deployment" in r["name"] for r in results)


def test_recall_finds_matching_memory_by_content(client):
    client.post(
        "/memory",
        json={"name": "alpha", "type": "note", "content": "unique-recall-token", "description": ""},
    )
    results = client.get("/memory/recall?topic=unique-recall-token").get_json()
    assert len(results) >= 1


def test_recall_returns_400_when_topic_absent(client):
    resp = client.get("/memory/recall")
    assert resp.status_code == 400


def test_recall_supports_limit_param(client):
    for i in range(5):
        client.post(
            "/memory",
            json={"name": f"recall-limit-{i}", "type": "note", "content": "topic token", "description": ""},
        )
    resp = client.get("/memory/recall?topic=topic&limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_recall_rejects_blank_topic(client):
    resp = client.get("/memory/recall?topic=   ")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /memory/search
# ---------------------------------------------------------------------------

def test_memory_search_returns_200_with_list(client):
    resp = client.get("/memory/search?q=foo")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_memory_search_returns_matching_record(client):
    client.post(
        "/memory",
        json={"name": "fts-target", "type": "note", "content": "searchable phrase", "description": ""},
    )
    results = client.get("/memory/search?q=searchable").get_json()
    assert any("searchable" in r.get("content", "") for r in results)


def test_memory_search_returns_empty_list_when_no_match(client):
    results = client.get("/memory/search?q=zzznomatch999").get_json()
    assert results == []


def test_memory_search_returns_400_when_q_absent(client):
    resp = client.get("/memory/search")
    assert resp.status_code == 400


def test_memory_search_supports_limit_param(client):
    for i in range(5):
        client.post(
            "/memory",
            json={"name": f"mem-limit-{i}", "type": "note", "content": "search limit token", "description": ""},
        )
    resp = client.get("/memory/search?q=search&limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_memory_search_rejects_invalid_offset(client):
    resp = client.get("/memory/search?q=search&offset=-1")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /memory/<id>
# ---------------------------------------------------------------------------

def _create_memory(client, name="to-delete"):
    resp = client.post(
        "/memory",
        json={"name": name, "type": "note", "content": "delete me", "description": ""},
    )
    return resp.get_json()["id"]


def test_delete_memory_returns_success_status(client):
    mem_id = _create_memory(client)
    resp = client.delete(f"/memory/{mem_id}")
    assert resp.status_code in (200, 204)


def test_delete_memory_returns_404_for_nonexistent_id(client):
    resp = client.delete("/memory/99999")
    assert resp.status_code == 404


def test_delete_memory_removes_item_from_list(client):
    mem_id = _create_memory(client, name="gone-soon")
    client.delete(f"/memory/{mem_id}")
    items = client.get("/memory/list").get_json()
    assert all(item["id"] != mem_id for item in items)


def test_delete_is_idempotent_second_call_returns_404(client):
    mem_id = _create_memory(client)
    client.delete(f"/memory/{mem_id}")
    resp = client.delete(f"/memory/{mem_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /entity
# ---------------------------------------------------------------------------

def test_create_entity_returns_201_on_valid_payload(client):
    resp = client.post(
        "/entity",
        json={"name": "Alice", "type": "person", "details": "...", "tags": "team"},
    )
    assert resp.status_code == 201


def test_create_entity_response_contains_id(client):
    resp = client.post(
        "/entity",
        json={"name": "Bob", "type": "person", "details": "lead", "tags": ""},
    )
    data = resp.get_json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_create_entity_returns_400_when_name_missing(client):
    resp = client.post(
        "/entity",
        json={"type": "person", "details": "no name here"},
    )
    assert resp.status_code == 400


def test_create_entity_returns_400_on_non_json_body(client):
    resp = client.post(
        "/entity",
        data="bad",
        content_type="text/plain",
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /entity/search
# ---------------------------------------------------------------------------

def test_entity_search_returns_200_with_list(client):
    resp = client.get("/entity/search?q=Alice")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_entity_search_returns_400_when_q_absent(client):
    resp = client.get("/entity/search")
    assert resp.status_code == 400


def test_entity_search_returns_matching_entities(client):
    client.post(
        "/entity",
        json={"name": "Charlie", "type": "person", "details": "engineer", "tags": "backend"},
    )
    results = client.get("/entity/search?q=Charlie").get_json()
    assert any("Charlie" in r.get("name", "") for r in results)


def test_entity_search_supports_limit_and_offset(client):
    for i in range(5):
        client.post(
            "/entity",
            json={"name": f"EntityLimit{i}", "type": "person", "details": "eng", "tags": "team"},
        )
    page1 = client.get("/entity/search?q=EntityLimit&limit=2").get_json()
    page2 = client.get("/entity/search?q=EntityLimit&limit=2&offset=2").get_json()
    assert len(page1) <= 2
    assert len(page2) <= 2
    if page1 and page2:
        assert page1[0]["id"] != page2[0]["id"]


def test_entity_search_rejects_blank_q(client):
    resp = client.get("/entity/search?q=   ")
    assert resp.status_code == 400


def test_entity_search_rejects_invalid_offset(client):
    resp = client.get("/entity/search?q=Entity&offset=-1")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Phase 2D: Performance tests (RED baseline)
# ---------------------------------------------------------------------------

def test_memory_list_endpoint_bounded_by_default_limit(client):
    """Verify /memory/list doesn't return unbounded result set.

    Endpoint should apply default pagination (limit=20) when params are absent.
    """
    # Insert 50 memories
    for i in range(50):
        client.post(
            "/memory",
            json={"name": f"perf-mem-{i}", "type": "note", "content": f"content {i}", "description": ""},
        )
    
    # Should paginate, not return all 50
    results = client.get("/memory/list").get_json()
    assert len(results) <= 20


def test_memory_list_supports_limit_and_offset(client):
    """Verify /memory/list supports pagination parameters."""
    for i in range(30):
        client.post(
            "/memory",
            json={"name": f"list-mem-{i}", "type": "note", "content": f"content {i}", "description": ""},
        )
    
    # Should support limit and offset like other search endpoints
    resp = client.get("/memory/list?limit=5&offset=0")
    assert resp.status_code == 200
    results = resp.get_json()
    assert len(results) <= 5
    
    resp2 = client.get("/memory/list?limit=5&offset=5")
    results2 = resp2.get_json()
    if results and results2:
        assert results[0]["id"] != results2[0]["id"]
