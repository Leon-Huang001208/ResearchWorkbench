"""Unit tests for Global Search Service"""
import pytest
from unittest.mock import Mock, patch

from core.services.search_service import GlobalSearchService


def test_search_service_initialization():
    """Test that search service initializes correctly"""
    mock_session = Mock()
    service = GlobalSearchService(mock_session)
    assert service.session == mock_session


def test_search_empty_query():
    """Test search with no filters returns all groups"""
    mock_session = Mock()
    
    # Mock queries
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_session.query.return_value = mock_query
    
    service = GlobalSearchService(mock_session)
    results = service.search("test")
    
    # All result groups should be present
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
    mock_session = Mock()
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_session.query.return_value = mock_query
    
    service = GlobalSearchService(mock_session)
    results = service.search("test", type_filter=["symbols", "events"])
    
    # Only requested types should be populated (others are empty)
    assert len(results["symbols"]) == 0  # still empty but exists
    assert len(results["events"]) == 0
    assert len(results["signals"]) == 0  # not requested should be empty but exists
    assert all(k in results for k in [
        "symbols", "event_types", "theses", "source_docs", 
        "failure_memories", "market_episodes", "signals", 
        "events", "outcomes", "reviews"
    ])


def test_search_handles_missing_tables_gracefully():
    """Test that search doesn't crash when optional tables are missing"""
    mock_session = Mock()
    
    # For source_docs, simulate that the table doesn't exist
    def mock_query_raising(*args, **kwargs):
        raise NameError("name 'SourceDocDB' is not defined")
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    
    mock_session.query = mock_query_raising
    
    service = GlobalSearchService(mock_session)
    # Should not crash, just return empty source_docs
    results = service.search("test", type_filter=["source_docs"])
    assert results["source_docs"] == []
