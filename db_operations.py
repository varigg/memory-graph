import json
import math
import sqlite3


def _deserialize_metadata(metadata_json: str):
    if not metadata_json:
        return {}
    try:
        parsed = json.loads(metadata_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}

# ---------------------------------------------------------------------------
# kv_store helpers
# ---------------------------------------------------------------------------

def upsert_kv(db: sqlite3.Connection, key: str, value) -> None:
    db.execute(
        "INSERT OR REPLACE INTO kv_store (key, value, updated_at)"
        " VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, json.dumps(value)),
    )
    db.commit()


def get_kv(db: sqlite3.Connection, key: str):
    row = db.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def get_memory_usefulness_metrics(db: sqlite3.Connection) -> dict:
    counts = db.execute(
        "SELECT "
        "COUNT(*) AS total_memories, "
        "SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_memories, "
        "SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) AS archived_memories, "
        "SUM(CASE WHEN status = 'invalidated' THEN 1 ELSE 0 END) AS invalidated_memories, "
        "SUM(CASE WHEN status = 'active' AND visibility = 'shared' THEN 1 ELSE 0 END) AS shared_active_memories, "
        "SUM(CASE WHEN status = 'active' AND visibility = 'private' THEN 1 ELSE 0 END) AS private_active_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS run_tracked_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(idempotency_key, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS idempotent_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(tags, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS tagged_memories, "
        "SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS verified_memories, "
        "SUM(CASE WHEN verification_status = 'disputed' THEN 1 ELSE 0 END) AS disputed_memories, "
        "SUM(CASE WHEN verification_status IN ('verified', 'disputed') THEN 1 ELSE 0 END) AS reviewed_memories "
        "FROM memories"
    ).fetchone()

    def _value(key):
        value = counts[key]
        return int(value or 0)

    total_memories = _value("total_memories")

    def _pct(value):
        if total_memories == 0:
            return 0.0
        return round((value / total_memories) * 100.0, 2)

    run_tracked_memories = _value("run_tracked_memories")
    idempotent_memories = _value("idempotent_memories")
    tagged_memories = _value("tagged_memories")
    verified_memories = _value("verified_memories")
    disputed_memories = _value("disputed_memories")
    reviewed_memories = _value("reviewed_memories")

    run_stats = db.execute(
        "SELECT "
        "COUNT(DISTINCT run_id) AS distinct_runs, "
        "SUM(CASE WHEN status = 'active' AND NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS active_run_tracked_memories "
        "FROM memories "
        "WHERE NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL"
    ).fetchone()

    freshness = db.execute(
        "SELECT "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) <= 1 THEN 1 ELSE 0 END) AS updated_last_24h, "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) <= 7 THEN 1 ELSE 0 END) AS updated_last_7d, "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) > 7 THEN 1 ELSE 0 END) AS updated_older_than_7d "
        "FROM memories"
    ).fetchone()

    top_runs_rows = db.execute(
        "SELECT run_id, COUNT(*) AS memory_count "
        "FROM memories "
        "WHERE NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL "
        "GROUP BY run_id "
        "ORDER BY memory_count DESC, run_id ASC "
        "LIMIT 5"
    ).fetchall()

    run_tracked_active_memories = int((run_stats["active_run_tracked_memories"] or 0))

    return {
        "memory_counts": {
            "total": total_memories,
            "active": _value("active_memories"),
            "archived": _value("archived_memories"),
            "invalidated": _value("invalidated_memories"),
            "shared_active": _value("shared_active_memories"),
            "private_active": _value("private_active_memories"),
        },
        "adoption_signals": {
            "run_tracked": run_tracked_memories,
            "idempotent": idempotent_memories,
            "tagged": tagged_memories,
        },
        "trust_signals": {
            "verified": verified_memories,
            "disputed": disputed_memories,
            "reviewed": reviewed_memories,
        },
        "run_signals": {
            "distinct_runs": int((run_stats["distinct_runs"] or 0)),
            "active_run_tracked": run_tracked_active_memories,
            "top_runs": [
                {"run_id": r["run_id"], "memory_count": int(r["memory_count"])}
                for r in top_runs_rows
            ],
        },
        "freshness_signals": {
            "updated_last_24h": int((freshness["updated_last_24h"] or 0)),
            "updated_last_7d": int((freshness["updated_last_7d"] or 0)),
            "updated_older_than_7d": int((freshness["updated_older_than_7d"] or 0)),
        },
        "coverage_pct": {
            "run_tracked": _pct(run_tracked_memories),
            "run_tracked_active": _pct(run_tracked_active_memories),
            "idempotent": _pct(idempotent_memories),
            "tagged": _pct(tagged_memories),
            "reviewed": _pct(reviewed_memories),
            "verified": _pct(verified_memories),
        },
    }


