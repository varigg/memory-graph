from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from services.action_log_service import (
    complete_action_log_entry,
    create_or_get_action_log,
    list_action_logs_for_query,
)
from services.memory_request_models import (
    parse_action_log_complete_payload,
    parse_action_log_create_payload,
)

bp = Blueprint("action_log", __name__)


@bp.route("/action-log", methods=["POST"])
def create_action_log():
    data = request.get_json(silent=True)
    try:
        payload = parse_action_log_create_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result, err = create_or_get_action_log(db, payload)
    if err == "goal_not_found":
        return jsonify({"error": "goal not found"}), 404
    if err == "forbidden_goal":
        return jsonify({"error": "forbidden"}), 403
    if err == "parent_not_found":
        return jsonify({"error": "parent action not found"}), 404
    if err == "invalid_parent":
        return jsonify({"error": "parent action must belong to the same goal"}), 409
    if err == "rollback_not_found":
        return jsonify({"error": "rollback action not found"}), 404
    if err == "invalid_mode":
        return jsonify({"error": "mode must be one of: plan, dry_run, live, rollback"}), 400
    if err == "invalid_status":
        return jsonify({"error": "status must be one of: queued, running, succeeded, failed, rolled_back"}), 400

    if result["created"]:
        return jsonify({"id": result["id"]}), 201
    return jsonify({"id": result["id"], "idempotent_replay": True}), 200


@bp.route("/action-log/list", methods=["GET"])
def list_action_logs():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    owner_agent_id = request.args.get("owner_agent_id")
    if owner_agent_id is not None:
        owner_agent_id = owner_agent_id.strip()
        if not owner_agent_id:
            return jsonify({"error": "owner_agent_id must be non-empty"}), 400

    goal_id = request.args.get("goal_id")
    parsed_goal_id = None
    if goal_id is not None:
        try:
            parsed_goal_id = int(goal_id)
        except ValueError:
            return jsonify({"error": "goal_id must be an integer"}), 400
        if parsed_goal_id <= 0:
            return jsonify({"error": "goal_id must be a positive integer"}), 400

    status = request.args.get("status")
    if status is not None:
        status = status.strip()
        if not status:
            return jsonify({"error": "status must be non-empty"}), 400
        if status not in {"queued", "running", "succeeded", "failed", "rolled_back"}:
            return jsonify({"error": "status must be one of: queued, running, succeeded, failed, rolled_back"}), 400

    run_id = request.args.get("run_id")
    if run_id is not None:
        run_id = run_id.strip()
        if not run_id:
            return jsonify({"error": "run_id must be non-empty"}), 400

    db = get_db()
    rows = list_action_logs_for_query(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        goal_id=parsed_goal_id,
        status=status,
        run_id=run_id,
    )
    return jsonify(rows), 200


@bp.route("/action-log/<int:action_id>/complete", methods=["POST"])
def complete_action_log(action_id):
    data = request.get_json(silent=True)
    try:
        payload = parse_action_log_complete_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result, err = complete_action_log_entry(
        db,
        action_id=action_id,
        owner_agent_id=payload["owner_agent_id"],
        status=payload["status"],
        observed_result=payload["observed_result"],
        rollback_action_id=payload["rollback_action_id"],
    )
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "invalid_status":
        return jsonify({"error": "status must be one of: succeeded, failed, rolled_back"}), 400
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    if err == "rollback_not_found":
        return jsonify({"error": "rollback action not found"}), 404

    return jsonify(result), 200
