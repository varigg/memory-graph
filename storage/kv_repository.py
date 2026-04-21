import json
import sqlite3


def upsert_kv(db: sqlite3.Connection, key: str, value) -> None:
    db.execute(
        "INSERT OR REPLACE INTO kv_store (key, value, updated_at)"
        " VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, json.dumps(value)),
    )
    db.commit()


def get_kv(db: sqlite3.Connection, key: str):
    row = db.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return json.loads(row[0])
