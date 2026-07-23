"""Tests for AssetAnalysisService."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from core.contracts import AssetAnalysisCard, AssetAnalysisSnapshot, IndustryData, PriceBar
from services.asset_analysis_service import AssetAnalysisService


def _make_quote(close=100.0, high=105.0, low=95.0):
    """Helper to create a mock quote object."""
    q = Mock()
    q.close = close
    q.high = high
    q.low = low
    q.open = 99.0
    q.volume = 1000000
    q.amount = 100000000.0
    q.timestamp = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return q


class TestAssetAnalysisService:
    """Test suite for AssetAnalysisService."""

    @pytest.mark.asyncio
    async def test_generate_snapshot_with_mock_data(self):
        """Test generating a snapshot with mock data."""
        mock_repo = Mock()
        mock_repo.save.return_value = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
            financial={},
            fund_flow={},
            price_volume={},
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )

        mock_result = Mock()
        mock_result.success = True
        mock_result.data = [_make_quote()]
        mock_result.error_message = None

        mock_coordinator = Mock()
        mock_coordinator.fetch_historical_data.return_value = mock_result

        service = AssetAnalysisService(
            asset_snapshot_repo=mock_repo,
            coordinator=mock_coordinator,
        )

        snapshot = await service.generate_snapshot(
            canonical_id="600000.SH",
            as_of=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
        )

        assert snapshot is not None
        assert snapshot.canonical_id == "600000.SH"
        mock_repo.save.assert_called_once()

    def test_get_latest_snapshot(self):
        """Test getting the latest snapshot for an asset."""
        mock_repo = Mock()
        expected_snapshot = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
            financial={},
            fund_flow={},
            price_volume={},
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )
        mock_repo.get_latest_by_canonical_id.return_value = expected_snapshot

        service = AssetAnalysisService(asset_snapshot_repo=mock_repo)
        snapshot = service.get_latest_snapshot("600000.SH")

        assert snapshot == expected_snapshot
        mock_repo.get_latest_by_canonical_id.assert_called_once_with("600000.SH")

    @pytest.mark.asyncio
    async def test_mock_snapshot_contains_all_fields(self):
        """Test that mock snapshot contains all required fields."""
        mock_repo = Mock()
        mock_repo.save.side_effect = lambda x: x

        mock_result = Mock()
        mock_result.success = True
        mock_result.data = [_make_quote()]
        mock_result.error_message = None

        mock_coordinator = Mock()
        mock_coordinator.fetch_historical_data.return_value = mock_result

        service = AssetAnalysisService(
            asset_snapshot_repo=mock_repo,
            coordinator=mock_coordinator,
        )
        snapshot = await service.generate_snapshot("600000.SH")

        assert snapshot.financial is not None
        assert snapshot.fund_flow is not None
        assert snapshot.price_volume is not None
        assert snapshot.valuation is not None
        assert snapshot.shareholder is not None
        assert snapshot.industry is not None
        assert snapshot.event_impact is not None
        assert snapshot.macro_exposure is not None
        assert snapshot.evidence_refs is not None

    def test_price_bar_keeps_technical_indicator_fields(self):
        """PriceBar should preserve enriched technical indicator fields for the UI."""
        bar = PriceBar(
            date=date(2026, 6, 3),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1_000_000,
            amount=103_000_000,
            turnover=2.5,
            ma5=101.0,
            ma10=100.5,
            ma20=99.8,
            ma60=98.0,
            boll_upper=107.0,
            boll_middle=100.0,
            boll_lower=93.0,
            macd_dif=1.5,
            macd_dea=1.2,
            macd_hist=0.6,
            vwap=102.0,
            pct_change=3.0,
            amplitude=6.0,
        )

        dumped = bar.model_dump()

        assert dumped["boll_upper"] == 107.0
        assert dumped["boll_middle"] == 100.0
        assert dumped["boll_lower"] == 93.0
        assert dumped["macd_dif"] == 1.5
        assert dumped["macd_dea"] == 1.2
        assert dumped["macd_hist"] == 0.6
        assert dumped["vwap"] == 102.0
        assert dumped["pct_change"] == 3.0
        assert dumped["amplitude"] == 6.0

    @pytest.mark.asyncio
    async def test_generate_analysis_card_uses_requested_time_range(self):
        """Analysis card should pass requested time range into K-line enrichment."""
        service = AssetAnalysisService()
        service.generate_snapshot = AsyncMock(
            return_value=AssetAnalysisSnapshot(
                canonical_id="600000.SH",
                as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
                financial={},
                fund_flow={},
                price_volume={},
                valuation={},
                shareholder={},
                industry={},
                event_impact=[],
                macro_exposure={},
                evidence_refs=[],
            )
        )
        service._fill_structured_data = Mock(side_effect=lambda card, snapshot: card)
        service._enrich_from_coordinator = AsyncMock(
            return_value=AssetAnalysisCard(
                canonical_id="600000.SH",
                as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
            )
        )

        await service.generate_analysis_card(
            canonical_id="600000.SH",
            as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
            time_range="2Y",
        )

        service._enrich_from_coordinator.assert_awaited_once()
        assert service._enrich_from_coordinator.await_args.args[3] == "2Y"

    def test_days_from_time_range_maps_wind_style_ranges(self):
        """Time range mapping should support Wind-style quick range buttons."""
        assert AssetAnalysisService._days_from_time_range(None) == 252
        assert AssetAnalysisService._days_from_time_range("1M") == 31
        assert AssetAnalysisService._days_from_time_range("3M") == 92
        assert AssetAnalysisService._days_from_time_range("6M") == 183
        assert AssetAnalysisService._days_from_time_range("1Y") == 365
        assert AssetAnalysisService._days_from_time_range("2Y") == 730
        assert AssetAnalysisService._days_from_time_range("3Y") == 1095
        assert AssetAnalysisService._days_from_time_range("5Y") == 1826
        assert AssetAnalysisService._days_from_time_range("ALL") == 0
        assert AssetAnalysisService._days_from_time_range("all") == 0
        assert AssetAnalysisService._days_from_time_range("unknown") == 252

    @pytest.mark.asyncio
    async def test_enrich_uses_cjpy_then_fast_cache_path_without_slow_fallbacks(self):
        """Asset cards should try Cjpy briefly, then render cached K-lines without slow probes."""
        symbol = "688981.SH"
        market_repo = Mock()
        market_repo.db = None
        stock = Mock()
        stock.name = "中芯国际"
        stock.market = "A-share"
        stock.list_date = None
        stock.industry_level1 = "电子"
        stock.industry_level2 = None
        stock.industry_level3 = None
        market_repo.get_stock_master.return_value = stock
        market_repo.get_latest_shareholders.return_value = []

        result = Mock()
        result.success = True
        result.primary_source = "cache"
        result.data = [
            _make_quote(close=100.0, high=103.0, low=98.0),
            _make_quote(close=102.0, high=104.0, low=99.0),
        ]
        result.data[0].timestamp = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
        result.data[1].timestamp = datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)
        coordinator = Mock()
        coordinator.fetch_historical_data.return_value = result

        service = AssetAnalysisService(coordinator=coordinator, market_repo=market_repo)
        service._fetch_cjpy_price_bars_with_timeout = AsyncMock(return_value=[])
        service._fetch_wind_price_bars_with_timeout = AsyncMock(return_value=[])
        service._fill_wind_market_snapshot = Mock(
            side_effect=AssertionError("Wind snapshot should be skipped in fast cache mode")
        )
        service._get_available_wind_adapter = Mock(
            side_effect=AssertionError("Wind adapter should not be probed")
        )
        service._compute_macro_sensitivity = Mock(
            side_effect=AssertionError("Macro sensitivity should be skipped in fast cache mode")
        )

        card = await service._enrich_from_coordinator(
            AssetAnalysisCard(
                canonical_id=symbol,
                as_of=datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            ),
            symbol,
            datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            "1Y",
        )

        assert card.current_price == 102.0
        assert card.technical["provider"] == "cache"
        assert card.basic_info.name == "中芯国际"
        assert card.industry.sw_level_1 == "电子"
        assert card.top_10_shareholders == []
        service._fetch_cjpy_price_bars_with_timeout.assert_awaited_once()
        service._fetch_wind_price_bars_with_timeout.assert_awaited_once()
        service._fill_wind_market_snapshot.assert_not_called()
        service._compute_macro_sensitivity.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_prefers_cjpy_bars_when_available(self):
        """Cjpy bars should be used for today's asset card when available."""
        service = AssetAnalysisService(coordinator=Mock(), market_repo=None)
        service._fetch_cjpy_price_bars_with_timeout = AsyncMock(
            return_value=[
                PriceBar(
                    date=date(2026, 6, 23),
                    open=100.0,
                    high=106.0,
                    low=99.0,
                    close=105.0,
                    volume=10_000,
                )
            ]
        )
        service._fill_price_bars_from_coordinator = Mock(
            side_effect=AssertionError("Coordinator should not be used when Cjpy returns bars")
        )
        service._fill_wind_market_snapshot = Mock()
        service._fill_industry_data = Mock(return_value=IndustryData())
        service._fill_shareholder_data = AsyncMock(return_value=([], []))
        service._fill_recent_events = Mock(return_value=[])
        service._compute_macro_sensitivity = Mock(return_value=None)

        card = await service._enrich_from_coordinator(
            AssetAnalysisCard(
                canonical_id="688981.SH",
                as_of=datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            ),
            "688981.SH",
            datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            "1Y",
        )

        assert card.current_price == 105.0
        assert card.technical["provider"] == "cjpy"
        service._fill_price_bars_from_coordinator.assert_not_called()

    def test_fetch_cjpy_price_bars_requests_recent_window_and_merges_latest_trade_day(self):
        """Cjpy latest fetch should use a small window for pre-open/non-trading days."""
        requested = {}
        service = AssetAnalysisService(coordinator=Mock(), market_repo=None)
        service._merge_cached_history_with_realtime_bar = Mock(
            return_value=[
                PriceBar(
                    date=date(2026, 6, 22),
                    open=14.2,
                    high=14.6,
                    low=14.1,
                    close=14.4,
                ),
                PriceBar(
                    date=date(2026, 6, 23),
                    open=14.5,
                    high=14.9,
                    low=14.3,
                    close=14.8,
                ),
            ]
        )

        class FakeCjpyAdapter:
            def fetch_daily_quotes(self, codes, start_date, end_date):
                requested["codes"] = codes
                requested["start_date"] = start_date
                requested["end_date"] = end_date
                return pd.DataFrame(
                    [
                        {
                            "时间": "2026-06-22",
                            "open": 14.0,
                            "high": 14.4,
                            "low": 13.9,
                            "close": 14.2,
                            "vol": 900,
                        },
                        {
                            "时间": "2026-06-23",
                            "open": 14.5,
                            "high": 14.9,
                            "low": 14.3,
                            "close": 14.8,
                            "vol": 1000,
                        },
                    ]
                )

        with patch("data_layer.adapters.cjpy_adapter.CjpyAdapter", return_value=FakeCjpyAdapter()):
            bars = service._fetch_cjpy_price_bars(
                "688599.SH",
                date(2025, 6, 23),
                date(2026, 6, 24),
            )

        assert requested == {
            "codes": ["688599.SH"],
            "start_date": "20260610",
            "end_date": "20260624",
        }
        assert bars[-1].date == date(2026, 6, 23)
        assert bars[-1].close == 14.8

    @pytest.mark.asyncio
    async def test_enrich_uses_wind_realtime_when_cjpy_unavailable(self):
        """Wind Excel realtime bars should be tried before cache fallback."""
        service = AssetAnalysisService(coordinator=Mock(), market_repo=None)
        service._fetch_cjpy_price_bars_with_timeout = AsyncMock(return_value=[])
        service._fetch_wind_price_bars_with_timeout = AsyncMock(
            return_value=[
                PriceBar(
                    date=date(2026, 6, 23),
                    open=100.0,
                    high=106.0,
                    low=99.0,
                    close=104.0,
                    volume=10_000,
                )
            ]
        )
        service._fill_price_bars_from_coordinator = Mock(
            side_effect=AssertionError("Coordinator should not be used when Wind returns bars")
        )
        service._fill_wind_market_snapshot = Mock()
        service._fill_industry_data = Mock(return_value=IndustryData())
        service._fill_shareholder_data = AsyncMock(return_value=([], []))
        service._fill_recent_events = Mock(return_value=[])
        service._compute_macro_sensitivity = Mock(return_value=None)

        card = await service._enrich_from_coordinator(
            AssetAnalysisCard(
                canonical_id="688981.SH",
                as_of=datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            ),
            "688981.SH",
            datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC),
            "1Y",
        )

        assert card.current_price == 104.0
        assert card.technical["provider"] == "wind_local"
        service._fill_price_bars_from_coordinator.assert_not_called()

    def test_chip_distribution_profiles_all_supplied_price_volume(self):
        """Chip distribution should preserve volume across the supplied K-line range."""
        bars = [
            PriceBar(
                date=date(2026, 1, 1),
                open=10.0,
                high=10.1,
                low=9.9,
                close=10.0,
                volume=1_000_000,
                turnover=100.0,
            ),
            PriceBar(
                date=date(2026, 1, 2),
                open=20.0,
                high=20.1,
                low=19.9,
                close=20.0,
                volume=1_000_000,
                turnover=100.0,
            ),
            PriceBar(
                date=date(2026, 1, 3),
                open=30.0,
                high=30.1,
                low=29.9,
                close=30.0,
                volume=1_000_000,
                turnover=100.0,
            ),
            PriceBar(
                date=date(2026, 1, 4),
                open=40.0,
                high=40.1,
                low=39.9,
                close=40.0,
                volume=1_000_000,
                turnover=100.0,
            ),
            PriceBar(
                date=date(2026, 1, 5),
                open=50.0,
                high=50.1,
                low=49.9,
                close=50.0,
                volume=1_000_000,
                turnover=100.0,
            ),
        ]

        chip_data = AssetAnalysisService._calculate_chip_distribution(bars, buckets=60)
        peak = max(chip_data, key=lambda point: point.concentration_pct)
        low_cost_concentration = sum(
            point.concentration_pct for point in chip_data if point.price < 15.0
        )
        high_cost_concentration = sum(
            point.concentration_pct for point in chip_data if point.price > 45.0
        )

        assert 9.0 <= peak.price <= 51.0
        assert low_cost_concentration > 10.0
        assert high_cost_concentration > 10.0

    def test_fill_wind_market_snapshot_populates_valuation_turnover_and_basic_info(self):
        """Wind market snapshot should fill empty valuation, turnover, and share fields."""
        wind_adapter = Mock()
        wind_adapter.is_available.return_value = True
        wind_adapter.fetch_market_snapshot.return_value = pd.DataFrame(
            [
                {
                    "code": "600519.SH",
                    "close": 1500.0,
                    "turnover": 0.72,
                    "pe_ttm": 28.5,
                    "pb": 9.1,
                    "pcf_ocf_ttm": 31.2,
                    "total_shares": 1_256_197_800.0,
                }
            ]
        )
        service = AssetAnalysisService(wind_adapter=wind_adapter)
        card = AssetAnalysisCard(
            canonical_id="600519.SH",
            as_of=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
        )

        service._fill_wind_market_snapshot(
            card,
            "600519.SH",
            datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
        )
        basic_info = service._build_basic_info("600519.SH", card.valuation)

        assert card.current_price == 1500.0
        assert card.turnover == 0.72
        assert card.price_volume["turnover"] == 0.72
        assert card.valuation["pe_ttm"] == 28.5
        assert card.valuation["pb"] == 9.1
        assert card.valuation["pcf_ocf_ttm"] == 31.2
        assert card.valuation["total_shares"] == 1_256_197_800.0
        assert card.valuation["market_cap"] == 1_884_296_700_000.0
        assert basic_info.total_shares == 1_256_197_800.0
        assert basic_info.market_cap == 1_884_296_700_000.0
        wind_adapter.fetch_market_snapshot.assert_called_once_with(
            ["600519.SH"], trade_date="2026-06-03"
        )

    def test_fill_industry_data_uses_wind_when_stock_master_has_only_level1(self):
        """Industry fallback should use Wind for missing SW level 2/3 fields."""
        stock = Mock()
        stock.industry_level1 = "食品饮料"
        stock.industry_level2 = None
        stock.industry_level3 = None
        market_repo = Mock()
        market_repo.get_stock_master.return_value = stock
        wind_adapter = Mock()
        wind_adapter.is_available.return_value = True
        wind_adapter.fetch_industry_data.return_value = pd.DataFrame(
            [
                {
                    "code": "600519.SH",
                    "industry_sw": "食品饮料",
                    "industry_sw_l2": "白酒Ⅱ",
                    "industry_sw_l3": "白酒Ⅲ",
                }
            ]
        )
        service = AssetAnalysisService(market_repo=market_repo, wind_adapter=wind_adapter)

        industry = service._fill_industry_data("600519.SH")

        assert industry == IndustryData(
            sw_level_1="食品饮料",
            sw_level_2="白酒Ⅱ",
            sw_level_3="白酒Ⅲ",
        )
        wind_adapter.fetch_industry_data.assert_called_once_with(["600519.SH"])

    @pytest.mark.asyncio
    async def test_fill_shareholder_data_falls_back_to_wind_aggregates_when_db_empty(self):
        """Empty shareholder table should fall back to Wind individual details, then aggregate."""
        market_repo = Mock()
        market_repo.get_latest_shareholders.return_value = []
        wind_adapter = Mock()
        wind_adapter.is_available.return_value = True
        # individual details returns empty -> fall through to aggregate
        wind_adapter.fetch_top10_holder_details.return_value = pd.DataFrame()
        wind_adapter.fetch_holder_data.return_value = pd.DataFrame(
            [
                {
                    "code": "600519.SH",
                    "holder_num": 152345,
                    "top10_pct": 64.3,
                    "institutional_pct": 42.5,
                }
            ]
        )
        service = AssetAnalysisService(market_repo=market_repo, wind_adapter=wind_adapter)

        with patch.object(service, "_latest_report_date", return_value=date(2026, 3, 31)):
            top10, floating = await service._fill_shareholder_data("600519.SH")

        assert floating == []
        assert [holder.name for holder in top10] == ["前十大股东合计", "机构持股合计", "股东户数"]
        assert [holder.share_ratio for holder in top10] == [64.3, 42.5, 0.0]
        assert [holder.shareholder_type for holder in top10] == [
            "aggregate_top10",
            "aggregate_institutional",
            "count:152345",
        ]
        wind_adapter.fetch_holder_data.assert_called_once_with(
            ["600519.SH"], report_date="2026/03/31"
        )
