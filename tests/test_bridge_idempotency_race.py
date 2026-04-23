import sqlite3

from services import action_log_service, autonomy_checkpoint_service, goal_service


def test_goal_create_integrity_error_returns_idempotent_replay(monkeypatch):
    db = sqlite3.connect(":memory:")

    payload = {
        "title": "goal",
        "owner_agent_id": "agent-a",
        "status": "active",
        "utility": 1.0,
        "deadline": None,
        "constraints_json": "{}",
        "success_criteria_json": "{}",
        "risk_tier": "low",
        "autonomy_level_requested": 1,
        "autonomy_level_effective": 1,
        "run_id": "run-1",
        "idempotency_key": "goal-idem-1",
    }

    calls = {"count": 0}

    def fake_lookup(_db, owner_agent_id, idempotency_key):
        assert owner_agent_id == "agent-a"
        assert idempotency_key == "goal-idem-1"
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return {"id": 42}

    monkeypatch.setattr(goal_service, "get_goal_by_idempotency_key", fake_lookup)

    def fail_insert(*_args, **_kwargs):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")

    monkeypatch.setattr(goal_service, "insert_goal", fail_insert)

    result = goal_service.create_or_get_goal(db, payload)
    assert result == {"id": 42, "created": False}



def test_action_log_create_integrity_error_returns_idempotent_replay(monkeypatch):
    db = sqlite3.connect(":memory:")

    payload = {
        "goal_id": 11,
        "parent_action_id": None,
        "action_type": "run",
        "tool_name": None,
        "mode": "dry_run",
        "status": "queued",
        "input_summary": None,
        "expected_result": None,
        "observed_result": None,
        "rollback_action_id": None,
        "owner_agent_id": "agent-a",
        "run_id": "run-1",
        "idempotency_key": "action-idem-1",
    }

    monkeypatch.setattr(action_log_service, "get_goal_by_id", lambda *_: {"owner_agent_id": "agent-a"})
    calls = {"count": 0}

    def fake_lookup(_db, owner_agent_id, idempotency_key):
        assert owner_agent_id == "agent-a"
        assert idempotency_key == "action-idem-1"
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return {"id": 77}

    monkeypatch.setattr(action_log_service, "get_action_log_by_idempotency_key", fake_lookup)

    def fail_insert(*_args, **_kwargs):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")

    monkeypatch.setattr(action_log_service, "insert_action_log", fail_insert)

    result, err = action_log_service.create_or_get_action_log(db, payload)
    assert err is None
    assert result == {"id": 77, "created": False}



def test_autonomy_create_integrity_error_returns_idempotent_replay(monkeypatch):
    db = sqlite3.connect(":memory:")

    payload = {
        "goal_id": None,
        "action_id": None,
        "requested_level": 3,
        "approved_level": 2,
        "verdict": "sandbox_only",
        "rationale": None,
        "stop_conditions_json": "{}",
        "rollback_required": False,
        "reviewer_type": "system",
        "owner_agent_id": "agent-a",
        "run_id": "run-1",
        "idempotency_key": "autonomy-idem-1",
    }

    calls = {"count": 0}

    def fake_lookup(_db, owner_agent_id, idempotency_key):
        assert owner_agent_id == "agent-a"
        assert idempotency_key == "autonomy-idem-1"
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return {"id": 99}

    monkeypatch.setattr(
        autonomy_checkpoint_service,
        "get_autonomy_checkpoint_by_idempotency_key",
        fake_lookup,
    )

    def fail_insert(*_args, **_kwargs):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")

    monkeypatch.setattr(autonomy_checkpoint_service, "insert_autonomy_checkpoint", fail_insert)

    result, err = autonomy_checkpoint_service.create_or_get_autonomy_checkpoint(db, payload)
    assert err is None
    assert result == {"id": 99, "created": False}
