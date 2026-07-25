"""
AkShare 适配器单元测试
"""

from datetime import date, datetime
from unittest.mock import Mock

import pytest

from data_layer.crawlers.akshare import (
    DEFAULT_CONFIG,
    AkShareAdapter,
    AkShareConfig,
    FinancialData,
    MacroData,
    MarketData,
    NewsData,
    StockInfo,
)


@pytest.fixture
def config():
    """测试配置"""
    return AkShareConfig(
        enable_cache=False,
        verbose=True,
    )


@pytest.fixture
def adapter(config):
    """适配器实例"""
    return AkShareAdapter(config)


class TestAkShareConfig:
    """配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        assert DEFAULT_CONFIG.enable_cache is True
        assert DEFAULT_CONFIG.verbose is False

    def test_custom_config(self):
        """测试自定义配置"""
        config = AkShareConfig(
            enable_cache=False,
            verbose=True,
            news_limit=200,
        )
        assert config.enable_cache is False
        assert config.verbose is True
        assert config.news_limit == 200


class TestDataClasses:
    """数据类测试"""

    def test_market_data(self):
        """测试市场数据"""
        data = MarketData(
            symbol="600000.SH",
            timestamp=datetime.now(),
            open=10.0,
            high=11.0,
            low=9.5,
            close=10.5,
            volume=1000000,
        )
        assert data.symbol == "600000.SH"
        assert data.close == 10.5

    def test_stock_info(self):
        """测试股票信息"""
        stock = StockInfo(
            symbol="600000.SH",
            name="浦发银行",
            market="SH",
            industry="银行",
        )
        assert stock.symbol == "600000.SH"
        assert stock.name == "浦发银行"

    def test_news_data(self):
        """测试新闻数据"""
        news = NewsData(
            title="测试新闻",
            content="新闻内容",
            publish_time=datetime.now(),
            source="test",
        )
        assert news.title == "测试新闻"
        assert news.source == "test"

    def test_financial_data(self):
        """测试财务数据"""
        financial = FinancialData(
            symbol="600000.SH",
            report_date=date(2024, 3, 31),
            report_type="quarterly",
            net_profit=1000000000.0,
            roe=10.5,
        )
        assert financial.symbol == "600000.SH"
        assert financial.report_type == "quarterly"

    def test_macro_data(self):
        """测试宏观数据"""
        macro = MacroData(
            indicator="GDP",
            value=1234567.89,
            period="2024",
            unit="亿元",
        )
        assert macro.indicator == "GDP"
        assert macro.value == 1234567.89


class TestAkShareAdapter:
    """适配器测试"""

    def test_adapter_initialization(self, adapter):
        """测试适配器初始化"""
        assert adapter is not None
        assert adapter.config is not None

    def test_market_fetcher_access(self, adapter):
        """测试行情获取器访问"""
        assert adapter.market is not None

    def test_financial_fetcher_access(self, adapter):
        """测试财务获取器访问"""
        assert adapter.financial is not None

    def test_news_fetcher_access(self, adapter):
        """测试新闻获取器访问"""
        assert adapter.news is not None

    def test_macro_fetcher_access(self, adapter):
        """测试宏观获取器访问"""
        assert adapter.macro is not None


class TestWithMockAkShare:
    """使用 Mock 的 AkShare 测试"""

    @pytest.fixture
    def mock_ak(self):
        """Mock AkShare 模块"""
        mock = Mock()
        return mock

    @pytest.fixture
    def adapter_with_mock(self, config, mock_ak):
        """带 Mock 的适配器"""
        adapter = AkShareAdapter(config)

        # 确保 fetcher 被创建
        _ = adapter.market

        # 替换 ak 属性
        if adapter.market._ak is None:
            adapter.market._initialized = True
            adapter.market._ak = mock_ak

        return adapter

    def test_health_check(self, adapter_with_mock, mock_ak):
        """测试健康检查"""
        # Mock 股票列表返回
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = iter([(0, {"代码": "600000", "名称": "浦发银行", "行业": "银行"})])
        mock_ak.stock_zh_a_spot_em.return_value = mock_df

        result = adapter_with_mock.health_check()

        assert result["status"] in ["healthy", "unhealthy"]  # 可能失败但不崩溃
        assert "timestamp" in result


class TestUtils:
    """工具函数测试（集成测试）"""

    def test_can_import_all(self):
        """测试可以导入所有模块"""
        from data_layer.crawlers.akshare import base, config, financial, macro, market, news, utils

        # 验证模块都可访问
        assert config is not None
        assert base is not None
        assert market is not None
        assert financial is not None
        assert news is not None
        assert macro is not None
        assert utils is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
