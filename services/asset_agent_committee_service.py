"""Asset-level Agent committee analysis service."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol

from cognitive_agents import AgentView, AgentWorkflow, AgentWorkflowRunner, AgentWorkflowStage
from cognitive_agents.agents.base import AgentContext
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentRole, AgentWorkflowResult, EvidenceBundle, EvidenceItem
from core.contracts import AssetAnalysisCard
from core.observability import get_logger

logger = get_logger(__name__)


class AssetAnalysisCardService(Protocol):
    """Protocol for the asset service method needed by the committee."""

    async def generate_analysis_card(
        self,
        canonical_id: str,
        as_of: datetime | None = None,
        use_mock: bool | None = None,
        source: str | None = None,
        time_range: str | None = None,
    ) -> AssetAnalysisCard:
        """Generate an asset analysis card."""


class OfficialEvidenceProvider(Protocol):
    """Protocol for retrieving official evidence items for an asset."""

    def find_for_asset(
        self,
        canonical_id: str,
        asset_name: str | None = None,
        limit: int = 5,
    ) -> list[EvidenceItem]:
        """Find official evidence items for one asset."""


class AssetAgentCommitteeService:
    """Run a minimal asset committee workflow from existing asset-analysis data."""

    def __init__(
        self,
        asset_service: AssetAnalysisCardService,
        official_evidence_provider: OfficialEvidenceProvider | None = None,
    ):
        self.asset_service = asset_service
        self.official_evidence_provider = official_evidence_provider

    async def analyze(
        self,
        canonical_id: str,
        question: str,
        *,
        event_id: str | None = None,
        as_of: datetime | None = None,
        time_range: str | None = None,
    ) -> AgentWorkflowResult:
        """Generate an asset analysis card and synthesize macro/fundamental/technical views."""
        logger.info(
            "running asset agent committee",
            canonical_id=canonical_id,
            event_id=event_id,
            time_range=time_range,
        )
        try:
            card = await self.asset_service.generate_analysis_card(
                canonical_id=canonical_id,
                as_of=as_of,
                time_range=time_range,
            )
            official_evidence = self._load_official_evidence(canonical_id, card)
            evidence_bundle = _build_evidence_bundle(
                card,
                question,
                event_id,
                official_evidence_items=official_evidence,
            )
            workflow = AgentWorkflow(
                workflow_id="workflow_asset_committee_v1",
                target_id=canonical_id,
                event_id=event_id,
                question=question,
                stages=[
                    AgentWorkflowStage(
                        stage_id="asset_research",
                        label="资产多维分析",
                        agent_roles=["macro", "fundamental", "technical"],
                        policy="parallel",
                        requires_prior_views=False,
                        synthesis_after_stage=True,
                    )
                ],
                metadata={"source": "asset_analysis_card", "version": "v1"},
            )
            context = AgentContext(
                target_id=canonical_id,
                event_id=event_id,
                question=question,
                evidence_bundle=evidence_bundle,
                market_data=evidence_bundle.market_snapshot,
            )
            runner = AgentWorkflowRunner(agent_factory=_AssetCommitteeAgentFactory(card))
            result = await runner.run(workflow, context, CognitiveBlackboard())
            if result.synthesis is not None:
                result.synthesis.metadata["official_evidence_count"] = len(official_evidence)
            return result
        except Exception as exc:
            logger.error(
                "asset agent committee failed",
                canonical_id=canonical_id,
                event_id=event_id,
                error=str(exc),
                exc_info=True,
            )
            raise

    def _load_official_evidence(
        self,
        canonical_id: str,
        card: AssetAnalysisCard,
    ) -> list[EvidenceItem]:
        if self.official_evidence_provider is None:
            return []
        asset_name = getattr(card.basic_info, "name", None) if card.basic_info is not None else None
        try:
            return self.official_evidence_provider.find_for_asset(
                canonical_id,
                asset_name=asset_name,
                limit=5,
            )
        except Exception as exc:
            logger.error(
                "asset_committee_official_evidence_failed",
                canonical_id=canonical_id,
                asset_name=asset_name,
                error=str(exc),
                exc_info=True,
            )
            return []


class _AssetCommitteeAgentFactory:
    """Factory adapter for deterministic asset committee agents."""

    def __init__(self, card: AssetAnalysisCard):
        self._card = card

    def create(self, role: AgentRole) -> "_DeterministicAssetAgent":
        if role not in {"macro", "fundamental", "technical"}:
            raise ValueError(f"Unsupported asset committee role: {role}")
        return _DeterministicAssetAgent(role=role, card=self._card)


class _DeterministicAssetAgent:
    """Small rule-based Agent used until full LLM SOP agents are wired into the API."""

    def __init__(self, role: AgentRole, card: AssetAnalysisCard):
        self.agent_role = role
        self.agent_name = f"{role}_asset_agent"
        self._card = card

    async def analyze(self, context: AgentContext) -> AgentView:
        bundle = context.get_evidence_bundle()
        if self.agent_role == "fundamental":
            return self._fundamental_view(context, bundle)
        if self.agent_role == "technical":
            return self._technical_view(context, bundle)
        if self.agent_role == "macro":
            return self._macro_view(context, bundle)
        raise ValueError(f"Unsupported deterministic asset agent role: {self.agent_role}")

    def _fundamental_view(self, context: AgentContext, bundle: EvidenceBundle) -> AgentView:
        financial = self._card.financial
        industry = self._card.industry
        positive: list[str] = []
        negative: list[str] = []

        roe = _to_float(getattr(financial, "roe", None))
        pe_ttm = _to_float(getattr(financial, "pe_ttm", None))
        industry_pe = _to_float(getattr(industry, "industry_pe", None))
        net_profit = _to_float(getattr(financial, "net_profit", None))
        gross_margin = _to_float(getattr(financial, "gross_margin", None))

        if roe is not None and roe >= 12:
            positive.append(f"ROE {roe:.1f}% 显示盈利质量较好")
        elif roe is not None and roe < 6:
            negative.append(f"ROE {roe:.1f}% 偏弱")
        if net_profit is not None and net_profit > 0:
            positive.append("净利润为正，基本面未见明显亏损压力")
        elif net_profit is not None and net_profit <= 0:
            negative.append("净利润非正，盈利质量需要警惕")
        if pe_ttm is not None and industry_pe is not None:
            if pe_ttm < industry_pe:
                positive.append(f"PE {pe_ttm:.1f} 低于行业 {industry_pe:.1f}")
            elif pe_ttm > industry_pe * 1.5:
                negative.append(f"PE {pe_ttm:.1f} 显著高于行业 {industry_pe:.1f}")
        if gross_margin is not None and gross_margin >= 30:
            positive.append(f"毛利率 {gross_margin:.1f}% 提供安全垫")

        view, confidence = _score_direction(positive, negative)
        return self._view(
            context,
            view=view,
            confidence=confidence,
            thesis=_thesis("基本面", view, positive, negative),
            reasoning=positive + negative or ["可用财务证据不足，暂维持中性"],
            assumptions=["财务摘要字段可代表近期基本面状态"],
            risks=["估值口径与行业估值口径可能不完全一致"],
            invalidation_triggers=["后续财报显示盈利质量恶化", "行业估值中枢快速下移"],
            recommended_next_checks=["核对最新定期报告与巨潮公告", "比较同业估值和盈利增速"],
            evidence_refs=bundle.evidence_ref_ids(),
            evaluation={
                "positive_signals": float(len(positive)),
                "negative_signals": float(len(negative)),
            },
        )

    def _technical_view(self, context: AgentContext, bundle: EvidenceBundle) -> AgentView:
        positive: list[str] = []
        negative: list[str] = []
        latest = self._card.price_bars[-1] if self._card.price_bars else None
        price_change_pct = _to_float(self._card.price_change_pct)
        capital_flow = self._card.capital_flow
        main_net = _to_float(getattr(capital_flow, "main_net", None))

        if latest is not None:
            close = _to_float(latest.close)
            ma20 = _to_float(latest.ma20)
            ma60 = _to_float(latest.ma60)
            macd_hist = _to_float(latest.macd_hist)
            if close is not None and ma20 is not None:
                if close > ma20:
                    positive.append("收盘价站上 20 日均线")
                else:
                    negative.append("收盘价低于 20 日均线")
            if ma20 is not None and ma60 is not None:
                if ma20 > ma60:
                    positive.append("20 日均线位于 60 日均线上方")
                else:
                    negative.append("20 日均线低于 60 日均线")
            if macd_hist is not None:
                if macd_hist > 0:
                    positive.append("MACD 柱为正")
                elif macd_hist < 0:
                    negative.append("MACD 柱为负")
        if price_change_pct is not None:
            if price_change_pct > 0:
                positive.append(f"近期涨跌幅 {price_change_pct:.2f}% 为正")
            elif price_change_pct < 0:
                negative.append(f"近期涨跌幅 {price_change_pct:.2f}% 为负")
        if main_net is not None:
            if main_net > 0:
                positive.append("主力资金净流入")
            elif main_net < 0:
                negative.append("主力资金净流出")

        view, confidence = _score_direction(positive, negative)
        return self._view(
            context,
            view=view,
            confidence=confidence,
            thesis=_thesis("技术面", view, positive, negative),
            reasoning=positive + negative or ["缺少足够 K 线和资金流证据，暂维持中性"],
            assumptions=["价格、均线与资金流字段已按当前时间范围计算"],
            risks=["短期技术信号容易受流动性和市场风格扰动"],
            invalidation_triggers=["跌破关键均线且主力资金转为净流出"],
            recommended_next_checks=["查看成交量是否同步放大", "复核筹码峰与压力位"],
            evidence_refs=bundle.evidence_ref_ids(),
            evaluation={
                "positive_signals": float(len(positive)),
                "negative_signals": float(len(negative)),
            },
        )

    def _macro_view(self, context: AgentContext, bundle: EvidenceBundle) -> AgentView:
        macro = self._card.macro_sensitivity
        industry = self._card.industry
        positive: list[str] = []
        negative: list[str] = []

        liquidity = _to_float(getattr(macro, "liquidity_sensitivity", None))
        rate = _to_float(getattr(macro, "interest_rate_sensitivity", None))
        heat = _to_float(getattr(industry, "industry_heat", None))
        factors = list(getattr(macro, "key_macro_factors", []) or [])

        if liquidity is not None:
            if liquidity > 0.3:
                positive.append("对流动性改善较敏感")
            elif liquidity < -0.3:
                negative.append("流动性改善可能带来负向影响")
        if rate is not None:
            if rate < -0.3:
                negative.append("对利率上行较敏感")
            elif rate > 0.3:
                positive.append("利率敏感度偏正")
        if heat is not None:
            if heat >= 0.6:
                positive.append("行业热度处于较高水平")
            elif heat <= 0.3:
                negative.append("行业热度偏低")
        if factors:
            positive.append("已识别关键宏观因子: " + "、".join(factors[:3]))

        view, confidence = _score_direction(positive, negative)
        return self._view(
            context,
            view=view,
            confidence=confidence,
            thesis=_thesis("宏观", view, positive, negative),
            reasoning=positive + negative or ["缺少宏观敏感性数据，暂维持中性"],
            assumptions=["宏观敏感性字段能反映标的对主要宏观变量的暴露"],
            risks=["宏观变量方向变化可能快速改变结论"],
            invalidation_triggers=["流动性或行业景气拐头向下", "利率和汇率冲击超出历史区间"],
            recommended_next_checks=["跟踪流动性指标与行业景气数据", "补充政策与宏观事件证据"],
            evidence_refs=bundle.evidence_ref_ids(),
            evaluation={
                "positive_signals": float(len(positive)),
                "negative_signals": float(len(negative)),
            },
        )

    def _view(
        self,
        context: AgentContext,
        *,
        view: str,
        confidence: float,
        thesis: str,
        reasoning: list[str],
        assumptions: list[str],
        risks: list[str],
        invalidation_triggers: list[str],
        recommended_next_checks: list[str],
        evidence_refs: list[str],
        evaluation: dict[str, float],
    ) -> AgentView:
        return AgentView(
            view_id=f"view_{self.agent_role}_{uuid.uuid4().hex[:12]}",
            agent_name=self.agent_name,
            agent_role=self.agent_role,
            target_id=context.target_id,
            event_id=context.event_id,
            view=view,
            thesis=thesis,
            confidence=confidence,
            reasoning=reasoning,
            assumptions=assumptions,
            risks=risks,
            invalidation_triggers=invalidation_triggers,
            recommended_next_checks=recommended_next_checks,
            evidence_refs=evidence_refs,
            evaluation=evaluation,
            metadata={"mode": "deterministic_asset_committee"},
        )


def _build_evidence_bundle(
    card: AssetAnalysisCard,
    question: str,
    event_id: str | None,
    official_evidence_items: list[EvidenceItem] | None = None,
) -> EvidenceBundle:
    evidence_items = [
        EvidenceItem(
            evidence_id="asset_financial_summary",
            ref_id="asset_financial_summary",
            ref_type="market_data",
            evidence_kind="structured",
            source_type="asset_analysis_card",
            source_name="AssetAnalysisService",
            title="财务与估值摘要",
            summary=str(_safe_dump(card.financial))[:600],
            reliability=0.7,
            relevance=0.8,
            payload=_safe_dump(card.financial),
        ),
        EvidenceItem(
            evidence_id="asset_technical_snapshot",
            ref_id="asset_technical_snapshot",
            ref_type="market_data",
            evidence_kind="market_reaction",
            source_type="asset_analysis_card",
            source_name="AssetAnalysisService",
            title="量价与资金流摘要",
            summary=str(
                {
                    "price_change_pct": card.price_change_pct,
                    "capital_flow": _safe_dump(card.capital_flow),
                    "latest_bar": _safe_dump(card.price_bars[-1]) if card.price_bars else {},
                }
            )[:600],
            reliability=0.7,
            relevance=0.8,
            payload={"price_bars": [_safe_dump(bar) for bar in card.price_bars[-5:]]},
        ),
        EvidenceItem(
            evidence_id="asset_macro_industry_snapshot",
            ref_id="asset_macro_industry_snapshot",
            ref_type="market_data",
            evidence_kind="structured",
            source_type="asset_analysis_card",
            source_name="AssetAnalysisService",
            title="宏观与行业摘要",
            summary=str(
                {
                    "macro_sensitivity": _safe_dump(card.macro_sensitivity),
                    "industry": _safe_dump(card.industry),
                }
            )[:600],
            reliability=0.65,
            relevance=0.75,
            payload={
                "macro_sensitivity": _safe_dump(card.macro_sensitivity),
                "industry": _safe_dump(card.industry),
            },
        ),
    ]
    for ref in card.evidence_refs:
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"asset_ref_{ref}",
                ref_id=ref,
                ref_type="source_document",
                evidence_kind="other",
                source_type="asset_analysis_card",
                title="资产分析卡外部证据引用",
                summary=ref,
                reliability=0.5,
                relevance=0.6,
            )
        )
    official_evidence_items = official_evidence_items or []
    evidence_items.extend(official_evidence_items)

    return EvidenceBundle(
        target_id=card.canonical_id,
        event_id=event_id,
        question=question,
        as_of=card.as_of,
        evidence_items=evidence_items,
        market_snapshot={
            "current_price": card.current_price,
            "price_change_pct": card.price_change_pct,
            "volume": card.volume,
            "amount": card.amount,
            "turnover": card.turnover,
        },
        metadata={
            "source": "asset_analysis_card",
            "as_of": card.as_of.isoformat(),
            "official_evidence_count": len(official_evidence_items),
        },
    )


def _score_direction(positive: list[str], negative: list[str]) -> tuple[str, float]:
    score = len(positive) - len(negative)
    total = max(len(positive) + len(negative), 1)
    if score >= 2:
        return "bullish", min(0.85, 0.5 + abs(score) / (total + 3))
    if score <= -2:
        return "bearish", min(0.85, 0.5 + abs(score) / (total + 3))
    if score == 0 and len(positive) > 0 and len(negative) > 0:
        return "mixed", 0.55
    if score > 0:
        return "bullish", 0.58
    if score < 0:
        return "bearish", 0.58
    return "neutral", 0.45


def _thesis(prefix: str, view: str, positive: list[str], negative: list[str]) -> str:
    leading = positive if view == "bullish" else negative
    if leading:
        return f"{prefix}观点偏{_view_label(view)}：{leading[0]}"
    return f"{prefix}证据不足，暂维持{_view_label(view)}"


def _view_label(view: str) -> str:
    return {
        "bullish": "积极",
        "bearish": "谨慎",
        "neutral": "中性",
        "mixed": "分歧",
        "unknown": "未知",
    }.get(view, view)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_dump(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": value}
