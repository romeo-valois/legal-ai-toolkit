#!/bin/bash
# Turn the automatic refresh (every 6 hours) on or off for THIS project.
#   schedule.sh install     macOS: a launchd job.  Linux: prints the crontab line to add.
#   schedule.sh uninstall
#   schedule.sh status
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import kb; print(kb.ROOT)")"
PY="$(command -v python3)"
SLUG="$(basename "$ROOT" | tr -c 'A-Za-z0-9\n' '-' | tr 'A-Z' 'a-z')"
LABEL="com.claude.kb-ingest.$SLUG"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# launchd starts with a bare PATH: give it the folders that hold python3, claude and (optional) gws
PATHS="$(dirname "$PY")"
for b in claude gws node; do p="$(command -v $b 2>/dev/null || true)"; [ -n "$p" ] && PATHS="$PATHS:$(dirname "$p")"; done
PATHS="$PATHS:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

case "${1:-status}" in
  install)
    if [ "$(uname)" != "Darwin" ]; then
      echo "Add this line with 'crontab -e':"
      echo "0 */6 * * * cd \"$ROOT\" && PATH=$PATHS $PY \"$HERE/ingest_all.py\" >> \"$ROOT/.kb/cron.log\" 2>&1"
      exit 0
    fi
    mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/.kb"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>$PY</string><string>$HERE/ingest_all.py</string></array>
    <key>EnvironmentVariables</key>
    <dict><key>PATH</key><string>$PATHS</string><key>KB_ROOT</key><string>$ROOT</string></dict>
    <key>StartInterval</key><integer>21600</integer>
    <key>WorkingDirectory</key><string>$ROOT</string>
    <key>StandardOutPath</key><string>$ROOT/.kb/launchd.log</string>
    <key>StandardErrorPath</key><string>$ROOT/.kb/launchd.log</string>
    <key>LowPriorityIO</key><true/>
    <key>Nice</key><integer>10</integer>
    <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "installed $LABEL: refreshes $ROOT every 6 hours (log: $ROOT/.kb/ingest.log)"
    ;;
  uninstall)
    if [ -f "$PLIST" ]; then launchctl unload "$PLIST" 2>/dev/null || true; rm "$PLIST"; echo "removed $LABEL"
    else echo "not installed (on Linux, remove the line with 'crontab -e')"; fi
    ;;
  status)
    if [ -f "$PLIST" ]; then echo "installed: $PLIST"; else echo "not installed"; fi
    ;;
  *) echo "usage: schedule.sh install|uninstall|status"; exit 1 ;;
esac
