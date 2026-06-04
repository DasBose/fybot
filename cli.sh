#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating virtual environment at $VENV"
  python3 -m venv "$VENV"
  echo "Installing dependencies from requirements.txt"
  "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/cli_launcher.py" "$@"
