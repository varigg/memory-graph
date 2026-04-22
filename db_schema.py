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
    confidence  REAL DEFAULT 1.0,
    tags        TEXT DEFAULT '',
    run_id      TEXT,
    idempotency_key TEXT,
    metadata_json TEXT DEFAULT '{}',
    verification_status TEXT DEFAULT 'unverified' CHECK (verification_status IN ('unverified', 'verified', 'disputed')),
    verification_source TEXT,
    verified_at DATETIME
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

CREATE TABLE IF NOT EXISTS memory_relations (
    id               INTEGER PRIMARY KEY,
    source_memory_id INTEGER NOT NULL,
    target_memory_id INTEGER NOT NULL,
    relation_type    TEXT NOT NULL CHECK (relation_type IN ('merged_into', 'superseded_by')),
    actor_agent_id   TEXT NOT NULL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_memory_id, target_memory_id, relation_type),
    FOREIGN KEY(source_memory_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY(target_memory_id) REFERENCES memories(id) ON DELETE CASCADE
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

    if "status" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN status TEXT NOT NULL DEFAULT 'active' "
            "CHECK (status IN ('active', 'archived', 'invalidated'))"
        )

    if "status_updated_at" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN status_updated_at DATETIME"
        )

    if "tags" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN tags TEXT DEFAULT ''"
        )

    if "run_id" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN run_id TEXT"
        )

    if "idempotency_key" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN idempotency_key TEXT"
        )

    if "metadata_json" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN metadata_json TEXT DEFAULT '{}'"
        )

    if "verification_status" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN verification_status TEXT DEFAULT 'unverified'"
        )

    if "verification_source" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN verification_source TEXT"
        )

    if "verified_at" not in cols:
        conn.execute(
            "ALTER TABLE memories "
            "ADD COLUMN verified_at DATETIME"
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
    conn.execute(
        "UPDATE memories "
        "SET status = CASE "
        "WHEN status IN ('active', 'archived', 'invalidated') THEN status "
        "ELSE 'active' END"
    )
    conn.execute(
        "UPDATE memories "
        "SET status_updated_at = COALESCE(status_updated_at, updated_at, timestamp, CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "UPDATE memories "
        "SET tags = COALESCE(tags, '')"
    )
    conn.execute(
        "UPDATE memories "
        "SET verification_status = CASE "
        "WHEN verification_status IN ('unverified', 'verified', 'disputed') THEN verification_status "
        "ELSE 'unverified' END"
    )
    conn.execute(
        "UPDATE memories "
        "SET metadata_json = CASE "
        "WHEN metadata_json IS NULL OR TRIM(metadata_json) = '' THEN '{}' "
        "WHEN json_valid(metadata_json) = 1 THEN metadata_json "
        "ELSE '{}' END"
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_status "
        "ON memories(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_status_updated_at "
        "ON memories(status_updated_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_run_id "
        "ON memories(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_confidence "
        "ON memories(confidence)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_owner_idempotency "
        "ON memories(owner_agent_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_source "
        "ON memory_relations(source_memory_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_relations_target "
        "ON memory_relations(target_memory_id)"
    )
    conn.executemany(
        "INSERT OR IGNORE INTO importance_keywords (keyword, score) VALUES (?, ?)",
        _SEED_KEYWORDS,
    )
    conn.commit()
    conn.close()
