import json

from flask import Blueprint, jsonify, request

from db_operations import (
    fts_search_memories,
    fts_search_memories_scoped,
    get_memory_by_idempotency_key,
    insert_entity,
    insert_memory,
)
from db_operations import list_memories as list_memories_db
from db_operations import (
    list_memories_scoped,
    promote_memory_to_shared,
    relate_memory_lifecycle,
    set_memory_verification,
    transition_memory_status,
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
    def _err(message):
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            jsonify({"error": message}),
            400,
        )

    visibility = request.args.get("visibility")
    owner_agent_id = request.args.get("owner_agent_id")
    status = request.args.get("status", "active")

    if visibility is not None and visibility not in {"shared", "private"}:
        return _err("visibility must be 'shared' or 'private'")

    if status not in {"active", "archived", "invalidated"}:
        return _err("status must be 'active', 'archived', or 'invalidated'")

    if owner_agent_id is not None and not owner_agent_id.strip():
        return _err("owner_agent_id must be non-empty")

    normalized_owner = owner_agent_id.strip() if owner_agent_id is not None else None
    run_id = request.args.get("run_id")
    normalized_run_id = run_id.strip() if run_id is not None and run_id.strip() else None

    tag = request.args.get("tag")
    normalized_tag = tag.strip() if tag is not None and tag.strip() else None

    min_confidence = request.args.get("min_confidence")
    parsed_min_confidence = None
    if min_confidence is not None:
        try:
            parsed_min_confidence = float(min_confidence)
        except ValueError:
            return _err("min_confidence must be a number")
        if parsed_min_confidence < 0.0 or parsed_min_confidence > 1.0:
            return _err("min_confidence must be between 0 and 1")

    updated_since = request.args.get("updated_since")
    normalized_updated_since = (
        updated_since.strip() if updated_since is not None and updated_since.strip() else None
    )

    recency_half_life_hours = request.args.get("recency_half_life_hours")
    parsed_recency_half_life_hours = None
    if recency_half_life_hours is not None:
        try:
            parsed_recency_half_life_hours = float(recency_half_life_hours)
        except ValueError:
            return _err("recency_half_life_hours must be a number")
        if parsed_recency_half_life_hours <= 0:
            return _err("recency_half_life_hours must be > 0")

    metadata_key = request.args.get("metadata_key")
    normalized_metadata_key = (
        metadata_key.strip() if metadata_key is not None and metadata_key.strip() else None
    )

    metadata_value_raw = request.args.get("metadata_value")
    metadata_value_type = request.args.get("metadata_value_type", "string")
    parsed_metadata_value = None
    parsed_metadata_value_type = None
    if normalized_metadata_key is not None:
        allowed_types = {"string", "number", "boolean", "null"}
        if metadata_value_type not in allowed_types:
            return _err("metadata_value_type must be one of: string, number, boolean, null")
        parsed_metadata_value_type = metadata_value_type

        if metadata_value_raw is not None:
            if metadata_value_type == "string":
                parsed_metadata_value = metadata_value_raw
            elif metadata_value_type == "number":
                try:
                    parsed_metadata_value = float(metadata_value_raw)
                except ValueError:
                    return _err("metadata_value must be numeric when metadata_value_type=number")
            elif metadata_value_type == "boolean":
                lowered = metadata_value_raw.lower()
                if lowered not in {"true", "false"}:
                    return _err("metadata_value must be true or false when metadata_value_type=boolean")
                parsed_metadata_value = lowered == "true"
            elif metadata_value_type == "null":
                parsed_metadata_value = None
        elif metadata_value_type == "null":
            parsed_metadata_value = None

    return (
        visibility,
        normalized_owner,
        status,
        normalized_run_id,
        normalized_tag,
        parsed_min_confidence,
        normalized_updated_since,
        parsed_recency_half_life_hours,
        normalized_metadata_key,
        parsed_metadata_value,
        parsed_metadata_value_type,
        None,
        None,
    )


