"""Test configuration and fixtures."""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# pytest loads this module before importing test modules.  Set the runtime
# database before importing repository globals, otherwise their engine is
# permanently bound to the development PostgreSQL URL for the entire test run.
if os.getenv("ALPHAFOUNDRY_RUN_POSTGRES_TESTS") != "1":
    _TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"alphafoundry-pytest-{os.getpid()}.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE_PATH}"

from data_layer.repositories import base
from data_layer.repositories.base import Base, ensure_schema


def pytest_configure(config):
    """Keep default test runs deterministic and offline."""
    os.environ.setdefault("ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS", "1")


@pytest.fixture
def runtime_database():
    """Provide a clean SQLite runtime schema for tests using repository globals."""
    ensure_schema()
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=base.engine)


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
