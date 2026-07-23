"""Tests for deterministic asset Agent committee service."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from cognitive_agents import EvidenceItem
from core.contracts import (
    AssetAnalysisCard,
    AssetBasicInfo,
    CapitalFlow,
    FinancialSummary,
    IndustryData,
    MacroSensitivity,
    PriceBar,
)
from services.asset_agent_committee_service import AssetAgentCommitteeService


def _sample_card() -> AssetAnalysisCard:
    return AssetAnalysisCard(
        canonical_id="300308.SZ",
        as_of=datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC),
        basic_info=AssetBasicInfo(symbol="300308.SZ", name="中际旭创"),
        current_price=120.0,
        price_change_pct=3.2,
        financial=FinancialSummary(
            revenue=10_000_000_000,
            net_profit=1_500_000_000,
            roe=18.5,
            gross_margin=42.0,
            pe_ttm=28.0,
            pb_mrq=4.2,
        ),
        capital_flow=CapitalFlow(main_net=180_000_000),
        industry=IndustryData(sw_level_1="电子", industry_pe=42.0, industry_heat=0.72),
        macro_sensitivity=MacroSensitivity(
            liquidity_sensitivity=0.6,
            interest_rate_sensitivity=-0.2,
            key_macro_factors=["流动性", "AI算力周期"],
        ),
        price_bars=[
            PriceBar(
                date=date(2026, 6, 4),
                open=112.0,
                high=119.0,
                low=110.0,
                close=116.0,
                ma20=108.0,
                ma60=98.0,
                macd_hist=0.8,
            ),
            PriceBar(
                date=date(2026, 6, 5),
                open=116.0,
                high=122.0,
                low=115.0,
                close=120.0,
                ma20=110.0,
                ma60=99.0,
                macd_hist=1.1,
            ),
        ],
        evidence_refs=["doc_001"],
    )


@pytest.mark.asyncio
async def test_asset_agent_committee_service_runs_workflow_and_synthesizes():
    asset_service = Mock()
    asset_service.generate_analysis_card = AsyncMock(return_value=_sample_card())
    service = AssetAgentCommitteeService(asset_service)

    result = await service.analyze(
        canonical_id="300308.SZ",
        question="这个标的是否值得进入研究池？",
        time_range="1Y",
    )

    assert result.workflow_id == "workflow_asset_committee_v1"
    assert len(result.views) == 3
    assert {view.agent_role for view in result.views} == {"macro", "fundamental", "technical"}
    assert result.synthesis is not None
    assert result.synthesis.target_id == "300308.SZ"
    assert result.synthesis.final_view in {"bullish", "mixed"}
    assert result.synthesis.metadata["view_count"] == 3
    asset_service.generate_analysis_card.assert_awaited_once_with(
        canonical_id="300308.SZ",
        as_of=None,
        time_range="1Y",
    )


class _FakeOfficialEvidenceProvider:
    def __init__(self):
        self.calls = []

    def find_for_asset(self, canonical_id: str, asset_name: str | None = None, limit: int = 5):
        self.calls.append({"canonical_id": canonical_id, "asset_name": asset_name, "limit": limit})
        return [
            EvidenceItem(
                evidence_id="official_doc_cninfo_001",
                ref_id="doc_cninfo_001",
                ref_type="source_document",
                evidence_kind="official",
                source_type="cninfo",
                source_name="巨潮资讯网",
                title="中际旭创：2025年年度报告",
                summary="公司实现营业收入100亿元。",
                reliability=0.95,
                relevance=0.9,
            )
        ]


@pytest.mark.asyncio
async def test_asset_agent_committee_adds_cninfo_official_evidence_to_views():
    asset_service = Mock()
    asset_service.generate_analysis_card = AsyncMock(return_value=_sample_card())
    official_provider = _FakeOfficialEvidenceProvider()
    service = AssetAgentCommitteeService(
        asset_service, official_evidence_provider=official_provider
    )

    result = await service.analyze(canonical_id="300308.SZ", question="是否进入研究池？")

    assert official_provider.calls == [
        {"canonical_id": "300308.SZ", "asset_name": "中际旭创", "limit": 5}
    ]
    assert all("doc_cninfo_001" in view.evidence_refs for view in result.views)
    assert result.synthesis is not None
    assert result.synthesis.metadata["official_evidence_count"] == 1
