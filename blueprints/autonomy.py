from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from services.autonomy_checkpoint_service import (
    create_or_get_autonomy_checkpoint,
    list_autonomy_checkpoints_for_query,
)
from services.memory_request_models import parse_autonomy_checkpoint_payload

bp = Blueprint("autonomy", __name__)


@bp.route("/autonomy/check", methods=["POST"])
def create_autonomy_check():
    data = request.get_json(silent=True)
    try:
        payload = parse_autonomy_checkpoint_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result, err = create_or_get_autonomy_checkpoint(db, payload)
    if err == "goal_not_found":
        return jsonify({"error": "goal not found"}), 404
    if err == "action_not_found":
        return jsonify({"error": "action not found"}), 404
    if err in {"forbidden_goal", "forbidden_action"}:
        return jsonify({"error": "forbidden"}), 403
    if err == "goal_action_mismatch":
        return jsonify({"error": "action must belong to the provided goal"}), 409
    if err == "invalid_requested_level":
        return jsonify({"error": "requested_level must be between 0 and 5"}), 400
    if err == "invalid_approved_level":
        return jsonify({"error": "approved_level must be between 0 and 5"}), 400
    if err == "approved_level_exceeds_requested":
        return jsonify({"error": "approved_level must be <= requested_level"}), 400

    if result["created"]:
        return jsonify({"id": result["id"]}), 201
    return jsonify({"id": result["id"], "idempotent_replay": True}), 200


@bp.route("/autonomy/check/list", methods=["GET"])
def list_autonomy_checks():
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

    action_id = request.args.get("action_id")
    parsed_action_id = None
    if action_id is not None:
        try:
            parsed_action_id = int(action_id)
        except ValueError:
            return jsonify({"error": "action_id must be an integer"}), 400
        if parsed_action_id <= 0:
            return jsonify({"error": "action_id must be a positive integer"}), 400

    verdict = request.args.get("verdict")
    if verdict is not None:
        verdict = verdict.strip()
        if not verdict:
            return jsonify({"error": "verdict must be non-empty"}), 400
        if verdict not in {"approved", "denied", "sandbox_only"}:
            return jsonify({"error": "verdict must be one of: approved, denied, sandbox_only"}), 400

    reviewer_type = request.args.get("reviewer_type")
    if reviewer_type is not None:
        reviewer_type = reviewer_type.strip()
        if not reviewer_type:
            return jsonify({"error": "reviewer_type must be non-empty"}), 400
        if reviewer_type not in {"policy", "human", "system"}:
            return jsonify({"error": "reviewer_type must be one of: policy, human, system"}), 400

    run_id = request.args.get("run_id")
    if run_id is not None:
        run_id = run_id.strip()
        if not run_id:
            return jsonify({"error": "run_id must be non-empty"}), 400

    db = get_db()
    rows = list_autonomy_checkpoints_for_query(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        goal_id=parsed_goal_id,
        action_id=parsed_action_id,
        verdict=verdict,
        reviewer_type=reviewer_type,
        run_id=run_id,
    )
    return jsonify(rows), 200
