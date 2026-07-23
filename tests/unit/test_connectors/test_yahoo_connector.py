"""Yahoo MarketDataConnector 单元测试 — mock 验证完整生命周期."""

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.market.yahoo import YahooMarketConnector
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
    """构造两条模拟 Yahoo 行情数据."""
    from data_layer.crawlers.yahoo.base import YahooMarketData

    return [
        YahooMarketData(
            symbol="AAPL",
            timestamp=datetime(2026, 6, 1),
            open=195.0,
            high=198.5,
            low=194.0,
            close=197.0,
            volume=50000000,
            adj_close=196.5,
        ),
        YahooMarketData(
            symbol="AAPL",
            timestamp=datetime(2026, 6, 2),
            open=197.0,
            high=200.0,
            low=196.0,
            close=199.5,
            volume=48000000,
            adj_close=199.0,
        ),
    ]


@pytest.fixture
def mock_stock_info():
    """构造模拟股票信息."""
    from data_layer.crawlers.yahoo.base import YahooStockInfo

    return YahooStockInfo(
        symbol="AAPL",
        name="Apple Inc.",
        currency="USD",
        exchange="NMS",
        country="United States",
        industry="Consumer Electronics",
        sector="Technology",
        market_cap=3000000000000.0,
        pe_ratio=32.5,
        pb_ratio=45.2,
        dividend_yield=0.005,
        beta=1.2,
        fifty_two_week_high=210.0,
        fifty_two_week_low=165.0,
        current_price=197.0,
    )


