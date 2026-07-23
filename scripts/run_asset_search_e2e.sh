#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${ALPHAFOUNDRY_E2E_PORT:-8002}"
BASE_URL="${ALPHAFOUNDRY_WEB_URL:-http://127.0.0.1:${PORT}}"
LOG_FILE="${ALPHAFOUNDRY_E2E_LOG:-logs/asset_search_e2e_server.log}"
SERVER_PID=""

mkdir -p logs output/playwright

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

url_ok() {
  python - "$BASE_URL" <<'PY'
import sys
from urllib.request import ProxyHandler, build_opener

base_url = sys.argv[1].rstrip("/")
opener = build_opener(ProxyHandler({}))
for path in ("/health", "/"):
    try:
        with opener.open(base_url + path, timeout=1.5) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception:
        pass
raise SystemExit(1)
PY
}

wait_for_server() {
  local attempts="${1:-45}"
  for _ in $(seq 1 "$attempts"); do
    if url_ok; then
      return 0
    fi
    if [[ -n "$SERVER_PID" ]] && ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
      echo "AlphaFoundry Web 服务启动进程已退出，最近日志：" >&2
      tail -80 "$LOG_FILE" >&2 || true
      return 1
    fi
    sleep 1
  done
  echo "等待 AlphaFoundry Web 服务超时：${BASE_URL}" >&2
  tail -80 "$LOG_FILE" >&2 || true
  return 1
}

if url_ok; then
  echo "复用已运行的 AlphaFoundry Web 服务：${BASE_URL}"
else
  echo "启动 AlphaFoundry Web 服务：${BASE_URL}"
  : > "$LOG_FILE"
  python -m uvicorn app.api.main:app --host 127.0.0.1 --port "$PORT" >> "$LOG_FILE" 2>&1 &
  SERVER_PID="$!"
  wait_for_server
fi

ALPHAFOUNDRY_WEB_URL="$BASE_URL" node tests/e2e/asset_search_playwright_core.js
