import sqlite3

from db_utils import write_transaction
from storage.goal_repository import (
    ALLOWED_GOAL_STATUSES,
    append_goal_status_history,
    get_goal_by_id,
    get_goal_by_idempotency_key,
    insert_goal,
    list_goals,
    update_goal_status,
)

_ALLOWED_STATUS_TRANSITIONS = {
    "active": {"active", "blocked", "completed", "abandoned"},
    "blocked": {"blocked", "active", "completed", "abandoned"},
    "completed": {"completed"},
    "abandoned": {"abandoned"},
}


def create_or_get_goal(db: sqlite3.Connection, payload: dict) -> dict:
    owner_agent_id = payload["owner_agent_id"]
    idempotency_key = payload["idempotency_key"]

    if idempotency_key:
        existing = get_goal_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is not None:
            return {"id": int(existing["id"]), "created": False}

    with write_transaction(db):
        goal_id = insert_goal(
            db,
            title=payload["title"],
            owner_agent_id=owner_agent_id,
            status=payload["status"],
            utility=payload["utility"],
            deadline=payload["deadline"],
            constraints_json=payload["constraints_json"],
            success_criteria_json=payload["success_criteria_json"],
            risk_tier=payload["risk_tier"],
            autonomy_level_requested=payload["autonomy_level_requested"],
            autonomy_level_effective=payload["autonomy_level_effective"],
            run_id=payload["run_id"],
            idempotency_key=idempotency_key,
        )
        append_goal_status_history(
            db,
            goal_id=goal_id,
            old_status=None,
            new_status=payload["status"],
            changed_by_agent_id=owner_agent_id,
            reason="created",
        )
    return {"id": goal_id, "created": True}


def get_goal(db: sqlite3.Connection, goal_id: int):
    goal = get_goal_by_id(db, goal_id)
    if goal is None:
        return None, "not_found"
    return goal, None


def list_goals_for_query(
    db: sqlite3.Connection,
    limit: int,
    offset: int,
    owner_agent_id: str = None,
    status: str = None,
    run_id: str = None,
):
    return list_goals(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        status=status,
        run_id=run_id,
    )


def set_goal_status(
    db: sqlite3.Connection,
    goal_id: int,
    owner_agent_id: str,
    target_status: str,
    reason: str = None,
):
    if target_status not in ALLOWED_GOAL_STATUSES:
        return None, "invalid_status"

    goal = get_goal_by_id(db, goal_id)
    if goal is None:
        return None, "not_found"
    if goal["owner_agent_id"] != owner_agent_id:
        return None, "forbidden"

    current_status = goal["status"] or "active"
    if target_status == current_status:
        return {"id": goal_id, "status": current_status}, None

    allowed_targets = _ALLOWED_STATUS_TRANSITIONS.get(current_status, {current_status})
    if target_status not in allowed_targets:
        return None, "invalid_transition"

    with write_transaction(db):
        update_goal_status(db, goal_id=goal_id, new_status=target_status)
        append_goal_status_history(
            db,
            goal_id=goal_id,
            old_status=current_status,
            new_status=target_status,
            changed_by_agent_id=owner_agent_id,
            reason=reason,
        )

    return {"id": goal_id, "status": target_status}, None
