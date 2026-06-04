"""AKShare MarketDataConnector 集成测试 — 使用 mock 验证完整生命周期."""
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.market.akshare import AkShareMarketConnector
from core.connectors.base import DiscoveryItem, ParsedTable, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    IngestionStatus,
)

# ---------------------------------------------------------------------------
# Mock fixture: create a connector with mocked AkShareAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_market_data():
    """构造两条模拟行情数据."""
    from data_layer.crawlers.akshare.base import MarketData

    return [
        MarketData(
            symbol="600000.SH",
            timestamp=datetime(2026, 6, 1),
            open=10.5,
            high=11.0,
            low=10.3,
            close=10.8,
            volume=1000000,
            amount=10800000.0,
            turnover=1.5,
            source="akshare",
        ),
        MarketData(
            symbol="600000.SH",
            timestamp=datetime(2026, 6, 2),
            open=10.8,
            high=11.2,
            low=10.7,
            close=11.0,
            volume=1200000,
            amount=13200000.0,
            turnover=1.8,
            source="akshare",
        ),
    ]


@pytest.fixture
def mock_stock_info_list():
    """构造模拟股票列表."""
    from data_layer.crawlers.akshare.base import StockInfo

    return [
        StockInfo(
            symbol="600000.SH",
            name="浦发银行",
            market="SH",
            industry="银行",
        ),
        StockInfo(
            symbol="000001.SZ",
            name="平安银行",
            market="SZ",
            industry="银行",
        ),
    ]


