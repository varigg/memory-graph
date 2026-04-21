import sqlite3


def get_memory_usefulness_metrics(db: sqlite3.Connection) -> dict:
    counts = db.execute(
        "SELECT "
        "COUNT(*) AS total_memories, "
        "SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_memories, "
        "SUM(CASE WHEN status = 'archived' THEN 1 ELSE 0 END) AS archived_memories, "
        "SUM(CASE WHEN status = 'invalidated' THEN 1 ELSE 0 END) AS invalidated_memories, "
        "SUM(CASE WHEN status = 'active' AND visibility = 'shared' THEN 1 ELSE 0 END) AS shared_active_memories, "
        "SUM(CASE WHEN status = 'active' AND visibility = 'private' THEN 1 ELSE 0 END) AS private_active_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS run_tracked_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(idempotency_key, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS idempotent_memories, "
        "SUM(CASE WHEN NULLIF(TRIM(COALESCE(tags, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS tagged_memories, "
        "SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS verified_memories, "
        "SUM(CASE WHEN verification_status = 'disputed' THEN 1 ELSE 0 END) AS disputed_memories, "
        "SUM(CASE WHEN verification_status IN ('verified', 'disputed') THEN 1 ELSE 0 END) AS reviewed_memories "
        "FROM memories"
    ).fetchone()

    def _value(key):
        value = counts[key]
        return int(value or 0)

    total_memories = _value("total_memories")

    def _pct(value):
        if total_memories == 0:
            return 0.0
        return round((value / total_memories) * 100.0, 2)

    run_tracked_memories = _value("run_tracked_memories")
    idempotent_memories = _value("idempotent_memories")
    tagged_memories = _value("tagged_memories")
    verified_memories = _value("verified_memories")
    disputed_memories = _value("disputed_memories")
    reviewed_memories = _value("reviewed_memories")

    run_stats = db.execute(
        "SELECT "
        "COUNT(DISTINCT run_id) AS distinct_runs, "
        "SUM(CASE WHEN status = 'active' AND NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL THEN 1 ELSE 0 END) AS active_run_tracked_memories "
        "FROM memories "
        "WHERE NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL"
    ).fetchone()

    freshness = db.execute(
        "SELECT "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) <= 1 THEN 1 ELSE 0 END) AS updated_last_24h, "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) <= 7 THEN 1 ELSE 0 END) AS updated_last_7d, "
        "SUM(CASE WHEN julianday('now') - julianday(COALESCE(updated_at, timestamp)) > 7 THEN 1 ELSE 0 END) AS updated_older_than_7d "
        "FROM memories"
    ).fetchone()

    top_runs_rows = db.execute(
        "SELECT run_id, COUNT(*) AS memory_count "
        "FROM memories "
        "WHERE NULLIF(TRIM(COALESCE(run_id, '')), '') IS NOT NULL "
        "GROUP BY run_id "
        "ORDER BY memory_count DESC, run_id ASC "
        "LIMIT 5"
    ).fetchall()

    run_tracked_active_memories = int((run_stats["active_run_tracked_memories"] or 0))

    return {
        "memory_counts": {
            "total": total_memories,
            "active": _value("active_memories"),
            "archived": _value("archived_memories"),
            "invalidated": _value("invalidated_memories"),
            "shared_active": _value("shared_active_memories"),
            "private_active": _value("private_active_memories"),
        },
        "adoption_signals": {
            "run_tracked": run_tracked_memories,
            "idempotent": idempotent_memories,
            "tagged": tagged_memories,
        },
        "trust_signals": {
            "verified": verified_memories,
            "disputed": disputed_memories,
            "reviewed": reviewed_memories,
        },
        "run_signals": {
            "distinct_runs": int((run_stats["distinct_runs"] or 0)),
            "active_run_tracked": run_tracked_active_memories,
            "top_runs": [
                {"run_id": r["run_id"], "memory_count": int(r["memory_count"])}
                for r in top_runs_rows
            ],
        },
        "freshness_signals": {
            "updated_last_24h": int((freshness["updated_last_24h"] or 0)),
            "updated_last_7d": int((freshness["updated_last_7d"] or 0)),
            "updated_older_than_7d": int((freshness["updated_older_than_7d"] or 0)),
        },
        "coverage_pct": {
            "run_tracked": _pct(run_tracked_memories),
            "run_tracked_active": _pct(run_tracked_active_memories),
            "idempotent": _pct(idempotent_memories),
            "tagged": _pct(tagged_memories),
            "reviewed": _pct(reviewed_memories),
            "verified": _pct(verified_memories),
        },
    }
