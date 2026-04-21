# API Documentation Gaps

Gaps discovered while building and testing `agent_memory_client.py`. Each entry
notes the discrepancy, the discovered behavior, and whether the README or code
should be updated to close the gap.

---

## 1. `POST /memory/batch` — `verification_status` silently ignored

**Discovered**: 2026-04-21

**Symptom**: Passing `verification_status: "verified"` in a batch write payload has
no effect. All batch-written memories are stored as `unverified` regardless.

**Actual behavior**: The batch write endpoint ignores `verification_status` and
`verification_source` in the request body and defaults every memory to `unverified`.
Verification requires a separate `POST /memory/verify` call after the batch write.

**Workaround**: Two-pass write — batch write first, then call `/memory/verify` for
each memory that should be marked verified. Implemented in `agent_memory_client.py`.

**Resolution needed**: README should document that `verification_status` is not
accepted by `POST /memory/batch` and that callers must use `POST /memory/verify`
for explicit verification. Alternatively, the endpoint could be extended to accept
and apply `verification_status` during write.

---

## 2. `GET /memory/list` — response is a bare array, not a keyed object

**Discovered**: 2026-04-21

**Symptom**: Calling `response.get("memories", [])` on the list response fails with
`AttributeError: 'list' object has no attribute 'get'`.

**Actual behavior**: The response body is a bare JSON array `[{...}, {...}]`, not a
wrapped object `{"memories": [...]}`. This differs from what one might infer from the
batch write response shape or from the recall endpoint.

**Resolution needed**: README should explicitly document the response shape for
`GET /memory/list` (and confirm whether `recall` and `search` follow the same pattern).

---

## 3. `POST /memory/batch` — response shape not documented

**Discovered**: 2026-04-21

**Symptom**: Ambiguous what the batch write response contains. Initial assumption was
`{"memories": [{"name": "...", "id": 123}]}` but that is incorrect.

**Actual behavior**: Response is `{"results": [{"created": bool, "id": int}]}`. The
results array is positionally aligned with the input `memories` array; there is no
`name` field in each result, so callers must zip results against the input array to
correlate IDs back to names.

**Resolution needed**: README should document the exact batch write response shape,
including the positional alignment between request `memories` and response `results`.

---
