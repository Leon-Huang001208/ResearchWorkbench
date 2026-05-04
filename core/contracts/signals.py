from typing import Literal

from pydantic import BaseModel, Field


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


class TradeCandidate(BaseModel):
    """交易候选 - 从信号转化的具体交易建议"""

    candidate_id: str
    signal_id: str
    action: Literal["long", "short", "neutral"]
    sizing_hint: float
    risk_notes: list[str] = Field(default_factory=list)
