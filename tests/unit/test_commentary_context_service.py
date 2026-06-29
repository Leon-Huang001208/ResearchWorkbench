from datetime import datetime

from core.contracts.commentary import CommentaryEvidenceItem
from core.contracts.dashboard import (
    GlobalNewsItem,
    MarketBreadthSnapshot,
    MarketIndexItem,
    MarketOverviewSection,
    SectorChangeItem,
)
from services.commentary_context_service import CommentaryContextService


class FakeDashboardService:
    def get_market_overview_section(self):
        return MarketOverviewSection(
            indices=[
                MarketIndexItem(
                    code="000001.SH",
                    name="上证指数",
                    value="2980.12",
                    change=-2.1,
                    source="sina",
                ),
                MarketIndexItem(
                    code="399006.SZ",
                    name="创业板指",
                    value="1850.42",
                    change=-3.8,
                    source="sina",
                ),
            ],
            breadth=MarketBreadthSnapshot(
                up=621,
                down=4620,
                turnover="1.8万亿",
                turnoverDelta="+18%",
                netInflow="-420亿",
            ),
            market_stats={"capital_flow_net": -420, "limit_up_count": 38, "limit_down_count": 22},
            global_news=[
                GlobalNewsItem(
                    news_id="news-ai",
                    title="海外 AI 链调整引发风险偏好回落",
                    source="CLS",
                    importance_score=0.92,
                    summary="软银和韩国半导体链下跌，市场担忧 AI 交易降温。",
                    published_at="2026-06-26T14:00:00",
                    region="Asia",
                )
            ],
            last_updated=datetime(2026, 6, 26, 14, 0, 0),
        )

    def get_market_sector_view(self, view_key, limit=8):
        return {
            "up": [
                {"name": "贵金属", "change_pct": 1.8, "source": "wind", "view_label": "同花顺行业"}
            ],
            "down": [
                {"name": "半导体", "change_pct": -4.6, "source": "wind", "view_label": "同花顺行业"},
                {"name": "证券", "change_pct": -3.2, "source": "wind", "view_label": "同花顺行业"},
            ],
        }

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        return {
            "items": [
                {
                    "doc_id": "zq-report-1",
                    "title": "券商研报提示 AI 算力链拥挤度升温",
                    "summary": "研报认为算力链估值交易已进入验证期。",
                    "source_name": "知丘研报",
                    "source_type": "zq_report",
                    "published_at": "2026-06-26T12:30:00",
                    "url": "https://example.test/report",
                },
                {
                    "doc_id": "cnstock-1",
                    "title": "海外科技股下跌拖累亚太市场",
                    "summary": "中国证券网报道，亚太科技股普遍回落。",
                    "source_name": "中国证券网",
                    "source_type": "cnstock",
                    "published_at": "2026-06-26T13:20:00",
                    "url": "https://example.test/news",
                },
            ]
        }


def test_commentary_context_service_builds_prefill_text_from_dashboard_data():
    service = CommentaryContextService(FakeDashboardService())

    context = service.build_context(recipe_id="market-drawdown")

    assert context.recipe_id == "market-drawdown"
    assert "宽基指数：上证指数 -2.10%，创业板指 -3.80%" in context.data_snapshot_text
    assert "市场广度：上涨 621 家，下跌 4620 家，成交额 1.8万亿" in context.data_snapshot_text
    assert "拖累方向：半导体 -4.60%，证券 -3.20%" in context.data_snapshot_text
    assert "媒体报道：海外 AI 链调整引发风险偏好回落" in context.evidence_pack_text
    assert any(item.kind == "confirmed" for item in context.evidence_items)
    assert any(item.kind == "reported" for item in context.evidence_items)


def test_commentary_context_service_adds_news_research_evidence_with_verification_labels():
    service = CommentaryContextService(FakeDashboardService())

    context = service.build_context(recipe_id="market-drawdown")

    assert "研报/纪要：券商研报提示 AI 算力链拥挤度升温" in context.evidence_pack_text
    assert "媒体报道：海外科技股下跌拖累亚太市场" in context.evidence_pack_text

    research = next(item for item in context.evidence_items if item.title.startswith("券商研报"))
    assert research.kind == "reported"
    assert research.source_type == "research"
    assert research.verification_status == "source_published"
    assert research.display_label == "媒体报道/研报"
    assert research.confidence_score == 0.72
    assert research.url == "https://example.test/report"

    market_data = next(item for item in context.evidence_items if item.title.startswith("上证指数"))
    assert market_data.source_type == "market_data"
    assert market_data.verification_status == "verified"
    assert market_data.confidence_score == 0.95


def test_commentary_context_service_balances_evidence_pack_between_data_and_reported_sources():
    items = [
        service_item
        for service_item in [
            *[
                {
                    "kind": "confirmed",
                    "title": f"行业数据 {idx}",
                    "summary": "行情快照。",
                    "source": "market",
                    "source_type": "market_data",
                    "verification_status": "verified",
                    "confidence_score": 0.9,
                    "display_label": "已确认数据",
                }
                for idx in range(12)
            ],
            {
                "kind": "reported",
                "title": "研报提示 AI 链拥挤度升温",
                "summary": "研报观点需要结合后续数据验证。",
                "source": "知丘研报",
                "source_type": "research",
                "verification_status": "source_published",
                "confidence_score": 0.72,
                "display_label": "媒体报道/研报",
            },
        ]
    ]

    evidence_items = [CommentaryEvidenceItem(**item) for item in items]

    lines = CommentaryContextService._build_evidence_lines(evidence_items)

    assert any("已确认数据：行业数据" in line for line in lines)
    assert any("研报/纪要：研报提示 AI 链拥挤度升温" in line for line in lines)


def test_commentary_context_service_ranks_attribution_signals_by_explanatory_power():
    service = CommentaryContextService(FakeDashboardService())

    context = service.build_context(recipe_id="market-drawdown")

    assert context.attribution_signals
    assert context.attribution_signals[0].rank == 1
    assert context.attribution_signals[0].strength == "primary"
    assert context.attribution_signals[0].tag == "ai_crowding"
    assert context.attribution_signals[0].score >= 80
    assert "半导体" in context.attribution_signals[0].rationale

    tags = [signal.tag for signal in context.attribution_signals]
    assert "liquidity_outflow" in tags
    assert "overseas_shock" in tags
    assert all(signal.evidence_titles for signal in context.attribution_signals)
