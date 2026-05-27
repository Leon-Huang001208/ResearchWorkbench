"""Worker Watchdog — 独立进程，监控并自动重启 knowledge_worker

用法: python -m workers.watchdog [--worker knowledge_worker]
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_DIR / "logs" / "watchdog.pid"

MAX_RESTARTS_PER_HOUR = 10
COOLDOWN_WINDOW = 3600  # 1 hour
RESTART_BACKOFF_BASE = 5
MAX_RESTART_BACKOFF = 120


def _write_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


_current_child: subprocess.Popen | None = None


def _terminate_child() -> None:
    """终止子进程：先 SIGTERM，2 秒后仍存活则 SIGKILL"""
    global _current_child
    if _current_child is None or _current_child.poll() is not None:
        return
    print(f"[watchdog] Terminating child PID {_current_child.pid}")
    _current_child.terminate()
    try:
        _current_child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        print(f"[watchdog] Child did not exit, force killing PID {_current_child.pid}")
        _current_child.kill()
        _current_child.wait()


def run_worker(worker_module: str) -> int:
    """启动 worker 子进程，返回 exit code"""
    global _current_child
    proc = subprocess.Popen(
        [sys.executable, "-m", f"workers.{worker_module}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _current_child = proc
    assert proc.stdout
    for line in proc.stdout:
        sys.stdout.write(line)
    proc.wait()
    _current_child = None
    return proc.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker Watchdog")
    parser.add_argument(
        "--worker",
        default="knowledge_worker",
        help="Worker module to monitor (default: knowledge_worker)",
    )
    args = parser.parse_args()

    worker_module = args.worker
    _write_pid()

    # 信号处理
    shutdown = False

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutdown
        print(f"[watchdog] Received signal {signum}, shutting down")
        shutdown = True
        _terminate_child()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    restart_count = 0
    window_start = time.time()

    print(f"[watchdog] Monitoring workers.{worker_module} (PID: {os.getpid()})")

    while not shutdown:
        try:
            exit_code = run_worker(worker_module)
            print(f"[watchdog] Worker exited with code {exit_code}")
        except Exception as e:
            print(f"[watchdog] Worker spawn failed: {e}")

        if shutdown:
            break

        # 冷却窗口内限制重启次数
        now = time.time()
        if now - window_start > COOLDOWN_WINDOW:
            restart_count = 0
            window_start = now

        restart_count += 1
        if restart_count > MAX_RESTARTS_PER_HOUR:
            print(
                f"[watchdog] Too many restarts ({restart_count} in {COOLDOWN_WINDOW}s), "
                "giving up. Manual intervention required."
            )
            sys.exit(1)

        backoff = min(RESTART_BACKOFF_BASE * (2 ** min(restart_count - 1, 5)), MAX_RESTART_BACKOFF)
        print(
            f"[watchdog] Restarting worker in {backoff}s "
            f"(restart {restart_count}/{MAX_RESTARTS_PER_HOUR} this window)"
        )
        time.sleep(backoff)

    _remove_pid()
    print("[watchdog] Shutdown complete")


if __name__ == "__main__":
    main()
