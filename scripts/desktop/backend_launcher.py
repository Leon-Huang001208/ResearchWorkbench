"""Desktop backend launcher for the AlphaFoundry Tauri shell."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# 在任何其他 import 之前强制 UTF-8 I/O，避免 Windows GBK 编码导致 structlog 崩溃
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_LOG_DIR = Path("logs")
APP_IMPORT = "app.api.main:app"
PROJECT_ROOT = Path(
    os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT", Path(__file__).resolve().parents[2])
)

# 桌面版默认 .env 模板（首次安装时生成，用户可编辑）
_DEFAULT_ENV_TEMPLATE = """\
# AlphaFoundry 桌面版配置
# 本文件由桌面版首次启动时自动生成，可按需修改。

# 数据库（PostgreSQL + pgvector）
# 使用 postgresql+psycopg:// 显式指定 psycopg v3 驱动
# 用户名/密码需与本地 PostgreSQL 安装时一致
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/alphafoundry

# 日志级别
LOG_LEVEL=INFO

# LLM 并发提取
LLM_EXTRACT_MAX_WORKERS=8
LLM_EXTRACT_CHUNK_SIZE=3500
LLM_EXTRACT_CHUNK_OVERLAP=300
LLM_EXTRACT_MAX_RETRIES=2
LLM_EXTRACT_LONG_TEXT_THRESHOLD=1000

# ── LLM Provider（按需填写）──
# LLM_PROVIDER_1_NAME=deepseek
# LLM_PROVIDER_1_PROTOCOL=openai_compatible
# LLM_PROVIDER_1_BASE_URL=http://your-llm-gateway/v1
# LLM_PROVIDER_1_API_KEY=your-api-key

# ── 任务路由 ──
# TASK_EXTRACT_PROVIDER=deepseek
# TASK_EXTRACT_MODEL=deepseek
# TASK_CLASSIFY_PROVIDER=deepseek
# TASK_CLASSIFY_MODEL=deepseek
# TASK_DEFAULT_PROVIDER=deepseek
# TASK_DEFAULT_MODEL=deepseek

# ── 爬虫夜间静默（本地时间整点，默认 00:00–06:00）──
CRAWLER_QUIET_START=0
CRAWLER_QUIET_END=6
"""


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the packaged desktop backend."""
    parser = argparse.ArgumentParser(description="Run the AlphaFoundry desktop backend")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for local dev")
    return parser


def configure_launcher_logging(log_dir: Path) -> Path:
    """Configure file logging and return the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "desktop-backend.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return log_file


def is_frozen() -> bool:
    """Return whether this launcher is running from a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def desktop_data_dir() -> Path:
    """Return the persistent per-user data directory for desktop builds."""
    override = os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR")
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "AlphaFoundry"
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "AlphaFoundry"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "AlphaFoundry"


def _ensure_default_env(data_dir: Path) -> Path:
    """如果 data_dir/.env 不存在，创建默认模板并返回路径。"""
    env_path = data_dir / ".env"
    if not env_path.exists():
        env_path.write_text(_DEFAULT_ENV_TEMPLATE, encoding="utf-8")
        logging.getLogger("alphafoundry.desktop").info(
            "Created default .env at %s — edit DATABASE_URL and LLM settings as needed", env_path
        )
    return env_path


def apply_frozen_desktop_defaults() -> Path | None:
    """Apply standalone desktop defaults before app settings are imported.

    优先级（高 → 低）：
    1. 已有环境变量（Tauri/系统层注入）
    2. data_dir/.env 文件（用户可编辑）
    3. 内置路径默认值（LOG_DIR、OBJECT_STORAGE_PATH 等目录）
    4. SQLite fallback（仅当 .env 里未设置 DATABASE_URL 时保留向下兼容）
    """
    if not is_frozen():
        return None

    data_dir = desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "objects").mkdir(parents=True, exist_ok=True)
    (data_dir / "markdown").mkdir(parents=True, exist_ok=True)
    (data_dir / "raw_text").mkdir(parents=True, exist_ok=True)

    # ── 先写好目录环境变量（.env 加载前需要 data_dir 已知）──
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(data_dir))

    # ── 首次安装：生成默认 .env 模板 ──
    env_path = _ensure_default_env(data_dir)

    # ── 加载 data_dir/.env，override=False 表示不覆盖已有环境变量 ──
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        pass  # dotenv 不可用时静默跳过（frozen 包里应已捆绑）

    # ── 路径类默认值（.env 未设置时使用 data_dir 下的子目录）──
    os.environ.setdefault("LOG_DIR", str(data_dir / "logs"))
    os.environ.setdefault("OBJECT_STORAGE_PATH", str(data_dir / "objects"))
    os.environ.setdefault("PDF_MARKDOWN_DIR", str(data_dir / "markdown"))
    os.environ.setdefault("PDF_RAW_TEXT_DIR", str(data_dir / "raw_text"))

    # ── DATABASE_URL fallback：仅当 .env 里也未配置时才用 SQLite（向下兼容）──
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir / 'alphafoundry.db'}")

    return data_dir