def _normalize_memory_payload(data):
    if not data:
        return None, jsonify({"error": "JSON body required"}), 400

    name = data.get("name")
    content = data.get("content")
    if not name or not content:
        return None, jsonify({"error": "name and content are required"}), 400

    owner_agent_id = data.get("owner_agent_id")
    if not isinstance(owner_agent_id, str) or not owner_agent_id.strip():
        return None, jsonify({"error": "owner_agent_id is required"}), 400

    visibility = data.get("visibility", "shared")
    if visibility not in {"shared", "private"}:
        return None, jsonify({"error": "visibility must be 'shared' or 'private'"}), 400

    type_ = data.get("type", "note")
    description = data.get("description", "")
    tags = data.get("tags", "")
    if tags is None:
        tags = ""
    if not isinstance(tags, str):
        return None, jsonify({"error": "tags must be a string"}), 400

    run_id = data.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
        return None, jsonify({"error": "run_id must be a non-empty string when provided"}), 400

    idempotency_key = data.get("idempotency_key")
    if idempotency_key is not None and (
        not isinstance(idempotency_key, str) or not idempotency_key.strip()
    ):
        return None, jsonify({"error": "idempotency_key must be a non-empty string when provided"}), 400

    metadata = data.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        return None, jsonify({"error": "metadata must be an object when provided"}), 400

    try:
        metadata_json = json.dumps(metadata)
    except (TypeError, ValueError):
        return None, jsonify({"error": "metadata must be JSON-serializable"}), 400

    return {
        "name": name,
        "content": content,
        "owner_agent_id": owner_agent_id.strip(),
        "visibility": visibility,
        "type": type_,
        "description": description,
        "tags": tags,
        "run_id": run_id.strip() if isinstance(run_id, str) else None,
        "idempotency_key": idempotency_key.strip() if isinstance(idempotency_key, str) else None,
        "metadata_json": metadata_json,
    }, None, None


def _create_or_get_memory(db, payload):
    idempotency_key = payload["idempotency_key"]
    owner_agent_id = payload["owner_agent_id"]
    if idempotency_key:
        existing = get_memory_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is not None:
            return {"id": existing[0], "created": False}

    rowid = insert_memory(
        db,
        payload["name"],
        payload["type"],
        payload["content"],
        payload["description"],
        owner_agent_id=owner_agent_id,
        visibility=payload["visibility"],
        tags=payload["tags"],
        run_id=payload["run_id"],
        idempotency_key=idempotency_key,
        metadata_json=payload["metadata_json"],
    )
    return {"id": rowid, "created": True}


def _transition_memory_lifecycle(target_status):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    memory_id = data.get("memory_id")
    agent_id = data.get("agent_id")
    if not isinstance(memory_id, int):
        return jsonify({"error": "memory_id must be an integer"}), 400
    if not isinstance(agent_id, str) or not agent_id.strip():
        return jsonify({"error": "agent_id is required"}), 400

    db = get_db()
    transitioned, err = transition_memory_status(
        db,
        memory_id,
        agent_id.strip(),
        target_status,
    )
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(transitioned), 200


def _relate_memory_lifecycle(relation_type):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    memory_id = data.get("memory_id")
    target_memory_id = data.get("target_memory_id")
    if target_memory_id is None:
        target_memory_id = data.get("replacement_memory_id")

    agent_id = data.get("agent_id")
    if not isinstance(memory_id, int):
        return jsonify({"error": "memory_id must be an integer"}), 400
    if not isinstance(target_memory_id, int):
        return jsonify({"error": "target_memory_id must be an integer"}), 400
    if not isinstance(agent_id, str) or not agent_id.strip():
        return jsonify({"error": "agent_id is required"}), 400

    db = get_db()
    related, err = relate_memory_lifecycle(
        db,
        memory_id,
        target_memory_id,
        agent_id.strip(),
        relation_type,
    )
    if err in {"source_not_found", "target_not_found"}:
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err in {"same_memory", "invalid_transition", "invalid_relation"}:
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(related), 200


# ---------------------------------------------------------------------------
# Memory routes
# ---------------------------------------------------------------------------


@bp.route("/memory", methods=["POST"])
def create_memory():
    data = request.get_json(silent=True)
    payload, err_resp, err_status = _normalize_memory_payload(data)
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    result = _create_or_get_memory(db, payload)
    if result["created"]:
        return jsonify({"id": result["id"]}), 201
    return jsonify({"id": result["id"], "idempotent_replay": True}), 200


@bp.route("/memory/batch", methods=["POST"])
def create_memory_batch():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    memories = data.get("memories")
    if not isinstance(memories, list) or not memories:
        return jsonify({"error": "memories must be a non-empty list"}), 400

    db = get_db()
    created = []
    for index, item in enumerate(memories):
        payload, err_resp, err_status = _normalize_memory_payload(item)
        if err_resp is not None:
            return jsonify({"error": f"invalid item at index {index}", "detail": err_resp.get_json()["error"]}), err_status
        created.append(_create_or_get_memory(db, payload))

    return jsonify({"results": created}), 201


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


@bp.route("/memory/archive", methods=["POST"])
def archive_memory():
    return _transition_memory_lifecycle("archived")


