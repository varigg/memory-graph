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

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'completed', 'abandoned')),
    utility REAL NOT NULL DEFAULT 0,
    deadline TEXT,
    constraints_json TEXT NOT NULL DEFAULT '{}',
    success_criteria_json TEXT NOT NULL DEFAULT '{}',
    risk_tier TEXT NOT NULL DEFAULT 'low' CHECK (risk_tier IN ('low', 'medium', 'high', 'critical')),
    autonomy_level_requested INTEGER NOT NULL DEFAULT 0,
    autonomy_level_effective INTEGER NOT NULL DEFAULT 0,
    owner_agent_id TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_status_history (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL CHECK (new_status IN ('active', 'blocked', 'completed', 'abandoned')),
    changed_by_agent_id TEXT NOT NULL,
    reason TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER NOT NULL,
    parent_action_id INTEGER,
    action_type TEXT NOT NULL,
    tool_name TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('plan', 'dry_run', 'live', 'rollback')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'rolled_back')),
    input_summary TEXT,
    expected_result TEXT,
    observed_result TEXT,
    rollback_action_id INTEGER,
    owner_agent_id TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE,
    FOREIGN KEY(parent_action_id) REFERENCES action_logs(id) ON DELETE SET NULL,
    FOREIGN KEY(rollback_action_id) REFERENCES action_logs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS autonomy_checkpoints (
    id INTEGER PRIMARY KEY,
    goal_id INTEGER,
    action_id INTEGER,
    requested_level INTEGER NOT NULL,
    approved_level INTEGER NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('approved', 'denied', 'sandbox_only')),
    rationale TEXT,
    stop_conditions_json TEXT NOT NULL DEFAULT '{}',
    rollback_required INTEGER NOT NULL DEFAULT 0,
    reviewer_type TEXT NOT NULL DEFAULT 'system' CHECK (reviewer_type IN ('policy', 'human', 'system')),
    owner_agent_id TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE SET NULL,
    FOREIGN KEY(action_id) REFERENCES action_logs(id) ON DELETE SET NULL
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_goals_owner_status_updated "
        "ON goals(owner_agent_id, status, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_goals_run_created "
        "ON goals(run_id, created_at DESC)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_goals_owner_idempotency "
        "ON goals(owner_agent_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_goal_status_history_goal_created "
        "ON goal_status_history(goal_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_logs_goal_created "
        "ON action_logs(goal_id, created_at ASC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_logs_owner_run_created "
        "ON action_logs(owner_agent_id, run_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_logs_status_created "
        "ON action_logs(status, created_at DESC)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_action_logs_owner_idempotency "
        "ON action_logs(owner_agent_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_logs_parent "
        "ON action_logs(parent_action_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_logs_rollback "
        "ON action_logs(rollback_action_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_autonomy_owner_run_created "
        "ON autonomy_checkpoints(owner_agent_id, run_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_autonomy_goal_created "
        "ON autonomy_checkpoints(goal_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_autonomy_action_created "
        "ON autonomy_checkpoints(action_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_autonomy_verdict_created "
        "ON autonomy_checkpoints(verdict, created_at DESC)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_autonomy_owner_idempotency "
        "ON autonomy_checkpoints(owner_agent_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    conn.executemany(
        "INSERT OR IGNORE INTO importance_keywords (keyword, score) VALUES (?, ?)",
        _SEED_KEYWORDS,
    )
    conn.commit()
    conn.close()
