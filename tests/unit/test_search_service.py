"""Unit tests for search_service."""

from unittest.mock import MagicMock

from services.search_service import GlobalSearchService


def test_search_basic():
    """Test basic search functionality."""
    mock_repo = MagicMock()
    mock_repo.search_symbols.return_value = [{"symbol": "600519.SH", "name": "贵州茅台"}]
    mock_repo.search_theses.return_value = [{"thesis_id": "1", "text": "Earnings growth"}]

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("茅台", limit=10)

    assert "symbols" in results
    assert "theses" in results
    assert len(results["symbols"]) == 1
    assert len(results["theses"]) == 1


def test_search_with_type_filter():
    """Test search with type filters."""
    mock_repo = MagicMock()
    mock_repo.search_symbols.return_value = [{"symbol": "600519.SH"}]

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("test", type_filter=["symbol"], limit=10)

    assert "symbols" in results
    assert len(results["symbols"]) == 1
    # Other types should be empty lists
    assert len(results["theses"]) == 0
    assert len(results["signals"]) == 0


def test_search_handles_exceptions():
    """Test search handles exceptions gracefully."""
    mock_repo = MagicMock()
    mock_repo.search_symbols.side_effect = Exception("DB error")
    mock_repo.search_theses.return_value = []

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("test")

    # Should still return results dict even with errors
    assert "symbols" in results
    assert "theses" in results


def test_search_all_types():
    """Test searching all types."""
    mock_repo = MagicMock()
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

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("test")

    # All result categories should be present
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


def test_search_signals_and_theses():
    """Test signal and thesis search."""
    mock_repo = MagicMock()
    mock_repo.search_signals.return_value = [{"signal_id": "1", "thesis": "Test thesis"}]

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("thesis", type_filter=["signal"])

    mock_repo.search_signals.assert_called_once()
    assert len(results["signals"]) == 1


def test_search_events_and_event_types():
    """Test event and event type search."""
    mock_repo = MagicMock()
    mock_repo.search_events.return_value = [{"event_id": "1", "title": "Test event"}]
    mock_repo.search_event_types.return_value = ["earnings", "news"]

    service = GlobalSearchService(search_repo=mock_repo)
    results = service.search("event", type_filter=["event", "event_type"])

    mock_repo.search_events.assert_called_once()
    mock_repo.search_event_types.assert_called_once()
    assert len(results["events"]) == 1
    assert len(results["event_types"]) == 2
