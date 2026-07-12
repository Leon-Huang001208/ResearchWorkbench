from datetime import datetime

from core.contracts.commentary import CommentaryEvidenceItem
from core.contracts.dashboard import (
    GlobalNewsItem,
    MarketBreadthSnapshot,
    MarketIndexItem,
    MarketOverviewSection,
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
            "up": [{"name": "贵金属", "change_pct": 1.8, "source": "wind", "view_label": "同花顺行业"}],
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


class FakeDashboardServiceWithMetaShock(FakeDashboardService):
    def get_market_overview_section(self):
        overview = super().get_market_overview_section()
        overview.global_news = []
        return overview

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        noisy_items = [
            {
                "doc_id": f"generic-{idx}",
                "title": f"普通宏观新闻 {idx}",
                "summary": "这是一条与市场泛化风险偏好相关但缺少具体科技触发因素的新闻。",
                "source_name": "新闻源",
                "source_type": "news",
                "published_at": "2026-07-02T08:00:00",
            }
            for idx in range(10)
        ]
        return {
            "items": [
                *noisy_items,
                {
                    "doc_id": "meta-shock",
                    "title": "Meta 释放 AI 投入相关消息，美股科技股承压",
                    "summary": "市场关注 Meta 对 AI 基础设施投入、模型路线和科技巨头资本开支预期的影响。",
                    "source_name": "海外新闻",
                    "source_type": "news",
                    "published_at": "2026-07-02T07:30:00",
                    "url": "https://example.test/meta",
                },
            ]
        }


class FakeDashboardServiceWithBuriedNews(FakeDashboardService):
    def get_market_overview_section(self):
        overview = super().get_market_overview_section()
        overview.global_news = [
            GlobalNewsItem(
                news_id=f"generic-news-{idx}",
                title=f"普通市场新闻 {idx}",
                source="CLS",
                importance_score=0.5,
                summary="泛化描述市场风险偏好变化，没有明确触发因素。",
                published_at=f"2026-07-02T08:{idx:02d}:00",
                region="China",
            )
            for idx in range(8)
        ]
        return overview

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        generic_items = [
            {
                "doc_id": f"generic-crawl-{idx}",
                "title": f"普通宏观新闻 {idx}",
                "summary": "泛化描述风险偏好和资金分歧，没有明确事件主体。",
                "source_name": "新闻源",
                "source_type": "news",
                "published_at": f"2026-07-02T09:{idx:02d}:00",
            }
            for idx in range(30)
        ]
        return {
            "items": [
                *generic_items,
                {
                    "doc_id": "meta-ai-capex",
                    "title": "Meta 释放 AI 资本开支上修信号，美股科技股大跌",
                    "summary": "市场担忧 Meta AI 基础设施投入推升科技巨头资本开支，纳指和半导体链承压。",
                    "source_name": "海外新闻",
                    "source_type": "news",
                    "published_at": "2026-07-02T10:10:00",
                    "url": "https://example.test/meta-ai-capex",
                },
            ]
        }


class FakeDashboardServiceWithDuplicateNews(FakeDashboardService):
    def get_market_overview_section(self):
        overview = super().get_market_overview_section()
        overview.global_news = []
        return overview

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        return {
            "items": [
                {
                    "doc_id": "nvidia-a",
                    "title": "英伟达推出AI基础设施新合作模式",
                    "summary": "英伟达与AI云服务商通过收入分成建设算力基础设施。",
                    "source_name": "新闻源A",
                    "source_type": "news",
                    "published_at": "2026-07-02T10:00:00",
                },
                {
                    "doc_id": "nvidia-b",
                    "title": "英伟达推出AI基础设施新合作模式 与AI云厂商共享收入",
                    "summary": "英伟达推出AI基础设施合作模式，帮助企业获得AI算力。",
                    "source_name": "新闻源B",
                    "source_type": "news",
                    "published_at": "2026-07-02T10:01:00",
                },
                {
                    "doc_id": "openai-policy",
                    "title": "OpenAI据悉提议向美国政府提供股权以争取政策支持",
                    "summary": "市场关注人工智能产业政策支持和科技股风险偏好变化。",
                    "source_name": "新闻源C",
                    "source_type": "news",
                    "published_at": "2026-07-02T10:02:00",
                },
            ]
        }


class FakeDashboardServiceWithSectorSpecificNews(FakeDashboardService):
    def get_market_overview_section(self):
        overview = super().get_market_overview_section()
        overview.global_news = []
        return overview

    def get_market_sector_view(self, view_key, limit=8):
        return {
            "up": [{"name": "贵金属", "change_pct": 3.9, "source": "ths", "view_label": "同花顺行业"}],
            "down": [{"name": "证券", "change_pct": -3.2, "source": "ths", "view_label": "同花顺行业"}],
        }

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        return {
            "items": [
                {
                    "doc_id": "fixed-ai",
                    "title": "OpenAI 推出新模型，人工智能产业关注度提升",
                    "summary": "这条新闻命中固定 AI 关键词，但和今日贵金属领涨关系不强。",
                    "source_name": "海外新闻",
                    "source_type": "news",
                    "published_at": "2026-07-02T10:00:00",
                },
                {
                    "doc_id": "gold-sector",
                    "title": "国际金价走强，贵金属板块领涨",
                    "summary": "避险需求升温叠加美元走弱，黄金和白银相关公司受资金关注。",
                    "source_name": "全源新闻",
                    "source_type": "cnstock",
                    "published_at": "2026-07-02T10:05:00",
                },
            ]
        }


class FakeDashboardServiceRecordingCrawlScope(FakeDashboardService):
    def __init__(self):
        self.crawl_calls = []

    def get_crawl_feed(self, limit=20, since=None, source_type=None):
        self.crawl_calls.append(
            {
                "limit": limit,
                "since": since,
                "source_type": source_type,
            }
        )
        return {"items": []}


class FailingDashboardService:
    def get_market_overview_section(self):
        raise RuntimeError("dashboard unavailable")

    def get_market_sector_view(self, view_key, limit=8):
        raise RuntimeError("sector unavailable")


def test_commentary_context_service_builds_prefill_text_from_dashboard_data():
    service = CommentaryContextService(FakeDashboardService())

    context = service.build_context(recipe_id="market-drawdown")

    assert context.recipe_id == "market-drawdown"
    assert "宽基指数：上证指数 -2.10%，创业板指 -3.80%" in context.data_snapshot_text
    assert "市场广度：上涨 621 家，下跌 4620 家，成交额 1.8万亿" in context.data_snapshot_text
    assert "拖累方向：半导体 -4.60%，证券 -3.20%" in context.data_snapshot_text
    assert "消息面主线：海外 AI 链调整引发风险偏好回落" in context.evidence_pack_text
    assert any(item.kind == "confirmed" for item in context.evidence_items)
    assert any(item.kind == "reported" for item in context.evidence_items)


def test_commentary_context_service_adds_news_research_evidence_with_verification_labels():
    service = CommentaryContextService(FakeDashboardService())

    context = service.build_context(recipe_id="market-drawdown")

    assert "消息面主线：券商研报提示 AI 算力链拥挤度升温" in context.evidence_pack_text
    assert "消息面主线：海外科技股下跌拖累亚太市场" in context.evidence_pack_text

    research = next(item for item in context.evidence_items if item.title.startswith("券商研报"))
    assert research.kind == "reported"
    assert research.source_type == "research"
    assert research.verification_status == "source_published"
    assert research.display_label == "媒体报道/研报"
    assert research.confidence_score >= 0.72
    assert research.metadata["matched_terms"]
    assert research.metadata["retrieval_rank"] >= 1
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

    assert any("行情验证：行业数据" in line for line in lines)
    assert any("消息面主线：研报提示 AI 链拥挤度升温" in line for line in lines)


def test_commentary_context_service_compacts_multiline_news_summary_in_evidence_lines():
    items = [
        CommentaryEvidenceItem(
            kind="reported",
            title="英伟达推出 AI 基础设施合作模式",
            summary="第一段新闻正文。\n\n第二段包含更多细节。\n第三段继续解释影响。",
            source="新闻源",
            source_type="news",
            verification_status="source_published",
            confidence_score=0.8,
            display_label="媒体报道/新闻",
        )
    ]

    lines = CommentaryContextService._build_evidence_lines(items, recipe_id="market-drawdown")

    assert len(lines) == 1
    assert "\n" not in lines[0]
    assert "影响：第一段新闻正文。" in lines[0]
    assert "第二段包含更多细节" not in lines[0]


def test_commentary_context_service_formats_ranked_news_as_event_impact_line():
    items = [
        CommentaryEvidenceItem(
            kind="reported",
            title="Meta 释放 AI 资本开支上修信号，美股科技股大跌",
            summary=(
                "市场担忧 Meta AI 基础设施投入推升科技巨头资本开支，纳指和半导体链承压。" "第二段继续展开大量背景材料和行业涨跌幅，容易让生成结果变成新闻原文摘抄。"
            ),
            source="海外新闻",
            source_type="news",
            verification_status="source_published",
            confidence_score=0.86,
            display_label="媒体报道/新闻",
            metadata={"matched_terms": ["Meta", "资本开支", "科技股", "AI"]},
        )
    ]

    line = CommentaryContextService._build_evidence_lines(
        items,
        recipe_id="market-drawdown",
    )[0]

    assert line.startswith("消息面主线：Meta 释放 AI 资本开支上修信号")
    assert "触发词：" in line
    assert "Meta" in line
    assert "资本开支" in line
    assert "；影响：" in line
    assert "第二段继续展开大量背景材料" not in line
    assert len(line) <= 170


def test_commentary_context_service_dedupes_similar_news_events():
    service = CommentaryContextService(FakeDashboardServiceWithDuplicateNews())

    context = service.build_context(recipe_id="market-drawdown")

    lines = context.evidence_pack_text.splitlines()
    nvidia_lines = [line for line in lines if "英伟达推出AI基础设施新合作模式" in line]
    assert len(nvidia_lines) == 1
    assert any("OpenAI据悉提议" in line for line in lines)


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


def test_commentary_context_service_prioritizes_meta_us_tech_shock_evidence():
    service = CommentaryContextService(FakeDashboardServiceWithMetaShock())

    context = service.build_context(recipe_id="market-drawdown")

    assert "Meta 释放 AI 投入相关消息" in context.evidence_pack_text
    overseas = next(
        signal for signal in context.attribution_signals if signal.tag == "overseas_shock"
    )
    assert overseas.score >= 74
    assert overseas.strength in {"primary", "secondary"}
    assert any("Meta" in title for title in overseas.evidence_titles)


def test_commentary_context_service_uses_report_style_news_selection_before_market_data():
    service = CommentaryContextService(FakeDashboardServiceWithBuriedNews())

    context = service.build_context(recipe_id="market-drawdown")

    first_line = context.evidence_pack_text.splitlines()[0]
    assert first_line.startswith("消息面主线：Meta 释放 AI 资本开支上修信号")
    assert "普通宏观新闻 0" not in context.evidence_pack_text
    assert context.evidence_pack_text.index("消息面主线：") < context.evidence_pack_text.index("行情验证：")
    first_item = context.evidence_items[0]
    assert first_item.source_type == "news"
    assert first_item.metadata["retrieval_method"] == "keyword"
    assert "Meta" in first_item.metadata["matched_terms"]


def test_commentary_context_service_uses_today_sector_movers_as_dynamic_news_terms():
    service = CommentaryContextService(FakeDashboardServiceWithSectorSpecificNews())

    context = service.build_context(recipe_id="daily-close")

    first_line = context.evidence_pack_text.splitlines()[0]
    assert first_line.startswith("消息面主线：国际金价走强，贵金属板块领涨")
    assert "OpenAI 推出新模型" in context.evidence_pack_text
    first_item = context.evidence_items[0]
    assert first_item.title.startswith("国际金价走强")
    assert "贵金属" in first_item.metadata["matched_terms"]
    assert "黄金" in first_item.metadata["matched_terms"]
    assert "贵金属" in first_item.metadata["dynamic_terms"]


def test_commentary_context_service_reads_broad_unfiltered_crawl_feed_pool():
    dashboard = FakeDashboardServiceRecordingCrawlScope()
    service = CommentaryContextService(dashboard)

    service.build_context(recipe_id="daily-close")

    assert dashboard.crawl_calls
    assert dashboard.crawl_calls[0]["limit"] >= 200
    assert dashboard.crawl_calls[0]["source_type"] is None


def test_commentary_context_service_returns_editable_fallback_when_dashboard_fails():
    service = CommentaryContextService(FailingDashboardService())

    context = service.build_context(recipe_id="daily-close")

    assert context.recipe_id == "daily-close"
    assert "市场数据：仪表盘数据暂不可用" in context.data_snapshot_text
    assert "证据包：仪表盘上下文加载失败" in context.evidence_pack_text
    assert len(context.evidence_items) == 1
    assert context.evidence_items[0].source == "commentary_context"
    assert context.evidence_items[0].verification_status == "unverified"
