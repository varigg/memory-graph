from flask import Blueprint, jsonify, request

from db_operations import (
    fts_search_memories,
    fts_search_memories_scoped,
    insert_entity,
    insert_memory,
    list_memories as list_memories_db,
    list_memories_scoped,
    promote_memory_to_shared,
)
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


def _parse_scope_flags():
    """Parse shared_only and private_only flags."""
    shared_only_str = request.args.get("shared_only", "false").lower()
    private_only_str = request.args.get("private_only", "false").lower()

    shared_only = shared_only_str == "true"
    private_only = private_only_str == "true"

    if shared_only and private_only:
        return None, None, jsonify(
            {"error": "Cannot specify both shared_only and private_only"}
        ), 400

    return shared_only, private_only, None, None


def _parse_read_filters():
    visibility = request.args.get("visibility")
    owner_agent_id = request.args.get("owner_agent_id")

    if visibility is not None and visibility not in {"shared", "private"}:
        return None, None, jsonify({"error": "visibility must be 'shared' or 'private'"}), 400

    if owner_agent_id is not None and not owner_agent_id.strip():
        return None, None, jsonify({"error": "owner_agent_id must be non-empty"}), 400

    normalized_owner = owner_agent_id.strip() if owner_agent_id is not None else None
    return visibility, normalized_owner, None, None


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
    owner_agent_id = data.get("owner_agent_id")
    if not isinstance(owner_agent_id, str) or not owner_agent_id.strip():
        return jsonify({"error": "owner_agent_id is required"}), 400
    visibility = data.get("visibility", "shared")
    if visibility not in {"shared", "private"}:
        return jsonify({"error": "visibility must be 'shared' or 'private'"}), 400
    type_ = data.get("type", "note")
    description = data.get("description", "")
    db = get_db()
    rowid = insert_memory(
        db,
        name,
        type_,
        content,
        description,
        owner_agent_id=owner_agent_id.strip(),
        visibility=visibility,
    )
    return jsonify({"id": rowid}), 201


@bp.route("/memory/<int:memory_id>/promote", methods=["POST"])
def promote_memory(memory_id):
    agent_id = request.args.get("agent_id")
    if agent_id is None or not agent_id.strip():
        return jsonify({"error": "agent_id query parameter required"}), 400

    db = get_db()
    promoted, err = promote_memory_to_shared(db, memory_id, agent_id.strip())
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    return jsonify(promoted), 200


@bp.route("/memory/list", methods=["GET"])
def list_memories():
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = _parse_scope_flags()
    if err_resp is not None:
        return err_resp, err_status
    visibility, owner_agent_id, err_resp, err_status = _parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()

    # If agent_id is provided, use scoped listing
    if agent_id:
        rows = list_memories_scoped(
            db,
            agent_id,
            limit,
            offset,
            shared_only,
            private_only,
            visibility,
            owner_agent_id,
        )
        return jsonify(rows)

    # Legacy behavior: no scoping if agent_id not provided
    rows = list_memories_db(db, limit, offset, visibility, owner_agent_id)
    return jsonify(rows)


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

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = _parse_scope_flags()
    if err_resp is not None:
        return err_resp, err_status
    visibility, owner_agent_id, err_resp, err_status = _parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    try:
        safe_topic = cleaned_topic.replace('"', "")
        if agent_id:
            results = fts_search_memories_scoped(
                db,
                f'"{safe_topic}"',
                agent_id,
                limit=limit,
                offset=offset,
                shared_only=shared_only,
                private_only=private_only,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
            )
        else:
            results = fts_search_memories(
                db,
                f'"{safe_topic}"',
                limit=limit,
                offset=offset,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
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

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = _parse_scope_flags()
    if err_resp is not None:
        return err_resp, err_status
    visibility, owner_agent_id, err_resp, err_status = _parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    try:
        safe_q = cleaned_q.replace('"', "")
        if agent_id:
            results = fts_search_memories_scoped(
                db,
                f'"{safe_q}"',
                agent_id,
                limit=limit,
                offset=offset,
                shared_only=shared_only,
                private_only=private_only,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
            )
        else:
            results = fts_search_memories(
                db,
                f'"{safe_q}"',
                limit=limit,
                offset=offset,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
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
