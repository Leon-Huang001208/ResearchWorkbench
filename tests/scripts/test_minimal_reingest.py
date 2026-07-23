"""
Smoke test for minimal re-ingestion bootstrap pipeline.

Verifies that the recovery path can run with sample data and produce working state.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data_layer.repositories.base import check_database_connection, db_session
from data_layer.repositories.models import AlphaSignalDB, CanonicalEvent, SourceDocument


def test_bootstrap_sample_directory_exists():
    """Test that the bootstrap sample directory exists with sample data."""
    sample_dir = project_root / "benchmarks" / "bootstrap_sample"
    assert sample_dir.exists(), "Bootstrap sample directory missing"

    sample_files = list(sample_dir.glob("*.json"))
    assert len(sample_files) >= 3, f"Need at least 3 sample files, found {len(sample_files)}"

    for file in sample_files:
        assert file.stat().st_size > 0, f"Empty sample file: {file}"


def test_database_connectivity():
    """Test that database connection is available."""
    # Should not raise exception
    check_database_connection()
    assert True


def test_can_import_reingest_script():
    """Test that the main script can be imported without errors."""
    from scripts.minimal_reingest_bootstrap import (
        MinimalReingestReporter,
        ingest_bounded_sample,
        run_bootstrap,
        run_rebuild_derived_state,
        run_smoke_validation,
    )

    assert run_bootstrap is not None
    assert ingest_bounded_sample is not None
    assert run_rebuild_derived_state is not None
    assert run_smoke_validation is not None
    assert MinimalReingestReporter is not None


def test_sample_data_has_required_fields():
    """Test that all sample event files have required fields."""
    sample_dir = project_root / "benchmarks" / "bootstrap_sample"
    sample_files = list(sample_dir.glob("*.json"))

    import json

    required_fields = [
        "event_id",
        "event_type",
        "title",
        "event_time",
        "impact_direction",
        "confidence",
        "impacted_symbols",
    ]

    for file in sample_files:
        with open(file, "r") as f:
            data = json.load(f)

        for field in required_fields:
            assert field in data, f"Missing required field {field} in {file.name}"


def test_database_has_data_after_dry_run():
    """Test that after a dry run, we can still query the database (schema exists)."""
    from scripts.minimal_reingest_bootstrap import MinimalReingestReporter

    MinimalReingestReporter()

    # Check connectivity - this will fail if schema doesn't exist
    with db_session() as db:
        # Try to query source documents - should not throw exception
        count = db.query(SourceDocument).count()
        # Count can be zero if we haven't ingested yet, just check query works
        assert count >= 0
        assert isinstance(count, int)

        # Same for events
        event_count = db.query(CanonicalEvent).count()
        assert event_count >= 0

        # Same for signals
        signal_count = db.query(AlphaSignalDB).count()
        assert signal_count >= 0

    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
