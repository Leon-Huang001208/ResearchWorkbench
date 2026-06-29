"""Unit tests for Dashboard Service"""
from unittest.mock import Mock, patch

import pytest

from core.contracts.dashboard import DashboardResponse, MarketBreadthSnapshot, MarketIndexItem
from data_layer.repositories.dashboard_data import _normalize_crawl_document_text
from services.dashboard_service import DashboardService, _market_sector_cache


@pytest.fixture(autouse=True)
def _mock_market_command_snapshot(monkeypatch):
    """Dashboard unit tests should not call live market quote providers."""
    monkeypatch.setattr(DashboardService, "_get_market_indices", lambda self: [])
    monkeypatch.setattr(DashboardService, "_get_market_breadth", lambda self: None)


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


def test_normalize_crawl_document_splits_bracketed_telegram_text():
    """Live monitor should show a clean headline and move telegram body into details."""
    doc = Mock()
    doc.title = "【美伊谈判代表均已抵达瑞士】财联社6月21日电，据多家媒体21日报道，美国副总统万斯已抵达瑞士"
    doc.summary = None
    doc.content = (
        "【美伊谈判代表均已抵达瑞士】财联社6月21日电，据多家媒体21日报道，"
        "美国副总统万斯已抵达瑞士，他将参加定于当天在比尔根山举行的美伊谈判。"
    )

    normalized = _normalize_crawl_document_text(doc)

    assert normalized["title"] == "美伊谈判代表均已抵达瑞士"
    assert normalized["content"].startswith("财联社6月21日电")
    assert normalized["has_content"] is True


def test_normalize_crawl_document_filters_cnstock_boilerplate_content():
    """Boilerplate app promo text should not be presented as useful article content."""
    doc = Mock()
    doc.title = "知名私募，规模腰斩"
    doc.summary = None
    doc.content = "知名私募，规模腰斩\n权威、专业、价值 尽在上海证券报客户端"

    normalized = _normalize_crawl_document_text(doc)

    assert normalized["title"] == "知名私募，规模腰斩"
    assert normalized["content"] == ""
    assert normalized["has_content"] is False


def test_normalize_crawl_document_filters_zq_metadata_json_without_body():
    """ZQ metadata JSON is not useful article/report content for the live monitor."""
    doc = Mock()
    doc.title = "量化择时和拥挤度预警周报"
    doc.summary = None
    doc.content = (
        '{"OBJID":43153409,"DOCID":64351291,'
        '"pdfNAME":"国泰海通_金融工程周报.pdf",'
        '"title":"量化择时和拥挤度预警周报",'
        '"viewpoint":"","core":"","coreViewpoint":""}'
    )

    normalized = _normalize_crawl_document_text(doc)

    assert normalized["title"] == "量化择时和拥挤度预警周报"
    assert normalized["content"] == ""
    assert normalized["has_content"] is False


def test_normalize_crawl_document_cleans_zq_reference_markers():
    """ZQ meeting/report reference markers should not leak into the live monitor."""
    doc = Mock()
    doc.source_type = "zhiqiu_transcript"
    doc.title = "机器人再迎新催化"
    doc.summary = None
    doc.content = "物理AI推动机器人产业链发展##5$$##6$$，订单放量。"

    normalized = _normalize_crawl_document_text(doc)

    assert "##5$$" not in normalized["content"]
    assert "物理AI" in normalized["content"]
    assert normalized["has_content"] is True


