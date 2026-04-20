from flask import Blueprint, jsonify, request

from db_operations import fts_search_memories, insert_entity, insert_memory
from db_utils import get_db

bp = Blueprint("memory", __name__)

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
# Memory routes
# ---------------------------------------------------------------------------


@bp.route("/memory", methods=["POST"])
def create_memory():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    name = data.get("name")
    content = data.get("content")
    if not name or not content:
        return jsonify({"error": "name and content are required"}), 400
    type_ = data.get("type", "note")
    description = data.get("description", "")
    db = get_db()
    rowid = insert_memory(db, name, type_, content, description)
    return jsonify({"id": rowid}), 201


@bp.route("/memory/list", methods=["GET"])
def list_memories():
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    rows = db.execute(
        "SELECT id, name, type, content, description, timestamp, confidence FROM memories"
        " LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/memory/recall", methods=["GET"])
def recall_memory():
    topic = request.args.get("topic")
    if topic is None:
        return jsonify({"error": "topic parameter required"}), 400
    cleaned_topic = topic.strip()
    if not cleaned_topic:
        return jsonify({"error": "topic parameter must be non-empty"}), 400
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    try:
        safe_topic = cleaned_topic.replace('"', "")
        results = fts_search_memories(
            db,
            f'"{safe_topic}"',
            limit=limit,
            offset=offset,
        )
    except Exception:
        results = []
    return jsonify(results)


@bp.route("/memory/search", methods=["GET"])
def search_memory():
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
    try:
        safe_q = cleaned_q.replace('"', "")
        results = fts_search_memories(
            db,
            f'"{safe_q}"',
            limit=limit,
            offset=offset,
        )
    except Exception:
        results = []
    return jsonify(results)


@bp.route("/memory/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    db = get_db()
    row = db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    db.commit()
    return jsonify({"deleted": memory_id}), 200


# ---------------------------------------------------------------------------
# Entity routes
# ---------------------------------------------------------------------------


@bp.route("/entity", methods=["POST"])
def create_entity():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    type_ = data.get("type", "")
    details = data.get("details", "")
    tags = data.get("tags", "")
    db = get_db()
    rowid = insert_entity(db, name, type_, details, tags)
    return jsonify({"id": rowid}), 201


@bp.route("/entity/search", methods=["GET"])
def search_entity():
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
    escaped = (
        cleaned_q.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    rows = db.execute(
        "SELECT id, name, type, details, tags FROM entities"
        " WHERE name LIKE ? ESCAPE '\\'"
        " OR type LIKE ? ESCAPE '\\'"
        " OR details LIKE ? ESCAPE '\\'"
        " OR tags LIKE ? ESCAPE '\\'"
        " ORDER BY id DESC LIMIT ? OFFSET ?",
        (pattern, pattern, pattern, pattern, limit, offset),
    ).fetchall()
    return jsonify([dict(r) for r in rows])
