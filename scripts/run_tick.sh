#!/bin/bash
# launchd entry: load .env, run one tick. Extra args pass through (e.g. --test).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo ".env missing" >&2; exit 1; }
# .env values must be shell-quoted (sourced as shell)
set -a; . ./.env; set +a
export PATH="$HOME/.local/bin:/usr/bin:/bin"
exec venv/bin/python -m metrics_report tick "$@"
