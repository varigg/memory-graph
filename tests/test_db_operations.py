"""Tests for db_operations.py — SQLite helpers."""
import json
import math
import sqlite3

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    """Return an initialised sqlite3 connection in a temp directory."""
    import db_schema  # noqa: PLC0415
    db_path = str(tmp_path / "ops_test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# upsert_kv / get_kv
# ---------------------------------------------------------------------------

class TestUpsertAndGetKv:
    def test_upsert_kv_inserts_new_key(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "mykey", {"hello": "world"})
        result = ops.get_kv(db, "mykey")
        assert result == {"hello": "world"}

    def test_upsert_kv_updates_existing_key(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "counter", 1)
        ops.upsert_kv(db, "counter", 2)
        result = ops.get_kv(db, "counter")
        assert result == 2

    def test_upsert_kv_stores_list(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "items", [1, 2, 3])
        result = ops.get_kv(db, "items")
        assert result == [1, 2, 3]

    def test_upsert_kv_stores_string(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "greeting", "hello")
        result = ops.get_kv(db, "greeting")
        assert result == "hello"

    def test_upsert_kv_stores_nested_dict(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "nested", {"a": {"b": 42}})
        result = ops.get_kv(db, "nested")
        assert result == {"a": {"b": 42}}

    def test_get_kv_returns_none_for_missing_key(self, db):
        import db_operations as ops  # noqa: PLC0415
        result = ops.get_kv(db, "does_not_exist")
        assert result is None

    def test_get_kv_different_keys_do_not_interfere(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.upsert_kv(db, "k1", "val1")
        ops.upsert_kv(db, "k2", "val2")
        assert ops.get_kv(db, "k1") == "val1"
        assert ops.get_kv(db, "k2") == "val2"


# ---------------------------------------------------------------------------
# fts_search_conversations
# ---------------------------------------------------------------------------

class TestFtsSearchConversations:
    def _insert_conv(self, db, content, role="user", channel="test"):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_conversation(db, role, content, channel, importance=0.5, embedding_id=None)

    def test_returns_matching_rows(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_conv(db, "The deployment pipeline failed today")
        results = ops.fts_search_conversations(db, "deployment")
        assert len(results) >= 1

    def test_returns_empty_list_when_no_match(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_conv(db, "Hello world")
        results = ops.fts_search_conversations(db, "xyzzy_not_a_word_42")
        assert results == []

    def test_returns_only_matching_rows(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_conv(db, "Python is great")
        self._insert_conv(db, "Rust is fast")
        results = ops.fts_search_conversations(db, "Python")
        contents = [r["content"] if isinstance(r, dict) else r[0] for r in results]
        assert any("Python" in str(c) for c in contents)

    def test_returns_list_type(self, db):
        import db_operations as ops  # noqa: PLC0415
        results = ops.fts_search_conversations(db, "anything")
        assert isinstance(results, list)

    def test_multiple_matches_returned(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_conv(db, "notes from Monday")
        self._insert_conv(db, "notes from Tuesday")
        results = ops.fts_search_conversations(db, "notes")
        assert len(results) >= 2


# ---------------------------------------------------------------------------
# fts_search_memories
# ---------------------------------------------------------------------------

class TestFtsSearchMemories:
    def _insert_mem(self, db, name, content, description=""):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_memory(db, name, "note", content, description, confidence=0.9)

    def test_returns_matching_rows(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_mem(db, "auth_flow", "JWT token lifecycle notes")
        results = ops.fts_search_memories(db, "JWT")
        assert len(results) >= 1

    def test_returns_empty_list_when_no_match(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_mem(db, "irrelevant", "some content here")
        results = ops.fts_search_memories(db, "xyzzy_not_a_word_42")
        assert results == []

    def test_returns_list_type(self, db):
        import db_operations as ops  # noqa: PLC0415
        results = ops.fts_search_memories(db, "anything")
        assert isinstance(results, list)

    def test_multiple_memories_returned(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_mem(db, "m1", "project planning notes")
        self._insert_mem(db, "m2", "project retrospective notes")
        results = ops.fts_search_memories(db, "project")
        assert len(results) >= 2

    def test_match_by_name_field(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._insert_mem(db, "deployment_runbook", "steps to release")
        results = ops.fts_search_memories(db, "deployment_runbook")
        assert len(results) >= 1


class TestFtsSyncOnMutation:
    def test_conversation_update_refreshes_fts_index(self, db):
        import db_operations as ops  # noqa: PLC0415

        conv_id = ops.insert_conversation(db, "user", "oldtoken", "test", 0.1, None)
        db.execute("UPDATE conversations SET content=? WHERE id=?", ("newtoken", conv_id))
        db.commit()

        assert len(ops.fts_search_conversations(db, "oldtoken")) == 0
        assert len(ops.fts_search_conversations(db, "newtoken")) >= 1

    def test_conversation_delete_removes_fts_row(self, db):
        import db_operations as ops  # noqa: PLC0415

        conv_id = ops.insert_conversation(db, "user", "deletetoken", "test", 0.1, None)
        db.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        db.commit()

        assert len(ops.fts_search_conversations(db, "deletetoken")) == 0

    def test_memory_update_refreshes_fts_index(self, db):
        import db_operations as ops  # noqa: PLC0415

        mem_id = ops.insert_memory(db, "m1", "note", "oldmemorytoken", "", 0.9)
        db.execute("UPDATE memories SET content=? WHERE id=?", ("newmemorytoken", mem_id))
        db.commit()

        assert len(ops.fts_search_memories(db, "oldmemorytoken")) == 0
        assert len(ops.fts_search_memories(db, "newmemorytoken")) >= 1

    def test_memory_delete_removes_fts_row(self, db):
        import db_operations as ops  # noqa: PLC0415

        mem_id = ops.insert_memory(db, "m2", "note", "removememorytoken", "", 0.9)
        db.execute("DELETE FROM memories WHERE id=?", (mem_id,))
        db.commit()

        assert len(ops.fts_search_memories(db, "removememorytoken")) == 0

    def test_conversation_update_to_null_content_keeps_fts_valid(self, db):
        import db_operations as ops  # noqa: PLC0415

        conv_id = ops.insert_conversation(db, "user", "nulltoken", "test", 0.1, None)
        db.execute("UPDATE conversations SET content=NULL WHERE id=?", (conv_id,))
        db.commit()

        assert len(ops.fts_search_conversations(db, "nulltoken")) == 0
        assert len(ops.fts_search_conversations(db, "user")) >= 1

    def test_memory_update_to_null_content_keeps_fts_valid(self, db):
        import db_operations as ops  # noqa: PLC0415

        mem_id = ops.insert_memory(db, "nullmem", "note", "nullmemtoken", "desc", 0.9)
        db.execute("UPDATE memories SET content=NULL WHERE id=?", (mem_id,))
        db.commit()

        assert len(ops.fts_search_memories(db, "nullmemtoken")) == 0
        assert len(ops.fts_search_memories(db, "nullmem")) >= 1


# ---------------------------------------------------------------------------
# insert_conversation
# ---------------------------------------------------------------------------

class TestInsertConversation:
    def test_returns_rowid(self, db):
        import db_operations as ops  # noqa: PLC0415
        rowid = ops.insert_conversation(db, "user", "Hello", "general", 0.5, None)
        assert rowid is not None
        assert isinstance(rowid, int)

    def test_row_exists_after_insert(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_conversation(db, "assistant", "Hi there", "general", 0.3, None)
        row = db.execute("SELECT role, content FROM conversations WHERE role='assistant'").fetchone()
        assert row is not None

    def test_rowid_increments_for_multiple_inserts(self, db):
        import db_operations as ops  # noqa: PLC0415
        id1 = ops.insert_conversation(db, "user", "First", "ch1", 0.1, None)
        id2 = ops.insert_conversation(db, "user", "Second", "ch1", 0.1, None)
        assert id2 > id1

    def test_content_persisted_correctly(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_conversation(db, "user", "Unique content abc123", "chan", 0.5, None)
        row = db.execute(
            "SELECT content FROM conversations WHERE content='Unique content abc123'"
        ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# insert_memory
# ---------------------------------------------------------------------------

class TestInsertMemory:
    def test_returns_rowid(self, db):
        import db_operations as ops  # noqa: PLC0415
        rowid = ops.insert_memory(db, "test_mem", "fact", "content", "desc", 0.8)
        assert rowid is not None
        assert isinstance(rowid, int)

    def test_row_exists_after_insert(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_memory(db, "unique_mem_xyz", "fact", "content here", "desc", 0.7)
        row = db.execute("SELECT name FROM memories WHERE name='unique_mem_xyz'").fetchone()
        assert row is not None

    def test_rowid_increments(self, db):
        import db_operations as ops  # noqa: PLC0415
        id1 = ops.insert_memory(db, "m1", "fact", "c1", "d1", 0.5)
        id2 = ops.insert_memory(db, "m2", "fact", "c2", "d2", 0.5)
        assert id2 > id1

    def test_confidence_persisted(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_memory(db, "conf_test", "note", "body", "desc", 0.95)
        row = db.execute(
            "SELECT confidence FROM memories WHERE name='conf_test'"
        ).fetchone()
        assert row is not None
        assert abs(row[0] - 0.95) < 1e-6


# ---------------------------------------------------------------------------
# insert_entity
# ---------------------------------------------------------------------------

class TestInsertEntity:
    def test_returns_rowid(self, db):
        import db_operations as ops  # noqa: PLC0415
        rowid = ops.insert_entity(db, "Alice", "person", "Engineer", "python,backend")
        assert rowid is not None
        assert isinstance(rowid, int)

    def test_row_exists_after_insert(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_entity(db, "UniqueEntityZZZ", "service", "details", "")
        row = db.execute(
            "SELECT name FROM entities WHERE name='UniqueEntityZZZ'"
        ).fetchone()
        assert row is not None

    def test_tags_persisted(self, db):
        import db_operations as ops  # noqa: PLC0415
        ops.insert_entity(db, "TagEntity", "concept", "details", "flask,sqlite")
        row = db.execute(
            "SELECT tags FROM entities WHERE name='TagEntity'"
        ).fetchone()
        assert row is not None
        assert "flask" in str(row[0])

    def test_rowid_increments(self, db):
        import db_operations as ops  # noqa: PLC0415
        id1 = ops.insert_entity(db, "E1", "t", "d", "")
        id2 = ops.insert_entity(db, "E2", "t", "d", "")
        assert id2 > id1


# ---------------------------------------------------------------------------
# insert_embedding
# ---------------------------------------------------------------------------

class TestInsertEmbedding:
    def test_returns_id(self, db):
        import db_operations as ops  # noqa: PLC0415
        eid = ops.insert_embedding(db, "hello", [0.1, 0.2, 0.3], "text-embedding-3-small")
        assert eid is not None
        assert isinstance(eid, int)

    def test_row_exists_after_insert(self, db):
        import db_operations as ops  # noqa: PLC0415
        eid = ops.insert_embedding(db, "test text", [1.0, 0.0], "model-v1")
        row = db.execute("SELECT id FROM embeddings WHERE id=?", (eid,)).fetchone()
        assert row is not None

    def test_id_increments(self, db):
        import db_operations as ops  # noqa: PLC0415
        id1 = ops.insert_embedding(db, "text1", [0.1], "m1")
        id2 = ops.insert_embedding(db, "text2", [0.2], "m1")
        assert id2 > id1

    def test_vector_persisted_as_json(self, db):
        import db_operations as ops  # noqa: PLC0415
        vector = [0.5, 0.25, 0.75]
        eid = ops.insert_embedding(db, "vec_text", vector, "m1")
        row = db.execute("SELECT vector FROM embeddings WHERE id=?", (eid,)).fetchone()
        assert row is not None
        stored = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert stored == pytest.approx(vector)


# ---------------------------------------------------------------------------
# compute_importance
# ---------------------------------------------------------------------------

class TestComputeImportance:
    def test_returns_float(self, db):
        import db_operations as ops  # noqa: PLC0415
        score = ops.compute_importance(db, "some text here")
        assert isinstance(score, float)

    def test_text_with_notes_keyword_scores_at_or_above_1_0(self, db):
        import db_operations as ops  # noqa: PLC0415
        score = ops.compute_importance(db, "These are my important notes for today")
        assert score >= 1.0

    def test_text_with_no_keywords_scores_0_0(self, db):
        import db_operations as ops  # noqa: PLC0415
        score = ops.compute_importance(db, "zzz qqq aaa bbb ccc")
        assert score == pytest.approx(0.0)

    def test_score_is_non_negative(self, db):
        import db_operations as ops  # noqa: PLC0415
        score = ops.compute_importance(db, "random text")
        assert score >= 0.0

    def test_project_keyword_increases_score(self, db):
        import db_operations as ops  # noqa: PLC0415
        baseline = ops.compute_importance(db, "zzz qqq aaa bbb ccc")
        with_kw = ops.compute_importance(db, "project kickoff zzz qqq aaa")
        assert with_kw > baseline

    def test_score_is_capped(self, db):
        """A single keyword match should not produce an unbounded score."""
        import db_operations as ops  # noqa: PLC0415
        score = ops.compute_importance(
            db, "notes notes notes notes notes notes notes"
        )
        assert score <= 1.0  # reasonable upper bound; implementation may cap at 1.0


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors_return_1_0(self):
        import db_operations as ops  # noqa: PLC0415
        v = [0.3, 0.4, 0.5]
        assert ops.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_return_0_0(self):
        import db_operations as ops  # noqa: PLC0415
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        assert ops.cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors_return_minus_1_0(self):
        import db_operations as ops  # noqa: PLC0415
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert ops.cosine_similarity(v1, v2) == pytest.approx(-1.0, abs=1e-6)

    def test_result_is_float(self):
        import db_operations as ops  # noqa: PLC0415
        result = ops.cosine_similarity([1.0, 0.0], [0.5, 0.5])
        assert isinstance(result, float)

    def test_commutative(self):
        import db_operations as ops  # noqa: PLC0415
        v1 = [0.6, 0.8]
        v2 = [0.8, 0.6]
        assert ops.cosine_similarity(v1, v2) == pytest.approx(
            ops.cosine_similarity(v2, v1), abs=1e-9
        )

    def test_unit_vectors_at_45_degrees(self):
        import db_operations as ops  # noqa: PLC0415
        v1 = [1.0, 0.0]
        v2 = [math.sqrt(2) / 2, math.sqrt(2) / 2]
        assert ops.cosine_similarity(v1, v2) == pytest.approx(math.sqrt(2) / 2, abs=1e-6)

    def test_mismatched_dimensions_return_0_0(self):
        import db_operations as ops  # noqa: PLC0415
        assert ops.cosine_similarity([1.0, 0.0], [1.0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# semantic_search
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    def _seed_embeddings(self, db, vectors):
        import db_operations as ops  # noqa: PLC0415
        for i, vec in enumerate(vectors):
            ops.insert_embedding(db, f"text_{i}", vec, "test-model")

    def test_returns_at_most_top_k_results(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._seed_embeddings(db, [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.9, 0.1]])
        results = ops.semantic_search(db, [1.0, 0.0], top_k=2)
        assert len(results) <= 2

    def test_returns_list(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._seed_embeddings(db, [[1.0, 0.0]])
        results = ops.semantic_search(db, [1.0, 0.0], top_k=5)
        assert isinstance(results, list)

    def test_most_similar_vector_ranked_first(self, db):
        import db_operations as ops  # noqa: PLC0415

        # Insert two vectors; the one closer to query should rank first.
        ops.insert_embedding(db, "close", [1.0, 0.0], "m")
        ops.insert_embedding(db, "far", [0.0, 1.0], "m")
        results = ops.semantic_search(db, [1.0, 0.0], top_k=2)
        assert len(results) >= 1
        first_text = results[0]["text"] if isinstance(results[0], dict) else results[0][1]
        assert first_text == "close"

    def test_empty_db_returns_empty_list(self, db):
        import db_operations as ops  # noqa: PLC0415
        results = ops.semantic_search(db, [1.0, 0.0], top_k=5)
        assert results == []

    def test_top_k_zero_returns_empty_list(self, db):
        import db_operations as ops  # noqa: PLC0415
        self._seed_embeddings(db, [[1.0, 0.0], [0.0, 1.0]])
        results = ops.semantic_search(db, [1.0, 0.0], top_k=0)
        assert results == []

    def test_skips_malformed_vector_rows(self, db):
        import db_operations as ops  # noqa: PLC0415

        db.execute(
            "INSERT INTO embeddings (text, vector, model_version) VALUES (?, ?, ?)",
            ("bad", "not-json", "m"),
        )
        db.commit()
        self._seed_embeddings(db, [[1.0, 0.0]])

        results = ops.semantic_search(db, [1.0, 0.0], top_k=5)
        assert any(r["text"] == "text_0" for r in results)


# ---------------------------------------------------------------------------
# Visibility/ownership scoping (Phase 3A PR-3)
# ---------------------------------------------------------------------------

class TestMemoryVisibilityScoping:
    def test_list_memories_scoped_default_includes_shared_and_own_private(self, db):
        import db_operations as ops  # noqa: PLC0415

        # Create shared and private memories
        ops.insert_memory(
            db, "shared", "note", "shared-content", "", visibility="shared", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "private-alpha", "note", "private-alpha-content", "", visibility="private", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "private-beta", "note", "private-beta-content", "", visibility="private", owner_agent_id="agent-beta"
        )

        # List as agent-alpha with default scope
        results = ops.list_memories_scoped(db, "agent-alpha", limit=100)
        names = {r["name"] for r in results}
        assert "shared" in names
        assert "private-alpha" in names
        assert "private-beta" not in names

    def test_list_memories_scoped_shared_only(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(db, "shared", "note", "content", "", visibility="shared", owner_agent_id="agent-alpha")
        ops.insert_memory(db, "private", "note", "content", "", visibility="private", owner_agent_id="agent-alpha")

        results = ops.list_memories_scoped(db, "agent-alpha", limit=100, shared_only=True)
        names = {r["name"] for r in results}
        assert "shared" in names
        assert "private" not in names

    def test_list_memories_scoped_private_only(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(db, "shared", "note", "content", "", visibility="shared", owner_agent_id="agent-alpha")
        ops.insert_memory(db, "private", "note", "content", "", visibility="private", owner_agent_id="agent-alpha")

        results = ops.list_memories_scoped(db, "agent-alpha", limit=100, private_only=True)
        names = {r["name"] for r in results}
        assert "private" in names
        assert "shared" not in names

    def test_fts_search_memories_scoped(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(
            db, "shared-search", "note", "deployment token", "", visibility="shared", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "private-search", "note", "deployment marker", "", visibility="private", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "private-beta", "note", "deployment secret", "", visibility="private", owner_agent_id="agent-beta"
        )

        # Search as agent-alpha should find shared + own private
        results = ops.fts_search_memories_scoped(db, '"deployment"', "agent-alpha", limit=100)
        names = {r["name"] for r in results}
        assert "shared-search" in names or "private-search" in names
        assert "private-beta" not in names

    def test_scope_predicate_rejects_conflicting_flags(self, db):
        import db_operations as ops  # noqa: PLC0415

        with pytest.raises(ValueError, match="Cannot combine"):
            ops._build_scope_predicate("agent-alpha", shared_only=True, private_only=True)

    def test_list_memories_scoped_accepts_visibility_and_owner_filters(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(
            db, "shared-alpha", "note", "x", "", visibility="shared", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "shared-beta", "note", "x", "", visibility="shared", owner_agent_id="agent-beta"
        )
        ops.insert_memory(
            db, "private-alpha", "note", "x", "", visibility="private", owner_agent_id="agent-alpha"
        )

        results = ops.list_memories_scoped(
            db,
            "agent-alpha",
            limit=100,
            visibility="shared",
            owner_agent_id="agent-beta",
        )
        names = {r["name"] for r in results}
        assert names == {"shared-beta"}

    def test_fts_search_memories_unscoped_accepts_owner_filter(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(
            db, "alpha", "note", "owner-token", "", visibility="shared", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "beta", "note", "owner-token", "", visibility="shared", owner_agent_id="agent-beta"
        )

        results = ops.fts_search_memories(
            db,
            '"owner-token"',
            limit=100,
            owner_agent_id="agent-alpha",
        )
        names = {r["name"] for r in results}
        assert names == {"alpha"}

    def test_default_status_filter_excludes_archived(self, db):
        import db_operations as ops  # noqa: PLC0415

        mem_id = ops.insert_memory(
            db,
            "archived-default-hidden",
            "note",
            "status-token",
            "",
            visibility="shared",
            owner_agent_id="agent-alpha",
        )
        db.execute(
            "UPDATE memories SET status = 'archived', status_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (mem_id,),
        )
        db.commit()

        list_results = ops.list_memories_scoped(db, "agent-alpha", limit=100)
        list_names = {r["name"] for r in list_results}
        assert "archived-default-hidden" not in list_names

        search_results = ops.fts_search_memories_scoped(db, '"status-token"', "agent-alpha", limit=100)
        search_names = {r["name"] for r in search_results}
        assert "archived-default-hidden" not in search_names

    def test_transition_memory_status_validates_owner_and_transitions(self, db):
        import db_operations as ops  # noqa: PLC0415

        mem_id = ops.insert_memory(
            db,
            "lifecycle",
            "note",
            "transition-token",
            "",
            visibility="private",
            owner_agent_id="agent-alpha",
        )

        transitioned, err = ops.transition_memory_status(db, mem_id, "agent-beta", "archived")
        assert transitioned is None
        assert err == "forbidden"

        transitioned, err = ops.transition_memory_status(db, mem_id, "agent-alpha", "invalidated")
        assert err is None
        assert transitioned["status"] == "invalidated"

        transitioned, err = ops.transition_memory_status(db, mem_id, "agent-alpha", "archived")
        assert transitioned is None
        assert err == "invalid_transition"

    def test_list_memories_scoped_orders_shared_before_private(self, db):
        import db_operations as ops  # noqa: PLC0415

        ops.insert_memory(
            db, "private-first", "note", "ranking", "", confidence=0.9,
            visibility="private", owner_agent_id="agent-alpha"
        )
        ops.insert_memory(
            db, "shared-second", "note", "ranking", "", confidence=0.1,
            visibility="shared", owner_agent_id="agent-alpha"
        )

        results = ops.list_memories_scoped(db, "agent-alpha", limit=100)
        names = [r["name"] for r in results]
        assert names[:2] == ["shared-second", "private-first"]

    def test_fts_search_memories_scoped_orders_by_confidence_then_recency(self, db):
        import db_operations as ops  # noqa: PLC0415

        older_id = ops.insert_memory(
            db, "older-high", "note", "rank-token", "", confidence=0.9,
            visibility="shared", owner_agent_id="agent-alpha"
        )
        newer_low_id = ops.insert_memory(
            db, "newer-low", "note", "rank-token", "", confidence=0.5,
            visibility="shared", owner_agent_id="agent-alpha"
        )
        newer_high_id = ops.insert_memory(
            db, "newer-high", "note", "rank-token", "", confidence=0.9,
            visibility="shared", owner_agent_id="agent-alpha"
        )

        db.execute(
            "UPDATE memories SET updated_at = '2024-01-01 00:00:00' WHERE id = ?",
            (older_id,),
        )
        db.execute(
            "UPDATE memories SET updated_at = '2024-01-03 00:00:00' WHERE id = ?",
            (newer_low_id,),
        )
        db.execute(
            "UPDATE memories SET updated_at = '2024-01-04 00:00:00' WHERE id = ?",
            (newer_high_id,),
        )
        db.commit()

        results = ops.fts_search_memories_scoped(db, '"rank-token"', "agent-alpha", limit=100)
        names = [r["name"] for r in results]
        assert names[:3] == ["newer-high", "older-high", "newer-low"]
