#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── 检测操作系统 ──────────────────────────────────────────────────
case "$(uname -s 2>/dev/null || echo 'Windows')" in
    CYGWIN*|MINGW*|MSYS*|Windows) IS_WINDOWS=1 ;;
    *) IS_WINDOWS=0 ;;
esac

# ── Python 解释器探测（Windows 优先探测 conda 环境）─────────────
if [[ -n "${RESEARCH_PYTHON:-}" ]]; then
    PYTHON_BIN="$RESEARCH_PYTHON"
elif [[ "$IS_WINDOWS" == "1" ]]; then
    # Windows (Git Bash / MSYS2): 优先探测 research_workbench conda 环境
    if [[ -x "$USERPROFILE/AppData/Local/anaconda3/envs/research_workbench/python.exe" ]]; then
        PYTHON_BIN="$USERPROFILE/AppData/Local/anaconda3/envs/research_workbench/python.exe"
    elif [[ -x "$HOME/AppData/Local/anaconda3/envs/research_workbench/python.exe" ]]; then
        PYTHON_BIN="$HOME/AppData/Local/anaconda3/envs/research_workbench/python.exe"
    elif [[ -x "$USERPROFILE/anaconda3/envs/research_workbench/python.exe" ]]; then
        PYTHON_BIN="$USERPROFILE/anaconda3/envs/research_workbench/python.exe"
    elif [[ -x "$USERPROFILE/AppData/Local/anaconda3/python.exe" ]]; then
        PYTHON_BIN="$USERPROFILE/AppData/Local/anaconda3/python.exe"
    elif command -v python3.11 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3.11)"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    else
        echo "[ERROR] Cannot find Python on Windows. Set RESEARCH_PYTHON env var." >&2
        exit 1
    fi
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
elif [[ -x "$HOME/opt/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/opt/anaconda3/bin/python"
elif [[ -x "$HOME/anaconda3/bin/python" ]]; then
    PYTHON_BIN="$HOME/anaconda3/bin/python"
else
    PYTHON_BIN="$(command -v python3)"
fi

cd "$REPO_ROOT"
exec "$PYTHON_BIN" "$REPO_ROOT/scripts/desktop/backend_launcher.py" "$@"
