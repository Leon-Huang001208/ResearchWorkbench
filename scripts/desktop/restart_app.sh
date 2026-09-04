#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="${RESEARCH_APP_PATH:-/Applications/Research Workbench.app}"
BASE_URL="${RESEARCH_DESKTOP_URL:-http://127.0.0.1:8765}"
HEALTH_URL="${BASE_URL%/}/health"
MAX_ATTEMPTS="${RESEARCH_RESTART_HEALTH_ATTEMPTS:-90}"
LOG_DIR="${RESEARCH_RESTART_LOG_DIR:-$REPO_ROOT/logs}"
LOG_FILE="$LOG_DIR/desktop-restart.log"
ICON_SOURCE="${RESEARCH_ICON_SOURCE:-$REPO_ROOT/src-tauri/icons/icon.icns}"
ICON_DEST="$APP_PATH/Contents/Resources/icon.icns"
PATCH_AUTOMATION_SCRIPT="$REPO_ROOT/scripts/desktop/patch_macos_automation_permissions.sh"

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

curl_health() {
  HTTPS_PROXY= HTTP_PROXY= ALL_PROXY= https_proxy= http_proxy= all_proxy= \
    curl --silent --show-error --fail --max-time 2 "$HEALTH_URL"
}

kill_listeners_on_desktop_port() {
  local port="${BASE_URL##*:}"
  port="${port%%/*}"

  if [[ ! "$port" =~ ^[0-9]+$ ]]; then
    return 0
  fi

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    log "Stopping stale listener on port $port: pid=$pid"
    kill "$pid" 2>/dev/null || true
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
}

sync_installed_icon() {
  if [[ ! -f "$ICON_SOURCE" || ! -d "$APP_PATH/Contents/Resources" ]]; then
    return 0
  fi

  if [[ -f "$ICON_DEST" ]] && cmp -s "$ICON_SOURCE" "$ICON_DEST"; then
    log "Installed icon is already current"
    return 0
  fi

  log "Syncing installed app icon from $ICON_SOURCE"
  cp "$ICON_SOURCE" "$ICON_DEST"
  touch "$APP_PATH"
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "$APP_PATH" >/dev/null 2>&1 || true
  killall Dock >/dev/null 2>&1 || true
}

if [[ ! -d "$APP_PATH" ]]; then
  log "Research Workbench app is missing: $APP_PATH"
  exit 1
fi

log "Restarting Research Workbench from $APP_PATH"
sync_installed_icon

osascript -e 'tell application "Research Workbench" to quit' >/dev/null 2>&1 || true
sleep 2

while IFS= read -r pid; do
  [[ -n "$pid" ]] || continue
  log "Stopping stale Research Workbench app process: pid=$pid"
  kill "$pid" 2>/dev/null || true
done < <(pgrep -f "$APP_PATH/Contents/MacOS/research_workbench" 2>/dev/null || true)

sleep 1
kill_listeners_on_desktop_port

if [[ -x "$PATCH_AUTOMATION_SCRIPT" ]]; then
  log "Patching macOS automation permission metadata"
  if ! "$PATCH_AUTOMATION_SCRIPT" | tee -a "$LOG_FILE"; then
    log "macOS automation permission metadata patch failed; continuing restart"
  fi
else
  log "macOS automation permission patch script is missing or not executable: $PATCH_AUTOMATION_SCRIPT"
fi

log "Opening Research Workbench"
open "$APP_PATH"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if response="$(curl_health 2>/dev/null)"; then
    log "Research Workbench is healthy after $attempt attempt(s): $response"
    exit 0
  fi
  sleep 1
done

log "Research Workbench did not become healthy at $HEALTH_URL within $MAX_ATTEMPTS seconds"
exit 1
