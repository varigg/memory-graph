import json
import sqlite3


def _deserialize_metadata(metadata_json: str):
    if not metadata_json:
        return {}
    try:
        parsed = json.loads(metadata_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_scope_predicate(agent_id, shared_only=False, private_only=False):
    if shared_only and private_only:
        raise ValueError("Cannot combine shared_only and private_only")

    if shared_only:
        return "(visibility = 'shared')", []
    if private_only:
        return "(visibility = 'private' AND owner_agent_id = ?)", [agent_id]

    return (
        "(visibility = 'shared' OR (visibility = 'private' AND owner_agent_id = ?))",
        [agent_id],
    )


def _build_memory_filter_predicate(
    visibility=None,
    owner_agent_id=None,
    status="active",
    run_id=None,
    tag=None,
    min_confidence=None,
    updated_since=None,
    metadata_key=None,
    metadata_value=None,
    metadata_value_type=None,
):
    predicates = []
    bind_params = []

    if visibility is not None:
        predicates.append("visibility = ?")
        bind_params.append(visibility)

    if owner_agent_id is not None:
        predicates.append("owner_agent_id = ?")
        bind_params.append(owner_agent_id)

    if status is not None:
        predicates.append("status = ?")
        bind_params.append(status)

    if run_id is not None:
        predicates.append("run_id = ?")
        bind_params.append(run_id)

    if tag is not None:
        predicates.append("(',' || LOWER(COALESCE(tags, '')) || ',') LIKE ?")
        bind_params.append(f"%,{tag.lower()},%")

    if min_confidence is not None:
        predicates.append("confidence >= ?")
        bind_params.append(min_confidence)

    if updated_since is not None:
        predicates.append("COALESCE(updated_at, timestamp) >= ?")
        bind_params.append(updated_since)

    safe_metadata_expr = (
        "CASE WHEN json_valid(COALESCE(metadata_json, '')) = 1 "
        "THEN metadata_json ELSE '{}' END"
    )

    if metadata_key is not None:
        if metadata_value_type == "null":
            predicates.append(f"json_type({safe_metadata_expr}, '$.' || ?) = 'null'")
            bind_params.append(metadata_key)
        elif metadata_value is None:
            predicates.append(f"json_type({safe_metadata_expr}, '$.' || ?) IS NOT NULL")
            bind_params.append(metadata_key)
        elif metadata_value_type == "string":
            predicates.append(f"json_extract({safe_metadata_expr}, '$.' || ?) = ?")
            bind_params.extend([metadata_key, str(metadata_value)])
        elif metadata_value_type == "number":
            predicates.append(f"json_extract({safe_metadata_expr}, '$.' || ?) = ?")
            bind_params.extend([metadata_key, float(metadata_value)])
        elif metadata_value_type == "boolean":
            predicates.append(f"json_extract({safe_metadata_expr}, '$.' || ?) = ?")
            bind_params.extend([metadata_key, 1 if metadata_value else 0])

    if not predicates:
        return "", []

    return "(" + " AND ".join(predicates) + ")", bind_params


def _memory_order_by_clause(recency_half_life_hours: float = None):
    if recency_half_life_hours is not None and recency_half_life_hours > 0:
        return (
            " ORDER BY CASE visibility WHEN 'shared' THEN 0 ELSE 1 END,"
            " (confidence + MAX(0.0, 1.0 - ((julianday('now') - julianday(COALESCE(updated_at, timestamp))) * 24.0) / ?)) DESC,"
            " COALESCE(updated_at, timestamp) DESC, id DESC",
            [recency_half_life_hours],
        )

    return (
        " ORDER BY CASE visibility WHEN 'shared' THEN 0 ELSE 1 END,"
        " confidence DESC, COALESCE(updated_at, timestamp) DESC, id DESC",
        [],
    )


def list_memories(
    db: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    visibility: str = None,
    owner_agent_id: str = None,
    status: str = "active",
    run_id: str = None,
    tag: str = None,
    min_confidence: float = None,
    updated_since: str = None,
    metadata_key: str = None,
    metadata_value=None,
    metadata_value_type: str = None,
    recency_half_life_hours: float = None,
) -> list:
    filter_predicate, filter_params = _build_memory_filter_predicate(
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        metadata_key,
        metadata_value,
        metadata_value_type,
    )
    where_clause = ""
    query_params = list(filter_params)
    if filter_predicate:
        where_clause = f" WHERE {filter_predicate}"

    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    query_params.extend(order_params)
    query_params.extend([limit, offset])
    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, owner_agent_id, visibility, status, tags, run_id, idempotency_key, metadata_json, verification_status, verification_source, verified_at "
        f"FROM memories{where_clause} "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _deserialize_metadata(item.get("metadata_json"))
        result.append(item)
    return result


def list_memories_scoped(
    db: sqlite3.Connection,
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    shared_only: bool = False,
    private_only: bool = False,
    visibility: str = None,
    owner_agent_id: str = None,
    status: str = "active",
    run_id: str = None,
    tag: str = None,
    min_confidence: float = None,
    updated_since: str = None,
    metadata_key: str = None,
    metadata_value=None,
    metadata_value_type: str = None,
    recency_half_life_hours: float = None,
) -> list:
    predicate, bind_params = _build_scope_predicate(agent_id, shared_only, private_only)
    filter_predicate, filter_params = _build_memory_filter_predicate(
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        metadata_key,
        metadata_value,
        metadata_value_type,
    )
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)
    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    query_params = bind_params + order_params + [limit, offset]

    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, "
        f"owner_agent_id, visibility, status, tags, run_id, idempotency_key, metadata_json, verification_status, verification_source, verified_at FROM memories "
        f"WHERE {predicate} "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()
    return [
        {
            "id": r[0],
            "name": r[1],
            "type": r[2],
            "content": r[3],
            "description": r[4],
            "timestamp": r[5],
            "confidence": r[6],
            "owner_agent_id": r[7],
            "visibility": r[8],
            "status": r[9],
            "tags": r[10],
            "run_id": r[11],
            "idempotency_key": r[12],
            "metadata_json": r[13],
            "metadata": _deserialize_metadata(r[13]),
            "verification_status": r[14],
            "verification_source": r[15],
            "verified_at": r[16],
        }
        for r in rows
    ]


