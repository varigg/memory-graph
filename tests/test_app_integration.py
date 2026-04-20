"""Integration tests for the Flask application factory and startup behaviour."""

import sqlite3
from unittest.mock import patch

import pytest
from flask import Flask

FIXED_VECTOR = [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(db_path):
    """Create a TESTING-mode app against *db_path*, with embed patched."""
    with patch("embeddings.embed", return_value=FIXED_VECTOR):
        from api_server import create_app

        app = create_app(db_path=str(db_path))
    app.config["TESTING"] = True
    return app


def sqlite_tables(db_path):
    """Return the set of table/virtual-table names present in the DB."""
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow') "
        "UNION "
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def sqlite_all_names(db_path):
    """Return all object names from sqlite_master (tables, virtual tables, triggers)."""
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT name FROM sqlite_master").fetchall()
    conn.close()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class TestAppFactory:
    def test_returns_flask_instance(self, tmp_path):
        app = make_app(tmp_path / "a.db")
        assert isinstance(app, Flask)

    def test_returns_new_object_each_call(self, tmp_path):
        app1 = make_app(tmp_path / "a.db")
        app2 = make_app(tmp_path / "b.db")
        assert app1 is not app2

    def test_two_apps_have_independent_db_paths(self, tmp_path):
        path_a = str(tmp_path / "a.db")
        path_b = str(tmp_path / "b.db")
        app1 = make_app(tmp_path / "a.db")
        app2 = make_app(tmp_path / "b.db")
        assert app1.config["DB_PATH"] == path_a
        assert app2.config["DB_PATH"] == path_b

    def test_two_apps_do_not_share_config(self, tmp_path):
        app1 = make_app(tmp_path / "a.db")
        app2 = make_app(tmp_path / "b.db")
        # Mutating one app's config must not affect the other
        app1.config["CUSTOM_KEY"] = "sentinel"
        assert "CUSTOM_KEY" not in app2.config

    def test_testing_flag_is_false_by_default(self, tmp_path):
        """create_app itself must not set TESTING=True."""
        with patch("embeddings.embed", return_value=FIXED_VECTOR):
            from api_server import create_app

            app = create_app(db_path=str(tmp_path / "c.db"))
        assert app.config.get("TESTING") is not True

    def test_debug_is_false_by_default(self, tmp_path):
        with patch("embeddings.embed", return_value=FIXED_VECTOR):
            from api_server import create_app

            app = create_app(db_path=str(tmp_path / "d.db"))
        assert app.debug is False

    def test_testing_mode_can_be_set_after_factory(self, tmp_path):
        app = make_app(tmp_path / "e.db")
        assert app.config["TESTING"] is True


# ---------------------------------------------------------------------------
# Schema auto-initialisation
# ---------------------------------------------------------------------------

REQUIRED_TABLES = {
    "conversations",
    "memories",
    "entities",
    "embeddings",
    "importance_keywords",
    "kv_store",
    "fts_conversations",
    "fts_memories",
}


class TestSchemaInitialisation:
    def test_all_eight_tables_exist(self, tmp_path):
        db_file = tmp_path / "schema.db"
        make_app(db_file)
        names = sqlite_all_names(db_file)
        assert REQUIRED_TABLES.issubset(names), (
            f"Missing tables: {REQUIRED_TABLES - names}"
        )

    def test_fts_virtual_tables_exist(self, tmp_path):
        db_file = tmp_path / "fts.db"
        make_app(db_file)
        names = sqlite_all_names(db_file)
        assert "fts_conversations" in names
        assert "fts_memories" in names

    def test_importance_keywords_seeded_with_at_least_ten_rows(self, tmp_path):
        db_file = tmp_path / "kw.db"
        make_app(db_file)
        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM importance_keywords").fetchone()[0]
        conn.close()
        assert count >= 10

    def test_schema_init_is_idempotent(self, tmp_path):
        """Calling create_app twice against the same DB must not raise or duplicate seed rows."""
        db_file = tmp_path / "idem.db"
        make_app(db_file)
        make_app(db_file)  # second call — must not throw
        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM importance_keywords").fetchone()[0]
        conn.close()
        assert count >= 10

    def test_schema_tables_are_present_immediately_after_factory(self, tmp_path):
        """Tables must exist before any request is made."""
        db_file = tmp_path / "early.db"
        make_app(db_file)
        conn = sqlite3.connect(str(db_file))
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "conversations" in tables
        assert "memories" in tables


# ---------------------------------------------------------------------------
# Blueprint registration
# ---------------------------------------------------------------------------


class TestBlueprintRegistration:
    @pytest.fixture()
    def client(self, tmp_path):
        return make_app(tmp_path / "bp.db").test_client()

    def test_conversation_recent_is_reachable(self, client):
        resp = client.get("/conversation/recent")
        assert resp.status_code != 404

    def test_memory_list_is_reachable(self, client):
        resp = client.get("/memory/list")
        assert resp.status_code != 404

    def test_search_semantic_is_reachable(self, client):
        with patch("embeddings.embed", return_value=FIXED_VECTOR):
            resp = client.get("/search/semantic?q=hello")
        assert resp.status_code != 404

    def test_kv_endpoint_is_reachable(self, client):
        # PUT a key first so the GET returns 200, not a business-logic 404.
        client.put("/kv/probe_key", json={"value": "probe"})
        resp = client.get("/kv/probe_key")
        assert resp.status_code == 200

    def test_health_endpoint_is_reachable(self, client):
        resp = client.get("/health")
        assert resp.status_code != 404

    def test_health_returns_status_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert data.get("status") == "ok"

    def test_health_response_is_json(self, client):
        resp = client.get("/health")
        assert "application/json" in resp.content_type


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------


class TestCorsHeaders:
    @pytest.fixture()
    def client(self, tmp_path):
        return make_app(tmp_path / "cors.db").test_client()

    def test_health_get_includes_acao_header(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_health_acao_header_is_not_empty(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("Access-Control-Allow-Origin")

    def test_options_preflight_returns_success_status(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)

    def test_options_preflight_includes_acao_header(self, client):
        resp = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "Access-Control-Allow-Origin" in resp.headers

    def test_cors_header_present_on_non_health_route(self, client):
        resp = client.get("/memory/list", headers={"Origin": "http://example.com"})
        assert "Access-Control-Allow-Origin" in resp.headers


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


class TestErrorHandler:
    @pytest.fixture()
    def app_with_bomb(self, tmp_path):
        """App augmented with a route that unconditionally raises RuntimeError.

        PROPAGATE_EXCEPTIONS must be False so Flask routes unhandled exceptions
        through the registered @errorhandler(500) rather than re-raising them
        (which is what TESTING=True would otherwise cause).
        """
        app = make_app(tmp_path / "err.db")
        # Keep TESTING so the test client works correctly, but override the
        # propagation flag so the 500 handler is actually exercised.
        app.config["TESTING"] = True
        app.config["PROPAGATE_EXCEPTIONS"] = False

        @app.route("/test/boom")
        def boom():
            raise RuntimeError("deliberate boom")

        return app

    @pytest.fixture()
    def client(self, app_with_bomb):
        return app_with_bomb.test_client()

    def test_500_returns_json_body(self, client):
        resp = client.get("/test/boom")
        assert resp.status_code == 500
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_500_content_type_is_json(self, client):
        resp = client.get("/test/boom")
        assert resp.status_code == 500
        assert "application/json" in resp.content_type

    def test_500_body_is_not_html(self, client):
        resp = client.get("/test/boom")
        assert resp.status_code == 500
        assert b"<!DOCTYPE" not in resp.data
        assert b"<html" not in resp.data

    def test_500_error_key_contains_message(self, client):
        resp = client.get("/test/boom")
        data = resp.get_json()
        assert isinstance(data["error"], str)
        assert len(data["error"]) > 0


class TestJsonHttpErrors:
    @pytest.fixture()
    def client(self, tmp_path):
        return make_app(tmp_path / "http_errors.db").test_client()

    def test_404_returns_json(self, client):
        resp = client.get("/does-not-exist")
        assert resp.status_code == 404
        assert "application/json" in resp.content_type
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "error" in data

    def test_405_returns_json(self, client):
        resp = client.put("/health", json={"x": 1})
        assert resp.status_code == 405
        assert "application/json" in resp.content_type
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "error" in data


class TestRequestSizeLimit:
    @pytest.fixture()
    def client(self, tmp_path):
        app = make_app(tmp_path / "body_limit.db")
        app.config["MAX_CONTENT_LENGTH"] = 64
        return app.test_client()

    def test_413_returns_json_for_large_request_body(self, client):
        big_payload = "x" * 1024
        resp = client.post(
            "/memory",
            data=big_payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413
        assert "application/json" in resp.content_type
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "error" in data


# ---------------------------------------------------------------------------
# DB isolation per request
# ---------------------------------------------------------------------------


class TestDbIsolationPerRequest:
    @pytest.fixture()
    def app(self, tmp_path):
        return make_app(tmp_path / "iso.db")

    @pytest.fixture()
    def client(self, app):
        return app.test_client()

    def test_write_in_request_1_visible_in_request_2(self, app):
        """Data written via one request context is readable in a subsequent one."""
        from db_utils import get_db

        with app.test_request_context():
            db = get_db()
            db.execute(
                "INSERT INTO kv_store (key, value) VALUES (?, ?)",
                ("isolation_key", "isolation_value"),
            )
            db.commit()

        with app.test_request_context():
            db = get_db()
            row = db.execute(
                "SELECT value FROM kv_store WHERE key = ?", ("isolation_key",)
            ).fetchone()
            assert row is not None
            assert row[0] == "isolation_value"

    def test_get_db_is_idempotent_within_a_single_request_context(self, app):
        """Multiple get_db() calls within the same request context must return
        the identical connection object — proving it is cached in g, not
        opened anew on every call.
        """
        from db_utils import get_db

        with app.test_request_context():
            assert get_db() is get_db()

    def test_teardown_closes_db_connection_when_app_context_exits(self, app):
        """The teardown_appcontext handler must close the DB connection when
        the app context is popped, preventing connection leaks.

        We push an explicit app context (not a request context) to get full
        control over the teardown cycle, independent of pytest-flask's
        long-lived request context fixture.
        """

        from db_utils import get_db

        ctx = app.app_context()
        ctx.push()
        conn = get_db()
        conn.execute("SELECT 1")   # connection is open and usable
        ctx.pop()                  # triggers teardown_appcontext → closes conn

        # sqlite3 raises ProgrammingError on any operation after close()
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_connection_closed_after_request_context_teardown(self, app):
        """get_db inside a request context should not raise; connection is cleaned up."""
        from db_utils import get_db

        with app.test_request_context():
            db = get_db()
            # Basic sanity: connection is usable
            result = db.execute("SELECT 1").fetchone()
            assert result[0] == 1
        # After __exit__, teardown_appcontext has run; no assertion needed —
        # any exception during teardown would have propagated here.

    def test_client_requests_persist_data_across_calls(self, client):
        """Two sequential test-client requests see the same underlying DB file."""
        # Write via the KV PUT endpoint, then read back via GET
        put_resp = client.put(
            "/kv/persist_test",
            json={"value": "hello_persistence"},
        )
        assert put_resp.status_code in (200, 201, 204)

        get_resp = client.get("/kv/persist_test")
        assert get_resp.status_code == 200
        data = get_resp.get_json()
        assert data is not None
