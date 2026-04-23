#!/usr/bin/env bash
# SessionEnd hook — fires on controlled session shutdown.
# Writes a final operational state snapshot to memory-graph.
# Exit codes and stdout are ignored by Claude Code for this hook type.
#
# Reason codes (matcher_value): clear, resume, logout,
# prompt_input_exit, bypass_permissions_disabled, other.

set -euo pipefail

PAYLOAD=$(cat)
SESSION_ID=$(echo "$PAYLOAD" | jq -r '.session_id // "unknown"')
REASON=$(echo "$PAYLOAD" | jq -r '.matcher_value // "unknown"')
API="http://127.0.0.1:7777"

if ! curl -sf "$API/health" > /dev/null 2>&1; then
  exit 0
fi

GOALS_JSON=$(curl -sf "$API/goal/active" 2>/dev/null || echo "[]")
GOALS_SUMMARY=$(echo "$GOALS_JSON" | jq -r '
  if length == 0 then "No open goals."
  else .[] | "- [\(.status)] \(.title) (id: \(.id))"
  end' 2>/dev/null || echo "Could not read goals.")

CONTENT="Session end snapshot (reason: $REASON, session: $SESSION_ID).

Open goals at shutdown:
$GOALS_SUMMARY"

curl -sf -X POST "$API/memory" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg name "session_snapshot" \
        --arg content "$CONTENT" \
        --arg run "$SESSION_ID" \
        '{name: $name,
          type: "project",
          content: $content,
          description: "Auto-snapshot at session end",
          visibility: "private",
          owner_agent_id: "autonomous",
          run_id: $run,
          tags: ["snapshot", "session-end"]}')" > /dev/null 2>&1 || true

exit 0
