"""Tests for action log bridge endpoints (/action-log/*)."""


def _goal_payload(title="Goal for action logs", owner_agent_id="agent-alpha", **overrides):
    payload = {
        "title": title,
        "owner_agent_id": owner_agent_id,
        "status": "active",
        "utility": 1.0,
        "autonomy_level_requested": 1,
    }
    payload.update(overrides)
    return payload


def _action_payload(goal_id: int, owner_agent_id="agent-alpha", **overrides):
    payload = {
        "goal_id": goal_id,
        "action_type": "run-check",
        "mode": "dry_run",
        "status": "queued",
        "owner_agent_id": owner_agent_id,
    }
    payload.update(overrides)
    return payload


def test_create_action_log_returns_201(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]

    resp = client.post("/action-log", json=_action_payload(goal_id))
    assert resp.status_code == 201
    assert isinstance(resp.get_json()["id"], int)


def test_create_action_log_requires_existing_goal(client):
    resp = client.post("/action-log", json=_action_payload(goal_id=99999))
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "goal not found"


def test_create_action_log_requires_goal_owner_alignment(client):
    goal_id = client.post("/goal", json=_goal_payload(owner_agent_id="agent-owner")).get_json()["id"]

    resp = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_id, owner_agent_id="agent-other"),
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_create_action_log_idempotency_key_replays(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    payload = _action_payload(goal_id=goal_id, idempotency_key="action-unique-1")

    first = client.post("/action-log", json=payload)
    second = client.post("/action-log", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert second.get_json()["idempotent_replay"] is True


def test_create_action_log_rejects_parent_from_different_goal(client):
    goal_a = client.post("/goal", json=_goal_payload(title="A")).get_json()["id"]
    goal_b = client.post("/goal", json=_goal_payload(title="B")).get_json()["id"]

    parent_id = client.post("/action-log", json=_action_payload(goal_id=goal_a)).get_json()["id"]
    resp = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_b, parent_action_id=parent_id),
    )

    assert resp.status_code == 409
    assert resp.get_json()["error"] == "parent action must belong to the same goal"


def test_create_action_log_rejects_rollback_from_different_goal(client):
    goal_a = client.post("/goal", json=_goal_payload(title="A")).get_json()["id"]
    goal_b = client.post("/goal", json=_goal_payload(title="B")).get_json()["id"]

    rollback_id = client.post("/action-log", json=_action_payload(goal_id=goal_a)).get_json()["id"]
    resp = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_b, rollback_action_id=rollback_id),
    )

    assert resp.status_code == 409
    assert resp.get_json()["error"] == "rollback action must belong to the same goal and owner"


def test_list_action_logs_filters_by_goal_and_status(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    other_goal_id = client.post("/goal", json=_goal_payload(title="other")).get_json()["id"]

    first_id = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_id, status="running"),
    ).get_json()["id"]
    client.post(
        "/action-log",
        json=_action_payload(goal_id=other_goal_id, status="queued"),
    )

    resp = client.get(f"/action-log/list?goal_id={goal_id}&status=running")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["id"] == first_id
    assert rows[0]["status"] == "running"


def test_list_action_logs_rejects_non_positive_goal_id(client):
    resp = client.get("/action-log/list?goal_id=0")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "goal_id must be a positive integer"


def test_create_action_log_rejects_non_positive_goal_id(client):
    resp = client.post("/action-log", json=_action_payload(goal_id=0))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "goal_id must be a positive integer"


def test_complete_action_log_updates_status(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    action_id = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_id, status="running"),
    ).get_json()["id"]

    resp = client.post(
        f"/action-log/{action_id}/complete",
        json={
            "owner_agent_id": "agent-alpha",
            "status": "succeeded",
            "observed_result": "dry run passed",
        },
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"id": action_id, "status": "succeeded"}

    listed = client.get(f"/action-log/list?goal_id={goal_id}").get_json()
    assert listed[0]["status"] == "succeeded"
    assert listed[0]["observed_result"] == "dry run passed"


def test_complete_action_log_forbidden_for_non_owner(client):
    goal_id = client.post("/goal", json=_goal_payload(owner_agent_id="agent-owner")).get_json()["id"]
    action_id = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_id, owner_agent_id="agent-owner"),
    ).get_json()["id"]

    resp = client.post(
        f"/action-log/{action_id}/complete",
        json={"owner_agent_id": "agent-other", "status": "failed"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_complete_action_log_rejects_terminal_status_change(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    action_id = client.post("/action-log", json=_action_payload(goal_id=goal_id)).get_json()["id"]

    first = client.post(
        f"/action-log/{action_id}/complete",
        json={"owner_agent_id": "agent-alpha", "status": "succeeded"},
    )
    second = client.post(
        f"/action-log/{action_id}/complete",
        json={"owner_agent_id": "agent-alpha", "status": "failed"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["error"] == "invalid transition"


def test_complete_action_log_rejects_rollback_from_different_goal(client):
    goal_a = client.post("/goal", json=_goal_payload(title="A")).get_json()["id"]
    goal_b = client.post("/goal", json=_goal_payload(title="B")).get_json()["id"]

    action_id = client.post(
        "/action-log",
        json=_action_payload(goal_id=goal_a, status="running"),
    ).get_json()["id"]
    rollback_id = client.post("/action-log", json=_action_payload(goal_id=goal_b)).get_json()["id"]

    resp = client.post(
        f"/action-log/{action_id}/complete",
        json={
            "owner_agent_id": "agent-alpha",
            "status": "failed",
            "rollback_action_id": rollback_id,
        },
    )

    assert resp.status_code == 409
    assert resp.get_json()["error"] == "rollback action must belong to the same goal and owner"