@pytest.fixture
def akshare_connector(mock_market_data, mock_stock_info_list):
    """创建 AKShare connector，mock 掉内部 AkShareAdapter."""
    connector = AkShareMarketConnector()

    # Mock adapter.market methods
    mock_market = MagicMock()
    mock_market.get_historical_data.return_value = mock_market_data
    mock_market.get_stock_list.return_value = mock_stock_info_list
    mock_market.get_index_historical.return_value = mock_market_data

    mock_adapter = MagicMock()
    mock_adapter.health_check.return_value = {"status": "healthy", "source": "akshare"}
    mock_adapter.market = mock_market

    connector._adapter = mock_adapter
    return connector


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestAkShareHealthCheck:
    def test_healthy(self, akshare_connector):
        result = akshare_connector.health_check()
        assert result == HealthStatus.HEALTHY
        assert akshare_connector._health == HealthStatus.HEALTHY

    def test_degraded(self, akshare_connector):
        akshare_connector._adapter.health_check.return_value = {
            "status": "degraded",
            "source": "akshare",
            "error": "slow response",
        }
        result = akshare_connector.health_check()
        assert result == HealthStatus.DEGRADED

    def test_unavailable(self, akshare_connector):
        akshare_connector._adapter.health_check.side_effect = RuntimeError("timeout")
        result = akshare_connector.health_check()
        assert result == HealthStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestAkShareDiscover:
    def test_stock_daily_with_symbols(self, akshare_connector):
        items = akshare_connector.discover(
            dataset="stock_daily",
            symbols=["600000.SH", "000001.SZ"],
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 2
        assert items[0].item_type == "stock_daily"
        assert items[0].params["symbol"] == "600000.SH"
        assert items[0].item_id == "stock_daily_600000.SH_2026-01-01_2026-06-01"

    def test_stock_daily_without_symbols(self, akshare_connector):
        items = akshare_connector.discover(dataset="stock_daily")
        assert len(items) == 1
        assert items[0].item_type == "stock_master"

    def test_stock_master(self, akshare_connector):
        items = akshare_connector.discover(dataset="stock_master")
        assert len(items) == 1
        assert items[0].item_type == "stock_master"

    def test_index_daily(self, akshare_connector):
        items = akshare_connector.discover(
            dataset="index_daily",
            symbol="000001.SH",
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 1
        assert items[0].item_type == "index_daily"
        assert items[0].params["symbol"] == "000001.SH"

    def test_unknown_dataset(self, akshare_connector):
        items = akshare_connector.discover(dataset="unknown_dataset")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestAkShareFetch:
    def test_fetch_stock_daily(self, akshare_connector):
        item = DiscoveryItem(
            item_id="stock_daily_600000.SH_2026-01-01_2026-06-01",
            item_type="stock_daily",
            params={
                "symbol": "600000.SH",
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
            },
        )
        raw = akshare_connector.fetch(dataset="stock_daily", item=item)
        assert isinstance(raw, RawObject)
        assert raw.content_type == "application/json"
        assert "600000.SH" in raw.source_uri
        assert raw.metadata["item_type"] == "stock_daily"
        assert raw.metadata["item_count"] == 2

    def test_fetch_stock_master(self, akshare_connector):
        item = DiscoveryItem(
            item_id="stock_master",
            item_type="stock_master",
            params={},
        )
        raw = akshare_connector.fetch(dataset="stock_master", item=item)
        assert isinstance(raw, RawObject)
        assert raw.metadata["item_type"] == "stock_master"
        assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_type_raises(self, akshare_connector):
        item = DiscoveryItem(item_id="bad", item_type="unknown", params={})
        with pytest.raises(ValueError, match="Unknown item_type"):
            akshare_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_table
# ---------------------------------------------------------------------------


class TestAkShareParseTable:
    def test_parse_market_data(self, akshare_connector):
        data = [
            {"symbol": "600000.SH", "trade_date": "2026-06-01", "open": 10.5, "close": 10.8},
            {"symbol": "600000.SH", "trade_date": "2026-06-02", "open": 10.8, "close": 11.0},
        ]
        raw = RawObject(
            data=json.dumps(data),
            content_type="application/json",
            source_uri="akshare://test",
            metadata={"item_type": "stock_daily", "symbol": "600000.SH"},
        )
        table = akshare_connector.parse_table(raw)
        assert isinstance(table, ParsedTable)
        assert table.table_name == "stock_daily"
        assert len(table.rows) == 2
        assert "symbol" in table.columns
        assert "trade_date" in table.columns

    def test_parse_empty_data(self, akshare_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="akshare://test",
            metadata={"item_type": "stock_daily"},
        )
        table = akshare_connector.parse_table(raw)
        assert table.rows == []
        assert table.columns == []


# ---------------------------------------------------------------------------
# normalize_bars
# ---------------------------------------------------------------------------


class TestAkShareNormalizeBars:
    def test_normalize_stock_daily(self, akshare_connector):
        table = ParsedTable(
            columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "amount"],
            rows=[
                {
                    "symbol": "600000.SH",
                    "trade_date": date(2026, 6, 1),
                    "open": 10.5,
                    "high": 11.0,
                    "low": 10.3,
                    "close": 10.8,
                    "volume": 1000000,
                    "amount": 10800000.0,
                }
            ],
            table_name="stock_daily",
            metadata={"symbol": "600000.SH", "adjustment": "qfq"},
        )
        records = akshare_connector.normalize_bars(
            dataset="stock_daily",
            table=table,
            raw_uri="akshare://test",
            content_hash="abc123",
        )
        assert len(records) == 1
        assert isinstance(records[0], IngestionRecord)
        assert records[0].source == "akshare"
        assert records[0].dataset == "stock_daily"
        assert records[0].asset_type == AssetType.MARKET
        assert records[0].entity_type == EntityType.STOCK
        assert records[0].entity_id == "600000.SH"
        assert records[0].payload["close"] == 10.8
        assert records[0].payload["open"] == 10.5


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestAkShareRun:
    def test_run_stock_daily_full_lifecycle(self, akshare_connector):
        """验证 run() 模版方法完整生命周期."""
        # Mock persist to avoid DB dependency
        with patch.object(akshare_connector, "persist", return_value=1):
            result = akshare_connector.run(
                dataset="stock_daily",
                symbols=["600000.SH"],
                start_date="2026-01-01",
                end_date="2026-06-01",
            )
            assert result.source == "akshare"
            assert result.dataset == "stock_daily"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1
            assert result.stats.fetched >= 1
            assert result.stats.persisted >= 1

    def test_run_unavailable_source(self, akshare_connector):
        """数据源不可用时 run() 应立即返回 UNAVAILABLE."""
        akshare_connector._adapter.health_check.side_effect = RuntimeError("no network")
        result = akshare_connector.run(dataset="stock_daily", symbols=["600000.SH"])
        assert result.status == IngestionStatus.FAILED
        assert result.error_message is not None
