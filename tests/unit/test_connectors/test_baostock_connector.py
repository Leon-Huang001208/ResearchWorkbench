"""BaoStock MarketDataConnector 单元测试 — mock 验证完整生命周期."""

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.market.baostock import BaostockMarketConnector
from core.connectors.base import DiscoveryItem, ParsedTable, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    IngestionStatus,
)

# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_market_data():
    """构造两条模拟行情数据."""
    from data_layer.crawlers.akshare.base import MarketData

    return [
        MarketData(
            symbol="600519.SH",
            timestamp=datetime(2026, 6, 1),
            open=1680.0,
            high=1705.0,
            low=1665.0,
            close=1690.0,
            volume=5000000,
            amount=8450000000.0,
            turnover=0.4,
            source="baostock",
        ),
        MarketData(
            symbol="600519.SH",
            timestamp=datetime(2026, 6, 2),
            open=1690.0,
            high=1720.0,
            low=1688.0,
            close=1710.0,
            volume=4800000,
            amount=8208000000.0,
            turnover=0.38,
            source="baostock",
        ),
    ]


@pytest.fixture
def mock_stock_info_list():
    """构造模拟股票列表."""
    from data_layer.crawlers.akshare.base import StockInfo

    return [
        StockInfo(symbol="600519.SH", name="贵州茅台", market="SH"),
        StockInfo(symbol="000858.SZ", name="五粮液", market="SZ"),
    ]


