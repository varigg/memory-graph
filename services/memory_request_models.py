from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictFloat,
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


class GoalCreatePayload(_BaseRequestModel):
    title: StrictStr
    owner_agent_id: StrictStr
    status: Literal["active", "blocked", "completed", "abandoned"] = "active"
    utility: StrictFloat | StrictInt = 0
    deadline: StrictStr | None = None
    constraints: dict[str, Any] | None = None
    success_criteria: dict[str, Any] | None = None
    risk_tier: Literal["low", "medium", "high", "critical"] = "low"
    autonomy_level_requested: StrictInt = 0
    autonomy_level_effective: StrictInt | None = None
    run_id: StrictStr | None = None
    idempotency_key: StrictStr | None = None


class GoalStatusPayload(_BaseRequestModel):
    owner_agent_id: StrictStr
    status: Literal["active", "blocked", "completed", "abandoned"]
    reason: StrictStr | None = None


class ActionLogCreatePayload(_BaseRequestModel):
    goal_id: StrictInt
    parent_action_id: StrictInt | None = None
    action_type: StrictStr
    tool_name: StrictStr | None = None
    mode: Literal["plan", "dry_run", "live", "rollback"]
    status: Literal["queued", "running", "succeeded", "failed", "rolled_back"]
    input_summary: StrictStr | None = None
    expected_result: StrictStr | None = None
    observed_result: StrictStr | None = None
    rollback_action_id: StrictInt | None = None
    owner_agent_id: StrictStr
    run_id: StrictStr | None = None
    idempotency_key: StrictStr | None = None


class ActionLogCompletePayload(_BaseRequestModel):
    owner_agent_id: StrictStr
    status: Literal["succeeded", "failed", "rolled_back"]
    observed_result: StrictStr | None = None
    rollback_action_id: StrictInt | None = None


class AutonomyCheckpointPayload(_BaseRequestModel):
    requested_level: StrictInt
    approved_level: StrictInt
    verdict: Literal["approved", "denied", "sandbox_only"]
    owner_agent_id: StrictStr
    goal_id: StrictInt | None = None
    action_id: StrictInt | None = None
    rationale: StrictStr | None = None
    stop_conditions: dict[str, Any] | None = None
    rollback_required: StrictBool = False
    reviewer_type: Literal["policy", "human", "system"] = "system"
    run_id: StrictStr | None = None
    idempotency_key: StrictStr | None = None


def _serialize_json_object(value: dict[str, Any], field_name: str) -> str:
    try:
        return json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-serializable") from exc


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
    if payload.memory_id <= 0:
        raise ValueError("memory_id must be a positive integer")
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

    if payload.memory_id <= 0:
        raise ValueError("memory_id must be a positive integer")

    target_memory_id = payload.target_memory_id
    if target_memory_id is None:
        target_memory_id = payload.replacement_memory_id
    if target_memory_id is None:
        raise ValueError("target_memory_id must be an integer")
    if target_memory_id <= 0:
        raise ValueError("target_memory_id must be a positive integer")

    return {
        "memory_id": payload.memory_id,
        "target_memory_id": target_memory_id,
        "agent_id": payload.agent_id.strip(),
    }


