"""Tests for the memory blueprint (/memory/*, /entity/*)."""


def _memory_payload(name="foo", content="bar", **overrides):
    payload = {
        "name": name,
        "type": "note",
        "content": content,
        "description": "",
        "owner_agent_id": "agent-alpha",
        "visibility": "shared",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# POST /memory
# ---------------------------------------------------------------------------

def test_create_memory_returns_201_on_valid_payload(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(description="baz"),
    )
    assert resp.status_code == 201


def test_create_memory_response_contains_id(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(description="baz"),
    )
    data = resp.get_json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_create_memory_returns_400_when_name_missing(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name=None, description="baz"),
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_when_content_missing(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(content=None, description="baz"),
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_on_non_json_body(client):
    resp = client.post(
        "/memory",
        data="not json",
        content_type="text/plain",
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_when_owner_agent_id_missing(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(owner_agent_id=None),
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_when_owner_agent_id_blank(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(owner_agent_id="   "),
    )
    assert resp.status_code == 400


def test_create_memory_returns_400_when_visibility_invalid(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(visibility="team"),
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
        json=_memory_payload(name="my-memory", content="some content", description="desc"),
    )
    items = client.get("/memory/list").get_json()
    assert any(item["name"] == "my-memory" for item in items)


def test_list_memories_grows_with_each_insert(client):
    for i in range(3):
        client.post(
            "/memory",
            json=_memory_payload(name=f"mem-{i}", content=f"content {i}"),
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
        json=_memory_payload(name="deployment-checklist", content="run migrations"),
    )
    results = client.get("/memory/recall?topic=deployment").get_json()
    assert any("deployment" in r["name"] for r in results)


def test_recall_finds_matching_memory_by_content(client):
    client.post(
        "/memory",
        json=_memory_payload(name="alpha", content="unique-recall-token"),
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
            json=_memory_payload(name=f"recall-limit-{i}", content="topic token"),
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
        json=_memory_payload(name="fts-target", content="searchable phrase"),
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
            json=_memory_payload(name=f"mem-limit-{i}", content="search limit token"),
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
        json=_memory_payload(name=name, content="delete me"),
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
# POST /memory/<id>/promote
# ---------------------------------------------------------------------------

def test_promote_memory_returns_200_for_owner(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="promote-me", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    promote = client.post(f"/memory/{memory_id}/promote?agent_id=agent-alpha")
    assert promote.status_code == 200
    data = promote.get_json()
    assert data["id"] == memory_id
    assert data["visibility"] == "shared"


def test_promote_memory_returns_400_when_agent_id_missing(client):
    memory_id = _create_memory(client, name="promote-missing-agent")
    resp = client.post(f"/memory/{memory_id}/promote")
    assert resp.status_code == 400


def test_promote_memory_returns_404_for_unknown_memory(client):
    resp = client.post("/memory/999999/promote?agent_id=agent-alpha")
    assert resp.status_code == 404


def test_promote_memory_returns_403_for_non_owner(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="private-mem", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    promote = client.post(f"/memory/{memory_id}/promote?agent_id=agent-beta")
    assert promote.status_code == 403


# ---------------------------------------------------------------------------
# POST /memory/archive and /memory/invalidate
# ---------------------------------------------------------------------------

def test_archive_memory_returns_200_for_owner(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="archive-me", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    archive = client.post(
        "/memory/archive",
        json={"memory_id": memory_id, "agent_id": "agent-alpha"},
    )
    assert archive.status_code == 200
    assert archive.get_json()["status"] == "archived"


def test_invalidate_memory_returns_200_for_owner(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="invalidate-me", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    invalidate = client.post(
        "/memory/invalidate",
        json={"memory_id": memory_id, "agent_id": "agent-alpha"},
    )
    assert invalidate.status_code == 200
    assert invalidate.get_json()["status"] == "invalidated"


def test_archive_memory_requires_json_body(client):
    resp = client.post("/memory/archive")
    assert resp.status_code == 400


def test_archive_memory_requires_integer_memory_id(client):
    resp = client.post(
        "/memory/archive",
        json={"memory_id": "1", "agent_id": "agent-alpha"},
    )
    assert resp.status_code == 400


def test_archive_memory_returns_403_for_non_owner(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="archive-private", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    archive = client.post(
        "/memory/archive",
        json={"memory_id": memory_id, "agent_id": "agent-beta"},
    )
    assert archive.status_code == 403


def test_archive_memory_returns_404_for_unknown_memory(client):
    resp = client.post(
        "/memory/archive",
        json={"memory_id": 999999, "agent_id": "agent-alpha"},
    )
    assert resp.status_code == 404


def test_archive_rejected_after_invalidation(client):
    resp = client.post(
        "/memory",
        json=_memory_payload(name="invalidate-then-archive", visibility="private"),
    )
    memory_id = resp.get_json()["id"]

    invalidate = client.post(
        "/memory/invalidate",
        json={"memory_id": memory_id, "agent_id": "agent-alpha"},
    )
    assert invalidate.status_code == 200

    archive = client.post(
        "/memory/archive",
        json={"memory_id": memory_id, "agent_id": "agent-alpha"},
    )
    assert archive.status_code == 409


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
            json=_memory_payload(name=f"perf-mem-{i}", content=f"content {i}"),
        )

    # Should paginate, not return all 50
    results = client.get("/memory/list").get_json()
    assert len(results) <= 20


def test_memory_list_supports_limit_and_offset(client):
    """Verify /memory/list supports pagination parameters."""
    for i in range(30):
        client.post(
            "/memory",
            json=_memory_payload(name=f"list-mem-{i}", content=f"content {i}"),
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


# ---------------------------------------------------------------------------
# Phase 3A: Memory read scoping by visibility and ownership
# ---------------------------------------------------------------------------

class TestMemoryReadScoping:
    """Tests for read-path visibility and ownership scoping (Phase 3A PR-3)."""

    def test_list_with_agent_id_includes_shared_and_own_private(self, client):
        """GET /memory/list?agent_id=<id> should include shared + agent's private."""
        # Create shared memory
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-mem",
                content="shared content",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )

        # Create private memory for agent-alpha
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-alpha",
                content="alpha private",
                owner_agent_id="agent-alpha",
                visibility="private",
            ),
        )

        # Create private memory for agent-beta
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-beta",
                content="beta private",
                owner_agent_id="agent-beta",
                visibility="private",
            ),
        )

        # List as agent-alpha should see shared + their private, not beta's private
        resp = client.get("/memory/list?agent_id=agent-alpha")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert "shared-mem" in names, "Should see shared memories"
        assert "private-alpha" in names, "Should see own private memories"
        assert "private-beta" not in names, "Should not see other agent's private memories"

    def test_list_shared_only_flag(self, client):
        """GET /memory/list?agent_id=<id>&shared_only=true should return only shared."""
        # Create shared and private
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-1",
                visibility="shared",
                agent_id="agent-alpha",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-1",
                visibility="private",
                agent_id="agent-alpha",
            ),
        )

        # List with shared_only
        resp = client.get("/memory/list?agent_id=agent-alpha&shared_only=true")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert "shared-1" in names, "Should see shared"
        assert "private-1" not in names, "Should not see private with shared_only"

    def test_list_private_only_flag(self, client):
        """GET /memory/list?agent_id=<id>&private_only=true should return only own private."""
        # Create shared and private
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-2",
                visibility="shared",
                agent_id="agent-alpha",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-2",
                visibility="private",
                agent_id="agent-alpha",
            ),
        )

        # List with private_only
        resp = client.get("/memory/list?agent_id=agent-alpha&private_only=true")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert "private-2" in names, "Should see own private"
        assert "shared-2" not in names, "Should not see shared with private_only"

    def test_list_rejects_conflicting_scope_flags(self, client):
        """GET /memory/list should reject both shared_only and private_only."""
        resp = client.get("/memory/list?agent_id=agent-alpha&shared_only=true&private_only=true")
        assert resp.status_code == 400
        assert "cannot" in resp.get_json().get("error", "").lower()

    def test_search_with_scoping(self, client):
        """GET /memory/search?agent_id=<id> should scope FTS results."""
        # Create shared and private memories with unique content
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-search",
                content="unique-shared-marker",
                visibility="shared",
                owner_agent_id="agent-alpha",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-search",
                content="unique-private-marker",
                visibility="private",
                owner_agent_id="agent-alpha",
            ),
        )

        # Search as agent-alpha should find both
        resp = client.get("/memory/search?q=unique&agent_id=agent-alpha")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert "shared-search" in names or "private-search" in names, (
            "Should find scoped search results"
        )

    def test_recall_with_scoping(self, client):
        """GET /memory/recall?topic=<t>&agent_id=<id> should scope FTS results."""
        # Create shared and private memories
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-recall",
                content="deployment shared",
                visibility="shared",
                owner_agent_id="agent-alpha",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-recall",
                content="deployment private",
                visibility="private",
                owner_agent_id="agent-alpha",
            ),
        )

        # Recall as agent-alpha should find both
        resp = client.get("/memory/recall?topic=deployment&agent_id=agent-alpha")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert "shared-recall" in names or "private-recall" in names, (
            "Should find scoped recall results"
        )

    def test_list_without_agent_id_unscoped_legacy_behavior(self, client):
        """GET /memory/list without agent_id should return all memories (legacy)."""
        # Create memories as different agents
        for agent in ["alpha", "beta"]:
            client.post(
                "/memory",
                json=_memory_payload(
                    name=f"mem-{agent}",
                    visibility="private",
                    owner_agent_id=f"agent-{agent}",
                ),
            )

        # List without agent_id should see all (legacy compatibility)
        resp = client.get("/memory/list")
        assert resp.status_code == 200
        # With legacy behavior, both should be visible
        names = {m.get("name") for m in resp.get_json()}
        assert "mem-alpha" in names
        assert "mem-beta" in names
        # This documents current behavior; scoping requires agent_id

    def test_list_rejects_invalid_visibility_filter(self, client):
        resp = client.get("/memory/list?visibility=team")
        assert resp.status_code == 400
        assert "visibility" in resp.get_json().get("error", "").lower()

    def test_list_rejects_blank_owner_filter(self, client):
        resp = client.get("/memory/list?owner_agent_id=   ")
        assert resp.status_code == 400
        assert "owner_agent_id" in resp.get_json().get("error", "")

    def test_list_filters_compose_with_scoped_default(self, client):
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-alpha",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-beta",
                owner_agent_id="agent-beta",
                visibility="shared",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-alpha",
                owner_agent_id="agent-alpha",
                visibility="private",
            ),
        )

        resp = client.get(
            "/memory/list?agent_id=agent-alpha&visibility=shared&owner_agent_id=agent-beta"
        )
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert names == {"shared-beta"}

    def test_list_prefers_shared_memories_before_private(self, client):
        client.post(
            "/memory",
            json=_memory_payload(
                name="private-ranked",
                owner_agent_id="agent-alpha",
                visibility="private",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="shared-ranked",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )

        resp = client.get("/memory/list?agent_id=agent-alpha")
        assert resp.status_code == 200
        names = [m.get("name") for m in resp.get_json()[:2]]
        assert names == ["shared-ranked", "private-ranked"]

    def test_search_filters_by_owner_without_agent_id(self, client):
        client.post(
            "/memory",
            json=_memory_payload(
                name="alpha-hit",
                content="shared token",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )
        client.post(
            "/memory",
            json=_memory_payload(
                name="beta-hit",
                content="shared token",
                owner_agent_id="agent-beta",
                visibility="shared",
            ),
        )

        resp = client.get("/memory/search?q=token&owner_agent_id=agent-alpha")
        assert resp.status_code == 200
        names = {m.get("name") for m in resp.get_json()}
        assert names == {"alpha-hit"}

    def test_default_reads_exclude_archived(self, client):
        create = client.post(
            "/memory",
            json=_memory_payload(
                name="becomes-archived",
                content="status-token",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )
        memory_id = create.get_json()["id"]
        archive = client.post(
            "/memory/archive",
            json={"memory_id": memory_id, "agent_id": "agent-alpha"},
        )
        assert archive.status_code == 200

        list_resp = client.get("/memory/list?agent_id=agent-alpha")
        list_names = {m.get("name") for m in list_resp.get_json()}
        assert "becomes-archived" not in list_names

        search_resp = client.get("/memory/search?q=status-token&agent_id=agent-alpha")
        search_names = {m.get("name") for m in search_resp.get_json()}
        assert "becomes-archived" not in search_names

    def test_status_filter_allows_archived_reads(self, client):
        create = client.post(
            "/memory",
            json=_memory_payload(
                name="archived-visible",
                content="archived-token",
                owner_agent_id="agent-alpha",
                visibility="shared",
            ),
        )
        memory_id = create.get_json()["id"]
        archive = client.post(
            "/memory/archive",
            json={"memory_id": memory_id, "agent_id": "agent-alpha"},
        )
        assert archive.status_code == 200

        list_resp = client.get("/memory/list?agent_id=agent-alpha&status=archived")
        list_names = {m.get("name") for m in list_resp.get_json()}
        assert "archived-visible" in list_names

        search_resp = client.get(
            "/memory/search?q=archived-token&agent_id=agent-alpha&status=archived"
        )
        search_names = {m.get("name") for m in search_resp.get_json()}
        assert "archived-visible" in search_names
