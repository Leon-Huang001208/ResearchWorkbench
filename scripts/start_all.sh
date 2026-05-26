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

# ── API Server ──────────────────────────────────
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

# ── Scheduler ────────────────────────────────────
echo "[2/3] Starting crawl scheduler..."
if [ -f "$LOGS_DIR/scheduler.pid" ] && kill -0 "$(cat "$LOGS_DIR/scheduler.pid")" 2>/dev/null; then
    echo "  [WARN] Scheduler already running (PID $(cat "$LOGS_DIR/scheduler.pid"))"
else
    nohup python -m workers.crawl_scheduler_worker \
        > "$LOGS_DIR/scheduler.log" 2>&1 &
    echo $! > "$LOGS_DIR/scheduler.pid"
    echo "  [OK] Scheduler started (PID $(cat "$LOGS_DIR/scheduler.pid"))"
fi

# ── Knowledge Worker ─────────────────────────────
echo "[3/3] Starting knowledge worker..."
if [ -f "$LOGS_DIR/knowledge_worker.pid" ] && kill -0 "$(cat "$LOGS_DIR/knowledge_worker.pid")" 2>/dev/null; then
    echo "  [WARN] Knowledge worker already running (PID $(cat "$LOGS_DIR/knowledge_worker.pid"))"
else
    nohup python -m workers.knowledge_worker \
        > "$LOGS_DIR/knowledge_worker.log" 2>&1 &
    echo $! > "$LOGS_DIR/knowledge_worker.pid"
    echo "  [OK] Knowledge worker started (PID $(cat "$LOGS_DIR/knowledge_worker.pid"))"
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
