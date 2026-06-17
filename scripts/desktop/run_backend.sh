#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -n "${ALPHAFOUNDRY_PYTHON:-}" ]]; then
    PYTHON_BIN="$ALPHAFOUNDRY_PYTHON"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
elif [[ -x "$HOME/opt/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/opt/anaconda3/bin/python"
elif [[ -x "$HOME/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/anaconda3/bin/python"
else
    PYTHON_BIN="$(command -v python3)"
fi

exec "$PYTHON_BIN" "$REPO_ROOT/scripts/desktop/backend_launcher.py" "$@"