def _start_knowledge_worker(data_dir: Path | None, log_dir: Path) -> subprocess.Popen | None:
    """启动 watchdog 进程，由 watchdog 负责拉起并守护 knowledge_worker。

    watchdog 在 worker 崩溃时按指数退避自动重启，避免队列消费长时间中断。

    frozen 模式下通过 ALPHAFOUNDRY_WATCHDOG_MODE=1 让子进程以 watchdog 模式启动；
    dev 模式下直接用 sys.executable（conda Python）运行 workers.watchdog 模块。

    继承当前进程的环境变量（含已设置的 DATABASE_URL、LLM 配置等）。
    stdout/stderr 重定向到 log_dir/knowledge_worker.log。
    """
    logger = logging.getLogger("alphafoundry.desktop")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        worker_log = log_dir / "knowledge_worker.log"
        worker_log_fh = open(worker_log, "a", encoding="utf-8")  # noqa: SIM115
        if is_frozen():
            # frozen exe 通过环境变量区分运行模式
            cmd = [sys.executable]
            child_env = {**os.environ, "ALPHAFOUNDRY_WATCHDOG_MODE": "1"}
        else:
            # dev 模式：直接用 Python 模块运行 watchdog（sys.executable 已是 conda Python）
            cmd = [sys.executable, "-m", "workers.watchdog"]
            child_env = dict(os.environ)
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=child_env,
            stdout=worker_log_fh,
            stderr=worker_log_fh,
            start_new_session=True,
        )
        logger.info("Knowledge worker watchdog started (pid=%d, log=%s)", proc.pid, worker_log)
        return proc
    except Exception:
        logger.exception("Failed to start knowledge worker — queue will not be processed")
        return None


def _start_crawl_scheduler(data_dir: Path | None, log_dir: Path) -> subprocess.Popen | None:
    """通过 watchdog 启动 crawl_scheduler_worker，watchdog 负责崩溃后自动重启。

    frozen 模式下通过 ALPHAFOUNDRY_SCHEDULER_WATCHDOG_MODE=1 让子进程以
    scheduler watchdog 模式启动；dev 模式下直接用 sys.executable 运行
    workers.watchdog 模块并传入 --worker crawl_scheduler_worker 参数。

    stdout/stderr 重定向到 log_dir/crawl_scheduler_worker.log。
    """
    logger = logging.getLogger("alphafoundry.desktop")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        sched_log = log_dir / "crawl_scheduler_worker.log"
        sched_log_fh = open(sched_log, "a", encoding="utf-8")  # noqa: SIM115
        pid_file = str(log_dir / "scheduler_watchdog.pid")
        if is_frozen():
            cmd = [sys.executable]
            child_env = {**os.environ, "ALPHAFOUNDRY_SCHEDULER_WATCHDOG_MODE": "1"}
        else:
            cmd = [
                sys.executable,
                "-m",
                "workers.watchdog",
                "--worker",
                "crawl_scheduler_worker",
                "--worker-mode-env",
                "ALPHAFOUNDRY_SCHEDULER_MODE",
                "--pid-file",
                pid_file,
            ]
            child_env = dict(os.environ)
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=child_env,
            stdout=sched_log_fh,
            stderr=sched_log_fh,
            start_new_session=True,
        )
        logger.info("Crawl scheduler watchdog started (pid=%d, log=%s)", proc.pid, sched_log)
        return proc
    except Exception:
        logger.exception("Failed to start crawl scheduler watchdog")
        return None


