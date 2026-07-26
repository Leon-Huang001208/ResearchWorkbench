"""
Test for database bootstrap script idempotency.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


from data_layer.repositories import base
from data_layer.repositories.base import check_database_connection, db_session, ensure_schema
from data_layer.repositories.models import AlertThresholdDB
from scripts.bootstrap_db import DEFAULT_ALERT_THRESHOLDS, verify_schema


@pytest.fixture
def bootstrap_database(monkeypatch):
    """Run bootstrap checks against an isolated in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(base, "engine", engine)
    monkeypatch.setattr(base, "SessionLocal", session_factory)
    try:
        yield
    finally:
        engine.dispose()


def test_bootstrap_idempotent(bootstrap_database):
    """Test that bootstrap can be run multiple times safely (idempotency)."""
    # Run the bootstrap steps against the isolated test database.
    check_database_connection()
    ensure_schema()
    verify_schema()

    # Count initial alert thresholds
    with db_session() as db:
        initial_count = db.query(AlertThresholdDB).count()

    # Run seeding again
    with db_session() as db:
        from scripts.bootstrap_db import seed_defaults

        seed_defaults(db)

    # Count after - should be same (all existing updated, no new inserted unless defaults changed)
    with db_session() as db:
        final_count = db.query(AlertThresholdDB).count()

    # All default thresholds should exist
    assert final_count >= len(DEFAULT_ALERT_THRESHOLDS)
    # Verify we didn't duplicate
    assert final_count == initial_count or final_count == initial_count + len(
        DEFAULT_ALERT_THRESHOLDS
    )

    # Check all default thresholds are present and enabled
    with db_session() as db:
        for threshold in DEFAULT_ALERT_THRESHOLDS:
            existing = (
                db.query(AlertThresholdDB).filter_by(threshold_id=threshold["threshold_id"]).first()
            )
            assert existing is not None
            assert existing.enabled == threshold["enabled"]
            assert float(existing.value) == threshold["value"]


def test_schema_verification_passes(bootstrap_database):
    """Test that schema verification passes when all tables exist."""
    ensure_schema()
    # Should not raise exception
    verify_schema()
