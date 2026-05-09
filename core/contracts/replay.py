"""
Core contracts for replay tasks and results (historical event batch replay and signal calibration).

This module defines Pydantic models for replay jobs, single-event replay results,
aggregate replay results, and replay job creation requests in AlphaFoundry.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReplayJob(BaseModel):
    """回放任务.

    Represents a replay job, including job ID, name, description, event filter,
    max events, status, creation time, and completion time.

    Attributes:
        job_id: Unique identifier for the replay job.
        name: Name of the replay job.
        description: Optional description of the job.
        event_filter: Optional dictionary with filter conditions (event_type, source_type, date_range).
        max_events: Maximum number of events to replay (default 100).
        status: Status of the job (pending, running, completed, failed) (default "pending").
        created_at: Timestamp when the job was created.
        completed_at: Timestamp when the job was completed (if applicable).
    """

    job_id: str = Field(description="Unique identifier for the replay job")
    name: str = Field(description="Name of the replay job")
    description: Optional[str] = Field(default=None, description="Optional description of the job")
    event_filter: Optional[dict] = Field(default=None, description="Optional filter conditions (event_type, source_type, date_range)")
    max_events: int = Field(default=100, description="Maximum number of events to replay")
    status: str = Field(default="pending", description="Status of the job (pending, running, completed, failed)")
    created_at: datetime = Field(description="Timestamp when the job was created")
    completed_at: Optional[datetime] = Field(default=None, description="Timestamp when the job was completed (if applicable)")


class ReplayResult(BaseModel):
    """单事件回放结果.

    Represents the replay result for a single event, including job ID, event ID,
    signal/outcome IDs, event/source type, signal score/confidence, timing action,
    outcome metrics, and error message (if any).

    Attributes:
        job_id: Unique identifier of the replay job.
        event_id: Unique identifier of the event.
        signal_id: Optional unique identifier of the generated signal.
        outcome_id: Optional unique identifier of the outcome.
        event_type: Type of the event.
        source_type: Type of the source.
        signal_score: Optional score of the generated signal.
        signal_confidence: Optional confidence of the generated signal.
        timing_action: Optional timing action taken.
        outcome_return: Optional return of the outcome.
        outcome_excess_return: Optional excess return of the outcome.
        max_drawdown: Optional maximum drawdown of the outcome.
        decay: Optional decay score of the outcome.
        error: Optional error message (if replay failed for this event).
    """

    job_id: str = Field(description="Unique identifier of the replay job")
    event_id: str = Field(description="Unique identifier of the event")
    signal_id: Optional[str] = Field(default=None, description="Optional unique identifier of the generated signal")
    outcome_id: Optional[str] = Field(default=None, description="Optional unique identifier of the outcome")
    event_type: str = Field(description="Type of the event")
    source_type: str = Field(description="Type of the source")
    signal_score: Optional[float] = Field(default=None, description="Optional score of the generated signal")
    signal_confidence: Optional[float] = Field(default=None, description="Optional confidence of the generated signal")
    timing_action: Optional[str] = Field(default=None, description="Optional timing action taken")
    outcome_return: Optional[float] = Field(default=None, description="Optional return of the outcome")
    outcome_excess_return: Optional[float] = Field(default=None, description="Optional excess return of the outcome")
    max_drawdown: Optional[float] = Field(default=None, description="Optional maximum drawdown of the outcome")
    decay: Optional[float] = Field(default=None, description="Optional decay score of the outcome")
    error: Optional[str] = Field(default=None, description="Optional error message (if replay failed for this event)")


class ReplayAggregate(BaseModel):
    """回放聚合结果.

    Represents aggregate results for a replay job, including job ID, total events,
    successful/failed counts, hit rate, average metrics, breakdowns by event type,
    source type, timing action, and calibration data.

    Attributes:
        job_id: Unique identifier of the replay job.
        total_events: Total number of events replayed.
        successful: Number of successful replays.
        failed: Number of failed replays.
        hit_rate: Hit rate (proportion of positive returns).
        avg_excess_return: Average excess return across events.
        avg_max_drawdown: Average maximum drawdown across events.
        avg_decay: Average decay score across events.
        by_event_type: Breakdown by event type (dict).
        by_source_type: Breakdown by source type (dict).
        by_timing_action: Breakdown by timing action (dict).
        calibration: Calibration data (dict).
    """

    job_id: str = Field(description="Unique identifier of the replay job")
    total_events: int = Field(description="Total number of events replayed")
    successful: int = Field(description="Number of successful replays")
    failed: int = Field(description="Number of failed replays")
    hit_rate: float = Field(description="Hit rate (proportion of positive returns)")
    avg_excess_return: float = Field(description="Average excess return across events")
    avg_max_drawdown: float = Field(description="Average maximum drawdown across events")
    avg_decay: float = Field(description="Average decay score across events")
    by_event_type: dict[str, dict] = Field(default_factory=dict, description="Breakdown by event type")
    by_source_type: dict[str, dict] = Field(default_factory=dict, description="Breakdown by source type")
    by_timing_action: dict[str, dict] = Field(default_factory=dict, description="Breakdown by timing action")
    calibration: dict = Field(default_factory=dict, description="Calibration data")


class ReplayJobCreateRequest(BaseModel):
    """创建回放任务请求.

    Request schema for creating a new replay job, including name, description,
    event filter, and max events.

    Attributes:
        name: Name of the replay job (default "Default Replay").
        description: Optional description of the job.
        event_filter: Optional dictionary with filter conditions.
        max_events: Maximum number of events to replay (default 100).
    """

    name: str = Field(default="Default Replay", description="Name of the replay job")
    description: Optional[str] = Field(default=None, description="Optional description of the job")
    event_filter: Optional[dict] = Field(default=None, description="Optional filter conditions")
    max_events: int = Field(default=100, description="Maximum number of events to replay")
