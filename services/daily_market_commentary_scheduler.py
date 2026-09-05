"""Opt-in application scheduler for the configuration-driven market workflow."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core.observability import get_logger
from core.utils.trading_calendar import get_trading_calendar
from data_layer.repositories.base import db_session
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from services.daily_market_commentary_spec import load_daily_market_commentary_spec
from services.runtime_workflow_service import (
    DailyMarketCommentaryRequest,
    RuntimeWorkflowService,
)

logger = get_logger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


class DailyMarketCommentaryScheduler:
    """Owns only scheduling; the workflow itself remains independently runnable."""

    def __init__(self) -> None:
        self.scheduler: AsyncIOScheduler | None = None
        self.running = False

    def start(self) -> None:
        spec = load_daily_market_commentary_spec()
        if not APSCHEDULER_AVAILABLE or not spec.schedule.enabled:
            logger.info("daily market commentary schedule disabled or unavailable")
            return
        if self.running:
            return
        self.scheduler = AsyncIOScheduler(timezone=spec.schedule.timezone)
        self.scheduler.add_job(
            self._run,
            "cron",
            day_of_week="mon-fri" if spec.schedule.trading_days_only else "mon-sun",
            hour=spec.schedule.hour,
            minute=spec.schedule.minute,
            id="daily_market_commentary",
            replace_existing=True,
            coalesce=True,
        )
        self.scheduler.start()
        self.running = True
        logger.info(
            "daily market commentary scheduler started",
            hour=spec.schedule.hour,
            minute=spec.schedule.minute,
        )

    def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
        self.scheduler = None
        self.running = False

    def _run(self) -> None:
        spec = load_daily_market_commentary_spec()
        now = datetime.now(ZoneInfo(spec.schedule.timezone))
        if (
            spec.schedule.trading_days_only
            and now.date() not in get_trading_calendar().get_latest_trading_days(1, now.date())
        ):
            logger.info("daily market commentary skipped on non-trading day")
            return
        try:
            with db_session() as session:
                service = RuntimeWorkflowService(RuntimeWorkflowRepository(session))
                created = service.create_daily_market_commentary(
                    DailyMarketCommentaryRequest(
                        as_of=now,
                        question="生成当日A股每日收盘点评",
                        runtime_id=spec.runtime_id,
                    )
                )
                result = service.execute(created["run_id"])
                logger.info(
                    "daily market commentary scheduled run finished",
                    run_id=created["run_id"],
                    status=result.status,
                )
        except Exception as exc:
            logger.exception(
                "daily market commentary scheduled run failed", error_type=type(exc).__name__
            )


_scheduler: DailyMarketCommentaryScheduler | None = None


def get_daily_market_commentary_scheduler() -> DailyMarketCommentaryScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyMarketCommentaryScheduler()
    return _scheduler