# ---------------------------------------------------------------------------
# FTS search
# ---------------------------------------------------------------------------

def fts_search_conversations(
    db: sqlite3.Connection, query: str, limit: int = 20, offset: int = 0
) -> list:
    rows = db.execute(
        "SELECT content, role, channel, conversation_id"
        " FROM fts_conversations WHERE fts_conversations MATCH ?"
        " LIMIT ? OFFSET ?",
        (query, limit, offset),
    ).fetchall()
    return [{"content": r[0], "role": r[1], "channel": r[2], "conversation_id": r[3]} for r in rows]


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


# ---------------------------------------------------------------------------
# Visibility/ownership scoping
# ---------------------------------------------------------------------------

def _build_scope_predicate(agent_id, shared_only=False, private_only=False):
    """Build visibility scope SQL predicate.

    Returns tuple: (predicate_string, bind_params)
    where predicate_string is ready for use in WHERE clause.
    """
    if shared_only and private_only:
        raise ValueError("Cannot combine shared_only and private_only")

    if shared_only:
        return "(visibility = 'shared')", []
    if private_only:
        return "(visibility = 'private' AND owner_agent_id = ?)", [agent_id]

    # Default: shared + agent's private
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
        # Store tags as comma-separated values and match exact token boundaries.
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
    """List memories with visibility scoping applied."""
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
    """FTS search on memories with visibility scoping."""
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

    # Build parameter list in correct order: scope params, query, limit, offset
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


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

def insert_conversation(
    db: sqlite3.Connection,
    role: str,
    content: str,
    channel: str,
    importance: float = 0.0,
    embedding_id=None,
) -> int:
    cur = db.execute(
        "INSERT INTO conversations (role, content, channel, importance, embedding_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (role, content, channel, importance, embedding_id),
    )
    db.commit()
    return cur.lastrowid


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
    db.commit()
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