def test_normalize_crawl_document_cleans_pdf_report_noise_for_display():
    """ZQ report details should hide PDF table/header noise and keep readable body text."""
    doc = Mock()
    doc.source_type = "zhiqiu_reports"
    doc.title = "网上商品消费持续渗透，电商行业回归健康发展"
    doc.summary = None
    doc.content = """
<!-- page: 1 -->
本报告仅供：华安基金管理有限公司 黄泳嘉 使用，已记录日志请勿传阅。
||||p1||||股票||||股票研究 / ||||证券研究报告||||
[Table_Title]
网上商品消费持续渗透，电商行业回归健康发展
[Table_Summary]
投资要点： [[TT aabbll下 ee__周 SSuu（ mmmm20 aa2 rryy6 ]]0 622-20260626
[T abl投e_S资um建m议ar：y]伴随需求恢复，行业景气度继续改善。
5月电商行业月度跟踪显示，线上零售保持韧性，内容电商和即时零售贡献增量。
请阅读最后评级说明和重要声明
"""

    normalized = _normalize_crawl_document_text(doc)

    assert "本报告仅供" not in normalized["content"]
    assert "Table_" not in normalized["content"]
    assert "||||" not in normalized["content"]
    assert "TT aabbll" not in normalized["content"]
    assert "T abl" not in normalized["content"]
    assert "线上零售保持韧性" in normalized["content"]
    assert normalized["has_content"] is True


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_overview_uses_ths_movers_without_blocking_on_wind(
    mock_repo_cls, mock_wind_provider_cls
):
    """Market overview should render quickly from THS while Wind views load on demand."""
    mock_repo = Mock()
    mock_repo.get_combined_global_news.return_value = ([], False)
    mock_repo.get_sector_changes_from_signals.return_value = (
        [
            {
                "sector_id": "sector-ths",
                "name": "同花顺板块",
                "change_pct": 1.23,
                "leading_stocks": [],
                "related_news_count": 6,
                "is_concept": False,
            }
        ],
        [
            {
                "sector_id": "sector-ths-down",
                "name": "同花顺下跌板块",
                "change_pct": -0.88,
                "leading_stocks": [],
                "related_news_count": 4,
                "is_concept": False,
            }
        ],
        True,
        0.0,
    )
    mock_repo_cls.return_value = mock_repo

    service = DashboardService(Mock())
    overview = service.get_market_overview_section()

    assert overview.uses_real_sectors is True
    assert overview.top_up_sectors[0].name == "同花顺板块"
    assert overview.top_down_sectors[0].name == "同花顺下跌板块"
    assert overview.sector_views["ths_industry"].up[0].name == "同花顺板块"
    assert overview.sector_views["ths_industry"].up[0].view_label == "同花顺行业"
    mock_wind_provider_cls.assert_not_called()


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.dashboard_service.DashboardDataRepository")
def test_market_overview_exposes_real_index_and_breadth_snapshots(
    mock_repo_cls, mock_wind_provider_cls, monkeypatch
):
    """Market overview should pass explicit index and breadth data to the frontend."""
    monkeypatch.setattr(
        DashboardService,
        "_get_market_indices",
        lambda self: [
            MarketIndexItem(
                code="sh000001",
                name="上证指数",
                value="4163.10",
                change=1.78,
                source="sina",
            )
        ],
    )
    monkeypatch.setattr(
        DashboardService,
        "_get_market_breadth",
        lambda self: MarketBreadthSnapshot(
            up=3200,
            down=1800,
            upRatio=64.0,
            downRatio=36.0,
            turnover="1.42万亿",
            source="sina_all_a",
            sourceLabel="全A实时",
        ),
    )
    mock_repo = Mock()
    mock_repo.get_combined_global_news.return_value = ([], False)
    mock_repo.get_sector_changes_from_signals.return_value = ([], [], False, 0.0)
    mock_repo_cls.return_value = mock_repo

    service = DashboardService(Mock())
    overview = service.get_market_overview_section()

    assert overview.indices[0].name == "上证指数"
    assert overview.indices[0].value == "4163.10"
    assert overview.breadth is not None
    assert overview.breadth.sourceLabel == "全A实时"
    mock_wind_provider_cls.assert_not_called()


def test_get_market_sector_view_returns_ths_board_movers():
    """The 同花顺行业 option should use the original AKShare/THS board movers."""
    _market_sector_cache.clear()
    service = DashboardService(Mock())
    service.dashboard_repo = Mock()
    service.dashboard_repo.get_sector_changes_from_signals.return_value = (
        [
            {
                "sector_id": "sector-ths-up",
                "name": "同花顺上涨板块",
                "change_pct": 2.34,
                "leading_stocks": [],
                "related_news_count": 10,
                "is_concept": False,
            }
        ],
        [
            {
                "sector_id": "sector-ths-down",
                "name": "同花顺下跌板块",
                "change_pct": -1.23,
                "leading_stocks": [],
                "related_news_count": 8,
                "is_concept": False,
            }
        ],
        True,
        123.0,
    )

    result = service.get_market_sector_view("ths_industry", limit=5)

    service.dashboard_repo.get_sector_changes_from_signals.assert_called_once_with(
        days=7,
        limit_per_direction=5,
    )
    assert result["view_key"] == "ths_industry"
    assert result["view_label"] == "同花顺行业"
    assert result["has_real_data"] is True
    assert result["up"][0]["name"] == "同花顺上涨板块"
    assert result["up"][0]["source"] == "ths"
    assert result["up"][0]["is_concept"] is False
    assert result["down"][0]["view_label"] == "同花顺行业"


