"""Dashboard 首页数据结构 Pydantic 模型"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TodayEvent(BaseModel):
    """今日新事件"""
    event_id: str
    event_type: str
    summary: str
    impact_direction: Optional[str]
    confidence: float
    created_at: str


class HighPriorityThesis(BaseModel):
    """高优先级论题"""
    signal_id: str
    subject_id: str
    thesis: str
    score: float
    confidence: float
    status: str
    event_type: str


class AbnormalFlow(BaseModel):
    """异常流向/主题扩散"""
    symbol: str
    industry: str
    diffusion_strength: float
    change_pct: float
    updated_at: str


class TodaySection(BaseModel):
    """Today 板块数据"""
    new_events: List[TodayEvent] = Field(default_factory=list)
    high_priority_theses: List[HighPriorityThesis] = Field(default_factory=list)
    abnormal_flows: List[AbnormalFlow] = Field(default_factory=list)


class PendingAssertion(BaseModel):
    """待处理断言"""
    assertion_id: str
    signal_id: str
    subject: str
    claim: str
    status: str
    created_at: str


class MissingEvidence(BaseModel):
    """缺失证据项"""
    assertion_id: str
    required_evidence_type: str
    subject: str


class MappingReviewItem(BaseModel):
    """待映射审查项"""
    review_id: str
    subject: str
    reviewer: str
    status: str


class ResearchQueueSection(BaseModel):
    """Research Queue 板块数据"""
    pending_assertions: List[PendingAssertion] = Field(default_factory=list)
    missing_evidence: List[MissingEvidence] = Field(default_factory=list)
    mapping_reviews: List[MappingReviewItem] = Field(default_factory=list)


class CandidateItem(BaseModel):
    """候选机会候选"""
    candidate_id: str
    signal_id: str
    subject: str
    readiness_score: float
    thesis: str
    timing_blocker: Optional[str]
    trigger_condition: Optional[str]
    event_type: str


class CandidateBoardSection(BaseModel):
    """Candidate Board 板块数据"""
    top_candidates: List[CandidateItem] = Field(default_factory=list)


class RecentFailure(BaseModel):
    """最近失败记录"""
    outcome_id: str
    signal_id: str
    subject_id: str
    failure_reason: str
    lesson: str
    outcome_return: Optional[float]
    created_at: str


class BestPerformingEventType(BaseModel):
    """表现最好的事件类型"""
    event_type: str
    avg_excess_return: float
    total_signals: int
    win_rate: float


class WeeklyLesson(BaseModel):
    """每周经验总结"""
    id: str
    week: str
    key_takeaway: str
    created_at: str


class LearningSection(BaseModel):
    """Learning 板块数据"""
    recent_failures: List[RecentFailure] = Field(default_factory=list)
    best_event_types: List[BestPerformingEventType] = Field(default_factory=list)
    weekly_lessons: List[WeeklyLesson] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    """完整首页聚合响应"""
    today: TodaySection
    research_queue: ResearchQueueSection
    candidate_board: CandidateBoardSection
    learning: LearningSection
    generated_at: datetime = Field(default_factory=datetime.utcnow)
