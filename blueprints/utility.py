import os

from flask import Blueprint, current_app, jsonify

from db_operations import get_memory_usefulness_metrics
from db_utils import get_db

bp = Blueprint("utility", __name__)

_VERSION = "0.1.0"


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": _VERSION}), 200


@bp.route("/version", methods=["GET"])
def version():
    return jsonify({"version": _VERSION}), 200


@bp.route("/metrics/memory-usefulness", methods=["GET"])
def memory_usefulness_metrics():
    db = get_db()
    return jsonify(get_memory_usefulness_metrics(db)), 200


@bp.route("/graph", methods=["GET"])
def graph():
    static_folder = current_app.static_folder or os.path.join(
        os.path.dirname(__file__), "..", "static"
    )
    index_path = os.path.join(static_folder, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as f:
            content = f.read()
        return content, 200, {"Content-Type": "text/html; charset=utf-8"}
    stub = "<!DOCTYPE html><html><head><title>Memory Graph</title></head><body><p>Memory Graph</p></body></html>"
    return stub, 200, {"Content-Type": "text/html; charset=utf-8"}