def parse_goal_create_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = GoalCreatePayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "title" in fields:
            raise ValueError("title is required") from exc
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id is required") from exc
        if "status" in fields:
            raise ValueError("status must be one of: active, blocked, completed, abandoned") from exc
        if "utility" in fields:
            raise ValueError("utility must be a number") from exc
        if "constraints" in fields:
            raise ValueError("constraints must be an object when provided") from exc
        if "success_criteria" in fields:
            raise ValueError("success_criteria must be an object when provided") from exc
        if "risk_tier" in fields:
            raise ValueError("risk_tier must be one of: low, medium, high, critical") from exc
        if "autonomy_level_requested" in fields or "autonomy_level_effective" in fields:
            raise ValueError("autonomy levels must be integers") from exc
        if "run_id" in fields:
            raise ValueError("run_id must be a non-empty string when provided") from exc
        if "idempotency_key" in fields:
            raise ValueError("idempotency_key must be a non-empty string when provided") from exc
        raise ValueError("invalid request payload") from exc

    title = payload.title.strip()
    if not title:
        raise ValueError("title is required")

    owner_agent_id = payload.owner_agent_id.strip()
    if not owner_agent_id:
        raise ValueError("owner_agent_id is required")

    run_id = payload.run_id.strip() if payload.run_id is not None else None
    if payload.run_id is not None and not run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    idempotency_key = payload.idempotency_key.strip() if payload.idempotency_key is not None else None
    if payload.idempotency_key is not None and not idempotency_key:
        raise ValueError("idempotency_key must be a non-empty string when provided")

    requested_level = payload.autonomy_level_requested
    if requested_level < 0 or requested_level > 5:
        raise ValueError("autonomy_level_requested must be between 0 and 5")

    effective_level = payload.autonomy_level_effective
    if effective_level is None:
        effective_level = requested_level
    if effective_level < 0 or effective_level > 5:
        raise ValueError("autonomy_level_effective must be between 0 and 5")

    constraints = payload.constraints if payload.constraints is not None else {}
    success_criteria = payload.success_criteria if payload.success_criteria is not None else {}

    deadline = payload.deadline.strip() if payload.deadline is not None else None
    if payload.deadline is not None and not deadline:
        raise ValueError("deadline must be a non-empty string when provided")

    return {
        "title": title,
        "owner_agent_id": owner_agent_id,
        "status": payload.status,
        "utility": float(payload.utility),
        "deadline": deadline,
        "constraints_json": _serialize_json_object(constraints, "constraints"),
        "success_criteria_json": _serialize_json_object(success_criteria, "success_criteria"),
        "risk_tier": payload.risk_tier,
        "autonomy_level_requested": requested_level,
        "autonomy_level_effective": effective_level,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
    }


def parse_goal_status_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = GoalStatusPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id is required") from exc
        if "status" in fields:
            raise ValueError("status must be one of: active, blocked, completed, abandoned") from exc
        if "reason" in fields:
            raise ValueError("reason must be a string when provided") from exc
        raise ValueError("invalid request payload") from exc

    owner_agent_id = payload.owner_agent_id.strip()
    if not owner_agent_id:
        raise ValueError("owner_agent_id is required")

    reason = payload.reason
    if reason is not None:
        reason = reason.strip()
        if not reason:
            reason = None

    return {
        "owner_agent_id": owner_agent_id,
        "status": payload.status,
        "reason": reason,
    }


def parse_action_log_create_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = ActionLogCreatePayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "goal_id" in fields or "parent_action_id" in fields or "rollback_action_id" in fields:
            raise ValueError("goal_id, parent_action_id, and rollback_action_id must be integers") from exc
        if "action_type" in fields:
            raise ValueError("action_type is required") from exc
        if "mode" in fields:
            raise ValueError("mode must be one of: plan, dry_run, live, rollback") from exc
        if "status" in fields:
            raise ValueError("status must be one of: queued, running, succeeded, failed, rolled_back") from exc
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id is required") from exc
        if "run_id" in fields:
            raise ValueError("run_id must be a non-empty string when provided") from exc
        if "idempotency_key" in fields:
            raise ValueError("idempotency_key must be a non-empty string when provided") from exc
        raise ValueError("invalid request payload") from exc

    action_type = payload.action_type.strip()
    if not action_type:
        raise ValueError("action_type is required")

    owner_agent_id = payload.owner_agent_id.strip()
    if not owner_agent_id:
        raise ValueError("owner_agent_id is required")

    if payload.goal_id <= 0:
        raise ValueError("goal_id must be a positive integer")
    if payload.parent_action_id is not None and payload.parent_action_id <= 0:
        raise ValueError("parent_action_id must be a positive integer when provided")
    if payload.rollback_action_id is not None and payload.rollback_action_id <= 0:
        raise ValueError("rollback_action_id must be a positive integer when provided")

    run_id = payload.run_id.strip() if payload.run_id is not None else None
    if payload.run_id is not None and not run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    idempotency_key = payload.idempotency_key.strip() if payload.idempotency_key is not None else None
    if payload.idempotency_key is not None and not idempotency_key:
        raise ValueError("idempotency_key must be a non-empty string when provided")

    def _normalize_optional(value: str | None):
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    return {
        "goal_id": payload.goal_id,
        "parent_action_id": payload.parent_action_id,
        "action_type": action_type,
        "tool_name": _normalize_optional(payload.tool_name),
        "mode": payload.mode,
        "status": payload.status,
        "input_summary": _normalize_optional(payload.input_summary),
        "expected_result": _normalize_optional(payload.expected_result),
        "observed_result": _normalize_optional(payload.observed_result),
        "rollback_action_id": payload.rollback_action_id,
        "owner_agent_id": owner_agent_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
    }


