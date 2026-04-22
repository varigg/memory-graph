# API Documentation Gaps

Gaps discovered while building and testing `agent_memory_client.py`.

Status legend:

- `open`: documentation does not yet match runtime behavior
- `resolved`: README now reflects observed behavior

---

## 1. `POST /memory/batch` — `verification_status` silently ignored

**Status**: resolved

**Discovered**: 2026-04-21

**Symptom**: Passing `verification_status: "verified"` in a batch write payload has
no effect. All batch-written memories are stored as `unverified` regardless.

**Actual behavior**: The batch write endpoint ignores `verification_status` and
`verification_source` in the request body and defaults every memory to `unverified`.
Verification requires a separate `POST /memory/verify` call after the batch write.

**Workaround**: Two-pass write — batch write first, then call `/memory/verify` for
each memory that should be marked verified. Implemented in `agent_memory_client.py`.

**Resolution applied**: README now documents that batch writes default to
`verification_status=unverified` and that callers should use `POST /memory/verify`
for confirmed memories.

---

## 2. `GET /memory/list` — response is a bare array, not a keyed object

**Status**: resolved

**Discovered**: 2026-04-21

**Symptom**: Calling `response.get("memories", [])` on the list response fails with
`AttributeError: 'list' object has no attribute 'get'`.

**Actual behavior**: The response body is a bare JSON array `[{...}, {...}]`, not a
wrapped object `{"memories": [...]}`. This differs from what one might infer from the
batch write response shape or from the recall endpoint.

**Resolution applied**: README now documents that `GET /memory/list`,
`GET /memory/recall`, and `GET /memory/search` return a bare JSON array.

---

## 3. `POST /memory/batch` — response shape not documented

**Status**: resolved

**Discovered**: 2026-04-21

**Symptom**: Ambiguous what the batch write response contains. Initial assumption was
`{"memories": [{"name": "...", "id": 123}]}` but that is incorrect.

**Actual behavior**: Response is `{"results": [{"created": bool, "id": int}]}`. The
results array is positionally aligned with the input `memories` array; there is no
`name` field in each result, so callers must zip results against the input array to
correlate IDs back to names.

**Resolution applied**: README now documents the batch response shape as
`{"results": [{"id": <int>, "created": <bool>}, ...]}` and calls out positional
alignment with request `memories`.

---
