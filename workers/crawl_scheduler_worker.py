"""后台爬虫调度器 Worker — 独立进程，管理 APScheduler 定时抓取任务"""

import asyncio
import concurrent.futures
import os
import signal
import sys
import threading
from pathlib import Path

from core.observability import get_logger

logger = get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_DIR / "logs" / "scheduler.pid"

_SHUTDOWN_TIMEOUT = 10  # 优雅退出超时秒数


def _write_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


async def _async_main() -> None:
    from core.services.crawl_scheduler import CrawlScheduler

    logger.info("Crawl scheduler worker starting")
    _write_pid()

    scheduler = CrawlScheduler()
    scheduler.start()

    await _startup_gap_backfill(scheduler)

    stop_event = asyncio.Event()

    def _force_exit() -> None:
        logger.warning(f"Scheduler did not exit within {_SHUTDOWN_TIMEOUT}s, forcing exit")
        os._exit(1)

    def _shutdown() -> None:
        logger.info("Received shutdown signal")
        scheduler.stop()
        _remove_pid()
        stop_event.set()
        # 确保进程在超时后强制退出
        threading.Timer(_SHUTDOWN_TIMEOUT, _force_exit).start()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT, _shutdown)

    logger.info("Crawl scheduler worker started, waiting for jobs")

    await stop_event.wait()
    scheduler.stop()
    _remove_pid()
    logger.info("Crawl scheduler worker stopped")
    sys.exit(0)


def _run_backfill_in_thread(scheduler, source_type) -> None:
    """在线程中运行单个来源的回补检查（每个线程拥有独立事件循环）"""
    from core.contracts import SourceType as _SourceType

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

    asyncio.run(_run())


async def _startup_gap_backfill(scheduler) -> None:
    """启动时检测所有来源的抓取遗漏并回补（线程池并行执行）"""
    from core.source_registry import get_enabled

    source_types = [s.source_type for s in get_enabled()]

    loop = asyncio.get_running_loop()
    max_workers = len(source_types)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            loop.run_in_executor(pool, _run_backfill_in_thread, scheduler, st)
            for st in source_types
        ]
        await asyncio.gather(*futures)


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
