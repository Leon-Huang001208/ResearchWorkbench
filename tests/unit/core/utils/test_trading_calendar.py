"""
测试交易日历模块
"""

from datetime import date, datetime, time, timedelta

from core.utils.trading_calendar import (
    AFTERNOON_START,
    MORNING_START,
    TradingCalendar,
    TradingPeriod,
    get_trading_calendar,
)


class TestTradingPeriod:
    """测试交易时段"""

    def test_contains(self):
        """测试时段包含检查"""
        period = TradingPeriod(time(9, 30), time(11, 30), "上午")

        assert period.contains(time(10, 0)) is True
        assert period.contains(time(9, 30)) is True
        assert period.contains(time(11, 29)) is True
        assert period.contains(time(11, 30)) is False
        assert period.contains(time(8, 0)) is False


class TestTradingCalendar:
    """测试交易日历"""

    def test_is_trading_time_morning(self):
        """测试上午交易时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 10, 0, 0)
        assert calendar.is_trading_time(dt) is True

    def test_is_trading_time_afternoon(self):
        """测试下午交易时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 14, 0, 0)
        assert calendar.is_trading_time(dt) is True

    def test_is_not_trading_time_before(self):
        """测试开盘前"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 9, 0, 0)
        assert calendar.is_trading_time(dt) is False

    def test_is_not_trading_time_midday(self):
        """测试午间休市"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 12, 0, 0)
        assert calendar.is_trading_time(dt) is False

    def test_is_not_trading_time_after(self):
        """测试收盘后"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 16, 0, 0)
        assert calendar.is_trading_time(dt) is False

    def test_is_midday_break(self):
        """测试午间休市检查"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 12, 0, 0)
        assert calendar.is_midday_break(dt) is True

        dt = datetime(2024, 5, 11, 11, 30, 0)
        assert calendar.is_midday_break(dt) is True

        dt = datetime(2024, 5, 11, 13, 0, 0)
        assert calendar.is_midday_break(dt) is False

    def test_get_current_period_morning(self):
        """测试获取当前上午时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 10, 0, 0)
        period = calendar.get_current_period(dt)
        assert period is not None
        assert period.name == "上午"

    def test_get_current_period_afternoon(self):
        """测试获取当前下午时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 14, 0, 0)
        period = calendar.get_current_period(dt)
        assert period is not None
        assert period.name == "下午"

    def test_get_current_period_none(self):
        """测试不在交易时段返回None"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 16, 0, 0)
        period = calendar.get_current_period(dt)
        assert period is None

    def test_get_next_session_start_from_before(self):
        """测试从开盘前计算下一时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 8, 0, 0)
        next_start = calendar.get_next_session_start(dt)
        assert next_start.time() == MORNING_START
        assert next_start.date() == dt.date()

    def test_get_next_session_start_from_morning(self):
        """测试从上午交易中计算下一时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 10, 0, 0)
        next_start = calendar.get_next_session_start(dt)
        assert next_start.time() == AFTERNOON_START
        assert next_start.date() == dt.date()

    def test_get_next_session_start_from_midday(self):
        """测试从午间休市计算下一时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 12, 0, 0)
        next_start = calendar.get_next_session_start(dt)
        assert next_start.time() == AFTERNOON_START
        assert next_start.date() == dt.date()

    def test_get_next_session_start_from_afternoon(self):
        """测试从下午交易中计算下一时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 14, 0, 0)
        next_start = calendar.get_next_session_start(dt)
        assert next_start.time() == MORNING_START
        assert next_start.date() == dt.date() + timedelta(days=1)

    def test_get_next_session_start_from_after(self):
        """测试从收盘后计算下一时段"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 16, 0, 0)
        next_start = calendar.get_next_session_start(dt)
        assert next_start.time() == MORNING_START
        assert next_start.date() == dt.date() + timedelta(days=1)

    def test_should_run_now_during_trading(self):
        """测试交易时段应该运行"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 10, 0, 0)
        should_run, reason = calendar.should_run_now(dt, allow_non_trading=False)
        assert should_run is True
        assert "时段" in reason

    def test_should_run_now_midday_break_not_allow(self):
        """测试午间休市不允许运行"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 12, 0, 0)
        should_run, reason = calendar.should_run_now(dt, allow_non_trading=False)
        assert should_run is False
        assert "午间休市" in reason

    def test_should_run_now_midday_break_allow(self):
        """测试午间休市如果允许可以运行"""
        calendar = TradingCalendar()
        dt = datetime(2024, 5, 11, 12, 0, 0)
        should_run, reason = calendar.should_run_now(dt, allow_non_trading=True)
        assert should_run is True
        assert "允许运行" in reason

    def test_include_auction(self):
        """测试包含集合竞价"""
        calendar = TradingCalendar(include_auction=True)
        dt = datetime(2024, 5, 11, 9, 20, 0)
        assert calendar.is_trading_time(dt) is True

        period = calendar.get_current_period(dt)
        assert period is not None
        assert period.name == "集合竞价"

    def test_not_include_auction(self):
        """测试不包含集合竞价"""
        calendar = TradingCalendar(include_auction=False)
        dt = datetime(2024, 5, 11, 9, 20, 0)
        assert calendar.is_trading_time(dt) is False

    def test_get_latest_trading_days_uses_weekdays(self):
        """测试获取最近工作日交易日"""
        calendar = TradingCalendar()

        days = calendar.get_latest_trading_days(n=3, end=date(2024, 5, 13))

        assert days == [
            date(2024, 5, 9),
            date(2024, 5, 10),
            date(2024, 5, 13),
        ]

    def test_get_missing_trading_days(self):
        """测试从已有日期中找缺失工作日"""
        calendar = TradingCalendar()

        missing = calendar.get_missing_trading_days(
            existing_dates={date(2024, 5, 9), date(2024, 5, 13)},
            start=date(2024, 5, 9),
            end=date(2024, 5, 13),
        )

        assert missing == [date(2024, 5, 10)]


class TestGlobalCalendar:
    """测试全局日历实例"""

    def test_get_trading_calendar(self):
        """测试获取全局日历"""
        calendar1 = get_trading_calendar()
        calendar2 = get_trading_calendar()
        assert calendar1 is calendar2

    def test_get_trading_calendar_with_options(self):
        """测试获取带选项的全局日历"""
        # 注意：全局单例，如果第一次调用没有include_auction，之后的调用也不会有
        # 这里只测试能正常返回
        calendar = get_trading_calendar(include_auction=False)
        assert calendar is not None