@patch("services.dashboard_service.WindMarketOverviewProvider")
def test_get_market_sector_view_defaults_to_ths_without_wind(mock_wind_provider_cls):
    """Missing or unknown selector values should not fall back to a slow Wind request."""
    _market_sector_cache.clear()
    service = DashboardService(Mock())
    service.dashboard_repo = Mock()
    service.dashboard_repo.get_sector_changes_from_signals.return_value = (
        [{"sector_id": "sector-up", "name": "默认上涨", "change_pct": 1.0}],
        [{"sector_id": "sector-down", "name": "默认下跌", "change_pct": -1.0}],
        True,
        123.0,
    )

    result = service.get_market_sector_view("", limit=5)

    assert result["view_key"] == "ths_industry"
    assert result["up"][0]["name"] == "默认上涨"
    mock_wind_provider_cls.assert_not_called()


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_prefers_realtime_workbook_by_default(
    mock_workbook_reader_cls,
    mock_wind_provider_cls,
    monkeypatch,
):
    """Wind/中信/申万口径默认走常驻工作簿，不再请求时写临时公式。"""
    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    _market_sector_cache.clear()
    mock_reader = mock_workbook_reader_cls.return_value
    mock_reader.get_view.return_value = {
        "view_key": "citic_l1",
        "view_label": "中信一级",
        "up": [
            {
                "sector_id": "wind-CI005003-WI",
                "name": "电子",
                "change_pct": 3.2,
                "leading_stocks": [],
                "related_news_count": 0,
                "is_concept": False,
                "source": "wind",
                "view_key": "citic_l1",
                "view_label": "中信一级",
            }
        ],
        "down": [],
        "has_real_data": True,
        "fetched_at": "2026-06-24T10:00:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60.0,
        "status": "ok",
        "source": "wind_realtime_workbook",
    }

    result = DashboardService(Mock()).get_market_sector_view("citic_l1", limit=5)

    mock_reader.get_view.assert_called_once_with("citic_l1", limit=5)
    mock_wind_provider_cls.assert_not_called()
    assert result["source"] == "wind_realtime_workbook"
    assert result["up"][0]["name"] == "电子"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_workbook_manager.get_wind_workbook_manager")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_returns_workbook_status_without_formula_fallback(
    mock_workbook_reader_cls,
    mock_manager_getter,
    mock_wind_provider_cls,
    monkeypatch,
):
    """工作簿没准备好时快速返回状态，不悄悄退回慢的 Wind 临时公式路径。"""
    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    _market_sector_cache.clear()
    mock_reader = mock_workbook_reader_cls.return_value
    mock_reader.get_view.return_value = {
        "view_key": "sw_l3",
        "view_label": "申万三级",
        "up": [],
        "down": [],
        "has_real_data": False,
        "fetched_at": "2026-06-24T10:00:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60.0,
        "status": "workbook_not_open",
        "message": "Wind实时工作簿未在Excel中打开",
        "source": "wind_realtime_workbook",
    }

    result = DashboardService(Mock()).get_market_sector_view("sw_l3", limit=5)

    mock_reader.get_view.assert_called_once_with("sw_l3", limit=5)
    mock_manager_getter.return_value.start_background_ensure.assert_called_once_with(
        reason="workbook_not_open"
    )
    mock_wind_provider_cls.assert_not_called()
    assert result["has_real_data"] is False
    assert result["status"] == "workbook_not_open"
    assert result["message"] == "Wind实时工作簿未在Excel中打开"


def test_ths_market_sector_badges_are_always_industry_colored():
    """The 同花顺行业 view should not mix concept and industry badge colors."""
    item = {
        "sector_id": "sector-ai",
        "name": "AI应用",
        "change_pct": 3.2,
        "is_concept": True,
    }

    decorated = DashboardService._decorate_market_sector_item(item, "ths_industry")

    assert decorated["view_label"] == "同花顺行业"
    assert decorated["is_concept"] is False
