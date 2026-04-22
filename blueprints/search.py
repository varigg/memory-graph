import sqlite3

from flask import Blueprint, current_app, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from services.hybrid_search_service import hybrid_search
from services.ops_metrics_service import (
    record_db_lock_event,
    record_reindex_observation,
    record_retrieval_observation,
)
from storage.embedding_repository import reindex_embeddings, semantic_search
from storage.metrics_repository import get_embedding_dedupe_signals

bp = Blueprint("search", __name__)

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
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    vector = embeddings.embed(cleaned_q)
    if vector is None:
        return jsonify([])
    db = get_db()
    results = semantic_search(db, vector, top_k=offset + limit)
    results = results[offset : offset + limit]
    record_retrieval_observation(current_app, "semantic_search", len(results))
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
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    results = hybrid_search(db, embeddings.embed, cleaned_q, limit, offset)
    record_retrieval_observation(current_app, "hybrid_search", len(results))
    return jsonify(results)


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
    import embeddings

    db = get_db()
    before = get_embedding_dedupe_signals(db)
    try:
        count = reindex_embeddings(db, embeddings.embed)
    except sqlite3.Error as exc:
        db.rollback()
        if "database is locked" in str(exc).lower():
            record_db_lock_event(current_app, "embeddings_reindex")
        return jsonify({"error": "reindex failed"}), 500

    after = get_embedding_dedupe_signals(db)
    deduped_rows = max(
        int(before["embedding_duplicate_rows"]) - int(after["embedding_duplicate_rows"]),
        0,
    )
    record_reindex_observation(current_app, count, deduped_rows)

    return jsonify({"reindexed": count})
