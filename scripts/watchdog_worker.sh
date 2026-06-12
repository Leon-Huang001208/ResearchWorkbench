#!/usr/bin/env bash
set +e

if [ "$#" -lt 4 ]; then
    echo "Usage: watchdog_worker.sh <name> <pid_file> <log_file> <command...>" >&2
    exit 2
fi

name="$1"
pid_file="$2"
log_file="$3"
shift 3
cmd=("$@")
watchdog_pid_file="$pid_file.watchdog"

mkdir -p "$(dirname "$pid_file")" "$(dirname "$log_file")"
echo $$ > "$watchdog_pid_file"
trap '' HUP

crash_count=0
crash_window_start=0

while true; do
    "${cmd[@]}" >> "$log_file" 2>&1 &
    worker_pid=$!
    echo "$worker_pid" > "$pid_file"
    echo "[$(date '+%H:%M:%S')] [$name] Started (PID $worker_pid)"

    wait "$worker_pid" 2>/dev/null
    exit_code=$?

    now=$(date +%s)
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
