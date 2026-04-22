"""Tests for autonomy checkpoint bridge endpoints (/autonomy/check*)."""


def _goal_payload(title="Goal for autonomy checks", owner_agent_id="agent-alpha", **overrides):
    payload = {
        "title": title,
        "owner_agent_id": owner_agent_id,
        "status": "active",
        "utility": 1.0,
    }
    payload.update(overrides)
    return payload


def _action_payload(goal_id: int, owner_agent_id="agent-alpha", **overrides):
    payload = {
        "goal_id": goal_id,
        "action_type": "execute-step",
        "mode": "live",
        "status": "running",
        "owner_agent_id": owner_agent_id,
    }
    payload.update(overrides)
    return payload


def _checkpoint_payload(owner_agent_id="agent-alpha", **overrides):
    payload = {
        "requested_level": 3,
        "approved_level": 2,
        "verdict": "sandbox_only",
        "owner_agent_id": owner_agent_id,
        "reviewer_type": "system",
        "stop_conditions": {"max_steps": 1},
        "rollback_required": True,
        "run_id": "run-autonomy-tests",
    }
    payload.update(overrides)
    return payload


def test_create_autonomy_checkpoint_returns_201(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    action_id = client.post("/action-log", json=_action_payload(goal_id)).get_json()["id"]

    resp = client.post(
        "/autonomy/check",
        json=_checkpoint_payload(goal_id=goal_id, action_id=action_id),
    )
    assert resp.status_code == 201
    assert isinstance(resp.get_json()["id"], int)


def test_create_autonomy_checkpoint_rejects_approved_greater_than_requested(client):
    resp = client.post(
        "/autonomy/check",
        json=_checkpoint_payload(requested_level=2, approved_level=3),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "approved_level must be <= requested_level"


def test_create_autonomy_checkpoint_requires_existing_goal(client):
    resp = client.post("/autonomy/check", json=_checkpoint_payload(goal_id=99999))
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "goal not found"


def test_create_autonomy_checkpoint_requires_existing_action(client):
    resp = client.post("/autonomy/check", json=_checkpoint_payload(action_id=99999))
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "action not found"


def test_create_autonomy_checkpoint_forbidden_when_goal_owner_mismatch(client):
    goal_id = client.post("/goal", json=_goal_payload(owner_agent_id="agent-owner")).get_json()["id"]

    resp = client.post(
        "/autonomy/check",
        json=_checkpoint_payload(owner_agent_id="agent-other", goal_id=goal_id),
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_create_autonomy_checkpoint_rejects_goal_action_mismatch(client):
    goal_a = client.post("/goal", json=_goal_payload(title="A")).get_json()["id"]
    goal_b = client.post("/goal", json=_goal_payload(title="B")).get_json()["id"]
    action_id = client.post("/action-log", json=_action_payload(goal_a)).get_json()["id"]

    resp = client.post(
        "/autonomy/check",
        json=_checkpoint_payload(goal_id=goal_b, action_id=action_id),
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "action must belong to the provided goal"


def test_create_autonomy_checkpoint_idempotency_replay(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]

    payload = _checkpoint_payload(goal_id=goal_id, idempotency_key="autonomy-1")
    first = client.post("/autonomy/check", json=payload)
    second = client.post("/autonomy/check", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert second.get_json()["idempotent_replay"] is True


def test_list_autonomy_checkpoints_returns_parsed_stop_conditions(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    client.post(
        "/autonomy/check",
        json=_checkpoint_payload(goal_id=goal_id, stop_conditions={"max_steps": 2}),
    )

    rows = client.get("/autonomy/check/list").get_json()
    assert len(rows) == 1
    assert rows[0]["stop_conditions"] == {"max_steps": 2}


def test_create_autonomy_checkpoint_rejects_non_positive_goal_id(client):
    resp = client.post("/autonomy/check", json=_checkpoint_payload(goal_id=0))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "goal_id must be a positive integer when provided"


def test_list_autonomy_checkpoints_rejects_non_positive_goal_id(client):
    resp = client.get("/autonomy/check/list?goal_id=0")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "goal_id must be a positive integer"


def test_list_autonomy_checkpoints_filters_by_verdict(client):
    goal_id = client.post("/goal", json=_goal_payload()).get_json()["id"]
    client.post("/autonomy/check", json=_checkpoint_payload(goal_id=goal_id, verdict="approved", approved_level=3))
    client.post("/autonomy/check", json=_checkpoint_payload(goal_id=goal_id, verdict="denied", approved_level=0))

    resp = client.get("/autonomy/check/list?verdict=denied")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["verdict"] == "denied"


def test_list_autonomy_checkpoints_filters_by_owner(client):
    goal_a = client.post("/goal", json=_goal_payload(owner_agent_id="agent-a")).get_json()["id"]
    goal_b = client.post("/goal", json=_goal_payload(owner_agent_id="agent-b")).get_json()["id"]

    client.post(
        "/autonomy/check",
        json=_checkpoint_payload(owner_agent_id="agent-a", goal_id=goal_a, idempotency_key="a-1"),
    )
    client.post(
        "/autonomy/check",
        json=_checkpoint_payload(owner_agent_id="agent-b", goal_id=goal_b, idempotency_key="b-1"),
    )

    resp = client.get("/autonomy/check/list?owner_agent_id=agent-a")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["owner_agent_id"] == "agent-a"
