"""Tests for the utility blueprint (/health, /version, /graph)."""


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_response_contains_status_ok(client):
    data = client.get("/health").get_json()
    assert data.get("status") == "ok"


def test_health_response_contains_version_field(client):
    data = client.get("/health").get_json()
    assert "version" in data


def test_health_returns_json_content_type(client):
    resp = client.get("/health")
    assert "application/json" in resp.content_type


# ---------------------------------------------------------------------------
# GET /version
# ---------------------------------------------------------------------------

def test_version_returns_200(client):
    resp = client.get("/version")
    assert resp.status_code == 200


def test_version_response_contains_version_field(client):
    data = client.get("/version").get_json()
    assert "version" in data


def test_version_is_non_empty_string(client):
    data = client.get("/version").get_json()
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


def test_version_matches_health_version(client):
    health_version = client.get("/health").get_json()["version"]
    version_version = client.get("/version").get_json()["version"]
    assert health_version == version_version


# ---------------------------------------------------------------------------
# GET /graph
# ---------------------------------------------------------------------------

def test_graph_returns_200(client):
    resp = client.get("/graph")
    assert resp.status_code == 200


def test_graph_content_type_is_html(client):
    resp = client.get("/graph")
    assert "text/html" in resp.content_type


def test_graph_response_body_is_non_empty(client):
    resp = client.get("/graph")
    assert len(resp.data) > 0


# ---------------------------------------------------------------------------
# GET /metrics/memory-usefulness
# ---------------------------------------------------------------------------

def test_memory_usefulness_metrics_returns_200(client):
    resp = client.get("/metrics/memory-usefulness")
    assert resp.status_code == 200


def test_memory_usefulness_metrics_returns_json_shape(client):
    data = client.get("/metrics/memory-usefulness").get_json()
    assert "memory_counts" in data
    assert "adoption_signals" in data
    assert "trust_signals" in data
    assert "coverage_pct" in data


def test_memory_usefulness_metrics_empty_db_is_zeroed(client):
    data = client.get("/metrics/memory-usefulness").get_json()
    assert data["memory_counts"]["total"] == 0
    assert data["coverage_pct"]["run_tracked"] == 0.0
    assert data["coverage_pct"]["verified"] == 0.0


def test_memory_usefulness_metrics_reflects_memory_state(client):
    first = client.post(
        "/memory",
        json={
            "name": "decision-1",
            "type": "decision",
            "content": "Use run-aware checkpointing",
            "owner_agent_id": "agent-alpha",
            "visibility": "shared",
            "tags": "decision,ops",
            "run_id": "run-1",
            "idempotency_key": "agent-alpha:run-1:decision-1",
        },
    )
    second = client.post(
        "/memory",
        json={
            "name": "draft-1",
            "type": "trace",
            "content": "Private draft note",
            "owner_agent_id": "agent-alpha",
            "visibility": "private",
        },
    )

    first_id = first.get_json()["id"]
    second_id = second.get_json()["id"]

    verify = client.post(
        "/memory/verify",
        json={
            "memory_id": first_id,
            "agent_id": "agent-alpha",
            "verification_status": "verified",
            "verification_source": "test-run",
        },
    )
    assert verify.status_code == 200

    archive = client.post(
        "/memory/archive",
        json={"memory_id": second_id, "agent_id": "agent-alpha"},
    )
    assert archive.status_code == 200

    data = client.get("/metrics/memory-usefulness").get_json()
    assert data["memory_counts"]["total"] == 2
    assert data["memory_counts"]["active"] == 1
    assert data["memory_counts"]["archived"] == 1
    assert data["memory_counts"]["shared_active"] == 1
    assert data["memory_counts"]["private_active"] == 0
    assert data["adoption_signals"]["run_tracked"] == 1
    assert data["adoption_signals"]["idempotent"] == 1
    assert data["adoption_signals"]["tagged"] == 1
    assert data["trust_signals"]["verified"] == 1
    assert data["trust_signals"]["reviewed"] == 1
    assert data["coverage_pct"]["run_tracked"] == 50.0
    assert data["coverage_pct"]["verified"] == 50.0
