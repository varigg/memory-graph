"""Integration checks for the harness bridge primitives (M1-M4) with M4 polish assertions."""


def test_harness_bridge_end_to_end_flow(client):
    goal_resp = client.post(
        "/goal",
        json={
            "title": "Ship bridge",
            "owner_agent_id": "agent-alpha",
            "status": "active",
            "constraints": {"budget": "local"},
            "success_criteria": {"result": "integration-green"},
            "run_id": "run-harness-bridge-int",
        },
    )
    assert goal_resp.status_code == 201
    goal_id = goal_resp.get_json()["id"]

    goal = client.get(f"/goal/{goal_id}")
    assert goal.status_code == 200
    goal_body = goal.get_json()
    assert goal_body["constraints"] == {"budget": "local"}
    assert goal_body["success_criteria"] == {"result": "integration-green"}

    action_resp = client.post(
        "/action-log",
        json={
            "goal_id": goal_id,
            "action_type": "dry-run-check",
            "mode": "dry_run",
            "status": "running",
            "owner_agent_id": "agent-alpha",
            "run_id": "run-harness-bridge-int",
        },
    )
    assert action_resp.status_code == 201
    action_id = action_resp.get_json()["id"]

    checkpoint_resp = client.post(
        "/autonomy/check",
        json={
            "goal_id": goal_id,
            "action_id": action_id,
            "requested_level": 3,
            "approved_level": 2,
            "verdict": "sandbox_only",
            "owner_agent_id": "agent-alpha",
            "stop_conditions": {"max_steps": 1},
            "reviewer_type": "system",
            "run_id": "run-harness-bridge-int",
        },
    )
    assert checkpoint_resp.status_code == 201

    checks = client.get("/autonomy/check/list?run_id=run-harness-bridge-int")
    assert checks.status_code == 200
    check_rows = checks.get_json()
    assert len(check_rows) == 1
    assert check_rows[0]["goal_id"] == goal_id
    assert check_rows[0]["action_id"] == action_id
    assert check_rows[0]["stop_conditions"] == {"max_steps": 1}

    complete_resp = client.post(
        f"/action-log/{action_id}/complete",
        json={
            "owner_agent_id": "agent-alpha",
            "status": "succeeded",
            "observed_result": "all checks passed",
        },
    )
    assert complete_resp.status_code == 200

    actions = client.get(f"/action-log/list?goal_id={goal_id}&run_id=run-harness-bridge-int")
    assert actions.status_code == 200
    action_rows = actions.get_json()
    assert len(action_rows) == 1
    assert action_rows[0]["status"] == "succeeded"
    assert action_rows[0]["observed_result"] == "all checks passed"
