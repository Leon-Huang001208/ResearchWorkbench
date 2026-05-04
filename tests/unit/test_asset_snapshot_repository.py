"""Tests for AssetSnapshotRepositoryImpl."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from core.contracts import AssetAnalysisSnapshot
from data_layer.repositories.asset_snapshot_repository import AssetSnapshotRepositoryImpl
from data_layer.repositories.models import AssetSnapshot


class TestAssetSnapshotRepositoryImpl:
    """Test suite for AssetSnapshotRepositoryImpl."""

    def test_save_new_snapshot(self, db_session):
        """Test saving a new snapshot."""
        repo = AssetSnapshotRepositoryImpl(db_session)
        snapshot = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of=datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
            financial={"pe": 10.0},
            fund_flow={},
            price_volume={},
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )

        saved = repo.save(snapshot)

        assert saved is not None
        assert saved.canonical_id == "600000.SH"

        # Verify in database
        db_result = db_session.query(AssetSnapshot).first()
        assert db_result is not None
        assert db_result.canonical_id == "600000.SH"

    def test_save_update_existing_snapshot(self, db_session):
        """Test updating an existing snapshot."""
        repo = AssetSnapshotRepositoryImpl(db_session)
        snapshot_time = datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC)

        # First save
        snapshot1 = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of=snapshot_time,
            financial={"pe": 10.0},
            fund_flow={},
            price_volume={},
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )
        repo.save(snapshot1)

        # Second save with same time should update
        snapshot2 = AssetAnalysisSnapshot(
            canonical_id="600000.SH",
            as_of=snapshot_time,
            financial={"pe": 15.0},
            fund_flow={},
            price_volume={},
            valuation={},
            shareholder={},
            industry={},
            event_impact=[],
            macro_exposure={},
            evidence_refs=[],
        )
        repo.save(snapshot2)

        # Verify only one record exists with updated data
        db_results = db_session.query(AssetSnapshot).all()
        assert len(db_results) == 1
        assert db_results[0].financial == {"pe": 15.0}

    def test_get_latest_by_canonical_id(self, db_session):
        """Test getting the latest snapshot for an asset."""
        repo = AssetSnapshotRepositoryImpl(db_session)

        # Create multiple snapshots
        times = [
            datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
        ]

        for t in times:
            snapshot = AssetAnalysisSnapshot(
                canonical_id="600000.SH",
                as_of=t,
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
            repo.save(snapshot)

        latest = repo.get_latest_by_canonical_id("600000.SH")

        assert latest is not None
        assert latest.as_of == times[2]

    def test_get_by_canonical_id_and_time_range(self, db_session):
        """Test getting snapshots in a time range."""
        repo = AssetSnapshotRepositoryImpl(db_session)

        # Create multiple snapshots
        times = [
            datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
            datetime(2026, 5, 3, 12, 0, 0, tzinfo=UTC),
        ]

        for t in times:
            snapshot = AssetAnalysisSnapshot(
                canonical_id="600000.SH",
                as_of=t,
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
            repo.save(snapshot)

        results = repo.get_by_canonical_id_and_time_range(
            "600000.SH",
            "2026-05-01T00:00:00",
            "2026-05-02T23:59:59",
        )

        assert len(results) == 2

    def test_get_nonexistent_snapshot(self, db_session):
        """Test getting a snapshot that doesn't exist."""
        repo = AssetSnapshotRepositoryImpl(db_session)
        result = repo.get("nonexistent-id")
        assert result is None

    def test_list_snapshots(self, db_session):
        """Test listing snapshots."""
        repo = AssetSnapshotRepositoryImpl(db_session)

        # Create some snapshots
        for i in range(3):
            snapshot = AssetAnalysisSnapshot(
                canonical_id=f"00000{i}.SZ",
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
            repo.save(snapshot)

        results = repo.list(limit=10)
        assert len(results) == 3
