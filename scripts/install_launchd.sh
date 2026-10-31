#!/bin/bash
# Install (default) or remove (--uninstall) the hourly launchd job.
set -euo pipefail
LABEL=com.noo9.metrics-report
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="gui/$(id -u)"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "$DOMAIN/$LABEL" || true
  rm -f "$DEST"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" "$REPO/scripts/$LABEL.plist" > "$DEST"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$DEST"
