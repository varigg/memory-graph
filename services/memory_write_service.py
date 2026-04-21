import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from storage.memory_repository import get_memory_by_idempotency_key, insert_memory


class MemoryCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: StrictStr | None = None
    type: StrictStr = "note"
    content: StrictStr | None = None
    description: StrictStr = ""
    owner_agent_id: StrictStr | None = None
    visibility: Literal["shared", "private"] = "shared"
    tags: StrictStr | None = ""
    run_id: StrictStr | None = None
    idempotency_key: StrictStr | None = None
    metadata: dict[str, Any] | None = None


def parse_memory_payload(data: dict) -> dict:
    if not isinstance(data, dict) or not data:
        raise ValueError("JSON body required")

    try:
        payload = MemoryCreatePayload.model_validate(data)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "visibility" in fields:
            raise ValueError("visibility must be 'shared' or 'private'") from exc
        if "tags" in fields:
            raise ValueError("tags must be a string") from exc
        if "run_id" in fields:
            raise ValueError("run_id must be a non-empty string when provided") from exc
        if "idempotency_key" in fields:
            raise ValueError("idempotency_key must be a non-empty string when provided") from exc
        if "metadata" in fields:
            raise ValueError("metadata must be an object when provided") from exc
        raise ValueError("invalid request payload") from exc

    name = payload.name
    content = payload.content
    if not name or not content:
        raise ValueError("name and content are required")

    owner_agent_id = payload.owner_agent_id
    if not isinstance(owner_agent_id, str) or not owner_agent_id.strip():
        raise ValueError("owner_agent_id is required")

    visibility = payload.visibility
    if visibility not in {"shared", "private"}:
        raise ValueError("visibility must be 'shared' or 'private'")

    type_ = payload.type
    description = payload.description
    tags = payload.tags
    if tags is None:
        tags = ""
    if not isinstance(tags, str):
        raise ValueError("tags must be a string")

    run_id = payload.run_id
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip()):
        raise ValueError("run_id must be a non-empty string when provided")

    idempotency_key = payload.idempotency_key
    if idempotency_key is not None and (
        not isinstance(idempotency_key, str) or not idempotency_key.strip()
    ):
        raise ValueError("idempotency_key must be a non-empty string when provided")

    metadata = payload.metadata if payload.metadata is not None else {}
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
