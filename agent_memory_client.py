"""
Wrapper for memory-graph API operations.

Provides simplified interfaces for Copilot's task-end batch writes and recovery queries.
Auto-fills boilerplate fields (owner_agent_id, visibility, idempotency_key, verification_status)
and handles health checks, error handling, and retry logic.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from typing import TypedDict


class Finding(TypedDict, total=False):
    """A finding/decision/learning to batch-write."""

    name: str  # Required: slug e.g. "learning/test-coverage-gap"
    content: str  # Required: finding text
    type: str  # Required: "finding", "decision", "learning", etc.
    tags: str  # Required: comma-separated lowercase tags
    verified: bool  # Required: True if task-verified, False if needs review
    verification_source: str  # Optional if verified=True, recommended


class MemoryWriteResult(TypedDict):
    """Result of a batch write."""

    name: str
    memory_id: int


class CheckpointMemory(TypedDict, total=False):
    """A memory retrieved from a checkpoint query."""

    name: str
    content: str
    type: str
    tags: str
    verification_status: str
    created_at: str


API_BASE = "http://localhost:7777"
OWNER_AGENT_ID = "copilot"


def _health_check() -> bool:
    """Check if the memory-graph API is healthy."""
    try:
        req = urllib.request.Request(f"{API_BASE}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("status") == "ok"
    except Exception as e:
        print(f"Health check failed: {e}", file=sys.stderr)
        return False


def _make_idempotency_key(run_id: str, name: str) -> str:
    """
    Generate a deterministic idempotency key.

    Format: copilot:<run_id>:<name_hash>
    This ensures the same finding in the same run always produces the same key,
    preventing duplicates on retry.
    """
    name_hash = hashlib.sha256(name.encode()).hexdigest()[:12]
    return f"{OWNER_AGENT_ID}:{run_id}:{name_hash}"


def _verify_memory(memory_id: int, verification_source: str) -> None:
    """
    Mark a memory as verified with a given source.

    Separate API call after batch write (batch write doesn't accept verification_status).
    """
    payload = {
        "memory_id": memory_id,
        "agent_id": OWNER_AGENT_ID,
        "verification_status": "verified",
        "verification_source": verification_source,
    }
    req = urllib.request.Request(
        f"{API_BASE}/memory/verify",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()  # Consume response
    except Exception as e:
        # Log but don't fail the whole batch if verification fails
        print(f"Warning: Failed to verify memory {memory_id}: {e}", file=sys.stderr)


def batch_write_findings(findings: list[Finding], run_id: str) -> list[MemoryWriteResult]:
    """
    Batch-write validated findings at task end.

    Args:
        findings: List of findings with name, content, type, tags, verified, verification_source
        run_id: Correlation ID for this task (e.g. "run-2026-04-21-analysis")

    Returns:
        List of (name, memory_id) results for tracking

    Raises:
        RuntimeError: If API is unavailable or write fails
    """
    if not _health_check():
        raise RuntimeError("Memory-graph API health check failed. Is it running on localhost:7777?")

    if not findings:
        return []

    # Validate required fields
    for finding in findings:
        if not finding.get("name"):
            raise ValueError("Each finding must have a 'name' (slug)")
        if not finding.get("content"):
            raise ValueError("Each finding must have 'content'")
        if not finding.get("type"):
            raise ValueError("Each finding must have a 'type'")
        if not finding.get("tags"):
            raise ValueError("Each finding must have 'tags'")
        if "verified" not in finding:
            raise ValueError("Each finding must have 'verified' (True/False)")

    # Transform findings into API format (note: verification_status not accepted in batch write)
    api_memories = []
    verification_updates = []  # Track which ones need verify() calls
    for finding in findings:
        verified = finding["verified"]
        api_finding = {
            "name": finding["name"],
            "content": finding["content"],
            "type": finding["type"],
            "tags": finding["tags"],
            "owner_agent_id": OWNER_AGENT_ID,
            "visibility": "shared",
            "run_id": run_id,
            "idempotency_key": _make_idempotency_key(run_id, finding["name"]),
        }

        api_memories.append(api_finding)

        # Track findings that need verification
        if verified and "verification_source" in finding:
            verification_updates.append((finding["name"], verified, finding["verification_source"]))

    # POST to /memory/batch
    payload = {"memories": api_memories}
    req = urllib.request.Request(
        f"{API_BASE}/memory/batch",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            response_data = json.loads(resp.read().decode())
            # API returns {"results": [{"created": true/false, "id": 123}, ...]}
            results = []
            for idx, result in enumerate(response_data.get("results", [])):
                if idx < len(api_memories):
                    results.append({"name": api_memories[idx]["name"], "memory_id": result["id"]})
            
            # Now verify the ones marked as verified (requires separate API call)
            for idx, (name, _, verification_source) in enumerate(verification_updates):
                if idx < len(results) and results[idx]["name"] == name:
                    memory_id = results[idx]["memory_id"]
                    _verify_memory(memory_id, verification_source)
            
            return results
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"Batch write failed ({e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"Batch write error: {e}")


def get_run_checkpoint(run_id: str, limit: int = 10) -> list[CheckpointMemory]:
    """
    Retrieve checkpoints from a prior run for recovery at task restart.

    Args:
        run_id: The run ID to query (e.g. "run-2026-04-21-analysis")
        limit: Max results to return (default 10, most recent first)

    Returns:
        List of checkpoint memories with name, content, verification_status, tags, etc.

    Raises:
        RuntimeError: If API is unavailable or query fails
    """
    if not _health_check():
        raise RuntimeError("Memory-graph API health check failed. Is it running on localhost:7777?")

    # Query /memory/list with run_id filter
    query_url = f"{API_BASE}/memory/list?agent_id={OWNER_AGENT_ID}&run_id={run_id}&status=active&limit={limit}"
    req = urllib.request.Request(query_url)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            response_data = json.loads(resp.read().decode())
            # API returns a list directly: [{...}, {...}]
            memories = []
            for mem in response_data:
                memories.append(
                    {
                        "name": mem["name"],
                        "content": mem["content"],
                        "type": mem.get("type"),
                        "tags": mem.get("tags"),
                        "verification_status": mem.get("verification_status"),
                        "created_at": mem.get("timestamp"),
                    }
                )
            return memories
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"Checkpoint query failed ({e.code}): {error_body}")
    except Exception as e:
        raise RuntimeError(f"Checkpoint query error: {e}")


def print_checkpoint_summary(checkpoint: list[CheckpointMemory]) -> None:
    """
    Pretty-print a checkpoint for task restart context.

    Useful for understanding where a prior session left off.
    """
    if not checkpoint:
        print("No prior checkpoint found for this run.")
        return

    print(f"\n{'=' * 80}")
    print(f"Checkpoint Summary: {len(checkpoint)} findings from prior session")
    print(f"{'=' * 80}\n")

    for mem in checkpoint:
        status_indicator = "✓" if mem.get("verification_status") == "verified" else "○"
        print(f"{status_indicator} [{mem['type']}] {mem['name']}")
        print(f"  Tags: {mem.get('tags', 'none')}")
        print(f"  Status: {mem.get('verification_status', 'unknown')}")
        print(f"  Content: {mem['content'][:100]}...")
        print()


if __name__ == "__main__":
    # Quick smoke test
    print("Testing memory-graph API connectivity...")
    if _health_check():
        print("✓ API health check passed")
    else:
        print("✗ API health check failed")
        sys.exit(1)

    # Example batch write (commented out for safety)
    # result = batch_write_findings(
    #     findings=[
    #         {
    #             "name": "finding/test",
    #             "content": "Test finding",
    #             "type": "finding",
    #             "tags": "test",
    #             "verified": True,
    #             "verification_source": "manual-test"
    #         }
    #     ],
    #     run_id="run-2026-04-21-test"
    # )
    # print(f"Write result: {result}")
