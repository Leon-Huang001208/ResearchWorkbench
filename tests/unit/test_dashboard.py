"""Unit tests for Dashboard Service"""
import asyncio
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


@patch("services.dashboard_service.DashboardDataRepository")
def test_crawl_feed_supports_cninfo_source_filter(mock_repo_cls):
    """Dashboard crawl feed should expose cninfo for implementation monitoring."""
    mock_repo = Mock()
    mock_repo.get_recent_crawled_documents.return_value = {
        "items": [
            {
                "doc_id": "doc_cninfo_001",
                "title": "贵州茅台2025年年度报告",
                "source_type": "cninfo",
            }
        ],
        "total_today": 1,
        "last_crawled_at": "2026-06-05T09:00:00",
    }
    mock_repo_cls.return_value = mock_repo

    service = DashboardService(Mock())
    result = service.get_crawl_feed(limit=20, source_type="cninfo")

    mock_repo.get_recent_crawled_documents.assert_called_once_with(
        limit=20, since=None, source_type="cninfo"
    )
    assert result["items"][0]["source_type"] == "cninfo"


@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_sector_view_prefers_workbook_real_data(mock_repo_cls, mock_reader_cls):
    """Wind sector views should return workbook data without repo fallback when real."""
    mock_repo = Mock()
    mock_repo_cls.return_value = mock_repo
    mock_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [{"name": "GPU指数", "change_pct": 8.8}],
        "down": [],
        "has_real_data": True,
        "fetched_at": "2026-06-22T08:30:00+00:00",
        "cache_hit": True,
        "cache_ttl_seconds": 60,
        "status": "ok",
        "message": "",
        "source": "wind_realtime_workbook",
        "updated_at": "2026-06-22T08:29:59+00:00",
        "error_count": 0,
    }

    result = DashboardService(Mock()).get_market_sector_view("wind_hot_concept", limit=5)

    mock_reader_cls.return_value.get_view.assert_called_once_with(
        "wind_hot_concept", limit=5
    )
    mock_repo.get_sector_changes_from_signals.assert_not_called()
    assert result["source"] == "wind_realtime_workbook"
    assert result["has_real_data"] is True
    assert result["up"][0]["name"] == "GPU指数"


@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_sector_view_falls_back_to_repo_when_workbook_has_no_real_data(
    mock_repo_cls, mock_reader_cls
):
    """Missing workbook data should use real repo sector movers when available."""
    mock_repo = Mock()
    mock_repo.get_sector_changes_from_signals.return_value = (
        [{"sector_id": "sector-ai", "name": "AI", "change_pct": 3.2}],
        [{"sector_id": "sector-coal", "name": "煤炭", "change_pct": -1.4}],
        True,
        1782090000.0,
    )
    mock_repo_cls.return_value = mock_repo
    mock_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_l1",
        "view_label": "Wind一级",
        "up": [],
        "down": [],
        "has_real_data": False,
        "fetched_at": "2026-06-22T08:30:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60,
        "status": "workbook_missing",
        "message": "missing",
        "source": "wind_realtime_workbook",
        "updated_at": None,
        "error_count": 0,
    }

    result = DashboardService(Mock()).get_market_sector_view("wind_l1", limit=7)

    mock_repo.get_sector_changes_from_signals.assert_called_once_with(
        days=7, limit_per_direction=7
    )
    assert result["source"] == "repo_sector_fallback"
    assert result["status"] == "ok"
    assert result["message"] == ""
    assert result["has_real_data"] is True
    assert result["up"][0]["name"] == "AI"
    assert result["down"][0]["name"] == "煤炭"


@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_sector_view_returns_workbook_status_when_no_real_data_anywhere(
    mock_repo_cls, mock_reader_cls
):
    """No workbook data and no repo data should preserve workbook status/message."""
    mock_repo = Mock()
    mock_repo.get_sector_changes_from_signals.return_value = ([], [], False, 0.0)
    mock_repo_cls.return_value = mock_repo
    mock_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_l4",
        "view_label": "Wind四级",
        "up": [],
        "down": [],
        "has_real_data": False,
        "fetched_at": "2026-06-22T08:30:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60,
        "status": "snapshot_empty",
        "message": "Wind快照暂无可用数据",
        "source": "wind_realtime_workbook",
        "updated_at": None,
        "error_count": 2,
    }

    result = DashboardService(Mock()).get_market_sector_view("wind_l4", limit=3)

    assert result["source"] == "wind_realtime_workbook"
    assert result["status"] == "snapshot_empty"
    assert result["message"] == "Wind快照暂无可用数据"
    assert result["has_real_data"] is False
    assert result["up"] == []
    assert result["down"] == []
    assert result["error_count"] == 2


@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_sector_view_rejects_unsupported_view_without_fallback(
    mock_repo_cls, mock_reader_cls
):
    """Unsupported views should not be disguised as repo sector data."""
    mock_repo = Mock()
    mock_repo.get_sector_changes_from_signals.return_value = (
        [{"sector_id": "sector-ai", "name": "AI", "change_pct": 3.2}],
        [],
        True,
        1782090000.0,
    )
    mock_repo_cls.return_value = mock_repo

    result = DashboardService(Mock()).get_market_sector_view("ths_industry", limit=10)

    mock_reader_cls.assert_not_called()
    mock_repo_cls.assert_not_called()
    mock_repo.get_sector_changes_from_signals.assert_not_called()
    assert result["view_key"] == "ths_industry"
    assert result["status"] == "unsupported_view"
    assert result["source"] == "dashboard_service"
    assert result["has_real_data"] is False
    assert result["up"] == []
    assert result["down"] == []


def test_sector_movers_route_is_callable():
    """Route function should delegate query args to DashboardService."""
    from app.api.routes import dashboard as dashboard_route

    mock_db = Mock()
    mock_service = Mock()
    mock_service.get_market_sector_view.return_value = {
        "view_key": "wind_l2",
        "view_label": "Wind二级",
        "up": [],
        "down": [],
        "has_real_data": False,
        "fetched_at": "2026-06-22T08:30:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60,
        "status": "snapshot_empty",
        "message": "",
        "source": "wind_realtime_workbook",
        "updated_at": None,
        "error_count": 0,
    }

    with patch.object(dashboard_route, "SessionLocal", return_value=mock_db), patch.object(
        dashboard_route, "DashboardService", return_value=mock_service
    ):
        result = asyncio.run(
            dashboard_route.get_sector_movers(view_key="wind_l2", limit=12)
        )

    mock_service.get_market_sector_view.assert_called_once_with(
        view_key="wind_l2", limit=12
    )
    mock_db.close.assert_called_once()
    assert result["view_key"] == "wind_l2"
