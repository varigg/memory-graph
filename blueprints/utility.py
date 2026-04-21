import os
import sqlite3

from flask import Blueprint, current_app, jsonify, request

from db_utils import get_db
from services.ops_metrics_service import build_ops_signals_snapshot
from storage.metrics_repository import (
    get_integrity_report,
    get_memory_usefulness_metrics,
)

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


@bp.route("/metrics/ops", methods=["GET"])
def ops_metrics():
    """Return per-route request counts, error counts, and latency summaries."""
    raw = current_app.config.get("OPS_COUNTERS", {})
    routes = []
    for route_key, c in sorted(raw.items()):
        n = c["requests"]
        avg_ms = round(c["total_latency_ms"] / n, 3) if n > 0 else 0.0
        routes.append(
            {
                "route": route_key,
                "requests": n,
                "errors": c["errors"],
                "avg_latency_ms": avg_ms,
                "total_latency_ms": round(c["total_latency_ms"], 3),
            }
        )
    db = get_db()
    signals = build_ops_signals_snapshot(current_app, db)
    return jsonify({"routes": routes, "signals": signals}), 200


@bp.route("/maintenance/integrity", methods=["GET"])
def maintenance_integrity():
    sample_limit_raw = request.args.get("sample_limit", "10")
    try:
        sample_limit = int(sample_limit_raw)
    except ValueError:
        return jsonify({"error": "sample_limit must be an integer"}), 400
    if sample_limit <= 0:
        return jsonify({"error": "sample_limit must be > 0"}), 400

    db = get_db()
    return jsonify(get_integrity_report(db, sample_limit=sample_limit)), 200


@bp.route("/maintenance/sqlite", methods=["POST"])
def maintenance_sqlite():
    data = request.get_json(silent=True) or {}

    dry_run = data.get("dry_run", True)
    if not isinstance(dry_run, bool):
        return jsonify({"error": "dry_run must be a boolean when provided"}), 400

    checkpoint_mode = data.get("checkpoint_mode", "PASSIVE")
    if not isinstance(checkpoint_mode, str):
        return jsonify({"error": "checkpoint_mode must be a string when provided"}), 400
    normalized_checkpoint_mode = checkpoint_mode.strip().upper()
    if normalized_checkpoint_mode not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
        return jsonify({"error": "checkpoint_mode must be one of PASSIVE, FULL, RESTART, TRUNCATE"}), 400

    planned_actions = [
        "PRAGMA optimize",
        f"PRAGMA wal_checkpoint({normalized_checkpoint_mode})",
    ]
    if dry_run:
        return jsonify({
            "dry_run": True,
            "planned_actions": planned_actions,
        }), 200

    db = get_db()
    try:
        optimize_rows = db.execute("PRAGMA optimize").fetchall()
        checkpoint_row = db.execute(
            f"PRAGMA wal_checkpoint({normalized_checkpoint_mode})"
        ).fetchone()
    except sqlite3.Error as exc:
        return jsonify({"error": "sqlite maintenance failed", "detail": str(exc)}), 500

    checkpoint = {
        "busy": int(checkpoint_row[0]) if checkpoint_row is not None else 0,
        "log_frames": int(checkpoint_row[1]) if checkpoint_row is not None else 0,
        "checkpointed_frames": int(checkpoint_row[2]) if checkpoint_row is not None else 0,
    }
    return jsonify(
        {
            "dry_run": False,
            "actions": planned_actions,
            "optimize_result_rows": len(optimize_rows),
            "checkpoint": checkpoint,
        }
    ), 200


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
