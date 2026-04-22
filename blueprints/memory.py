from flask import Blueprint, current_app, jsonify, request

from blueprints._params import parse_limit_offset, parse_read_filters, parse_scope_flags
from db_utils import get_db, write_transaction
from services.memory_lifecycle_service import (
    cleanup_stale_private_memories,
    promote_memory_to_shared,
    relate_memory_lifecycle,
    set_memory_verification,
    transition_memory_status,
)
from services.memory_request_models import (
    parse_action_payload,
    parse_cleanup_payload,
    parse_relation_payload,
    parse_verify_payload,
)
from services.memory_retrieval_service import list_memories as list_memories_service
from services.memory_retrieval_service import recall_memories, search_memories
from services.memory_write_service import (
    create_memory_batch as service_create_memory_batch,
)
from services.memory_write_service import create_or_get_memory, parse_memory_payload
from services.ops_metrics_service import record_retrieval_observation
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
    with write_transaction(db):
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

    payloads = []
    for index, item in enumerate(memories):
        try:
            payloads.append(parse_memory_payload(item))
        except ValueError as exc:
            return jsonify({"error": f"invalid item at index {index}", "detail": str(exc)}), 400

    db = get_db()
    results = service_create_memory_batch(db, payloads)
    return jsonify({"results": results}), 201


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
    try:
        payload = parse_action_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    transitioned, err = transition_memory_status(
        db,
        payload["memory_id"],
        payload["agent_id"],
        "archived",
    )
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
    try:
        payload = parse_action_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    transitioned, err = transition_memory_status(
        db,
        payload["memory_id"],
        payload["agent_id"],
        "invalidated",
    )
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
    try:
        payload = parse_cleanup_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result, err = cleanup_stale_private_memories(
        db,
        retention_days=payload["retention_days"],
        dry_run=payload["dry_run"],
        owner_agent_id=payload["owner_agent_id"],
        status=payload["status"],
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
    try:
        payload = parse_verify_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    verified, err = set_memory_verification(
        db,
        payload["memory_id"],
        payload["agent_id"],
        payload["verification_status"],
        payload["verification_source"],
    )
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    return jsonify(verified), 200


@bp.route("/memory/merge", methods=["POST"])
def merge_memory():
    data = request.get_json(silent=True)
    try:
        payload = parse_relation_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    related, err = relate_memory_lifecycle(
        db,
        payload["memory_id"],
        payload["target_memory_id"],
        payload["agent_id"],
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
    try:
        payload = parse_relation_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    related, err = relate_memory_lifecycle(
        db,
        payload["memory_id"],
        payload["target_memory_id"],
        payload["agent_id"],
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
    record_retrieval_observation(current_app, "memory_list", len(rows))
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
    record_retrieval_observation(current_app, "memory_recall", len(results))
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
    record_retrieval_observation(current_app, "memory_search", len(results))
    return jsonify(results)


@bp.route("/memory/<int:memory_id>", methods=["DELETE"])
def delete_memory(memory_id):
    db = get_db()
    row = db.execute("SELECT id FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    with write_transaction(db):
        db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
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
