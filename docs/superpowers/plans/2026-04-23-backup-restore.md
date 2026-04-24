# Backup / Restore Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `GET /backup/info`, `GET /backup/export` (SQLite snapshot or SQL dump), and `POST /backup/import` (validate, back up current DB, swap in uploaded file).

**Architecture:** A single `blueprints/backup.py` handles all three routes. No new tables — the feature operates directly on the SQLite file at `app.config["DB_PATH"]`. Export streams via Flask `send_file` / `Response`. Import uses `tempfile` + `shutil.copy2` for an atomic-ish swap; pre-import backups are written as `<db_stem>.pre-import-<timestamp>.db` alongside the live file. No storage module needed.

**Tech Stack:** Flask (`send_file`, `Response`, `request.files`), Python `os`, `shutil`, `tempfile`, `sqlite3` (validation), `datetime`.

---

## Chunk 1: GET /backup/info and GET /backup/export

### Task 1: Blueprint skeleton + GET /backup/info

**Files:**
- Create: `blueprints/backup.py`
- Create: `tests/test_backup.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_backup.py`:

```python
"""Tests for GET /backup/info, GET /backup/export, POST /backup/import."""
import os
import sqlite3
import tempfile


def test_backup_info_returns_200(client):
    resp = client.get("/backup/info")
    assert resp.status_code == 200


def test_backup_info_has_required_fields(client):
    resp = client.get("/backup/info")
    data = resp.get_json()
    assert "db_path" in data
    assert "db_size_bytes" in data
    assert "last_modified" in data
    assert "pre_import_backups" in data
    assert "disk_free_bytes" in data


def test_backup_info_pre_import_backups_is_list(client):
    resp = client.get("/backup/info")
    data = resp.get_json()
    assert isinstance(data["pre_import_backups"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/varigg/code/memory-graph
uv run pytest tests/test_backup.py::test_backup_info_returns_200 \
              tests/test_backup.py::test_backup_info_has_required_fields \
              tests/test_backup.py::test_backup_info_pre_import_backups_is_list -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `blueprints/backup.py`**

```python
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, send_file

bp = Blueprint("backup", __name__)

_REQUIRED_TABLES = {"conversations", "memories", "importance_keywords"}


def _db_path() -> str:
    return current_app.config["DB_PATH"]


def _pre_import_backups(db_path: str) -> list:
    directory = os.path.dirname(os.path.abspath(db_path))
    stem = os.path.splitext(os.path.basename(db_path))[0]
    prefix = f"{stem}.pre-import-"
    entries = []
    for fname in os.listdir(directory):
        if fname.startswith(prefix) and fname.endswith(".db"):
            fpath = os.path.join(directory, fname)
            stat = os.stat(fpath)
            entries.append({
                "filename": fname,
                "size_bytes": stat.st_size,
                "modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
            })
    return sorted(entries, key=lambda e: e["filename"], reverse=True)


@bp.route("/backup/info", methods=["GET"])
def backup_info():
    db_path = _db_path()
    abs_path = os.path.abspath(db_path)
    stat = os.stat(abs_path)
    statvfs = os.statvfs(os.path.dirname(abs_path))
    return jsonify({
        "db_path": abs_path,
        "db_size_bytes": stat.st_size,
        "last_modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
        "pre_import_backups": _pre_import_backups(db_path),
        "disk_free_bytes": statvfs.f_bavail * statvfs.f_frsize,
    }), 200
```

- [ ] **Step 4: Register blueprint in `api_server.py`**

Add import:

```python
from blueprints.backup import bp as backup_bp
```

Add registration:

```python
app.register_blueprint(backup_bp)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_backup.py::test_backup_info_returns_200 \
              tests/test_backup.py::test_backup_info_has_required_fields \
              tests/test_backup.py::test_backup_info_pre_import_backups_is_list -v
```
Expected: All three PASS.

- [ ] **Step 6: Commit**

```bash
git add blueprints/backup.py api_server.py tests/test_backup.py
git commit -m "feat: add GET /backup/info endpoint"
```

---

### Task 2: GET /backup/export

**Files:**
- Modify: `blueprints/backup.py`
- Modify: `tests/test_backup.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_backup.py`:

```python
def test_export_returns_200(client):
    resp = client.get("/backup/export")
    assert resp.status_code == 200


def test_export_default_content_type_is_octet_stream(client):
    resp = client.get("/backup/export")
    assert "application/octet-stream" in resp.content_type or \
           "application/x-sqlite3" in resp.content_type


def test_export_content_disposition_is_attachment(client):
    resp = client.get("/backup/export")
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd


