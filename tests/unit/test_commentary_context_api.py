from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.commentary import (
    get_commentary_context_service,
    get_commentary_draft_service,
    router,
)
from core.contracts.commentary import (
    CommentaryAttributionSignal,
    CommentaryContextPack,
    CommentaryDraftResponse,
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
            citations=[
                {"title": "上证指数 -2.10%", "kind": "confirmed", "source": "market_overview"}
            ],
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


def make_client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_commentary_context_service] = (
        lambda: FakeCommentaryContextService()
    )
    app.dependency_overrides[get_commentary_draft_service] = lambda: FakeCommentaryDraftService()
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


def test_main_app_registers_commentary_context_route():
    from app.api.main import app as main_app

    main_app.dependency_overrides[get_commentary_context_service] = (
        lambda: FakeCommentaryContextService()
    )
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
