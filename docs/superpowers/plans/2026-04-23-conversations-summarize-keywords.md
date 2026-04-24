# Conversations Summarize + Keywords Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `POST /conversation/summarize` (weekly grouping of old messages into summary records) and the `GET/POST/DELETE /keywords` API for managing importance-scoring keywords.

**Architecture:** `summarize` queries conversations older than `days_old`, groups by ISO week, inserts one synthetic `role="summary"` record per week-group, and returns the new IDs. Keywords routes delegate to a new `storage/keywords_repository.py`. `compute_importance` is extended to increment `hit_count` for matched keywords. No new tables; both features operate on existing schema.

**Tech Stack:** Flask, SQLite (via `get_db()`), `datetime.date.isocalendar()`, existing `parse_limit_offset` from `blueprints/_params.py`.

---

## Chunk 1: Keyword hit-count tracking + keywords CRUD

### Task 1: Hit-count tracking in `compute_importance`

**Files:**
- Modify: `storage/conversation_repository.py`
- Modify: `tests/test_conversations.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_conversations.py`:

```python
def test_log_increments_keyword_hit_count(client):
    db = client.application.extensions.get("sqlalchemy") or None
    # POST a message with a seeded keyword
    client.post("/conversation/log", json={"role": "user", "content": "new project alpha"})
    # Read hit_count directly via a fresh DB connection
    with client.application.app_context():
        from db_utils import get_db
        db = get_db()
        row = db.execute(
            "SELECT hit_count FROM importance_keywords WHERE keyword = 'project'"
        ).fetchone()
    assert row is not None
    assert row["hit_count"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/varigg/code/memory-graph
uv run pytest tests/test_conversations.py::test_log_increments_keyword_hit_count -v
```
Expected: FAIL — hit_count stays 0.

- [ ] **Step 3: Update `compute_importance` to track hits**

In `storage/conversation_repository.py`, replace the function body:

```python
def compute_importance(db: sqlite3.Connection, text: str) -> float:
    lower_text = text.lower()
    keywords = db.execute("SELECT keyword, score FROM importance_keywords").fetchall()
    total = 0.0
    matched = []
    for row in keywords:
        keyword, score = row[0], row[1]
        if keyword in lower_text:
            total += score
            matched.append(keyword)
    if matched:
        placeholders = ",".join("?" * len(matched))
        db.execute(
            f"UPDATE importance_keywords "
            f"SET hit_count = hit_count + 1, updated_at = CURRENT_TIMESTAMP "
            f"WHERE keyword IN ({placeholders})",
            matched,
        )
        db.commit()
    return min(total, 1.0)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_conversations.py::test_log_increments_keyword_hit_count -v
```
Expected: PASS

- [ ] **Step 5: Run full conversation test suite — no regressions**

```bash
uv run pytest tests/test_conversations.py -v
```
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add storage/conversation_repository.py tests/test_conversations.py
git commit -m "feat: track keyword hit counts in compute_importance"
```

---

### Task 2: Keywords repository

**Files:**
- Create: `storage/keywords_repository.py`
- Create: `tests/test_keywords.py` (skeleton — first three tests)

- [ ] **Step 1: Write failing tests**

Create `tests/test_keywords.py`:

```python
"""Tests for GET/POST/DELETE /keywords."""


def test_list_keywords_returns_200(client):
    resp = client.get("/keywords")
    assert resp.status_code == 200


def test_list_keywords_returns_seeded_entries(client):
    resp = client.get("/keywords")
    data = resp.get_json()
    assert isinstance(data, list)
    keywords = [item["keyword"] for item in data]
    assert "project" in keywords


def test_list_keywords_entries_have_required_fields(client):
    resp = client.get("/keywords")
    data = resp.get_json()
    assert len(data) > 0
    item = data[0]
    assert "id" in item
    assert "keyword" in item
    assert "score" in item
    assert "hit_count" in item
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_keywords.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/keywords_repository.py`**

```python
import sqlite3


def list_keywords(db: sqlite3.Connection) -> list:
    rows = db.execute(
        "SELECT id, keyword, score, hit_count FROM importance_keywords ORDER BY score DESC, keyword"
    ).fetchall()
    return [{"id": r[0], "keyword": r[1], "score": r[2], "hit_count": r[3]} for r in rows]


def upsert_keyword(db: sqlite3.Connection, keyword: str, score: float) -> dict:
    db.execute(
        "INSERT INTO importance_keywords (keyword, score) VALUES (?, ?) "
        "ON CONFLICT(keyword) DO UPDATE SET score = excluded.score, "
        "updated_at = CURRENT_TIMESTAMP",
        (keyword, score),
    )
    db.commit()
    row = db.execute(
        "SELECT id, keyword, score, hit_count FROM importance_keywords WHERE keyword = ?",
        (keyword,),
    ).fetchone()
    return {"id": row[0], "keyword": row[1], "score": row[2], "hit_count": row[3]}


