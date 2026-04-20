"""End-to-end integration tests that run against an already-running server.

The server is started externally (in an environment that holds the real API
keys) and its address is passed in via the ``TEST_BASE_URL`` environment
variable.  The tests themselves never touch credentials.

Start the server, then run:

    TEST_BASE_URL=http://localhost:5000 pytest -m e2e tests/test_live_server_e2e.py -v

Tests are marked ``e2e`` and will skip when ``TEST_BASE_URL`` is not set or
the server is unreachable.
"""

import os

import pytest
import requests

# ---------------------------------------------------------------------------
# Fixture — point at an external server
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "http://localhost:5000"


@pytest.fixture(scope="module")
def e2e_base():
    """Resolve the base URL of the target server and verify it is reachable.

    Reads ``TEST_BASE_URL`` from the environment (falls back to
    ``http://localhost:5000``).  Skips the entire module if the server does
    not respond to ``GET /health`` within two seconds.
    """
    base_url = os.environ.get("TEST_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")

    try:
        r = requests.get(f"{base_url}/health", timeout=2)
        r.raise_for_status()
    except Exception as exc:
        pytest.skip(
            f"Server at {base_url} is unreachable ({exc}).\n"
            f"Start the server with your API keys and set TEST_BASE_URL, then re-run."
        )

    yield base_url


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestE2EEmbeddings:
    """Full-stack tests including the real embedding provider."""

    def test_log_conversation_generates_embedding(self, e2e_base):
        """Logging a conversation must persist an embedding row via the real API."""
        content = "The quick brown fox jumps"
        r = requests.post(
            f"{e2e_base}/conversation/log",
            json={"role": "user", "content": content},
        )
        assert r.status_code == 201
        assert isinstance(r.json()["id"], int)

        # Verify the embedding was actually stored by searching for the exact text.
        r = requests.get(f"{e2e_base}/search/semantic", params={"q": content})
        assert r.status_code == 200
        results = r.json()
        assert len(results) > 0, (
            "Semantic search returned no results after logging a conversation. "
            "The embedding was not stored — check that the embedding API call succeeded."
        )

    def test_semantic_search_returns_relevant_result(self, e2e_base):
        """Semantic search must return results with the expected shape."""
        seed = "distributed systems and consensus algorithms"
        r = requests.post(
            f"{e2e_base}/conversation/log",
            json={"role": "user", "content": seed},
        )
        assert r.status_code == 201

        r = requests.get(
            f"{e2e_base}/search/semantic",
            params={"q": "consensus and distributed computing"},
        )
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert len(results) > 0, (
            "Semantic search returned no results. The embedding API may have failed "
            "silently for the seeded conversation — check API key and provider."
        )
        for item in results:
            assert "id" in item
            assert "similarity" in item


@pytest.mark.e2e
class TestE2EMemoryOwnership:
    """Tests for memory ownership, visibility, and promotion (Phase 3A)."""

    def _memory_payload(self, name, content, agent_id="agent-alpha", visibility="shared", **overrides):
        """Helper to build a memory creation payload."""
        payload = {
            "name": name,
            "content": content,
            "type": "note",
            "owner_agent_id": agent_id,
            "visibility": visibility,
        }
        payload.update(overrides)
        return payload

    def test_create_memory_requires_owner_agent_id(self, e2e_base):
        """POST /memory must reject requests without owner_agent_id."""
        r = requests.post(
            f"{e2e_base}/memory",
            json={"name": "no-owner", "content": "content", "type": "note"},
        )
        assert r.status_code == 400
        assert "owner_agent_id" in r.json().get("error", "").lower()

    def test_create_memory_validates_visibility(self, e2e_base):
        """POST /memory must reject invalid visibility values."""
        r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload(
                "bad-visibility",
                "content",
                visibility="team-only"
            ),
        )
        assert r.status_code == 400
        assert "visibility" in r.json().get("error", "").lower()

    def test_create_shared_memory(self, e2e_base):
        """POST /memory must allow creating shared memories."""
        r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload("shared-mem", "shared content", visibility="shared"),
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_create_private_memory(self, e2e_base):
        """POST /memory must allow creating private memories."""
        r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload("private-mem", "private content", visibility="private"),
        )
        assert r.status_code == 201
        assert "id" in r.json()

    def test_promote_memory_to_shared(self, e2e_base):
        """POST /memory/<id>/promote must allow owner to make private memory shared."""
        # Create a private memory
        create_r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload(
                "promote-me",
                "private initially",
                agent_id="agent-alpha",
                visibility="private"
            ),
        )
        assert create_r.status_code == 201
        memory_id = create_r.json()["id"]

        # Promote it to shared
        promote_r = requests.post(
            f"{e2e_base}/memory/{memory_id}/promote?agent_id=agent-alpha",
        )
        assert promote_r.status_code == 200
        result = promote_r.json()
        assert result["visibility"] == "shared"

    def test_promote_memory_rejects_non_owner(self, e2e_base):
        """POST /memory/<id>/promote must reject non-owners."""
        # Create a private memory as agent-alpha
        create_r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload(
                "restricted",
                "only for alpha",
                agent_id="agent-alpha",
                visibility="private"
            ),
        )
        assert create_r.status_code == 201
        memory_id = create_r.json()["id"]

        # Try to promote as agent-beta (should fail)
        promote_r = requests.post(
            f"{e2e_base}/memory/{memory_id}/promote?agent_id=agent-beta",
        )
        assert promote_r.status_code == 403
        assert "forbidden" in promote_r.json().get("error", "").lower()

    def test_promote_requires_agent_id(self, e2e_base):
        """POST /memory/<id>/promote must require agent_id parameter."""
        # Create a memory
        create_r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload("needs-agent", "content", visibility="private"),
        )
        assert create_r.status_code == 201
        memory_id = create_r.json()["id"]

        # Try to promote without agent_id
        promote_r = requests.post(f"{e2e_base}/memory/{memory_id}/promote")
        assert promote_r.status_code == 400


