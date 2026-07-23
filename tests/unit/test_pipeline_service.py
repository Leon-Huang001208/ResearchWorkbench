"""
Unit tests for core.services.pipeline_service
"""

from unittest.mock import Mock

import pytest

from core.contracts import CanonicalEvent
from memory_learning.journal import LearningJournal
from services.pipeline_service import ResearchPipeline


def test_research_pipeline_initialization():
    """Test ResearchPipeline initialization with dependencies."""
    mock_blackboard = Mock()
    mock_signal_service = Mock()

    pipeline = ResearchPipeline(
        blackboard=mock_blackboard,
        signal_service=mock_signal_service,
    )

    assert pipeline.blackboard == mock_blackboard
    assert pipeline.signal_service == mock_signal_service


@pytest.mark.asyncio
async def test_run_asset_analysis_returns_snapshot():
    """Test run_asset_analysis returns valid AssetAnalysisSnapshot."""
    pipeline = ResearchPipeline()
    result = await pipeline.run_asset_analysis("test-asset-123")

    assert result is not None
    assert result.canonical_id == "test-asset-123"
    assert result.as_of is not None


@pytest.mark.asyncio
async def test_run_event_signal_runs_without_exception():
    """Test run_event_signal executes without exception."""
    pipeline = ResearchPipeline()
    event = CanonicalEvent(
        event_id="test-evt-123",
        event_type="test",
        source_type="test",
        source_name="TestSource",
        title="test event",
        summary="test event",
        impact_direction="positive",
        confidence=0.8,
        needs_review=False,
        entities=[],
        evidence_spans=[],
        source_doc_id="doc-test-123",
    )

    # Should not raise any exceptions
    await pipeline.run_event_signal(event)


@pytest.mark.asyncio
async def test_run_scenario_analysis_returns_scenario_set():
    """Test run_scenario_analysis returns valid ScenarioSet."""
    pipeline = ResearchPipeline()
    result = await pipeline.run_scenario_analysis(
        "test question",
        ["subject-1", "subject-2"],
    )

    assert result is not None
    assert hasattr(result, "hypotheses")


@pytest.mark.asyncio
async def test_run_event_signal_records_to_journal():
    """Test run_event_signal records to LearningJournal when provided."""
    journal = LearningJournal()
    pipeline = ResearchPipeline(learning_journal=journal)
    event = CanonicalEvent(
        event_id="test-evt-456",
        event_type="earnings",
        source_type="report",
        source_name="TestSource",
        title="test event",
        summary="test event",
        impact_direction="positive",
        confidence=0.8,
        needs_review=False,
        entities=[],
        evidence_spans=[],
        source_doc_id="doc-test-456",
    )

    await pipeline.run_event_signal(event)

    # Check that an episode was recorded
    episodes = journal.list_episodes(event_type="earnings")
    assert len(episodes) == 1


@pytest.mark.asyncio
async def test_record_outcome_updates_episode():
    """Test record_outcome updates an existing episode."""
    journal = LearningJournal()
    pipeline = ResearchPipeline(learning_journal=journal)
    # First record an episode
    from memory_learning.contracts import MarketEpisode

    episode = MarketEpisode(
        episode_id="test-episode-outcome",
        event_id="test-event-outcome",
        event_type="earnings",
        market_regime="bullish",
        initial_reaction="up",
        outcome_horizon="20d",
        outcome_return=0.0,
        outcome_excess_return=0.0,
    )
    journal.record_episode(episode)

    # Now record the outcome
    updated_episode = await pipeline.record_outcome(
        episode_id="test-episode-outcome",
        outcome_return=0.05,
        outcome_excess_return=0.03,
        lesson="Great call",
    )

    assert updated_episode is not None
    assert updated_episode.outcome_return == 0.05
    assert updated_episode.outcome_excess_return == 0.03
    assert updated_episode.lesson == "Great call"
