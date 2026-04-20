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
) -> list:
    filter_predicate, filter_params = _build_memory_filter_predicate(visibility, owner_agent_id)
    where_clause = "f.fts_memories MATCH ?"
    query_params = [query]

    if filter_predicate:
        where_clause = f"{where_clause} AND {filter_predicate}"
        query_params.extend(filter_params)

    query_params.extend([limit, offset])
    rows = db.execute(
        f"SELECT m.name, m.content, m.description, m.id "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {where_clause} "
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


def _build_memory_filter_predicate(visibility=None, owner_agent_id=None):
    predicates = []
    bind_params = []

    if visibility is not None:
        predicates.append("visibility = ?")
        bind_params.append(visibility)

    if owner_agent_id is not None:
        predicates.append("owner_agent_id = ?")
        bind_params.append(owner_agent_id)

    if not predicates:
        return "", []

    return "(" + " AND ".join(predicates) + ")", bind_params


def list_memories(
    db: sqlite3.Connection,
    limit: int = 20,
    offset: int = 0,
    visibility: str = None,
    owner_agent_id: str = None,
) -> list:
    filter_predicate, filter_params = _build_memory_filter_predicate(visibility, owner_agent_id)
    where_clause = ""
    query_params = list(filter_params)
    if filter_predicate:
        where_clause = f" WHERE {filter_predicate}"

    query_params.extend([limit, offset])
    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, owner_agent_id, visibility "
        f"FROM memories{where_clause} "
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
) -> list:
    """List memories with visibility scoping applied."""
    predicate, bind_params = _build_scope_predicate(agent_id, shared_only, private_only)
    filter_predicate, filter_params = _build_memory_filter_predicate(visibility, owner_agent_id)
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)
    query_params = bind_params + [limit, offset]

    rows = db.execute(
        f"SELECT id, name, type, content, description, timestamp, confidence, "
        f"owner_agent_id, visibility FROM memories "
        f"WHERE {predicate} "
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
) -> list:
    """FTS search on memories with visibility scoping."""
    predicate, bind_params = _build_scope_predicate(agent_id, shared_only, private_only)
    filter_predicate, filter_params = _build_memory_filter_predicate(visibility, owner_agent_id)
    if filter_predicate:
        predicate = f"{predicate} AND {filter_predicate}"
        bind_params.extend(filter_params)

    # Build parameter list in correct order: scope params, query, limit, offset
    full_query_params = bind_params + [query, limit, offset]
    rows = db.execute(
        f"SELECT m.name, m.content, m.description, m.id "
        f"FROM memories m "
        f"INNER JOIN fts_memories f ON f.memory_id = m.id "
        f"WHERE {predicate} "
        f"AND f.fts_memories MATCH ? "
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
) -> int:
    cur = db.execute(
        "INSERT INTO memories ("
        "name, type, content, description, confidence, owner_agent_id, visibility"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, type_, content, description, confidence, owner_agent_id, visibility),
    )
    db.commit()
    return cur.lastrowid


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
