import sqlite3


def _row_to_action_log(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "goal_id": row["goal_id"],
        "parent_action_id": row["parent_action_id"],
        "action_type": row["action_type"],
        "tool_name": row["tool_name"],
        "mode": row["mode"],
        "status": row["status"],
        "input_summary": row["input_summary"],
        "expected_result": row["expected_result"],
        "observed_result": row["observed_result"],
        "rollback_action_id": row["rollback_action_id"],
        "owner_agent_id": row["owner_agent_id"],
        "run_id": row["run_id"],
        "idempotency_key": row["idempotency_key"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
    }


def get_action_log_by_id(db: sqlite3.Connection, action_id: int):
    row = db.execute(
        "SELECT id, goal_id, parent_action_id, action_type, tool_name, mode, status, "
        "input_summary, expected_result, observed_result, rollback_action_id, "
        "owner_agent_id, run_id, idempotency_key, created_at, completed_at "
        "FROM action_logs WHERE id = ?",
        (action_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_action_log(row)


def get_action_log_by_idempotency_key(
    db: sqlite3.Connection,
    owner_agent_id: str,
    idempotency_key: str,
):
    return db.execute(
        "SELECT id FROM action_logs WHERE owner_agent_id = ? AND idempotency_key = ?",
        (owner_agent_id, idempotency_key),
    ).fetchone()


def insert_action_log(
    db: sqlite3.Connection,
    goal_id: int,
    action_type: str,
    mode: str,
    status: str,
    owner_agent_id: str,
    parent_action_id: int = None,
    tool_name: str = None,
    input_summary: str = None,
    expected_result: str = None,
    observed_result: str = None,
    rollback_action_id: int = None,
    run_id: str = None,
    idempotency_key: str = None,
) -> int:
    cursor = db.execute(
        "INSERT INTO action_logs ("
        "goal_id, parent_action_id, action_type, tool_name, mode, status, "
        "input_summary, expected_result, observed_result, rollback_action_id, "
        "owner_agent_id, run_id, idempotency_key"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            goal_id,
            parent_action_id,
            action_type,
            tool_name,
            mode,
            status,
            input_summary,
            expected_result,
            observed_result,
            rollback_action_id,
            owner_agent_id,
            run_id,
            idempotency_key,
        ),
    )
    return int(cursor.lastrowid)


def list_action_logs(
    db: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    owner_agent_id: str = None,
    goal_id: int = None,
    status: str = None,
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
        "SELECT id, goal_id, parent_action_id, action_type, tool_name, mode, status, "
        "input_summary, expected_result, observed_result, rollback_action_id, "
        "owner_agent_id, run_id, idempotency_key, created_at, completed_at "
        f"FROM action_logs{where_clause} "
        "ORDER BY created_at DESC, id DESC "
        "LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [_row_to_action_log(row) for row in rows]


def complete_action_log(
    db: sqlite3.Connection,
    action_id: int,
    status: str,
    observed_result: str = None,
    rollback_action_id: int = None,
):
    cursor = db.execute(
        "UPDATE action_logs "
        "SET status = ?, observed_result = ?, rollback_action_id = ?, completed_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (status, observed_result, rollback_action_id, action_id),
    )
    return int(cursor.rowcount)
