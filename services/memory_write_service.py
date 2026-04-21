import json

from storage.memory_repository import get_memory_by_idempotency_key, insert_memory


def parse_memory_payload(data: dict) -> dict:
    if not data:
        raise ValueError("JSON body required")

    name = data.get("name")
    content = data.get("content")
    if not name or not content:
        raise ValueError("name and content are required")

    owner_agent_id = data.get("owner_agent_id")
    if not isinstance(owner_agent_id, str) or not owner_agent_id.strip():
        raise ValueError("owner_agent_id is required")

    visibility = data.get("visibility", "shared")
    if visibility not in {"shared", "private"}:
        raise ValueError("visibility must be 'shared' or 'private'")

    type_ = data.get("type", "note")
    description = data.get("description", "")
    tags = data.get("tags", "")
    if tags is None:
        tags = ""
    if not isinstance(tags, str):
        raise ValueError("tags must be a string")

    run_id = data.get("run_id")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
        raise ValueError("run_id must be a non-empty string when provided")

    idempotency_key = data.get("idempotency_key")
    if idempotency_key is not None and (
        not isinstance(idempotency_key, str) or not idempotency_key.strip()
    ):
        raise ValueError("idempotency_key must be a non-empty string when provided")

    metadata = data.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object when provided")

    try:
        metadata_json = json.dumps(metadata)
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON-serializable") from exc

    return {
        "name": name,
        "content": content,
        "owner_agent_id": owner_agent_id.strip(),
        "visibility": visibility,
        "type": type_,
        "description": description,
        "tags": tags,
        "run_id": run_id.strip() if isinstance(run_id, str) else None,
        "idempotency_key": idempotency_key.strip() if isinstance(idempotency_key, str) else None,
        "metadata_json": metadata_json,
    }


def create_or_get_memory(db, payload: dict) -> dict:
    idempotency_key = payload["idempotency_key"]
    owner_agent_id = payload["owner_agent_id"]
    if idempotency_key:
        existing = get_memory_by_idempotency_key(db, owner_agent_id, idempotency_key)
        if existing is not None:
            return {"id": existing[0], "created": False}

    rowid = insert_memory(
        db,
        payload["name"],
        payload["type"],
        payload["content"],
        payload["description"],
        owner_agent_id=owner_agent_id,
        visibility=payload["visibility"],
        tags=payload["tags"],
        run_id=payload["run_id"],
        idempotency_key=idempotency_key,
        metadata_json=payload["metadata_json"],
    )
    return {"id": rowid, "created": True}