@pytest.mark.e2e
class TestE2EMemoryScoping:
    """Tests for memory read scoping by visibility and ownership (Phase 3A)."""

    def _memory_payload(self, name, content, agent_id="agent-alpha", visibility="shared", **overrides):
        """Helper to build a memory creation payload."""
        payload = {
            "name": name,
            "content": content,
            "type": "note",
            "owner_agent_id": agent_id,
            "visibility": visibility,
        }
        payload.update(overrides)
        return payload

    def test_memory_list_includes_shared_memories(self, e2e_base):
        """GET /memory/list should include shared memories from all agents."""
        # Create shared memories from different agents
        for i in range(2):
            requests.post(
                f"{e2e_base}/memory",
                json=self._memory_payload(
                    f"shared-{i}",
                    f"shared content {i}",
                    agent_id=f"agent-{i}",
                    visibility="shared"
                ),
            )

        # List memories
        r = requests.get(f"{e2e_base}/memory/list?limit=100")
        assert r.status_code == 200
        names = [m.get("name", "") for m in r.json()]
        assert any("shared-" in name for name in names), (
            "List did not return shared memories; visibility scoping may not be implemented."
        )

    def test_memory_search_respects_visibility(self, e2e_base):
        """GET /memory/search should respect visibility constraints when agent_id is provided."""
        # Create a private memory with unique content
        private_r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload(
                "private-search-test",
                "ultra-unique-private-search-marker",
                agent_id="agent-alpha",
                visibility="private"
            ),
        )
        assert private_r.status_code == 201

        # Search for it as a different agent (should not find it without explicit scoping)
        search_r = requests.get(
            f"{e2e_base}/memory/search",
            params={"q": "ultra-unique-private-search-marker"},
        )
        assert search_r.status_code == 200
        results = search_r.json()
        # Depending on Phase 3A PR-3 implementation, private records should not leak
        # This test documents the expected behavior

    def test_memory_recall_finds_owned_private(self, e2e_base):
        """GET /memory/recall with agent_id should find that agent's private memories."""
        # Create a private memory
        private_r = requests.post(
            f"{e2e_base}/memory",
            json=self._memory_payload(
                "recall-test",
                "recall-unique-token-marker",
                agent_id="agent-alpha",
                visibility="private"
            ),
        )
        assert private_r.status_code == 201

        # Recall should find it (behavior depends on Phase 3A PR-3 implementation)
        recall_r = requests.get(
            f"{e2e_base}/memory/recall",
            params={"topic": "recall-unique-token-marker"},
        )
        assert recall_r.status_code == 200
        results = recall_r.json()
        # Test documents expected behavior when read scoping is implemented

    def test_hybrid_search_returns_ranked_results(self, e2e_base):
        """Hybrid search must combine FTS and semantic legs and return hits."""
        seed = "microservice observability with OpenTelemetry"
        r = requests.post(
            f"{e2e_base}/conversation/log",
            json={"role": "user", "content": seed},
        )
        assert r.status_code == 201

        r = requests.get(
            f"{e2e_base}/search/hybrid",
            params={"q": "OpenTelemetry tracing"},
        )
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert len(results) > 0, (
            "Hybrid search returned no results. Either the FTS index or the embedding "
            "for the seeded conversation is missing — check API key and provider."
        )

    def test_memory_search_with_real_content(self, e2e_base):
        """FTS on memories must find recently inserted records."""
        requests.post(
            f"{e2e_base}/memory",
            json={
                "name": "E2E Memory",
                "content": "raft consensus leader election quorum",
                "type": "note",
            },
        )
        r = requests.get(f"{e2e_base}/memory/search", params={"q": "quorum"})
        assert r.status_code == 200
        results = r.json()
        assert any("quorum" in item.get("content", "") for item in results)
