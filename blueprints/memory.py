from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset, parse_read_filters, parse_scope_flags
from db_utils import get_db
from services.memory_lifecycle_service import (
    cleanup_stale_private_memories,
    promote_memory_to_shared,
    relate_memory_lifecycle,
    set_memory_verification,
    transition_memory_status,
)
from services.memory_retrieval_service import list_memories as list_memories_service
from services.memory_retrieval_service import recall_memories, search_memories
from services.memory_write_service import create_or_get_memory, parse_memory_payload
from storage.entity_repository import insert_entity, search_entities

bp = Blueprint("memory", __name__)


@bp.route("/memory", methods=["POST"])
def create_memory():
    data = request.get_json(silent=True)
    try:
        payload = parse_memory_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result = create_or_get_memory(db, payload)
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
        try:
            payload = parse_memory_payload(item)
        except ValueError as exc:
            return jsonify({"error": f"invalid item at index {index}", "detail": str(exc)}), 400
        created.append(create_or_get_memory(db, payload))

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
    transitioned, err = transition_memory_status(db, memory_id, agent_id.strip(), "archived")
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(transitioned), 200


@bp.route("/memory/invalidate", methods=["POST"])
def invalidate_memory():
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
    transitioned, err = transition_memory_status(db, memory_id, agent_id.strip(), "invalidated")
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(transitioned), 200


@bp.route("/memory/cleanup-private", methods=["POST"])
def cleanup_private_memories():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    retention_days = data.get("retention_days")
    if not isinstance(retention_days, int):
        return jsonify({"error": "retention_days must be an integer"}), 400

    dry_run = data.get("dry_run", True)
    if not isinstance(dry_run, bool):
        return jsonify({"error": "dry_run must be a boolean when provided"}), 400

    owner_agent_id = data.get("owner_agent_id")
    if owner_agent_id is not None and not isinstance(owner_agent_id, str):
        return jsonify({"error": "owner_agent_id must be a string when provided"}), 400

    status = data.get("status", "active")
    if not isinstance(status, str):
        return jsonify({"error": "status must be a string when provided"}), 400

    db = get_db()
    result, err = cleanup_stale_private_memories(
        db,
        retention_days=retention_days,
        dry_run=dry_run,
        owner_agent_id=owner_agent_id,
        status=status,
    )
    if err == "invalid_retention_days":
        return jsonify({"error": "retention_days must be > 0"}), 400
    if err == "invalid_status":
        return jsonify({"error": "status must be 'active', 'archived', 'invalidated', or 'all'"}), 400
    if err == "invalid_owner_agent_id":
        return jsonify({"error": "owner_agent_id must be non-empty when provided"}), 400
    return jsonify(result), 200


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
        "merged_into",
    )
    if err in {"source_not_found", "target_not_found"}:
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err in {"same_memory", "invalid_transition", "invalid_relation"}:
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(related), 200


@bp.route("/memory/supersede", methods=["POST"])
def supersede_memory():
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
        "superseded_by",
    )
    if err in {"source_not_found", "target_not_found"}:
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err in {"same_memory", "invalid_transition", "invalid_relation"}:
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(related), 200


@bp.route("/memory/list", methods=["GET"])
def list_memories():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = parse_scope_flags()
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
    ) = parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    rows = list_memories_service(
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


@bp.route("/memory/recall", methods=["GET"])
def recall_memory():
    topic = request.args.get("topic")
    if topic is None:
        return jsonify({"error": "topic parameter required"}), 400
    cleaned_topic = topic.strip()
    if not cleaned_topic:
        return jsonify({"error": "topic parameter must be non-empty"}), 400

    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = parse_scope_flags()
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
    ) = parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    results = recall_memories(
        db,
        topic=cleaned_topic,
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
        recency_half_life_hours=recency_half_life_hours,
        metadata_key=metadata_key,
        metadata_value=metadata_value,
        metadata_value_type=metadata_value_type,
    )
    return jsonify(results)


@bp.route("/memory/search", methods=["GET"])
def search_memory():
    q = request.args.get("q")
    if q is None:
        return jsonify({"error": "q parameter required"}), 400
    cleaned_q = q.strip()
    if not cleaned_q:
        return jsonify({"error": "q parameter must be non-empty"}), 400

    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    agent_id = request.args.get("agent_id")
    shared_only, private_only, err_resp, err_status = parse_scope_flags()
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
    ) = parse_read_filters()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    results = search_memories(
        db,
        q=cleaned_q,
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
        recency_half_life_hours=recency_half_life_hours,
        metadata_key=metadata_key,
        metadata_value=metadata_value,
        metadata_value_type=metadata_value_type,
    )
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

    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    db = get_db()
    rows = search_entities(db, cleaned_q, limit, offset)
    return jsonify(rows)