def parse_action_log_complete_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = ActionLogCompletePayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id is required") from exc
        if "status" in fields:
            raise ValueError("status must be one of: succeeded, failed, rolled_back") from exc
        if "rollback_action_id" in fields:
            raise ValueError("rollback_action_id must be an integer") from exc
        raise ValueError("invalid request payload") from exc

    owner_agent_id = payload.owner_agent_id.strip()
    if not owner_agent_id:
        raise ValueError("owner_agent_id is required")

    if payload.rollback_action_id is not None and payload.rollback_action_id <= 0:
        raise ValueError("rollback_action_id must be a positive integer when provided")

    observed_result = payload.observed_result
    if observed_result is not None:
        observed_result = observed_result.strip()
        if not observed_result:
            observed_result = None

    return {
        "owner_agent_id": owner_agent_id,
        "status": payload.status,
        "observed_result": observed_result,
        "rollback_action_id": payload.rollback_action_id,
    }


def parse_autonomy_checkpoint_payload(data: Any) -> dict:
    body = _require_json_body(data)
    try:
        payload = AutonomyCheckpointPayload.model_validate(body)
    except ValidationError as exc:
        fields = {".".join(str(part) for part in e["loc"]) for e in exc.errors()}
        if "requested_level" in fields or "approved_level" in fields:
            raise ValueError("requested_level and approved_level must be integers") from exc
        if "verdict" in fields:
            raise ValueError("verdict must be one of: approved, denied, sandbox_only") from exc
        if "owner_agent_id" in fields:
            raise ValueError("owner_agent_id is required") from exc
        if "goal_id" in fields or "action_id" in fields:
            raise ValueError("goal_id and action_id must be integers when provided") from exc
        if "stop_conditions" in fields:
            raise ValueError("stop_conditions must be an object when provided") from exc
        if "rollback_required" in fields:
            raise ValueError("rollback_required must be a boolean when provided") from exc
        if "reviewer_type" in fields:
            raise ValueError("reviewer_type must be one of: policy, human, system") from exc
        if "run_id" in fields:
            raise ValueError("run_id must be a non-empty string when provided") from exc
        if "idempotency_key" in fields:
            raise ValueError("idempotency_key must be a non-empty string when provided") from exc
        raise ValueError("invalid request payload") from exc

    owner_agent_id = payload.owner_agent_id.strip()
    if not owner_agent_id:
        raise ValueError("owner_agent_id is required")

    if payload.goal_id is not None and payload.goal_id <= 0:
        raise ValueError("goal_id must be a positive integer when provided")
    if payload.action_id is not None and payload.action_id <= 0:
        raise ValueError("action_id must be a positive integer when provided")

    if payload.requested_level < 0 or payload.requested_level > 5:
        raise ValueError("requested_level must be between 0 and 5")
    if payload.approved_level < 0 or payload.approved_level > 5:
        raise ValueError("approved_level must be between 0 and 5")
    if payload.approved_level > payload.requested_level:
        raise ValueError("approved_level must be <= requested_level")

    run_id = payload.run_id.strip() if payload.run_id is not None else None
    if payload.run_id is not None and not run_id:
        raise ValueError("run_id must be a non-empty string when provided")

    idempotency_key = payload.idempotency_key.strip() if payload.idempotency_key is not None else None
    if payload.idempotency_key is not None and not idempotency_key:
        raise ValueError("idempotency_key must be a non-empty string when provided")

    rationale = payload.rationale.strip() if payload.rationale is not None else None
    if payload.rationale is not None and not rationale:
        rationale = None

    stop_conditions = payload.stop_conditions if payload.stop_conditions is not None else {}

    return {
        "goal_id": payload.goal_id,
        "action_id": payload.action_id,
        "requested_level": payload.requested_level,
        "approved_level": payload.approved_level,
        "verdict": payload.verdict,
        "rationale": rationale,
        "stop_conditions_json": _serialize_json_object(stop_conditions, "stop_conditions"),
        "rollback_required": payload.rollback_required,
        "reviewer_type": payload.reviewer_type,
        "owner_agent_id": owner_agent_id,
        "run_id": run_id,
        "idempotency_key": idempotency_key,
    }
