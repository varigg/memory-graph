#!/usr/bin/env bash
# SessionStart hook — fires at every session start.
# Ensures the memory-graph service is running, then injects current
# operational state into the session as additionalContext so the model
# starts with full awareness without needing to be instructed to query.
#
# Output: JSON with "additionalContext" field, consumed by Claude Code.

set -euo pipefail

PAYLOAD=$(cat)
SESSION_ID=$(echo "$PAYLOAD" | jq -r '.session_id // "unknown"')
API="http://127.0.0.1:7777"

# Ensure the service is running.
if ! curl -sf "$API/health" > /dev/null 2>&1; then
  (cd ~/code/memory-graph && uv run python api_server.py >> /tmp/memory-api.log 2>&1 &)
  sleep 3
  if ! curl -sf "$API/health" > /dev/null 2>&1; then
    jq -n '{"additionalContext": "WARNING: memory-graph service failed to start. Check /tmp/memory-api.log."}'
    exit 0
  fi
fi

# Store the new session_id as the current run_id.
curl -sf -X PUT "$API/kv/current_run_id" \
  -H "Content-Type: application/json" \
  -d "{\"value\": \"$SESSION_ID\"}" > /dev/null 2>&1 || true

# Read open goals (bridge primitives surface — graceful no-op if not yet available).
GOALS_TEXT="No open goals."
GOALS_RESPONSE=$(curl -sf "$API/goal/list?status=active" 2>/dev/null || echo "")
if [ -n "$GOALS_RESPONSE" ] && echo "$GOALS_RESPONSE" | jq -e 'type == "array"' > /dev/null 2>&1; then
  GOALS_TEXT=$(echo "$GOALS_RESPONSE" | jq -r '
    if length == 0 then "No open goals."
    else [.[] | "- [\(.status)] \(.title) (id: \(.id))"] | join("\n")
    end' 2>/dev/null || echo "No open goals.")
fi

# Read last compaction or session snapshot.
SNAPSHOT_TEXT=$(curl -sf "$API/memory/recall?topic=session_snapshot&profile=autonomous&limit=1" 2>/dev/null \
  | jq -r '.[0].content // "No previous snapshot found."' 2>/dev/null \
  || echo "No previous snapshot found.")

# Read active preferences (confidence >= 0.7) if the surface exists.
PREFS_TEXT=""
PREFS_RESPONSE=$(curl -sf "$API/preference/active" 2>/dev/null || echo "")
if [ -n "$PREFS_RESPONSE" ] && echo "$PREFS_RESPONSE" | jq -e 'type == "array" and length > 0' > /dev/null 2>&1; then
  PREFS_TEXT=$(echo "$PREFS_RESPONSE" \
    | jq -r '"### Active Preferences\n" + ([.[] | "- \(.rule)"] | join("\n"))' 2>/dev/null || echo "")
fi

CONTEXT="## Session Context (injected by SessionStart hook)

Memory Graph service is running at $API.
Current session id: $SESSION_ID

### Open Goals
$GOALS_TEXT

### Last Session Snapshot
$SNAPSHOT_TEXT
$PREFS_TEXT"

jq -n --arg ctx "$CONTEXT" '{"additionalContext": $ctx}'
