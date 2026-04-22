from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
)


def _require_json_body(data: Any) -> dict:
    if not isinstance(data, dict) or not data:
        raise ValueError("JSON body required")
    return data


class _BaseRequestModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MemoryActionPayload(_BaseRequestModel):
    memory_id: StrictInt
    agent_id: StrictStr


class MemoryVerifyPayload(MemoryActionPayload):
    verification_status: Literal["unverified", "verified", "disputed"]
    verification_source: StrictStr | None = None


class MemoryCleanupPayload(_BaseRequestModel):
    retention_days: StrictInt
    dry_run: StrictBool = True
    owner_agent_id: StrictStr | None = None
    status: Literal["active", "archived", "invalidated", "all"] = "active"


class MemoryRelationPayload(_BaseRequestModel):
    memory_id: StrictInt
    target_memory_id: StrictInt | None = None
    replacement_memory_id: StrictInt | None = None
    agent_id: StrictStr


def parse_action_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = MemoryActionPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "memory_id" in fields:
            raise ValueError("memory_id must be an integer") from exc
        if "agent_id" in fields:
            raise ValueError("agent_id is required") from exc
        raise ValueError("invalid request payload") from exc
    if not payload.agent_id.strip():
        raise ValueError("agent_id is required")
    return {
        "memory_id": payload.memory_id,
        "agent_id": payload.agent_id.strip(),
    }


def parse_verify_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = MemoryVerifyPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "memory_id" in fields:
            raise ValueError("memory_id must be an integer") from exc
        if "agent_id" in fields:
            raise ValueError("agent_id is required") from exc
        if "verification_status" in fields:
            raise ValueError("verification_status must be 'unverified', 'verified', or 'disputed'") from exc
        if "verification_source" in fields:
            raise ValueError("verification_source must be a string when provided") from exc
        raise ValueError("invalid request payload") from exc
    if not payload.agent_id.strip():
        raise ValueError("agent_id is required")
    return {
        "memory_id": payload.memory_id,
        "agent_id": payload.agent_id.strip(),
        "verification_status": payload.verification_status,
        "verification_source": payload.verification_source,
    }


def parse_cleanup_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = MemoryCleanupPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "retention_days" in fields:
            raise ValueError("retention_days must be an integer") from exc
        if "dry_run" in fields:
            raise ValueError("dry_run must be a boolean when provided") from exc
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id must be a string when provided") from exc
        if "status" in fields:
            raise ValueError("status must be a string when provided") from exc
        raise ValueError("invalid request payload") from exc
    owner = payload.owner_agent_id
    if owner is not None and not owner.strip():
        raise ValueError("owner_agent_id must be non-empty when provided")
    return {
        "retention_days": payload.retention_days,
        "dry_run": payload.dry_run,
        "owner_agent_id": owner.strip() if owner is not None else None,
        "status": payload.status,
    }


def parse_relation_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = MemoryRelationPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "memory_id" in fields:
            raise ValueError("memory_id must be an integer") from exc
        if "target_memory_id" in fields or "replacement_memory_id" in fields:
            raise ValueError("target_memory_id must be an integer") from exc
        if "agent_id" in fields:
            raise ValueError("agent_id is required") from exc
        raise ValueError("invalid request payload") from exc

    if not payload.agent_id.strip():
        raise ValueError("agent_id is required")

    target_memory_id = payload.target_memory_id
    if target_memory_id is None:
        target_memory_id = payload.replacement_memory_id
    if target_memory_id is None:
        raise ValueError("target_memory_id must be an integer")

    return {
        "memory_id": payload.memory_id,
        "target_memory_id": target_memory_id,
        "agent_id": payload.agent_id.strip(),
    }
