"""Tests for the conversations blueprint (/conversation/*)."""


FIXED_VECTOR = [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# POST /conversation/log
# ---------------------------------------------------------------------------

def test_log_returns_201_on_valid_payload(client):
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "content": "hello world", "channel": "test"},
    )
    assert resp.status_code == 201


def test_log_response_contains_integer_id(client):
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "content": "hello", "channel": "test"},
    )
    data = resp.get_json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_log_returns_400_when_role_missing(client):
    resp = client.post(
        "/conversation/log",
        json={"content": "hello", "channel": "test"},
    )
    assert resp.status_code == 400


def test_log_returns_400_when_content_missing(client):
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "channel": "test"},
    )
    assert resp.status_code == 400


def test_log_channel_defaults_to_default_when_omitted(client):
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "content": "hello"},
    )
    assert resp.status_code == 201
    # verify the record appears in recent with channel == "default"
    recent = client.get("/conversation/recent").get_json()
    assert any(item["channel"] == "default" for item in recent)


def test_log_message_appears_in_recent(client):
    client.post(
        "/conversation/log",
        json={"role": "user", "content": "unique-content-xyz", "channel": "test"},
    )
    recent = client.get("/conversation/recent").get_json()
    contents = [item["content"] for item in recent]
    assert "unique-content-xyz" in contents


def test_log_project_keyword_yields_positive_importance(client):
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "content": "working on project alpha", "channel": "test"},
    )
    assert resp.status_code == 201
    recent = client.get("/conversation/recent").get_json()
    matching = [item for item in recent if "project" in item["content"]]
    assert matching, "logged message not found in recent"
    assert matching[0]["importance"] > 0


def test_log_returns_400_on_non_json_body(client):
    resp = client.post(
        "/conversation/log",
        data="not json",
        content_type="text/plain",
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /conversation/recent
# ---------------------------------------------------------------------------

def test_recent_returns_200_with_list(client):
    resp = client.get("/conversation/recent")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_recent_returns_empty_list_when_no_conversations_exist(client):
    resp = client.get("/conversation/recent")
    assert resp.get_json() == []


def test_recent_limit_param_caps_result_count(client):
    for i in range(5):
        client.post(
            "/conversation/log",
            json={"role": "user", "content": f"message {i}", "channel": "test"},
        )
    resp = client.get("/conversation/recent?limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_recent_supports_offset_param(client):
    for i in range(4):
        client.post(
            "/conversation/log",
            json={"role": "user", "content": f"recent-offset-{i}", "channel": "test"},
        )
    first = client.get("/conversation/recent?limit=2").get_json()
    second = client.get("/conversation/recent?limit=2&offset=2").get_json()
    assert len(first) == 2
    assert len(second) <= 2
    if second:
        assert first[0]["id"] != second[0]["id"]


def test_recent_rejects_invalid_limit(client):
    resp = client.get("/conversation/recent?limit=0")
    assert resp.status_code == 400


def test_recent_rejects_non_integer_limit(client):
    resp = client.get("/conversation/recent?limit=abc")
    assert resp.status_code == 400


def test_recent_items_ordered_newest_first(client):
    client.post("/conversation/log", json={"role": "user", "content": "first msg", "channel": "test"})
    client.post("/conversation/log", json={"role": "user", "content": "second msg", "channel": "test"})
    items = client.get("/conversation/recent").get_json()
    assert items[0]["content"] == "second msg"


def test_recent_items_contain_required_fields(client):
    client.post(
        "/conversation/log",
        json={"role": "assistant", "content": "hello", "channel": "default"},
    )
    items = client.get("/conversation/recent").get_json()
    required = {"id", "role", "content", "channel", "timestamp", "importance"}
    for item in items:
        assert required.issubset(item.keys())


# ---------------------------------------------------------------------------
# GET /conversation/search
# ---------------------------------------------------------------------------

def test_search_returns_200_with_list(client):
    resp = client.get("/conversation/search?q=hello")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_search_returns_matching_conversations(client):
    client.post(
        "/conversation/log",
        json={"role": "user", "content": "deployment pipeline", "channel": "ops"},
    )
    results = client.get("/conversation/search?q=deployment").get_json()
    assert any("deployment" in r["content"] for r in results)


def test_search_returns_empty_list_when_no_match(client):
    results = client.get("/conversation/search?q=zzznomatch999").get_json()
    assert results == []


def test_search_returns_400_when_q_param_absent(client):
    resp = client.get("/conversation/search")
    assert resp.status_code == 400


def test_search_supports_limit_param(client):
    for i in range(5):
        client.post(
            "/conversation/log",
            json={"role": "user", "content": f"limit-token-{i}", "channel": "ops"},
        )
    resp = client.get("/conversation/search?q=limit-token&limit=2")
    assert resp.status_code == 200
    assert len(resp.get_json()) <= 2


def test_search_rejects_invalid_limit(client):
    resp = client.get("/conversation/search?q=hello&limit=0")
    assert resp.status_code == 400


def test_search_rejects_blank_q(client):
    resp = client.get("/conversation/search?q=   ")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /conversation/stats
# ---------------------------------------------------------------------------

def test_stats_returns_200_with_json_object(client):
    resp = client.get("/conversation/stats")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), dict)


def test_stats_contains_total_field(client):
    resp = client.get("/conversation/stats")
    assert "total" in resp.get_json()


def test_stats_total_reflects_inserted_count(client):
    for role in ("user", "user", "assistant"):
        client.post(
            "/conversation/log",
            json={"role": role, "content": "msg", "channel": "test"},
        )
    data = client.get("/conversation/stats").get_json()
    assert data["total"] == 3


def test_stats_by_role_counts_are_accurate(client):
    for role in ("user", "user", "assistant"):
        client.post(
            "/conversation/log",
            json={"role": role, "content": "msg", "channel": "test"},
        )
    data = client.get("/conversation/stats").get_json()
    assert "by_role" in data
    assert data["by_role"]["user"] == 2
    assert data["by_role"]["assistant"] == 1
