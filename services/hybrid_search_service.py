import sqlite3

from storage.conversation_repository import fts_search_conversations
from storage.embedding_repository import semantic_search


def hybrid_search(db, embed_fn, query: str, limit: int, offset: int) -> list:
    try:
        fts_results = fts_search_conversations(
            db,
            query.replace('"', ""),
            limit=offset + limit,
            offset=0,
        )
    except (sqlite3.Error, ValueError):
        fts_results = []

    vector = embed_fn(query)
    sem_results = []
    if vector is not None:
        sem_results = semantic_search(db, vector, top_k=offset + limit)

    scores = {}

    fts_conv_ids = [r["conversation_id"] for r in fts_results]
    fts_importance = {}
    if fts_conv_ids:
        placeholders = ",".join("?" * len(fts_conv_ids))
        rows = db.execute(
            f"SELECT id, importance FROM conversations WHERE id IN ({placeholders})",
            fts_conv_ids,
        ).fetchall()
        fts_importance = {row[0]: row[1] for row in rows}

    for rank, result in enumerate(fts_results):
        conv_id = result["conversation_id"]
        importance = fts_importance.get(conv_id, 0.0)
        scores[conv_id] = scores.get(conv_id, 0.0) + (1.0 / (rank + 60)) * (
            1.0 + importance
        )

    sem_emb_ids = [r["id"] for r in sem_results]
    sem_conv_map = {}
    if sem_emb_ids:
        placeholders = ",".join("?" * len(sem_emb_ids))
        rows = db.execute(
            f"SELECT embedding_id, id, importance FROM conversations WHERE embedding_id IN ({placeholders})",
            sem_emb_ids,
        ).fetchall()
        sem_conv_map = {row[0]: (row[1], row[2]) for row in rows}

    for rank, result in enumerate(sem_results):
        emb_id = result["id"]
        if emb_id in sem_conv_map:
            conv_id, importance = sem_conv_map[emb_id]
            scores[conv_id] = scores.get(conv_id, 0.0) + (
                1.0 / (rank + 60)
            ) * (1.0 + importance)

    if not scores:
        return []

    result_conv_ids = list(scores.keys())
    placeholders = ",".join("?" * len(result_conv_ids))
    rows = db.execute(
        f"SELECT id, content, role, channel, importance FROM conversations WHERE id IN ({placeholders})",
        result_conv_ids,
    ).fetchall()
    conv_map = {row[0]: row for row in rows}

    results = []
    for conv_id, score in sorted(scores.items(), key=lambda x: -x[1]):
        if conv_id in conv_map:
            row = conv_map[conv_id]
            results.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "role": row[2],
                    "channel": row[3],
                    "importance": row[4],
                    "score": score,
                }
            )

    return results[offset : offset + limit]
