# Phase 1d — App Integration Review

## 1. `create_app()` Factory Pattern

`api_server.create_app()` follows the Flask application factory idiom: each call constructs and returns a fully configured `Flask` instance rather than relying on a module-level singleton. The factory accepts an optional `db_path` argument, falling back to `Config.DB_PATH` when absent. This single parameter is the mechanism through which the test suite achieves complete database isolation: every test fixture calls `create_app(db_path=":memory:")` (or a per-test temporary file), obtaining an application whose SQLite connection is entirely independent of any other test or of the production database.

The benefits of the factory pattern over a module-level `app = Flask(__name__)` are:

- **Testability.** Multiple app instances can coexist in the same process with different configurations. `pytest-flask` can request a new app per test class by passing a fresh `db_path`, preventing cross-test state contamination.
- **DB isolation.** Because `db_schema.init(db_path)` is called inside the factory, each app instance owns its own schema. Tests that populate data in one app can never observe rows created by another.
- **Import-time safety.** Blueprint routes are registered inside the factory via deferred imports, so importing `api_server` at the module level does not trigger side effects (no `db_schema.init` call, no filesystem access) unless `create_app()` is explicitly called.

The factory exposes `get_db` in its `__all__` for convenience, though callers typically import it directly from `db_utils`.

---

## 2. `get_db()` and the Flask `g` Pattern

`db_utils.get_db()` follows the standard Flask request-scoped resource pattern:

```python
def get_db():
    from flask import current_app
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db
```

`flask.g` is a namespace object whose lifetime is bounded by the active application context — in practice, a single HTTP request in a production deployment. The first call to `get_db()` within a request opens a `sqlite3.Connection` and caches it on `g`. Subsequent calls within the same request return the cached connection, ensuring at most one open connection per request and avoiding the overhead of repeated `sqlite3.connect()` calls. The `teardown_appcontext` hook registered in `create_app()` closes the connection when the application context is torn down:

```python
@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
```

`sqlite3.Row` is set as the row factory so that rows support both integer-index access and dictionary-style column-name access. Blueprint code uses `dict(r)` to serialize rows directly to JSON without manual column mapping.

The `current_app` import inside the function body (rather than at module level) is intentional: importing `current_app` at module load time outside an application context raises a `RuntimeError`. The deferred import ensures the function is safe to import in any context.

---

## 3. Blueprint Registration and URL Prefix Layout

Five blueprints are registered in `create_app()` with the following URL prefix assignments:

| Blueprint          | Module                        | Prefix          |
| ------------------ | ----------------------------- | --------------- |
| `conversations_bp` | `blueprints/conversations.py` | `/conversation` |
| `memory_bp`        | `blueprints/memory.py`        | _(none)_        |
| `search_bp`        | `blueprints/search.py`        | _(none)_        |
| `kv_bp`            | `blueprints/kv.py`            | `/kv`           |
| `utility_bp`       | `blueprints/utility.py`       | _(none)_        |

`memory_bp` and `search_bp` mount at the application root because their routes already carry descriptive path segments (`/memory`, `/entity`, `/search`, `/embeddings`). The absence of a prefix is an intentional design choice, not an oversight. `utility_bp` similarly mounts at root because `/health`, `/version`, and `/graph` require no additional namespace.

Blueprints are imported inside the factory body (deferred imports) to avoid circular import issues. Python resolves `from blueprints.conversations import bp` at call time rather than at module parse time; by then the application instance is fully constructed and there is no risk of importing blueprint modules before their dependencies are available.

---

## 4. CORS Configuration and Production Caveats

CORS is enabled with a single call:

```python
CORS(app)
```

`flask-cors` interprets this as `Access-Control-Allow-Origin: *` on all routes, with no restrictions on methods, headers, or exposed headers. For a service that binds to `0.0.0.0` and is accessed only from `localhost`, this is operationally safe in a development or personal-use deployment. In any environment where:

- the service is reachable from a network beyond `localhost`, or
- the API is extended to use session cookies or `Authorization` headers carrying credentials,

the wildcard policy becomes a credentialed cross-origin exfiltration risk. The Phase 2 remediation is to restrict to the actual consumer origin:

