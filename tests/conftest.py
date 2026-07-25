"""Test configuration and fixtures."""

import os
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

_POSTGRES_TEST_FLAG = "ALPHAFOUNDRY_RUN_POSTGRES_TESTS"
_POSTGRES_TEST_URL = "ALPHAFOUNDRY_TEST_DATABASE_URL"

if os.environ.get(_POSTGRES_TEST_FLAG) == "1":
    configured_test_url = os.environ.get(_POSTGRES_TEST_URL)
    if configured_test_url:
        os.environ["DATABASE_URL"] = configured_test_url


def pytest_configure(config):
    """Keep default test runs deterministic and offline."""
    os.environ.setdefault("ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS", "1")
    config.addinivalue_line(
        "markers",
        "postgresql: tests that require ALPHAFOUNDRY_RUN_POSTGRES_TESTS=1",
    )


def pytest_collection_modifyitems(config, items):
    """Skip PostgreSQL checks until a dedicated test database is explicitly configured."""
    test_database_url = os.environ.get(_POSTGRES_TEST_URL)
    if os.environ.get(_POSTGRES_TEST_FLAG) == "1" and _is_safe_postgres_test_url(test_database_url):
        return

    reason = (
        f"requires {_POSTGRES_TEST_FLAG}=1 and {_POSTGRES_TEST_URL} targeting a database "
        "whose name contains 'test'"
    )
    skip_postgresql = pytest.mark.skip(reason=reason)
    for item in items:
        if "postgresql" in item.keywords:
            item.add_marker(skip_postgresql)


def _is_safe_postgres_test_url(database_url: str | None) -> bool:
    """Require an isolated PostgreSQL database name before destructive test operations."""
    if not database_url:
        return False
    try:
        parsed = make_url(database_url)
    except Exception:
        return False
    return parsed.drivername.startswith("postgresql") and "test" in (parsed.database or "").lower()


from data_layer.repositories.base import Base


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_model_gateway():
    """Create a mock ModelGateway."""
    gateway = Mock()
    mock_response = Mock()
    mock_response.content = "Generated content"
    gateway.chat.return_value = mock_response
    return gateway


@pytest.fixture
def sample_asset_snapshot_data():
    """Return sample asset snapshot data."""
    return {
        "canonical_id": "600000.SH",
        "as_of": "2026-05-03T12:00:00",
        "financial": {
            "revenue": {"ttm": 15000000000, "qoq": 0.08, "yoy": 0.15},
            "net_profit": {"ttm": 3200000000, "qoq": 0.12, "yoy": 0.22},
        },
        "fund_flow": {"main_net_inflow": 250000000},
        "price_volume": {"close_price": 58.5, "ma20": 55.8},
        "valuation": {"pe_ttm": 24.9, "pb": 3.8},
        "shareholder": {"controlling_shareholder": "某某集团有限公司"},
        "industry": {"sw_level1": "有色金属"},
        "event_impact": ["2026-04-28：发布一季报"],
        "macro_exposure": {"gold_price_beta": 0.85},
        "evidence_refs": ["doc_001"],
    }
