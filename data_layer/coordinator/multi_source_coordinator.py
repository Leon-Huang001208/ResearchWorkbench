"""
多源协调器

整合所有组件，提供统一的接口：
1. 时间窗口策略
2. 数据源拉取
3. 复权对齐
4. 双源校验
5. 告警和审计
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from core.observability import get_logger
from data_layer.crawlers.akshare import AkShareAdapter
from data_layer.crawlers.akshare.base import MarketData
from data_layer.crawlers.baostock import BaoStockAdapter
from data_layer.validation import (
    AdjustmentNormalizer,
    AdjustmentType,
    AlertManager,
    AuditLogger,
    DualSourceValidator,
    FetchPlan,
    TimeWindowStrategy,
    ValidationResult,
    ValidationStatus,
    get_alert_manager,
    get_audit_logger,
)

logger = get_logger("multi_source_coordinator")


@dataclass
class CoordinatorResult:
    """协调器结果"""

    symbol: str
    data: List[MarketData]
    primary_source: str
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
    """

    def __init__(
        self,
        time_window_strategy: Optional[TimeWindowStrategy] = None,
        dual_source_validator: Optional[DualSourceValidator] = None,
        adjustment_normalizer: Optional[AdjustmentNormalizer] = None,
        alert_manager: Optional[AlertManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        target_adjustment: AdjustmentType = AdjustmentType.QFQ,
    ):
        """
        初始化协调器

        Args:
            time_window_strategy: 时间窗口策略
            dual_source_validator: 双源校验器
            adjustment_normalizer: 复权对齐器
            alert_manager: 告警管理器
            audit_logger: 审计日志记录器
            target_adjustment: 目标复权方式
        """
        self.time_window_strategy = time_window_strategy or TimeWindowStrategy()
        self.dual_source_validator = dual_source_validator or DualSourceValidator()
        self.adjustment_normalizer = adjustment_normalizer or AdjustmentNormalizer()
        self.alert_manager = alert_manager or get_alert_manager()
        self.audit_logger = audit_logger or get_audit_logger()
        self.target_adjustment = target_adjustment

        # 初始化适配器
        self.akshare_adapter = AkShareAdapter()
        self.baostock_adapter = BaoStockAdapter()

        self.logger = get_logger("multi_source_coordinator")

    def fetch_historical_data(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force_dual_validation: bool = False,
    ) -> CoordinatorResult:
        """
        获取历史数据（主入口）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            force_dual_validation: 强制双源校验

        Returns:
            协调器结果
        """
        fetch_time = datetime.now()

        # 获取拉取计划
        fetch_plan = self.time_window_strategy.get_fetch_plan(symbol)
        self.logger.info(
            f"Fetch plan for {symbol}: mode={fetch_plan.decision.current_mode.value}, "
            f"sources={fetch_plan.all_sources}"
        )

        # 获取拉取时应该使用的复权参数
        adjust_flags = self.adjustment_normalizer.get_fetch_adjustment_flags(
            self.target_adjustment
        )

        # 拉取数据
        data_by_source = {}
        errors = []

        for source in fetch_plan.all_sources:
            try:
                data = self._fetch_from_source(
                    symbol,
                    source,
                    start_date,
                    end_date,
                    adjust_flags.get(source),
                )
                data_by_source[source] = data
                self.audit_logger.log_fetch(
                    symbol=symbol,
                    source=source,
                    data_count=len(data),
                    success=True,
                )
                self.logger.info(f"Fetched {len(data)} records from {source} for {symbol}")
            except Exception as e:
                self.logger.error(f"Failed to fetch from {source} for {symbol}: {e}")
                errors.append(f"{source}: {str(e)}")
                self.audit_logger.log_fetch(
                    symbol=symbol,
                    source=source,
                    data_count=0,
                    success=False,
                    error=str(e),
                )
                self.alert_manager.send_data_source_error(source, e)

        if not data_by_source:
            # 所有源都失败了
            return CoordinatorResult(
                symbol=symbol,
                data=[],
                primary_source=fetch_plan.primary_source or "unknown",
                sources_used=list(data_by_source.keys()),
                fetch_time=fetch_time,
                success=False,
                error_message="All data sources failed: " + "; ".join(errors),
            )

        # 确定主数据
        primary_source = fetch_plan.primary_source or list(data_by_source.keys())[0]
        if primary_source not in data_by_source:
            # 如果主源失败，选择第一个可用源
            primary_source = list(data_by_source.keys())[0]

        primary_data = data_by_source[primary_source]

        # 执行校验（如果需要）
        validation_result = None
        should_validate = force_dual_validation or fetch_plan.should_validate

        if should_validate and len(data_by_source) >= 2:
            # 获取两个源进行校验
            sources = list(data_by_source.keys())
            source1, source2 = sources[0], sources[1]

            validation_result = self.dual_source_validator.validate(
                symbol=symbol,
                data_source1=data_by_source[source1],
                data_source2=data_by_source[source2],
                source1_name=source1,
                source2_name=source2,
            )

            # 记录校验结果
            self.audit_logger.log_validation(validation_result)

            # 如果校验失败，发送告警
            if validation_result.status != ValidationStatus.PASSED:
                self.alert_manager.send_validation_alert(validation_result)

            # 确定最终使用哪个源
            if validation_result.recommended_source:
                primary_source = validation_result.recommended_source
                if primary_source in data_by_source:
                    primary_data = data_by_source[primary_source]

            self.logger.info(
                f"Validation result for {symbol}: {validation_result.status.value}, "
                f"recommended source: {validation_result.recommended_source}"
            )

        # 记录合并操作
        self.audit_logger.log_merge(
            symbol=symbol,
            sources=list(data_by_source.keys()),
            final_data_count=len(primary_data),
            selected_source=primary_source,
            validation_passed=(validation_result.status == ValidationStatus.PASSED)
            if validation_result
            else False,
        )

        return CoordinatorResult(
            symbol=symbol,
            data=primary_data,
            primary_source=primary_source,
            validation_result=validation_result,
            sources_used=list(data_by_source.keys()),
            fetch_time=fetch_time,
            success=True,
        )

    def _fetch_from_source(
        self,
        symbol: str,
        source: str,
        start_date: Optional[date],
        end_date: Optional[date],
        adjust_flag: Optional[str],
    ) -> List[MarketData]:
        """
        从指定源拉取数据

        Args:
            symbol: 股票代码
            source: 数据源名称
            start_date: 开始日期
            end_date: 结束日期
            adjust_flag: 复权标志

        Returns:
            市场数据列表
        """
        if source == "akshare":
            # AkShare 使用前复权
            adjust = adjust_flag if adjust_flag else "qfq"
            return self.akshare_adapter.market.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        elif source == "baostock":
            # BaoStock 使用对应的 adjustflag
            adjustflag = adjust_flag if adjust_flag else "2"  # 2=前复权
            return self.baostock_adapter.market.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                adjustflag=adjustflag,
            )
        else:
            raise ValueError(f"Unknown data source: {source}")

    def health_check(self) -> dict:
        """
        健康检查

        Returns:
            健康状态字典
        """
        results = {}

        # 检查 AkShare
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

        # 检查时间窗口
        try:
            decision = self.time_window_strategy.get_decision()
            results["time_window"] = {
                "current_mode": decision.current_mode.value,
                "active_sources": decision.active_sources,
                "should_validate": decision.should_validate,
            }
        except Exception as e:
            results["time_window"] = {"status": "error", "error": str(e)}

        return results


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

