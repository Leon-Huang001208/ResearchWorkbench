"""
时间窗口策略

根据文章建议：
- 白天（09:00-21:00）：仅使用 AkShare（BaoStock 历史数据是 T+1）
- 晚上（21:00-09:00）：双源完整校验
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import List, Optional

from core.observability import get_logger

logger = get_logger("time_window_strategy")


class TimeWindowMode(Enum):
    """时间窗口模式"""

    DAYTIME = "daytime"  # 白天模式：仅 AkShare
    NIGHTTIME = "nighttime"  # 晚上模式：双源校验


@dataclass
class TimeWindowConfig:
    """时间窗口配置"""

    # 白天开始时间（默认 09:00）
    daytime_start: time = time(hour=9, minute=0)
    # 白天结束时间（默认 21:00）
    daytime_end: time = time(hour=21, minute=0)
    # 白天激活的数据源
    daytime_sources: List[str] = None
    # 晚上激活的数据源
    nighttime_sources: List[str] = None
    # 是否启用双源校验
    enable_dual_validation: bool = True

    def __post_init__(self):
        if self.daytime_sources is None:
            self.daytime_sources = ["akshare"]
        if self.nighttime_sources is None:
            self.nighttime_sources = ["akshare", "baostock"]


@dataclass
class TimeWindowDecision:
    """时间窗口决策结果"""

    current_mode: TimeWindowMode
    active_sources: List[str]
    should_validate: bool
    current_time: datetime
    next_transition: Optional[datetime]


class TimeWindowStrategy:
    """
    时间窗口策略

    根据当前时间决定：
    1. 使用哪些数据源
    2. 是否进行双源校验
    """

    def __init__(self, config: Optional[TimeWindowConfig] = None):
        self.config = config or TimeWindowConfig()
        self.logger = get_logger("time_window_strategy")

    def get_decision(self, current_time: Optional[datetime] = None) -> TimeWindowDecision:
        """
        获取当前时间的决策

        Args:
            current_time: 当前时间（默认现在）

        Returns:
            时间窗口决策
        """
        if current_time is None:
            current_time = datetime.now()

        current_t = current_time.time()

        # 判断模式
        if self.config.daytime_start <= current_t < self.config.daytime_end:
            mode = TimeWindowMode.DAYTIME
            active_sources = self.config.daytime_sources
            should_validate = False  # 白天不做双源校验
        else:
            mode = TimeWindowMode.NIGHTTIME
            active_sources = self.config.nighttime_sources
            should_validate = self.config.enable_dual_validation

        # 计算下次切换时间
        next_transition = self._get_next_transition(current_time)

        return TimeWindowDecision(
            current_mode=mode,
            active_sources=active_sources,
            should_validate=should_validate,
            current_time=current_time,
            next_transition=next_transition,
        )

    def _get_next_transition(self, current_time: datetime) -> Optional[datetime]:
        """
        计算下次模式切换时间

        Args:
            current_time: 当前时间

        Returns:
            下次切换时间
        """
        current_t = current_time.time()

        if current_t < self.config.daytime_start:
            # 现在是晚上，下次切换是今天白天开始
            transition = datetime.combine(current_time.date(), self.config.daytime_start)
        elif current_t < self.config.daytime_end:
            # 现在是白天，下次切换是今天晚上开始
            transition = datetime.combine(current_time.date(), self.config.daytime_end)
        else:
            # 现在是晚上，下次切换是明天白天开始
            tomorrow = current_time.date() + timedelta(days=1)
            transition = datetime.combine(tomorrow, self.config.daytime_start)

        return transition

    def is_daytime(self, current_time: Optional[datetime] = None) -> bool:
        """
        判断是否是白天

        Args:
            current_time: 当前时间

        Returns:
            是否是白天
        """
        decision = self.get_decision(current_time)
        return decision.current_mode == TimeWindowMode.DAYTIME

    def is_nighttime(self, current_time: Optional[datetime] = None) -> bool:
        """
        判断是否是晚上

        Args:
            current_time: 当前时间

        Returns:
            是否是晚上
        """
        decision = self.get_decision(current_time)
        return decision.current_mode == TimeWindowMode.NIGHTTIME

    def get_active_sources(self, current_time: Optional[datetime] = None) -> List[str]:
        """
        获取当前应该激活的数据源

        Args:
            current_time: 当前时间

        Returns:
            激活的数据源列表
        """
        decision = self.get_decision(current_time)
        return decision.active_sources

    def should_perform_validation(self, current_time: Optional[datetime] = None) -> bool:
        """
        判断是否应该执行双源校验

        Args:
            current_time: 当前时间

        Returns:
            是否应该执行双源校验
        """
        decision = self.get_decision(current_time)
        return decision.should_validate

    def get_fetch_plan(
        self,
        symbol: str,
        current_time: Optional[datetime] = None,
    ) -> "FetchPlan":
        """
        获取数据拉取计划

        Args:
            symbol: 股票代码
            current_time: 当前时间

        Returns:
            拉取计划
        """
        decision = self.get_decision(current_time)

        return FetchPlan(
            symbol=symbol,
            primary_source=decision.active_sources[0] if decision.active_sources else None,
            secondary_sources=decision.active_sources[1:],
            should_validate=decision.should_validate,
            decision=decision,
        )


@dataclass
class FetchPlan:
    """数据拉取计划"""

    symbol: str
    primary_source: Optional[str]  # 主数据源
    secondary_sources: List[str]  # 辅助数据源
    should_validate: bool  # 是否需要校验
    decision: TimeWindowDecision  # 原始决策

    @property
    def all_sources(self) -> List[str]:
        """所有需要拉取的数据源"""
        sources = []
        if self.primary_source:
            sources.append(self.primary_source)
        sources.extend(self.secondary_sources)
        return sources

