import sqlite3

from db_utils import write_transaction
from storage.action_log_repository import (
    ALLOWED_ACTION_MODES,
    ALLOWED_ACTION_STATUSES,
    complete_action_log,
    get_action_log_by_id,
    get_action_log_by_idempotency_key,
    insert_action_log,
    list_action_logs,
)
from storage.goal_repository import get_goal_by_id

_TERMINAL_STATUSES = {"succeeded", "failed", "rolled_back"}


def create_or_get_action_log(db: sqlite3.Connection, payload: dict) -> dict:
    owner_agent_id = payload["owner_agent_id"]
    idempotency_key = payload["idempotency_key"]

    if payload["mode"] not in ALLOWED_ACTION_MODES:
        return None, "invalid_mode"
    if payload["status"] not in ALLOWED_ACTION_STATUSES:
        return None, "invalid_status"

    goal = get_goal_by_id(db, payload["goal_id"])
    if goal is None:
        return None, "goal_not_found"
    if goal["owner_agent_id"] != owner_agent_id:
        return None, "forbidden_goal"

    if payload["parent_action_id"] is not None:
        parent = get_action_log_by_id(db, payload["parent_action_id"])
        if parent is None:
            return None, "parent_not_found"
        if parent["goal_id"] != payload["goal_id"]:
            return None, "invalid_parent"

    if payload["rollback_action_id"] is not None:
        rollback = get_action_log_by_id(db, payload["rollback_action_id"])
        if rollback is None:
            return None, "rollback_not_found"
        if (
            rollback["goal_id"] != payload["goal_id"]
            or rollback["owner_agent_id"] != owner_agent_id
        ):
            return None, "rollback_conflict"

    if idempotency_key:
        existing = get_action_log_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is not None:
            return {"id": int(existing["id"]), "created": False}, None

    try:
        with write_transaction(db):
            action_id = insert_action_log(
                db,
                goal_id=payload["goal_id"],
                parent_action_id=payload["parent_action_id"],
                action_type=payload["action_type"],
                tool_name=payload["tool_name"],
                mode=payload["mode"],
                status=payload["status"],
                input_summary=payload["input_summary"],
                expected_result=payload["expected_result"],
                observed_result=payload["observed_result"],
                rollback_action_id=payload["rollback_action_id"],
                owner_agent_id=owner_agent_id,
                run_id=payload["run_id"],
                idempotency_key=idempotency_key,
            )
    except sqlite3.IntegrityError:
        if not idempotency_key:
            raise
        existing = get_action_log_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is None:
            raise
        return {"id": int(existing["id"]), "created": False}, None
    return {"id": action_id, "created": True}, None


def list_action_logs_for_query(
    db: sqlite3.Connection,
    limit: int,
    offset: int,
    owner_agent_id: str = None,
    goal_id: int = None,
    status: str = None,
    run_id: str = None,
):
    return list_action_logs(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        goal_id=goal_id,
        status=status,
        run_id=run_id,
    )


def complete_action_log_entry(
    db: sqlite3.Connection,
    action_id: int,
    owner_agent_id: str,
    status: str,
    observed_result: str = None,
    rollback_action_id: int = None,
):
    if status not in _TERMINAL_STATUSES:
        return None, "invalid_status"

    existing = get_action_log_by_id(db, action_id)
    if existing is None:
        return None, "not_found"
    if existing["owner_agent_id"] != owner_agent_id:
        return None, "forbidden"

    current_status = existing["status"]
    if current_status in _TERMINAL_STATUSES and current_status != status:
        return None, "invalid_transition"

    if rollback_action_id is not None:
        rollback = get_action_log_by_id(db, rollback_action_id)
        if rollback is None:
            return None, "rollback_not_found"
        if (
            rollback["goal_id"] != existing["goal_id"]
            or rollback["owner_agent_id"] != existing["owner_agent_id"]
        ):
            return None, "rollback_conflict"

    with write_transaction(db):
        complete_action_log(
            db,
            action_id=action_id,
            status=status,
            observed_result=observed_result,
            rollback_action_id=rollback_action_id,
        )

    return {"id": action_id, "status": status}, None
