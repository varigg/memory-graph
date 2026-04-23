"""Tests for db_schema.py — table creation and seeding."""
import sqlite3

import pytest


def _get_table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {r[0] for r in rows}


def _get_column_names(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _get_trigger_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name"
    ).fetchall()
    return {r[0] for r in rows}


def _get_index_names(conn, table):
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    return {r[1] for r in rows}


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

class TestInitCreatesAllTables:
    EXPECTED_TABLES = {
        "conversations",
        "memories",
        "entities",
        "embeddings",
        "goals",
        "goal_status_history",
        "action_logs",
        "autonomy_checkpoints",
        "importance_keywords",
        "fts_conversations",
        "fts_memories",
        "kv_store",
    }

    def test_all_expected_tables_exist_after_init(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        tables = _get_table_names(conn)
        conn.close()
        assert self.EXPECTED_TABLES.issubset(tables)


class TestFtsTriggers:
    EXPECTED_TRIGGERS = {
        "trg_fts_conversations_insert",
        "trg_fts_conversations_update",
        "trg_fts_conversations_delete",
        "trg_fts_memories_insert",
        "trg_fts_memories_update",
        "trg_fts_memories_delete",
    }

    def test_fts_triggers_exist(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "triggers.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        triggers = _get_trigger_names(conn)
        conn.close()
        assert self.EXPECTED_TRIGGERS.issubset(triggers)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestInitIdempotency:
    def test_double_init_does_not_raise(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        db_schema.init(db_path)  # must not raise

    def test_tables_still_present_after_double_init(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        tables = _get_table_names(conn)
        conn.close()
        assert "conversations" in tables
        assert "memories" in tables

    def test_seed_data_not_duplicated_on_double_init(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        count_after_first = conn.execute(
            "SELECT COUNT(*) FROM importance_keywords WHERE keyword='notes'"
        ).fetchone()[0]
        conn.close()
        assert count_after_first == 1


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

class TestImportanceKeywordsSeed:
    def test_importance_keywords_has_at_least_10_rows(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM importance_keywords").fetchone()[0]
        conn.close()
        assert count >= 10

    def test_notes_keyword_has_score_1_0(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT score FROM importance_keywords WHERE keyword='notes'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == pytest.approx(1.0)

    def test_project_keyword_has_score_0_8(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT score FROM importance_keywords WHERE keyword='project'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == pytest.approx(0.8)

    def test_deploy_keyword_exists(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT keyword FROM importance_keywords WHERE keyword='deploy'"
        ).fetchone()
        conn.close()
        assert row is not None


# ---------------------------------------------------------------------------
# conversations columns
# ---------------------------------------------------------------------------

class TestConversationsColumns:
    EXPECTED = {"role", "content", "channel", "timestamp", "importance", "embedding_id"}

    def test_conversations_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "conversations")
        conn.close()
        assert self.EXPECTED.issubset(cols)

    def test_conversations_has_role_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "conversations")
        conn.close()
        assert "role" in cols

    def test_conversations_has_embedding_id_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "conversations")
        conn.close()
        assert "embedding_id" in cols


# ---------------------------------------------------------------------------
# memories columns
# ---------------------------------------------------------------------------

class TestMemoriesColumns:
    EXPECTED = {
        "name",
        "type",
        "content",
        "description",
        "timestamp",
        "confidence",
        "tags",
        "run_id",
        "idempotency_key",
        "metadata_json",
        "owner_agent_id",
        "visibility",
        "updated_at",
        "verification_status",
        "verification_source",
        "verified_at",
    }

    def test_memories_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert self.EXPECTED.issubset(cols)

    def test_memories_has_confidence_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert "confidence" in cols

    def test_memories_has_type_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert "type" in cols

    def test_memories_has_owner_agent_id_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert "owner_agent_id" in cols

    def test_memories_has_visibility_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert "visibility" in cols

    def test_memories_has_updated_at_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "memories")
        conn.close()
        assert "updated_at" in cols


# ---------------------------------------------------------------------------
# entities columns
# ---------------------------------------------------------------------------

class TestEntitiesColumns:
    EXPECTED = {"name", "type", "details", "created_at", "tags"}

    def test_entities_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "entities")
        conn.close()
        assert self.EXPECTED.issubset(cols)

    def test_entities_has_tags_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "entities")
        conn.close()
        assert "tags" in cols

    def test_entities_has_created_at_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "entities")
        conn.close()
        assert "created_at" in cols


# ---------------------------------------------------------------------------
# embeddings columns
# ---------------------------------------------------------------------------

class TestEmbeddingsColumns:
    EXPECTED = {"id", "text", "vector", "model_version", "created_at"}

    def test_embeddings_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "embeddings")
        conn.close()
        assert self.EXPECTED.issubset(cols)

    def test_embeddings_has_vector_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "embeddings")
        conn.close()
        assert "vector" in cols

    def test_embeddings_has_model_version_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "embeddings")
        conn.close()
        assert "model_version" in cols


# ---------------------------------------------------------------------------
# goals columns
# ---------------------------------------------------------------------------

class TestGoalsColumns:
    EXPECTED = {
        "title",
        "status",
        "utility",
        "deadline",
        "constraints_json",
        "success_criteria_json",
        "risk_tier",
        "autonomy_level_requested",
        "autonomy_level_effective",
        "owner_agent_id",
        "run_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    }

    def test_goals_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "goals")
        conn.close()
        assert self.EXPECTED.issubset(cols)


class TestGoalStatusHistoryColumns:
    EXPECTED = {
        "goal_id",
        "old_status",
        "new_status",
        "changed_by_agent_id",
        "reason",
        "created_at",
    }

    def test_goal_status_history_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "goal_status_history")
        conn.close()
        assert self.EXPECTED.issubset(cols)


