"""市场数据自动调度器 — 交易日后自动拉取 + 缺口检测.

基于 APScheduler，提供：
- 每日收盘后自动拉取行情（cron: 15:37）
- 启动时 + 每 4 小时缺口检测与回补
- 批量处理，自动多源降级（通过 DatasetRouter）

用法:
    scheduler = MarketDataScheduler()
    scheduler.start()
    scheduler.stop()
"""
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, cast

from core.observability import get_logger
from core.utils.trading_calendar import get_trading_calendar

logger = get_logger(__name__)

# APScheduler 可选导入
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not available, market data scheduling disabled")


class MarketDataScheduler:
    """市场数据自动调度器.

    职责：
    - 每日收盘后通过 fallback 路由拉取 daily_quotes
    - 检测已有数据与交易日历之间的缺口并回补
    - 管理启/停状态，支持状态查询

    Attributes:
        running: 调度器是否正在运行.
        scheduler: APScheduler AsyncIOScheduler 实例.
    """

    # 默认配置
    DAILY_CRON_HOUR = 15
    DAILY_CRON_MINUTE = 37  # 错开收盘高峰（15:00），留出数据处理时间
    GAP_CHECK_INTERVAL_HOURS = 4
    BATCH_SIZE = 50  # 每批处理的股票数
    LOOKBACK_DAYS = 5  # 每日拉取的交易日回溯天数
    GAP_LOOKBACK_DAYS = 365  # 缺口检测的最大回溯天数
    INDEX_STRUCTURE_CRON_HOUR = 18
    INDEX_STRUCTURE_CRON_MINUTE = 10
    INDEX_STRUCTURE_MAX_PER_PROVIDER = 20

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        dataset: str = "daily_quotes",
        enable_gap_check: bool = True,
        index_structure_codes: Optional[Dict[str, List[str]]] = None,
        index_structure_max_per_provider: int = INDEX_STRUCTURE_MAX_PER_PROVIDER,
        index_structure_ingestor: Optional[Callable[..., Dict[str, int]]] = None,
        index_structure_session_factory: Optional[Callable[[], Any]] = None,
        index_structure_repo_factory: Optional[Callable[[Any], Any]] = None,
    ):
        """初始化市场数据调度器.

        Args:
            symbols: 要拉取的证券代码列表，None 时从 stock_master 动态读取.
            dataset: 数据集标识，默认 "daily_quotes".
        """
        self._symbols = symbols
        self._dataset = dataset
        self._enable_gap_check = enable_gap_check
        self._index_structure_codes = index_structure_codes
        self._index_structure_max_per_provider = index_structure_max_per_provider
        self._index_structure_ingestor = index_structure_ingestor
        self._index_structure_session_factory = index_structure_session_factory
        self._index_structure_repo_factory = index_structure_repo_factory
        self.running = False
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._calendar = get_trading_calendar()
        self._stats: Dict[str, Any] = {
            "last_daily_run": None,
            "last_gap_check": None,
            "last_gap_count": 0,
            "last_index_structure_run": None,
            "last_index_structure_errors": 0,
            "total_ingested": 0,
            "total_failures": 0,
            "total_index_components": 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动调度器，注册所有定时任务."""
        if not APSCHEDULER_AVAILABLE:
            logger.error("APScheduler not available, cannot start market data scheduler")
            return

        if self.running:
            logger.warning("MarketDataScheduler already running")
            return

        logger.info("Starting MarketDataScheduler")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

        # 1. 每日收盘后拉取
        self.scheduler.add_job(
            self._daily_ingest_job,
            "cron",
            hour=self.DAILY_CRON_HOUR,
            minute=self.DAILY_CRON_MINUTE,
            id="market_data_daily_ingest",
            name="Daily Market Data Ingest",
        )

        # 2. 缺口检测与回补
        if self._enable_gap_check:
            self.scheduler.add_job(
                self._gap_detect_job,
                "interval",
                hours=self.GAP_CHECK_INTERVAL_HOURS,
                id="market_data_gap_check",
                name="Market Data Gap Detection",
                next_run_time=datetime.now() + timedelta(minutes=2),
            )

        # 3. 指数结构日更 — 官网成分股/权重，错开行情拉取与收盘高峰
        self.scheduler.add_job(
            self._index_structure_ingest_job,
            "cron",
            hour=self.INDEX_STRUCTURE_CRON_HOUR,
            minute=self.INDEX_STRUCTURE_CRON_MINUTE,
            id="market_data_index_structure_ingest",
            name="Official Index Structure Ingest",
        )

        self.scheduler.start()
        self.running = True
        logger.info(
            "MarketDataScheduler started",
            extra={
                "daily_cron": f"{self.DAILY_CRON_HOUR}:{self.DAILY_CRON_MINUTE:02d}",
                "gap_interval_hours": self.GAP_CHECK_INTERVAL_HOURS,
                "gap_check_enabled": self._enable_gap_check,
                "index_structure_cron": (
                    f"{self.INDEX_STRUCTURE_CRON_HOUR}:" f"{self.INDEX_STRUCTURE_CRON_MINUTE:02d}"
                ),
            },
        )

    def stop(self) -> None:
        """停止调度器."""
        if not self.running:
            return

        logger.info("Stopping MarketDataScheduler")
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        self.running = False

    def get_status(self) -> Dict[str, Any]:
        """获取调度器运行状态."""
        return {
            "running": self.running,
            "dataset": self._dataset,
            "daily_cron": f"{self.DAILY_CRON_HOUR}:{self.DAILY_CRON_MINUTE:02d}",
            "gap_interval_hours": self.GAP_CHECK_INTERVAL_HOURS,
            "gap_check_enabled": self._enable_gap_check,
            "index_structure_cron": (
                f"{self.INDEX_STRUCTURE_CRON_HOUR}:" f"{self.INDEX_STRUCTURE_CRON_MINUTE:02d}"
            ),
            "stats": dict(self._stats),
        }

    # ------------------------------------------------------------------
    # Job: Daily Ingest
    # ------------------------------------------------------------------

    async def _daily_ingest_job(self) -> None:
        """每日收盘后拉取最近 N 个交易日的行情（job 入口）."""
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._daily_ingest)

    def _daily_ingest(self) -> Dict[str, Any]:
        """同步每日拉取逻辑.

        Returns:
            拉取统计信息.
        """
        from core.connectors.registry import get_connector_registry

        logger.info("market_data_daily_ingest_start")

        symbols = self._get_symbols()
        if not symbols:
            logger.warning("market_data_daily_ingest_no_symbols")
            return {"status": "no_symbols"}

        # 获取最近 N 个交易日
        trading_days = self._calendar.get_latest_trading_days(n=self.LOOKBACK_DAYS)
        if not trading_days:
            logger.warning("market_data_daily_ingest_no_trading_days")
            return {"status": "no_trading_days"}

        start_date = min(trading_days).isoformat()
        end_date = max(trading_days).isoformat()

        reg = get_connector_registry()
        if not reg._connectors:
            reg.discover_all()

        total_ingested = 0
        total_failures = 0

        # 批量处理
        for i in range(0, len(symbols), self.BATCH_SIZE):
            batch = symbols[i : i + self.BATCH_SIZE]
            try:
                result = reg.run_with_fallback(
                    self._dataset,
                    codes=batch,
                    start_date=start_date,
                    end_date=end_date,
                )
                total_ingested += result.stats.persisted
                total_failures += result.stats.failed

                logger.info(
                    "market_data_daily_batch_done",
                    extra={
                        "batch": f"{i // self.BATCH_SIZE + 1}",
                        "symbols": len(batch),
                        "routed_source": result.routed_source or result.source,
                        "fallback_used": result.fallback_used,
                        "persisted": result.stats.persisted,
                        "failed": result.stats.failed,
                    },
                )
            except Exception:
                logger.exception(
                    "market_data_daily_batch_failed",
                    extra={"batch_size": len(batch)},
                )
                total_failures += len(batch)

        self._stats["last_daily_run"] = datetime.now().isoformat()
        self._stats["total_ingested"] += total_ingested
        self._stats["total_failures"] += total_failures

        logger.info(
            "market_data_daily_ingest_done",
            extra={
                "symbols": len(symbols),
                "ingested": total_ingested,
                "failures": total_failures,
                "date_range": f"{start_date}~{end_date}",
            },
        )
        return {
            "status": "completed",
            "symbols": len(symbols),
            "ingested": total_ingested,
            "failures": total_failures,
        }

    # ------------------------------------------------------------------
    # Job: Gap Detection
    # ------------------------------------------------------------------

    async def _gap_detect_job(self) -> None:
        """缺口检测与回补（job 入口）."""
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._gap_detect_and_backfill)

    def _gap_detect_and_backfill(self) -> Dict[str, Any]:
        """同步缺口检测与回补逻辑.

        对比 Cjpy 交易日历与数据库中已有数据，找出缺失日期并回补。

        Returns:
            回补统计信息.
        """
        from data_layer.repositories.base import get_session
        from data_layer.repositories.market_data_repository import MarketDataRepository

        logger.info("market_data_gap_detect_start")

        today = date.today()
        lookback_start = today - timedelta(days=self.GAP_LOOKBACK_DAYS)

        # 获取交易日历中该范围内的所有交易日
        trading_days = self._calendar.get_latest_trading_days(n=self.GAP_LOOKBACK_DAYS)
        if not trading_days:
            logger.warning("market_data_gap_detect_no_calendar")
            return {"status": "no_calendar_data"}

        symbols = self._get_symbols()
        if not symbols:
            logger.warning("market_data_gap_detect_no_symbols")
            return {"status": "no_symbols"}

        # 获取每个 symbol 的已有数据日期
        total_missing = 0
        total_backfilled = 0
        symbols_with_gaps = 0

        try:
            session = get_session()
            repo = MarketDataRepository(db=session)

            for i in range(0, len(symbols), self.BATCH_SIZE):
                batch = symbols[i : i + self.BATCH_SIZE]
                batch_missing: Dict[str, List[date]] = {}

                for sym in batch:
                    existing = repo.get_existing_trade_dates(
                        symbol=sym,
                        source="cjpy",  # 主源
                        start_date=lookback_start.isoformat(),
                        end_date=today.isoformat(),
                    )
                    missing = self._calendar.get_missing_trading_days(
                        existing_dates=existing,
                        start=lookback_start,
                        end=today,
                    )
                    if missing:
                        batch_missing[sym] = missing
                        symbols_with_gaps += 1
                        total_missing += len(missing)

                # 回补有缺口的股票
                if batch_missing:
                    self._backfill_symbols(batch_missing, repo)

                total_backfilled += sum(len(v) for v in batch_missing.values())

            session.close()

        except Exception:
            logger.exception("market_data_gap_detect_failed")

        self._stats["last_gap_check"] = datetime.now().isoformat()
        self._stats["last_gap_count"] = total_missing

        logger.info(
            "market_data_gap_detect_done",
            extra={
                "symbols_checked": len(symbols),
                "symbols_with_gaps": symbols_with_gaps,
                "total_missing_days": total_missing,
                "backfilled": total_backfilled,
            },
        )
        return {
            "status": "completed",
            "symbols_with_gaps": symbols_with_gaps,
            "total_missing_days": total_missing,
            "backfilled": total_backfilled,
        }

    def _backfill_symbols(
        self,
        batch_missing: Dict[str, List[date]],
        repo: Any = None,
    ) -> None:
        """回补指定股票在缺失日期的行情数据.

        Args:
            batch_missing: {symbol: [missing_dates]}.
            repo: MarketDataRepository 实例（可选）.
        """
        from core.connectors.registry import get_connector_registry

        reg = get_connector_registry()
        if not reg._connectors:
            reg.discover_all()

        for symbol, missing_dates in batch_missing.items():
            if not missing_dates:
                continue

            start_date = min(missing_dates).isoformat()
            end_date = max(missing_dates).isoformat()

            try:
                result = reg.run_with_fallback(
                    self._dataset,
                    codes=[symbol],
                    start_date=start_date,
                    end_date=end_date,
                )
                logger.info(
                    "market_data_backfill_symbol",
                    extra={
                        "symbol": symbol,
                        "missing_days": len(missing_dates),
                        "date_range": f"{start_date}~{end_date}",
                        "routed_source": result.routed_source or result.source,
                        "persisted": result.stats.persisted,
                    },
                )
            except Exception:
                logger.exception(
                    "market_data_backfill_symbol_failed",
                    extra={"symbol": symbol, "missing_days": len(missing_dates)},
                )

    # ------------------------------------------------------------------
    # Job: Index Structure Ingest
    # ------------------------------------------------------------------

    async def _index_structure_ingest_job(self) -> None:
        """指数结构批量更新（job 入口）."""
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._index_structure_ingest)

    def _index_structure_ingest(self) -> Dict[str, Any]:
        """Run official CSI/CNI constituent ingestion in scheduler context."""
        from data_layer.repositories.base import db_session
        from data_layer.repositories.market_data_repository import MarketDataRepository
        from services.official_index_structure_ingestion import (
            discover_official_index_codes,
            ingest_official_index_components,
        )

        logger.info("market_data_index_structure_ingest_start")
        provider_codes = self._get_index_structure_codes(discover_official_index_codes)
        if not provider_codes:
            logger.warning("market_data_index_structure_ingest_no_codes")
            return {"status": "no_codes"}

        session_factory = self._index_structure_session_factory or db_session
        repo_factory = self._index_structure_repo_factory or MarketDataRepository
        ingestor = self._index_structure_ingestor or ingest_official_index_components

        totals = {
            "index_master": 0,
            "index_component_snapshot": 0,
            "errors": 0,
        }
        with session_factory() as db:
            repo = repo_factory(db)
            for provider, index_codes in provider_codes.items():
                if not index_codes:
                    continue
                result = ingestor(repo, provider=provider, index_codes=index_codes)
                totals["index_master"] += int(result.get("index_master", 0))
                totals["index_component_snapshot"] += int(result.get("index_component_snapshot", 0))
                totals["errors"] += int(result.get("errors", 0))
                logger.info(
                    "market_data_index_structure_provider_done",
                    extra={
                        "provider": provider,
                        "indices": len(index_codes),
                        "index_master": result.get("index_master", 0),
                        "index_component_snapshot": result.get("index_component_snapshot", 0),
                        "errors": result.get("errors", 0),
                    },
                )

        self._stats["last_index_structure_run"] = datetime.now().isoformat()
        self._stats["last_index_structure_errors"] = totals["errors"]
        self._stats["total_index_components"] += totals["index_component_snapshot"]

        logger.info(
            "market_data_index_structure_ingest_done",
            extra={
                "providers": len(provider_codes),
                "index_master": totals["index_master"],
                "index_component_snapshot": totals["index_component_snapshot"],
                "errors": totals["errors"],
            },
        )
        return {
            "status": "completed",
            "providers": len(provider_codes),
            **totals,
        }

    def _get_index_structure_codes(
        self,
        discoverer: Callable[..., List[str]],
    ) -> Dict[str, List[str]]:
        if self._index_structure_codes is not None:
            return {
                provider.strip().upper(): list(index_codes)
                for provider, index_codes in self._index_structure_codes.items()
            }

        provider_codes = {}
        for provider in ("CSI", "CNI"):
            try:
                provider_codes[provider] = discoverer(
                    provider,
                    max_count=self._index_structure_max_per_provider,
                )
            except Exception:
                logger.exception(
                    "market_data_index_structure_discovery_failed",
                    extra={"provider": provider},
                )
                provider_codes[provider] = []
        return provider_codes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_symbols(self) -> List[str]:
        """获取要拉取的证券代码列表.

        优先使用构造时传入的 symbols 列表，
        否则从 stock_master 表动态读取。

        Returns:
            证券代码列表.
        """
        if self._symbols:
            return list(self._symbols)

        try:
            from data_layer.repositories.base import get_session
            from data_layer.repositories.market_data_repository import MarketDataRepository

            session = get_session()
            repo = MarketDataRepository(db=session)
            symbols = repo.get_all_stock_symbols(limit=5000)
            session.close()
            return cast(List[str], symbols)
        except Exception:
            logger.warning(
                "market_data_get_symbols_from_db_failed",
                exc_info=True,
            )
            return []


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_scheduler: Optional[MarketDataScheduler] = None


def get_market_data_scheduler() -> MarketDataScheduler:
    """获取全局 MarketDataScheduler 单例."""
    global _scheduler
    if _scheduler is None:
        _scheduler = MarketDataScheduler()
    return _scheduler


def reset_market_data_scheduler() -> None:
    """重置全局调度器（测试用）."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.stop()
    _scheduler = None
