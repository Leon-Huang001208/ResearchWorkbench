from core.contracts.commentary import (
    CommentaryAttributionSignal,
    CommentaryDraftRequest,
    CommentaryEvidenceItem,
)
from core.interfaces.model_gateway import ModelResponse
from services.commentary_draft_service import CommentaryDraftService


class FakeModelGateway:
    def __init__(self, fail=False, content=None):
        self.fail = fail
        self.content = content
        self.calls = []

    def chat(self, messages, model=None, temperature=0.7, max_tokens=None, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        if self.fail:
            raise RuntimeError("model unavailable")
        return ModelResponse(
            content=self.content
            or "# 市场大跌归因\n\n核心判断：市场调整来自风险偏好回落。\n\n后续观察成交额。",
            model_name="deepseek-test",
            provider="fake-provider",
            tokens_used=321,
            latency_ms=120,
        )


def _request():
    return CommentaryDraftRequest(
        recipe_id="market-drawdown",
        data_snapshot_text="宽基指数：上证指数 -2.10%，创业板指 -3.80%。",
        evidence_pack_text="已确认数据：上证指数 -2.10%。媒体报道：海外 AI 链调整。",
        subjective_judgement="核心是高拥挤交易降温，而不是单一利空。",
        evidence_items=[
            CommentaryEvidenceItem(
                kind="confirmed",
                title="上证指数 -2.10%",
                summary="指数行情来自市场总览。",
                source="market_overview",
                source_type="market_data",
                verification_status="verified",
                confidence_score=0.95,
                display_label="已确认数据",
            ),
            CommentaryEvidenceItem(
                kind="reported",
                title="海外 AI 链调整",
                summary="媒体报道软银和韩国半导体链下跌。",
                source="dashboard_news",
                source_type="news",
                verification_status="source_published",
                confidence_score=0.68,
                display_label="媒体报道/新闻",
            ),
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
            ),
            CommentaryAttributionSignal(
                rank=2,
                tag="liquidity_outflow",
                label="资金净流出放大",
                strength="secondary",
                score=72,
                confidence_score=0.9,
                verification_status="verified",
                rationale="市场广度较弱且资金净流出。",
                evidence_titles=["资金净流入 -420亿"],
            ),
        ],
    )


def test_commentary_draft_service_uses_model_gateway_when_available():
    gateway = FakeModelGateway()
    service = CommentaryDraftService(model_gateway=gateway)

    response = service.generate_draft(_request())

    assert "市场大跌归因" in response.draft_markdown
    assert response.model == "deepseek-test"
    assert response.provider == "fake-provider"
    assert response.tokens_used == 321
    assert response.citations[0]["title"] == "上证指数 -2.10%"
    assert gateway.calls[0]["model"] == "deepseek-v4-pro"
    assert gateway.calls[0]["kwargs"]["task"] == "reporting"
    assert "高拥挤交易降温" in gateway.calls[0]["messages"][1]["content"]


def test_commentary_draft_service_includes_verification_matrix_in_prompt_and_citations():
    gateway = FakeModelGateway()
    service = CommentaryDraftService(model_gateway=gateway)

    response = service.generate_draft(_request())

    prompt = gateway.calls[0]["messages"][1]["content"]
    assert "【结构化证据与核验状态】" in prompt
    assert "[已确认数据][market_data][verified][0.95] 上证指数 -2.10%" in prompt
    assert "[媒体报道/新闻][news][source_published][0.68] 海外 AI 链调整" in prompt
    assert "对 verification_status 不是 verified 的证据，必须使用“据报道/显示/需要继续核验”等表述" in prompt
    assert response.citations[0]["verification_status"] == "verified"
    assert response.citations[1]["confidence_score"] == 0.68


def test_commentary_draft_service_includes_attribution_ranking_in_prompt_and_response():
    gateway = FakeModelGateway()
    service = CommentaryDraftService(model_gateway=gateway)

    response = service.generate_draft(_request())

    prompt = gateway.calls[0]["messages"][1]["content"]
    assert "【归因排序】" in prompt
    assert "[1][primary][86] AI拥挤交易降温" in prompt
    assert "写作时按归因排序区分主因、次因和待核验因素" in prompt
    assert response.attribution_signals[0]["tag"] == "ai_crowding"
    assert response.attribution_signals[0]["strength"] == "primary"


def test_commentary_draft_service_balances_citations_between_market_data_and_news():
    request = _request()
    request.evidence_items = [
        CommentaryEvidenceItem(
            kind="confirmed",
            title=f"行业数据 {idx}",
            summary="行情快照。",
            source="market",
            source_type="market_data",
            verification_status="verified",
            confidence_score=0.9,
            display_label="已确认数据",
        )
        for idx in range(12)
    ] + [
        CommentaryEvidenceItem(
            kind="reported",
            title="日经225指数日内重挫5%",
            summary="财联社报道软银和芯片股下跌。",
            source="cls",
            source_type="news",
            verification_status="source_published",
            confidence_score=0.48,
            display_label="媒体报道/新闻",
        )
    ]
    service = CommentaryDraftService(model_gateway=FakeModelGateway())

    response = service.generate_draft(request)

    assert any(item["source_type"] == "market_data" for item in response.citations[:6])
    assert any(item["source_type"] == "news" for item in response.citations[:6])


def test_commentary_draft_service_returns_fallback_when_model_fails():
    gateway = FakeModelGateway(fail=True)
    service = CommentaryDraftService(model_gateway=gateway)

    response = service.generate_draft(_request())

    assert "市场大跌归因" in response.draft_markdown
    assert "宽基指数" in response.draft_markdown
    assert response.model == "rule_based_fallback"
    assert response.provider == "local"
    assert response.warnings
    assert response.warnings[0].startswith("llm_failed")


def test_commentary_draft_service_treats_provider_error_text_as_failure():
    gateway = FakeModelGateway(content="Error: invalid model")
    service = CommentaryDraftService(model_gateway=gateway)

    response = service.generate_draft(_request())

    assert response.model == "rule_based_fallback"
    assert response.provider == "local"
    assert response.warnings == ["llm_returned_error_text"]
    assert "宽基指数" in response.draft_markdown
