"""
Core contracts for the outcome journal (trade outcome tracking and failure memory).

This module defines Pydantic models for structured outcome recording, failure
classification, similar case retrieval, and weekly review reports, supporting
the failure-memory engine in AlphaFoundry.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class FailureClassification(str, Enum):
    """Standard failure types for classification of unsuccessful trades."""

    wrong_thesis = "wrong_thesis"
    timing_error = "timing_error"
    crowding_error = "crowding_error"
    regime_misread = "regime_misread"
    mapping_error = "mapping_error"
    evidence_weakness = "evidence_weakness"
    execution_error = "execution_error"
    risk_error = "risk_error"


class TradeOutcome(BaseModel):
    """Complete trade outcome record with all required metrics and classification."""

    outcome_id: str = Field(description="Unique identifier for this outcome record")
    signal_id: str = Field(description="ID of the alpha signal associated with this trade")
    candidate_id: Optional[str] = Field(default=None, description="ID of the trade candidate")
    entry_time: datetime = Field(description="Entry execution time")
    exit_time: datetime = Field(description="Exit execution time")
    entry_price: float = Field(description="Entry price per share/unit")
    exit_price: float = Field(description="Exit price per share/unit")
    return_5d: Optional[float] = Field(default=None, description="5-day return after entry")
    return_20d: Optional[float] = Field(default=None, description="20-day return after entry")
    return_60d: Optional[float] = Field(default=None, description="60-day return after entry")
    benchmark_excess_return: float = Field(default=0.0, description="Excess return over benchmark")
    thesis_success: bool = Field(description="Whether the original thesis was correct")
    failure_classification: Optional[FailureClassification] = Field(
        default=None, description="Classification if thesis failed"
    )
    failure_notes: Optional[str] = Field(default=None, description="Additional notes on failure")
    thesis_text: str = Field(description="Original thesis text for similarity comparison")
    propagation_path: List[str] = Field(
        default_factory=list, description="Propagation path of the thesis"
    )
    market_regime: Optional[str] = Field(default=None, description="Market regime at time of trade")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Record creation time"
    )


class SimilarCase(BaseModel):
    """Similar historical case retrieved from outcome memory."""

    outcome_id: str = Field(description="ID of the historical outcome")
    similarity_score: float = Field(description="Similarity score (0-1) to current thesis")
    trade_outcome: TradeOutcome = Field(description="Full outcome record of the historical case")
    is_success: bool = Field(description="Whether the historical case was a success")


class WeeklyReviewReport(BaseModel):
    """Weekly review report aggregating outcomes and failure analysis."""

    report_id: str = Field(description="Unique report ID")
    week_start_date: datetime = Field(description="Start date of the review week")
    week_end_date: datetime = Field(description="End date of the review week")
    total_outcomes: int = Field(description="Total number of outcomes recorded this week")
    successful_outcomes: int = Field(description="Number of successful outcomes")
    failed_outcomes: int = Field(description="Number of failed outcomes")
    success_rate: float = Field(description="Percentage of successful outcomes")
    failure_distribution: dict[FailureClassification, int] = Field(
        description="Count of failures by classification"
    )
    top_lessons: List[str] = Field(
        default_factory=list, description="Key lessons learned this week"
    )
    most_common_failure: Optional[FailureClassification] = Field(
        default=None, description="Most frequent failure type this week"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Report generation time"
    )
