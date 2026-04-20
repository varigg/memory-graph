import json
import math
import sqlite3

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
        f"SELECT m.name, m.content, m.description, m.id "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {where_clause} "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()
    return [{"name": r[0], "content": r[1], "description": r[2], "memory_id": r[3]} for r in rows]


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
    )
    where_clause = ""
    query_params = list(filter_params)
    if filter_predicate:
        where_clause = f" WHERE {filter_predicate}"

    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    query_params.extend(order_params)
    query_params.extend([limit, offset])
    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, owner_agent_id, visibility, status, tags, run_id, idempotency_key, verification_status, verification_source, verified_at "
        f"FROM memories{where_clause} "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        query_params,
    ).fetchall()
    return [dict(r) for r in rows]


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
    )
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)
    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    query_params = bind_params + order_params + [limit, offset]

    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, "
        f"owner_agent_id, visibility, status, tags, run_id, idempotency_key, verification_status, verification_source, verified_at FROM memories "
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
            "verification_status": r[13],
            "verification_source": r[14],
            "verified_at": r[15],
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
    )
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)

    # Build parameter list in correct order: scope params, query, limit, offset
    order_clause, order_params = _memory_order_by_clause(recency_half_life_hours)
    full_query_params = bind_params + [query] + order_params + [limit, offset]
    rows = db.execute(
        f"SELECT m.name, m.content, m.description, m.id "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {predicate} "
        f"AND f.fts_memories MATCH ? "
        f"{order_clause} "
        f"LIMIT ? OFFSET ?",
        full_query_params,
    ).fetchall()
    return [{"name": r[0], "content": r[1], "description": r[2], "memory_id": r[3]} for r in rows]


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
) -> int:
    cur = db.execute(
        "INSERT INTO memories ("
        "name, type, content, description, confidence, owner_agent_id, visibility, tags, run_id, idempotency_key"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
