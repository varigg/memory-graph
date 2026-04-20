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