@pytest.fixture
def baostock_connector(mock_market_data, mock_stock_info_list):
    """创建 Baostock connector，mock 掉内部 BaoStockAdapter."""
    connector = BaostockMarketConnector()

    # Mock adapter.market methods
    mock_market = MagicMock()
    mock_market.get_historical_data.return_value = mock_market_data
    mock_market.get_stock_list.return_value = mock_stock_info_list

    mock_adapter = MagicMock()
    mock_adapter.health_check.return_value = {"status": "healthy", "source": "baostock"}
    mock_adapter.market = mock_market

    connector._adapter = mock_adapter
    return connector


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestBaostockProperties:
    def test_source(self, baostock_connector):
        assert baostock_connector.source == "baostock"

    def test_datasets(self, baostock_connector):
        assert baostock_connector.datasets == ["stock_daily", "stock_master"]

    def test_asset_type(self, baostock_connector):
        assert baostock_connector.asset_type == "market"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestBaostockHealthCheck:
    def test_healthy(self, baostock_connector):
        result = baostock_connector.health_check()
        assert result == HealthStatus.HEALTHY
        assert baostock_connector._health == HealthStatus.HEALTHY

    def test_unhealthy(self, baostock_connector):
        baostock_connector._adapter.health_check.return_value = {
            "status": "unhealthy",
            "error": "login failed",
        }
        result = baostock_connector.health_check()
        assert result == HealthStatus.UNAVAILABLE

    def test_unavailable_exception(self, baostock_connector):
        baostock_connector._adapter.health_check.side_effect = RuntimeError("timeout")
        result = baostock_connector.health_check()
        assert result == HealthStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestBaostockDiscover:
    def test_stock_daily_with_symbols(self, baostock_connector):
        items = baostock_connector.discover(
            dataset="stock_daily",
            symbols=["600519.SH", "000858.SZ"],
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 2
        assert items[0].item_type == "stock_daily"
        assert items[0].params["symbol"] == "600519.SH"
        assert items[0].item_id == "stock_daily_600519.SH_2026-01-01_2026-06-01"

    def test_stock_daily_without_symbols_falls_back_to_master(self, baostock_connector):
        items = baostock_connector.discover(dataset="stock_daily")
        assert len(items) == 1
        assert items[0].item_type == "stock_master"

    def test_stock_master(self, baostock_connector):
        items = baostock_connector.discover(dataset="stock_master")
        assert len(items) == 1
        assert items[0].item_type == "stock_master"

    def test_unknown_dataset(self, baostock_connector):
        items = baostock_connector.discover(dataset="unknown_dataset")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestBaostockFetch:
    def test_fetch_stock_daily(self, baostock_connector):
        item = DiscoveryItem(
            item_id="stock_daily_600519.SH_2026-01-01_2026-06-01",
            item_type="stock_daily",
            params={
                "symbol": "600519.SH",
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
            },
        )
        raw = baostock_connector.fetch(dataset="stock_daily", item=item)
        assert isinstance(raw, RawObject)
        assert raw.content_type == "application/json"
        assert "600519.SH" in raw.source_uri
        assert raw.metadata["item_type"] == "stock_daily"
        assert raw.metadata["item_count"] == 2

    def test_fetch_stock_master(self, baostock_connector):
        item = DiscoveryItem(item_id="stock_master", item_type="stock_master", params={})
        raw = baostock_connector.fetch(dataset="stock_master", item=item)
        assert isinstance(raw, RawObject)
        assert raw.metadata["item_type"] == "stock_master"
        assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_type_raises(self, baostock_connector):
        item = DiscoveryItem(item_id="bad", item_type="unknown", params={})
        with pytest.raises(ValueError, match="Unknown item_type"):
            baostock_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_table
# ---------------------------------------------------------------------------


class TestBaostockParseTable:
    def test_parse_market_data(self, baostock_connector):
        data = [
            {"symbol": "600519.SH", "trade_date": "2026-06-01", "open": 1680.0, "close": 1690.0},
            {"symbol": "600519.SH", "trade_date": "2026-06-02", "open": 1690.0, "close": 1710.0},
        ]
        raw = RawObject(
            data=json.dumps(data),
            content_type="application/json",
            source_uri="baostock://test",
            metadata={"item_type": "stock_daily", "symbol": "600519.SH"},
        )
        table = baostock_connector.parse_table(raw)
        assert isinstance(table, ParsedTable)
        assert table.table_name == "stock_daily"
        assert len(table.rows) == 2
        assert "symbol" in table.columns
        assert "trade_date" in table.columns

    def test_parse_empty_data(self, baostock_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="baostock://test",
            metadata={"item_type": "stock_daily"},
        )
        table = baostock_connector.parse_table(raw)
        assert table.rows == []
        assert table.columns == []


# ---------------------------------------------------------------------------
# normalize_bars
# ---------------------------------------------------------------------------


class TestBaostockNormalizeBars:
    def test_normalize_stock_daily(self, baostock_connector):
        table = ParsedTable(
            columns=[
                "symbol",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover",
            ],
            rows=[
                {
                    "symbol": "600519.SH",
                    "trade_date": date(2026, 6, 1),
                    "open": 1680.0,
                    "high": 1705.0,
                    "low": 1665.0,
                    "close": 1690.0,
                    "volume": 5000000,
                    "amount": 8450000000.0,
                    "turnover": 0.4,
                }
            ],
            table_name="stock_daily",
            metadata={"symbol": "600519.SH", "adjustflag": "3"},
        )
        records = baostock_connector.normalize_bars(
            dataset="stock_daily",
            table=table,
            raw_uri="baostock://test",
            content_hash="abc123",
        )
        assert len(records) == 1
        assert isinstance(records[0], IngestionRecord)
        assert records[0].source == "baostock"
        assert records[0].dataset == "stock_daily"
        assert records[0].asset_type == AssetType.MARKET
        assert records[0].entity_type == EntityType.STOCK
        assert records[0].entity_id == "600519.SH"
        assert records[0].payload["close"] == 1690.0
        assert records[0].payload["open"] == 1680.0
        assert records[0].payload["adjustment"] == "3"


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestBaostockRun:
    def test_run_stock_daily_full_lifecycle(self, baostock_connector):
        """验证 run() 模版方法完整生命周期."""
        with patch.object(baostock_connector, "persist", return_value=1):
            result = baostock_connector.run(
                dataset="stock_daily",
                symbols=["600519.SH"],
                start_date="2026-01-01",
                end_date="2026-06-01",
            )
            assert result.source == "baostock"
            assert result.dataset == "stock_daily"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1
            assert result.stats.fetched >= 1
            assert result.stats.persisted >= 1

    def test_run_unavailable_source(self, baostock_connector):
        """数据源不可用时 run() 应立即返回 UNAVAILABLE/FAILED."""
        baostock_connector._adapter.health_check.side_effect = RuntimeError("no network")
        result = baostock_connector.run(dataset="stock_daily", symbols=["600519.SH"])
        assert result.status == IngestionStatus.FAILED
        assert result.error_message is not None
