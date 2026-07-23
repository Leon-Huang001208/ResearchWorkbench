"""
Core contracts for event signal outcome evaluation.

This module defines Pydantic models for evaluating signal outcomes (success,
failure, decay, lessons), providing a consistent evaluation standard for the
Memory & Learning layer in AlphaFoundry.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.contracts.timing_types import OutcomeHorizon, TimingAction


class SignalOutcome(BaseModel):
    """事件信号结果评估协议.

        Each SignalOutcome records the actual performance of a signal within a
    specified time window, serving as a structured evaluation supplement to
        MarketEpisode.

        Attributes:
            outcome_id: Unique identifier for the outcome record.
            event_id: Unique identifier of the associated event.
            signal_id: Unique identifier of the associated signal.
            subject_id: Canonical ID of the subject asset/entity.
            event_date: Date of the event.
            timing_action: Timing action taken (default "wait").
            entry_rule: Optional entry rule used (if applicable).
            horizon: Outcome horizon (e.g., "20d") (default "20d").
            benchmark: Optional benchmark used for excess return calculation.
            outcome_return: Return of the outcome (default 0.0).
            outcome_excess_return: Excess return over the benchmark (default 0.0).
            max_drawdown: Maximum drawdown experienced (default 0.0).
            decay: Decay score (default 0.0).
            failure_reason: Optional reason for failure (if applicable).
            lesson: Optional lesson learned (if applicable).
            evaluated_at: Timestamp when the outcome was evaluated (if applicable).
            metadata: Additional metadata as a dictionary of strings.
    """

    outcome_id: str = Field(description="Unique identifier for the outcome record")
    event_id: str = Field(description="Unique identifier of the associated event")
    signal_id: str = Field(description="Unique identifier of the associated signal")
    subject_id: str = Field(description="Canonical ID of the subject asset/entity")
    event_date: datetime = Field(description="Date of the event")
    timing_action: TimingAction = Field(default="wait", description="Timing action taken")
    entry_rule: Optional[str] = Field(
        default=None, description="Optional entry rule used (if applicable)"
    )
    horizon: OutcomeHorizon = Field(default="20d", description="Outcome horizon (e.g., 20d)")
    benchmark: Optional[str] = Field(
        default=None, description="Optional benchmark used for excess return calculation"
    )
    outcome_return: float = Field(default=0.0, description="Return of the outcome")
    outcome_excess_return: float = Field(
        default=0.0, description="Excess return over the benchmark"
    )
    max_drawdown: Optional[float] = Field(default=None, description="Maximum drawdown experienced")
    decay: Optional[float] = Field(default=None, description="Decay score")
    failure_reason: Optional[str] = Field(
        default=None, description="Optional reason for failure (if applicable)"
    )
    lesson: Optional[str] = Field(
        default=None, description="Optional lesson learned (if applicable)"
    )
    evaluated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the outcome was evaluated (if applicable)"
    )
    metadata: dict = Field(default_factory=dict, description="Additional metadata as a dictionary")
