from flask import Blueprint, jsonify, request

from db_operations import get_kv, upsert_kv
from db_utils import get_db

bp = Blueprint("kv", __name__)


@bp.route("/<key>", methods=["GET"])
def get_key(key):
    db = get_db()
    value = get_kv(db, key)
    if value is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"key": key, "value": value}), 200


@bp.route("/<key>", methods=["PUT"])
def put_key(key):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "JSON body required"}), 400
    if "value" not in data:
        return jsonify({"error": "value key required"}), 400
    db = get_db()
    upsert_kv(db, key, data["value"])
    return jsonify({"key": key}), 200
