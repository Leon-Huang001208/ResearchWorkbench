"""后台爬虫调度器 Worker — 独立进程，管理 APScheduler 定时抓取任务"""

import asyncio
import concurrent.futures
import importlib
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

# 优先使用环境变量，打包部署（Tauri sidecar）时 __file__ 指向 exe 内部路径失效
PROJECT_DIR = (
    Path(os.environ["RESEARCH_PROJECT_ROOT"])
    if "RESEARCH_PROJECT_ROOT" in os.environ
    else Path(__file__).resolve().parent.parent
)
PID_FILE = PROJECT_DIR / "logs" / "scheduler.pid"
HEARTBEAT_FILE = PROJECT_DIR / "logs" / "scheduler.heartbeat.json"

_SHUTDOWN_TIMEOUT = 60  # 优雅退出超时秒数（需足够长以完成启动回补）


def _write_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def _write_heartbeat(activity: str) -> None:
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.write_text(
        json.dumps(
            {
                "timestamp": time.time(),
                "activity": activity,
            },
            ensure_ascii=False,
        )
    )


def _flush_logs() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


async def _async_main() -> None:
    from services.crawl_scheduler import CrawlScheduler

    logger.info("Crawl scheduler worker starting")
    _write_pid()
    event_bus.record_worker_heartbeat("crawl_scheduler", "starting")
    _write_heartbeat("starting")

    scheduler = CrawlScheduler()
    scheduler.start()
    event_bus.record_worker_heartbeat("crawl_scheduler", "started, jobs scheduled")
    _write_heartbeat("started, jobs scheduled")

    def _log_startup_gap_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("[startup] gap backfill cancelled")
        except Exception:
            logger.exception("[startup] gap backfill crashed")

    startup_backfill_task = asyncio.create_task(_startup_gap_backfill(scheduler))
    startup_backfill_task.add_done_callback(_log_startup_gap_result)

    stop_event = asyncio.Event()
    _heartbeat_task = asyncio.create_task(_periodic_heartbeat(stop_event))

    shutdown_timer: threading.Timer | None = None

    def _force_exit() -> None:
        logger.warning(f"Scheduler did not exit within {_SHUTDOWN_TIMEOUT}s, forcing exit")
        _flush_logs()
        os._exit(1)

    def _shutdown() -> None:
        nonlocal shutdown_timer
        logger.info("Received shutdown signal")
        event_bus.record_worker_heartbeat("crawl_scheduler", "stopping")
        _write_heartbeat("stopping")
        stop_event.set()
        if shutdown_timer is None:
            shutdown_timer = threading.Timer(_SHUTDOWN_TIMEOUT, _force_exit)
            shutdown_timer.daemon = True
            shutdown_timer.start()

    loop = asyncio.get_running_loop()
    try:
        # add_signal_handler is Unix-only; not supported on Windows ProactorEventLoop
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
        loop.add_signal_handler(signal.SIGINT, _shutdown)
    except NotImplementedError:
        # Windows fallback: use signal.signal() instead
        signal.signal(signal.SIGTERM, lambda *_: _shutdown())
        signal.signal(signal.SIGINT, lambda *_: _shutdown())

    logger.info("Crawl scheduler worker started, waiting for jobs")

    await stop_event.wait()
    startup_backfill_task.cancel()
    _heartbeat_task.cancel()
    try:
        scheduler.stop()
    finally:
        _remove_pid()
        logger.info("Crawl scheduler worker stopped")
        _flush_logs()
        os._exit(0)


def _run_backfill_in_thread(scheduler, source_type, backfill_timeout: int = 600) -> None:
    """在线程中运行单个来源的回补检查（每个线程拥有独立事件循环）

    带超时保护：单个来源超时不会阻塞其他来源的启动回补。
    """

    async def _run() -> None:
        try:
            result = await scheduler.check_and_backfill_gap(source_type)
            if result:
                logger.info(
                    f"[startup] {source_type.value} startup backfill done: "
                    f"gap={result.get('gap_minutes', 0):.0f}min, "
                    f"saved={result.get('success_count', 0)}"
                )
        except Exception:
            logger.exception(f"[startup] {source_type.value} startup backfill failed")

    async def _run_with_timeout() -> None:
        try:
            await asyncio.wait_for(_run(), timeout=backfill_timeout)
        except asyncio.TimeoutError:
            logger.error(
                f"[startup] {source_type.value} startup backfill TIMEOUT after "
                f"{backfill_timeout}s — source may be hanging, will retry on next schedule"
            )

    asyncio.run(_run_with_timeout())


async def _startup_gap_backfill(scheduler) -> None:
    """启动时检测所有来源的抓取遗漏并回补（线程池并行执行）"""
    from core.source_registry import get_enabled

    source_specs = [s for s in get_enabled() if s.interval_minutes > 0]
    skipped = [s.source_type.value for s in get_enabled() if s.interval_minutes <= 0]
    if skipped:
        logger.info(
            "[startup] skipping startup backfill for non-scheduled sources",
            extra={"sources": skipped},
        )

    source_types = [s.source_type for s in source_specs]
    if not source_types:
        logger.info("[startup] no scheduled sources enabled for gap backfill")
        return

    # Import connector modules serially before threaded backfill. Some connector modules
    # import shared dependencies; doing that lazily in worker threads can trip Python's
    # module lock and make connector-backed sources look like empty legacy adapter runs.
    for spec in source_specs:
        if not spec.connector_class:
            continue
        module_path, _ = spec.connector_class.rsplit(".", 1)
        importlib.import_module(module_path)

    loop = asyncio.get_running_loop()
    max_workers = max(1, min(len(source_types), 8))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            loop.run_in_executor(pool, _run_backfill_in_thread, scheduler, st)
            for st in source_types
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)
        for source_type, result in zip(source_types, results):
            if isinstance(result, Exception):
                logger.error(
                    f"[startup] {source_type.value} startup backfill crashed outside guard",
                    extra={"error": str(result)},
                )


async def _periodic_heartbeat(stop_event: asyncio.Event, interval: int = 30) -> None:
    """每 30 秒记录一次调度器心跳"""
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            event_bus.record_worker_heartbeat("crawl_scheduler", "running, jobs active")
            _write_heartbeat("running, jobs active")


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
