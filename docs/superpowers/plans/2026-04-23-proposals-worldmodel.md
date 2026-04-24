# Proposals + World Model Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `POST/GET /proposal` with approve/reject state transitions, and `POST/GET/DELETE /worldmodel` with a `/promote` action that marks a soft observation as graduated.

**Architecture:** Each entity gets a storage module and a blueprint. Proposals have a status state machine (`pending` → `approved` | `rejected`) enforced in the storage layer. World model soft observations deduplicate on `(category, pattern)` using an `INSERT OR REPLACE` that increments `occurrences`; the `promote` action sets `promoted_to` and `promoted_at` on the row without creating additional tables.

**Tech Stack:** Flask, SQLite (`get_db()`), `parse_limit_offset` from `blueprints/_params.py`, `datetime`.

---

## Chunk 1: Schema

### Task 1: Add proposals and worldmodel tables

**Files:**
- Modify: `db_schema.py`
- Modify: `tests/test_db_schema.py`

- [ ] **Step 1: Write failing schema tests**

Append to `tests/test_db_schema.py`:

```python
def test_proposals_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "proposals" in tables


def test_worldmodel_table_exists(tmp_path):
    import db_schema, sqlite3
    db_path = str(tmp_path / "test.db")
    db_schema.init(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "worldmodel" in tables
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/varigg/code/memory-graph
uv run pytest tests/test_db_schema.py -k "proposals or worldmodel" -v
```
Expected: FAIL.

- [ ] **Step 3: Append DDL to `db_schema.py`**

Add to `_DDL` string:

```sql
CREATE TABLE IF NOT EXISTS proposals (
    id           INTEGER PRIMARY KEY,
    file_path    TEXT NOT NULL,
    change_type  TEXT NOT NULL,
    description  TEXT NOT NULL,
    diff_preview TEXT,
    status       TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    resolved_at  DATETIME,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS worldmodel (
    id          INTEGER PRIMARY KEY,
    category    TEXT NOT NULL,
    pattern     TEXT NOT NULL,
    evidence    TEXT NOT NULL DEFAULT '[]',
    confidence  REAL NOT NULL DEFAULT 0.5,
    occurrences INTEGER NOT NULL DEFAULT 1,
    promoted_to TEXT CHECK (promoted_to IN ('event', 'relation', 'prediction', NULL)),
    promoted_at DATETIME,
    expires_at  DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, pattern)
);
```

- [ ] **Step 4: Run schema tests**

```bash
uv run pytest tests/test_db_schema.py -k "proposals or worldmodel" -v
```
Expected: Both PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add db_schema.py tests/test_db_schema.py
git commit -m "feat: add proposals and worldmodel tables to schema"
```

---

## Chunk 2: Proposals

### Task 2: Proposals storage and blueprint

**Files:**
- Create: `storage/proposal_repository.py`
- Create: `blueprints/proposals.py`
- Create: `tests/test_proposals.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_proposals.py`:

```python
"""Tests for proposals CRUD and approve/reject workflow."""

_PROPOSAL = {
    "file_path": "services/auth.py",
    "change_type": "refactor",
    "description": "Extract auth middleware",
    "diff_preview": "- old_auth()\n+ new_auth()",
}


def test_create_proposal_returns_201(client):
    resp = client.post("/proposal", json=_PROPOSAL)
    assert resp.status_code == 201


def test_create_proposal_response_has_id_and_status(client):
    data = client.post("/proposal", json=_PROPOSAL).get_json()
    assert "id" in data
    assert data["status"] == "pending"


def test_create_proposal_returns_400_when_file_path_missing(client):
    bad = {k: v for k, v in _PROPOSAL.items() if k != "file_path"}
    resp = client.post("/proposal", json=bad)
    assert resp.status_code == 400


def test_create_proposal_returns_400_when_change_type_missing(client):
    bad = {k: v for k, v in _PROPOSAL.items() if k != "change_type"}
    resp = client.post("/proposal", json=bad)
    assert resp.status_code == 400


def test_create_proposal_returns_400_when_description_missing(client):
    bad = {k: v for k, v in _PROPOSAL.items() if k != "description"}
    resp = client.post("/proposal", json=bad)
    assert resp.status_code == 400


