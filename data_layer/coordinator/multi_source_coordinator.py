"""
多源协调器

整合所有组件，提供统一的接口：
1. 优先本地缓存
2. 检查缺失范围
3. 数据源拉取（AKShare → BaoStock → Yahoo 自动降级）
4. 更新缓存
5. 复权对齐
6. 双源校验
7. 告警和审计
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from core.observability import get_logger
from data_layer.adapters.akshare_adapter import AKShareAdapter
from data_layer.adapters.baostock_adapter import BaoStockAdapter
from data_layer.adapters.yahoo_adapter import YahooAdapter
from data_layer.coordinator.cache_manager import MarketDataCache, get_market_data_cache
from data_layer.crawlers.akshare.base import MarketData
from data_layer.validation import (
    AdjustmentNormalizer,
    AdjustmentType,
    AlertManager,
    AuditLogger,
    DualSourceValidator,
    ValidationResult,
    ValidationStatus,
    get_alert_manager,
    get_audit_logger,
)

logger = get_logger("multi_source_coordinator")

RECENT_CACHE_TAIL_GAP_DAYS = 4


@dataclass
class CoordinatorResult:
    """协调器结果"""

    symbol: str
    data: List[MarketData]
    primary_source: str
    from_cache: bool = False
    cache_updated: bool = False
    validation_result: Optional[ValidationResult] = None
    sources_used: List[str] = None
    fetch_time: datetime = None
    success: bool = True
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.sources_used is None:
            self.sources_used = []
        if self.fetch_time is None:
            self.fetch_time = datetime.now()


class MultiSourceCoordinator:
    """
    多源协调器

    整合所有组件，提供统一的接口。
    数据源策略：缓存优先 → AKShare → BaoStock → Yahoo 自动降级
    """

    def __init__(
        self,
        adjustment_normalizer: Optional[AdjustmentNormalizer] = None,
        dual_source_validator: Optional[DualSourceValidator] = None,
        alert_manager: Optional[AlertManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        cache: Optional[MarketDataCache] = None,
        use_cache: bool = True,
        target_adjustment: AdjustmentType = AdjustmentType.QFQ,
    ):
        """
        初始化协调器

        Args:
            adjustment_normalizer: 复权对齐器
            dual_source_validator: 双源校验器
            alert_manager: 告警管理器
            audit_logger: 审计日志记录器
            cache: 缓存管理器
            use_cache: 是否使用缓存
            target_adjustment: 目标复权方式
        """
        # 验证和审计组件
        self.adjustment_normalizer = adjustment_normalizer or AdjustmentNormalizer()
        self.dual_source_validator = dual_source_validator or DualSourceValidator()
        self.alert_manager = alert_manager or get_alert_manager()
        self.audit_logger = audit_logger or get_audit_logger()
        self.target_adjustment = target_adjustment

        # 缓存
        self.use_cache = use_cache
        self.cache = cache or get_market_data_cache()

        # 初始化适配器 - 按优先级排序
        self.akshare_adapter = AKShareAdapter()
        self.baostock_adapter = BaoStockAdapter()
        self.yahoo_adapter = YahooAdapter()

        self.logger = get_logger("multi_source_coordinator")

    def _get_available_sources(self) -> List[str]:
        """获取当前可用的数据源列表（按优先级排序）"""
        sources = []
        if self.akshare_adapter.is_available():
            sources.append("akshare")
        if self.baostock_adapter.is_available():
            sources.append("baostock")
        if self.yahoo_adapter.is_available():
            sources.append("yahoo")
        return sources

    def _fetch_from_source(
        self,
        symbol: str,
        source: str,
        start_date: Optional[date],
        end_date: Optional[date],
        adjust_flags: Dict[str, str],
    ) -> List[MarketData]:
        """
        从指定源拉取数据

        Args:
            symbol: 股票代码
            source: 数据源名称
            start_date: 开始日期
            end_date: 结束日期
            adjust_flags: 各数据源的复权参数

        Returns:
            市场数据列表
        """
        if source == "akshare":
            return self.akshare_adapter.crawler_adapter.market.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust_flags.get("akshare", "qfq"),
            )
        elif source == "baostock":
            return self.baostock_adapter.crawler_adapter.market.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjustflag=adjust_flags.get("baostock", "3"),
            )
        elif source == "yahoo":
            return self.yahoo_adapter.crawler_adapter.market.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            raise ValueError(f"Unknown data source: {source}")

    def _fetch_from_available_sources(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        available_sources: List[str],
        adjust_flags: Dict[str, str],
    ) -> tuple[List[MarketData], Optional[str]]:
        """
        从可用的数据源中获取数据（按优先级尝试）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            available_sources: 可用的数据源列表
            adjust_flags: 各数据源的复权参数

        Returns:
            (获取的数据列表, 使用的数据源)
        """
        for source in available_sources:
            try:
                self.logger.info(f"Fetching {symbol} from {source}: {start_date} to {end_date}")
                data = self._fetch_from_source(symbol, source, start_date, end_date, adjust_flags)
                if data:
                    self.audit_logger.log_fetch(
                        symbol=symbol, source=source, data_count=len(data), success=True
                    )
                    self.logger.info(f"Fetched {len(data)} records from {source} for {symbol}")
                    return data, source
                else:
                    self.logger.warning(f"{source} returned empty data for {symbol}")
                    self.audit_logger.log_fetch(
                        symbol=symbol, source=source, data_count=0, success=True
                    )
            except Exception as e:
                self.logger.error(f"Failed to fetch from {source} for {symbol}: {e}")
                self.audit_logger.log_fetch(
                    symbol=symbol, source=source, data_count=0, success=False, error=str(e)
                )
                self.alert_manager.send_data_source_error(source, e)

        return [], None

    def _perform_validation(
        self,
        symbol: str,
        data_by_source: dict[str, List[MarketData]],
        available_sources: List[str],
    ) -> Optional[ValidationResult]:
        """
        执行双源校验

        Args:
            symbol: 股票代码
            data_by_source: 按源分组的数据
            available_sources: 可用的数据源列表

        Returns:
            校验结果，如果没有足够的数据则返回 None
        """
        if len(data_by_source) >= 2:
            # 获取前两个源进行校验
            source1, source2 = available_sources[:2]
            if source1 in data_by_source and source2 in data_by_source:
                validation_result = self.dual_source_validator.validate(
                    symbol=symbol,
                    data_source1=data_by_source[source1],
                    data_source2=data_by_source[source2],
                    source1_name=source1,
                    source2_name=source2,
                )

                self.audit_logger.log_validation(validation_result)

                if validation_result.status != ValidationStatus.PASSED:
                    self.alert_manager.send_validation_alert(validation_result)

                self.logger.info(
                    f"Validation result for {symbol}: {validation_result.status.value}, "
                    f"recommended source: {validation_result.recommended_source}"
                )

                return validation_result

        return None

    def _can_return_recent_cached_tail(
        self,
        cache_range: object,
        missing_ranges: List[tuple[date, date]],
        requested_start: date,
        requested_end: date,
        cached_data: List[MarketData],
    ) -> bool:
        """允许资产页在仅缺最新尾部少量日线时先返回缓存。"""
        if not cached_data or not missing_ranges:
            return False

        if len(missing_ranges) != 1:
            return False

        missing_start, missing_end = missing_ranges[0]
        cache_start = getattr(cache_range, "start_date", None)
        cache_end = getattr(cache_range, "end_date", None)
        if not isinstance(cache_start, date) or not isinstance(cache_end, date):
            return False

        if cache_start > requested_start:
            return False

        today = date.today()
        if requested_end != today or missing_end != requested_end:
            return False

        if missing_start != cache_end + timedelta(days=1):
            return False

        tail_gap_days = (requested_end - cache_end).days
        return 0 < tail_gap_days <= RECENT_CACHE_TAIL_GAP_DAYS

    def fetch_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_refresh: bool = False,
        force_dual_validation: bool = False,
    ) -> CoordinatorResult:
        """
        获取历史数据（主入口）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            force_refresh: 强制刷新缓存
            force_dual_validation: 强制双源校验

        Returns:
            协调器结果
        """
        fetch_time = datetime.now()

        # 设置默认日期范围
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365)  # 默认一年

        self.logger.info(
            f"Requesting data for {symbol}: {start_date} to {end_date}, "
            f"force_refresh={force_refresh}, force_dual_validation={force_dual_validation}"
        )

        # 策略 1: 优先从缓存获取
        if self.use_cache and not force_refresh:
            cache_range = self.cache.get_cache_range(symbol)
            if cache_range:
                # 检查缓存是否完整覆盖了请求的范围
                cache_covers = (
                    cache_range.start_date <= start_date and cache_range.end_date >= end_date
                )
                if cache_covers:
                    cached_data = self.cache.get_cached_data(symbol, start_date, end_date)
                    if cached_data:
                        self.logger.info(
                            f"Cache hit for {symbol}, returning {len(cached_data)} records"
                        )
                        return CoordinatorResult(
                            symbol=symbol,
                            data=cached_data,
                            primary_source="cache",
                            from_cache=True,
                            sources_used=["cache"],
                            fetch_time=fetch_time,
                            success=True,
                        )

        # 策略 2: 如果启用缓存，计算缺失范围。最近尾部缺口先返回缓存，
        # 避免资产页被当日外部行情补数阻塞。
        missing_ranges = []
        if self.use_cache and not force_refresh:
            missing_ranges = self.cache.calculate_missing_ranges(symbol, start_date, end_date)
            if not missing_ranges:
                # 缓存完全覆盖
                cached_data = self.cache.get_cached_data(symbol, start_date, end_date)
                self.logger.info(
                    f"Cache complete for {symbol}, returning {len(cached_data)} records"
                )
                return CoordinatorResult(
                    symbol=symbol,
                    data=cached_data,
                    primary_source="cache",
                    from_cache=True,
                    sources_used=["cache"],
                    fetch_time=fetch_time,
                    success=True,
                )

            self.logger.info(f"Cache missing ranges for {symbol}: {missing_ranges}")

            cache_range = self.cache.get_cache_range(symbol)
            cached_data = self.cache.get_cached_data(symbol, start_date, end_date)
            if cache_range and self._can_return_recent_cached_tail(
                cache_range, missing_ranges, start_date, end_date, cached_data
            ):
                self.logger.info(
                    f"Recent cache tail gap for {symbol}; returning {len(cached_data)} "
                    f"cached records before live backfill"
                )
                return CoordinatorResult(
                    symbol=symbol,
                    data=cached_data,
                    primary_source="cache",
                    from_cache=True,
                    sources_used=["cache"],
                    fetch_time=fetch_time,
                    success=True,
                )

        # 获取可用的数据源
        available_sources = self._get_available_sources()
        if not available_sources:
            return CoordinatorResult(
                symbol=symbol,
                data=[],
                primary_source="none",
                sources_used=[],
                fetch_time=fetch_time,
                success=False,
                error_message="No data sources available",
            )

        self.logger.info(f"Available sources for {symbol}: {available_sources}")

        # 获取拉取时应该使用的复权参数
        adjust_flags = self.adjustment_normalizer.get_fetch_adjustment_flags(self.target_adjustment)

        # 策略 3: 从数据源获取缺失的数据
        data_by_source: Dict[str, List[MarketData]] = {}
        all_new_data: List[MarketData] = []
        used_source = None

        if missing_ranges:
            # 有缓存，只获取缺失的范围
            for miss_start, miss_end in missing_ranges:
                data, source = self._fetch_from_available_sources(
                    symbol, miss_start, miss_end, available_sources, adjust_flags
                )
                if data:
                    # 复权归一化
                    norm_result = self.adjustment_normalizer.normalize(data, self.target_adjustment)
                    if norm_result.warnings:
                        for warning in norm_result.warnings:
                            self.logger.warning(warning)
                    normalized_data = norm_result.data

                    all_new_data.extend(normalized_data)
                    if not used_source:
                        used_source = source
                    if source and source not in data_by_source:
                        data_by_source[source] = []
                    if source:
                        data_by_source[source].extend(normalized_data)
        else:
            # 无缓存或强制刷新，获取整个范围
            all_new_data, used_source = self._fetch_from_available_sources(
                symbol, start_date, end_date, available_sources, adjust_flags
            )
            if used_source and all_new_data:
                # 复权归一化
                norm_result = self.adjustment_normalizer.normalize(
                    all_new_data, self.target_adjustment
                )
                if norm_result.warnings:
                    for warning in norm_result.warnings:
                        self.logger.warning(warning)
                all_new_data = norm_result.data
                data_by_source[used_source] = all_new_data

            # 如果强制双源校验，尝试从第二个源也获取数据
            if force_dual_validation and len(available_sources) >= 2 and used_source:
                second_source = (
                    available_sources[1]
                    if available_sources[0] == used_source
                    else available_sources[0]
                )
                try:
                    second_data = self._fetch_from_source(
                        symbol, second_source, start_date, end_date, adjust_flags
                    )
                    if second_data:
                        # 复权归一化
                        norm_result = self.adjustment_normalizer.normalize(
                            second_data, self.target_adjustment
                        )
                        if norm_result.warnings:
                            for warning in norm_result.warnings:
                                self.logger.warning(warning)
                        normalized_second_data = norm_result.data

                        data_by_source[second_source] = normalized_second_data
                        self.audit_logger.log_fetch(
                            symbol=symbol,
                            source=second_source,
                            data_count=len(normalized_second_data),
                            success=True,
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to fetch from {second_source} for validation: {e}")

        if not all_new_data and not self.use_cache:
            # 没有获取到数据，也没有缓存
            return CoordinatorResult(
                symbol=symbol,
                data=[],
                primary_source=available_sources[0] if available_sources else "none",
                sources_used=available_sources,
                fetch_time=fetch_time,
                success=False,
                error_message="Failed to fetch data from all sources",
            )

        # 策略 4: 更新缓存（如果启用缓存）
        cache_updated = False
        if self.use_cache and all_new_data and used_source:
            self.cache.save_data(symbol, all_new_data, used_source)
            cache_updated = True

        # 策略 5: 合并缓存数据和新数据
        final_data = []
        if self.use_cache:
            final_data = self.cache.get_cached_data(symbol, start_date, end_date)
            if not final_data:
                final_data = all_new_data
        else:
            final_data = all_new_data

        if not final_data:
            return CoordinatorResult(
                symbol=symbol,
                data=[],
                primary_source=used_source or available_sources[0],
                sources_used=available_sources,
                fetch_time=fetch_time,
                success=False,
                error_message="No data available",
            )

        # 策略 6: 执行双源校验（如果需要）
        validation_result = None
        if force_dual_validation:
            validation_result = self._perform_validation(symbol, data_by_source, available_sources)
            # 如果校验结果推荐了另一个源，且我们有那个源的数据，使用那个源
            if (
                validation_result
                and validation_result.recommended_source
                and validation_result.recommended_source in data_by_source
            ):
                self.logger.info(
                    f"Using recommended source from validation: {validation_result.recommended_source}"
                )
                used_source = validation_result.recommended_source
                # 更新缓存（如果需要）
                if self.use_cache and data_by_source[used_source]:
                    self.cache.save_data(symbol, data_by_source[used_source], used_source)
                    final_data = self.cache.get_cached_data(symbol, start_date, end_date)
                    cache_updated = True

        # 记录合并操作
        self.audit_logger.log_merge(
            symbol=symbol,
            sources=list(data_by_source.keys()) or available_sources,
            final_data_count=len(final_data),
            selected_source=used_source or "cache",
            validation_passed=(
                (validation_result.status == ValidationStatus.PASSED)
                if validation_result
                else False
            ),
        )

        self.logger.info(
            f"Returning {len(final_data)} records for {symbol}, "
            f"source={used_source or 'cache'}, cache_updated={cache_updated}"
        )

        return CoordinatorResult(
            symbol=symbol,
            data=final_data,
            primary_source=used_source or "cache",
            from_cache=self.use_cache and not missing_ranges and not force_refresh,
            cache_updated=cache_updated,
            validation_result=validation_result,
            sources_used=available_sources + (["cache"] if self.use_cache else []),
            fetch_time=fetch_time,
            success=True,
        )

    def health_check(self) -> dict:
        """
        健康检查

        Returns:
            健康状态字典
        """
        results = {}

        # 检查缓存
        if self.use_cache:
            try:
                cache_stats = self.cache.get_cache_stats()
                results["cache"] = {
                    "status": "healthy",
                    "total_records": cache_stats["total_records"],
                    "total_symbols": cache_stats["total_symbols"],
                }
            except Exception as e:
                results["cache"] = {"status": "unhealthy", "error": str(e)}

        # 检查 AKShare
        try:
            ak_health = self.akshare_adapter.health_check()
            results["akshare"] = ak_health
        except Exception as e:
            results["akshare"] = {"status": "unhealthy", "error": str(e)}

        # 检查 BaoStock
        try:
            bs_health = self.baostock_adapter.health_check()
            results["baostock"] = bs_health
        except Exception as e:
            results["baostock"] = {"status": "unhealthy", "error": str(e)}

        # 检查 Yahoo
        try:
            yh_health = self.yahoo_adapter.health_check()
            results["yahoo"] = yh_health
        except Exception as e:
            results["yahoo"] = {"status": "unhealthy", "error": str(e)}

        return results

    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除缓存

        Args:
            symbol: 指定符号，None 则清除所有
        """
        if self.use_cache:
            self.cache.clear_cache(symbol)


# 全局协调器实例
_default_coordinator: Optional[MultiSourceCoordinator] = None


def get_coordinator() -> MultiSourceCoordinator:
    """
    获取全局协调器实例

    Returns:
        多源协调器
    """
    global _default_coordinator

    if _default_coordinator is None:
        _default_coordinator = MultiSourceCoordinator()

    return _default_coordinator