```python
CORS(app, origins=["http://localhost:7777"])
```

Preflight (`OPTIONS`) requests are handled automatically by `flask-cors`. The current setup returns `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers` populated from the request's `Access-Control-Request-*` headers, effectively reflecting all requested methods and headers back to the client — another behaviour that is permissive but acceptable for a local tool.

---

## 5. 500 Error Handler Behaviour

The factory registers a single JSON error handler:

```python
@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500
```

This ensures that unhandled exceptions in any route produce a machine-readable `{"error": "..."}` JSON body rather than Flask's default HTML traceback page. API clients that parse response bodies unconditionally will receive a consistently structured error.

The handler is registered for HTTP 500 only. Flask/Werkzeug generates HTML for 404, 405, and other framework-level errors unless handlers are registered for those codes as well. No `abort()` calls exist in the current codebase, so client-facing 4xx responses are all produced by explicit `return jsonify(...), <status>` statements in blueprint code — those are already JSON. The gap becomes material only if future routes use `abort()` or if the Werkzeug routing layer itself emits a 404 or 405.

---

## 6. Schema Auto-Initialization on Startup

`create_app()` calls `db_schema.init(db_path)` before registering blueprints or returning the application:

```python
db_schema.init(db_path)
app.config["DB_PATH"] = db_path
```

`db_schema.init()` opens its own `sqlite3.Connection` (separate from the request-scoped connection vended by `get_db()`), executes the DDL script via `executescript`, seeds `importance_keywords`, commits, and closes. Because every DDL statement uses `IF NOT EXISTS` and seed insertion uses `INSERT OR IGNORE`, the function is fully idempotent: calling it against an already-initialized database is a no-op with respect to data.

The practical consequence is that the database is guaranteed to be schema-complete before any request is handled. There is no startup race between the application accepting connections and the schema being ready. This also means tests using in-memory databases do not need to call `init()` themselves — the factory handles it.

---

## 7. Security Posture Summary

The following table consolidates security findings across Phase 1a, 1b, and 1c reviews, noting which were remediated in code and which remain deferred to Phase 2.

| ID       | Severity | Finding                                                                    | Status                                                                                                                  |
| -------- | -------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| —        | Medium   | Gemini API key passed as URL query parameter (`?key=`)                     | **Fixed** — moved to `x-goog-api-key` request header                                                                    |
| —        | Low      | No HTTP timeout on embedding API calls                                     | **Fixed** — `timeout=30` added to both `_embed_openai` and `_embed_gemini`                                              |
| —        | High     | `/embeddings/reindex` did not update `conversations.embedding_id`          | **Fixed** — `UPDATE conversations SET embedding_id = ?` now executed after insert                                       |
| —        | Low      | FTS user input not sanitized before MATCH binding                          | **Fixed** — double-quotes stripped from query strings in `conversations.search`, `search.hybrid`, and `search.semantic` |
| —        | Low      | Duplicate embeddings created on repeated `POST /conversation/log`          | **Fixed** — existence check against `embeddings.text` added before insert                                               |
| —        | Medium   | Wildcard CORS policy (`Access-Control-Allow-Origin: *`)                    | Deferred — acceptable for local use; restrict `origins` in Phase 2                                                      |
| —        | Medium   | Synchronous embedding HTTP call in request path (30s blocking risk)        | Deferred — background task queue planned for Phase 2                                                                    |
| —        | Low      | No request body size limit (`MAX_CONTENT_LENGTH` unset)                    | Deferred                                                                                                                |
| —        | Low      | 500 handler only; no JSON handlers for 404/405                             | Deferred                                                                                                                |
| SRI-001  | Medium   | D3 loaded from CDN without Subresource Integrity                           | Deferred                                                                                                                |
| CSP-001  | Medium   | No Content-Security-Policy header                                          | Deferred                                                                                                                |
| A11Y-001 | Low      | Tab bar lacks ARIA roles                                                   | Deferred                                                                                                                |
| —        | —        | FTS UPDATE/DELETE triggers absent (index desync on mutations)              | Deferred                                                                                                                |
| —        | —        | `Config.EMBEDDING_PROVIDER` evaluated at class definition (stale in tests) | Deferred                                                                                                                |
