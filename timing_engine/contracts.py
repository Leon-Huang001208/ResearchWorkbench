"""Timing Engine 契约。"""
from typing import Literal

from pydantic import BaseModel, Field


TimingModelName = Literal[
    "regime",
    "flow",
    "theme_diffusion",
    "sentiment",
    "market_structure",
    "liquidity",
    "crowding",
    "expectation_gap",
    "alpha_decay",
]

MarketRegime = Literal[
    "ai_growth",
    "dividend_defensive",
    "risk_off",
    "hot_money_theme",
    "institutional_trend",
    "liquidity_bull",
    "bear_rebound",
    "unknown",
]

TimingAction = Literal["enter", "wait", "reduce", "exit", "block"]


class TimingModelScore(BaseModel):
    """单个择时模型的评分。

    score 表示该模型对“现在能否交易”的支持度。对 crowding / alpha_decay
    这类风险模型，score 越高表示风险越高，MetaTimingEngine 会反向处理。
    """

    model_name: TimingModelName
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    horizon: Literal["intraday", "1d", "5d", "20d", "60d"] = "20d"
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class TimingDecision(BaseModel):
    """Meta Timing System 的最终择时决策。"""

    decision_id: str | None = None
    action: TimingAction
    readiness_score: float = Field(ge=0.0, le=1.0)
    signal_id: str | None = None
    market_regime: MarketRegime = "unknown"
    model_scores: list[TimingModelScore] = Field(default_factory=list)
    active_weights: dict[str, float] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
