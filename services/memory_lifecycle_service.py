import sqlite3
from datetime import UTC, datetime, timedelta

from db_utils import write_transaction
from storage.memory_repository import (
    delete_memories_by_ids,
    list_stale_private_memories,
)


def set_memory_verification(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
    verification_status: str,
    verification_source: str = None,
):
    row = db.execute(
        "SELECT id, owner_agent_id FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    if verification_status not in {"unverified", "verified", "disputed"}:
        return None, "invalid_status"

    if verification_status == "verified":
        with write_transaction(db):
            db.execute(
                "UPDATE memories "
                "SET verification_status = ?, verification_source = ?, verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (verification_status, verification_source, memory_id),
            )
    else:
        with write_transaction(db):
            db.execute(
                "UPDATE memories "
                "SET verification_status = ?, verification_source = ?, verified_at = NULL, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (verification_status, verification_source, memory_id),
            )
    return {
        "id": memory_id,
        "verification_status": verification_status,
        "verification_source": verification_source,
    }, None


def promote_memory_to_shared(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
):
    row = db.execute(
        "SELECT id, owner_agent_id FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    with write_transaction(db):
        db.execute(
            "UPDATE memories "
            "SET visibility = 'shared', updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (memory_id,),
        )
    return {"id": row[0], "visibility": "shared"}, None


def transition_memory_status(
    db: sqlite3.Connection,
    memory_id: int,
    requester_agent_id: str,
    target_status: str,
):
    row = db.execute(
        "SELECT id, owner_agent_id, status FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if row is None:
        return None, "not_found"
    if row[1] != requester_agent_id:
        return None, "forbidden"

    current_status = row[2] or "active"
    if current_status == target_status:
        return {"id": row[0], "status": current_status}, None

    if target_status not in {"archived", "invalidated"}:
        return None, "invalid_status"

    if current_status == "invalidated":
        return None, "invalid_transition"
    if current_status == "archived" and target_status == "archived":
        return {"id": row[0], "status": current_status}, None

    with write_transaction(db):
        db.execute(
            "UPDATE memories "
            "SET status = ?, updated_at = CURRENT_TIMESTAMP, status_updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (target_status, memory_id),
        )
    return {"id": row[0], "status": target_status}, None


def relate_memory_lifecycle(
    db: sqlite3.Connection,
    memory_id: int,
    target_memory_id: int,
    requester_agent_id: str,
    relation_type: str,
):
    if memory_id == target_memory_id:
        return None, "same_memory"

    if relation_type not in {"merged_into", "superseded_by"}:
        return None, "invalid_relation"

    source_row = db.execute(
        "SELECT id, owner_agent_id, visibility, status FROM memories WHERE id = ?",
        (memory_id,),
    ).fetchone()
    if source_row is None:
        return None, "source_not_found"

    target_row = db.execute(
        "SELECT id, owner_agent_id, visibility, status FROM memories WHERE id = ?",
        (target_memory_id,),
    ).fetchone()
    if target_row is None:
        return None, "target_not_found"

    if source_row[1] != requester_agent_id:
        return None, "forbidden"

    if target_row[2] == "private" and target_row[1] != requester_agent_id:
        return None, "forbidden"

    source_status = source_row[3] or "active"
    target_status = target_row[3] or "active"
    if source_status != "active" or target_status != "active":
        return None, "invalid_transition"

    existing = db.execute(
        "SELECT id FROM memory_relations "
        "WHERE source_memory_id = ? AND target_memory_id = ? AND relation_type = ?",
        (memory_id, target_memory_id, relation_type),
    ).fetchone()

    if existing is not None:
        source_status_value = "archived" if relation_type == "merged_into" else "invalidated"
        return {
            "source_memory_id": memory_id,
            "target_memory_id": target_memory_id,
            "relation_type": relation_type,
            "source_status": source_status_value,
        }, None

    source_status_value = "archived" if relation_type == "merged_into" else "invalidated"

    with write_transaction(db):
        db.execute(
            "INSERT INTO memory_relations ("
            "source_memory_id, target_memory_id, relation_type, actor_agent_id"
            ") VALUES (?, ?, ?, ?)",
            (memory_id, target_memory_id, relation_type, requester_agent_id),
        )
        db.execute(
            "UPDATE memories "
            "SET status = ?, updated_at = CURRENT_TIMESTAMP, status_updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (source_status_value, memory_id),
        )
        db.execute(
            "UPDATE memories "
            "SET updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (target_memory_id,),
        )
    return {
        "source_memory_id": memory_id,
        "target_memory_id": target_memory_id,
        "relation_type": relation_type,
        "source_status": source_status_value,
    }, None


def cleanup_stale_private_memories(
    db: sqlite3.Connection,
    retention_days: int,
    dry_run: bool = True,
    owner_agent_id: str = None,
    status: str = "active",
):
    if retention_days <= 0:
        return None, "invalid_retention_days"
    if status not in {"active", "archived", "invalidated", "all"}:
        return None, "invalid_status"
    if owner_agent_id is not None and not owner_agent_id.strip():
        return None, "invalid_owner_agent_id"

    normalized_owner = owner_agent_id.strip() if owner_agent_id is not None else None
    cutoff_dt = datetime.now(UTC) - timedelta(days=retention_days)
    cutoff_timestamp = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    stale_rows = list_stale_private_memories(
        db,
        cutoff_timestamp=cutoff_timestamp,
        owner_agent_id=normalized_owner,
        status=status,
    )
    stale_ids = [int(r["id"]) for r in stale_rows]

    deleted_count = 0
    if not dry_run:
        with write_transaction(db):
            deleted_count = delete_memories_by_ids(db, stale_ids)

    return {
        "dry_run": dry_run,
        "retention_days": retention_days,
        "cutoff_timestamp": cutoff_timestamp,
        "owner_agent_id": normalized_owner,
        "status": status,
        "candidate_count": len(stale_ids),
        "deleted_count": deleted_count,
        "candidate_ids": stale_ids,
    }, None
