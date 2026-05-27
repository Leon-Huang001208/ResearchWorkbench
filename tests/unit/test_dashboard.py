"""Unit tests for Dashboard Service"""
from unittest.mock import Mock, patch

from core.contracts.dashboard import DashboardResponse
from services.dashboard_service import DashboardService


def test_dashboard_service_initialization():
    """Test that dashboard service initializes correctly"""
    mock_session = Mock()
    service = DashboardService(mock_session)
    assert service.session == mock_session
    assert service.today_cutoff is not None


@patch("services.dashboard_service.DashboardDataRepository")
def test_get_full_dashboard(mock_repo_cls):
    """Test full dashboard aggregation doesn't crash"""
    mock_repo = Mock()
    mock_repo.get_global_news_from_events.return_value = []
    mock_repo.get_market_overview_section.return_value = None
    mock_repo.get_top_candidates.return_value = []
    mock_repo.get_pending_assertions.return_value = []
    mock_repo.get_mapping_review_items.return_value = []
    mock_repo.get_recent_failures.return_value = []
    mock_repo.get_weekly_lessons.return_value = []
    mock_repo.get_sector_changes.return_value = []
    mock_repo.get_best_performing_event_types.return_value = []
    mock_repo.get_missing_evidence.return_value = []
    mock_repo.get_abnormal_flows.return_value = []
    mock_repo_cls.return_value = mock_repo

    # Also need to mock self.session for get_today_section() which uses session directly
    mock_session = Mock()
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_session.query.return_value = mock_query

    service = DashboardService(mock_session)

    dashboard = service.get_full_dashboard()
    assert isinstance(dashboard, DashboardResponse)
    assert isinstance(dashboard.today.new_events, list)
    assert isinstance(dashboard.today.high_priority_theses, list)
    assert isinstance(dashboard.research_queue.pending_assertions, list)
    assert isinstance(dashboard.candidate_board.top_candidates, list)
    assert isinstance(dashboard.learning.recent_failures, list)


@patch("services.dashboard_service.DashboardDataRepository")
def test_abnormal_flows_handled(mock_repo_cls):
    """Test abnormal flows are handled gracefully even when missing"""
    mock_repo = Mock()
    mock_repo.get_global_news_from_events.return_value = []
    mock_repo.get_market_overview_section.return_value = None
    mock_repo.get_abnormal_flows.return_value = []
    mock_repo_cls.return_value = mock_repo

    mock_session = Mock()
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_session.query.return_value = mock_query

    service = DashboardService(mock_session)
    today = service.get_today_section()

    assert isinstance(today.abnormal_flows, list)
    # When import fails, falls back to mock data (2 entries)
