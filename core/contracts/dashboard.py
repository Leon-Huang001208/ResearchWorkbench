"""
Core contracts for dashboard data structures.

This module defines Pydantic models that standardize the data for the AlphaFoundry
dashboard, including sections for today's events, research queue, candidate board,
and learning insights.
"""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TodayEvent(BaseModel):
    """今日新事件.

    Represents a new event detected today, including type, summary, impact,
    confidence, and creation time.

    Attributes:
        event_id: Unique identifier for the event.
        event_type: Type of the event (e.g., "earnings", "news", "regulatory").
        summary: Brief summary of the event.
        impact_direction: Direction of impact (e.g., "positive", "negative", "neutral").
        confidence: Confidence score (0.0 to 1.0) of the event's impact assessment.
        created_at: Timestamp when the event was created (as a string).
    """

    event_id: str = Field(description="Unique identifier for the event")
    event_type: str = Field(description="Type of the event (earnings, news, regulatory, etc.)")
    summary: str = Field(description="Brief summary of the event")
    impact_direction: Optional[str] = Field(
        description="Direction of impact (positive, negative, neutral, etc.)"
    )
    confidence: float = Field(description="Confidence score (0.0 to 1.0) of the impact assessment")
    created_at: str = Field(description="Timestamp when the event was created")


class HighPriorityThesis(BaseModel):
    """高优先级论题.

    Represents a high-priority thesis (investment idea) with signal ID, subject,
    thesis text, score, confidence, status, and event type.

    Attributes:
        signal_id: Unique identifier for the associated signal.
        subject_id: Canonical ID of the subject asset/entity.
        thesis: Text of the investment thesis.
        score: Priority or quality score for the thesis.
        confidence: Confidence score (0.0 to 1.0) of the thesis.
        status: Status of the thesis (e.g., "pending", "active", "closed").
        event_type: Type of event that triggered the thesis.
    """

    signal_id: str = Field(description="Unique identifier for the associated signal")
    subject_id: str = Field(description="Canonical ID of the subject asset/entity")
    thesis: str = Field(description="Text of the investment thesis")
    score: float = Field(description="Priority or quality score")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    status: str = Field(description="Status of the thesis (pending, active, closed, etc.)")
    event_type: str = Field(description="Type of event that triggered the thesis")


class AbnormalFlow(BaseModel):
    """异常流向/主题扩散.

    Represents an abnormal fund flow or theme diffusion, including symbol, industry,
    diffusion strength, percentage change, and update time.

    Attributes:
        symbol: Ticker symbol of the asset.
        industry: Industry sector of the asset.
        diffusion_strength: Strength of the theme diffusion (0.0 to 1.0 or similar scale).
        change_pct: Percentage change in price or flow.
        updated_at: Timestamp when this data was last updated (as a string).
    """

    symbol: str = Field(description="Ticker symbol of the asset")
    industry: str = Field(description="Industry sector of the asset")
    diffusion_strength: float = Field(description="Strength of the theme diffusion")
    change_pct: float = Field(description="Percentage change in price or flow")
    updated_at: str = Field(description="Timestamp when this data was last updated")


class TodaySection(BaseModel):
    """Today 板块数据.

    Contains data for the "Today" dashboard section, including new events, high-priority
    theses, and abnormal flows.

    Attributes:
        new_events: List of today's new events.
        high_priority_theses: List of high-priority theses.
        abnormal_flows: List of abnormal flow/theme diffusion items.
    """

    new_events: List[TodayEvent] = Field(
        default_factory=list, description="List of today's new events"
    )
    high_priority_theses: List[HighPriorityThesis] = Field(
        default_factory=list, description="List of high-priority theses"
    )
    abnormal_flows: List[AbnormalFlow] = Field(
        default_factory=list, description="List of abnormal flow/theme diffusion items"
    )


class PendingAssertion(BaseModel):
    """待处理断言.

    Represents an assertion that is pending review, including assertion ID, signal ID,
    subject, claim, status, and creation time.

    Attributes:
        assertion_id: Unique identifier for the assertion.
        signal_id: Unique identifier for the associated signal.
        subject: Subject of the assertion.
        claim: The factual claim made by the assertion.
        status: Status of the assertion (e.g., "pending", "draft").
        created_at: Timestamp when the assertion was created (as a string).
    """

    assertion_id: str = Field(description="Unique identifier for the assertion")
    signal_id: str = Field(description="Unique identifier for the associated signal")
    subject: str = Field(description="Subject of the assertion")
    claim: str = Field(description="The factual claim made by the assertion")
    status: str = Field(description="Status of the assertion (pending, draft, etc.)")
    created_at: str = Field(description="Timestamp when the assertion was created")


