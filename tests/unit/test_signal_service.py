"""Unit tests for signal_service."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from core.contracts import AlphaSignal, EventAlphaSignal
from core.services.signal_service import SignalService


def test_create_signal_basic():
    """Test creating a basic signal."""
    service = SignalService()

    signal = service.create_signal(
        subject_id="600519.SH",
        thesis="Company earnings expected to grow",
        horizon="20d",
        score=0.7,
        confidence=0.6,
    )

    assert signal is not None
    assert signal.signal_id is not None
    assert signal.subject_id == "600519.SH"
    assert signal.thesis == "Company earnings expected to grow"
    assert signal.horizon == "20d"
    assert signal.score == 0.7
    assert signal.confidence == 0.6
    assert signal.status == "research_only"


def test_create_signal_with_refs():
    """Test creating a signal with scenario and evidence refs."""
    service = SignalService()

    scenario_refs = [str(uuid.uuid4()), str(uuid.uuid4())]
    evidence_refs = [str(uuid.uuid4())]

    signal = service.create_signal(
        subject_id="AAPL.NASDAQ",
        thesis="Tech stock expected to outperform",
        scenario_refs=scenario_refs,
        evidence_refs=evidence_refs,
        status="candidate",
    )

    assert signal is not None
    assert signal.scenario_refs == scenario_refs
    assert signal.evidence_refs == evidence_refs
    assert signal.status == "candidate"


def test_create_event_signal():
    """Test creating an event-based signal."""
    service = SignalService()
    event_time = datetime(2024, 5, 10, tzinfo=timezone.utc)

    signal = service.create_event_signal(
        event_id="evt_123",
        event_type="earnings",
        subject_id="600036.SH",
        thesis="Earnings beat will drive price appreciation",
        event_time=event_time,
        impact_path=["financial sector", "consumer finance"],
        bullish_companies=["600036.SH"],
        bearish_companies=["600000.SH"],
    )

    assert isinstance(signal, EventAlphaSignal)
    assert signal.event_id == "evt_123"
    assert signal.event_type == "earnings"
    assert signal.event_time == event_time
    assert len(signal.impact_path) == 2
    assert len(signal.bullish_companies) == 1
    assert len(signal.bearish_companies) == 1


def test_get_signal():
    """Test retrieving a signal by ID."""
    service = SignalService()

    created = service.create_signal(subject_id="TSLA.NASDAQ", thesis="EV growth thesis")
    retrieved = service.get_signal(created.signal_id)

    assert retrieved is not None
    assert retrieved.signal_id == created.signal_id
    assert retrieved.subject_id == "TSLA.NASDAQ"
    assert retrieved.thesis == "EV growth thesis"


def test_get_signal_not_found():
    """Test retrieving a non-existent signal returns None."""
    service = SignalService()
    assert service.get_signal("non_existent_id") is None


def test_list_signals():
    """Test listing signals."""
    service = SignalService()

    service.create_signal(subject_id="600519.SH", thesis="Thesis 1", status="research_only")
    service.create_signal(subject_id="600036.SH", thesis="Thesis 2", status="candidate")
    service.create_signal(subject_id="600519.SH", thesis="Thesis 3", status="research_only")

    all_signals = service.list_signals()
    assert len(all_signals) == 3

    filtered_by_status = service.list_signals(status="research_only")
    assert len(filtered_by_status) == 2

    filtered_by_subject = service.list_signals(subject_id="600519.SH")
    assert len(filtered_by_subject) == 2

    limited = service.list_signals(limit=1)
    assert len(limited) == 1


def test_promote_signal():
    """Test promoting a signal through statuses."""
    service = SignalService()
    signal = service.create_signal(subject_id="600519.SH", thesis="Thesis")

    promoted1 = service.promote_signal(signal.signal_id, "candidate")
    assert promoted1 is not None
    assert promoted1.status == "candidate"

    promoted2 = service.promote_signal(signal.signal_id, "paper_trade")
    assert promoted2 is not None
    assert promoted2.status == "paper_trade"


def test_promote_signal_invalid_status():
    """Test promoting to invalid status fails."""
    service = SignalService()
    signal = service.create_signal(subject_id="600519.SH", thesis="Thesis")

    result = service.promote_signal(signal.signal_id, "invalid_status")
    assert result is None


def test_promote_signal_cannot_demote():
    """Test cannot demote a signal."""
    service = SignalService()
    signal = service.create_signal(subject_id="600519.SH", thesis="Thesis", status="candidate")

    result = service.promote_signal(signal.signal_id, "research_only")
    assert result is None


def test_promote_signal_not_found():
    """Test promoting non-existent signal returns None."""
    service = SignalService()
    assert service.promote_signal("non_existent", "candidate") is None


def test_validate_signal():
    """Test signal validation."""
    service = SignalService()
    signal = service.create_signal(subject_id="600519.SH", thesis="Test thesis")

    result = service.validate_signal(signal)

    assert result["signal_id"] == signal.signal_id
    assert "composite_score" in result
    assert "features" in result
    assert "backtest" in result
    assert "validated_at" in result


def test_generate_trade_candidate():
    """Test generating a trade candidate from signal."""
    service = SignalService()
    signal = service.create_signal(subject_id="600519.SH", thesis="Test thesis")

    candidate = service.generate_trade_candidate(signal)

    assert candidate is not None
    assert candidate.candidate_id is not None
    assert candidate.signal_id == signal.signal_id


def test_signal_service_with_mock_repository():
    """Test signal service with mock repository."""
    mock_repo = MagicMock()
    mock_signal = AlphaSignal(
        signal_id="test_id",
        subject_id="600519.SH",
        thesis="Test",
        horizon="20d",
        score=0.5,
        confidence=0.5,
    )
    mock_repo.save.return_value = mock_signal

    service = SignalService(repository=mock_repo)
    signal = service.create_signal(subject_id="600519.SH", thesis="Test")

    mock_repo.save.assert_called_once()
    assert signal.signal_id == "test_id"
