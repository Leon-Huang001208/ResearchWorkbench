"""Unit tests for MemoryRepository."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.observability import get_logger
from data_layer.repositories.base import Base
from data_layer.repositories.memory_repository import MemoryRepositoryImpl
from memory_learning.contracts import AgentMemory, FailureMemory, MarketEpisode, StrategyMemory

logger = get_logger(__name__)

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # Create the memory tables manually since they use raw SQL not ORM models
    with engine.connect() as conn:
        # Create market_episode
        conn.execute(text("""
            CREATE TABLE market_episode (
                episode_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                market_regime TEXT NOT NULL,
                initial_reaction TEXT NOT NULL,
                outcome_horizon TEXT NOT NULL,
                outcome_return NUMERIC NOT NULL,
                outcome_excess_return NUMERIC NOT NULL,
                timing_action TEXT,
                signal_id TEXT,
                timing_decision_id TEXT,
                failed_reason TEXT,
                lesson TEXT,
                evidence_refs JSON NOT NULL DEFAULT '[]',
                metadata JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create strategy_memory
        conn.execute(text("""
            CREATE TABLE strategy_memory (
                strategy_id TEXT PRIMARY KEY,
                signal_family TEXT NOT NULL,
                market_regime TEXT NOT NULL,
                sample_size INTEGER NOT NULL DEFAULT 0,
                win_rate NUMERIC NOT NULL,
                average_excess_return NUMERIC NOT NULL,
                sharpe_ratio NUMERIC NOT NULL,
                notes JSON NOT NULL DEFAULT '[]',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create agent_memory
        conn.execute(text("""
            CREATE TABLE agent_memory (
                memory_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                belief TEXT NOT NULL,
                confidence NUMERIC NOT NULL,
                support_count INTEGER NOT NULL DEFAULT 0,
                contradiction_count INTEGER NOT NULL DEFAULT 0,
                last_updated_reason TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create failure_memory
        conn.execute(text("""
            CREATE TABLE failure_memory (
                failure_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                failure_type TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                corrective_action TEXT NOT NULL,
                evidence_refs JSON NOT NULL DEFAULT '[]',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_session_factory(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session(test_session_factory):
    session = test_session_factory()
    yield session
    session.rollback()
    session.close()


def test_save_and_get_episode(db_session):
    """Test saving and retrieving a market episode."""
    repo = MemoryRepositoryImpl(db_session)

    episode = MarketEpisode(
        episode_id="test-episode-001",
        event_id="event-001",
        event_type="earnings",
        market_regime="bull",
        initial_reaction="positive",
        outcome_horizon="5d",
        outcome_return=2.5,
        outcome_excess_return=1.8,
        timing_action="enter",
        lesson="Earnings beats tend to have positive follow-through in bull markets",
        evidence_refs=["doc-123", "doc-456"],
        metadata={"source": "test"},
    )

    saved = repo.save_episode(episode)
    assert saved.episode_id == episode.episode_id

    retrieved = repo.get_episode(episode.episode_id)
    assert retrieved is not None
    assert retrieved.episode_id == episode.episode_id
    assert retrieved.event_type == episode.event_type
    assert retrieved.market_regime == episode.market_regime
    assert retrieved.outcome_return == pytest.approx(episode.outcome_return)
    assert retrieved.lesson == episode.lesson
    assert len(retrieved.evidence_refs) == 2
    assert retrieved.metadata == {"source": "test"}


def test_list_episodes_with_filter(db_session):
    """Test listing episodes with filtering."""
    repo = MemoryRepositoryImpl(db_session)

    # Add two episodes of different types
    episode1 = MarketEpisode(
        episode_id="test-episode-002",
        event_id="event-002",
        event_type="policy",
        market_regime="volatile",
        initial_reaction="negative",
        outcome_horizon="20d",
        outcome_return=-3.2,
        outcome_excess_return=-2.1,
        evidence_refs=[],
        metadata={},
    )
    episode2 = MarketEpisode(
        episode_id="test-episode-003",
        event_id="event-003",
        event_type="earnings",
        market_regime="bull",
        initial_reaction="positive",
        outcome_horizon="1d",
        outcome_return=1.2,
        outcome_excess_return=0.8,
        evidence_refs=[],
        metadata={},
    )

    repo.save_episode(episode1)
    repo.save_episode(episode2)

    all_episodes = repo.list_episodes(limit=10)
    assert len(all_episodes) == 2

    filtered = repo.list_episodes(event_type="earnings")
    assert len(filtered) == 1
    assert filtered[0].episode_id == "test-episode-003"

    filtered_regime = repo.list_episodes(market_regime="bull")
    assert len(filtered_regime) == 1
    assert filtered_regime[0].event_type == "earnings"


def test_save_and_list_strategies(db_session):
    """Test saving and listing strategy memory."""
    repo = MemoryRepositoryImpl(db_session)

    strategy = StrategyMemory(
        strategy_id="strat-001",
        signal_family="earnings_beats",
        market_regime="bull",
        sample_size=50,
        win_rate=0.68,
        average_excess_return=1.2,
        sharpe_ratio=1.8,
        notes=["Works well low position sizing", "Avoid when volatility is high"],
    )

    saved = repo.save_strategy(strategy)
    assert saved.strategy_id == strategy.strategy_id

    strategies = repo.list_strategies(signal_family="earnings_beats")
    assert len(strategies) == 1
    assert strategies[0].win_rate == pytest.approx(0.68)
    assert strategies[0].sharpe_ratio == pytest.approx(1.8)
    assert len(strategies[0].notes) == 2


def test_save_and_list_agent_memory(db_session):
    """Test saving and listing agent memory."""
    repo = MemoryRepositoryImpl(db_session)

    memory = AgentMemory(
        memory_id="am-001",
        agent_name="MacroAgent",
        agent_role="macro_analyst",
        belief="High inflation leads to tighter monetary policy which is bad for growth stocks",
        confidence=0.85,
        support_count=28,
        contradiction_count=3,
        last_updated_reason="Updated with 2024 data",
    )

    saved = repo.save_agent_memory(memory)
    assert saved.memory_id == memory.memory_id

    memories = repo.list_agent_memories(agent_role="macro_analyst")
    assert len(memories) == 1
    assert memories[0].confidence == pytest.approx(0.85)
    assert memories[0].support_count == 28


def test_save_and_list_failures(db_session):
    """Test saving and listing failure memory."""
    repo = MemoryRepositoryImpl(db_session)

    failure = FailureMemory(
        failure_id="fail-001",
        source_id="signal-123",
        failure_type="timing_error",
        root_cause="Entered too early before initial volatility settled",
        corrective_action="Wait 3-5 days after event before entering",
        evidence_refs=["episode-456"],
    )

    saved = repo.save_failure(failure)
    assert saved.failure_id == failure.failure_id

    failures = repo.list_failures(failure_type="timing_error")
    assert len(failures) == 1
    assert failures[0].failure_type == "timing_error"
    assert failures[0].root_cause == failure.root_cause
    assert len(failures[0].evidence_refs) == 1


def test_summarize_event_type(db_session):
    """Test event type summary statistics."""
    repo = MemoryRepositoryImpl(db_session)

    # Add multiple earnings episodes
    episodes = [
        MarketEpisode(
            episode_id=f"summary-test-{i}",
            event_id=f"event-{i}",
            event_type="earnings",
            market_regime="bull",
            initial_reaction="positive" if i % 2 == 0 else "negative",
            outcome_horizon="5d",
            outcome_return=2.0 + i * 0.5,
            outcome_excess_return=1.0 + i * 0.3,
            evidence_refs=[],
            metadata={},
        )
        for i in range(4)
    ]

    # Add a negative one
    episodes.append(
        MarketEpisode(
            episode_id="summary-test-4",
            event_id="event-4",
            event_type="earnings",
            market_regime="bull",
            initial_reaction="negative",
            outcome_horizon="5d",
            outcome_return=-3.0,
            outcome_excess_return=-2.5,
            evidence_refs=[],
            metadata={},
        )
    )

    for ep in episodes:
        repo.save_episode(ep)

    summary = repo.summarize_event_type("earnings")
    assert summary["total_episodes"] == 5
    assert summary["positive_rate"] == pytest.approx(4 / 5)
    # Average return should be (2 + 2.5 + 3 + 3.5 - 3)/5 = (8)/5 = 1.6
    assert summary["average_return"] == pytest.approx(1.6)
