"""Unit tests for closed_loop_service."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.base import Base
from data_layer.repositories.models import CanonicalEvent
from services.closed_loop_service import ClosedLoopService


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite DB."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture
def sample_event():
    """Create sample CanonicalEvent."""
    return CanonicalEvent(
        event_id=str(uuid.uuid4()),
        event_type="earnings",
        summary="贵州茅台2024年Q1财报超市场预期，营收增长20%",
        impact_direction="positive",
        confidence=0.9,
        event_time=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )


def test_closed_loop_service_init():
    """Test initializing ClosedLoopService."""
    service = ClosedLoopService()
    assert service is not None
    assert service.benchmark_code == "000300.SH"
    assert service.learning_journal is not None
    assert service.pattern_learner is not None


def test_generate_thesis_from_event(sample_event):
    """Test generating thesis from event."""
    service = ClosedLoopService()
    thesis = service._generate_thesis_from_event(sample_event)
    assert thesis is not None
    assert "贵州茅台" in thesis
    assert "利好" in thesis


def test_generate_thesis_from_event_policy(sample_event):
    """Test generating thesis from policy event."""
    sample_event.event_type = "policy"
    sample_event.summary = "央行降准政策发布"
    service = ClosedLoopService()
    thesis = service._generate_thesis_from_event(sample_event)
    assert thesis is not None
    assert "政策" in thesis


def test_calculate_returns():
    """Test calculating returns from price data."""
    service = ClosedLoopService()
    quotes = [
        {"date": "2024-05-01", "close": 100.0},
        {"date": "2024-05-02", "close": 102.0},
        {"date": "2024-05-21", "close": 110.0},
    ]
    event_time = datetime(2024, 5, 1, tzinfo=timezone.utc)
    entry_price, exit_price, outcome_return, max_drawdown = service._calculate_returns(
        quotes, event_time, 20
    )
    assert entry_price == 100.0
    assert exit_price == 110.0
    assert outcome_return == pytest.approx(0.1, rel=1e-2)


def test_calculate_returns_empty_quotes():
    """Test calculating returns with empty quotes."""
    service = ClosedLoopService()
    event_time = datetime(2024, 5, 1, tzinfo=timezone.utc)
    entry_price, exit_price, outcome_return, max_drawdown = service._calculate_returns(
        [], event_time, 20
    )
    assert entry_price == 0.0
    assert exit_price == 0.0
    assert outcome_return == 0.0
    assert max_drawdown == 0.0


def test_generate_lesson_correct_direction_positive_return():
    """Test generating lesson when direction is correct and positive return."""
    service = ClosedLoopService()
    mock_signal = MagicMock()
    mock_signal.event_type = "earnings"
    lesson = service._generate_lesson(mock_signal, 0.1, 0.06, True)
    assert "优秀" in lesson
    assert "超额收益" in lesson


def test_generate_lesson_incorrect_direction():
    """Test generating lesson when direction is incorrect."""
    service = ClosedLoopService()
    mock_signal = MagicMock()
    mock_signal.event_type = "earnings"
    lesson = service._generate_lesson(mock_signal, -0.05, -0.03, False)
    assert "错误" in lesson


def test_closed_loop_service_with_db(in_memory_db, sample_event):
    """Test ClosedLoopService with database."""
    in_memory_db.add(sample_event)
    in_memory_db.commit()

    with patch("services.closed_loop_service.SessionLocal", return_value=in_memory_db):
        service = ClosedLoopService()
        with patch.object(service, "_get_price_data") as mock_get_price:
            mock_get_price.return_value = [
                {"date": "2024-05-01", "close": 100.0},
                {"date": "2024-05-21", "close": 110.0},
            ]
            signals = service.generate_signals_from_events()
            assert len(signals) >= 0


def test_run_full_loop():
    """Test running full loop (with mocks)."""
    service = ClosedLoopService()

    with patch.object(service, "generate_signals_from_events") as mock_generate:
        with patch.object(service, "backtest_signals") as mock_backtest:
            with patch.object(service, "_record_market_episodes") as mock_record:
                mock_generate.return_value = []
                mock_backtest.return_value = []
                mock_record.return_value = 0

                summary = service.run_full_loop()

                assert summary is not None
                assert summary["signals_generated"] == 0
                assert summary["signals_backtested"] == 0
                assert summary["episodes_recorded"] == 0
