# Self-Evolving System: CRUD Entities Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four CRUD entity groups — Skills, Reflections, Preferences, and Insights — each with its own table, storage module, blueprint, and tests.

**Architecture:** All four entities follow the same pattern: a `storage/<entity>_repository.py` with insert/list/delete functions, a `blueprints/<entity>.py` with Flask routes, and tests in `tests/test_<entity>.py`. Schema additions go in `db_schema.py` via `_DDL`. Each entity is independent and can be implemented and deployed separately.

**Tech Stack:** Flask, SQLite (`get_db()`), `parse_limit_offset` from `blueprints/_params.py`.

**Schema summary:**
- `skills`: id, name, trigger_pattern, description, steps (JSON text), times_used, last_used, created_at
- `reflections`: id, date, content, patterns, mistakes, insights, created_at
- `preferences`: id, rule, source_count, confidence, created_at
- `insights`: id, type, pattern, evidence (JSON text), confidence, valid_until, created_at

---

## Chunk 1: Schema migration

### Task 1: Add all four tables to `db_schema.py`

**Files:**
- Modify: `db_schema.py`
- Modify: `tests/test_db_schema.py`

- [ ] **Step 1: Write failing schema tests**

Append to `tests/test_db_schema.py`:

```python
def test_skills_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "skills" in tables


def test_reflections_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "reflections" in tables


def test_preferences_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "preferences" in tables


def test_insights_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "insights" in tables
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/varigg/code/memory-graph
uv run pytest tests/test_db_schema.py -k "skills or reflections or preferences or insights" -v
```
Expected: FAIL — tables not yet created.

- [ ] **Step 3: Add DDL to `db_schema.py`**