# ---------------------------------------------------------------------------
# action_logs columns
# ---------------------------------------------------------------------------

class TestActionLogsColumns:
    EXPECTED = {
        "goal_id",
        "parent_action_id",
        "action_type",
        "tool_name",
        "mode",
        "status",
        "input_summary",
        "expected_result",
        "observed_result",
        "rollback_action_id",
        "owner_agent_id",
        "run_id",
        "idempotency_key",
        "created_at",
        "completed_at",
    }

    def test_action_logs_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "action_logs")
        conn.close()
        assert self.EXPECTED.issubset(cols)


class TestAutonomyCheckpointColumns:
    EXPECTED = {
        "goal_id",
        "action_id",
        "requested_level",
        "approved_level",
        "verdict",
        "rationale",
        "stop_conditions_json",
        "rollback_required",
        "reviewer_type",
        "owner_agent_id",
        "run_id",
        "idempotency_key",
        "created_at",
    }

    def test_autonomy_checkpoints_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "autonomy_checkpoints")
        conn.close()
        assert self.EXPECTED.issubset(cols)


# ---------------------------------------------------------------------------
# kv_store columns
# ---------------------------------------------------------------------------

class TestKvStoreColumns:
    EXPECTED = {"key", "value", "updated_at"}

    def test_kv_store_has_all_required_columns(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "kv_store")
        conn.close()
        assert self.EXPECTED.issubset(cols)

    def test_kv_store_has_key_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "kv_store")
        conn.close()
        assert "key" in cols

    def test_kv_store_has_updated_at_column(self, tmp_path):
        import db_schema  # noqa: PLC0415
        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        cols = _get_column_names(conn, "kv_store")
        conn.close()
        assert "updated_at" in cols


# ---------------------------------------------------------------------------
# embeddings uniqueness / migration safety
# ---------------------------------------------------------------------------

class TestEmbeddingsTextUniqueness:
    def test_embeddings_text_unique_index_exists(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        indexes = _get_index_names(conn, "embeddings")
        conn.close()
        assert "idx_embeddings_text_unique" in indexes

    def test_init_dedupes_legacy_duplicate_embeddings_and_repairs_refs(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)

        conn = sqlite3.connect(db_path)
        conn.execute("DROP INDEX IF EXISTS idx_embeddings_text_unique")
        conn.execute(
            "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
            ("same", "[0.1, 0.2]", "m"),
        )
        emb1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
            ("same", "[0.1, 0.2]", "m"),
        )
        emb2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "INSERT INTO conversations (role, content, channel, embedding_id) VALUES (?, ?, ?, ?)",
            ("user", "c1", "t", emb1),
        )
        conn.execute(
            "INSERT INTO conversations (role, content, channel, embedding_id) VALUES (?, ?, ?, ?)",
            ("user", "c2", "t", emb2),
        )
        conn.commit()
        conn.close()

        # Re-run init over legacy data: should dedupe and recreate uniqueness guard.
        db_schema.init(db_path)

        conn = sqlite3.connect(db_path)
        emb_count = conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE text = ?",
            ("same",),
        ).fetchone()[0]
        conv_refs = conn.execute(
            "SELECT DISTINCT embedding_id FROM conversations ORDER BY embedding_id"
        ).fetchall()
        indexes = _get_index_names(conn, "embeddings")
        conn.close()

        assert emb_count == 1
        assert len(conv_refs) == 1
        assert "idx_embeddings_text_unique" in indexes


# ---------------------------------------------------------------------------
# memories scope migration safety
# ---------------------------------------------------------------------------

class TestMemoriesScopeMigration:
    def test_scope_indexes_exist_after_init(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)
        conn = sqlite3.connect(db_path)
        indexes = _get_index_names(conn, "memories")
        conn.close()

        assert "idx_memories_visibility_owner" in indexes
        assert "idx_memories_updated_at" in indexes

    def test_init_backfills_scope_defaults_on_legacy_rows(self, tmp_path):
        import db_schema  # noqa: PLC0415

        db_path = str(tmp_path / "test.db")
        db_schema.init(db_path)

        conn = sqlite3.connect(db_path)
        conn.execute("DROP INDEX IF EXISTS idx_memories_visibility_owner")
        conn.execute("DROP INDEX IF EXISTS idx_memories_updated_at")

        conn.execute(
            "CREATE TABLE memories_legacy ("
            "id INTEGER PRIMARY KEY, "
            "name TEXT, "
            "type TEXT, "
            "content TEXT, "
            "description TEXT, "
            "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "confidence REAL DEFAULT 1.0"
            ")"
        )
        conn.execute(
            "INSERT INTO memories_legacy (id, name, type, content, description, timestamp, confidence) "
            "SELECT id, name, type, content, description, timestamp, confidence FROM memories"
        )
        conn.execute("DROP TABLE memories")
        conn.execute("ALTER TABLE memories_legacy RENAME TO memories")

        conn.execute(
            "INSERT INTO memories (name, type, content, description) VALUES (?, ?, ?, ?)",
            ("legacy", "note", "legacy-content", ""),
        )
        conn.commit()
        conn.close()

        db_schema.init(db_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT owner_agent_id, visibility, updated_at FROM memories WHERE name = ?",
            ("legacy",),
        ).fetchone()
        indexes = _get_index_names(conn, "memories")
        conn.close()

        assert row is not None
        assert row[0] == "unknown"
        assert row[1] == "shared"
        assert row[2] is not None
        assert "idx_memories_visibility_owner" in indexes
        assert "idx_memories_updated_at" in indexes
