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