class MissingEvidence(BaseModel):
    """缺失证据项.

    Represents an item where evidence is missing, including assertion ID, required
    evidence type, and subject.

    Attributes:
        assertion_id: Unique identifier for the assertion.
        required_evidence_type: Type of evidence that is missing.
        subject: Subject of the assertion.
    """

    assertion_id: str = Field(description="Unique identifier for the assertion")
    required_evidence_type: str = Field(description="Type of evidence that is missing")
    subject: str = Field(description="Subject of the assertion")


class MappingReviewItem(BaseModel):
    """待映射审查项.

    Represents an item pending mapping review, including review ID, subject, reviewer,
    and status.

    Attributes:
        review_id: Unique identifier for the review item.
        subject: Subject of the review.
        reviewer: Identifier of the assigned reviewer.
        status: Status of the review (e.g., "pending", "in_progress").
    """

    review_id: str = Field(description="Unique identifier for the review item")
    subject: str = Field(description="Subject of the review")
    reviewer: str = Field(description="Identifier of the assigned reviewer")
    status: str = Field(description="Status of the review (pending, in_progress, etc.)")


class ResearchQueueSection(BaseModel):
    """Research Queue 板块数据.

    Contains data for the "Research Queue" dashboard section, including pending assertions,
    missing evidence, and mapping reviews.

    Attributes:
        pending_assertions: List of pending assertions.
        missing_evidence: List of missing evidence items.
        mapping_reviews: List of mapping review items.
    """

    pending_assertions: List[PendingAssertion] = Field(
        default_factory=list, description="List of pending assertions"
    )
    missing_evidence: List[MissingEvidence] = Field(
        default_factory=list, description="List of missing evidence items"
    )
    mapping_reviews: List[MappingReviewItem] = Field(
        default_factory=list, description="List of mapping review items"
    )


class CandidateItem(BaseModel):
    """候选机会候选.

    Represents a candidate investment opportunity, including candidate ID, signal ID,
    subject, readiness score, thesis, timing blocker, trigger condition, and event type.

    Attributes:
        candidate_id: Unique identifier for the candidate item.
        signal_id: Unique identifier for the associated signal.
        subject: Subject asset/entity of the candidate.
        readiness_score: Score indicating how ready the candidate is (0.0 to 1.0).
        thesis: Text of the investment thesis for the candidate.
        timing_blocker: Any timing-related blocker (if applicable).
        trigger_condition: Condition that would trigger acting on the candidate (if applicable).
        event_type: Type of event that generated the candidate.
    """

    candidate_id: str = Field(description="Unique identifier for the candidate item")
    signal_id: str = Field(description="Unique identifier for the associated signal")
    subject: str = Field(description="Subject asset/entity of the candidate")
    readiness_score: float = Field(description="Readiness score (0.0 to 1.0)")
    thesis: str = Field(description="Investment thesis for the candidate")
    timing_blocker: Optional[str] = Field(description="Timing-related blocker (if applicable)")
    trigger_condition: Optional[str] = Field(description="Trigger condition (if applicable)")
    event_type: str = Field(description="Type of event that generated the candidate")


class CandidateBoardSection(BaseModel):
    """Candidate Board 板块数据.

    Contains data for the "Candidate Board" dashboard section, including top candidates.

    Attributes:
        top_candidates: List of top candidate investment opportunities.
    """

    top_candidates: List[CandidateItem] = Field(
        default_factory=list, description="List of top candidate investment opportunities"
    )


class RecentFailure(BaseModel):
    """最近失败记录.

    Represents a recent failure, including outcome ID, signal ID, subject ID, failure reason,
    lesson learned, outcome return, and creation time.

    Attributes:
        outcome_id: Unique identifier for the outcome.
        signal_id: Unique identifier for the associated signal.
        subject_id: Canonical ID of the subject asset/entity.
        failure_reason: Reason for the failure.
        lesson: Lesson learned from the failure.
        outcome_return: Return of the outcome (if applicable).
        created_at: Timestamp when the failure was recorded (as a string).
    """

    outcome_id: str = Field(description="Unique identifier for the outcome")
    signal_id: str = Field(description="Unique identifier for the associated signal")
    subject_id: str = Field(description="Canonical ID of the subject asset/entity")
    failure_reason: str = Field(description="Reason for the failure")
    lesson: str = Field(description="Lesson learned from the failure")
    outcome_return: Optional[float] = Field(description="Return of the outcome (if applicable)")
    created_at: str = Field(description="Timestamp when the failure was recorded")