def test_get_proposal_returns_200(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    resp = client.get(f"/proposal/{pid}")
    assert resp.status_code == 200


def test_get_proposal_returns_404_for_unknown_id(client):
    resp = client.get("/proposal/999999")
    assert resp.status_code == 404


def test_pending_proposals_returns_only_pending(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    resp = client.get("/proposal/pending")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.get_json()]
    assert pid in ids


def test_list_proposals_returns_all_by_default(client):
    client.post("/proposal", json=_PROPOSAL)
    resp = client.get("/proposal/list")
    assert resp.status_code == 200
    assert len(resp.get_json()) >= 1


def test_list_proposals_filters_by_status(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    client.put(f"/proposal/{pid}/approve")
    approved = client.get("/proposal/list?status=approved").get_json()
    assert any(p["id"] == pid for p in approved)
    pending = client.get("/proposal/list?status=pending").get_json()
    assert not any(p["id"] == pid for p in pending)


def test_approve_proposal_returns_200(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    resp = client.put(f"/proposal/{pid}/approve")
    assert resp.status_code == 200


def test_approve_proposal_sets_status_to_approved(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    client.put(f"/proposal/{pid}/approve")
    data = client.get(f"/proposal/{pid}").get_json()
    assert data["status"] == "approved"
    assert data["resolved_at"] is not None


def test_approve_proposal_returns_404_for_unknown_id(client):
    resp = client.put("/proposal/999999/approve")
    assert resp.status_code == 404


def test_reject_proposal_sets_status_to_rejected(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    client.put(f"/proposal/{pid}/reject")
    data = client.get(f"/proposal/{pid}").get_json()
    assert data["status"] == "rejected"


def test_reject_already_resolved_proposal_returns_409(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    client.put(f"/proposal/{pid}/approve")
    resp = client.put(f"/proposal/{pid}/reject")
    assert resp.status_code == 409


def test_approve_already_resolved_proposal_returns_409(client):
    pid = client.post("/proposal", json=_PROPOSAL).get_json()["id"]
    client.put(f"/proposal/{pid}/reject")
    resp = client.put(f"/proposal/{pid}/approve")
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_proposals.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/proposal_repository.py`**

```python
import sqlite3
from datetime import datetime


def insert_proposal(
    db: sqlite3.Connection,
    file_path: str,
    change_type: str,
    description: str,
    diff_preview: str = None,
) -> dict:
    cur = db.execute(
        "INSERT INTO proposals (file_path, change_type, description, diff_preview) "
        "VALUES (?, ?, ?, ?)",
        (file_path, change_type, description, diff_preview),
    )
    db.commit()
    return {"id": int(cur.lastrowid), "status": "pending"}


def _row_to_proposal(row) -> dict:
    return {
        "id": row[0],
        "file_path": row[1],
        "change_type": row[2],
        "description": row[3],
        "diff_preview": row[4],
        "status": row[5],
        "resolved_at": row[6],
        "created_at": row[7],
    }


def get_proposal(db: sqlite3.Connection, proposal_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, file_path, change_type, description, diff_preview, status, resolved_at, created_at "
        "FROM proposals WHERE id = ?",
        (proposal_id,),
    ).fetchone()
    return _row_to_proposal(row) if row else None


def list_proposals(db: sqlite3.Connection, status: str = None, limit: int = 100, offset: int = 0) -> list:
    if status is not None:
        rows = db.execute(
            "SELECT id, file_path, change_type, description, diff_preview, status, resolved_at, created_at "
            "FROM proposals WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT id, file_path, change_type, description, diff_preview, status, resolved_at, created_at "
            "FROM proposals ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_proposal(r) for r in rows]


def resolve_proposal(db: sqlite3.Connection, proposal_id: int, verdict: str) -> dict | None:
    existing = get_proposal(db, proposal_id)
    if existing is None:
        return None
    if existing["status"] != "pending":
        return {"conflict": True, "current_status": existing["status"]}
    resolved_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE proposals SET status = ?, resolved_at = ? WHERE id = ?",
        (verdict, resolved_at, proposal_id),
    )
    db.commit()
    return get_proposal(db, proposal_id)
```

- [ ] **Step 4: Create `blueprints/proposals.py`**

```python
from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.proposal_repository import (
    get_proposal,
    insert_proposal,
    list_proposals,
    resolve_proposal,
)

bp = Blueprint("proposals", __name__)

_VALID_STATUSES = {"pending", "approved", "rejected"}


@bp.route("/proposal", methods=["POST"])
def create_proposal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    for field in ("file_path", "change_type", "description"):
        if not data.get(field) or not str(data[field]).strip():
            return jsonify({"error": f"{field} is required"}), 400
    db = get_db()
    result = insert_proposal(
        db,
        file_path=str(data["file_path"]).strip(),
        change_type=str(data["change_type"]).strip(),
        description=str(data["description"]).strip(),
        diff_preview=data.get("diff_preview"),
    )
    return jsonify(result), 201


@bp.route("/proposal/pending", methods=["GET"])
def pending_proposals():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_proposals(db, status="pending", limit=limit, offset=offset)), 200


@bp.route("/proposal/list", methods=["GET"])
def list_all_proposals():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    status = request.args.get("status")
    if status is not None and status not in _VALID_STATUSES:
        return jsonify({"error": f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}"}), 400
    db = get_db()
    return jsonify(list_proposals(db, status=status, limit=limit, offset=offset)), 200


@bp.route("/proposal/<int:proposal_id>", methods=["GET"])
def get_one_proposal(proposal_id: int):
    db = get_db()
    proposal = get_proposal(db, proposal_id)
    if proposal is None:
        return jsonify({"error": "proposal not found"}), 404
    return jsonify(proposal), 200


def _resolve(proposal_id: int, verdict: str):
    db = get_db()
    result = resolve_proposal(db, proposal_id, verdict)
    if result is None:
        return jsonify({"error": "proposal not found"}), 404
    if result.get("conflict"):
        return jsonify({"error": f"proposal is already {result['current_status']}"}), 409
    return jsonify(result), 200


@bp.route("/proposal/<int:proposal_id>/approve", methods=["PUT", "POST", "PATCH"])
def approve_proposal(proposal_id: int):
    return _resolve(proposal_id, "approved")


@bp.route("/proposal/<int:proposal_id>/reject", methods=["PUT", "POST", "PATCH"])
def reject_proposal(proposal_id: int):
    return _resolve(proposal_id, "rejected")
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.proposals import bp as proposals_bp
# ...
app.register_blueprint(proposals_bp)
```

- [ ] **Step 6: Run proposals tests**

```bash
uv run pytest tests/test_proposals.py -v
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add storage/proposal_repository.py blueprints/proposals.py api_server.py tests/test_proposals.py
git commit -m "feat: add proposals CRUD with pending/approve/reject workflow"
```

---

## Chunk 3: World Model

### Task 3: World Model storage and blueprint

**Files:**
- Create: `storage/worldmodel_repository.py`
- Create: `blueprints/worldmodel.py`
- Create: `tests/test_worldmodel.py`
- Modify: `api_server.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_worldmodel.py`:

```python
"""Tests for POST/GET/DELETE /worldmodel and POST /worldmodel/<id>/promote."""

_OBS = {
    "category": "deploy_frequency",
    "pattern": "Deploys happen on Fridays",
    "evidence": ["2026-04-18", "2026-04-11"],
    "confidence": 0.6,
}


def test_create_observation_returns_201(client):
    resp = client.post("/worldmodel", json=_OBS)
    assert resp.status_code == 201


def test_create_observation_response_has_id(client):
    data = client.post("/worldmodel", json=_OBS).get_json()
    assert "id" in data


def test_create_observation_returns_400_when_category_missing(client):
    resp = client.post("/worldmodel", json={"pattern": "x"})
    assert resp.status_code == 400


def test_create_observation_returns_400_when_pattern_missing(client):
    resp = client.post("/worldmodel", json={"category": "x"})
    assert resp.status_code == 400


def test_duplicate_observation_increments_occurrences(client):
    client.post("/worldmodel", json=_OBS)
    client.post("/worldmodel", json=_OBS)
    items = client.get("/worldmodel/list").get_json()
    matching = [i for i in items if i["category"] == _OBS["category"] and i["pattern"] == _OBS["pattern"]]
    assert len(matching) == 1
    assert matching[0]["occurrences"] >= 2


def test_active_observations_returns_200(client):
    resp = client.get("/worldmodel/active")
    assert resp.status_code == 200


def test_active_observations_excludes_promoted(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    client.post(f"/worldmodel/{obs_id}/promote", json={"promote_to": "event"})
    active = client.get("/worldmodel/active").get_json()
    assert not any(o["id"] == obs_id for o in active)


def test_list_observations_includes_promoted(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    client.post(f"/worldmodel/{obs_id}/promote", json={"promote_to": "event"})
    all_obs = client.get("/worldmodel/list").get_json()
    assert any(o["id"] == obs_id for o in all_obs)


def test_list_observations_returns_200(client):
    resp = client.get("/worldmodel/list")
    assert resp.status_code == 200


def test_promote_observation_returns_200(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    resp = client.post(f"/worldmodel/{obs_id}/promote", json={"promote_to": "event"})
    assert resp.status_code == 200


def test_promote_sets_promoted_to_field(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    client.post(f"/worldmodel/{obs_id}/promote", json={"promote_to": "relation"})
    all_obs = client.get("/worldmodel/list").get_json()
    match = next(o for o in all_obs if o["id"] == obs_id)
    assert match["promoted_to"] == "relation"
    assert match["promoted_at"] is not None


def test_promote_returns_400_for_invalid_promote_to(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    resp = client.post(f"/worldmodel/{obs_id}/promote", json={"promote_to": "unknown"})
    assert resp.status_code == 400


def test_promote_returns_404_for_unknown_id(client):
    resp = client.post("/worldmodel/999999/promote", json={"promote_to": "event"})
    assert resp.status_code == 404


def test_delete_observation_returns_200(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    resp = client.delete(f"/worldmodel/{obs_id}")
    assert resp.status_code == 200


def test_delete_observation_removes_from_list(client):
    obs_id = client.post("/worldmodel", json=_OBS).get_json()["id"]
    client.delete(f"/worldmodel/{obs_id}")
    items = client.get("/worldmodel/list").get_json()
    assert not any(o["id"] == obs_id for o in items)


def test_delete_observation_returns_404_for_unknown_id(client):
    resp = client.delete("/worldmodel/999999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_worldmodel.py -v
```
Expected: FAIL with 404.

- [ ] **Step 3: Create `storage/worldmodel_repository.py`**

```python
import json
import sqlite3
from datetime import datetime

_VALID_PROMOTE_TO = {"event", "relation", "prediction"}


def upsert_observation(
    db: sqlite3.Connection,
    category: str,
    pattern: str,
    evidence=None,
    confidence: float = 0.5,
    expires_at: str = None,
) -> dict:
    evidence_json = json.dumps(evidence or [])
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    existing = db.execute(
        "SELECT id, occurrences FROM worldmodel WHERE category = ? AND pattern = ?",
        (category, pattern),
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE worldmodel SET occurrences = occurrences + 1, evidence = ?, "
            "confidence = ?, updated_at = ? WHERE id = ?",
            (evidence_json, confidence, now, existing[0]),
        )
        db.commit()
        obs_id = existing[0]
    else:
        cur = db.execute(
            "INSERT INTO worldmodel (category, pattern, evidence, confidence, expires_at, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (category, pattern, evidence_json, confidence, expires_at, now, now),
        )
        db.commit()
        obs_id = int(cur.lastrowid)

    return _get_observation_by_id(db, obs_id)


def _row_to_observation(row) -> dict:
    return {
        "id": row[0],
        "category": row[1],
        "pattern": row[2],
        "evidence": json.loads(row[3]) if row[3] else [],
        "confidence": row[4],
        "occurrences": row[5],
        "promoted_to": row[6],
        "promoted_at": row[7],
        "expires_at": row[8],
        "created_at": row[9],
        "updated_at": row[10],
    }


def _get_observation_by_id(db: sqlite3.Connection, obs_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, category, pattern, evidence, confidence, occurrences, "
        "promoted_to, promoted_at, expires_at, created_at, updated_at "
        "FROM worldmodel WHERE id = ?",
        (obs_id,),
    ).fetchone()
    return _row_to_observation(row) if row else None


def list_observations(db: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list:
    rows = db.execute(
        "SELECT id, category, pattern, evidence, confidence, occurrences, "
        "promoted_to, promoted_at, expires_at, created_at, updated_at "
        "FROM worldmodel ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [_row_to_observation(r) for r in rows]


def list_active_observations(db: sqlite3.Connection) -> list:
    rows = db.execute(
        "SELECT id, category, pattern, evidence, confidence, occurrences, "
        "promoted_to, promoted_at, expires_at, created_at, updated_at "
        "FROM worldmodel "
        "WHERE promoted_to IS NULL "
        "AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) "
        "ORDER BY confidence DESC, occurrences DESC",
    ).fetchall()
    return [_row_to_observation(r) for r in rows]


def promote_observation(db: sqlite3.Connection, obs_id: int, promote_to: str) -> dict | None:
    if promote_to not in _VALID_PROMOTE_TO:
        return {"invalid": True}
    existing = _get_observation_by_id(db, obs_id)
    if existing is None:
        return None
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE worldmodel SET promoted_to = ?, promoted_at = ?, updated_at = ? WHERE id = ?",
        (promote_to, now, now, obs_id),
    )
    db.commit()
    return _get_observation_by_id(db, obs_id)


def delete_observation(db: sqlite3.Connection, obs_id: int) -> bool:
    cur = db.execute("DELETE FROM worldmodel WHERE id = ?", (obs_id,))
    db.commit()
    return cur.rowcount > 0
```

- [ ] **Step 4: Create `blueprints/worldmodel.py`**

```python
from flask import Blueprint, jsonify, request

from blueprints._params import parse_limit_offset
from db_utils import get_db
from storage.worldmodel_repository import (
    delete_observation,
    list_active_observations,
    list_observations,
    promote_observation,
    upsert_observation,
)

bp = Blueprint("worldmodel", __name__)


@bp.route("/worldmodel", methods=["POST"])
def create_observation():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    category = data.get("category")
    pattern = data.get("pattern")
    if not category or not str(category).strip():
        return jsonify({"error": "category is required"}), 400
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
    obs = upsert_observation(
        db,
        category=str(category).strip(),
        pattern=str(pattern).strip(),
        evidence=data.get("evidence"),
        confidence=confidence,
        expires_at=data.get("expires_at"),
    )
    return jsonify(obs), 201


@bp.route("/worldmodel/active", methods=["GET"])
def active_observations():
    db = get_db()
    return jsonify(list_active_observations(db)), 200


@bp.route("/worldmodel/list", methods=["GET"])
def list_all_observations():
    limit, offset, err_resp, err_status = parse_limit_offset()
    if err_resp is not None:
        return err_resp, err_status
    db = get_db()
    return jsonify(list_observations(db, limit=limit, offset=offset)), 200


@bp.route("/worldmodel/<int:obs_id>/promote", methods=["POST"])
def promote(obs_id: int):
    data = request.get_json(silent=True) or {}
    promote_to = data.get("promote_to")
    if not promote_to:
        return jsonify({"error": "promote_to is required"}), 400
    db = get_db()
    result = promote_observation(db, obs_id, promote_to)
    if result is None:
        return jsonify({"error": "observation not found"}), 404
    if result.get("invalid"):
        return jsonify({"error": "promote_to must be one of: event, relation, prediction"}), 400
    return jsonify(result), 200


@bp.route("/worldmodel/<int:obs_id>", methods=["DELETE"])
def remove_observation(obs_id: int):
    db = get_db()
    deleted = delete_observation(db, obs_id)
    if not deleted:
        return jsonify({"error": "observation not found"}), 404
    return jsonify({"deleted": True}), 200
```

- [ ] **Step 5: Register blueprint in `api_server.py`**

```python
from blueprints.worldmodel import bp as worldmodel_bp
# ...
app.register_blueprint(worldmodel_bp)
```

- [ ] **Step 6: Run world model tests**

```bash
uv run pytest tests/test_worldmodel.py -v
```
Expected: All PASS.

- [ ] **Step 7: Run full test suite — no regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add storage/worldmodel_repository.py blueprints/worldmodel.py api_server.py tests/test_worldmodel.py
git commit -m "feat: add worldmodel soft-observation endpoints with upsert and promote"
```
