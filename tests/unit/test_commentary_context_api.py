from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.commentary import (
    get_commentary_context_service,
    get_commentary_draft_service,
    get_commentary_run_service,
    router,
)
from core.contracts.commentary import (
    CommentaryAttributionSignal,
    CommentaryContextPack,
    CommentaryDraftResponse,
    CommentaryQualityCheckResponse,
    CommentaryQualityIssue,
    CommentaryRunRecord,
    CommentaryRunRecordResponse,
    CommentarySectionRewriteResponse,
)


class FakeCommentaryContextService:
    def build_context(self, recipe_id: str = "daily-close") -> CommentaryContextPack:
        return CommentaryContextPack(
            recipe_id=recipe_id,
            data_snapshot_text="宽基指数：上证指数 -2.10%，沪深300 -2.40%。",
            evidence_pack_text="媒体报道：海外 AI 链调整引发风险偏好回落。",
            evidence_items=[
                {
                    "kind": "confirmed",
                    "title": "上证指数 -2.10%",
                    "summary": "指数行情来自市场总览。",
                    "source": "market_overview",
                    "source_type": "market_data",
                    "verification_status": "verified",
                    "confidence_score": 0.95,
                    "display_label": "已确认数据",
                },
                {
                    "kind": "reported",
                    "title": "海外 AI 链调整",
                    "summary": "新闻证据来自仪表盘热点新闻。",
                    "source": "dashboard_news",
                    "source_type": "news",
                    "verification_status": "source_published",
                    "confidence_score": 0.68,
                    "display_label": "媒体报道/新闻",
                },
            ],
            attribution_signals=[
                CommentaryAttributionSignal(
                    rank=1,
                    tag="ai_crowding",
                    label="AI拥挤交易降温",
                    strength="primary",
                    score=86,
                    confidence_score=0.78,
                    verification_status="derived",
                    rationale="半导体领跌且海外 AI 链新闻共振。",
                    evidence_titles=["半导体 -4.60%", "海外 AI 链调整"],
                )
            ],
            generated_at=datetime(2026, 6, 26, 15, 30, 0),
        )


class FakeCommentaryDraftService:
    def generate_draft(self, request):
        return CommentaryDraftResponse(
            recipe_id=request.recipe_id,
            draft_markdown="# 市场大跌归因\n\n今日市场调整主要来自风险偏好回落。",
            sections=[
                {"heading": "核心判断", "content": "风险偏好回落是主要矛盾。"},
            ],
            citations=[{"title": "上证指数 -2.10%", "kind": "confirmed", "source": "market_overview"}],
            attribution_signals=[
                {
                    "rank": 1,
                    "tag": "ai_crowding",
                    "label": "AI拥挤交易降温",
                    "strength": "primary",
                    "score": 86,
                }
            ],
            warnings=[],
            model="fake-model",
            provider="fake",
        )

    def rewrite_section(self, **kwargs):
        return CommentarySectionRewriteResponse(
            recipe_id=kwargs["recipe_id"],
            section_heading=kwargs["section_heading"],
            rewritten_content="改写后的核心判断：风险偏好仍需观察。",
            action=kwargs["action"],
            warnings=[],
            model="fake-model",
            provider="fake",
        )

    def check_quality(self, draft_markdown, context):
        return CommentaryQualityCheckResponse(
            status="blocked",
            summary={"blocked": 1, "warning": 0, "info": 0},
            issues=[
                CommentaryQualityIssue(
                    code="missing_risk_disclosure",
                    severity="blocker",
                    title="缺少风险提示",
                    detail="草稿缺少后续观察或风险提示。",
                )
            ],
        )


class FakeCommentaryRunService:
    def __init__(self):
        self.records = []

    def record_run(self, request):
        record = CommentaryRunRecord(
            run_id="commentary-test-run",
            recipe_id=request.recipe_id,
            recipe_title=request.recipe_title,
            draft_markdown=request.draft_markdown,
            model=request.model,
            provider=request.provider,
            warnings=request.warnings,
            evidence_count=request.evidence_count,
            selected_evidence_count=request.selected_evidence_count,
            quality_status=request.quality_status,
            quality_summary=request.quality_summary,
        )
        self.records.append(record)
        return CommentaryRunRecordResponse(
            run_id=record.run_id,
            log_path="logs/commentary_runs.jsonl",
            record=record,
        )

    def list_runs(self, limit=20):
        return self.records[-limit:]


def make_client():
    app = FastAPI()
    fake_run_service = FakeCommentaryRunService()
    app.include_router(router)
    app.dependency_overrides[
        get_commentary_context_service
    ] = lambda: FakeCommentaryContextService()
    app.dependency_overrides[get_commentary_draft_service] = lambda: FakeCommentaryDraftService()
    app.dependency_overrides[get_commentary_run_service] = lambda: fake_run_service
    return TestClient(app)


def test_commentary_context_endpoint_returns_prefill_text_and_evidence_items():
    client = make_client()

    response = client.get("/api/commentary/context?recipe_id=market-drawdown")

    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] == "market-drawdown"
    assert "上证指数 -2.10%" in body["data_snapshot_text"]
    assert "海外 AI 链调整" in body["evidence_pack_text"]
    assert body["evidence_items"][0]["kind"] == "confirmed"
    assert body["evidence_items"][1]["kind"] == "reported"
    assert body["evidence_items"][0]["verification_status"] == "verified"
    assert body["evidence_items"][1]["source_type"] == "news"
    assert body["attribution_signals"][0]["tag"] == "ai_crowding"
    assert body["attribution_signals"][0]["strength"] == "primary"


