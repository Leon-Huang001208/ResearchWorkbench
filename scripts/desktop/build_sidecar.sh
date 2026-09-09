#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -n "${RESEARCH_PYTHON:-}" ]]; then
    PYTHON_BIN="$RESEARCH_PYTHON"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
elif [[ -x "$HOME/opt/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/opt/anaconda3/bin/python"
elif [[ -x "$HOME/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/anaconda3/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    PYTHON_BIN=""
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    echo "Python runtime not found or not executable: $PYTHON_BIN" >&2
    echo "Set RESEARCH_PYTHON=/path/to/python and retry." >&2
    exit 1
fi

exec "$PYTHON_BIN" "$REPO_ROOT/scripts/desktop/build_sidecar.py"
