"""Integration tests exercising the API against a real running HTTP server.

Each test makes genuine HTTP requests via ``requests`` so that routing,
serialisation, and error handling are covered end-to-end without Flask's
test-client abstraction.

The ``live_server`` fixture spins up a Werkzeug threaded server on a random
port, permanently replaces ``embeddings.embed`` with a deterministic stub for
the lifetime of the session, and tears the server down cleanly after each test.

End-to-end tests (marked ``e2e``) use a separate ``live_server_e2e`` fixture
that does NOT patch ``embeddings.embed``.  They require a real API key in the
environment (``GOOGLE_API_KEY`` or ``OPENAI_API_KEY``) and must be invoked
explicitly::

    pytest -m e2e tests/test_live_server.py -v
"""

import threading
import time

import pytest
import requests
import werkzeug.serving

import embeddings as _embeddings_mod

FIXED_VECTOR = [0.1, 0.2, 0.3]


def _memory_payload(name, content, **overrides):
    payload = {
        "name": name,
        "content": content,
        "type": "note",
        "owner_agent_id": "agent-alpha",
        "visibility": "shared",
    }
    payload.update(overrides)
    return payload

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """Start the Flask app in a real Werkzeug server thread.

    ``embeddings.embed`` is replaced with a synchronous stub before the server
    thread is created so the replacement is visible inside the thread.
    Yields a *base URL* string (no trailing slash).
    """
    db_path = tmp_path_factory.mktemp("live_db") / "live.db"

    # Replace embed globally so server threads pick up the stub.
    original_embed = _embeddings_mod.embed
    _embeddings_mod.embed = lambda text: FIXED_VECTOR

    from api_server import create_app

    app = create_app(db_path=str(db_path))
    app.config["TESTING"] = True

    server = werkzeug.serving.make_server("127.0.0.1", 0, app, threaded=True)
    port = server.socket.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Brief pause to guarantee the socket is accepting connections.
    time.sleep(0.05)

    yield base_url

    server.shutdown()
    thread.join(timeout=5)
    _embeddings_mod.embed = original_embed


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


@pytest.fixture()
def base(live_server):
    """Alias so tests can simply declare ``base`` as a parameter."""
    return live_server