class BestPerformingEventType(BaseModel):
    """表现最好的事件类型.

    Represents the best-performing event types, including event type, average excess return,
    total signals, and win rate.

    Attributes:
        event_type: Type of event (e.g., "earnings", "news").
        avg_excess_return: Average excess return for this event type.
        total_signals: Total number of signals generated for this event type.
        win_rate: Win rate (percentage of profitable signals) for this event type.
    """

    event_type: str = Field(description="Type of event (earnings, news, etc.)")
    avg_excess_return: float = Field(description="Average excess return for this event type")
    total_signals: int = Field(description="Total number of signals for this event type")
    win_rate: float = Field(description="Win rate for this event type")


class WeeklyLesson(BaseModel):
    """每周经验总结.

    Represents a weekly lesson summary, including ID, week, key takeaway, and creation time.

    Attributes:
        id: Unique identifier for the weekly lesson.
        week: Week identifier (e.g., "2024-W05").
        key_takeaway: Key takeaway from the week.
        created_at: Timestamp when the lesson was created (as a string).
    """

    id: str = Field(description="Unique identifier for the weekly lesson")
    week: str = Field(description="Week identifier (e.g., 2024-W05)")
    key_takeaway: str = Field(description="Key takeaway from the week")
    created_at: str = Field(description="Timestamp when the lesson was created")


class LearningSection(BaseModel):
    """Learning 板块数据.

    Contains data for the "Learning" dashboard section, including recent failures,
    best event types, and weekly lessons.

    Attributes:
        recent_failures: List of recent failure records.
        best_event_types: List of best-performing event types.
        weekly_lessons: List of weekly lesson summaries.
    """

    recent_failures: List[RecentFailure] = Field(
        default_factory=list, description="List of recent failure records"
    )
    best_event_types: List[BestPerformingEventType] = Field(
        default_factory=list, description="List of best-performing event types"
    )
    weekly_lessons: List[WeeklyLesson] = Field(
        default_factory=list, description="List of weekly lesson summaries"
    )


class GlobalNewsItem(BaseModel):
    """全球热点新闻项.

    Represents a global hot news item, including title, source, importance score,
    summary, publish time, and related symbols.

    Attributes:
        news_id: Unique identifier for the news.
        title: News title.
        source: News source (e.g., "Reuters", "Bloomberg").
        importance_score: Importance score (0.0 to 1.0), higher is more important.
        summary: Brief summary of the news.
        content_url: URL to the full content (optional).
        published_at: Publish time as a string.
        related_symbols: List of related ticker symbols (optional).
        region: Region this news pertains to (e.g., "Global", "US", "China", "Europe").
    """

    news_id: str = Field(description="Unique identifier for the news")
    title: str = Field(description="News title")
    source: str = Field(description="News source (e.g., Reuters, Bloomberg)")
    importance_score: float = Field(description="Importance score (0.0 to 1.0)")
    summary: str = Field(description="Brief summary of the news")
    content_url: Optional[str] = Field(description="URL to the full content", default=None)
    published_at: str = Field(description="Publish time as an ISO string")
    related_symbols: List[str] = Field(
        default_factory=list, description="List of related ticker symbols"
    )
    region: str = Field(description="Region this news pertains to (e.g., Global, US, China)")
    is_mock: bool = Field(
        default=False, description="Whether this is mock data (True) or real data (False)"
    )


class SectorChangeItem(BaseModel):
    """板块涨跌项.

    Represents a sector/concept change data, including name, change percentage,
    leading stocks, and related news count.

    Attributes:
        sector_id: Unique identifier for the sector/concept.
        name: Name of the sector/concept (e.g., "AI", "New Energy", "Banking").
        change_pct: Change percentage (positive for up, negative for down).
        leading_stocks: List of leading stock symbols in this sector.
        related_news_count: Number of related news items today.
        is_concept: Whether this is a concept (True) or a traditional sector (False).
    """

    sector_id: str = Field(description="Unique identifier for the sector/concept")
    name: str = Field(description="Name of the sector/concept")
    change_pct: float = Field(description="Change percentage (positive for up, negative for down)")
    leading_stocks: List[str] = Field(default_factory=list, description="Leading stock symbols")
    related_news_count: int = Field(default=0, description="Number of related news items today")
    is_concept: bool = Field(
        default=False, description="Whether this is a concept (True) or traditional sector (False)"
    )
    is_mock: bool = Field(
        default=False, description="Whether this is mock data (True) or real data (False)"
    )
    source: Optional[str] = Field(default=None, description="Source vendor or repository")
    view_key: Optional[str] = Field(default=None, description="Dashboard market view key")
    view_label: Optional[str] = Field(default=None, description="Dashboard market view label")


