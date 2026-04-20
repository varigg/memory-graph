import sqlite3

_SEED_KEYWORDS = [
    ("notes", 1.0),
    ("project", 0.8),
    ("deploy", 0.8),
    ("bug", 0.7),
    ("feature", 0.7),
    ("release", 0.9),
    ("error", 0.6),
    ("warning", 0.5),
    ("todo", 0.6),
    ("fix", 0.5),
]

_DDL = """
CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY,
    role         TEXT,
    content      TEXT,
    channel      TEXT,
    timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP,
    importance   REAL DEFAULT 0.0,
    embedding_id INTEGER
);

CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY,
    name        TEXT,
    type        TEXT,
    content     TEXT,
    description TEXT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence  REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY,
    name       TEXT,
    type       TEXT,
    details    TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    tags       TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
    id            INTEGER PRIMARY KEY,
    text          TEXT,
    vector        TEXT,
    model_version TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS importance_keywords (
    id         INTEGER PRIMARY KEY,
    keyword    TEXT UNIQUE,
    score      REAL,
    hit_count  INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS kv_store (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_conversations
    USING fts5(content, role, channel, conversation_id UNINDEXED);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_memories
    USING fts5(name, content, description, memory_id UNINDEXED);

CREATE TRIGGER IF NOT EXISTS trg_fts_conversations_insert
AFTER INSERT ON conversations
BEGIN
    INSERT INTO fts_conversations(content, role, channel, conversation_id)
    VALUES (COALESCE(NEW.content, ''), COALESCE(NEW.role, ''), COALESCE(NEW.channel, ''), NEW.id);
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_conversations_update
AFTER UPDATE ON conversations
BEGIN
    DELETE FROM fts_conversations WHERE conversation_id = OLD.id;
    INSERT INTO fts_conversations(content, role, channel, conversation_id)
    VALUES (COALESCE(NEW.content, ''), COALESCE(NEW.role, ''), COALESCE(NEW.channel, ''), NEW.id);
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_conversations_delete
AFTER DELETE ON conversations
BEGIN
    DELETE FROM fts_conversations WHERE conversation_id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_memories_insert
AFTER INSERT ON memories
BEGIN
    INSERT INTO fts_memories(name, content, description, memory_id)
    VALUES (COALESCE(NEW.name, ''), COALESCE(NEW.content, ''), COALESCE(NEW.description, ''), NEW.id);
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_memories_update
AFTER UPDATE ON memories
BEGIN
    DELETE FROM fts_memories WHERE memory_id = OLD.id;
    INSERT INTO fts_memories(name, content, description, memory_id)
    VALUES (COALESCE(NEW.name, ''), COALESCE(NEW.content, ''), COALESCE(NEW.description, ''), NEW.id);
END;

CREATE TRIGGER IF NOT EXISTS trg_fts_memories_delete
AFTER DELETE ON memories
BEGIN
    DELETE FROM fts_memories WHERE memory_id = OLD.id;
END;
"""


def _dedupe_embeddings_by_text(conn: sqlite3.Connection) -> None:
    duplicate_texts = conn.execute(
        "SELECT text, MIN(id) AS keep_id FROM embeddings "
        "WHERE text IS NOT NULL "
        "GROUP BY text HAVING COUNT(*) > 1"
    ).fetchall()

    for text, keep_id in duplicate_texts:
        dup_rows = conn.execute(
            "SELECT id FROM embeddings WHERE text = ? AND id != ?",
            (text, keep_id),
        ).fetchall()
        dup_ids = [row[0] for row in dup_rows]
        if not dup_ids:
            continue

        placeholders = ",".join("?" * len(dup_ids))
        conn.execute(
            f"UPDATE conversations SET embedding_id = ? WHERE embedding_id IN ({placeholders})",
            (keep_id, *dup_ids),
        )
        conn.execute(
            f"DELETE FROM embeddings WHERE id IN ({placeholders})",
            dup_ids,
        )


def _get_table_columns(conn: sqlite3.Connection, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _ensure_memories_scope_columns(conn: sqlite3.Connection) -> None:
    cols = _get_table_columns(conn, "memories")

    if "owner_agent_id" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN owner_agent_id TEXT NOT NULL DEFAULT 'unknown'"
        )

    if "visibility" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN visibility TEXT NOT NULL DEFAULT 'shared' "
            "CHECK (visibility IN ('shared', 'private'))"
        )

    if "updated_at" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN updated_at DATETIME"
        )

    conn.execute(
        "UPDATE memories "
        "SET owner_agent_id = COALESCE(NULLIF(TRIM(owner_agent_id), ''), 'unknown')"
    )
    conn.execute(
        "UPDATE memories "
        "SET visibility = CASE WHEN visibility IN ('shared', 'private') THEN visibility ELSE 'shared' END"
    )
    conn.execute(
        "UPDATE memories "
        "SET updated_at = COALESCE(updated_at, timestamp, CURRENT_TIMESTAMP)"
    )


def init(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(_DDL)
    _ensure_memories_scope_columns(conn)
    _dedupe_embeddings_by_text(conn)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_text_unique "
        "ON embeddings(text)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_visibility_owner "
        "ON memories(visibility, owner_agent_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_updated_at "
        "ON memories(updated_at)"
    )
    conn.executemany(
        "INSERT OR IGNORE INTO importance_keywords (keyword, score) VALUES (?, ?)",
        _SEED_KEYWORDS,
    )
    conn.commit()
    conn.close()
