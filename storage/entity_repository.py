import sqlite3


def insert_entity(
    db: sqlite3.Connection,
    name: str,
    type_: str,
    details: str,
    tags: str = "",
) -> int:
    cur = db.execute(
        "INSERT INTO entities (name, type, details, tags) VALUES (?, ?, ?, ?)",
        (name, type_, details, tags),
    )
    db.commit()
    return cur.lastrowid


def search_entities(db: sqlite3.Connection, query: str, limit: int, offset: int) -> list:
    escaped = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    rows = db.execute(
        "SELECT id, name, type, details, tags FROM entities"
        " WHERE name LIKE ? ESCAPE '\\'"
        " OR type LIKE ? ESCAPE '\\'"
        " OR details LIKE ? ESCAPE '\\'"
        " OR tags LIKE ? ESCAPE '\\'"
        " ORDER BY id DESC LIMIT ? OFFSET ?",
        (pattern, pattern, pattern, pattern, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]