# ---------------------------------------------------------------------------
# Health / utility endpoints
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, base):
        r = requests.get(f"{base}/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    def test_version_endpoint(self, base):
        r = requests.get(f"{base}/version")
        assert r.status_code == 200
        assert "version" in r.json()

    def test_graph_returns_html(self, base):
        r = requests.get(f"{base}/graph")
        assert r.status_code == 200
        assert "text/html" in r.headers["Content-Type"]

    def test_health_includes_request_id_header(self, base):
        r = requests.get(f"{base}/health")
        assert r.status_code == 200
        assert r.headers.get("X-Request-Id")

    def test_request_id_header_round_trips(self, base):
        custom = "live-req-id-001"
        r = requests.get(f"{base}/health", headers={"X-Request-Id": custom})
        assert r.status_code == 200
        assert r.headers.get("X-Request-Id") == custom

    def test_404_includes_request_id_in_body(self, base):
        r = requests.get(f"{base}/missing")
        assert r.status_code == 404
        body = r.json()
        assert body.get("error") == "Not found"
        assert body.get("request_id") == r.headers.get("X-Request-Id")


# ---------------------------------------------------------------------------
# Memory CRUD
# ---------------------------------------------------------------------------


class TestMemory:
    def test_create_memory_returns_id(self, base):
        r = requests.post(
            f"{base}/memory",
            json=_memory_payload("Test Memory", "Some content here"),
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_create_memory_missing_name(self, base):
        r = requests.post(f"{base}/memory", json={"content": "oops"})
        assert r.status_code == 400

    def test_create_memory_missing_content(self, base):
        r = requests.post(f"{base}/memory", json={"name": "oops"})
        assert r.status_code == 400

    def test_create_memory_no_body(self, base):
        r = requests.post(f"{base}/memory", data="not-json", headers={"Content-Type": "text/plain"})
        assert r.status_code == 400

    def test_list_memories_contains_created(self, base):
        requests.post(
            f"{base}/memory",
            json=_memory_payload("Listable", "Listed content"),
        )
        r = requests.get(f"{base}/memory/list")
        assert r.status_code == 200
        names = [m["name"] for m in r.json()]
        assert "Listable" in names

    def test_delete_memory(self, base):
        created = requests.post(
            f"{base}/memory",
            json=_memory_payload("ToDelete", "delete me"),
        ).json()
        memory_id = created["id"]

        r = requests.delete(f"{base}/memory/{memory_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] == memory_id

        # Confirm absence
        memories = requests.get(f"{base}/memory/list").json()
        assert all(m["id"] != memory_id for m in memories)

    def test_delete_nonexistent_memory(self, base):
        r = requests.delete(f"{base}/memory/999999")
        assert r.status_code == 404

    def test_recall_memory(self, base):
        requests.post(
            f"{base}/memory",
            json=_memory_payload("Recall Me", "recallable unique content"),
        )
        r = requests.get(f"{base}/memory/recall", params={"topic": "recallable"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_recall_requires_topic(self, base):
        r = requests.get(f"{base}/memory/recall")
        assert r.status_code == 400

    def test_memory_search(self, base):
        requests.post(
            f"{base}/memory",
            json=_memory_payload("Searchable", "searchable keyword xyzzy"),
        )
        r = requests.get(f"{base}/memory/search", params={"q": "xyzzy"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_memory_search_requires_q(self, base):
        r = requests.get(f"{base}/memory/search")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------


class TestEntity:
    def test_create_entity_returns_id(self, base):
        r = requests.post(
            f"{base}/entity",
            json={"name": "Alice", "type": "person", "details": "engineer"},
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_create_entity_missing_name(self, base):
        r = requests.post(f"{base}/entity", json={"type": "person"})
        assert r.status_code == 400

    def test_create_entity_no_body(self, base):
        r = requests.post(f"{base}/entity", data="not-json", headers={"Content-Type": "text/plain"})
        assert r.status_code == 400

    def test_search_entity_finds_created(self, base):
        requests.post(
            f"{base}/entity",
            json={"name": "Bob", "type": "person", "details": "architect"},
        )
        r = requests.get(f"{base}/entity/search", params={"q": "Bob"})
        assert r.status_code == 200
        names = [e["name"] for e in r.json()]
        assert "Bob" in names

    def test_search_entity_requires_q(self, base):
        r = requests.get(f"{base}/entity/search")
        assert r.status_code == 400

    def test_search_entity_no_match(self, base):
        r = requests.get(f"{base}/entity/search", params={"q": "zzznomatch_xyz"})
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Conversation logging and retrieval
# ---------------------------------------------------------------------------


class TestConversations:
    def test_log_conversation_returns_id(self, base):
        r = requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "Hello server"},
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_log_conversation_missing_role(self, base):
        r = requests.post(f"{base}/conversation/log", json={"content": "oops"})
        assert r.status_code == 400

    def test_log_conversation_missing_content(self, base):
        r = requests.post(f"{base}/conversation/log", json={"role": "user"})
        assert r.status_code == 400

    def test_log_conversation_no_body(self, base):
        r = requests.post(
            f"{base}/conversation/log",
            data="not-json",
            headers={"Content-Type": "text/plain"},
        )
        assert r.status_code == 400

    def test_recent_conversations_returns_list(self, base):
        requests.post(
            f"{base}/conversation/log",
            json={"role": "assistant", "content": "Recent message"},
        )
        r = requests.get(f"{base}/conversation/recent")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_recent_conversations_limit(self, base):
        for i in range(5):
            requests.post(
                f"{base}/conversation/log",
                json={"role": "user", "content": f"Message {i}"},
            )
        r = requests.get(f"{base}/conversation/recent", params={"limit": 2})
        assert r.status_code == 200
        assert len(r.json()) <= 2

    def test_conversation_search(self, base):
        requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "unique_search_term_abc123"},
        )
        r = requests.get(
            f"{base}/conversation/search", params={"q": "unique_search_term_abc123"}
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_conversation_search_requires_q(self, base):
        r = requests.get(f"{base}/conversation/search")
        assert r.status_code == 400

    def test_conversation_stats(self, base):
        requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "stats seed"},
        )
        r = requests.get(f"{base}/conversation/stats")
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert body["total"] >= 1
        assert "by_role" in body
        assert isinstance(body["by_role"], dict)

    def test_conversation_channel_stored(self, base):
        requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "channel test", "channel": "ops"},
        )
        recent = requests.get(f"{base}/conversation/recent", params={"limit": 50}).json()
        channels = [c["channel"] for c in recent]
        assert "ops" in channels


# ---------------------------------------------------------------------------
# Key-value store
# ---------------------------------------------------------------------------


class TestKV:
    def test_set_and_get_key(self, base):
        requests.put(f"{base}/kv/mykey", json={"value": "myvalue"})
        r = requests.get(f"{base}/kv/mykey")
        assert r.status_code == 200
        body = r.json()
        assert body["key"] == "mykey"
        assert body["value"] == "myvalue"

    def test_overwrite_key(self, base):
        requests.put(f"{base}/kv/overwrite_key", json={"value": "first"})
        requests.put(f"{base}/kv/overwrite_key", json={"value": "second"})
        r = requests.get(f"{base}/kv/overwrite_key")
        assert r.status_code == 200
        assert r.json()["value"] == "second"

    def test_get_missing_key(self, base):
        r = requests.get(f"{base}/kv/does_not_exist_xyz")
        assert r.status_code == 404

    def test_put_missing_value_field(self, base):
        r = requests.put(f"{base}/kv/badkey", json={"not_value": "x"})
        assert r.status_code == 400

    def test_put_no_body(self, base):
        r = requests.put(
            f"{base}/kv/badkey2",
            data="not-json",
            headers={"Content-Type": "text/plain"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


class TestSemanticSearch:
    def test_semantic_search_returns_list(self, base):
        # Seed an embedding via conversation log
        requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "semantic seed content"},
        )
        r = requests.get(f"{base}/search/semantic", params={"q": "semantic seed"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_semantic_search_requires_q(self, base):
        r = requests.get(f"{base}/search/semantic")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Hybrid search
# ---------------------------------------------------------------------------


class TestHybridSearch:
    def test_hybrid_search_returns_list(self, base):
        requests.post(
            f"{base}/conversation/log",
            json={"role": "user", "content": "hybrid search seed text"},
        )
        r = requests.get(f"{base}/search/hybrid", params={"q": "hybrid"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_hybrid_search_requires_q(self, base):
        r = requests.get(f"{base}/search/hybrid")
        assert r.status_code == 400
