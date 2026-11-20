#!/bin/bash
# PostToolUse hook (Edit|Write): runs every validator in validators/ against the
# file Claude just wrote, and feeds any warnings back to Claude. Warnings, never blocks.
#
#   1. fact_change_validator.py  stale values listed in config/fact-changes.yaml
#   2. gate_validator.py         "soft" gate statuses (CONDITIONAL_PASS etc.)
#   3. deadline_validator.py     a deadline within 14 days on the matter being edited
#
# WATCH_PATTERN: which paths get checked. Adjust to your layout.

INPUT=$(cat)
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
VALIDATORS_DIR="$(cd "$(dirname "$0")" && pwd)/validators"
WATCH_PATTERN="${WATCH_PATTERN:-(matters/|drafts/|output/)}"

FILE_PATH=$(echo "$INPUT" | python3 -c '
import sys, json
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
' 2>/dev/null)

echo "$FILE_PATH" | grep -qE "$WATCH_PATTERN" || exit 0

MESSAGES=""
for validator in "$VALIDATORS_DIR"/*.py; do
    [ -f "$validator" ] || continue
    RESULT=$(echo "$INPUT" | python3 "$validator" "$PROJECT_ROOT" "$FILE_PATH" 2>/dev/null)
    [ -n "$RESULT" ] && MESSAGES="${MESSAGES}${RESULT}"$'\n'
done

[ -z "$MESSAGES" ] && exit 0

# Build the JSON safely (handles quotes, backslashes and newlines).
printf '%s' "$MESSAGES" | python3 -c '
import sys, json
path = sys.argv[1]
msg = "VALIDATOR FEEDBACK on " + path + ":\n" + sys.stdin.read().strip()
print(json.dumps({"continue": True, "suppressOutput": False, "systemMessage": msg}))
' "$FILE_PATH"
