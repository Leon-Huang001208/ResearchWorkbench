"""
A股交易日历和时段检查

提供功能：
- 检查当前是否在交易时段
- 检查是否为交易日
- 获取下一个交易时段的开始时间
- 支持午间休市
"""
from datetime import datetime, time, timedelta
from typing import Optional, Tuple

from core.observability import get_logger

logger = get_logger(__name__)


# A股交易时段配置
# 上午：09:30 - 11:30
# 下午：13:00 - 15:00
# 集合竞价：09:15 - 09:25（可选择是否包含）
MORNING_START = time(9, 30, 0)
MORNING_END = time(11, 30, 0)
AFTERNOON_START = time(13, 0, 0)
AFTERNOON_END = time(15, 0, 0)

# 集合竞价时段（可选）
AUCTION_START = time(9, 15, 0)
AUCTION_END = time(9, 25, 0)


class TradingPeriod:
    """交易时段"""

    def __init__(
        self,
        start: time,
        end: time,
        name: str,
    ):
        self.start = start
        self.end = end
        self.name = name

    def contains(self, t: time) -> bool:
        """检查时间是否在时段内"""
        return self.start <= t < self.end


# 标准交易时段
MORNING_SESSION = TradingPeriod(MORNING_START, MORNING_END, "上午")
AFTERNOON_SESSION = TradingPeriod(AFTERNOON_START, AFTERNOON_END, "下午")
AUCTION_SESSION = TradingPeriod(AUCTION_START, AUCTION_END, "集合竞价")


class TradingCalendar:
    """A股交易日历"""

    def __init__(
        self,
        include_auction: bool = False,
        timezone: str = "Asia/Shanghai",
    ):
        self.include_auction = include_auction
        self.timezone = timezone

        # 构建时段列表
        self.periods: list[TradingPeriod] = []
        if include_auction:
            self.periods.append(AUCTION_SESSION)
        self.periods.extend([MORNING_SESSION, AFTERNOON_SESSION])

    def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """
        检查是否在交易时段内

        Args:
            dt: 检查时间，默认当前时间

        Returns:
            bool: 是否在交易时段
        """
        if dt is None:
            dt = datetime.now()

        t = dt.time()

        # 检查是否在任何交易时段内
        for period in self.periods:
            if period.contains(t):
                return True

        return False

    def is_midday_break(self, dt: Optional[datetime] = None) -> bool:
        """
        检查是否在午间休市时段

        Args:
            dt: 检查时间，默认当前时间

        Returns:
            bool: 是否在午间休市
        """
        if dt is None:
            dt = datetime.now()

        t = dt.time()
        return MORNING_END <= t < AFTERNOON_START

    def is_before_trading(self, dt: Optional[datetime] = None) -> bool:
        """检查是否在开盘前"""
        if dt is None:
            dt = datetime.now()

        t = dt.time()
        return t < MORNING_START

    def is_after_trading(self, dt: Optional[datetime] = None) -> bool:
        """检查是否在收盘后"""
        if dt is None:
            dt = datetime.now()

        t = dt.time()
        return t >= AFTERNOON_END

    def get_current_period(self, dt: Optional[datetime] = None) -> Optional[TradingPeriod]:
        """
        获取当前所在的交易时段

        Args:
            dt: 检查时间，默认当前时间

        Returns:
            TradingPeriod | None: 当前时段，如果不在交易时段返回None
        """
        if dt is None:
            dt = datetime.now()

        t = dt.time()

        for period in self.periods:
            if period.contains(t):
                return period

        return None

    def get_next_session_start(self, dt: Optional[datetime] = None) -> datetime:
        """
        获取下一个交易时段的开始时间

        Args:
            dt: 当前时间，默认当前时间

        Returns:
            datetime: 下一个交易时段的开始时间
        """
        if dt is None:
            dt = datetime.now()

        t = dt.time()
        today = dt.date()

        if t < MORNING_START:
            # 开盘前：今天上午开盘
            return datetime.combine(today, MORNING_START)
        elif t < MORNING_END:
            # 上午交易中：下午开盘
            return datetime.combine(today, AFTERNOON_START)
        elif t < AFTERNOON_START:
            # 午间休市：下午开盘
            return datetime.combine(today, AFTERNOON_START)
        elif t < AFTERNOON_END:
            # 下午交易中：明天上午开盘
            next_day = today + timedelta(days=1)
            return datetime.combine(next_day, MORNING_START)
        else:
            # 收盘后：明天上午开盘
            next_day = today + timedelta(days=1)
            return datetime.combine(next_day, MORNING_START)

    def get_time_until_next_session(self, dt: Optional[datetime] = None) -> timedelta:
        """
        获取到下一个交易时段的时间间隔

        Args:
            dt: 当前时间，默认当前时间

        Returns:
            timedelta: 时间间隔
        """
        if dt is None:
            dt = datetime.now()

        next_start = self.get_next_session_start(dt)
        return next_start - dt

    def should_run_now(
        self,
        dt: Optional[datetime] = None,
        allow_non_trading: bool = False,
    ) -> Tuple[bool, str]:
        """
        判断是否现在应该运行调度任务

        Args:
            dt: 当前时间
            allow_non_trading: 如果不在交易时段，是否仍然允许运行

        Returns:
            (bool, str): (是否应该运行, 原因说明)
        """
        if dt is None:
            dt = datetime.now()

        if self.is_trading_time(dt):
            period = self.get_current_period(dt)
            period_name = period.name if period else "交易"
            return True, f"在{period_name}时段"

        if allow_non_trading:
            return True, "非交易时段但允许运行"

        if self.is_midday_break(dt):
            wait_time = self.get_time_until_next_session(dt)
            return False, f"午间休市，{wait_time}后开始下午交易"

        if self.is_before_trading(dt):
            wait_time = self.get_time_until_next_session(dt)
            return False, f"开盘前，{wait_time}后开始交易"

        if self.is_after_trading(dt):
            wait_time = self.get_time_until_next_session(dt)
            return False, f"已收盘，{wait_time}后开始明天交易"

        return False, "不在交易时段"


# 全局交易日历实例
_default_calendar: Optional[TradingCalendar] = None


def get_trading_calendar(
    include_auction: bool = False,
    timezone: str = "Asia/Shanghai",
) -> TradingCalendar:
    """
    获取全局交易日历实例

    Args:
        include_auction: 是否包含集合竞价时段
        timezone: 时区

    Returns:
        TradingCalendar: 交易日历实例
    """
    global _default_calendar

    if _default_calendar is None:
        _default_calendar = TradingCalendar(include_auction=include_auction, timezone=timezone)

    return _default_calendar
