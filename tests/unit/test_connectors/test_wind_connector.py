"""Wind MarketDataConnector 集成测试 — 使用 mock 验证完整生命周期."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from connectors.market.wind import WindMarketConnector
from core.connectors.base import DiscoveryItem, ParsedTable, RawObject
from core.contracts.ingestion_record import HealthStatus, IngestionRecord, IngestionStatus

# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_daily_quotes_df():
    """模拟日行情 DataFrame."""
    return pd.DataFrame(
        [
            {
                "code": "600519.SH",
                "date": "2026-06-01",
                "open": 1800.0,
                "high": 1820.0,
                "low": 1790.0,
                "close": 1810.0,
                "volume": 5000000,
                "amount": 9050000000.0,
                "turnover": 0.8,
            },
            {
                "code": "600519.SH",
                "date": "2026-06-02",
                "open": 1810.0,
                "high": 1830.0,
                "low": 1805.0,
                "close": 1825.0,
                "volume": 4500000,
                "amount": 8200000000.0,
                "turnover": 0.7,
            },
        ]
    )


@pytest.fixture
def wind_connector():
    connector = WindMarketConnector()
    # Mock is_available to avoid real Excel connection
    return connector


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestWindHealthCheck:
    def test_healthy(self, wind_connector):
        with patch("data_layer.adapters.wind.wind_adapter.WindAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.is_available.return_value = True
            mock_adapter_class.return_value = mock_adapter

            result = wind_connector.health_check()
            assert result == HealthStatus.HEALTHY

    def test_unavailable(self, wind_connector):
        with patch("data_layer.adapters.wind.wind_adapter.WindAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.is_available.return_value = False
            mock_adapter_class.return_value = mock_adapter

            result = wind_connector.health_check()
            assert result == HealthStatus.UNAVAILABLE

    def test_exception(self, wind_connector):
        with patch("data_layer.adapters.wind.wind_adapter.WindAdapter") as mock_adapter_class:
            mock_adapter_class.side_effect = RuntimeError("Excel not running")
            result = wind_connector.health_check()
            assert result == HealthStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestWindDiscover:
    def test_daily_quotes_with_codes(self, wind_connector):
        items = wind_connector.discover(
            dataset="daily_quotes",
            codes=["600519.SH", "000858.SZ"],
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 2
        assert items[0].item_type == "daily_quotes"
        assert items[0].params["code"] == "600519.SH"

    def test_consensus_estimates(self, wind_connector):
        items = wind_connector.discover(
            dataset="consensus_estimates",
            codes=["600519.SH"],
            trade_date="2026-06-01",
        )
        assert len(items) == 1
        assert items[0].item_type == "consensus"

    def test_without_codes(self, wind_connector):
        items = wind_connector.discover(
            dataset="daily_quotes",
            start_date="2026-01-01",
            end_date="2026-06-01",
        )
        assert len(items) == 1
        assert "all" in items[0].item_id

    def test_unknown_dataset(self, wind_connector):
        items = wind_connector.discover(dataset="unknown")
        assert items == []

    def test_all_datasets_discoverable(self, wind_connector):
        """验证所有注册的 dataset 都能 discover 不报错."""
        for ds in wind_connector.datasets:
            items = wind_connector.discover(dataset=ds, codes=["600519.SH"])
            assert len(items) >= 0


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestWindFetch:
    def test_fetch_daily_quotes(self, wind_connector, mock_daily_quotes_df):
        with patch("data_layer.adapters.wind.wind_adapter.WindAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch_daily_quotes.return_value = mock_daily_quotes_df
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="wind_daily_quotes_600519.SH",
                item_type="daily_quotes",
                params={
                    "code": "600519.SH",
                    "start_date": "2026-01-01",
                    "end_date": "2026-06-01",
                },
            )
            raw = wind_connector.fetch(dataset="daily_quotes", item=item)
            assert isinstance(raw, RawObject)
            assert raw.content_type == "application/json"
            assert "wind://daily_quotes/" in raw.source_uri
            assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_dataset_raises(self, wind_connector):
        item = DiscoveryItem(item_id="bad", item_type="bad", params={})
        with pytest.raises(ValueError, match="Unknown dataset"):
            wind_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_table
# ---------------------------------------------------------------------------


class TestWindParseTable:
    def test_parse_daily_quotes(self, wind_connector):
        data = [
            {"code": "600519.SH", "date": "2026-06-01", "open": 1800.0, "close": 1810.0},
            {"code": "600519.SH", "date": "2026-06-02", "open": 1810.0, "close": 1825.0},
        ]
        raw = RawObject(
            data=json.dumps(data),
            content_type="application/json",
            source_uri="wind://test",
            metadata={"dataset": "daily_quotes"},
        )
        table = wind_connector.parse_table(raw)
        assert isinstance(table, ParsedTable)
        assert table.table_name == "daily_quotes"
        assert len(table.rows) == 2

    def test_parse_empty(self, wind_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="wind://test",
            metadata={"dataset": "daily_quotes"},
        )
        table = wind_connector.parse_table(raw)
        assert table.rows == []
        assert table.columns == []


# ---------------------------------------------------------------------------
# normalize_bars
# ---------------------------------------------------------------------------


class TestWindNormalizeBars:
    def test_normalize_daily_quotes(self, wind_connector):
        table = ParsedTable(
            columns=["code", "date", "open", "high", "low", "close", "volume", "amount"],
            rows=[
                {
                    "code": "600519.SH",
                    "date": date(2026, 6, 1),
                    "open": 1800.0,
                    "high": 1820.0,
                    "low": 1790.0,
                    "close": 1810.0,
                    "volume": 5000000,
                    "amount": 9050000000.0,
                }
            ],
            table_name="daily_quotes",
            metadata={"codes": ["600519.SH"]},
        )
        records = wind_connector.normalize_bars(
            dataset="daily_quotes",
            table=table,
            raw_uri="wind://test",
            content_hash="abc123",
        )
        assert len(records) == 1
        assert isinstance(records[0], IngestionRecord)
        assert records[0].source == "wind"
        assert records[0].dataset == "daily_quotes"
        assert records[0].entity_id == "600519.SH"
        assert records[0].payload["close"] == 1810.0
        assert records[0].payload["open"] == 1800.0


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestWindRun:
    def test_run_health_unavailable(self, wind_connector):
        with patch.object(wind_connector, "health_check", return_value=HealthStatus.UNAVAILABLE):
            result = wind_connector.run(dataset="daily_quotes", codes=["600519.SH"])
            assert result.status == IngestionStatus.FAILED

    def test_run_full_lifecycle(self, wind_connector, mock_daily_quotes_df):
        with (
            patch.object(wind_connector, "health_check", return_value=HealthStatus.HEALTHY),
            patch("data_layer.adapters.wind.wind_adapter.WindAdapter") as mock_adapter_class,
            patch.object(wind_connector, "persist", return_value=2),
        ):
            mock_adapter = MagicMock()
            mock_adapter.fetch_daily_quotes.return_value = mock_daily_quotes_df
            mock_adapter_class.return_value = mock_adapter

            result = wind_connector.run(
                dataset="daily_quotes",
                codes=["600519.SH"],
                start_date="2026-01-01",
                end_date="2026-06-01",
            )
            assert result.source == "wind"
            assert result.dataset == "daily_quotes"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1

    def test_run_unknown_dataset(self, wind_connector):
        with patch.object(wind_connector, "health_check", return_value=HealthStatus.HEALTHY):
            result = wind_connector.run(dataset="unknown")
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 0
