"""Unit tests for Dashboard Service"""
import json
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from core.contracts.dashboard import DashboardResponse, MarketBreadthSnapshot, MarketIndexItem
from data_layer.repositories.dashboard_data import _normalize_crawl_document_text
from services.dashboard_service import DashboardService, _market_sector_cache


@pytest.fixture(autouse=True)
def _mock_market_command_snapshot(monkeypatch, tmp_path):
    """Dashboard unit tests should not call live market quote providers."""
    from services import dashboard_service as module

    _market_sector_cache.clear()
    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
    monkeypatch.setattr(
        DashboardService,
        "_get_market_indices",
        lambda self, force_refresh=False: [],
    )
    monkeypatch.setattr(
        DashboardService,
        "_get_market_breadth",
        lambda self, force_refresh=False: None,
    )


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
    doc.content = "【美伊谈判代表均已抵达瑞士】财联社6月21日电，据多家媒体21日报道，" "美国副总统万斯已抵达瑞士，他将参加定于当天在比尔根山举行的美伊谈判。"

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
        lambda self, force_refresh=False: [
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
        lambda self, force_refresh=False: MarketBreadthSnapshot(
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


def test_sector_breadth_includes_previous_turnover(monkeypatch):
    """Breadth fallbacks should populate the previous trading day turnover."""
    from data_layer.crawlers.akshare.board import SectorBoardItem, SectorBoardSnapshot

    monkeypatch.setattr(
        DashboardService,
        "_get_previous_market_turnover",
        staticmethod(lambda force_refresh=False: {"formatted": "1.49万亿"}),
    )

    snapshot = SectorBoardSnapshot(
        sectors=[
            SectorBoardItem(
                name="测试行业",
                change_pct=1.2,
                net_flow=3.4,
                up_count=30,
                down_count=10,
                total_volume=100.0,
                total_amount=2500.0,
                avg_price=12.3,
                leading_stock_name="测试股份",
                leading_stock_price=10.0,
                leading_stock_change_pct=5.0,
            )
        ],
        fetched_at=time.time(),
    )
    monkeypatch.setattr(
        "data_layer.crawlers.akshare.board.fetch_sector_board",
        lambda force_refresh=False: snapshot,
    )

    breadth = DashboardService(Mock())._get_sector_board_breadth(force_refresh=True)

    assert breadth is not None
    assert breadth.previousTurnover == "1.49万亿"


def test_previous_market_turnover_sums_exchange_a_share_amounts(monkeypatch):
    """Previous turnover should use SSE/SZSE A-share rows and normalize units."""
    fake_ak = SimpleNamespace(
        stock_sse_deal_daily=lambda date: pd.DataFrame(
            [
                {
                    "单日情况": "成交金额",
                    "股票": 5676.60,
                    "主板A": 4545.46,
                    "主板B": 1.37,
                    "科创板": 1129.77,
                }
            ]
        ),
        stock_szse_summary=lambda date: pd.DataFrame(
            [
                {"证券类别": "股票", "成交金额": 9.203914e11},
                {"证券类别": "主板A股", "成交金额": 4.576296e11},
                {"证券类别": "主板B股", "成交金额": 1.108354e8},
                {"证券类别": "创业板A股", "成交金额": 4.626510e11},
            ]
        ),
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_ak)

    amount = DashboardService._fetch_previous_trading_day_turnover_yuan("20250630")

    expected = (4545.46 + 1129.77) * 100_000_000 + 4.576296e11 + 4.626510e11
    assert amount == pytest.approx(expected)


def test_get_market_sector_view_returns_ths_board_movers(monkeypatch, tmp_path):
    """The 同花顺行业 option should use the original AKShare/THS board movers."""
    from services import dashboard_service as module

    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
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
def test_get_market_sector_view_defaults_to_ths_without_wind(
    mock_wind_provider_cls,
    monkeypatch,
    tmp_path,
):
    """Missing or unknown selector values should not fall back to a slow Wind request."""
    from services import dashboard_service as module

    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
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
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_uses_persistent_cache_before_excel(
    mock_workbook_reader_cls,
    mock_wind_provider_cls,
    monkeypatch,
    tmp_path,
):
    """重启后优先使用本地快照，避免首屏请求阻塞在 Excel 自动化上。"""
    from services import dashboard_service as module

    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
    _market_sector_cache.clear()
    payload = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [
            {
                "sector_id": "wind-8841924-WI",
                "name": "光电路交换机(OCS)指数",
                "change_pct": 7.41,
                "leading_stocks": [],
                "related_news_count": 0,
                "is_concept": True,
                "source": "wind",
                "view_key": "wind_hot_concept",
                "view_label": "Wind热门概念",
            }
        ],
        "down": [],
        "has_real_data": True,
        "fetched_at": "2026-06-30T06:00:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60.0,
        "status": "ok",
        "source": "wind_realtime_workbook",
    }
    module.MARKET_SECTOR_DISK_CACHE_PATH.write_text(
        json.dumps(
            {
                "wind_hot_concept|30": {
                    "cached_at": time.time(),
                    "payload": payload,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = DashboardService(Mock()).get_market_sector_view(
        "wind_hot_concept",
        limit=30,
    )

    mock_workbook_reader_cls.assert_not_called()
    mock_wind_provider_cls.assert_not_called()
    assert result["cache_hit"] is True
    assert result["up"][0]["name"] == "光电路交换机(OCS)"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_force_refresh_bypasses_persistent_cache(
    mock_workbook_reader_cls,
    mock_wind_provider_cls,
    monkeypatch,
    tmp_path,
):
    """实时刷新必须绕过本地快照，直接读取 Excel Wind 工作簿。"""
    from services import dashboard_service as module

    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
    _market_sector_cache.clear()
    module.MARKET_SECTOR_DISK_CACHE_PATH.write_text(
        json.dumps(
            {
                "wind_hot_concept|30": {
                    "cached_at": time.time(),
                    "payload": {
                        "view_key": "wind_hot_concept",
                        "view_label": "Wind热门概念",
                        "up": [
                            {
                                "sector_id": "wind-8841924-WI",
                                "name": "缓存概念",
                                "change_pct": 7.41,
                                "source": "wind",
                            }
                        ],
                        "down": [],
                        "has_real_data": True,
                        "status": "ok",
                        "source": "wind_realtime_workbook",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mock_workbook_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [
            {
                "sector_id": "wind-8841902-WI",
                "name": "实时概念",
                "change_pct": 8.18,
                "source": "wind",
            }
        ],
        "down": [],
        "has_real_data": True,
        "cache_hit": False,
        "status": "ok",
        "source": "wind_realtime_workbook",
    }

    result = DashboardService(Mock()).get_market_sector_view(
        "wind_hot_concept",
        limit=30,
        force_refresh=True,
    )

    mock_workbook_reader_cls.return_value.get_view.assert_called_once_with(
        "wind_hot_concept",
        limit=30,
    )
    mock_wind_provider_cls.assert_not_called()
    assert result["source"] == "wind_realtime_workbook"
    assert result["cache_hit"] is False
    assert result["up"][0]["name"] == "实时概念"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_ignores_ths_persistent_cache_for_wind_view(
    mock_workbook_reader_cls,
    mock_wind_provider_cls,
    monkeypatch,
    tmp_path,
):
    """Wind 口径不能复用 THS 行业兜底缓存，否则 UI 会显示错数据源。"""
    from services import dashboard_service as module

    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
    _market_sector_cache.clear()
    module.MARKET_SECTOR_DISK_CACHE_PATH.write_text(
        json.dumps(
            {
                "wind_hot_concept|30": {
                    "cached_at": time.time(),
                    "payload": {
                        "view_key": "wind_hot_concept",
                        "view_label": "Wind热门概念",
                        "up": [
                            {
                                "sector_id": "sector-ths-up",
                                "name": "贵金属",
                                "change_pct": 4.66,
                                "source": "ths_board_fallback",
                            }
                        ],
                        "down": [],
                        "has_real_data": True,
                        "status": "wind_unavailable_ths_fallback",
                        "source": "ths_board_fallback",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mock_workbook_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [
            {
                "sector_id": "wind-8841924-WI",
                "name": "光电路交换机(OCS)指数",
                "change_pct": 7.41,
                "source": "wind",
            }
        ],
        "down": [],
        "has_real_data": True,
        "source": "wind_realtime_workbook",
        "status": "ok",
    }

    result = DashboardService(Mock()).get_market_sector_view(
        "wind_hot_concept",
        limit=30,
    )

    mock_workbook_reader_cls.return_value.get_view.assert_called_once_with(
        "wind_hot_concept",
        limit=30,
    )
    mock_wind_provider_cls.assert_not_called()
    assert result["source"] == "wind_realtime_workbook"
    assert result["up"][0]["name"] == "光电路交换机(OCS)"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_ignores_stale_inactive_wind_cache(
    mock_workbook_reader_cls,
    mock_wind_provider_cls,
    monkeypatch,
    tmp_path,
):
    """Wind 缓存若包含已从 active catalog 移除的指数，应丢弃并重新读工作簿。"""
    from services import dashboard_service as module

    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    monkeypatch.setattr(
        module,
        "MARKET_SECTOR_DISK_CACHE_PATH",
        tmp_path / "market_sector_movers.json",
    )
    monkeypatch.setattr(
        module,
        "load_wind_index_catalog",
        lambda: (
            SimpleNamespace(
                code="8841892.WI",
                view_key="wind_hot_concept",
                is_active=True,
            ),
        ),
    )
    _market_sector_cache.clear()
    module.MARKET_SECTOR_DISK_CACHE_PATH.write_text(
        json.dumps(
            {
                "wind_hot_concept|30": {
                    "cached_at": time.time(),
                    "payload": {
                        "view_key": "wind_hot_concept",
                        "view_label": "Wind热门概念",
                        "up": [
                            {
                                "sector_id": "wind-884833-WI",
                                "name": "折叠屏指数",
                                "change_pct": 7.27,
                                "source": "wind",
                            }
                        ],
                        "down": [],
                        "has_real_data": True,
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    mock_workbook_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [
            {
                "sector_id": "wind-8841892-WI",
                "name": "光芯片指数",
                "change_pct": 7.99,
                "source": "wind",
            }
        ],
        "down": [],
        "has_real_data": True,
        "source": "wind_realtime_workbook",
    }

    result = DashboardService(Mock()).get_market_sector_view(
        "wind_hot_concept",
        limit=30,
    )

    assert result["source"] == "wind_realtime_workbook"
    assert result["up"][0]["name"] == "光芯片"
    mock_workbook_reader_cls.return_value.get_view.assert_called_once_with(
        "wind_hot_concept",
        limit=30,
    )
    mock_wind_provider_cls.assert_not_called()


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_workbook_manager.get_wind_workbook_manager")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_falls_back_when_workbook_not_open(
    mock_workbook_reader_cls,
    mock_manager_getter,
    mock_wind_provider_cls,
    monkeypatch,
):
    """工作簿没打开时，默认回落到 Wind 指数公式兜底，避免前端空白。"""
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
    mock_provider = mock_wind_provider_cls.return_value
    mock_provider.seeds = []
    mock_provider.get_grouped_movers.return_value = {
        "views": {
            "sw_l3": {
                "up": [
                    {
                        "sector_id": "wind-801012-SI",
                        "name": "半导体",
                        "change_pct": 2.4,
                        "leading_stocks": [],
                        "related_news_count": 0,
                        "is_concept": False,
                        "source": "wind",
                        "view_key": "sw_l3",
                        "view_label": "申万三级",
                    }
                ],
                "down": [],
            }
        },
        "has_real_data": True,
        "fetched_at": 123.0,
    }

    result = DashboardService(Mock()).get_market_sector_view("sw_l3", limit=5)

    mock_reader.get_view.assert_called_once_with("sw_l3", limit=5)
    mock_manager_getter.return_value.start_background_ensure.assert_called_once_with(
        reason="workbook_not_open"
    )
    mock_provider.get_grouped_movers.assert_called_once_with(
        limit=5,
        view_keys=("sw_l3",),
    )
    assert result["has_real_data"] is True
    assert result["up"][0]["name"] == "半导体"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_workbook_manager.get_wind_workbook_manager")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_times_out_slow_workbook_read(
    mock_workbook_reader_cls,
    mock_manager_getter,
    mock_wind_provider_cls,
    monkeypatch,
):
    """Excel 自动化卡住时，Wind 口径请求要快速返回而不是拖死桌面后端。"""
    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_WIND_WORKBOOK_READ_TIMEOUT_SECONDS", "0.01")
    _market_sector_cache.clear()
    mock_reader = mock_workbook_reader_cls.return_value

    def slow_get_view(*_args, **_kwargs):
        time.sleep(0.2)
        return {
            "view_key": "sw_l3",
            "view_label": "申万三级",
            "up": [],
            "down": [],
            "has_real_data": False,
            "status": "snapshot_invalid",
            "source": "wind_realtime_workbook",
        }

    mock_reader.get_view.side_effect = slow_get_view

    started = time.time()
    result = DashboardService(Mock()).get_market_sector_view("sw_l3", limit=5)

    assert time.time() - started < 0.5
    mock_manager_getter.return_value.start_background_ensure.assert_called_once_with(
        reason="workbook_timeout"
    )
    mock_wind_provider_cls.assert_not_called()
    assert result["has_real_data"] is False
    assert result["status"] == "workbook_timeout"
    assert result["source"] == "wind_realtime_workbook"


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_workbook_manager.get_wind_workbook_manager")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_does_not_mask_wind_view_with_ths_fallback(
    mock_workbook_reader_cls,
    mock_manager_getter,
    mock_wind_provider_cls,
    monkeypatch,
):
    """Wind/Excel 都不可用时，Wind 口径不能伪装成 THS 行业数据。"""
    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", raising=False)
    _market_sector_cache.clear()
    mock_reader = mock_workbook_reader_cls.return_value
    mock_reader.get_view.return_value = {
        "view_key": "wind_hot_concept",
        "view_label": "Wind热门概念",
        "up": [],
        "down": [],
        "has_real_data": False,
        "fetched_at": "2026-06-24T10:00:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 60.0,
        "status": "workbook_read_error",
        "message": "Excel 自动化权限被拒绝",
        "source": "wind_realtime_workbook",
    }
    mock_provider = mock_wind_provider_cls.return_value
    mock_provider.seeds = []
    mock_provider.get_grouped_movers.return_value = {
        "views": {"wind_hot_concept": {"up": [], "down": []}},
        "has_real_data": False,
        "fetched_at": 0.0,
    }
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
                "is_concept": True,
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

    result = service.get_market_sector_view("wind_hot_concept", limit=5)

    mock_manager_getter.return_value.start_background_ensure.assert_called_once_with(
        reason="workbook_read_error"
    )
    service.dashboard_repo.get_sector_changes_from_signals.assert_not_called()
    assert result["status"] == "workbook_read_error"
    assert result["source"] == "wind_realtime_workbook"
    assert result["view_label"] == "Wind热门概念"
    assert result["up"] == []
    assert result["down"] == []
    assert result["has_real_data"] is False


@patch("services.dashboard_service.WindMarketOverviewProvider")
@patch("services.wind_workbook_manager.get_wind_workbook_manager")
@patch("services.wind_realtime_workbook.WindRealtimeWorkbookReader")
def test_get_market_sector_view_returns_workbook_status_without_formula_fallback(
    mock_workbook_reader_cls,
    mock_manager_getter,
    mock_wind_provider_cls,
    monkeypatch,
):
    """显式关闭兜底时，工作簿没准备好会快速返回状态。"""
    monkeypatch.delenv("ALPHAFOUNDRY_ENABLE_WIND_WORKBOOK", raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_ALLOW_WIND_EXCEL_FALLBACK", "0")
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
