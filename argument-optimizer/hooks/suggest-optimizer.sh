#!/bin/bash
# PostToolUse hook (Edit|Write): when a file under a drafts/ folder changes,
# nudge Claude to offer the argument optimizer.
#
# Change DRAFTS_PATTERN to match your own folder layout.

DRAFTS_PATTERN="${DRAFTS_PATTERN:-/drafts/}"

FILE_PATH=$(python3 -c '
import sys, json
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
' 2>/dev/null)

if echo "$FILE_PATH" | grep -qE "$DRAFTS_PATTERN"; then
    cat <<'EOF'
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "OPTIMIZER SUGGESTION: a draft was just modified. If the edit was substantive (not a typo fix), ask the user: 'This draft was just updated. Want me to run the argument optimizer on it before review?' Ask once per draft per session."
}
EOF
fi
