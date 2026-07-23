"""市场数据调度器 Worker — 独立进程，管理 APScheduler 定时行情拉取任务."""

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_DIR / "logs" / "market_data_scheduler.pid"
HEARTBEAT_FILE = PROJECT_DIR / "logs" / "market_data_scheduler.heartbeat.json"

_SHUTDOWN_TIMEOUT = 60  # 优雅退出超时秒数


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


async def _async_main() -> None:
    from services.market_data_scheduler import MarketDataScheduler

    logger.info("Market data scheduler worker starting")
    _write_pid()
    event_bus.record_worker_heartbeat("market_data_scheduler", "starting")
    _write_heartbeat("starting")

    scheduler = MarketDataScheduler(enable_gap_check=False)
    scheduler.start()
    event_bus.record_worker_heartbeat("market_data_scheduler", "started, jobs scheduled")
    _write_heartbeat("started, jobs scheduled")

    stop_event = asyncio.Event()
    _heartbeat_task = asyncio.create_task(_periodic_heartbeat(stop_event))

    def _force_exit() -> None:
        for handler in logging.getLogger().handlers:
            handler.flush()
        logger.warning(
            f"Market data scheduler did not exit within {_SHUTDOWN_TIMEOUT}s, " "forcing exit"
        )
        os._exit(1)

    def _shutdown() -> None:
        logger.info("Received shutdown signal (market data scheduler)")
        event_bus.record_worker_heartbeat("market_data_scheduler", "stopping")
        _write_heartbeat("stopping")
        stop_event.set()
        threading.Timer(_SHUTDOWN_TIMEOUT, _force_exit).start()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT, _shutdown)

    logger.info("Market data scheduler worker started, waiting for jobs")

    await stop_event.wait()
    scheduler.stop()
    _remove_pid()
    logger.info("Market data scheduler worker stopped")
    sys.exit(0)


async def _periodic_heartbeat(stop_event: asyncio.Event, interval: int = 30) -> None:
    """每 30 秒记录一次心跳."""
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            event_bus.record_worker_heartbeat("market_data_scheduler", "running, jobs active")
            _write_heartbeat("running, jobs active")


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