def fts_search_memories(
    db: sqlite3.Connection,
    query: str,
    limit: int = 20,
    offset: int = 0,
    visibility: str = None,
    owner_agent_id: str = None,
    status: str = "active",
    run_id: str = None,
    tag: str = None,
    min_confidence: float = None,
    updated_since: str = None,
    metadata_key: str = None,
    metadata_value=None,
    metadata_value_type: str = None,
    recency_half_life_hours: float = None,
) -> list:
    filter_predicate, filter_params = _build_memory_filter_predicate(
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        metadata_key,
        metadata_value,
        metadata_value_type,
    )
    where_clause = "f.fts_memories MATCH ?"
    query_params = [query]

    if filter_predicate:
        where_clause = f"{where_clause} AND {filter_predicate}"
        query_params.extend(filter_params)

    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    query_params.extend(order_params)
    query_params.extend([limit, offset])
    rows = db.execute(
        f"SELECT m.name, m.content, m.description, m.id, m.metadata_json "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {where_clause} "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()
    return [
        {
            "name": r[0],
            "content": r[1],
            "description": r[2],
            "memory_id": r[3],
            "metadata_json": r[4],
            "metadata": _deserialize_metadata(r[4]),
        }
        for r in rows
    ]


def fts_search_memories_scoped(
    db: sqlite3.Connection,
    query: str,
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    shared_only: bool = False,
    private_only: bool = False,
    visibility: str = None,
    owner_agent_id: str = None,
    status: str = "active",
    run_id: str = None,
    tag: str = None,
    min_confidence: float = None,
    updated_since: str = None,
    metadata_key: str = None,
    metadata_value=None,
    metadata_value_type: str = None,
    recency_half_life_hours: float = None,
) -> list:
    predicate, bind_params = _build_scope_predicate(agent_id, shared_only, private_only)
    filter_predicate, filter_params = _build_memory_filter_predicate(
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        metadata_key,
        metadata_value,
        metadata_value_type,
    )
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)

    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    full_query_params = bind_params + [query] + order_params + [limit, offset]
    rows = db.execute(
        f"SELECT m.name, m.content, m.description, m.id, m.metadata_json "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {predicate} "
        f"AND f.fts_memories MATCH ? "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        full_query_params,
    ).fetchall()
    return [
        {
            "name": r[0],
            "content": r[1],
            "description": r[2],
            "memory_id": r[3],
            "metadata_json": r[4],
            "metadata": _deserialize_metadata(r[4]),
        }
        for r in rows
    ]


def insert_memory(
    db: sqlite3.Connection,
    name: str,
    type_: str,
    content: str,
    description: str,
    confidence: float = 1.0,
    owner_agent_id: str = "unknown",
    visibility: str = "shared",
    tags: str = "",
    run_id: str = None,
    idempotency_key: str = None,
    metadata_json: str = "{}",
) -> int:
    cur = db.execute(
        "INSERT INTO memories ("
        "name, type, content, description, confidence, owner_agent_id, visibility, tags, run_id, idempotency_key, metadata_json"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            type_,
            content,
            description,
            confidence,
            owner_agent_id,
            visibility,
            tags,
            run_id,
            idempotency_key,
            metadata_json,
        ),
    )
    return cur.lastrowid


def get_memory_by_idempotency_key(
    db: sqlite3.Connection,
    owner_agent_id: str,
    idempotency_key: str,
):
    return db.execute(
        "SELECT id FROM memories WHERE owner_agent_id = ? AND idempotency_key = ?",
        (owner_agent_id, idempotency_key),
    ).fetchone()


def list_stale_private_memories(
    db: sqlite3.Connection,
    cutoff_timestamp: str,
    owner_agent_id: str = None,
    status: str = "active",
) -> list:
    predicates = [
        "visibility = 'private'",
        "COALESCE(updated_at, timestamp) < ?",
    ]
    params = [cutoff_timestamp]

    if owner_agent_id is not None:
        predicates.append("owner_agent_id = ?")
        params.append(owner_agent_id)

    if status != "all":
        predicates.append("status = ?")
        params.append(status)

    where_clause = " AND ".join(predicates)
    rows = db.execute(
        "SELECT id, owner_agent_id, status, visibility, updated_at, timestamp "
        "FROM memories "
        f"WHERE {where_clause} "
        "ORDER BY COALESCE(updated_at, timestamp) ASC, id ASC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def delete_memories_by_ids(db: sqlite3.Connection, memory_ids: list[int]) -> int:
    if not memory_ids:
        return 0

    placeholders = ",".join("?" * len(memory_ids))
    cur = db.execute(
        f"DELETE FROM memories WHERE id IN ({placeholders})",
        memory_ids,
    )
    return int(cur.rowcount or 0)
