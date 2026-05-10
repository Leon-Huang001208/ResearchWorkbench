"""Tests for Timing repository"""
import pytest
from sqlalchemy import text
from timing_engine.contracts import TimingDecision, TimingModelScore
from data_layer.repositories.timing_repository import TimingRepositoryImpl
from core.observability import get_logger

logger = get_logger(__name__)


class TestTimingRepositorySQLite:
    """Test the repository with in-memory SQLite"""

    @pytest.fixture
    def repo(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        # Create tables manually for SQLite test
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE timing_decision (
                    decision_id TEXT PRIMARY KEY,
                    signal_id TEXT,
                    action TEXT NOT NULL,
                    readiness_score NUMERIC NOT NULL,
                    market_regime TEXT NOT NULL DEFAULT 'unknown',
                    model_scores JSON NOT NULL DEFAULT ('[]'),
                    active_weights JSON NOT NULL DEFAULT ('{}'),
                    blockers JSON NOT NULL DEFAULT ('[]'),
                    rationale JSON NOT NULL DEFAULT ('[]'),
                    created_at TIMESTAMP
                )
            """))
            conn.commit()

        Session = sessionmaker(bind=engine)
        session = Session()
        repository = TimingRepositoryImpl(db=session)
        return repository

    def test_save_and_get_timing_decision(self, repo):
        """Test saving and retrieving a timing decision"""
        decision = TimingDecision(
            action="enter",
            readiness_score=0.85,
            signal_id="test-signal-123",
            market_regime="liquidity_bull",
            model_scores=[
                TimingModelScore(
                    model_name="regime",
                    score=0.9,
                    confidence=0.8,
                    rationale="Current market is in bullish liquidity regime",
                )
            ],
            active_weights={"regime": 0.6, "sentiment": 0.4},
            blockers=[],
            rationale=["Multiple models support entering position"],
        )

        saved = repo.save(decision)

        assert saved.decision_id is not None
        assert saved.action == "enter"
        assert saved.readiness_score == 0.85
        assert saved.signal_id == "test-signal-123"

        retrieved = repo.get(saved.decision_id)
        assert retrieved is not None
        assert retrieved.action == saved.action
        assert retrieved.readiness_score == saved.readiness_score
        assert len(retrieved.model_scores) == 1
        assert retrieved.model_scores[0].model_name == "regime"

    def test_list_and_filter(self, repo):
        """Test listing and filtering decisions"""
        decision1 = TimingDecision(
            action="enter",
            readiness_score=0.75,
            signal_id="signal-abc",
        )
        decision2 = TimingDecision(
            action="wait",
            readiness_score=0.3,
            signal_id="signal-abc",
        )

        repo.save(decision1)
        repo.save(decision2)

        # Filter by signal_id
        decisions = repo.list(signal_id="signal-abc")
        assert len(decisions) >= 2

        # Filter by action
        enter_decisions = repo.list(action="enter")
        assert any(d.action == "enter" for d in enter_decisions)

    def test_get_latest_for_signal(self, repo):
        """Test getting latest decision for signal"""
        decision1 = TimingDecision(
            action="wait",
            readiness_score=0.4,
            signal_id="latest-test-signal",
        )
        decision2 = TimingDecision(
            action="enter",
            readiness_score=0.8,
            signal_id="latest-test-signal",
        )

        repo.save(decision1)
        repo.save(decision2)

        latest = repo.get_latest_for_signal("latest-test-signal")
        assert latest is not None
        assert latest.action == "enter"
