"""
采集调度器 - Issue #43: 增量调度机制

基于 APScheduler，提供：
- 定时任务配置
- 任务管理
- 健康检查
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import SourceType
from core.observability import get_logger
from core.utils.trading_calendar import TradingCalendar, get_trading_calendar
from services.crawl_orchestrator import CrawlOrchestrator

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
        deep_backfill_enabled: bool = False,
    ):
        self.source_type = source_type
        self.source_name = source_name or source_type.value
        self.interval_minutes = interval_minutes
        self.days_per_crawl = days_per_crawl
        self.max_docs = max_docs
        self.enabled = enabled
        self.backfill_enabled = backfill_enabled
        self.backfill_interval_hours = backfill_interval_hours
        self.deep_backfill_enabled = deep_backfill_enabled


# 默认配置 — 从数据源注册表自动生成
def _get_default_configs() -> List[SourceCrawlConfig]:
    """从 SourceSpec 注册表构建 SourceCrawlConfig 列表。"""
    from core.source_registry import get_enabled  # 延迟导入避免循环

    configs = []
    for spec in get_enabled():
        configs.append(
            SourceCrawlConfig(
                source_type=spec.source_type,
                source_name=spec.source_name,
                interval_minutes=spec.interval_minutes,
                days_per_crawl=spec.days_per_crawl,
                max_docs=spec.max_docs,
                enabled=spec.enabled,
                backfill_enabled=spec.backfill_enabled,
                backfill_interval_hours=spec.backfill_interval_hours,
                deep_backfill_enabled=spec.deep_backfill_enabled,
            )
        )
    return configs


DEFAULT_CRAWL_CONFIGS = _get_default_configs()


class CrawlScheduler:
    """采集调度器"""

    def __init__(self):
        self.scheduler: Optional[Any] = None
        self.configs: Dict[SourceType, SourceCrawlConfig] = {}
        self.running = False
        self.last_backfill_times: Dict[SourceType, datetime] = {}
        self.calendars: Dict[SourceType, TradingCalendar] = {}

        # 加载默认配置
        for cfg in DEFAULT_CRAWL_CONFIGS:
            self.configs[cfg.source_type] = cfg
            self.calendars[cfg.source_type] = get_trading_calendar()

    def add_config(self, config: SourceCrawlConfig) -> None:
        """添加抓取配置"""
        self.configs[config.source_type] = config
        self.calendars[config.source_type] = get_trading_calendar()

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
            self.scheduler.shutdown(wait=False)
        self.running = False

    def trigger_crawl(self, source_type: SourceType) -> Optional[Dict[str, Any]]:
        """手动触发抓取"""
        config = self.configs.get(source_type)
        if not config:
            logger.warning(f"No config found for {source_type}")
            return None

        logger.info(f"Manually triggering crawl for {source_type}")
        orchestrator = CrawlOrchestrator()
        result = orchestrator.crawl_source(
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
        orchestrator = CrawlOrchestrator()
        result = orchestrator.backfill_source(
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
        now = datetime.now()
        orchestrator = CrawlOrchestrator()
        status = {
            "running": self.running,
            "current_time": now.isoformat(),
            "sources": [],
        }

        for source_type, config in self.configs.items():
            source_status = orchestrator.get_crawl_status(source_type)
            calendar = self.calendars.get(source_type)
            should_run, reason = False, ""
            if calendar:
                should_run, reason = calendar.should_run_now(
                    now,
                    allow_non_trading=True,
                )

            status["sources"].append(
                {
                    "source_type": source_type.value,
                    "enabled": config.enabled,
                    "interval_minutes": config.interval_minutes,
                    "last_backfill": self.last_backfill_times.get(source_type),
                    "crawl_status": source_status,
                    "should_run": should_run,
                    "run_reason": reason,
                }
            )

        if self.scheduler:
            jobs = self.scheduler.get_jobs()
            status["jobs"] = [
                {
                    "id": job.id,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs
            ]

        return status

    def check_source_should_run(self, source_type: SourceType) -> Tuple[bool, str]:
        """
        检查来源是否应该现在运行

        Args:
            source_type: 来源类型

        Returns:
            (bool, str): (是否应该运行, 原因)
        """
        config = self.configs.get(source_type)
        if not config:
            return False, "无配置"

        if not config.enabled:
            return False, "已禁用"

        calendar = self.calendars.get(source_type)
        if not calendar:
            return True, "无日历配置，总是运行"

        return calendar.should_run_now(allow_non_trading=True)

    def _add_jobs_for_source(self, config: SourceCrawlConfig) -> None:
        """为来源添加调度任务（含 ±20% 随机抖动，避免整点雷同）"""
        if not self.scheduler:
            return

        # 常规抓取任务
        job_id = f"crawl_{config.source_type.value}"
        crawl_jitter = int(config.interval_minutes * 60 * 0.2)
        self.scheduler.add_job(
            self._run_crawl_job,
            "interval",
            minutes=config.interval_minutes,
            jitter=crawl_jitter,
            id=job_id,
            name=f"Crawl {config.source_name}",
            kwargs={"source_type": config.source_type},
            next_run_time=datetime.now(),
        )

        # 补漏任务（如果启用）
        if config.backfill_enabled:
            backfill_job_id = f"backfill_{config.source_type.value}"
            backfill_jitter = int(config.backfill_interval_hours * 3600 * 0.2)
            self.scheduler.add_job(
                self._run_backfill_job,
                "interval",
                hours=config.backfill_interval_hours,
                jitter=backfill_jitter,
                id=backfill_job_id,
                name=f"Backfill {config.source_name}",
                kwargs={"source_type": config.source_type},
                next_run_time=datetime.now() + timedelta(hours=6),
            )

        # 深度历史回补 — 按 backfill_family 分类
        from core.source_registry import get as _get_spec

        spec = _get_spec(config.source_type)
        family = spec.backfill_family if spec else None

        if family == "cls":
            # CLS 专属深度回补（每 30 分钟）
            deep_job_id = f"deep_backfill_{config.source_type.value}"
            self.scheduler.add_job(
                self._run_deep_backfill_job,
                "interval",
                minutes=30,
                jitter=360,
                id=deep_job_id,
                name=f"Deep Backfill {config.source_name}",
                next_run_time=datetime.now() + timedelta(minutes=5),
            )

        if config.deep_backfill_enabled and family == "cnstock":
            # CNSTOCK 深度回补（每 6 小时）
            cn_deep_job_id = f"cn_deep_backfill_{config.source_type.value}"
            self.scheduler.add_job(
                self._run_cnstock_deep_backfill_job,
                "interval",
                hours=6,
                jitter=4320,
                id=cn_deep_job_id,
                name=f"CN Deep Backfill {config.source_name}",
                kwargs={"source_type": config.source_type},
                next_run_time=datetime.now() + timedelta(minutes=10),
            )

        if config.deep_backfill_enabled and family == "zq":
            # ZQ 深度回补（每 2 小时）
            zq_deep_job_id = f"zq_deep_backfill_{config.source_type.value}"
            self.scheduler.add_job(
                self._run_zq_deep_backfill_job,
                "interval",
                hours=2,
                jitter=1440,
                id=zq_deep_job_id,
                name=f"ZQ Deep Backfill {config.source_name}",
                next_run_time=datetime.now() + timedelta(minutes=20),
            )

    async def _run_crawl_job(self, source_type: SourceType) -> None:
        """执行抓取任务"""
        config = self.configs.get(source_type)
        if not config:
            return

        should_run, reason = self.check_source_should_run(source_type)
        if not should_run:
            logger.info(f"Skipping crawl for {source_type}: {reason}")
            return

        try:
            logger.info(f"Running scheduled crawl for {source_type}")
            orchestrator = CrawlOrchestrator()
            orchestrator.crawl_source(
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
            orchestrator = CrawlOrchestrator()
            orchestrator.backfill_source(
                source_type=config.source_type,
                lookback_days=7,
            )
            self.last_backfill_times[source_type] = datetime.utcnow()
        except Exception as e:
            logger.error(f"Scheduled backfill failed for {source_type}: {e}", exc_info=True)

    async def _run_deep_backfill_job(self) -> None:
        """执行深度历史回补任务（仅财联社 /detail/{id} 逐条扫描）"""
        try:
            logger.info("Running scheduled deep backfill for CLS")
            orchestrator = CrawlOrchestrator()
            result = orchestrator.deep_backfill_step(batch_size=10)
            logger.info(
                f"Deep backfill done: {result.success_count} saved, "
                f"{result.skipped_count} skipped, {result.failure_count} failed"
            )
        except Exception as e:
            logger.error(f"Scheduled deep backfill failed: {e}", exc_info=True)

    async def _run_cnstock_deep_backfill_job(self, source_type: SourceType) -> None:
        """执行 CNSTOCK 深度回补（max_pages=30，扩展历史覆盖）"""
        config = self.configs.get(source_type)
        if not config:
            return

        should_run, reason = self.check_source_should_run(source_type)
        if not should_run:
            logger.info(f"Skipping CN deep backfill for {source_type}: {reason}")
            return

        try:
            logger.info(f"Running scheduled CN deep backfill for {source_type}")
            orchestrator = CrawlOrchestrator()
            result = orchestrator.backfill_source(
                source_type=config.source_type,
                lookback_days=7,
                max_pages=30,
            )
            logger.info(
                f"CN deep backfill {source_type.value}: {result.success_count} saved, "
                f"{result.skipped_count} skipped, {result.failure_count} failed"
            )
        except Exception as e:
            logger.error(f"CN deep backfill failed for {source_type}: {e}", exc_info=True)

    async def _run_zq_deep_backfill_job(self) -> None:
        """执行 ZQ 滑动窗口深度历史回补"""
        try:
            logger.info("Running scheduled ZQ deep backfill step")
            orchestrator = CrawlOrchestrator()
            result = orchestrator.zq_deep_backfill_step(
                window_days=5,
                max_pages=30,
            )
            logger.info(
                f"ZQ deep backfill step: {result.success_count} saved, "
                f"{result.skipped_count} skipped, {result.failure_count} failed"
            )
        except Exception as e:
            logger.error(f"ZQ deep backfill failed: {e}", exc_info=True)

    async def check_and_backfill_gap(self, source_type: SourceType) -> Optional[Dict[str, Any]]:
        """启动时检测抓取遗漏窗口并回补

        双重检测：
        1. cursor.last_successful_crawl_time（scheduler 上次成功爬取时间）
        2. 数据库中该 source_type 最近一条文档的 created_at（实际覆盖终点）
        取两者中更久的作为有效缺口，避免手动触发/cursor脏数据掩盖真实缺口。
        """
        config = self.configs.get(source_type)
        if not config or not config.enabled:
            return None

        orchestrator = CrawlOrchestrator()
        threshold = config.interval_minutes * 2

        # ── 来源 A：cursor 记录的“上次调度成功时间” ──
        status = orchestrator.get_crawl_status(source_type)
        cursor = (status or {}).get("cursor") if status else None
        cursor_gap_minutes: Optional[float] = None

        if cursor:
            last_crawl_str = cursor.get("last_successful_crawl_time")
            if last_crawl_str:
                try:
                    last_crawl = datetime.fromisoformat(str(last_crawl_str))
                    cursor_gap_minutes = (
                        datetime.utcnow() - last_crawl.replace(tzinfo=None)
                    ).total_seconds() / 60
                except (ValueError, TypeError):
                    pass

        # ── 来源 B：数据库中实际最近文档时间 ──
        db_gap_minutes: Optional[float] = None
        try:
            latest_doc_ts = orchestrator.get_latest_document_time(source_type)
            if latest_doc_ts:
                db_gap_minutes = (
                    datetime.utcnow() - latest_doc_ts.replace(tzinfo=None)
                ).total_seconds() / 60
        except Exception:
            logger.debug(
                f"[startup] {source_type.value}: could not query latest doc time", exc_info=True
            )

        # 取两个来源中更保守（更大）的缺口
        effective_gap = cursor_gap_minutes or 0
        if db_gap_minutes is not None and db_gap_minutes > effective_gap:
            effective_gap = db_gap_minutes

        if cursor_gap_minutes is None and db_gap_minutes is None:
            # 首次启动：cnstock 系列执行 max_pages=50 的初始历史回填
            from core.source_registry import get as _gs

            _sp = _gs(config.source_type)
            if _sp and _sp.backfill_family == "cnstock":
                logger.info(
                    f"[startup] {source_type.value}: no data yet, running initial backfill with max_pages=50"
                )
                try:
                    result = orchestrator.backfill_source(
                        source_type=config.source_type,
                        lookback_days=7,
                        max_pages=50,
                    )
                    self.last_backfill_times[source_type] = datetime.utcnow()
                    logger.info(
                        f"[startup] {source_type.value}: initial backfill completed — "
                        f"{result.success_count} saved, {result.skipped_count} skipped"
                    )
                    return {
                        "source_type": source_type.value,
                        "lookback_days": 7,
                        "max_pages": 50,
                        "success_count": result.success_count,
                        "skipped_count": result.skipped_count,
                    }
                except Exception as e:
                    logger.error(
                        f"[startup] {source_type.value}: initial backfill failed: {e}",
                        exc_info=True,
                    )
                    return None
            logger.info(f"[startup] {source_type.value}: no data yet, skipping gap check")
            return None

        if effective_gap <= threshold:
            logger.info(
                f"[startup] {source_type.value}: effective gap {effective_gap:.0f}min <= "
                f"threshold {threshold}min (cursor={cursor_gap_minutes}min, db={db_gap_minutes}min), "
                f"no backfill needed"
            )
            return None

        lookback_days = max(1, int(effective_gap / (60 * 24)) + 1)
        lookback_days = min(lookback_days, 18)

        logger.info(
            f"[startup] {source_type.value}: effective gap {effective_gap:.0f}min > "
            f"threshold {threshold}min (cursor={cursor_gap_minutes}min, db={db_gap_minutes}min), "
            f"running backfill with lookback={lookback_days}d"
        )

        try:
            from core.source_registry import get as _gs2

            _sp2 = _gs2(config.source_type)
            _max_pages = 50 if (_sp2 and _sp2.backfill_family == "cnstock") else None
            result = orchestrator.backfill_source(
                source_type=config.source_type,
                lookback_days=lookback_days,
                max_pages=_max_pages,
            )
            self.last_backfill_times[source_type] = datetime.utcnow()
            logger.info(
                f"[startup] {source_type.value}: backfill completed — "
                f"{result.success_count} saved, {result.skipped_count} skipped"
            )
            return {
                "source_type": source_type.value,
                "gap_minutes": effective_gap,
                "lookback_days": lookback_days,
                "max_pages": _max_pages,
                "success_count": result.success_count,
                "skipped_count": result.skipped_count,
            }
        except Exception as e:
            logger.error(f"[startup] {source_type.value}: backfill failed: {e}", exc_info=True)
            return None

    async def _health_check(self) -> None:
        """健康检查"""
        logger.debug("Health check")


def build_scheduler_status() -> Dict[str, Any]:
    """纯函数：从 DB 读取所有来源的抓取状态，不依赖 in-process 调度器。

    供 API 路由 / CLI 在跨进程场景使用。
    """
    now = datetime.now()
    orchestrator = CrawlOrchestrator()

    sources = []
    for cfg in DEFAULT_CRAWL_CONFIGS:
        source_status = orchestrator.get_crawl_status(cfg.source_type)
        calendar = get_trading_calendar()
        should_run, reason = calendar.should_run_now(now, allow_non_trading=True)

        sources.append(
            {
                "source_type": cfg.source_type.value,
                "enabled": cfg.enabled,
                "interval_minutes": cfg.interval_minutes,
                "last_backfill": None,
                "crawl_status": source_status,
                "should_run": should_run,
                "run_reason": reason,
            }
        )

    return {
        "running": True,
        "current_time": now.isoformat(),
        "sources": sources,
    }


def get_scheduler_process_status(pid_file: str | None = None) -> Dict[str, Any]:
    """检查调度器进程是否存活（通过 PID 文件）。

    Args:
        pid_file: PID 文件路径，默认使用 logs/scheduler.pid

    Returns:
        {"alive": bool, "pid": int|None, "pid_file": str}
    """
    if pid_file is None:
        pid_file = str(Path(__file__).parent.parent / "logs" / "scheduler.pid")

    result: Dict[str, Any] = {"alive": False, "pid": None, "pid_file": pid_file}

    pid_path = Path(pid_file)
    if not pid_path.exists():
        return result

    try:
        pid = int(pid_path.read_text().strip())
        result["pid"] = pid
        os.kill(pid, 0)
        result["alive"] = True
    except (ValueError, OSError):
        pass

    return result


# 全局调度器实例（仅在调度器 worker 进程内使用）
_scheduler: Optional[CrawlScheduler] = None


def get_crawl_scheduler() -> CrawlScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CrawlScheduler()
    return _scheduler
