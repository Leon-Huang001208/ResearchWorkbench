"""
Core contracts for portfolio construction and risk budgeting.

This module defines Pydantic models for converting multiple concurrent signals
into a consistent investment portfolio, translating scored signals into ranked
allocations under explicit constraints in AlphaFoundry.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioCandidate(BaseModel):
    """组合候选 — 来自单个信号的配置建议.

    Represents a portfolio candidate from a single signal, including signal ID,
    subject ID, event type, score, confidence, readiness, timing action,
    suggested weight, historical stats, sector, and theme.

    Attributes:
        signal_id: Unique identifier of the associated signal.
        subject_id: Canonical ID of the subject asset/entity.
        event_type: Type of event that generated this candidate.
        signal_score: Score of the signal.
        signal_confidence: Confidence of the signal (0.0 to 1.0).
        readiness: Readiness status from timing (if applicable).
        timing_action: Timing action recommended (if applicable).
        suggested_weight: Suggested initial weight (default 0.0).
        historical_hit_rate: Historical hit rate from outcomes (if available).
        historical_avg_excess_return: Historical average excess return (if available).
        sector: Sector label for concentration constraints (if available).
        theme: Theme label for concentration constraints (if available).
    """

    signal_id: str = Field(description="Unique identifier of the associated signal")
    subject_id: str = Field(description="Canonical ID of the subject asset/entity")
    event_type: str = Field(description="Type of event that generated this candidate")
    signal_score: float = Field(description="Score of the signal")
    signal_confidence: float = Field(description="Confidence of the signal (0.0 to 1.0)")
    readiness: Optional[str] = Field(default=None, description="Readiness status from timing (if applicable)")
    timing_action: Optional[str] = Field(default=None, description="Timing action recommended (if applicable)")
    suggested_weight: float = Field(default=0.0, description="Suggested initial weight")
    historical_hit_rate: Optional[float] = Field(default=None, description="Historical hit rate from outcomes (if available)")
    historical_avg_excess_return: Optional[float] = Field(default=None, description="Historical average excess return (if available)")
    sector: Optional[str] = Field(default=None, description="Sector label for concentration constraints (if available)")
    theme: Optional[str] = Field(default=None, description="Theme label for concentration constraints (if available)")


class PortfolioConstraints(BaseModel):
    """组合约束.

    Defines constraints for portfolio construction, including position size,
    sector/theme concentration, candidate count, correlation threshold,
    minimum signal score/confidence, and regime exposure limits.

    Attributes:
        max_position_size: Maximum weight for a single position (default 0.15).
        max_sector_concentration: Maximum sector concentration (default 0.40).
        max_theme_concentration: Maximum theme concentration (default 0.30).
        min_candidates: Minimum number of candidates (default 3).
        max_candidates: Maximum number of candidates (default 20).
        correlation_threshold: Correlation threshold for deduplication (default 0.7).
        min_signal_score: Minimum signal score (default 0.3).
        min_confidence: Minimum confidence (default 0.3).
        regime_exposure_limit: Optional market regime exposure limits (dict).
    """

    max_position_size: float = Field(default=0.15, description="Maximum weight for a single position")
    max_sector_concentration: float = Field(default=0.40, description="Maximum sector concentration")
    max_theme_concentration: float = Field(default=0.30, description="Maximum theme concentration")
    min_candidates: int = Field(default=3, description="Minimum number of candidates")
    max_candidates: int = Field(default=20, description="Maximum number of candidates")
    correlation_threshold: float = Field(default=0.7, description="Correlation threshold for deduplication")
    min_signal_score: float = Field(default=0.3, description="Minimum signal score")
    min_confidence: float = Field(default=0.3, description="Minimum confidence")
    regime_exposure_limit: Optional[Dict[str, float]] = Field(default=None, description="Optional market regime exposure limits (dict)")


class PortfolioProposal(BaseModel):
    """组合提案 — 多信号约束后的最终配置.

    Represents the final portfolio proposal after applying constraints to
    multiple signals, including proposal ID, name, creation time, candidates,
    allocations, applied constraints, excluded signals, and rationale.

    Attributes:
        proposal_id: Unique identifier for the proposal.
        name: Name of the portfolio proposal.
        created_at: Timestamp when the proposal was created.
        candidates: List of portfolio candidates included.
        allocations: Dictionary mapping subject IDs to weights.
        constraints_applied: List of constraints that were applied.
        excluded_signals: List of excluded signals and reasons.
        rationale: Dictionary with decision rationale.
    """

    proposal_id: str = Field(description="Unique identifier for the proposal")
    name: str = Field(description="Name of the portfolio proposal")
    created_at: datetime = Field(description="Timestamp when the proposal was created")
    candidates: List[PortfolioCandidate] = Field(description="List of portfolio candidates included")
    allocations: Dict[str, float] = Field(description="Dictionary mapping subject IDs to weights")
    constraints_applied: List[str] = Field(description="List of constraints that were applied")
    excluded_signals: List[Dict[str, Any]] = Field(description="List of excluded signals and reasons")
    rationale: Dict[str, Any] = Field(description="Dictionary with decision rationale")
