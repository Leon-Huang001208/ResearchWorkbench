"""Single idempotent scheduler for all framework-owned collectors."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.observability import get_logger

from .dollar.collector import DollarCollector
from .dollar.store import DollarSnapshotStore
from .goldar.collector import GoldCollector
from .goldar.store import GoldSnapshotStore
from .registry import FrameworkRegistry

log = get_logger(__name__)


def collectors_enabled() -> bool:
    configured = os.environ.get("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED")
    if configured is not None:
        return configured.strip().lower() not in {"0", "false", "no", "off"}
    return "PYTEST_CURRENT_TEST" not in os.environ


class FrameworkScheduler:
    def __init__(self, registry: FrameworkRegistry) -> None:
        gold_store = registry.get("gold").store
        dollar_store = registry.get("dollar").store
        if not isinstance(gold_store, GoldSnapshotStore) or not isinstance(
            dollar_store, DollarSnapshotStore
        ):
            raise TypeError("framework registry store mismatch")
        self.gold = GoldCollector(gold_store)
        self.dollar = DollarCollector(dollar_store)
        self.scheduler: AsyncIOScheduler | None = None

    async def start(self) -> None:
        if self.scheduler is not None or not collectors_enabled():
            return
        scheduler = AsyncIOScheduler(timezone=UTC)
        now = datetime.now(UTC)
        jobs = (
            ("gold-macro", self.gold.collect_macro, 60),
            ("gold-goldhub", self.gold.collect_goldhub, 24 * 60),
            ("gold-options", self.gold.collect_options, 24 * 60),
            ("gold-cftc", self.gold.collect_cftc, 7 * 24 * 60),
            ("dollar-core", self.dollar.collect_core, 60),
            ("dollar-fiscal", self.dollar.collect_fiscal, 60),
        )
        for job_id, function, minutes in jobs:
            scheduler.add_job(
                function,
                "interval",
                minutes=minutes,
                id=job_id,
                next_run_time=now,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=300,
                replace_existing=True,
            )
        scheduler.start()
        self.scheduler = scheduler
        log.info("framework_scheduler_started", job_count=len(jobs))

    async def close(self) -> None:
        scheduler = self.scheduler
        if scheduler is None:
            return
        self.scheduler = None
        scheduler.shutdown(wait=False)
        log.info("framework_scheduler_closed")
