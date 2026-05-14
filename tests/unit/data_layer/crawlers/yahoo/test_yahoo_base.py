
"""
Yahoo Finance 基础模块测试
"""
from datetime import date, datetime, timedelta

import pytest

from data_layer.crawlers.yahoo.base import (
    YahooConfig,
    YahooMarketData,
    YahooStockInfo,
    YahooFinancialData,
    YahooError,
    DEFAULT_CONFIG,
)


class TestYahooConfig:
    """Yahoo 配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = YahooConfig()
        assert config.enable_cache is True
        assert config.base_delay == 2.0
        assert config.max_requests_per_hour == 1800
        assert config.default_interval == "1d"
        assert config.default_period == "1y"
        assert config.auto_adjust is True

    def test_custom_config(self):
        """测试自定义配置"""
        config = YahooConfig(
            enable_cache=False,
            base_delay=3.0,
            max_requests_per_hour=1000,
            default_interval="1wk",
        )
        assert config.enable_cache is False
        assert config.base_delay == 3.0
        assert config.max_requests_per_hour == 1000
        assert config.default_interval == "1wk"


class TestYahooMarketData:
    """Yahoo 市场数据测试"""

    def test_market_data_creation(self):
        """测试创建市场数据"""
        ts = datetime.now()
        data = YahooMarketData(
            symbol="AAPL",
            timestamp=ts,
            open=175.50,
            high=178.20,
            low=174.80,
            close=177.90,
            volume=50000000,
            adj_close=177.90,
        )

        assert data.symbol == "AAPL"
        assert data.timestamp == ts
        assert data.open == 175.50
        assert data.close == 177.90
        assert data.volume == 50000000
        assert data.adj_close == 177.90
        assert data.source == "yahoo"

    def test_market_data_to_dict(self):
        """测试转换为字典"""
        ts = datetime.now()
        data = YahooMarketData(
            symbol="AAPL",
            timestamp=ts,
            open=175.50,
            close=177.90,
        )

        d = data.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["open"] == 175.50
        assert d["close"] == 177.90
        assert d["source"] == "yahoo"
        assert "timestamp" in d


class TestYahooStockInfo:
    """Yahoo 股票信息测试"""

    def test_stock_info_creation(self):
        """测试创建股票信息"""
        info = YahooStockInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
            country="USA",
            industry="Consumer Electronics",
            sector="Technology",
            market_cap=2500000000000,
            pe_ratio=35.5,
            pb_ratio=45.2,
            dividend_yield=0.005,
            beta=1.25,
            fifty_two_week_high=198.23,
            fifty_two_week_low=124.17,
            current_price=177.90,
        )

        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.currency == "USD"
        assert info.market_cap == 2500000000000
        assert info.pe_ratio == 35.5
        assert info.beta == 1.25

    def test_stock_info_to_dict(self):
        """测试转换为字典"""
        info = YahooStockInfo(
            symbol="AAPL",
            name="Apple Inc.",
            currency="USD",
            exchange="NASDAQ",
        )

        d = info.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["name"] == "Apple Inc."
        assert d["currency"] == "USD"


class TestYahooFinancialData:
    """Yahoo 财务数据测试"""

    def test_financial_data_creation(self):
        """测试创建财务数据"""
        report_date = date(2024, 3, 31)
        financial = YahooFinancialData(
            symbol="AAPL",
            report_date=report_date,
            report_type="annual",
            total_revenue=383933000000,
            net_income=96995000000,
            eps=6.16,
            total_assets=352755000000,
            total_liabilities=290023000000,
            total_equity=62732000000,
        )

        assert financial.symbol == "AAPL"
        assert financial.report_date == report_date
        assert financial.report_type == "annual"
        assert financial.total_revenue == 383933000000
        assert financial.net_income == 96995000000
        assert financial.eps == 6.16

    def test_financial_data_to_dict(self):
        """测试转换为字典"""
        report_date = date(2024, 3, 31)
        financial = YahooFinancialData(
            symbol="AAPL",
            report_date=report_date,
            report_type="annual",
        )

        d = financial.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["report_type"] == "annual"


class TestYahooError:
    """Yahoo 错误测试"""

    def test_yahoo_error_creation(self):
        """测试创建 Yahoo 错误"""
        error = YahooError("Test error message")
        assert str(error) == "Test error message"

    def test_yahoo_error_raise(self):
        """测试抛出 Yahoo 错误"""
        with pytest.raises(YahooError) as exc_info:
            raise YahooError("Something went wrong")
        assert "Something went wrong" in str(exc_info.value)