def set_memory_verification(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
    verification_status: str,
    verification_source: str = None,
):
    row = db.execute(
        "SELECT id, owner_agent_id FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    if verification_status not in {"unverified", "verified", "disputed"}:
        return None, "invalid_status"

    if verification_status == "verified":
        db.execute(
            "UPDATE memories "
            "SET verification_status = ?, verification_source = ?, verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (verification_status, verification_source, memory_id),
        )
    else:
        db.execute(
            "UPDATE memories "
            "SET verification_status = ?, verification_source = ?, verified_at = NULL, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (verification_status, verification_source, memory_id),
        )
    db.commit()
    return {
        "id": memory_id,
        "verification_status": verification_status,
        "verification_source": verification_source,
    }, None


def promote_memory_to_shared(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
):
    row = db.execute(
        "SELECT id, owner_agent_id FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    db.execute(
        "UPDATE memories "
        "SET visibility = 'shared', updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (memory_id,),
    )
    db.commit()
    return {"id": row[0], "visibility": "shared"}, None


def transition_memory_status(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
    target_status: str,
):
    row = db.execute(
        "SELECT id, owner_agent_id, status FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    current_status = row[2] or "active"
    if current_status == target_status:
        return {"id": row[0], "status": current_status}, None

    if target_status not in {"archived", "invalidated"}:
        return None, "invalid_status"

    if current_status == "invalidated":
        return None, "invalid_transition"
    if current_status == "archived" and target_status == "archived":
        return {"id": row[0], "status": current_status}, None

    db.execute(
        "UPDATE memories "
        "SET status = ?, updated_at = CURRENT_TIMESTAMP, status_updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (target_status, memory_id),
    )
    db.commit()
    return {"id": row[0], "status": target_status}, None


def relate_memory_lifecycle(
    db: sqlite3.Connection,
    memory_id: int,
    target_memory_id: int,
    requester_agent_id: str,
    relation_type: str,
):
    """Create lifecycle relation and transition source memory status.

    Supported relation types:
    - merged_into: source transitions to archived
    - superseded_by: source transitions to invalidated
    """
    if memory_id == target_memory_id:
        return None, "same_memory"

    if relation_type not in {"merged_into", "superseded_by"}:
        return None, "invalid_relation"

    source_row = db.execute(
        "SELECT id, owner_agent_id, visibility, status FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if source_row is None:
        return None, "source_not_found"

    target_row = db.execute(
        "SELECT id, owner_agent_id, visibility, status FROM memories WHERE id = ?",
        (target_memory_id,),
    ).fetchone()
    if target_row is None:
        return None, "target_not_found"

    if source_row[1] != requester_agent_id:
        return None, "forbidden"

    # Target must be visible to requester: shared or requester's private.
    if target_row[2] == "private" and target_row[1] != requester_agent_id:
        return None, "forbidden"

    source_status = source_row[3] or "active"
    target_status = target_row[3] or "active"
    if source_status != "active" or target_status != "active":
        return None, "invalid_transition"

    existing = db.execute(
        "SELECT id FROM memory_relations "
        "WHERE source_memory_id = ? AND target_memory_id = ? AND relation_type = ?",
        (memory_id, target_memory_id, relation_type),
    ).fetchone()

    if existing is not None:
        source_status_value = "archived" if relation_type == "merged_into" else "invalidated"
        return {
            "source_memory_id": memory_id,
            "target_memory_id": target_memory_id,
            "relation_type": relation_type,
            "source_status": source_status_value,
        }, None

    source_status_value = "archived" if relation_type == "merged_into" else "invalidated"

    db.execute(
        "INSERT INTO memory_relations ("
        "source_memory_id, target_memory_id, relation_type, actor_agent_id"
        ") VALUES (?, ?, ?, ?)",
        (memory_id, target_memory_id, relation_type, requester_agent_id),
    )
    db.execute(
        "UPDATE memories "
        "SET status = ?, updated_at = CURRENT_TIMESTAMP, status_updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (source_status_value, memory_id),
    )
    db.execute(
        "UPDATE memories "
        "SET updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (target_memory_id,),
    )
    db.commit()
    return {
        "source_memory_id": memory_id,
        "target_memory_id": target_memory_id,
        "relation_type": relation_type,
        "source_status": source_status_value,
    }, None


def insert_entity(
    db: sqlite3.Connection,
    name: str,
    type_: str,
    details: str,
    tags: str = "",
) -> int:
    cur = db.execute(
        "INSERT INTO entities (name, type, details, tags) VALUES (?, ?, ?, ?)",
        (name, type_, details, tags),
    )
    db.commit()
    return cur.lastrowid


def insert_embedding(
    db: sqlite3.Connection,
    text: str,
    vector: list,
    model_version: str,
) -> int:
    cur = db.execute(
        "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
        (text, json.dumps(vector), model_version),
    )
    db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Importance scoring
# ---------------------------------------------------------------------------

def compute_importance(db: sqlite3.Connection, text: str) -> float:
    lower_text = text.lower()
    keywords = db.execute("SELECT keyword, score FROM importance_keywords").fetchall()
    total = 0.0
    for row in keywords:
        keyword = row[0]
        score = row[1]
        if keyword in lower_text:
            total += score
    return min(total, 1.0)


# ---------------------------------------------------------------------------
# Vector similarity
# ---------------------------------------------------------------------------

def cosine_similarity(v1: list, v2: list) -> float:
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


def semantic_search(db: sqlite3.Connection, query_vector: list, top_k: int = 10) -> list:
    """Perform semantic search with bounded result set using cursor iteration.
    
    Instead of loading all embeddings into memory, this iterates through rows
    and maintains only the top-k results, reducing O(n) memory to O(k).
    """
    # Use a min-heap to efficiently maintain top-k results without loading all
    import heapq

    if top_k <= 0:
        return []

    rows = db.execute("SELECT id, text, vector FROM embeddings")
    top_results = []  # min-heap of (similarity, id, text)

    for row in rows:
        try:
            stored_vector = json.loads(row[2])
        except (TypeError, ValueError):
            continue
        if not isinstance(stored_vector, list):
            continue
        sim = cosine_similarity(query_vector, stored_vector)

        # Keep only top-k by using negative similarity in min-heap
        if len(top_results) < top_k:
            heapq.heappush(top_results, (sim, row[0], row[1]))
        elif sim > top_results[0][0]:  # Better than worst in top-k
            heapq.heapreplace(top_results, (sim, row[0], row[1]))

    # Extract and sort results by similarity descending
    scored = [
        {"id": item[1], "text": item[2], "similarity": item[0]}
        for item in sorted(top_results, reverse=True)
    ]
    return scored
