import sqlite3


def insert_conversation(
    db: sqlite3.Connection,
    role: str,
    content: str,
    channel: str,
    importance: float = 0.0,
    embedding_id=None,
) -> int:
    cur = db.execute(
        "INSERT INTO conversations (role, content, channel, importance, embedding_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (role, content, channel, importance, embedding_id),
    )
    db.commit()
    return cur.lastrowid


def fts_search_conversations(
    db: sqlite3.Connection, query: str, limit: int = 20, offset: int = 0
) -> list:
    rows = db.execute(
        "SELECT content, role, channel, conversation_id"
        " FROM fts_conversations WHERE fts_conversations MATCH ?"
        " LIMIT ? OFFSET ?",
        (query, limit, offset),
    ).fetchall()
    return [
        {"content": r[0], "role": r[1], "channel": r[2], "conversation_id": r[3]}
        for r in rows
    ]


def compute_importance(db: sqlite3.Connection, text: str) -> float:
    lower_text = text.lower()
    keywords = db.execute("SELECT keyword, score FROM importance_keywords").fetchall()
    total = 0.0
    for row in keywords:
        keyword = row[0]
        score = row[1]
        if keyword in lower_text:
            total += score
    return min(total, 1.0)
