from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
from timing_engine import TimingDecision


class AlphaSignal(BaseModel):
    """Alpha 信号 - 研究发现的交易信号"""

    signal_id: str
    subject_id: str
    horizon: Literal["1d", "5d", "20d", "60d"]
    thesis: str
    score: float
    confidence: float
    scenario_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    status: Literal["research_only", "candidate", "paper_trade"] = "research_only"


class EventAlphaSignal(AlphaSignal):
    """事件型 Alpha 信号 - 将 AI 事件理解转化为可验证的交易假设"""

    event_id: str
    event_type: str
    event_time: datetime | None = None
    impact_path: list[str] = Field(default_factory=list)
    industry_impacts: list[str] = Field(default_factory=list)
    bullish_companies: list[str] = Field(default_factory=list)
    bearish_companies: list[str] = Field(default_factory=list)
    diffusion_stage: Literal[
        "discovery",
        "early_awareness",
        "theme_trading",
        "institutional_coverage",
        "consensus",
        "decay",
        "unknown",
    ] = "unknown"
    market_regime: str | None = None
    validation_status: Literal[
        "pending_backtest",
        "validated",
        "rejected",
        "paper_trade",
    ] = "pending_backtest"
    validation_metrics: dict[str, float] = Field(default_factory=dict)
    timing_decision: Optional[TimingDecision] = None


class TradeCandidate(BaseModel):
    """交易候选 - 从信号转化的具体交易建议"""

    candidate_id: str
    signal_id: str
    action: Literal["long", "short", "neutral"]
    sizing_hint: float
    risk_notes: list[str] = Field(default_factory=list)
