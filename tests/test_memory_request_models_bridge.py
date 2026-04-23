from services.memory_request_models import (
    parse_autonomy_checkpoint_payload,
    parse_goal_create_payload,
)


def test_parse_goal_payload_rejects_non_serializable_constraints():
    payload = {
        "title": "ship",
        "owner_agent_id": "agent-a",
        "constraints": {"unsupported": {"nested": {1, 2}}},
    }

    try:
        parse_goal_create_payload(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "constraints must be JSON-serializable"



def test_parse_autonomy_payload_rejects_non_serializable_stop_conditions():
    payload = {
        "requested_level": 2,
        "approved_level": 1,
        "verdict": "sandbox_only",
        "owner_agent_id": "agent-a",
        "stop_conditions": {"unsupported": {"values": {1, 2}}},
    }

    try:
        parse_autonomy_checkpoint_payload(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "stop_conditions must be JSON-serializable"