def _kill_stale_process_on_port(host: str, port: int) -> bool:
    """检测并清理占用指定端口的残留进程。

    仅当端口确实被占用时才执行清理；空闲端口直接返回 True。
    在 Windows 上通过 netstat + taskkill 定位并强杀占用进程；
    在非 Windows 上通过 lsof + kill -9 实现。
    排除自身 PID，避免自杀。
    """
    logger = logging.getLogger("alphafoundry.desktop")

    # ── 快速检测：端口空闲直接跳过 ──
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex((host, port)) != 0:
            logger.info("Port %s:%d is free, no cleanup needed.", host, port)
            return True

    logger.warning("Port %s:%d is occupied, attempting cleanup...", host, port)

    my_pid = os.getpid()

    try:
        if platform.system() == "Windows":
            # netstat -ano | findstr :8765.*LISTENING
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid_str = parts[-1]
                    try:
                        pid = int(pid_str)
                    except ValueError:
                        continue
                    if pid == my_pid:
                        logger.debug("Skipping own PID %d", my_pid)
                        continue
                    logger.info(
                        "Killing stale process on port %s:%d (PID=%d)...",
                        host,
                        port,
                        pid,
                    )
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        capture_output=True,
                        timeout=10,
                    )
        else:
            # lsof -ti :PORT
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    pid = int(line)
                except ValueError:
                    continue
                if pid == my_pid:
                    logger.debug("Skipping own PID %d", my_pid)
                    continue
                logger.info(
                    "Killing stale process on port %s:%d (PID=%d)...",
                    host,
                    port,
                    pid,
                )
                subprocess.run(
                    ["kill", "-9", str(pid)],
                    capture_output=True,
                    timeout=10,
                )

        # ── 等待操作系统释放端口 ──
        import time

        for _ in range(30):  # 最多等 3 秒
            time.sleep(0.1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex((host, port)) != 0:
                    logger.info("Port %s:%d successfully freed.", host, port)
                    return True

        # ── 僵尸端口检测并兜底清理 ──
        # Windows 上进程异常退出后，子进程可能继承 LISTENING socket 句柄，
        # 导致 netstat 仍显示 LISTENING 但原 PID 已不存在。
        # 尝试发送 HTTP 请求：有响应 → 端口确实被占用；无响应 → 僵尸端口。
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test:
                test.settimeout(2)
                test.connect((host, port))
                test.sendall(f"GET /health HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
                test.recv(1)
            # 收到响应 → 端口确实被占用
            logger.error("Port %s:%d still occupied after killing stale process(es).", host, port)
            return False
        except (socket.timeout, ConnectionResetError, ConnectionAbortedError, OSError):
            logger.warning(
                "Port %s:%d has zombie listener (no application response), "
                "falling back to kill-all-Python cleanup.",
                host,
                port,
            )
            if platform.system() == "Windows":
                # 僵尸 socket 通常由已死进程的子进程（worker/scheduler）持有句柄，
                # 直接杀所有 python.exe（排除自身），让内核回收端口。
                import time

                subprocess.run(
                    ["taskkill", "/F", "/FI", f"PID ne {my_pid}", "/IM", "python.exe"],
                    capture_output=True,
                    timeout=15,
                )
                for _ in range(50):  # 最多等 5 秒确认释放
                    time.sleep(0.1)
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1)
                        if s.connect_ex((host, port)) != 0:
                            logger.info("Port %s:%d freed after kill-all-Python.", host, port)
                            return True
                logger.error("Port %s:%d still occupied even after kill-all-Python.", host, port)
                return False
            logger.info(
                "Port %s:%d has zombie listener — treating as free (non-Windows).",
                host,
                port,
            )
            return True

    except Exception:
        logger.exception("Failed to clean up port %s:%d", host, port)
        return False


def run_backend(host: str, port: int, reload: bool) -> None:
    """Run the FastAPI backend through uvicorn."""
    import uvicorn

    os.chdir(PROJECT_ROOT)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # reload_excludes 防止 watchfiles 检测 __pycache__/logs/data 等
    # 非源码目录的变更，避免 worker 进程在导入 C 扩展（psycopg/
    # pydantic-core）时被 reload 触发强杀，导致 DLL use-after-free
    # 引发的 ACCESS_VIOLATION 崩溃。
    _reload_excludes: list[str] | None = None
    if reload:
        _reload_excludes = [
            "**/__pycache__/**",
            "**/*.pyc",
            "**/logs/**",
            "**/data/**",
            "**/.git/**",
            "**/node_modules/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/docs/**",
        ]
    # ── 启动前清理占用端口的残留进程 ─────────────────────────
    # 桌面端关闭后 worker/sidecar 子进程可能残留在 Windows 上
    # 继续占用端口，导致下次启动失败。此处自动检测并强杀。
    if not _kill_stale_process_on_port(host, port):
        _logger = logging.getLogger("alphafoundry.desktop")
        _logger.error(
            "Cannot free port %s:%d — startup aborted. "
            "Please check for non-AlphaFoundry processes using this port.",
            host,
            port,
        )
        raise SystemExit(1)

    uvicorn.run(
        APP_IMPORT,
        host=host,
        port=port,
        reload=reload,
        reload_excludes=_reload_excludes,
        reload_delay=0.5,  # 防止瞬时多次触发 reload
        log_config=None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Start the desktop backend and return a process exit code."""
    args = build_parser().parse_args(argv)

    # ── 开发模式自动启用 reload ──────────────────────────────────
    # ALPHAFOUNDRY_DEV=1 时即使命令行没传 --reload 也自动启用，
    # 避免用户手动启动时忘记加 --reload 导致改代码不生效。
    if not args.reload and os.environ.get("ALPHAFOUNDRY_DEV") == "1":
        args.reload = True
        logging.getLogger("alphafoundry.desktop").info(
            "Auto-enabled uvicorn reload (ALPHAFOUNDRY_DEV=1)"
        )

    data_dir = apply_frozen_desktop_defaults()
    if data_dir is not None and args.log_dir == DEFAULT_LOG_DIR:
        args.log_dir = data_dir / "logs"
    log_file = configure_launcher_logging(args.log_dir)
    logger = logging.getLogger("alphafoundry.desktop")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP", "1")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_URL", f"http://{args.host}:{args.port}")

    # ── 启动 knowledge_worker 和 crawl_scheduler 子进程 ──
    _worker_proc: subprocess.Popen | None = _start_knowledge_worker(data_dir, args.log_dir)
    _sched_proc: subprocess.Popen | None = _start_crawl_scheduler(data_dir, args.log_dir)

    try:
        logger.info(
            "Starting AlphaFoundry desktop backend",
            extra={"host": args.host, "port": args.port, "log_file": str(log_file)},
        )
        run_backend(args.host, args.port, args.reload)
    except Exception:
        logger.exception("AlphaFoundry desktop backend failed")
        return 1
    finally:
        # uvicorn 退出后，优雅终止 watchdog（守护 knowledge_worker）和 scheduler。
        # watchdog 自身的信号 handler 会终止其 worker 子进程；若 watchdog 被强杀
        # 导致 worker 孤儿残留，下次启动时 get_all_worker_statuses() 的 PID 自愈
        # 会清理孤儿 PID 文件。
        for label, proc in [
            ("knowledge worker watchdog", _worker_proc),
            ("crawl scheduler", _sched_proc),
        ]:
            if proc is not None and proc.poll() is None:
                logger.info("Terminating %s (pid=%d)", label, proc.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return 0


if __name__ == "__main__":
    # frozen 模式下通过环境变量区分运行模式
    if os.environ.get("ALPHAFOUNDRY_WATCHDOG_MODE") == "1":
        # knowledge worker watchdog 子进程模式：拉起并守护 knowledge_worker
        apply_frozen_desktop_defaults()
        from workers.watchdog import main as watchdog_main

        watchdog_main()
    elif os.environ.get("ALPHAFOUNDRY_SCHEDULER_WATCHDOG_MODE") == "1":
        # crawl scheduler watchdog 子进程模式：拉起并守护 crawl_scheduler_worker
        apply_frozen_desktop_defaults()
        import sys as _sys

        _sys.argv = [
            _sys.argv[0],
            "--worker",
            "crawl_scheduler_worker",
            "--worker-mode-env",
            "ALPHAFOUNDRY_SCHEDULER_MODE",
            "--pid-file",
            str(Path(os.environ.get("LOG_DIR", "logs")) / "scheduler_watchdog.pid"),
        ]
        from workers.watchdog import main as watchdog_main

        watchdog_main()
    elif os.environ.get("ALPHAFOUNDRY_WORKER_MODE") == "1":
        # knowledge worker 子进程模式
        apply_frozen_desktop_defaults()
        import asyncio

        from workers.knowledge_worker import main as worker_main

        asyncio.run(worker_main())
    elif os.environ.get("ALPHAFOUNDRY_SCHEDULER_MODE") == "1":
        # crawl scheduler 子进程模式
        apply_frozen_desktop_defaults()
        from workers.crawl_scheduler_worker import main as scheduler_main

        scheduler_main()
    else:
        raise SystemExit(main())
