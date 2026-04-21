from flask import jsonify, request

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def parse_limit_offset():
    raw_limit = request.args.get("limit")
    raw_offset = request.args.get("offset")
    try:
        limit = int(raw_limit) if raw_limit is not None else _DEFAULT_LIMIT
        offset = int(raw_offset) if raw_offset is not None else 0
    except ValueError:
        return None, None, jsonify({"error": "limit and offset must be integers"}), 400
    if limit <= 0:
        return None, None, jsonify({"error": "limit must be a positive integer"}), 400
    if offset < 0:
        return None, None, jsonify({"error": "offset must be a non-negative integer"}), 400
    return min(limit, _MAX_LIMIT), offset, None, None


def parse_scope_flags():
    shared_only_str = request.args.get("shared_only", "false").lower()
    private_only_str = request.args.get("private_only", "false").lower()

    shared_only = shared_only_str == "true"
    private_only = private_only_str == "true"

    if shared_only and private_only:
        return None, None, jsonify({"error": "Cannot specify both shared_only and private_only"}), 400

    return shared_only, private_only, None, None


def parse_read_filters():
    def _err(message):
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            jsonify({"error": message}),
            400,
        )

    visibility = request.args.get("visibility")
    owner_agent_id = request.args.get("owner_agent_id")
    status = request.args.get("status", "active")

    if visibility is not None and visibility not in {"shared", "private"}:
        return _err("visibility must be 'shared' or 'private'")

    if status not in {"active", "archived", "invalidated"}:
        return _err("status must be 'active', 'archived', or 'invalidated'")

    if owner_agent_id is not None and not owner_agent_id.strip():
        return _err("owner_agent_id must be non-empty")

    normalized_owner = owner_agent_id.strip() if owner_agent_id is not None else None
    run_id = request.args.get("run_id")
    normalized_run_id = run_id.strip() if run_id is not None and run_id.strip() else None

    tag = request.args.get("tag")
    normalized_tag = tag.strip() if tag is not None and tag.strip() else None

    min_confidence = request.args.get("min_confidence")
    parsed_min_confidence = None
    if min_confidence is not None:
        try:
            parsed_min_confidence = float(min_confidence)
        except ValueError:
            return _err("min_confidence must be a number")
        if parsed_min_confidence < 0.0 or parsed_min_confidence > 1.0:
            return _err("min_confidence must be between 0 and 1")

    updated_since = request.args.get("updated_since")
    normalized_updated_since = (
        updated_since.strip() if updated_since is not None and updated_since.strip() else None
    )

    recency_half_life_hours = request.args.get("recency_half_life_hours")
    parsed_recency_half_life_hours = None
    if recency_half_life_hours is not None:
        try:
            parsed_recency_half_life_hours = float(recency_half_life_hours)
        except ValueError:
            return _err("recency_half_life_hours must be a number")
        if parsed_recency_half_life_hours <= 0:
            return _err("recency_half_life_hours must be > 0")

    metadata_key = request.args.get("metadata_key")
    normalized_metadata_key = (
        metadata_key.strip() if metadata_key is not None and metadata_key.strip() else None
    )

    metadata_value_raw = request.args.get("metadata_value")
    metadata_value_type = request.args.get("metadata_value_type", "string")
    parsed_metadata_value = None
    parsed_metadata_value_type = None
    if normalized_metadata_key is not None:
        allowed_types = {"string", "number", "boolean", "null"}
        if metadata_value_type not in allowed_types:
            return _err("metadata_value_type must be one of: string, number, boolean, null")
        parsed_metadata_value_type = metadata_value_type

        if metadata_value_raw is not None:
            if metadata_value_type == "string":
                parsed_metadata_value = metadata_value_raw
            elif metadata_value_type == "number":
                try:
                    parsed_metadata_value = float(metadata_value_raw)
                except ValueError:
                    return _err("metadata_value must be numeric when metadata_value_type=number")
            elif metadata_value_type == "boolean":
                lowered = metadata_value_raw.lower()
                if lowered not in {"true", "false"}:
                    return _err("metadata_value must be true or false when metadata_value_type=boolean")
                parsed_metadata_value = lowered == "true"
            elif metadata_value_type == "null":
                parsed_metadata_value = None
        elif metadata_value_type == "null":
            parsed_metadata_value = None

    return (
        visibility,
        normalized_owner,
        status,
        normalized_run_id,
        normalized_tag,
        parsed_min_confidence,
        normalized_updated_since,
        parsed_recency_half_life_hours,
        normalized_metadata_key,
        parsed_metadata_value,
        parsed_metadata_value_type,
        None,
        None,
    )
