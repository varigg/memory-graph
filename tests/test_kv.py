"""Tests for the kv blueprint (/kv/*)."""


# ---------------------------------------------------------------------------
# GET /kv/<key>
# ---------------------------------------------------------------------------

def test_get_kv_returns_404_for_missing_key(client):
    resp = client.get("/kv/nonexistent-key-xyz")
    assert resp.status_code == 404


def test_get_kv_returns_200_after_put(client):
    client.put("/kv/mykey", json={"value": "hello"})
    resp = client.get("/kv/mykey")
    assert resp.status_code == 200


def test_get_kv_response_has_key_and_value_fields(client):
    client.put("/kv/structured-key", json={"value": 42})
    data = client.get("/kv/structured-key").get_json()
    assert "key" in data
    assert "value" in data


def test_get_kv_key_field_matches_requested_key(client):
    client.put("/kv/echo-key", json={"value": "anything"})
    data = client.get("/kv/echo-key").get_json()
    assert data["key"] == "echo-key"


# ---------------------------------------------------------------------------
# PUT /kv/<key>
# ---------------------------------------------------------------------------

def test_put_kv_returns_success_status_for_valid_json(client):
    resp = client.put("/kv/new-key", json={"value": "anything"})
    assert resp.status_code in (200, 201)


def test_put_kv_returns_400_for_non_json_body(client):
    resp = client.put(
        "/kv/bad-key",
        data="not json",
        content_type="text/plain",
    )
    assert resp.status_code == 400


def test_put_kv_returns_400_when_value_key_absent(client):
    resp = client.put("/kv/missing-value", json={"not_value": "oops"})
    assert resp.status_code == 400


def test_put_kv_subsequent_get_returns_same_value(client):
    client.put("/kv/round-trip", json={"value": "round-trip-value"})
    data = client.get("/kv/round-trip").get_json()
    assert data["value"] == "round-trip-value"


def test_put_kv_overwrites_existing_value(client):
    client.put("/kv/overwrite-key", json={"value": "original"})
    client.put("/kv/overwrite-key", json={"value": "updated"})
    data = client.get("/kv/overwrite-key").get_json()
    assert data["value"] == "updated"


def test_put_kv_stores_non_string_values(client):
    client.put("/kv/numeric-key", json={"value": 99})
    data = client.get("/kv/numeric-key").get_json()
    assert data["value"] == 99


def test_put_kv_stores_dict_values(client):
    client.put("/kv/dict-key", json={"value": {"nested": True}})
    data = client.get("/kv/dict-key").get_json()
    assert data["value"] == {"nested": True}
