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
    db: sqlite3.Connection, query: str, limit: int = 20, offset: int = 0
) -> list:
    rows = db.execute(
        "SELECT name, content, description, memory_id"
        " FROM fts_memories WHERE fts_memories MATCH ?"
        " LIMIT ? OFFSET ?",
        (query, limit, offset),
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