def test_export_dump_format_returns_sql_text(client):
    resp = client.get("/backup/export?format=dump")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8", errors="replace")
    assert "CREATE TABLE" in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_backup.py -k "export" -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Add export route to `blueprints/backup.py`**

```python
@bp.route("/backup/export", methods=["GET"])
def backup_export():
    fmt = request.args.get("format", "db").lower()
    db_path = _db_path()

    if fmt == "dump":
        conn = sqlite3.connect(db_path)
        lines = "\n".join(conn.iterdump())
        conn.close()
        return Response(
            lines,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=memory_dump.sql"},
        )

    # Binary snapshot via VACUUM INTO a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(f"VACUUM INTO '{tmp.name}'")
        conn.close()
        return send_file(
            tmp.name,
            as_attachment=True,
            download_name="memory_backup.db",
            mimetype="application/octet-stream",
        )
    except Exception:
        os.unlink(tmp.name)
        raise
```

- [ ] **Step 4: Run export tests**

```bash
uv run pytest tests/test_backup.py -k "export" -v
```
Expected: All four PASS.

- [ ] **Step 5: Commit**

```bash
git add blueprints/backup.py tests/test_backup.py
git commit -m "feat: add GET /backup/export (binary snapshot and SQL dump)"
```

---

## Chunk 2: POST /backup/import

### Task 3: Import endpoint

**Files:**
- Modify: `blueprints/backup.py`
- Modify: `tests/test_backup.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_backup.py`:

```python
def _make_valid_db(path: str) -> None:
    """Create a minimal valid SQLite DB with required tables."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE conversations (id INTEGER PRIMARY KEY, role TEXT, content TEXT, "
        "channel TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, importance REAL DEFAULT 0.0, "
        "embedding_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE memories (id INTEGER PRIMARY KEY, name TEXT, type TEXT, content TEXT)"
    )
    conn.execute(
        "CREATE TABLE importance_keywords (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE, "
        "score REAL, hit_count INTEGER DEFAULT 0, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()


def test_import_returns_200_for_valid_db(client, tmp_path):
    db_file = str(tmp_path / "upload.db")
    _make_valid_db(db_file)
    with open(db_file, "rb") as f:
        resp = client.post(
            "/backup/import",
            data={"file": (f, "upload.db")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 200


def test_import_response_contains_swapped_at(client, tmp_path):
    db_file = str(tmp_path / "upload2.db")
    _make_valid_db(db_file)
    with open(db_file, "rb") as f:
        resp = client.post(
            "/backup/import",
            data={"file": (f, "upload2.db")},
            content_type="multipart/form-data",
        )
    data = resp.get_json()
    assert "swapped_at" in data


def test_import_returns_400_when_no_file(client):
    resp = client.post("/backup/import", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_import_returns_400_for_non_sqlite_file(client, tmp_path):
    txt = tmp_path / "bad.db"
    txt.write_text("not a sqlite file")
    with open(str(txt), "rb") as f:
        resp = client.post(
            "/backup/import",
            data={"file": (f, "bad.db")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_backup.py -k "import" -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Add import route to `blueprints/backup.py`**

```python
@bp.route("/backup/import", methods=["POST"])
def backup_import():
    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "file field required"}), 400

    # Save upload to temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    uploaded.save(tmp.name)
    tmp.close()

    try:
        # Validate: must be a readable SQLite file with required tables
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute("PRAGMA integrity_check")
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
        except Exception:
            os.unlink(tmp.name)
            return jsonify({"error": "uploaded file is not a valid SQLite database"}), 400

        missing = _REQUIRED_TABLES - tables
        if missing:
            os.unlink(tmp.name)
            return jsonify({"error": f"missing required tables: {sorted(missing)}"}), 400

        # Back up current DB
        db_path = _db_path()
        abs_path = os.path.abspath(db_path)
        stem = os.path.splitext(os.path.basename(abs_path))[0]
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        backup_name = f"{stem}.pre-import-{ts}.db"
        backup_path = os.path.join(os.path.dirname(abs_path), backup_name)
        shutil.copy2(abs_path, backup_path)

        # Swap in the new file
        shutil.copy2(tmp.name, abs_path)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    return jsonify({
        "success": True,
        "previous_backup": backup_name,
        "swapped_at": datetime.utcnow().isoformat() + "Z",
    }), 200
```

- [ ] **Step 4: Run import tests**

```bash
uv run pytest tests/test_backup.py -k "import" -v
```
Expected: All four PASS.

- [ ] **Step 5: Run full backup test suite**

```bash
uv run pytest tests/test_backup.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Run full test suite — no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add blueprints/backup.py tests/test_backup.py
git commit -m "feat: add POST /backup/import with validation and pre-import snapshot"
```
