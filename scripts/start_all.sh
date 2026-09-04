#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOGS_DIR"
cd "$PROJECT_DIR"

# Use the research_workbench conda environment's Python interpreter
PYTHON="C:/Users/H01402/AppData/Local/anaconda3/envs/research_workbench/python.exe"

# The desktop shell may export a local proxy (for example 127.0.0.1:7890).
# If that proxy is not running, crawler requests fail before reaching sources.
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export NO_PROXY="*"

echo "=========================================="
echo "  Research Workbench - Starting All Services"
echo "=========================================="

is_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

pid_command_matches() {
    local pid="$1"
    local pattern="$2"
    ps -p "$pid" -o command= 2>/dev/null | grep -F "$pattern" >/dev/null 2>&1
}

heartbeat_fresh() {
    local heartbeat_file="$1"
    local max_age="$2"
    [ -f "$heartbeat_file" ] || return 1
    local now
    local mtime
    now=$(date +%s)
    mtime=$(stat -f %m "$heartbeat_file" 2>/dev/null || echo 0)
    [ $((now - mtime)) -le "$max_age" ]
}

terminate_pid() {
    local name="$1"
    local pid="$2"
    if is_alive "$pid"; then
        echo "  [INFO] Stopping stale $name (PID $pid)"
        kill "$pid" 2>/dev/null || true
        sleep 2
        if is_alive "$pid"; then
            echo "  [WARN] Force killing stale $name (PID $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
}

prepare_supervised_worker() {
    local name="$1"
    local pid_file="$LOGS_DIR/$2"
    local watchdog_file="$pid_file.watchdog"
    local command_pattern="$3"
    local heartbeat_file="$4"
    local max_heartbeat_age="$5"

    local worker_pid=""
    local watchdog_pid=""
    [ -f "$pid_file" ] && worker_pid=$(cat "$pid_file" 2>/dev/null || true)
    [ -f "$watchdog_file" ] && watchdog_pid=$(cat "$watchdog_file" 2>/dev/null || true)

    local worker_ok=0
    if is_alive "$worker_pid" && pid_command_matches "$worker_pid" "$command_pattern" \
        && heartbeat_fresh "$heartbeat_file" "$max_heartbeat_age"; then
        worker_ok=1
    fi

    local watchdog_ok=0
    if is_alive "$watchdog_pid"; then
        watchdog_ok=1
    fi

    if [ "$worker_ok" -eq 1 ] && [ "$watchdog_ok" -eq 1 ]; then
        echo "  [WARN] $name already running under watchdog (PID $worker_pid)"
        return 1
    fi

    if [ "$worker_ok" -eq 1 ] && [ "$watchdog_ok" -ne 1 ]; then
        echo "  [WARN] $name worker alive but watchdog missing; restarting under supervision"
        terminate_pid "$name" "$worker_pid"
    elif [ -n "$worker_pid" ]; then
        terminate_pid "$name" "$worker_pid"
    fi

    if [ -n "$watchdog_pid" ] && ! is_alive "$watchdog_pid"; then
        echo "  [INFO] Removing stale $name watchdog PID file"
    elif [ -n "$watchdog_pid" ]; then
        terminate_pid "$name watchdog" "$watchdog_pid"
    fi

    rm -f "$pid_file" "$watchdog_file"
    return 0
}

# ── Helper: launch a worker with auto-restart ──────
# Usage: start_with_watchdog <name> <pid_file> <log_file> <command...>
# The watchdog monitors the PID and restarts the worker if it dies.
# Fast crash detection: 3 crashes within 5 minutes → stop restarting and alert.
start_with_watchdog() {
    local name="$1"
    local pid_file="$LOGS_DIR/$2"
    local log_file="$LOGS_DIR/$3"
    shift 3
    local cmd=("$@")

    "$PYTHON" "$PROJECT_DIR/scripts/daemonize.py" \
        --cwd "$PROJECT_DIR" \
        --pid-file "$pid_file.watchdog" \
        --stdout "$log_file" \
        --stderr "$log_file" \
        -- "$PROJECT_DIR/scripts/watchdog_worker.sh" "$name" "$pid_file" "$log_file" "${cmd[@]}"
}

# ── Load .env into the shell so daemonized processes inherit the values ──
if [ -f "$PROJECT_DIR/.env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # skip blank lines and comments
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        # only export lines that look like KEY=value (no leading spaces required)
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            key="${line%%=*}"
            value="${line#*=}"
            export "$key"="$value"
        fi
    done < "$PROJECT_DIR/.env"
fi

echo ""
echo "[1/3] Starting API server..."
if [ -f "$LOGS_DIR/api.pid" ] && kill -0 "$(cat "$LOGS_DIR/api.pid")" 2>/dev/null; then
    echo "  [WARN] API server already running (PID $(cat "$LOGS_DIR/api.pid"))"
else
    "$PYTHON" "$PROJECT_DIR/scripts/daemonize.py" \
        --cwd "$PROJECT_DIR" \
        --pid-file "$LOGS_DIR/api.pid" \
        --stdout "$LOGS_DIR/api.log" \
        --stderr "$LOGS_DIR/api.log" \
        -- "$PYTHON" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
    echo "  [OK] API server started (PID $(cat "$LOGS_DIR/api.pid"))"
fi

# ── Scheduler (with watchdog) ─────────────────────
echo "[2/3] Starting crawl scheduler (with auto-restart)..."
if prepare_supervised_worker "Scheduler" "scheduler.pid" "workers.crawl_scheduler_worker" "$LOGS_DIR/scheduler.heartbeat.json" 180; then
    start_with_watchdog "scheduler" "scheduler.pid" "scheduler_stdout.log" \
        "$PYTHON" -m workers.crawl_scheduler_worker
    echo "  [OK] Scheduler started with watchdog"
fi

# ── Knowledge Worker (with watchdog) ──────────────
echo "[3/3] Starting knowledge worker (with auto-restart)..."
if prepare_supervised_worker "Knowledge worker" "knowledge_worker.pid" "workers.knowledge_worker" "$LOGS_DIR/knowledge_worker.heartbeat.json" 180; then
    start_with_watchdog "knowledge" "knowledge_worker.pid" "knowledge_worker.log" \
        "$PYTHON" -m workers.knowledge_worker
    echo "  [OK] Knowledge worker started with watchdog"
fi

# ── Health Check ─────────────────────────────────
echo ""
sleep 2
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "  [OK] API health check passed"
else
    echo "  [WARN] API health check failed (may need more time)"
fi

echo ""
echo "=========================================="
echo "  Research Workbench is running!"
echo "  Web:    http://127.0.0.1:8000"
echo "  Health: http://127.0.0.1:8000/api/system/health"
echo "  Logs:   $LOGS_DIR/"
echo "=========================================="