Append the following to the `_DDL` string (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS skills (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    trigger_pattern TEXT NOT NULL,
    description     TEXT,
    steps           TEXT NOT NULL DEFAULT '[]',
    times_used      INTEGER NOT NULL DEFAULT 0,
    last_used       DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reflections (
    id         INTEGER PRIMARY KEY,
    date       TEXT NOT NULL,
    content    TEXT,
    patterns   TEXT,
    mistakes   TEXT,
    insights   TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preferences (
    id           INTEGER PRIMARY KEY,
    rule         TEXT NOT NULL,
    source_count INTEGER NOT NULL DEFAULT 1,
    confidence   REAL NOT NULL DEFAULT 0.5,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS insights (
    id          INTEGER PRIMARY KEY,
    type        TEXT NOT NULL,
    pattern     TEXT NOT NULL,
    evidence    TEXT NOT NULL DEFAULT '[]',
    confidence  REAL NOT NULL DEFAULT 0.5,
    valid_until DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Run schema tests**

```bash
uv run pytest tests/test_db_schema.py -k "skills or reflections or preferences or insights" -v
```
Expected: All four PASS.

- [ ] **Step 5: Run full test suite — no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add db_schema.py tests/test_db_schema.py
git commit -m "feat: add skills, reflections, preferences, insights tables to schema"
```

---

## Chunk 2: Skills

### Task 2: Skills storage and blueprint

**Files:**
- Create: `storage/skill_repository.py`
- Create: `blueprints/skills.py`
- Create: `tests/test_skills.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_skills.py`:

```python
"""Tests for POST /skill, GET /skill/list, GET /skill/match, PUT /skill/<id>/use, DELETE /skill/<id>."""

_SKILL = {
    "name": "Deploy to staging",
    "trigger_pattern": "deploy",
    "description": "Steps to deploy",
    "steps": ["run tests", "push to staging"],
}


def test_create_skill_returns_201(client):
    resp = client.post("/skill", json=_SKILL)
    assert resp.status_code == 201


def test_create_skill_response_has_id(client):
    resp = client.post("/skill", json=_SKILL)
    data = resp.get_json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_create_skill_returns_400_when_name_missing(client):
    resp = client.post("/skill", json={"trigger_pattern": "x", "steps": []})
    assert resp.status_code == 400


def test_create_skill_returns_400_when_trigger_pattern_missing(client):
    resp = client.post("/skill", json={"name": "x", "steps": []})
    assert resp.status_code == 400


def test_list_skills_returns_200(client):
    resp = client.get("/skill/list")
    assert resp.status_code == 200


def test_list_skills_includes_created_skill(client):
    client.post("/skill", json=_SKILL)
    resp = client.get("/skill/list")
    names = [s["name"] for s in resp.get_json()]
    assert "Deploy to staging" in names


def test_match_skills_returns_matching_skill(client):
    client.post("/skill", json=_SKILL)
    resp = client.get("/skill/match?task=deploy to production")
    data = resp.get_json()
    assert isinstance(data, list)
    assert any("deploy" in s["trigger_pattern"].lower() for s in data)


def test_match_skills_returns_empty_for_no_match(client):
    client.post("/skill", json=_SKILL)
    resp = client.get("/skill/match?task=completely unrelated task xyz")
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_match_returns_400_when_task_missing(client):
    resp = client.get("/skill/match")
    assert resp.status_code == 400


def test_use_skill_increments_times_used(client):
    skill_id = client.post("/skill", json=_SKILL).get_json()["id"]
    client.put(f"/skill/{skill_id}/use")
    skills = client.get("/skill/list").get_json()
    match = next(s for s in skills if s["id"] == skill_id)
    assert match["times_used"] == 1


def test_delete_skill_returns_200(client):
    skill_id = client.post("/skill", json=_SKILL).get_json()["id"]
    resp = client.delete(f"/skill/{skill_id}")
    assert resp.status_code == 200


def test_delete_skill_removes_from_list(client):
    skill_id = client.post("/skill", json=_SKILL).get_json()["id"]
    client.delete(f"/skill/{skill_id}")
    skills = client.get("/skill/list").get_json()
    assert not any(s["id"] == skill_id for s in skills)


def test_delete_skill_returns_404_for_unknown_id(client):
    resp = client.delete("/skill/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_skills.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/skill_repository.py`**

```python
import json
import sqlite3


def insert_skill(
    db: sqlite3.Connection,
    name: str,
    trigger_pattern: str,
    description: str = None,
    steps=None,
) -> int:
    steps_json = json.dumps(steps or [])
    cur = db.execute(
        "INSERT INTO skills (name, trigger_pattern, description, steps) VALUES (?, ?, ?, ?)",
        (name, trigger_pattern, description, steps_json),
    )
    db.commit()
    return int(cur.lastrowid)


def _row_to_skill(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "trigger_pattern": row[2],
        "description": row[3],
        "steps": json.loads(row[4]) if row[4] else [],
        "times_used": row[5],
        "last_used": row[6],
        "created_at": row[7],
    }


def list_skills(db: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list:
    rows = db.execute(
        "SELECT id, name, trigger_pattern, description, steps, times_used, last_used, created_at "
        "FROM skills ORDER BY times_used DESC, created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_skill(r) for r in rows]


def match_skills(db: sqlite3.Connection, task: str) -> list:
    rows = db.execute(
        "SELECT id, name, trigger_pattern, description, steps, times_used, last_used, created_at "
        "FROM skills",
    ).fetchall()
    task_lower = task.lower()
    return [_row_to_skill(r) for r in rows if r[2].lower() in task_lower]


def increment_skill_use(db: sqlite3.Connection, skill_id: int) -> bool:
    cur = db.execute(
        "UPDATE skills SET times_used = times_used + 1, last_used = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (skill_id,),
    )
    db.commit()
    return cur.rowcount > 0


def delete_skill(db: sqlite3.Connection, skill_id: int) -> bool:
    cur = db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    db.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/skills.py`**

```python
import json

from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.skill_repository import (
    delete_skill,
    increment_skill_use,
    insert_skill,
    list_skills,
    match_skills,
)

bp = Blueprint("skills", __name__)


@bp.route("/skill", methods=["POST"])
def create_skill():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    name = data.get("name")
    trigger_pattern = data.get("trigger_pattern")
    if not name or not str(name).strip():
        return jsonify({"error": "name is required"}), 400
    if not trigger_pattern or not str(trigger_pattern).strip():
        return jsonify({"error": "trigger_pattern is required"}), 400
    db = get_db()
    skill_id = insert_skill(
        db,
        name=str(name).strip(),
        trigger_pattern=str(trigger_pattern).strip(),
        description=data.get("description"),
        steps=data.get("steps"),
    )
    return jsonify({"id": skill_id}), 201


@bp.route("/skill/list", methods=["GET"])
def list_all_skills():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_skills(db, limit=limit, offset=offset)), 200


@bp.route("/skill/match", methods=["GET"])
def match_skill():
    task = request.args.get("task")
    if not task or not task.strip():
        return jsonify({"error": "task parameter required"}), 400
    db = get_db()
    return jsonify(match_skills(db, task.strip())), 200


@bp.route("/skill/<int:skill_id>/use", methods=["PUT"])
def use_skill(skill_id: int):
    db = get_db()
    found = increment_skill_use(db, skill_id)
    if not found:
        return jsonify({"error": "skill not found"}), 404
    return jsonify({"updated": True}), 200


@bp.route("/skill/<int:skill_id>", methods=["DELETE"])
def remove_skill(skill_id: int):
    db = get_db()
    deleted = delete_skill(db, skill_id)
    if not deleted:
        return jsonify({"error": "skill not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.skills import bp as skills_bp
# ...
app.register_blueprint(skills_bp)
```

- [ ] **Step 6: Run skills tests**

```bash
uv run pytest tests/test_skills.py -v
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/skill_repository.py blueprints/skills.py api_server.py tests/test_skills.py
git commit -m "feat: add skills CRUD endpoints (POST/list/match/use/delete)"
```

---

## Chunk 3: Reflections

### Task 3: Reflections storage and blueprint

**Files:**
- Create: `storage/reflection_repository.py`
- Create: `blueprints/reflections.py`
- Create: `tests/test_reflections.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_reflections.py`:

```python
"""Tests for POST /reflection, GET /reflection/recent, GET /reflection/list, DELETE /reflection/<id>."""

_REFLECTION = {
    "date": "2026-04-21",
    "content": "Had a productive day.",
    "patterns": "Deep work in morning.",
    "mistakes": "Skipped tests once.",
    "insights": "Morning focus blocks are best.",
}


def test_create_reflection_returns_201(client):
    resp = client.post("/reflection", json=_REFLECTION)
    assert resp.status_code == 201


def test_create_reflection_response_has_id(client):
    data = client.post("/reflection", json=_REFLECTION).get_json()
    assert "id" in data


def test_create_reflection_returns_400_when_date_missing(client):
    resp = client.post("/reflection", json={"content": "no date"})
    assert resp.status_code == 400


def test_recent_reflections_returns_200(client):
    resp = client.get("/reflection/recent")
    assert resp.status_code == 200


def test_recent_reflections_includes_created(client):
    client.post("/reflection", json=_REFLECTION)
    resp = client.get("/reflection/recent")
    dates = [r["date"] for r in resp.get_json()]
    assert "2026-04-21" in dates


def test_list_reflections_returns_200(client):
    resp = client.get("/reflection/list")
    assert resp.status_code == 200


def test_delete_reflection_returns_200(client):
    rid = client.post("/reflection", json=_REFLECTION).get_json()["id"]
    resp = client.delete(f"/reflection/{rid}")
    assert resp.status_code == 200


def test_delete_reflection_removes_from_list(client):
    rid = client.post("/reflection", json=_REFLECTION).get_json()["id"]
    client.delete(f"/reflection/{rid}")
    items = client.get("/reflection/list").get_json()
    assert not any(r["id"] == rid for r in items)


def test_delete_reflection_returns_404_for_unknown_id(client):
    resp = client.delete("/reflection/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_reflections.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/reflection_repository.py`**

```python
import sqlite3


def insert_reflection(
    db: sqlite3.Connection,
    date: str,
    content: str = None,
    patterns: str = None,
    mistakes: str = None,
    insights: str = None,
) -> int:
    cur = db.execute(
        "INSERT INTO reflections (date, content, patterns, mistakes, insights) "
        "VALUES (?, ?, ?, ?, ?)",
        (date, content, patterns, mistakes, insights),
    )
    db.commit()
    return int(cur.lastrowid)


def _row_to_reflection(row) -> dict:
    return {
        "id": row[0],
        "date": row[1],
        "content": row[2],
        "patterns": row[3],
        "mistakes": row[4],
        "insights": row[5],
        "created_at": row[6],
    }


def list_reflections(db: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list:
    rows = db.execute(
        "SELECT id, date, content, patterns, mistakes, insights, created_at "
        "FROM reflections ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_reflection(r) for r in rows]


def delete_reflection(db: sqlite3.Connection, reflection_id: int) -> bool:
    cur = db.execute("DELETE FROM reflections WHERE id = ?", (reflection_id,))
    db.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/reflections.py`**

```python
from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.reflection_repository import delete_reflection, insert_reflection, list_reflections

bp = Blueprint("reflections", __name__)


@bp.route("/reflection", methods=["POST"])
def create_reflection():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    date = data.get("date")
    if not date or not str(date).strip():
        return jsonify({"error": "date is required"}), 400
    db = get_db()
    rid = insert_reflection(
        db,
        date=str(date).strip(),
        content=data.get("content"),
        patterns=data.get("patterns"),
        mistakes=data.get("mistakes"),
        insights=data.get("insights"),
    )
    return jsonify({"id": rid}), 201


@bp.route("/reflection/recent", methods=["GET"])
def recent_reflections():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_reflections(db, limit=limit, offset=offset)), 200


@bp.route("/reflection/list", methods=["GET"])
def list_all_reflections():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_reflections(db, limit=limit, offset=offset)), 200


@bp.route("/reflection/<int:reflection_id>", methods=["DELETE"])
def remove_reflection(reflection_id: int):
    db = get_db()
    deleted = delete_reflection(db, reflection_id)
    if not deleted:
        return jsonify({"error": "reflection not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.reflections import bp as reflections_bp
# ...
app.register_blueprint(reflections_bp)
```

- [ ] **Step 6: Run tests and verify they pass**

```bash
uv run pytest tests/test_reflections.py -v
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/reflection_repository.py blueprints/reflections.py api_server.py tests/test_reflections.py
git commit -m "feat: add reflections CRUD endpoints"
```

---

## Chunk 4: Preferences

### Task 4: Preferences storage and blueprint

**Files:**
- Create: `storage/preference_repository.py`
- Create: `blueprints/preferences.py`
- Create: `tests/test_preferences.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_preferences.py`:

```python
"""Tests for POST /preference, GET /preference/list, GET /preference/active, DELETE /preference/<id>."""

_PREF_LOW = {"rule": "Prefer short responses", "confidence": 0.5}
_PREF_HIGH = {"rule": "Always use TDD", "confidence": 0.9}


def test_create_preference_returns_201(client):
    resp = client.post("/preference", json=_PREF_LOW)
    assert resp.status_code == 201


def test_create_preference_response_has_id(client):
    data = client.post("/preference", json=_PREF_LOW).get_json()
    assert "id" in data


def test_create_preference_returns_400_when_rule_missing(client):
    resp = client.post("/preference", json={"confidence": 0.5})
    assert resp.status_code == 400


def test_list_preferences_returns_200(client):
    resp = client.get("/preference/list")
    assert resp.status_code == 200


def test_list_preferences_includes_created(client):
    client.post("/preference", json=_PREF_LOW)
    items = client.get("/preference/list").get_json()
    rules = [p["rule"] for p in items]
    assert "Prefer short responses" in rules


def test_active_preferences_returns_200(client):
    resp = client.get("/preference/active")
    assert resp.status_code == 200


def test_active_preferences_only_returns_high_confidence(client):
    client.post("/preference", json=_PREF_LOW)   # confidence 0.5 — excluded
    client.post("/preference", json=_PREF_HIGH)  # confidence 0.9 — included
    items = client.get("/preference/active").get_json()
    rules = [p["rule"] for p in items]
    assert "Always use TDD" in rules
    assert "Prefer short responses" not in rules


def test_delete_preference_returns_200(client):
    pid = client.post("/preference", json=_PREF_LOW).get_json()["id"]
    resp = client.delete(f"/preference/{pid}")
    assert resp.status_code == 200


def test_delete_preference_removes_from_list(client):
    pid = client.post("/preference", json=_PREF_LOW).get_json()["id"]
    client.delete(f"/preference/{pid}")
    items = client.get("/preference/list").get_json()
    assert not any(p["id"] == pid for p in items)


def test_delete_preference_returns_404_for_unknown_id(client):
    resp = client.delete("/preference/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_preferences.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/preference_repository.py`**

```python
import sqlite3

_ACTIVE_CONFIDENCE_THRESHOLD = 0.7


def insert_preference(
    db: sqlite3.Connection,
    rule: str,
    source_count: int = 1,
    confidence: float = 0.5,
) -> int:
    cur = db.execute(
        "INSERT INTO preferences (rule, source_count, confidence) VALUES (?, ?, ?)",
        (rule, source_count, confidence),
    )
    db.commit()
    return int(cur.lastrowid)


def _row_to_preference(row) -> dict:
    return {
        "id": row[0],
        "rule": row[1],
        "source_count": row[2],
        "confidence": row[3],
        "created_at": row[4],
    }


def list_preferences(db: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list:
    rows = db.execute(
        "SELECT id, rule, source_count, confidence, created_at "
        "FROM preferences ORDER BY confidence DESC, created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_preference(r) for r in rows]


def list_active_preferences(db: sqlite3.Connection) -> list:
    rows = db.execute(
        "SELECT id, rule, source_count, confidence, created_at "
        "FROM preferences WHERE confidence >= ? ORDER BY confidence DESC",
        (_ACTIVE_CONFIDENCE_THRESHOLD,),
    ).fetchall()
    return [_row_to_preference(r) for r in rows]


def delete_preference(db: sqlite3.Connection, preference_id: int) -> bool:
    cur = db.execute("DELETE FROM preferences WHERE id = ?", (preference_id,))
    db.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/preferences.py`**

```python
from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.preference_repository import (
    delete_preference,
    insert_preference,
    list_active_preferences,
    list_preferences,
)

bp = Blueprint("preferences", __name__)


@bp.route("/preference", methods=["POST"])
def create_preference():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    rule = data.get("rule")
    if not rule or not str(rule).strip():
        return jsonify({"error": "rule is required"}), 400
    confidence = data.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return jsonify({"error": "confidence must be a number"}), 400
    if confidence < 0.0 or confidence > 1.0:
        return jsonify({"error": "confidence must be between 0 and 1"}), 400
    source_count = data.get("source_count", 1)
    db = get_db()
    pid = insert_preference(db, rule=str(rule).strip(), source_count=int(source_count), confidence=confidence)
    return jsonify({"id": pid}), 201


@bp.route("/preference/list", methods=["GET"])
def list_all_preferences():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_preferences(db, limit=limit, offset=offset)), 200


@bp.route("/preference/active", methods=["GET"])
def active_preferences():
    db = get_db()
    return jsonify(list_active_preferences(db)), 200


@bp.route("/preference/<int:preference_id>", methods=["DELETE"])
def remove_preference(preference_id: int):
    db = get_db()
    deleted = delete_preference(db, preference_id)
    if not deleted:
        return jsonify({"error": "preference not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.preferences import bp as preferences_bp
# ...
app.register_blueprint(preferences_bp)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_preferences.py -v
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/preference_repository.py blueprints/preferences.py api_server.py tests/test_preferences.py
git commit -m "feat: add preferences CRUD endpoints with active filter (confidence >= 0.7)"
```

---

## Chunk 5: Insights

### Task 5: Insights storage and blueprint

**Files:**
- Create: `storage/insight_repository.py`
- Create: `blueprints/insights.py`
- Create: `tests/test_insights.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_insights.py`:

```python
"""Tests for POST /insight, GET /insight/active, GET /insight/list, DELETE /insight/<id>."""

import datetime

_INSIGHT = {
    "type": "pattern",
    "pattern": "Users prefer concise responses",
    "evidence": ["session-1", "session-2"],
    "confidence": 0.8,
}


def test_create_insight_returns_201(client):
    resp = client.post("/insight", json=_INSIGHT)
    assert resp.status_code == 201


def test_create_insight_response_has_id(client):
    data = client.post("/insight", json=_INSIGHT).get_json()
    assert "id" in data


def test_create_insight_returns_400_when_type_missing(client):
    resp = client.post("/insight", json={"pattern": "x", "confidence": 0.5})
    assert resp.status_code == 400


def test_create_insight_returns_400_when_pattern_missing(client):
    resp = client.post("/insight", json={"type": "x", "confidence": 0.5})
    assert resp.status_code == 400


def test_list_insights_returns_200(client):
    resp = client.get("/insight/list")
    assert resp.status_code == 200


def test_list_insights_includes_created(client):
    client.post("/insight", json=_INSIGHT)
    items = client.get("/insight/list").get_json()
    patterns = [i["pattern"] for i in items]
    assert "Users prefer concise responses" in patterns


def test_active_insights_returns_200(client):
    resp = client.get("/insight/active")
    assert resp.status_code == 200


def test_active_insights_excludes_expired(client):
    past = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
    client.post("/insight", json={**_INSIGHT, "valid_until": past})
    items = client.get("/insight/active").get_json()
    # the expired insight must not appear
    for item in items:
        if item["pattern"] == _INSIGHT["pattern"] and item.get("valid_until"):
            assert False, "expired insight appeared in active list"


def test_active_insights_includes_non_expiring(client):
    client.post("/insight", json=_INSIGHT)  # no valid_until
    items = client.get("/insight/active").get_json()
    assert any(i["pattern"] == _INSIGHT["pattern"] for i in items)


def test_delete_insight_returns_200(client):
    iid = client.post("/insight", json=_INSIGHT).get_json()["id"]
    resp = client.delete(f"/insight/{iid}")
    assert resp.status_code == 200


def test_delete_insight_removes_from_list(client):
    iid = client.post("/insight", json=_INSIGHT).get_json()["id"]
    client.delete(f"/insight/{iid}")
    items = client.get("/insight/list").get_json()
    assert not any(i["id"] == iid for i in items)


def test_delete_insight_returns_404_for_unknown_id(client):
    resp = client.delete("/insight/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_insights.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/insight_repository.py`**

```python
import json
import sqlite3


def insert_insight(
    db: sqlite3.Connection,
    type_: str,
    pattern: str,
    evidence=None,
    confidence: float = 0.5,
    valid_until: str = None,
) -> int:
    evidence_json = json.dumps(evidence or [])
    cur = db.execute(
        "INSERT INTO insights (type, pattern, evidence, confidence, valid_until) "
        "VALUES (?, ?, ?, ?, ?)",
        (type_, pattern, evidence_json, confidence, valid_until),
    )
    db.commit()
    return int(cur.lastrowid)


def _row_to_insight(row) -> dict:
    return {
        "id": row[0],
        "type": row[1],
        "pattern": row[2],
        "evidence": json.loads(row[3]) if row[3] else [],
        "confidence": row[4],
        "valid_until": row[5],
        "created_at": row[6],
    }


def list_insights(db: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list:
    rows = db.execute(
        "SELECT id, type, pattern, evidence, confidence, valid_until, created_at "
        "FROM insights ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_insight(r) for r in rows]


def list_active_insights(db: sqlite3.Connection) -> list:
    rows = db.execute(
        "SELECT id, type, pattern, evidence, confidence, valid_until, created_at "
        "FROM insights "
        "WHERE valid_until IS NULL OR valid_until > CURRENT_TIMESTAMP "
        "ORDER BY confidence DESC, created_at DESC",
    ).fetchall()
    return [_row_to_insight(r) for r in rows]


def delete_insight(db: sqlite3.Connection, insight_id: int) -> bool:
    cur = db.execute("DELETE FROM insights WHERE id = ?", (insight_id,))
    db.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/insights.py`**

```python
import json

from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.insight_repository import (
    delete_insight,
    insert_insight,
    list_active_insights,
    list_insights,
)

bp = Blueprint("insights", __name__)


@bp.route("/insight", methods=["POST"])
def create_insight():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    type_ = data.get("type")
    pattern = data.get("pattern")
    if not type_ or not str(type_).strip():
        return jsonify({"error": "type is required"}), 400
    if not pattern or not str(pattern).strip():
        return jsonify({"error": "pattern is required"}), 400
    confidence = data.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return jsonify({"error": "confidence must be a number"}), 400
    if confidence < 0.0 or confidence > 1.0:
        return jsonify({"error": "confidence must be between 0 and 1"}), 400
    db = get_db()
    iid = insert_insight(
        db,
        type_=str(type_).strip(),
        pattern=str(pattern).strip(),
        evidence=data.get("evidence"),
        confidence=confidence,
        valid_until=data.get("valid_until"),
    )
    return jsonify({"id": iid}), 201


@bp.route("/insight/active", methods=["GET"])
def active_insights():
    db = get_db()
    return jsonify(list_active_insights(db)), 200


@bp.route("/insight/list", methods=["GET"])
def list_all_insights():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_insights(db, limit=limit, offset=offset)), 200


@bp.route("/insight/<int:insight_id>", methods=["DELETE"])
def remove_insight(insight_id: int):
    db = get_db()
    deleted = delete_insight(db, insight_id)
    if not deleted:
        return jsonify({"error": "insight not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.insights import bp as insights_bp
# ...
app.register_blueprint(insights_bp)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_insights.py -v
```
Expected: All PASS.

- [ ] **Step 7: Run full test suite — no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add storage/insight_repository.py blueprints/insights.py api_server.py tests/test_insights.py
git commit -m "feat: add insights CRUD endpoints with active (non-expired) filter"
```
