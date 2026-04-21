import sqlite3

from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from services.hybrid_search_service import hybrid_search
from storage.embedding_repository import reindex_embeddings, semantic_search

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
    return jsonify(hybrid_search(db, embeddings.embed, cleaned_q, limit, offset))


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
    try:
        count = reindex_embeddings(db, embeddings.embed)
    except sqlite3.Error:
        db.rollback()
        return jsonify({"error": "reindex failed"}), 500

    return jsonify({"reindexed": count})
