#!/bin/sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

# Explicit Docker-only installation never probes a host interpreter.
DOCKER_ONLY=0
for ARGUMENT in "$@"; do
  test "$ARGUMENT" != docker || DOCKER_ONLY=1
done
if [ "$DOCKER_ONLY" = 1 ]; then
  ENVIRONMENT=stage INSTANCE=local PORT=18088 NO_START=0
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --runtime) test "${2:-}" = docker; shift 2;;
      --environment) ENVIRONMENT=${2:?}; shift 2;;
      --instance) INSTANCE=${2:?}; shift 2;;
      --web-port) PORT=${2:?}; shift 2;;
      --no-start) NO_START=1; shift;;
      *) echo 'docker_setup_argument_unsupported: use python scripts/setup_web.py for legacy installation flags' >&2; exit 2;;
    esac
  done
  "$PROJECT_ROOT/rwb-docker" bootstrap
  "$PROJECT_ROOT/rwb-docker" build
  "$PROJECT_ROOT/rwb-docker" "$ENVIRONMENT" "$INSTANCE" register --port "$PORT"
  if [ "$NO_START" = 0 ]; then
    "$PROJECT_ROOT/rwb-docker" "$ENVIRONMENT" "$INSTANCE" up
  fi
  exit 0
fi

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN=$(command -v python3.12)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=$(command -v python3)
else
  echo "未找到 Python 3.12；请先安装后重试。" >&2
  exit 1
fi

# Keep --runtime and every installer flag in the original argument order.
exec "$PYTHON_BIN" "$PROJECT_ROOT/scripts/setup_web.py" "$@"
