import json
import math
import sqlite3


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


def _cosine_similarity(v1: list, v2: list) -> float:
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


def semantic_search(db: sqlite3.Connection, query_vector: list, top_k: int = 10) -> list:
    import heapq

    if top_k <= 0:
        return []

    rows = db.execute("SELECT id, text, vector FROM embeddings")
    top_results = []

    for row in rows:
        try:
            stored_vector = json.loads(row[2])
        except (TypeError, ValueError):
            continue
        if not isinstance(stored_vector, list):
            continue
        sim = _cosine_similarity(query_vector, stored_vector)

        if len(top_results) < top_k:
            heapq.heappush(top_results, (sim, row[0], row[1]))
        elif sim > top_results[0][0]:
            heapq.heapreplace(top_results, (sim, row[0], row[1]))

    return [
        {"id": item[1], "text": item[2], "similarity": item[0]}
        for item in sorted(top_results, reverse=True)
    ]


def reindex_embeddings(db: sqlite3.Connection, embed_fn) -> int:
    rows = db.execute("SELECT id, content FROM conversations").fetchall()

    inserts_by_text = {}
    updates = []
    existing_by_text = {}
    count = 0

    for row in rows:
        conv_id = row[0]
        content = row[1]

        if content in existing_by_text:
            updates.append((existing_by_text[content], conv_id))
            count += 1
            continue

        if content in inserts_by_text:
            inserts_by_text[content]["conv_ids"].append(conv_id)
            count += 1
            continue

        vector = embed_fn(content)
        if vector is None:
            continue

        existing = db.execute(
            "SELECT id FROM embeddings WHERE text = ?", (content,)
        ).fetchone()

        if existing is None:
            inserts_by_text[content] = {
                "vector_json": json.dumps(vector),
                "model": "auto",
                "conv_ids": [conv_id],
            }
        else:
            emb_id = existing[0]
            existing_by_text[content] = emb_id
            updates.append((emb_id, conv_id))
        count += 1

    for content, payload in inserts_by_text.items():
        cur = db.execute(
            "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
            (content, payload["vector_json"], payload["model"]),
        )
        emb_id = cur.lastrowid

        for conv_id in payload["conv_ids"]:
            db.execute(
                "UPDATE conversations SET embedding_id = ? WHERE id = ? AND embedding_id IS NULL",
                (emb_id, conv_id),
            )

    for emb_id, conv_id in updates:
        db.execute(
            "UPDATE conversations SET embedding_id = ? WHERE id = ? AND embedding_id IS NULL",
            (emb_id, conv_id),
        )

    db.commit()
    return count
