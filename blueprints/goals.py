from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from services.goal_service import (
    create_or_get_goal,
    get_goal,
    list_goals_for_query,
    set_goal_status,
)
from services.memory_request_models import (
    parse_goal_create_payload,
    parse_goal_status_payload,
)

bp = Blueprint("goals", __name__)


@bp.route("/goal", methods=["POST"])
def create_goal():
    data = request.get_json(silent=True)
    try:
        payload = parse_goal_create_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    result = create_or_get_goal(db, payload)
    if result["created"]:
        return jsonify({"id": result["id"]}), 201
    return jsonify({"id": result["id"], "idempotent_replay": True}), 200


@bp.route("/goal/<int:goal_id>", methods=["GET"])
def get_goal_by_id(goal_id):
    db = get_db()
    goal, err = get_goal(db, goal_id)
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    return jsonify(goal), 200


@bp.route("/goal/list", methods=["GET"])
def list_goal_rows():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status

    owner_agent_id = request.args.get("owner_agent_id")
    if owner_agent_id is not None:
        owner_agent_id = owner_agent_id.strip()
        if not owner_agent_id:
            return jsonify({"error": "owner_agent_id must be non-empty"}), 400

    status = request.args.get("status")
    if status is not None:
        status = status.strip()
        if not status:
            return jsonify({"error": "status must be non-empty"}), 400
        if status not in {"active", "blocked", "completed", "abandoned"}:
            return jsonify({"error": "status must be one of: active, blocked, completed, abandoned"}), 400

    run_id = request.args.get("run_id")
    if run_id is not None:
        run_id = run_id.strip()
        if not run_id:
            return jsonify({"error": "run_id must be non-empty"}), 400

    db = get_db()
    rows = list_goals_for_query(
        db,
        limit=limit,
        offset=offset,
        owner_agent_id=owner_agent_id,
        status=status,
        run_id=run_id,
    )
    return jsonify(rows), 200


@bp.route("/goal/<int:goal_id>/status", methods=["POST"])
def update_goal_status(goal_id):
    data = request.get_json(silent=True)
    try:
        payload = parse_goal_status_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db = get_db()
    updated, err = set_goal_status(
        db,
        goal_id=goal_id,
        owner_agent_id=payload["owner_agent_id"],
        target_status=payload["status"],
        reason=payload["reason"],
    )
    if err == "not_found":
        return jsonify({"error": "not found"}), 404
    if err == "forbidden":
        return jsonify({"error": "forbidden"}), 403
    if err == "invalid_status":
        return jsonify({"error": "status must be one of: active, blocked, completed, abandoned"}), 400
    if err == "invalid_transition":
        return jsonify({"error": "invalid transition"}), 409
    return jsonify(updated), 200
