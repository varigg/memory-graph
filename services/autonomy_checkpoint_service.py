import sqlite3

from db_utils import write_transaction
from storage.action_log_repository import complete_action_log, get_action_log_by_id
from storage.autonomy_checkpoint_repository import (
    get_autonomy_checkpoint_by_idempotency_key,
    insert_autonomy_checkpoint,
    list_autonomy_checkpoints,
)
from storage.goal_repository import get_goal_by_id

from services._constants import ACTION_TERMINAL_STATUSES


def create_or_get_autonomy_checkpoint(db: sqlite3.Connection, payload: dict):
    owner_agent_id = payload["owner_agent_id"]
    goal_id = payload["goal_id"]
    action_id = payload["action_id"]

    requested_level = payload["requested_level"]
    approved_level = payload["approved_level"]
    if approved_level < 0 or approved_level > 5:
        return None, "invalid_approved_level"
    if requested_level < 0 or requested_level > 5:
        return None, "invalid_requested_level"
    if approved_level > requested_level:
        return None, "approved_level_exceeds_requested"

    if goal_id is not None:
        goal = get_goal_by_id(db, goal_id)
        if goal is None:
            return None, "goal_not_found"
        if goal["owner_agent_id"] != owner_agent_id:
            return None, "forbidden_goal"

    linked_action = None
    if action_id is not None:
        linked_action = get_action_log_by_id(db, action_id)
        if linked_action is None:
            return None, "action_not_found"
        if linked_action["owner_agent_id"] != owner_agent_id:
            return None, "forbidden_action"
        if goal_id is not None and linked_action["goal_id"] != goal_id:
            return None, "goal_action_mismatch"

    idempotency_key = payload["idempotency_key"]
    if idempotency_key:
        existing = get_autonomy_checkpoint_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is not None:
            return {"id": int(existing["id"]), "created": False}, None

    try:
        with write_transaction(db):
            checkpoint_id = insert_autonomy_checkpoint(
                db,
                goal_id=goal_id,
                action_id=action_id,
                requested_level=requested_level,
                approved_level=approved_level,
                verdict=payload["verdict"],
                rationale=payload["rationale"],
                stop_conditions_json=payload["stop_conditions_json"],
                rollback_required=payload["rollback_required"],
                reviewer_type=payload["reviewer_type"],
                owner_agent_id=owner_agent_id,
                run_id=payload["run_id"],
                idempotency_key=idempotency_key,
            )
            if (
                payload["verdict"] == "denied"
                and linked_action is not None
                and linked_action["status"] not in ACTION_TERMINAL_STATUSES
            ):
                complete_action_log(db, action_id=action_id, status="failed")
    except sqlite3.IntegrityError:
        if not idempotency_key:
            raise
        existing = get_autonomy_checkpoint_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is None:
            raise
        return {"id": int(existing["id"]), "created": False}, None
    return {"id": checkpoint_id, "created": True}, None


def list_autonomy_checkpoints_for_query(
    db: sqlite3.Connection,
    limit: int,
    offset: int,
    owner_agent_id: str = None,
    goal_id: int = None,
    action_id: int = None,
    verdict: str = None,
    reviewer_type: str = None,
    run_id: str = None,
):
    return list_autonomy_checkpoints(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        goal_id=goal_id,
        action_id=action_id,
        verdict=verdict,
        reviewer_type=reviewer_type,
        run_id=run_id,
    )
