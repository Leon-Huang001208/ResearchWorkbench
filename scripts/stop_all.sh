#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$PROJECT_DIR/logs"

echo "=========================================="
echo "  AlphaFoundry - Stopping All Services"
echo "=========================================="

stop_by_pid() {
    local name="$1"
    local pid_file="$LOGS_DIR/$name.pid"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "  [OK] $name stopped (PID $pid)"
        else
            echo "  [SKIP] $name not running (PID $pid does not exist)"
        fi
        rm -f "$pid_file"
    else
        echo "  [SKIP] $name not found (no PID file)"
    fi
}

# Stop watchdogs first (so they don't restart workers)
echo "Stopping watchdogs..."
for wpid in "$LOGS_DIR"/*.pid.watchdog; do
    if [ -f "$wpid" ]; then
        w_pid=$(cat "$wpid")
        if kill -0 "$w_pid" 2>/dev/null; then
            kill "$w_pid" 2>/dev/null || true
            echo "  [OK] Watchdog stopped (PID $w_pid)"
        fi
        rm -f "$wpid"
    fi
done

sleep 1

stop_by_pid "knowledge_worker"
stop_by_pid "scheduler"
stop_by_pid "api"

echo "=========================================="
echo "  All services stopped."
echo "=========================================="
