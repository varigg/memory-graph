from __future__ import annotations

import sqlite3
from typing import Any

from storage.metrics_repository import get_embedding_dedupe_signals


def _default_retrieval_bucket() -> dict[str, int]:
    return {
        "calls": 0,
        "results_total": 0,
        "zero_result_calls": 0,
    }


def ensure_ops_signals(app) -> dict[str, Any]:
    existing = app.config.get("OPS_SIGNALS")
    if not isinstance(existing, dict):
        existing = {}

    default_signals = {
        "retrieval": {
            "memory_list": _default_retrieval_bucket(),
            "memory_recall": _default_retrieval_bucket(),
            "memory_search": _default_retrieval_bucket(),
            "semantic_search": _default_retrieval_bucket(),
            "hybrid_search": _default_retrieval_bucket(),
        },
        "db_lock_events": {
            "total": 0,
            "by_operation": {},
        },
        "reindex_runs": 0,
        "reindex_rows_total": 0,
        "reindex_deduped_rows_total": 0,
    }

    signals = {
        "retrieval": existing.get("retrieval", default_signals["retrieval"]),
        "db_lock_events": existing.get("db_lock_events", default_signals["db_lock_events"]),
        "reindex_runs": existing.get("reindex_runs", 0),
        "reindex_rows_total": existing.get("reindex_rows_total", 0),
        "reindex_deduped_rows_total": existing.get("reindex_deduped_rows_total", 0),
    }

    # Ensure required retrieval buckets exist even for partially initialized config.
    for key in default_signals["retrieval"]:
        if key not in signals["retrieval"] or not isinstance(signals["retrieval"][key], dict):
            signals["retrieval"][key] = _default_retrieval_bucket()

    if not isinstance(signals["db_lock_events"], dict):
        signals["db_lock_events"] = {"total": 0, "by_operation": {}}
    signals["db_lock_events"].setdefault("total", 0)
    signals["db_lock_events"].setdefault("by_operation", {})

    app.config["OPS_SIGNALS"] = signals
    return signals


def record_retrieval_observation(app, operation: str, result_count: int) -> None:
    signals = ensure_ops_signals(app)
    retrieval = signals["retrieval"]
    if operation not in retrieval:
        retrieval[operation] = _default_retrieval_bucket()

    bucket = retrieval[operation]
    bucket["calls"] += 1
    bucket["results_total"] += max(int(result_count), 0)
    if int(result_count) == 0:
        bucket["zero_result_calls"] += 1


def record_db_lock_event(app, operation: str) -> None:
    signals = ensure_ops_signals(app)
    lock_events = signals["db_lock_events"]
    lock_events["total"] += 1
    by_operation = lock_events["by_operation"]
    by_operation[operation] = int(by_operation.get(operation, 0)) + 1


def record_reindex_observation(
    app,
    reindexed_rows: int,
    deduped_rows: int,
) -> None:
    signals = ensure_ops_signals(app)
    signals["reindex_runs"] += 1
    signals["reindex_rows_total"] += max(int(reindexed_rows), 0)
    signals["reindex_deduped_rows_total"] += max(int(deduped_rows), 0)


def _avg_results(calls: int, results_total: int) -> float:
    if calls <= 0:
        return 0.0
    return round(float(results_total) / float(calls), 3)


def build_ops_signals_snapshot(app, db: sqlite3.Connection) -> dict[str, Any]:
    signals = ensure_ops_signals(app)

    retrieval_signals = {}
    for operation, bucket in signals["retrieval"].items():
        calls = int(bucket["calls"])
        results_total = int(bucket["results_total"])
        zero_result_calls = int(bucket["zero_result_calls"])
        retrieval_signals[operation] = {
            "calls": calls,
            "results_total": results_total,
            "zero_result_calls": zero_result_calls,
            "avg_results": _avg_results(calls, results_total),
        }

    return {
        "retrieval_result_signals": retrieval_signals,
        "db_lock_signals": {
            "total": int(signals["db_lock_events"]["total"]),
            "by_operation": {
                key: int(value)
                for key, value in signals["db_lock_events"]["by_operation"].items()
            },
        },
        "dedupe_signals": {
            "reindex_runs": int(signals["reindex_runs"]),
            "reindex_rows_total": int(signals["reindex_rows_total"]),
            "reindex_deduped_rows_total": int(signals["reindex_deduped_rows_total"]),
            **get_embedding_dedupe_signals(db),
        },
    }