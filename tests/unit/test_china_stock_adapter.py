"""China Stock 适配器单元测试"""
from datetime import datetime
from unittest.mock import patch

import pytest

from core.contracts.assets import AssetAnalysisSnapshot
from data_layer.adapters.china_stock import ChinaStockMapper, ChinaStockPluginError
from data_layer.adapters.china_stock_adapter import ChinaStockAdapter
from data_layer.adapters.data_source_router import DataSourceRouter


class TestChinaStockMapper:
    """测试 ChinaStockMapper"""

    def test_map_market_data(self):
        """测试映射行情数据"""
        mapper = ChinaStockMapper()
        raw_data = [
            {
                "code": "000001",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000000,
                "turnover": 10000000.0,
                "date": "2024-01-01",
            }
        ]
        as_of = datetime.now()
        snapshots = mapper.map_market_data("000001", raw_data, as_of)
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert isinstance(snapshot, AssetAnalysisSnapshot)
        assert snapshot.canonical_id.startswith("china_stock:000001:")
        assert snapshot.price_volume["open"] == 10.0
        assert snapshot.price_volume["close"] == 10.5

    def test_map_technical_indicators(self):
        """测试映射技术指标数据"""
        mapper = ChinaStockMapper()
        raw_data = {
            "trend": {"ma5": 10.0, "ma20": 9.5},
            "momentum": {"rsi": 50.0},
            "volatility": {"atr": 0.5},
        }
        as_of = datetime.now()
        snapshots = mapper.map_technical_indicators("000001", raw_data, as_of)
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert snapshot.technical["trend"]["ma5"] == 10.0
        assert snapshot.technical["momentum"]["rsi"] == 50.0

    def test_map_sentiment(self):
        """测试映射情绪数据"""
        mapper = ChinaStockMapper()
        raw_data = {
            "overall_score": 0.7,
            "dimensions": {"market_breadth": 0.8, "limit_up_ratio": 0.6},
        }
        as_of = datetime.now()
        snapshots = mapper.map_sentiment("000001", raw_data, as_of)
        assert len(snapshots) == 1
        snapshot = snapshots[0]
        assert snapshot.sentiment["overall_score"] == 0.7


class TestChinaStockAdapter:
    """测试 ChinaStockAdapter"""

    @patch.object(ChinaStockAdapter, "_call_plugin_tool")
    def test_fetch_stock_quotes(self, mock_call_plugin):
        """测试获取股票行情数据"""
        mock_call_plugin.return_value = {
            "success": True,
            "data": {
                "items": [
                    {
                        "code": "000001",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.5,
                        "close": 10.5,
                        "volume": 1000000,
                        "date": "2024-01-01",
                    }
                ]
            },
        }
        adapter = ChinaStockAdapter()
        import asyncio

        snapshots = asyncio.run(adapter.fetch_stock_quotes(["000001"], "2024-01-01", "2024-01-31"))
        assert len(snapshots) == 1
        assert snapshots[0].price_volume["close"] == 10.5

    @patch.object(ChinaStockAdapter, "_call_plugin_tool")
    def test_fetch_stock_quotes_plugin_error(self, mock_call_plugin):
        """测试插件调用失败"""
        mock_call_plugin.return_value = {"success": False, "message": "Plugin error"}
        adapter = ChinaStockAdapter()
        import asyncio

        with pytest.raises(ChinaStockPluginError):
            asyncio.run(adapter.fetch_stock_quotes(["000001"], "2024-01-01", "2024-01-31"))


class TestDataSourceRouter:
    """测试 DataSourceRouter"""

    @patch("data_layer.adapters.china_stock_adapter.ChinaStockAdapter.fetch_stock_quotes")
    @patch("data_layer.adapters.akshare_adapter.AkShareAdapter.fetch_stock_quotes")
    @patch("data_layer.adapters.ifind_adapter.IFinDAdapter.fetch_stock_quotes")
    def test_router_fallback(self, mock_ifind_fetch, mock_akshare_fetch, mock_cs_fetch):
        """测试降级策略：iFinD 失败后使用 AkShare, then China Stock"""
        from data_layer.adapters.akshare.exceptions import AkShareAdapterError
        from data_layer.adapters.ifind.exceptions import IFinDDatasourceError

        mock_ifind_fetch.side_effect = IFinDDatasourceError("iFinD not available")
        # Make AkShare fail too, so it falls back to ChinaStock
        mock_akshare_fetch.side_effect = AkShareAdapterError("AkShare not available")
        mock_cs_fetch.return_value = [
            AssetAnalysisSnapshot(
                canonical_id="china_stock:000001:20240101:abc123",
                as_of=datetime.now(),
            )
        ]
        router = DataSourceRouter()
        import asyncio

        snapshots = asyncio.run(router.fetch_stock_quotes(["000001"], "2024-01-01", "2024-01-31"))
        assert len(snapshots) == 1
        assert mock_ifind_fetch.called
        assert mock_akshare_fetch.called
        assert mock_cs_fetch.called
