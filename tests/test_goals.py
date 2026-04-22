"""Tests for the goals bridge endpoints (/goal/*)."""


def _goal_payload(title="Improve retrieval quality", **overrides):
    payload = {
        "title": title,
        "owner_agent_id": "agent-alpha",
        "status": "active",
        "utility": 1.0,
        "constraints": {"budget": "local-only"},
        "success_criteria": {"metric": "hallucination_rate", "target": "down"},
        "risk_tier": "medium",
        "autonomy_level_requested": 2,
        "run_id": "run-goal-tests",
    }
    payload.update(overrides)
    return payload


def test_create_goal_returns_201_on_valid_payload(client):
    resp = client.post("/goal", json=_goal_payload())
    assert resp.status_code == 201
    assert isinstance(resp.get_json()["id"], int)


def test_create_goal_requires_title(client):
    resp = client.post("/goal", json=_goal_payload(title="   "))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "title is required"


def test_create_goal_requires_owner_agent_id(client):
    resp = client.post("/goal", json=_goal_payload(owner_agent_id=""))
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "owner_agent_id is required"


def test_create_goal_idempotency_key_replays_existing_row(client):
    payload = _goal_payload(idempotency_key="goal-unique-1")
    first = client.post("/goal", json=payload)
    second = client.post("/goal", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert second.get_json()["idempotent_replay"] is True


def test_get_goal_returns_200_for_existing_goal(client):
    created = client.post("/goal", json=_goal_payload()).get_json()["id"]

    resp = client.get(f"/goal/{created}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created
    assert resp.get_json()["status"] == "active"


def test_get_goal_returns_parsed_constraints_and_success_criteria(client):
    created = client.post(
        "/goal",
        json=_goal_payload(
            constraints={"k": "v"},
            success_criteria={"target": "ship"},
        ),
    ).get_json()["id"]

    resp = client.get(f"/goal/{created}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["constraints"] == {"k": "v"}
    assert body["success_criteria"] == {"target": "ship"}


def test_get_goal_returns_404_when_missing(client):
    resp = client.get("/goal/999999")
    assert resp.status_code == 404


def test_goal_list_filters_by_owner_and_status(client):
    client.post("/goal", json=_goal_payload(title="agent-a-active", owner_agent_id="agent-a", status="active"))
    client.post(
        "/goal",
        json=_goal_payload(title="agent-a-blocked", owner_agent_id="agent-a", status="blocked"),
    )
    client.post("/goal", json=_goal_payload(title="agent-b-active", owner_agent_id="agent-b", status="active"))

    resp = client.get("/goal/list?owner_agent_id=agent-a&status=blocked")
    assert resp.status_code == 200
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["title"] == "agent-a-blocked"


def test_goal_status_update_returns_200(client):
    goal_id = client.post("/goal", json=_goal_payload(status="active")).get_json()["id"]

    resp = client.post(
        f"/goal/{goal_id}/status",
        json={"owner_agent_id": "agent-alpha", "status": "blocked", "reason": "waiting"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"id": goal_id, "status": "blocked"}

    fetched = client.get(f"/goal/{goal_id}")
    assert fetched.status_code == 200
    assert fetched.get_json()["status"] == "blocked"


def test_goal_status_update_forbidden_for_non_owner(client):
    goal_id = client.post("/goal", json=_goal_payload(owner_agent_id="agent-owner")).get_json()["id"]

    resp = client.post(
        f"/goal/{goal_id}/status",
        json={"owner_agent_id": "agent-other", "status": "blocked"},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "forbidden"


def test_goal_status_invalid_transition_returns_409(client):
    goal_id = client.post("/goal", json=_goal_payload(status="completed")).get_json()["id"]

    resp = client.post(
        f"/goal/{goal_id}/status",
        json={"owner_agent_id": "agent-alpha", "status": "active"},
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "invalid transition"


def test_goal_status_noop_does_not_write_history_row(client):
    goal_id = client.post("/goal", json=_goal_payload(status="active")).get_json()["id"]

    from db_utils import get_db  # noqa: PLC0415

    with client.application.app_context():
        db = get_db()
        before = db.execute(
            "SELECT COUNT(*) FROM goal_status_history WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()[0]

    resp = client.post(
        f"/goal/{goal_id}/status",
        json={"owner_agent_id": "agent-alpha", "status": "active"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"id": goal_id, "status": "active"}

    with client.application.app_context():
        db = get_db()
        after = db.execute(
            "SELECT COUNT(*) FROM goal_status_history WHERE goal_id = ?",
            (goal_id,),
        ).fetchone()[0]

    assert before == 1
    assert after == before
