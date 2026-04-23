import json
import sqlite3

def _deserialize_json_object(raw_value: str):
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row_to_autonomy_checkpoint(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "goal_id": row["goal_id"],
        "action_id": row["action_id"],
        "requested_level": row["requested_level"],
        "approved_level": row["approved_level"],
        "verdict": row["verdict"],
        "rationale": row["rationale"],
        "stop_conditions_json": row["stop_conditions_json"],
        "stop_conditions": _deserialize_json_object(row["stop_conditions_json"]),
        "rollback_required": bool(row["rollback_required"]),
        "reviewer_type": row["reviewer_type"],
        "owner_agent_id": row["owner_agent_id"],
        "run_id": row["run_id"],
        "idempotency_key": row["idempotency_key"],
        "created_at": row["created_at"],
    }


def get_autonomy_checkpoint_by_idempotency_key(
    db: sqlite3.Connection,
    owner_agent_id: str,
    idempotency_key: str,
):
    return db.execute(
        "SELECT id FROM autonomy_checkpoints WHERE owner_agent_id = ? AND idempotency_key = ?",
        (owner_agent_id, idempotency_key),
    ).fetchone()


def insert_autonomy_checkpoint(
    db: sqlite3.Connection,
    requested_level: int,
    approved_level: int,
    verdict: str,
    owner_agent_id: str,
    goal_id: int = None,
    action_id: int = None,
    rationale: str = None,
    stop_conditions_json: str = "{}",
    rollback_required: bool = False,
    reviewer_type: str = "system",
    run_id: str = None,
    idempotency_key: str = None,
) -> int:
    cursor = db.execute(
        "INSERT INTO autonomy_checkpoints ("
        "goal_id, action_id, requested_level, approved_level, verdict, rationale, "
        "stop_conditions_json, rollback_required, reviewer_type, owner_agent_id, run_id, idempotency_key"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            goal_id,
            action_id,
            requested_level,
            approved_level,
            verdict,
            rationale,
            stop_conditions_json,
            1 if rollback_required else 0,
            reviewer_type,
            owner_agent_id,
            run_id,
            idempotency_key,
        ),
    )
    return int(cursor.lastrowid)


def list_autonomy_checkpoints(
    db: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    owner_agent_id: str = None,
    goal_id: int = None,
    action_id: int = None,
    verdict: str = None,
    reviewer_type: str = None,
    run_id: str = None,
) -> list:
    predicates = []
    params = []

    if owner_agent_id is not None:
        predicates.append("owner_agent_id = ?")
        params.append(owner_agent_id)
    if goal_id is not None:
        predicates.append("goal_id = ?")
        params.append(goal_id)
    if action_id is not None:
        predicates.append("action_id = ?")
        params.append(action_id)
    if verdict is not None:
        predicates.append("verdict = ?")
        params.append(verdict)
    if reviewer_type is not None:
        predicates.append("reviewer_type = ?")
        params.append(reviewer_type)
    if run_id is not None:
        predicates.append("run_id = ?")
        params.append(run_id)

    where_clause = ""
    if predicates:
        where_clause = " WHERE " + " AND ".join(predicates)

    params.extend([limit, offset])
    rows = db.execute(
        "SELECT id, goal_id, action_id, requested_level, approved_level, verdict, rationale, "
        "stop_conditions_json, rollback_required, reviewer_type, owner_agent_id, run_id, idempotency_key, created_at "
        f"FROM autonomy_checkpoints{where_clause} "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [_row_to_autonomy_checkpoint(row) for row in rows]
