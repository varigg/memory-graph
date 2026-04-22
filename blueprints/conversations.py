from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.conversation_repository import (
    compute_importance,
    fts_search_conversations,
    insert_conversation,
)
from storage.embedding_repository import insert_embedding

bp = Blueprint("conversations", __name__)

@bp.route("/log", methods=["POST"])
def log_conversation():
    import embeddings

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    role = data.get("role")
    content = data.get("content")
    if not role or not content:
        return jsonify({"error": "role and content are required"}), 400
    channel = data.get("channel", "default")
    db = get_db()
    importance = compute_importance(db, content)
    vector = embeddings.embed(content)
    embedding_id = None
    if vector is not None:
        existing = db.execute(
            "SELECT id FROM embeddings WHERE text = ?", (content,)
        ).fetchone()
        if existing is None:
            embedding_id = insert_embedding(db, content, vector, "auto")
        else:
            embedding_id = existing[0]
    rowid = insert_conversation(db, role, content, channel, importance, embedding_id)
    return jsonify({"id": rowid}), 201


@bp.route("/recent", methods=["GET"])
def recent():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    rows = db.execute(
        "SELECT id, role, content, channel, timestamp, importance"
        " FROM conversations ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/search", methods=["GET"])
def search():
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
    safe_q = cleaned_q.replace('"', '')
    results = fts_search_conversations(
        db,
        f'"{safe_q}"',
        limit=limit,
        offset=offset,
    )
    return jsonify(results)


@bp.route("/stats", methods=["GET"])
def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    rows = db.execute(
        "SELECT role, COUNT(*) FROM conversations GROUP BY role"
    ).fetchall()
    by_role = {r[0]: r[1] for r in rows}
    return jsonify({"total": total, "by_role": by_role})