class SectorMoverView(BaseModel):
    """A grouped sector mover view for one market classification lens."""

    up: List[SectorChangeItem] = Field(
        default_factory=list, description="Top gaining sectors/concepts for this view"
    )
    down: List[SectorChangeItem] = Field(
        default_factory=list, description="Top losing sectors/concepts for this view"
    )


class MarketIndexItem(BaseModel):
    """A real-time index quote used by the market command center."""

    code: str = Field(description="Index code")
    name: str = Field(description="Index display name")
    value: str = Field(description="Formatted latest index value")
    change: float = Field(description="Percentage change")
    point_change: Optional[float] = Field(default=None, description="Point change")
    amount: Optional[float] = Field(default=None, description="Turnover amount in yuan")
    source: str = Field(default="sina", description="Quote source")


class MarketBreadthSnapshot(BaseModel):
    """Market breadth snapshot for mainland market overview."""

    up: int = Field(default=0, description="Number of rising names")
    down: int = Field(default=0, description="Number of falling names")
    flat: int = Field(default=0, description="Number of unchanged names")
    upRatio: float = Field(default=50.0, description="Rising ratio for the breadth bar")
    downRatio: float = Field(default=50.0, description="Falling ratio for the breadth bar")
    turnover: str = Field(default="--", description="Formatted turnover")
    turnoverDelta: Optional[str] = Field(
        default=None, description="Optional turnover comparison text"
    )
    previousTurnover: Optional[str] = Field(
        default=None, description="Previous trading day turnover"
    )
    netInflow: Optional[str] = Field(default=None, description="Formatted net inflow")
    source: str = Field(default="unknown", description="Underlying data source")
    sourceLabel: str = Field(default="等待实时刷新", description="Human-readable source label")
    fetchedAt: Optional[datetime] = Field(default=None, description="Snapshot fetch time")


class MarketOverviewSection(BaseModel):
    """市场概览板块数据.

    Contains data for the "Market Overview" dashboard section, including global news
    and top sectors (up and down).

    Attributes:
        global_news: List of global hot news items (top 10 by importance).
        top_up_sectors: List of top gaining sectors/concepts (top 5).
        top_down_sectors: List of top losing sectors/concepts (top 5).
    """

    global_news: List[GlobalNewsItem] = Field(
        default_factory=list, description="List of global hot news items (top 10)"
    )
    top_up_sectors: List[SectorChangeItem] = Field(
        default_factory=list, description="List of top gaining sectors/concepts (top 5)"
    )
    top_down_sectors: List[SectorChangeItem] = Field(
        default_factory=list, description="List of top losing sectors/concepts (top 5)"
    )
    sector_views: Dict[str, SectorMoverView] = Field(
        default_factory=dict,
        description="Grouped sector movers by classification lens, e.g. theme or industry",
    )
    indices: List[MarketIndexItem] = Field(
        default_factory=list, description="Real-time market index quotes"
    )
    breadth: Optional[MarketBreadthSnapshot] = Field(
        default=None, description="Real-time market breadth snapshot"
    )
    market_stats: Dict[str, object] = Field(
        default_factory=dict,
        description="Supplementary market stats, such as limit-up/down and capital flow",
    )
    uses_real_news: bool = Field(
        default=False, description="Whether news data is from real sources"
    )
    uses_real_sectors: bool = Field(
        default=False, description="Whether sector data is from real sources"
    )
    last_updated: Optional[datetime] = Field(
        default=None, description="Timestamp when data was last updated from real sources"
    )


class DashboardResponse(BaseModel):
    """完整首页聚合响应.

    Represents the complete dashboard response, including market overview, today's section,
    research queue, candidate board, learning section, and generation timestamp.

    Attributes:
        market_overview: Data for the "Market Overview" section (news and sectors).
        today: Data for the "Today" section.
        research_queue: Data for the "Research Queue" section.
        candidate_board: Data for the "Candidate Board" section.
        learning: Data for the "Learning" section.
        generated_at: Timestamp when this dashboard response was generated.
    """

    market_overview: MarketOverviewSection = Field(
        description="Data for the 'Market Overview' section (news and sectors)"
    )
    today: TodaySection = Field(description="Data for the 'Today' section")
    research_queue: ResearchQueueSection = Field(
        description="Data for the 'Research Queue' section"
    )
    candidate_board: CandidateBoardSection = Field(
        description="Data for the 'Candidate Board' section"
    )
    learning: LearningSection = Field(description="Data for the 'Learning' section")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this dashboard response was generated",
    )
