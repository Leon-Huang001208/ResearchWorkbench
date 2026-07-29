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
from shutil import copy2
from typing import Sequence

from core.settings.paths import app_data_dir
from core.settings.registry import desktop_env_template

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


def resolve_project_root() -> Path:
    """Resolve the source root or PyInstaller bundle root for the launcher."""
    configured_root = os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT")
    if configured_root:
        return Path(configured_root).expanduser()
    bundle_root = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    if bundle_root:
        return Path(bundle_root).resolve()
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resolve_project_root()


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
    return app_data_dir()


def _migrate_legacy_roaming_env(data_dir: Path) -> None:
    """Copy a legacy Windows roaming config once without overwriting local data."""
    if platform.system() != "Windows" or (data_dir / ".env").exists():
        return
    roaming_root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    legacy_env = roaming_root / "AlphaFoundry" / ".env"
    if legacy_env.is_file():
        data_dir.mkdir(parents=True, exist_ok=True)
        copy2(legacy_env, data_dir / ".env")
        logging.getLogger("alphafoundry.desktop").info(
            "Migrated desktop configuration from legacy roaming directory"
        )


def _ensure_default_env(data_dir: Path) -> Path:
    """如果 data_dir/.env 不存在，创建默认模板并返回路径。"""
    env_path = data_dir / ".env"
    if not env_path.exists():
        descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(desktop_env_template())
        if os.name != "nt":
            env_path.chmod(0o600)
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

    桌面端必须连接 PostgreSQL + pgvector；缺少有效配置时由 API 进入设置模式。
    """
    if not (is_frozen() or os.environ.get("ALPHAFOUNDRY_DESKTOP")):
        return None

    data_dir = desktop_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_roaming_env(data_dir)
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

        # Persisted desktop settings must take precedence over stale launcher values.
        load_dotenv(env_path, override=True)
    except ImportError:
        pass  # dotenv 不可用时静默跳过（frozen 包里应已捆绑）

    # ── 路径类默认值（.env 未设置时使用 data_dir 下的子目录）──
    os.environ.setdefault("LOG_DIR", str(data_dir / "logs"))
    os.environ.setdefault("OBJECT_STORAGE_PATH", str(data_dir / "objects"))
    os.environ.setdefault("PDF_MARKDOWN_DIR", str(data_dir / "markdown"))
    os.environ.setdefault("PDF_RAW_TEXT_DIR", str(data_dir / "raw_text"))

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
    """Check whether the desktop listener port is available without touching other processes."""
    logger = logging.getLogger("alphafoundry.desktop")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) != 0:
            logger.info("Port %s:%d is free.", host, port)
            return True

    logger.error(
        "Port %s:%d is already occupied; refusing to terminate an unknown process.", host, port
    )
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


def _require_loopback_host(host: str) -> None:
    """Reject network exposure because the desktop configuration plane is local-only."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("桌面端仅允许监听 localhost 或 127.0.0.1")


def main(argv: Sequence[str] | None = None) -> int:
    """Start the desktop backend and return a process exit code."""
    args = build_parser().parse_args(argv)
    _require_loopback_host(args.host)

    # ── 开发模式自动启用 reload ──────────────────────────────────
    # ALPHAFOUNDRY_DEV=1 时即使命令行没传 --reload 也自动启用，
    # 避免用户手动启动时忘记加 --reload 导致改代码不生效。
    if not args.reload and os.environ.get("ALPHAFOUNDRY_DEV") == "1":
        args.reload = True
        logging.getLogger("alphafoundry.desktop").info(
            "Auto-enabled uvicorn reload (ALPHAFOUNDRY_DEV=1)"
        )

    os.environ["ALPHAFOUNDRY_DESKTOP"] = "1"
    os.environ["ALPHAFOUNDRY_RUN_MODE"] = "desktop"
    os.environ["ALPHAFOUNDRY_BACKEND_URL"] = f"http://{args.host}:{args.port}"

    data_dir = apply_frozen_desktop_defaults()
    if data_dir is not None and args.log_dir == DEFAULT_LOG_DIR:
        args.log_dir = data_dir / "logs"
    log_file = configure_launcher_logging(args.log_dir)
    logger = logging.getLogger("alphafoundry.desktop")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP", "1")
    os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_URL", f"http://{args.host}:{args.port}")

    _worker_proc: subprocess.Popen | None = None
    _sched_proc: subprocess.Popen | None = None
    try:
        # 数据库预检会间接加载运行时配置；必须在桌面环境变量和 .env
        # 已就绪后再导入，否则会把运行模式错误冻结为 web-dev。
        from services.database_readiness import probe_postgresql

        readiness = probe_postgresql(os.environ.get("DATABASE_URL", ""))
    except Exception:
        logger.warning(
            "Desktop database readiness code=%s",
            "unexpected_error",
        )
    else:
        if readiness.ready:
            _worker_proc = _start_knowledge_worker(data_dir, args.log_dir)
            _sched_proc = _start_crawl_scheduler(data_dir, args.log_dir)
        else:
            logger.warning(
                "Desktop database readiness code=%s",
                readiness.code.value,
            )

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
