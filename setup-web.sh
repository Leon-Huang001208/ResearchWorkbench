#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN=$(command -v python3.12)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=$(command -v python3)
else
  echo "未找到 Python 3.12；请先安装后重试。" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$PROJECT_ROOT/scripts/setup_web.py" "$@"
