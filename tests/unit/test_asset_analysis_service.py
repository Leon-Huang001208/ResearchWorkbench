"""Tests for AssetAnalysisService."""
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.contracts import AssetAnalysisSnapshot
from core.services.asset_analysis_service import AssetAnalysisService


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
