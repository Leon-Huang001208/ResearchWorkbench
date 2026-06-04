#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOGS_DIR"
cd "$PROJECT_DIR"

echo "=========================================="
echo "  AlphaFoundry - Starting All Services"
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

    (
        local crash_count=0
        local crash_window_start=0
        local watchdog_pid_file="$pid_file.watchdog"
        echo $BASHPID > "$watchdog_pid_file"

        while true; do
            # Start the worker
            "${cmd[@]}" >> "$log_file" 2>&1 &
            local worker_pid=$!
            echo "$worker_pid" > "$pid_file"
            echo "[$(date '+%H:%M:%S')] [$name] Started (PID $worker_pid)"

            # Wait for it to exit
            wait "$worker_pid" 2>/dev/null
            local exit_code=$?

            local now
            now=$(date +%s)

            # Fast crash detection
            if [ "$crash_window_start" -eq 0 ] || [ $((now - crash_window_start)) -gt 300 ]; then
                crash_window_start=$now
                crash_count=1
            else
                crash_count=$((crash_count + 1))
            fi

            echo "[$(date '+%H:%M:%S')] [$name] Exited (code=$exit_code), crash #$crash_count in window"

            if [ "$crash_count" -ge 3 ]; then
                echo "[$(date '+%H:%M:%S')] [$name] CRITICAL: 3 crashes in 5min, stopping auto-restart!"
                echo "[$(date '+%H:%M:%S')] [$name] CRITICAL: 3 crashes in 5min!" >> "$log_file"
                rm -f "$pid_file" "$watchdog_pid_file"
                exit 1
            fi

            sleep 3
        done
    ) &
    disown
}

echo ""
echo "[1/3] Starting API server..."
if [ -f "$LOGS_DIR/api.pid" ] && kill -0 "$(cat "$LOGS_DIR/api.pid")" 2>/dev/null; then
    echo "  [WARN] API server already running (PID $(cat "$LOGS_DIR/api.pid"))"
else
    nohup python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 \
        > "$LOGS_DIR/api.log" 2>&1 &
    echo $! > "$LOGS_DIR/api.pid"
    echo "  [OK] API server started (PID $(cat "$LOGS_DIR/api.pid"))"
fi

# ── Scheduler (with watchdog) ─────────────────────
echo "[2/3] Starting crawl scheduler (with auto-restart)..."
if prepare_supervised_worker "Scheduler" "scheduler.pid" "workers.crawl_scheduler_worker" "$LOGS_DIR/scheduler.heartbeat.json" 180; then
    start_with_watchdog "scheduler" "scheduler.pid" "scheduler_stdout.log" \
        python -m workers.crawl_scheduler_worker
    echo "  [OK] Scheduler started with watchdog"
fi

# ── Knowledge Worker (with watchdog) ──────────────
echo "[3/3] Starting knowledge worker (with auto-restart)..."
if prepare_supervised_worker "Knowledge worker" "knowledge_worker.pid" "workers.knowledge_worker" "$LOGS_DIR/knowledge_worker.heartbeat.json" 180; then
    start_with_watchdog "knowledge" "knowledge_worker.pid" "knowledge_worker.log" \
        python -m workers.knowledge_worker
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
echo "  AlphaFoundry is running!"
echo "  Web:    http://127.0.0.1:8000"
echo "  Health: http://127.0.0.1:8000/api/system/health"
echo "  Logs:   $LOGS_DIR/"
echo "=========================================="
