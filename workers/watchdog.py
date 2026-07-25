"""Worker Watchdog — 独立进程，监控并自动重启任意 worker

用法:
    python -m workers.watchdog [--worker knowledge_worker] [--worker-id N]
    python -m workers.watchdog --worker crawl_scheduler_worker [--worker-mode-env ALPHAFOUNDRY_SCHEDULER_MODE]

watchdog 自身由 desktop backend_launcher 启动（frozen 模式下通过
ALPHAFOUNDRY_WATCHDOG_MODE=1 / ALPHAFOUNDRY_SCHEDULER_WATCHDOG_MODE=1 进入
watchdog 模式），再由 watchdog spawn worker 子进程。worker 崩溃时 watchdog
按指数退避自动重启，达到 MAX_RESTARTS_PER_HOUR 上限则放弃并退出。
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# 在任何其他 import 之前强制 UTF-8 I/O，避免 Windows GBK 编码在
# sys.stdout.write() 转发 worker 日志时抛 UnicodeEncodeError。
os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.observability import get_logger
from workers._process_tree import ensure_child_dies_with_parent

logger = get_logger(__name__)

# 优先使用环境变量，打包部署（Tauri sidecar）时 __file__ 指向 exe 内部路径失效
PROJECT_DIR = (
    Path(os.environ["ALPHAFOUNDRY_PROJECT_ROOT"])
    if "ALPHAFOUNDRY_PROJECT_ROOT" in os.environ
    else Path(__file__).resolve().parent.parent
)

PID_FILE = PROJECT_DIR / "logs" / "watchdog.pid"

# watchdog 实例 PID 文件，可被 main() 覆盖（多实例时避免冲突）
_pid_file: Path = PID_FILE

MAX_RESTARTS_PER_HOUR = 10
COOLDOWN_WINDOW = 3600  # 1 hour
RESTART_BACKOFF_BASE = 5
MAX_RESTART_BACKOFF = 120


def _is_frozen() -> bool:
    """是否运行在 PyInstaller 打包的 exe 中。"""
    return bool(getattr(sys, "frozen", False))


def _write_pid() -> None:
    _pid_file.parent.mkdir(parents=True, exist_ok=True)
    _pid_file.write_text(str(os.getpid()))


def _remove_pid() -> None:
    if _pid_file.exists():
        try:
            _pid_file.unlink()
        except OSError:
            pass


_current_child: subprocess.Popen | None = None
# Job Object handle — 必须在 watchdog 生命周期内保持引用，handle 被 GC 回收时
# Job 关闭会立即终止其下所有 worker 进程。
_job_handle = None


def _build_worker_cmd(worker_module: str, worker_id: int | None) -> list[str]:
    """构造 worker 子进程启动命令。

    frozen 模式下复用同一个 exe，通过 ALPHAFOUNDRY_WORKER_MODE=1 让
    backend_launcher 入口以 worker 模式启动；dev 模式直接用 conda Python
    运行 workers.{module} 模块。
    """
    if _is_frozen():
        return [sys.executable]
    return [sys.executable, "-m", f"workers.{worker_module}"]


def _build_worker_env(
    worker_id: int | None, worker_mode_env: str = "ALPHAFOUNDRY_WORKER_MODE"
) -> dict[str, str]:
    """构造 worker 子进程环境变量。frozen 模式需注入运行模式标记。

    Args:
        worker_id: 多实例 ID，注入为 ALPHAFOUNDRY_WORKER_ID（knowledge_worker 专用）。
        worker_mode_env: frozen 模式下注入的运行模式环境变量名，默认为
            ALPHAFOUNDRY_WORKER_MODE（knowledge_worker）；crawl_scheduler_worker
            应传 ALPHAFOUNDRY_SCHEDULER_MODE。
    """
    env = dict(os.environ)
    if _is_frozen():
        env[worker_mode_env] = "1"
    if worker_id is not None:
        # knowledge_worker.main() 读取 ALPHAFOUNDRY_WORKER_ID 作为多实例 ID
        env["ALPHAFOUNDRY_WORKER_ID"] = str(worker_id)
    return env


def _terminate_child() -> None:
    """终止子进程：先 SIGTERM，2 秒后仍存活则 SIGKILL"""
    global _current_child
    if _current_child is None or _current_child.poll() is not None:
        return
    logger.info("Terminating child worker", pid=_current_child.pid)
    _current_child.terminate()
    try:
        _current_child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        logger.warning("Child did not exit, force killing", pid=_current_child.pid)
        _current_child.kill()
        _current_child.wait()


def run_worker(
    worker_module: str,
    worker_id: int | None = None,
    worker_mode_env: str = "ALPHAFOUNDRY_WORKER_MODE",
) -> int:
    """启动 worker 子进程，返回 exit code"""
    global _current_child, _job_handle
    cmd = _build_worker_cmd(worker_module, worker_id)
    env = _build_worker_env(worker_id, worker_mode_env)
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",  # 显式指定 UTF-8，避免 Windows GBK 解码中文日志失败
        errors="replace",  # 无法解码的字节替换为 ? 而非抛 UnicodeDecodeError
        start_new_session=True,
    )
    _current_child = proc
    # Windows: 把 worker 绑定到 watchdog 的 Job Object，watchdog 退出（含强杀）
    # 时 OS 自动终止 worker，避免孤儿进程。
    if proc.pid:
        _job_handle = ensure_child_dies_with_parent(proc.pid)
    assert proc.stdout
    for line in proc.stdout:
        # 转发 worker stdout，便于在 watchdog 日志中观察 worker 输出。
        # 绑定到 sys.stdout.buffer 直接写 UTF-8 字节，绕过 Python 文本层对
        # 终端编码（GBK）的限制，避免 UnicodeEncodeError 使 watchdog 崩溃。
        raw = line.encode("utf-8", errors="replace")
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(raw)
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(line)
            sys.stdout.flush()
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
    parser.add_argument(
        "--worker-id",
        type=int,
        default=None,
        help="Worker instance ID forwarded to the worker for multi-process mode",
    )
    parser.add_argument(
        "--worker-mode-env",
        default="ALPHAFOUNDRY_WORKER_MODE",
        help=(
            "frozen 模式下注入子进程的运行模式环境变量名 "
            "(default: ALPHAFOUNDRY_WORKER_MODE for knowledge_worker; "
            "use ALPHAFOUNDRY_SCHEDULER_MODE for crawl_scheduler_worker)"
        ),
    )
    parser.add_argument(
        "--pid-file",
        default=None,
        help="watchdog 自身的 PID 文件路径（默认 logs/watchdog.pid）；多实例时需各自指定",
    )
    args = parser.parse_args()

    global _pid_file
    if args.pid_file:
        _pid_file = Path(args.pid_file)

    worker_module = args.worker
    worker_mode_env = args.worker_mode_env
    _write_pid()

    # 信号处理
    shutdown = False

    def _handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutdown
        logger.info("Received signal, shutting down", signal=signum)
        shutdown = True
        _terminate_child()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    restart_count = 0
    window_start = time.time()

    logger.info(
        "Watchdog monitoring worker",
        worker_module=worker_module,
        worker_id=args.worker_id,
        pid=os.getpid(),
    )

    while not shutdown:
        try:
            exit_code = run_worker(worker_module, args.worker_id, worker_mode_env)
            logger.info("Worker exited", exit_code=exit_code)
        except Exception as e:
            logger.error("Worker spawn failed", error=str(e), exc_info=True)

        if shutdown:
            break

        # 冷却窗口内限制重启次数
        now = time.time()
        if now - window_start > COOLDOWN_WINDOW:
            restart_count = 0
            window_start = now

        restart_count += 1
        if restart_count > MAX_RESTARTS_PER_HOUR:
            logger.critical(
                "Too many restarts, giving up",
                restart_count=restart_count,
                cooldown_window=COOLDOWN_WINDOW,
            )
            _remove_pid()
            sys.exit(1)

        backoff = min(RESTART_BACKOFF_BASE * (2 ** min(restart_count - 1, 5)), MAX_RESTART_BACKOFF)
        logger.info(
            "Restarting worker after crash",
            restart_count=restart_count,
            max_restarts=MAX_RESTARTS_PER_HOUR,
            backoff_seconds=backoff,
        )
        time.sleep(backoff)

    _remove_pid()
    logger.info("Watchdog shutdown complete")


if __name__ == "__main__":
    main()
