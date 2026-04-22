import json
import sqlite3

ALLOWED_GOAL_STATUSES = {"active", "blocked", "completed", "abandoned"}


def _deserialize_json_object(raw_value: str):
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_goal(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "utility": row["utility"],
        "deadline": row["deadline"],
        "constraints_json": row["constraints_json"],
        "constraints": _deserialize_json_object(row["constraints_json"]),
        "success_criteria_json": row["success_criteria_json"],
        "success_criteria": _deserialize_json_object(row["success_criteria_json"]),
        "risk_tier": row["risk_tier"],
        "autonomy_level_requested": row["autonomy_level_requested"],
        "autonomy_level_effective": row["autonomy_level_effective"],
        "owner_agent_id": row["owner_agent_id"],
        "run_id": row["run_id"],
        "idempotency_key": row["idempotency_key"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_goal_by_idempotency_key(
    db: sqlite3.Connection,
    owner_agent_id: str,
    idempotency_key: str,
):
    return db.execute(
        "SELECT id, owner_agent_id FROM goals WHERE owner_agent_id = ? AND idempotency_key = ?",
        (owner_agent_id, idempotency_key),
    ).fetchone()


def insert_goal(
    db: sqlite3.Connection,
    title: str,
    owner_agent_id: str,
    status: str = "active",
    utility: float = 0.0,
    deadline: str = None,
    constraints_json: str = "{}",
    success_criteria_json: str = "{}",
    risk_tier: str = "low",
    autonomy_level_requested: int = 0,
    autonomy_level_effective: int = 0,
    run_id: str = None,
    idempotency_key: str = None,
) -> int:
    cursor = db.execute(
        "INSERT INTO goals ("
        "title, status, utility, deadline, constraints_json, success_criteria_json, "
        "risk_tier, autonomy_level_requested, autonomy_level_effective, "
        "owner_agent_id, run_id, idempotency_key"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            title,
            status,
            utility,
            deadline,
            constraints_json,
            success_criteria_json,
            risk_tier,
            autonomy_level_requested,
            autonomy_level_effective,
            owner_agent_id,
            run_id,
            idempotency_key,
        ),
    )
    return int(cursor.lastrowid)


def append_goal_status_history(
    db: sqlite3.Connection,
    goal_id: int,
    old_status: str,
    new_status: str,
    changed_by_agent_id: str,
    reason: str = None,
) -> int:
    cursor = db.execute(
        "INSERT INTO goal_status_history ("
        "goal_id, old_status, new_status, changed_by_agent_id, reason"
        ") VALUES (?, ?, ?, ?, ?)",
        (goal_id, old_status, new_status, changed_by_agent_id, reason),
    )
    return int(cursor.lastrowid)


def get_goal_by_id(db: sqlite3.Connection, goal_id: int):
    row = db.execute(
        "SELECT id, title, status, utility, deadline, constraints_json, success_criteria_json, "
        "risk_tier, autonomy_level_requested, autonomy_level_effective, "
        "owner_agent_id, run_id, idempotency_key, created_at, updated_at "
        "FROM goals WHERE id = ?",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_goal(row)


def list_goals(
    db: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    owner_agent_id: str = None,
    status: str = None,
    run_id: str = None,
) -> list:
    predicates = []
    params = []

    if owner_agent_id is not None:
        predicates.append("owner_agent_id = ?")
        params.append(owner_agent_id)
    if status is not None:
        predicates.append("status = ?")
        params.append(status)
    if run_id is not None:
        predicates.append("run_id = ?")
        params.append(run_id)

    where_clause = ""
    if predicates:
        where_clause = " WHERE " + " AND ".join(predicates)

    params.extend([limit, offset])
    rows = db.execute(
        "SELECT id, title, status, utility, deadline, constraints_json, success_criteria_json, "
        "risk_tier, autonomy_level_requested, autonomy_level_effective, "
        "owner_agent_id, run_id, idempotency_key, created_at, updated_at "
        f"FROM goals{where_clause} "
        "ORDER BY updated_at DESC, id DESC "
        "LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [_row_to_goal(row) for row in rows]


def update_goal_status(
    db: sqlite3.Connection,
    goal_id: int,
    new_status: str,
):
    cursor = db.execute(
        "UPDATE goals "
        "SET status = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (new_status, goal_id),
    )
    return int(cursor.rowcount)