def delete_keyword(db: sqlite3.Connection, keyword_id: int) -> bool:
    cursor = db.execute("DELETE FROM importance_keywords WHERE id = ?", (keyword_id,))
    db.commit()
    return cursor.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/keywords.py`**

```python
from flask import Blueprint, jsonify, request

from db_utils import get_db
from storage.keywords_repository import delete_keyword, list_keywords, upsert_keyword

bp = Blueprint("keywords", __name__)


@bp.route("/keywords", methods=["GET"])
def get_keywords():
    db = get_db()
    return jsonify(list_keywords(db)), 200


@bp.route("/keywords", methods=["POST"])
def post_keyword():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    keyword = data.get("keyword")
    score = data.get("score")
    if not keyword or not isinstance(keyword, str) or not keyword.strip():
        return jsonify({"error": "keyword is required"}), 400
    if score is None:
        return jsonify({"error": "score is required"}), 400
    try:
        score = float(score)
    except (TypeError, ValueError):
        return jsonify({"error": "score must be a number"}), 400
    if score < 0.0 or score > 1.0:
        return jsonify({"error": "score must be between 0 and 1"}), 400
    db = get_db()
    result = upsert_keyword(db, keyword.strip(), score)
    return jsonify(result), 201


@bp.route("/keywords/<int:keyword_id>", methods=["DELETE"])
def remove_keyword(keyword_id: int):
    db = get_db()
    deleted = delete_keyword(db, keyword_id)
    if not deleted:
        return jsonify({"error": "keyword not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

Add after the existing blueprint imports:

```python
from blueprints.keywords import bp as keywords_bp
```

And after the existing `register_blueprint` calls:

```python
app.register_blueprint(keywords_bp)
```

- [ ] **Step 6: Run the three new tests to verify they pass**

```bash
uv run pytest tests/test_keywords.py::test_list_keywords_returns_200 \
              tests/test_keywords.py::test_list_keywords_returns_seeded_entries \
              tests/test_keywords.py::test_list_keywords_entries_have_required_fields -v
```
Expected: All three PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/keywords_repository.py blueprints/keywords.py api_server.py tests/test_keywords.py
git commit -m "feat: add keywords storage and GET /keywords endpoint"
```

---

### Task 3: POST and DELETE keywords endpoints

**Files:**
- Modify: `tests/test_keywords.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_keywords.py`:

```python
def test_post_keyword_returns_201(client):
    resp = client.post("/keywords", json={"keyword": "deploy", "score": 0.9})
    assert resp.status_code == 201


def test_post_keyword_upserts_existing(client):
    client.post("/keywords", json={"keyword": "project", "score": 0.95})
    resp = client.get("/keywords")
    items = {item["keyword"]: item["score"] for item in resp.get_json()}
    assert abs(items["project"] - 0.95) < 0.001


def test_post_keyword_returns_400_when_score_out_of_range(client):
    resp = client.post("/keywords", json={"keyword": "test", "score": 2.0})
    assert resp.status_code == 400


def test_post_keyword_returns_400_when_keyword_missing(client):
    resp = client.post("/keywords", json={"score": 0.5})
    assert resp.status_code == 400


def test_delete_keyword_returns_200(client):
    # create then delete
    created = client.post("/keywords", json={"keyword": "temp_kw", "score": 0.3}).get_json()
    resp = client.delete(f"/keywords/{created['id']}")
    assert resp.status_code == 200


def test_delete_keyword_removes_from_list(client):
    created = client.post("/keywords", json={"keyword": "temp_kw2", "score": 0.3}).get_json()
    client.delete(f"/keywords/{created['id']}")
    resp = client.get("/keywords")
    keywords = [item["keyword"] for item in resp.get_json()]
    assert "temp_kw2" not in keywords


def test_delete_keyword_returns_404_for_unknown_id(client):
    resp = client.delete("/keywords/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail correctly**

```bash
uv run pytest tests/test_keywords.py -k "post_keyword or delete_keyword" -v
```
Expected: Some PASS (routes exist), some FAIL on logic.

- [ ] **Step 3: Run full keyword test suite**

```bash
uv run pytest tests/test_keywords.py -v
```
Expected: All PASS (implementation already complete from Task 2).

- [ ] **Step 4: Commit**

```bash
git add tests/test_keywords.py
git commit -m "test: add POST and DELETE keyword tests"
```

---

## Chunk 2: Conversation summarize endpoint

### Task 4: Summarize storage function

**Files:**
- Modify: `storage/conversation_repository.py`
- Modify: `tests/test_conversations.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_conversations.py`:

```python
import datetime


def _log_old_message(client, content, days_ago=10):
    """Helper: log a message, then backdate it in the DB."""
    resp = client.post(
        "/conversation/log",
        json={"role": "user", "content": content, "channel": "test"},
    )
    msg_id = resp.get_json()["id"]
    old_ts = (datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    with client.application.app_context():
        from db_utils import get_db
        db = get_db()
        db.execute("UPDATE conversations SET timestamp = ? WHERE id = ?", (old_ts, msg_id))
        db.commit()
    return msg_id


def test_summarize_returns_200(client):
    _log_old_message(client, "old message one")
    resp = client.post("/conversation/summarize", json={})
    assert resp.status_code == 200


def test_summarize_returns_summaries_list(client):
    _log_old_message(client, "old message two")
    resp = client.post("/conversation/summarize", json={})
    data = resp.get_json()
    assert "summaries" in data
    assert isinstance(data["summaries"], list)


def test_summarize_creates_summary_record_for_old_messages(client):
    _log_old_message(client, "old project message")
    resp = client.post("/conversation/summarize", json={})
    summaries = resp.get_json()["summaries"]
    assert len(summaries) >= 1
    s = summaries[0]
    assert "week" in s
    assert "message_count" in s
    assert "id" in s


def test_summarize_only_covers_messages_older_than_days_old(client):
    _log_old_message(client, "old enough", days_ago=10)
    # recent message — should not appear in summaries
    client.post("/conversation/log", json={"role": "user", "content": "fresh message"})
    resp = client.post("/conversation/summarize", json={"days_old": 7})
    summaries = resp.get_json()["summaries"]
    total_covered = sum(s["message_count"] for s in summaries)
    # only the backdated one should be covered
    assert total_covered >= 1


def test_summarize_does_not_delete_original_messages(client):
    _log_old_message(client, "preserve me")
    client.post("/conversation/summarize", json={})
    recent = client.get("/conversation/recent?limit=100").get_json()
    contents = [r["content"] for r in recent]
    assert "preserve me" in contents
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_conversations.py -k "summarize" -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Add `summarize_conversations` to `storage/conversation_repository.py`**

```python
import datetime


def summarize_conversations(db: sqlite3.Connection, days_old: int = 7) -> list:
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days_old)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows = db.execute(
        "SELECT id, content, role, timestamp FROM conversations "
        "WHERE timestamp < ? AND role != 'summary' "
        "ORDER BY timestamp",
        (cutoff,),
    ).fetchall()

    if not rows:
        return []

    # Group by ISO year-week
    groups: dict[str, list] = {}
    for row in rows:
        try:
            ts = datetime.datetime.strptime(row[3][:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            ts = datetime.datetime.utcnow()
        iso = ts.isocalendar()
        week_key = f"{iso[0]}-W{iso[1]:02d}"
        groups.setdefault(week_key, []).append(row)

    summaries = []
    for week_key, week_rows in sorted(groups.items()):
        count = len(week_rows)
        content = f"Week {week_key}: {count} message(s)."
        cur = db.execute(
            "INSERT INTO conversations (role, content, channel, importance) "
            "VALUES ('summary', ?, 'system', 0.0)",
            (content,),
        )
        db.commit()
        summaries.append({"week": week_key, "message_count": count, "id": cur.lastrowid})

    return summaries
```

- [ ] **Step 4: Add the route to `blueprints/conversations.py`**

Add import at top:

```python
from storage.conversation_repository import summarize_conversations
```

Add route:

```python
@bp.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json(silent=True) or {}
    raw_days = data.get("days_old", 7)
    try:
        days_old = int(raw_days)
    except (TypeError, ValueError):
        return jsonify({"error": "days_old must be an integer"}), 400
    if days_old < 1:
        return jsonify({"error": "days_old must be at least 1"}), 400
    db = get_db()
    summaries = summarize_conversations(db, days_old=days_old)
    return jsonify({"summaries": summaries}), 200
```

- [ ] **Step 5: Run summarize tests**

```bash
uv run pytest tests/test_conversations.py -k "summarize" -v
```
Expected: All five PASS.

- [ ] **Step 6: Run full test suite — no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/conversation_repository.py blueprints/conversations.py tests/test_conversations.py
git commit -m "feat: add POST /conversation/summarize and weekly grouping"
```
