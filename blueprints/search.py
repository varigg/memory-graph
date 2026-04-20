import sqlite3

from flask import Blueprint, jsonify, request

from db_operations import fts_search_conversations, semantic_search
from db_utils import get_db

bp = Blueprint("search", __name__)

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _parse_limit_offset():
    raw_limit = request.args.get("limit")
    raw_offset = request.args.get("offset")
    try:
        limit = int(raw_limit) if raw_limit is not None else _DEFAULT_LIMIT
        offset = int(raw_offset) if raw_offset is not None else 0
    except ValueError:
        return None, None, jsonify({"error": "limit and offset must be integers"}), 400
    if limit <= 0:
        return None, None, jsonify({"error": "limit must be a positive integer"}), 400
    if offset < 0:
        return None, None, jsonify({"error": "offset must be a non-negative integer"}), 400
    return min(limit, _MAX_LIMIT), offset, None, None


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


@bp.route("/search/semantic", methods=["GET"])
def semantic():
    import embeddings

    q = request.args.get("q")
    if q is None:
        return jsonify({"error": "q parameter required"}), 400
    cleaned_q = q.strip()
    if not cleaned_q:
        return jsonify({"error": "q parameter must be non-empty"}), 400
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    vector = embeddings.embed(cleaned_q)
    if vector is None:
        return jsonify([])
    db = get_db()
    results = semantic_search(db, vector, top_k=offset + limit)
    results = results[offset : offset + limit]
    return jsonify(results)


# ---------------------------------------------------------------------------
# Hybrid search
# ---------------------------------------------------------------------------


@bp.route("/search/hybrid", methods=["GET"])
def hybrid():
    import embeddings

    q = request.args.get("q")
    if q is None:
        return jsonify({"error": "q parameter required"}), 400
    cleaned_q = q.strip()
    if not cleaned_q:
        return jsonify({"error": "q parameter must be non-empty"}), 400
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()

    # FTS leg
    try:
        fts_results = fts_search_conversations(
            db,
            cleaned_q.replace('"', ''),
            limit=offset + limit,
            offset=0,
        )
    except (sqlite3.Error, ValueError):
        fts_results = []

    # Semantic leg
    vector = embeddings.embed(cleaned_q)
    sem_results = []
    if vector is not None:
        sem_results = semantic_search(db, vector, top_k=offset + limit)

    scores: dict = {}

    # Batch fetch all FTS conversation IDs and their importance in one query
    fts_conv_ids = [r["conversation_id"] for r in fts_results]
    fts_importance = {}
    if fts_conv_ids:
        placeholders = ",".join("?" * len(fts_conv_ids))
        rows = db.execute(
            f"SELECT id, importance FROM conversations WHERE id IN ({placeholders})",
            fts_conv_ids,
        ).fetchall()
        fts_importance = {row[0]: row[1] for row in rows}

    for rank, r in enumerate(fts_results):
        conv_id = r["conversation_id"]
        importance = fts_importance.get(conv_id, 0.0)
        scores[conv_id] = scores.get(conv_id, 0.0) + (1.0 / (rank + 60)) * (
            1.0 + importance
        )

    # Batch fetch all semantic embedding IDs and their associated conversations in one query
    sem_emb_ids = [r["id"] for r in sem_results]
    sem_conv_map = {}
    if sem_emb_ids:
        placeholders = ",".join("?" * len(sem_emb_ids))
        rows = db.execute(
            f"SELECT embedding_id, id, importance FROM conversations WHERE embedding_id IN ({placeholders})",
            sem_emb_ids,
        ).fetchall()
        sem_conv_map = {row[0]: (row[1], row[2]) for row in rows}

    for rank, r in enumerate(sem_results):
        emb_id = r["id"]
        if emb_id in sem_conv_map:
            conv_id, importance = sem_conv_map[emb_id]
            scores[conv_id] = scores.get(conv_id, 0.0) + (
                1.0 / (rank + 60)
            ) * (1.0 + importance)

    if not scores:
        return jsonify([])

    # Batch fetch all result conversations in one query
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

    return jsonify(results[offset : offset + limit])


# ---------------------------------------------------------------------------
# Embeddings stats + reindex
# ---------------------------------------------------------------------------


@bp.route("/embeddings/stats", methods=["GET"])
def embeddings_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    return jsonify({"total": total})


@bp.route("/embeddings/reindex", methods=["POST"])
def embeddings_reindex():
    import json

    import embeddings

    db = get_db()
    rows = db.execute("SELECT id, content FROM conversations").fetchall()
    
    # Batch the operations: collect all inserts and execute in bulk
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

        vector = embeddings.embed(content)
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
            # ensure the FK is set even if embedding already existed
            emb_id = existing[0]
            existing_by_text[content] = emb_id
            updates.append((emb_id, conv_id))
        count += 1
    
    try:
        # Execute all inserts in batch (still individual statements)
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

        # Execute all updates in batch
        for emb_id, conv_id in updates:
            db.execute(
                "UPDATE conversations SET embedding_id = ? WHERE id = ? AND embedding_id IS NULL",
                (emb_id, conv_id),
            )

        db.commit()
    except sqlite3.Error:
        db.rollback()
        return jsonify({"error": "reindex failed"}), 500

    return jsonify({"reindexed": count})