@pytest.fixture
def yahoo_connector(mock_market_data, mock_stock_info):
    """创建 Yahoo connector，mock 掉内部 YahooAdapter."""
    connector = YahooMarketConnector()

    # Mock adapter.market methods
    mock_market = MagicMock()
    mock_market.get_historical_data.return_value = mock_market_data
    mock_market.get_current_info.return_value = mock_stock_info

    mock_adapter = MagicMock()
    mock_adapter.health_check.return_value = {"status": "healthy", "source": "yahoo"}
    mock_adapter.market = mock_market

    connector._adapter = mock_adapter
    return connector


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestYahooProperties:
    def test_source(self, yahoo_connector):
        assert yahoo_connector.source == "yahoo"

    def test_datasets(self, yahoo_connector):
        assert yahoo_connector.datasets == ["stock_daily", "stock_info"]

    def test_asset_type(self, yahoo_connector):
        assert yahoo_connector.asset_type == "market"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestYahooHealthCheck:
    def test_healthy(self, yahoo_connector):
        result = yahoo_connector.health_check()
        assert result == HealthStatus.HEALTHY
        assert yahoo_connector._health == HealthStatus.HEALTHY

    def test_unhealthy(self, yahoo_connector):
        yahoo_connector._adapter.health_check.return_value = {
            "status": "unhealthy",
            "error": "no connectivity",
        }
        result = yahoo_connector.health_check()
        assert result == HealthStatus.UNAVAILABLE

    def test_unavailable_exception(self, yahoo_connector):
        yahoo_connector._adapter.health_check.side_effect = RuntimeError("timeout")
        result = yahoo_connector.health_check()
        assert result == HealthStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestYahooDiscover:
    def test_stock_daily_with_symbols(self, yahoo_connector):
        items = yahoo_connector.discover(
            dataset="stock_daily",
            symbols=["AAPL", "MSFT"],
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 2
        assert items[0].item_type == "stock_daily"
        assert items[0].params["symbol"] == "AAPL"
        assert "2026-01-01" in items[0].item_id
        assert items[0].params["auto_adjust"] is True

    def test_stock_daily_with_period(self, yahoo_connector):
        items = yahoo_connector.discover(
            dataset="stock_daily",
            symbols=["AAPL"],
            period="1y",
        )
        assert len(items) == 1
        assert items[0].params["period"] == "1y"

    def test_stock_daily_without_symbols(self, yahoo_connector):
        items = yahoo_connector.discover(dataset="stock_daily")
        assert items == []

    def test_stock_info(self, yahoo_connector):
        items = yahoo_connector.discover(dataset="stock_info", symbols=["AAPL"])
        assert len(items) == 1
        assert items[0].item_type == "stock_info"
        assert items[0].params["symbol"] == "AAPL"

    def test_stock_info_without_symbols(self, yahoo_connector):
        items = yahoo_connector.discover(dataset="stock_info")
        assert items == []

    def test_unknown_dataset(self, yahoo_connector):
        items = yahoo_connector.discover(dataset="unknown_dataset")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestYahooFetch:
    def test_fetch_stock_daily(self, yahoo_connector):
        item = DiscoveryItem(
            item_id="stock_daily_AAPL_2026-01-01_2026-06-01",
            item_type="stock_daily",
            params={
                "symbol": "AAPL",
                "start_date": "2026-01-01",
                "end_date": "2026-06-01",
                "period": None,
                "interval": "1d",
                "auto_adjust": True,
            },
        )
        raw = yahoo_connector.fetch(dataset="stock_daily", item=item)
        assert isinstance(raw, RawObject)
        assert raw.content_type == "application/json"
        assert "AAPL" in raw.source_uri
        assert raw.metadata["item_type"] == "stock_daily"
        assert raw.metadata["item_count"] == 2

    def test_fetch_stock_info(self, yahoo_connector):
        item = DiscoveryItem(
            item_id="stock_info_AAPL", item_type="stock_info", params={"symbol": "AAPL"}
        )
        raw = yahoo_connector.fetch(dataset="stock_info", item=item)
        assert isinstance(raw, RawObject)
        assert raw.metadata["item_type"] == "stock_info"
        assert raw.metadata["item_count"] == 1

    def test_fetch_unknown_type_raises(self, yahoo_connector):
        item = DiscoveryItem(item_id="bad", item_type="unknown", params={})
        with pytest.raises(ValueError, match="Unknown item_type"):
            yahoo_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_table
# ---------------------------------------------------------------------------


class TestYahooParseTable:
    def test_parse_market_data(self, yahoo_connector):
        data = [
            {
                "symbol": "AAPL",
                "timestamp": "2026-06-01T00:00:00",
                "open": 195.0,
                "close": 197.0,
                "adj_close": 196.5,
            },
            {
                "symbol": "AAPL",
                "timestamp": "2026-06-02T00:00:00",
                "open": 197.0,
                "close": 199.5,
                "adj_close": 199.0,
            },
        ]
        raw = RawObject(
            data=json.dumps(data),
            content_type="application/json",
            source_uri="yahoo://test",
            metadata={"item_type": "stock_daily", "symbol": "AAPL"},
        )
        table = yahoo_connector.parse_table(raw)
        assert isinstance(table, ParsedTable)
        assert table.table_name == "stock_daily"
        assert len(table.rows) == 2
        assert "symbol" in table.columns
        assert "adj_close" in table.columns

    def test_parse_empty_data(self, yahoo_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="yahoo://test",
            metadata={"item_type": "stock_daily"},
        )
        table = yahoo_connector.parse_table(raw)
        assert table.rows == []
        assert table.columns == []


# ---------------------------------------------------------------------------
# normalize_bars
# ---------------------------------------------------------------------------


class TestYahooNormalizeBars:
    def test_normalize_stock_daily(self, yahoo_connector):
        table = ParsedTable(
            columns=["symbol", "timestamp", "open", "high", "low", "close", "volume", "adj_close"],
            rows=[
                {
                    "symbol": "AAPL",
                    "timestamp": date(2026, 6, 1),
                    "open": 195.0,
                    "high": 198.5,
                    "low": 194.0,
                    "close": 197.0,
                    "volume": 50000000,
                    "adj_close": 196.5,
                }
            ],
            table_name="stock_daily",
            metadata={"symbol": "AAPL"},
        )
        records = yahoo_connector.normalize_bars(
            dataset="stock_daily",
            table=table,
            raw_uri="yahoo://test",
            content_hash="abc123",
        )
        assert len(records) == 1
        assert isinstance(records[0], IngestionRecord)
        assert records[0].source == "yahoo"
        assert records[0].dataset == "stock_daily"
        assert records[0].asset_type == AssetType.MARKET
        assert records[0].entity_type == EntityType.STOCK
        assert records[0].entity_id == "AAPL"
        assert records[0].payload["close"] == 197.0
        assert records[0].payload["open"] == 195.0


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestYahooRun:
    def test_run_stock_daily_full_lifecycle(self, yahoo_connector):
        """验证 run() 模版方法完整生命周期."""
        with patch.object(yahoo_connector, "persist", return_value=1):
            result = yahoo_connector.run(
                dataset="stock_daily",
                symbols=["AAPL"],
                start_date="2026-01-01",
                end_date="2026-06-01",
            )
            assert result.source == "yahoo"
            assert result.dataset == "stock_daily"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1
            assert result.stats.fetched >= 1
            assert result.stats.persisted >= 1

    def test_run_unavailable_source(self, yahoo_connector):
        """数据源不可用时 run() 应立即返回 UNAVAILABLE/FAILED."""
        yahoo_connector._adapter.health_check.side_effect = RuntimeError("no network")
        result = yahoo_connector.run(dataset="stock_daily", symbols=["AAPL"])
        assert result.status == IngestionStatus.FAILED
        assert result.error_message is not None
