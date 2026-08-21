#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/realistic_backtest_control_panel.py
fi

echo "Python 3.11 ou superior não foi encontrado." >&2
exit 1