def test_commentary_recipes_endpoint_returns_shared_template_contract():
    client = make_client()

    response = client.get("/api/commentary/recipes")

    assert response.status_code == 200
    body = response.json()
    assert body["default_recipe_id"] == "daily-close"
    assert body["recipes"][0]["id"] == "daily-close"
    assert body["recipes"][0]["title"] == "每日收盘点评"
    assert body["recipes"][0]["sections"] == [
        "今日市场表现",
        "行业与风格变化",
        "资金与情绪",
        "核心归因",
        "后续观察",
    ]
    assert any(recipe["id"] == "etf-allocation" for recipe in body["recipes"])


def test_main_app_registers_commentary_context_route():
    from app.api.main import app as main_app

    main_app.dependency_overrides[
        get_commentary_context_service
    ] = lambda: FakeCommentaryContextService()
    client = TestClient(main_app)

    try:
        response = client.get("/api/commentary/context")
        assert response.status_code == 200
        assert "宽基指数" in response.json()["data_snapshot_text"]
    finally:
        main_app.dependency_overrides.pop(get_commentary_context_service, None)


def test_commentary_draft_endpoint_returns_model_draft():
    client = make_client()

    response = client.post(
        "/api/commentary/draft",
        json={
            "recipe_id": "market-drawdown",
            "data_snapshot_text": "宽基指数：上证指数 -2.10%。",
            "evidence_pack_text": "已确认数据：上证指数 -2.10%。",
            "subjective_judgement": "核心是风险偏好回落。",
            "evidence_items": [
                {
                    "kind": "confirmed",
                    "title": "上证指数 -2.10%",
                    "summary": "指数行情来自市场总览。",
                    "source": "market_overview",
                    "source_type": "market_data",
                    "verification_status": "verified",
                    "confidence_score": 0.95,
                    "display_label": "已确认数据",
                }
            ],
            "attribution_signals": [
                {
                    "rank": 1,
                    "tag": "ai_crowding",
                    "label": "AI拥挤交易降温",
                    "strength": "primary",
                    "score": 86,
                    "confidence_score": 0.78,
                    "verification_status": "derived",
                    "rationale": "半导体领跌且海外 AI 链新闻共振。",
                    "evidence_titles": ["半导体 -4.60%", "海外 AI 链调整"],
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] == "market-drawdown"
    assert "市场大跌归因" in body["draft_markdown"]
    assert body["sections"][0]["heading"] == "核心判断"
    assert body["citations"][0]["kind"] == "confirmed"
    assert body["attribution_signals"][0]["tag"] == "ai_crowding"


def test_commentary_section_rewrite_endpoint_returns_single_section_result():
    client = make_client()

    response = client.post(
        "/api/commentary/section-rewrite",
        json={
            "recipe_id": "market-drawdown",
            "section_heading": "核心判断",
            "section_content": "市场必然继续调整，核心原因确定是海外冲击。",
            "action": "soften",
            "data_snapshot_text": "宽基指数：上证指数 -2.10%。",
            "evidence_pack_text": "已确认数据：上证指数 -2.10%。",
            "subjective_judgement": "核心是风险偏好回落。",
            "evidence_items": [],
            "attribution_signals": [],
            "writing_preferences": {"audience": "client", "length": "short"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] == "market-drawdown"
    assert body["section_heading"] == "核心判断"
    assert body["action"] == "soften"
    assert "风险偏好仍需观察" in body["rewritten_content"]
    assert body["model"] == "fake-model"


def test_commentary_quality_check_endpoint_returns_publish_gate_result():
    client = make_client()

    response = client.post(
        "/api/commentary/quality-check",
        json={
            "recipe_id": "market-drawdown",
            "draft_markdown": "# 市场大跌归因\n\n核心判断：海外 AI 链调整确定导致市场下跌。",
            "data_snapshot_text": "宽基指数：上证指数 -2.10%。",
            "evidence_pack_text": "媒体报道：海外 AI 链调整。",
            "subjective_judgement": "核心是风险偏好回落。",
            "evidence_items": [],
            "attribution_signals": [],
            "writing_preferences": {"audience": "client"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["summary"]["blocked"] == 1
    assert body["issues"][0]["code"] == "missing_risk_disclosure"


def test_commentary_runs_endpoint_records_and_lists_generation_runs():
    client = make_client()

    response = client.post(
        "/api/commentary/runs",
        json={
            "recipe_id": "market-drawdown",
            "recipe_title": "市场大跌归因",
            "draft_markdown": "# 市场大跌归因",
            "model": "deepseek-test",
            "provider": "fake-provider",
            "warnings": ["llm_returned_empty"],
            "evidence_count": 8,
            "selected_evidence_count": 5,
            "quality_status": "blocked",
            "quality_summary": {"blocked": 1, "warning": 0, "info": 0},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "commentary-test-run"
    assert body["record"]["recipe_title"] == "市场大跌归因"
    assert body["record"]["selected_evidence_count"] == 5

    list_response = client.get("/api/commentary/runs?limit=5")

    assert list_response.status_code == 200
    runs = list_response.json()
    assert runs[0]["run_id"] == "commentary-test-run"