@bp.route("/memory/invalidate", methods=["POST"])
def invalidate_memory():
    return _transition_memory_lifecycle("invalidated")


@bp.route("/memory/verify", methods=["POST"])
def verify_memory():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    memory_id = data.get("memory_id")
    agent_id = data.get("agent_id")
    verification_status = data.get("verification_status")
    verification_source = data.get("verification_source")

    if not isinstance(memory_id, int):
        return jsonify({"error": "memory_id must be an integer"}), 400
    if not isinstance(agent_id, str) or not agent_id.strip():
        return jsonify({"error": "agent_id is required"}), 400
    if verification_status not in {"unverified", "verified", "disputed"}:
        return jsonify({"error": "verification_status must be 'unverified', 'verified', or 'disputed'"}), 400
    if verification_source is not None and not isinstance(verification_source, str):
        return jsonify({"error": "verification_source must be a string when provided"}), 400

    db = get_db()
    verified, err = set_memory_verification(
        db,
        memory_id,
        agent_id.strip(),
        verification_status,
        verification_source,
    )
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    return jsonify(verified), 200


@bp.route("/memory/merge", methods=["POST"])
def merge_memory():
    return _relate_memory_lifecycle("merged_into")


@bp.route("/memory/supersede", methods=["POST"])
def supersede_memory():
    return _relate_memory_lifecycle("superseded_by")


@bp.route("/memory/list", methods=["GET"])
def list_memories():
    limit, offset, err_resp, err_status = _parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = _parse_scope_flags()
    if err_resp is not None:
        return err_resp, err_status
    (
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        recency_half_life_hours,
        metadata_key,
        metadata_value,
        metadata_value_type,
        err_resp,
        err_status,
    ) = _parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()

    # If agent_id is provided, use scoped listing
    if agent_id:
        rows = list_memories_scoped(
            db,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
            shared_only=shared_only,
            private_only=private_only,
            visibility=visibility,
            owner_agent_id=owner_agent_id,
            status=status,
            run_id=run_id,
            tag=tag,
            min_confidence=min_confidence,
            updated_since=updated_since,
            metadata_key=metadata_key,
            metadata_value=metadata_value,
            metadata_value_type=metadata_value_type,
            recency_half_life_hours=recency_half_life_hours,
        )
        return jsonify(rows)

    # Legacy behavior: no scoping if agent_id not provided
    rows = list_memories_db(
        db,
        limit=limit,
        offset=offset,
        visibility=visibility,
        owner_agent_id=owner_agent_id,
        status=status,
        run_id=run_id,
        tag=tag,
        min_confidence=min_confidence,
        updated_since=updated_since,
        metadata_key=metadata_key,
        metadata_value=metadata_value,
        metadata_value_type=metadata_value_type,
        recency_half_life_hours=recency_half_life_hours,
    )
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
    (
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        recency_half_life_hours,
        metadata_key,
        metadata_value,
        metadata_value_type,
        err_resp,
        err_status,
    ) = _parse_read_filters()
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
                status=status,
                run_id=run_id,
                tag=tag,
                min_confidence=min_confidence,
                updated_since=updated_since,
                recency_half_life_hours=recency_half_life_hours,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
                metadata_value_type=metadata_value_type,
            )
        else:
            results = fts_search_memories(
                db,
                f'"{safe_topic}"',
                limit=limit,
                offset=offset,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
                status=status,
                run_id=run_id,
                tag=tag,
                min_confidence=min_confidence,
                updated_since=updated_since,
                recency_half_life_hours=recency_half_life_hours,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
                metadata_value_type=metadata_value_type,
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
    (
        visibility,
        owner_agent_id,
        status,
        run_id,
        tag,
        min_confidence,
        updated_since,
        recency_half_life_hours,
        metadata_key,
        metadata_value,
        metadata_value_type,
        err_resp,
        err_status,
    ) = _parse_read_filters()
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
                status=status,
                run_id=run_id,
                tag=tag,
                min_confidence=min_confidence,
                updated_since=updated_since,
                recency_half_life_hours=recency_half_life_hours,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
                metadata_value_type=metadata_value_type,
            )
        else:
            results = fts_search_memories(
                db,
                f'"{safe_q}"',
                limit=limit,
                offset=offset,
                visibility=visibility,
                owner_agent_id=owner_agent_id,
                status=status,
                run_id=run_id,
                tag=tag,
                min_confidence=min_confidence,
                updated_since=updated_since,
                recency_half_life_hours=recency_half_life_hours,
                metadata_key=metadata_key,
                metadata_value=metadata_value,
                metadata_value_type=metadata_value_type,
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
