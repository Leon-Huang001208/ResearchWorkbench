"""
采集调度器 - Issue #43: 增量调度机制

基于 APScheduler，提供：
- 定时任务配置
- 任务管理
- 健康检查
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.contracts import SourceType
from core.observability import get_logger
from core.services.crawl_orchestrator import CrawlOrchestrator

logger = get_logger(__name__)

# 尝试导入 APScheduler
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not available, scheduling disabled")


class SourceCrawlConfig:
    """来源抓取配置"""

    def __init__(
        self,
        source_type: SourceType,
        source_name: Optional[str] = None,
        interval_minutes: int = 60,
        days_per_crawl: int = 1,
        max_docs: Optional[int] = None,
        enabled: bool = True,
        backfill_enabled: bool = True,
        backfill_interval_hours: int = 24,
    ):
        self.source_type = source_type
        self.source_name = source_name or source_type.value
        self.interval_minutes = interval_minutes
        self.days_per_crawl = days_per_crawl
        self.max_docs = max_docs
        self.enabled = enabled
        self.backfill_enabled = backfill_enabled
        self.backfill_interval_hours = backfill_interval_hours


# 默认配置
DEFAULT_CRAWL_CONFIGS = [
    # 财联社：每 15 分钟抓取一次
    SourceCrawlConfig(
        source_type=SourceType.CAILIAN_SHE,
        source_name="财联社",
        interval_minutes=15,
        days_per_crawl=1,
    ),
    # 中国证券报：每 30 分钟抓取一次
    SourceCrawlConfig(
        source_type=SourceType.CHINA_SECURITY_JOURNAL,
        source_name="中国证券报",
        interval_minutes=30,
        days_per_crawl=1,
    ),
    # 知丘研报：每 1 小时抓取一次
    SourceCrawlConfig(
        source_type=SourceType.ZHIQIU_REPORTS,
        source_name="知丘研报",
        interval_minutes=60,
        days_per_crawl=2,
    ),
]


class CrawlScheduler:
    """采集调度器"""

    def __init__(self):
        self.scheduler: Optional[Any] = None
        self.configs: Dict[SourceType, SourceCrawlConfig] = {}
        self.orchestrator = CrawlOrchestrator()
        self.running = False
        self.last_backfill_times: Dict[SourceType, datetime] = {}

        # 加载默认配置
        for cfg in DEFAULT_CRAWL_CONFIGS:
            self.configs[cfg.source_type] = cfg

    def add_config(self, config: SourceCrawlConfig) -> None:
        """添加抓取配置"""
        self.configs[config.source_type] = config

        # 如果调度器已运行，添加任务
        if self.running and self.scheduler:
            self._add_jobs_for_source(config)

    def start(self) -> None:
        """启动调度器"""
        if not APSCHEDULER_AVAILABLE:
            logger.error("APScheduler not available, cannot start scheduler")
            return

        if self.running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting crawl scheduler")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

        # 添加任务
        for config in self.configs.values():
            if config.enabled:
                self._add_jobs_for_source(config)

        # 添加健康检查任务
        self.scheduler.add_job(
            self._health_check,
            "interval",
            minutes=10,
            id="health_check",
            next_run_time=datetime.now(),
        )

        self.scheduler.start()
        self.running = True
        logger.info("Crawl scheduler started")

    def stop(self) -> None:
        """停止调度器"""
        if not self.running:
            return

        logger.info("Stopping crawl scheduler")
        if self.scheduler:
            self.scheduler.shutdown()
        self.running = False

    def trigger_crawl(self, source_type: SourceType) -> Optional[Dict[str, Any]]:
        """手动触发抓取"""
        config = self.configs.get(source_type)
        if not config:
            logger.warning(f"No config found for {source_type}")
            return None

        logger.info(f"Manually triggering crawl for {source_type}")
        result = self.orchestrator.crawl_source(
            source_type=config.source_type,
            source_name=config.source_name,
            days=config.days_per_crawl,
            max_docs=config.max_docs,
            enable_backfill=config.backfill_enabled,
        )

        return {
            "source_type": source_type.value,
            "success_count": result.success_count,
            "skipped_count": result.skipped_count,
            "failure_count": result.failure_count,
            "saved_doc_ids": result.saved_doc_ids,
        }

    def trigger_backfill(
        self, source_type: SourceType, lookback_days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """手动触发补漏"""
        config = self.configs.get(source_type)
        if not config:
            logger.warning(f"No config found for {source_type}")
            return None

        logger.info(f"Manually triggering backfill for {source_type}")
        result = self.orchestrator.backfill_source(
            source_type=config.source_type,
            lookback_days=lookback_days,
        )

        return {
            "source_type": source_type.value,
            "success_count": result.success_count,
            "skipped_count": result.skipped_count,
            "failure_count": result.failure_count,
        }

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        status = {
            "running": self.running,
            "sources": [],
        }

        for source_type, config in self.configs.items():
            source_status = self.orchestrator.get_crawl_status(source_type)
            status["sources"].append(
                {
                    "source_type": source_type.value,
                    "enabled": config.enabled,
                    "interval_minutes": config.interval_minutes,
                    "last_backfill": self.last_backfill_times.get(source_type),
                    "crawl_status": source_status,
                }
            )

        if self.scheduler:
            jobs = self.scheduler.get_jobs()
            status["jobs"] = [
                {
                    "id": job.id,
                    "next_run_time": job.next_run_time,
                }
                for job in jobs
            ]

        return status

    def _add_jobs_for_source(self, config: SourceCrawlConfig) -> None:
        """为来源添加调度任务"""
        if not self.scheduler:
            return

        # 常规抓取任务
        job_id = f"crawl_{config.source_type.value}"
        self.scheduler.add_job(
            self._run_crawl_job,
            "interval",
            minutes=config.interval_minutes,
            id=job_id,
            name=f"Crawl {config.source_name}",
            kwargs={"source_type": config.source_type},
            next_run_time=datetime.now(),
        )

        # 补漏任务（如果启用）
        if config.backfill_enabled:
            backfill_job_id = f"backfill_{config.source_type.value}"
            self.scheduler.add_job(
                self._run_backfill_job,
                "interval",
                hours=config.backfill_interval_hours,
                id=backfill_job_id,
                name=f"Backfill {config.source_name}",
                kwargs={"source_type": config.source_type},
                next_run_time=datetime.now() + timedelta(hours=6),
            )

    async def _run_crawl_job(self, source_type: SourceType) -> None:
        """执行抓取任务"""
        config = self.configs.get(source_type)
        if not config:
            return

        try:
            logger.info(f"Running scheduled crawl for {source_type}")
            self.orchestrator.crawl_source(
                source_type=config.source_type,
                source_name=config.source_name,
                days=config.days_per_crawl,
                max_docs=config.max_docs,
                enable_backfill=config.backfill_enabled,
            )
        except Exception as e:
            logger.error(f"Scheduled crawl failed for {source_type}: {e}", exc_info=True)

    async def _run_backfill_job(self, source_type: SourceType) -> None:
        """执行补漏任务"""
        config = self.configs.get(source_type)
        if not config:
            return

        try:
            logger.info(f"Running scheduled backfill for {source_type}")
            self.orchestrator.backfill_source(
                source_type=config.source_type,
                lookback_days=7,
            )
            self.last_backfill_times[source_type] = datetime.utcnow()
        except Exception as e:
            logger.error(f"Scheduled backfill failed for {source_type}: {e}", exc_info=True)

    async def _health_check(self) -> None:
        """健康检查"""
        logger.debug("Health check")
        # 可以在这里添加健康检查逻辑
        # 例如：检查连续失败次数，暂停有问题的来源
        pass


# 全局调度器实例
_scheduler: Optional[CrawlScheduler] = None


def get_crawl_scheduler() -> CrawlScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CrawlScheduler()
    return _scheduler
