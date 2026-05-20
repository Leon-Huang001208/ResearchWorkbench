"""Unit tests for Global Search Service"""
from unittest.mock import Mock

from core.services.search_service import GlobalSearchService


def test_search_service_initialization():
    """Test that search service initializes correctly"""
    mock_repo = Mock()
    service = GlobalSearchService(mock_repo)
    assert service.search_repo == mock_repo


def test_search_empty_query():
    """Test search with no filters returns all groups"""
    mock_repo = Mock()
    mock_repo.search_symbols.return_value = []
    mock_repo.search_theses.return_value = []
    mock_repo.search_source_docs.return_value = []
    mock_repo.search_failure_memory.return_value = []
    mock_repo.search_market_episodes.return_value = []
    mock_repo.search_signals.return_value = []
    mock_repo.search_events.return_value = []
    mock_repo.search_event_types.return_value = []
    mock_repo.search_outcomes.return_value = []
    mock_repo.search_reviews.return_value = []

    service = GlobalSearchService(mock_repo)
    results = service.search("test")

    assert "symbols" in results
    assert "event_types" in results
    assert "theses" in results
    assert "source_docs" in results
    assert "failure_memories" in results
    assert "market_episodes" in results
    assert "signals" in results
    assert "events" in results
    assert "outcomes" in results
    assert "reviews" in results


def test_search_with_type_filter():
    """Test search with specific type filter only returns that type"""
    mock_repo = Mock()
    mock_repo.search_signals.return_value = [{"signal_id": "s1", "thesis": "test"}]
    mock_repo.search_events.return_value = []
    mock_repo.search_symbols.return_value = []
    mock_repo.search_theses.return_value = []
    mock_repo.search_source_docs.return_value = []
    mock_repo.search_failure_memory.return_value = []
    mock_repo.search_market_episodes.return_value = []
    mock_repo.search_event_types.return_value = []
    mock_repo.search_outcomes.return_value = []
    mock_repo.search_reviews.return_value = []

    service = GlobalSearchService(mock_repo)
    results = service.search("test", type_filter=["signal", "event"])

    assert len(results["signals"]) == 1
    # Other groups should still be present but empty
    assert results["outcomes"] == []
    assert results["reviews"] == []
    assert all(
        k in results
        for k in [
            "symbols",
            "event_types",
            "theses",
            "source_docs",
            "failure_memories",
            "market_episodes",
            "signals",
            "events",
            "outcomes",
            "reviews",
        ]
    )


def test_search_handles_missing_tables_gracefully():
    """Test that search doesn't crash when optional tables are missing"""
    mock_repo = Mock()
    mock_repo.search_symbols.return_value = []
    mock_repo.search_theses.return_value = []
    mock_repo.search_source_docs.side_effect = Exception("Table not found")
    mock_repo.search_failure_memory.return_value = []
    mock_repo.search_market_episodes.return_value = []
    mock_repo.search_signals.return_value = []
    mock_repo.search_events.return_value = []
    mock_repo.search_event_types.return_value = []
    mock_repo.search_outcomes.return_value = []
    mock_repo.search_reviews.return_value = []

    service = GlobalSearchService(mock_repo)
    results = service.search("test", type_filter=["source_docs"])
    assert results["source_docs"] == []
