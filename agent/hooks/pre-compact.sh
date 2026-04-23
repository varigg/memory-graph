#!/usr/bin/env bash
# PreCompact hook — fires before context compaction (auto or manual).
# Reads current operational state from memory-graph and writes a
# snapshot memory so the post-compaction session can recover context.
#
# Cannot inject into the compaction summary (Claude Code ignores stdout
# for this hook type). The snapshot is written to the service and will
# be read by the SessionStart hook on next session, or recalled by the
# model after compaction via the bootstrap procedure.

set -euo pipefail

PAYLOAD=$(cat)
SESSION_ID=$(echo "$PAYLOAD" | jq -r '.session_id // "unknown"')
TRIGGER=$(echo "$PAYLOAD" | jq -r '.matcher_value // "unknown"')
API="http://127.0.0.1:7777"

if ! curl -sf "$API/health" > /dev/null 2>&1; then
  exit 0  # Service down — nothing to snapshot, exit cleanly.
fi

# Read current operational state.
GOALS_JSON=$(curl -sf "$API/goal/active" 2>/dev/null || echo "[]")
GOALS_SUMMARY=$(echo "$GOALS_JSON" | jq -r '
  if length == 0 then "No open goals."
  else .[] | "- [\(.status)] \(.title) (id: \(.id))"
  end' 2>/dev/null || echo "Could not read goals.")

RECENT_ACTIONS=$(curl -sf "$API/action-log/list?run_id=$SESSION_ID&limit=5" 2>/dev/null \
  | jq -r '.[] | "- \(.action_type): \(.result_summary // "pending")"' 2>/dev/null \
  || echo "No recent actions.")

CONTENT="Compaction snapshot (trigger: $TRIGGER, session: $SESSION_ID).

Open goals:
$GOALS_SUMMARY

Recent actions this session:
$RECENT_ACTIONS"

curl -sf -X POST "$API/memory" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
        --arg name "session_snapshot" \
        --arg content "$CONTENT" \
        --arg run "$SESSION_ID" \
        '{name: $name,
          type: "project",
          content: $content,
          description: "Auto-snapshot before context compaction",
          visibility: "private",
          owner_agent_id: "autonomous",
          run_id: $run,
          tags: ["snapshot", "compaction"]}')" > /dev/null 2>&1 || true

exit 0
