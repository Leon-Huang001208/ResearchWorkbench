"""
Core contracts for alpha signals, event alpha signals, and trade candidates.

This module defines Pydantic models for alpha signals, event-driven alpha signals,
and trade candidates in Research Workbench.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from timing_engine import TimingDecision


class AlphaSignal(BaseModel):
    """Alpha 信号 - 研究发现的交易信号.

    Represents an alpha signal from research, including signal ID, subject ID,
    horizon, thesis, score, confidence, scenario/evidence references, and status.

    Attributes:
        signal_id: Unique identifier for the signal.
        subject_id: Canonical ID of the subject asset/entity.
        horizon: Time horizon ("1d", "5d", "20d", "60d").
        thesis: Investment thesis for the signal.
        score: Score of the signal.
        confidence: Confidence of the signal (0.0 to 1.0).
        scenario_refs: List of scenario references.
        evidence_refs: List of evidence references.
        status: Status of the signal (research_only, candidate, paper_trade) (default "research_only").
    """

    signal_id: str = Field(description="Unique identifier for the signal")
    subject_id: str = Field(description="Canonical ID of the subject asset/entity")
    horizon: Literal["1d", "5d", "20d", "60d"] = Field(
        description="Time horizon (1d, 5d, 20d, 60d)"
    )
    thesis: str = Field(description="Investment thesis for the signal")
    score: float = Field(description="Score of the signal")
    confidence: float = Field(description="Confidence of the signal (0.0 to 1.0)")
    scenario_refs: list[str] = Field(
        default_factory=list, description="List of scenario references"
    )
    evidence_refs: list[str] = Field(
        default_factory=list, description="List of evidence references"
    )
    status: Literal["research_only", "candidate", "paper_trade"] = Field(
        default="research_only",
        description="Status of the signal (research_only, candidate, paper_trade)",
    )
    metadata: dict = Field(default_factory=dict, description="Extensible metadata (trace_id, etc.)")


class EventAlphaSignal(AlphaSignal):
    """事件型 Alpha 信号 - 将 AI 事件理解转化为可验证的交易假设.

    Extends AlphaSignal with event-specific fields, including event ID, type,
    time, impact path, industry impacts, bullish/bearish companies, diffusion stage,
    market regime, validation status/metrics, and timing decision.

    Attributes:
        event_id: Unique identifier for the event.
        event_type: Type of the event.
        event_time: Time of the event (if available).
        impact_path: List of steps in the impact propagation path.
        industry_impacts: List of impacted industries.
        bullish_companies: List of bullish companies from the event.
        bearish_companies: List of bearish companies from the event.
        diffusion_stage: Diffusion stage of the event (discovery, early_awareness, theme_trading, institutional_coverage, consensus, decay, unknown) (default "unknown").
        market_regime: Market regime at the time of the event (if available).
        validation_status: Validation status (pending_backtest, validated, rejected, paper_trade) (default "pending_backtest").
        validation_metrics: Dictionary with validation metrics.
        timing_decision: Optional timing decision from the timing engine.
    """

    event_id: str = Field(description="Unique identifier for the event")
    event_type: str = Field(description="Type of the event")
    event_time: datetime | None = Field(
        default=None, description="Time of the event (if available)"
    )
    impact_path: list[str] = Field(
        default_factory=list, description="List of steps in the impact propagation path"
    )
    industry_impacts: list[str] = Field(
        default_factory=list, description="List of impacted industries"
    )
    bullish_companies: list[str] = Field(
        default_factory=list, description="List of bullish companies from the event"
    )
    bearish_companies: list[str] = Field(
        default_factory=list, description="List of bearish companies from the event"
    )
    diffusion_stage: Literal[
        "discovery",
        "early_awareness",
        "theme_trading",
        "institutional_coverage",
        "consensus",
        "decay",
        "unknown",
    ] = Field(
        default="unknown",
        description="Diffusion stage of the event (discovery, early_awareness, theme_trading, institutional_coverage, consensus, decay, unknown)",
    )
    market_regime: str | None = Field(
        default=None, description="Market regime at the time of the event (if available)"
    )
    validation_status: Literal[
        "pending_backtest",
        "validated",
        "rejected",
        "paper_trade",
    ] = Field(
        default="pending_backtest",
        description="Validation status (pending_backtest, validated, rejected, paper_trade)",
    )
    validation_metrics: dict[str, float] = Field(
        default_factory=dict, description="Dictionary with validation metrics"
    )
    timing_decision: Optional[TimingDecision] = Field(
        default=None, description="Optional timing decision from the timing engine"
    )


class TradeCandidate(BaseModel):
    """交易候选 - 从信号转化的具体交易建议.

    Represents a trade candidate derived from a signal, including candidate ID,
    signal ID, action, sizing hint, and risk notes.

    Attributes:
        candidate_id: Unique identifier for the trade candidate.
        signal_id: Unique identifier of the associated signal.
        action: Action to take (long, short, neutral).
        sizing_hint: Sizing hint (e.g., target weight).
        risk_notes: List of risk-related notes.
    """

    candidate_id: str = Field(description="Unique identifier for the trade candidate")
    signal_id: str = Field(description="Unique identifier of the associated signal")
    action: Literal["long", "short", "neutral"] = Field(
        description="Action to take (long, short, neutral)"
    )
    sizing_hint: float = Field(description="Sizing hint (e.g., target weight)")
    risk_notes: list[str] = Field(default_factory=list, description="List of risk-related notes")
