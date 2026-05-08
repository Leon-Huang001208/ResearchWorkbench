"""Unit tests for Dashboard Service"""
import pytest
from unittest.mock import Mock, patch

from core.services.dashboard_service import DashboardService
from core.contracts.dashboard import DashboardResponse


def test_dashboard_service_initialization():
    """Test that dashboard service initializes correctly"""
    mock_session = Mock()
    service = DashboardService(mock_session)
    assert service.session == mock_session
    assert service.today_cutoff is not None


def test_get_full_dashboard():
    """Test full dashboard aggregation doesn't crash"""
    mock_session = Mock()
    
    # Mock the queries to return empty lists
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    
    mock_session.query.return_value = mock_query
    
    service = DashboardService(mock_session)
    
    # Should not crash even with no data
    dashboard = service.get_full_dashboard()
    
    assert isinstance(dashboard, DashboardResponse)
    assert len(dashboard.today.new_events) == 0
    assert len(dashboard.today.high_priority_theses) == 0
    assert len(dashboard.research_queue.pending_assertions) == 0
    assert len(dashboard.candidate_board.top_candidates) == 0
    assert len(dashboard.learning.recent_failures) == 0


def test_abnormal_flows_handled():
    """Test abnormal flows are handled gracefully even when missing"""
    mock_session = Mock()
    
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_session.query.return_value = mock_query
    
    service = DashboardService(mock_session)
    today = service.get_today_section()
    
    # Even if the repo is missing, it should return empty list
    assert isinstance(today.abnormal_flows, list)
    assert len(today.abnormal_flows) == 0
