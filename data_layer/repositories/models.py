
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, Text, JSON, DateTime
from sqlalchemy.orm import relationship

from data_layer.repositories.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Entity(Base):
    """实体模型"""

    __tablename__ = "entity"

    entity_id = Column(Text, primary_key=True)
    canonical_id = Column(Text, unique=True, nullable=False)
    entity_type = Column(Text, nullable=False)
    canonical_name = Column(Text, nullable=False)
    aliases = Column(JSON, nullable=False, default=list)
    vendor_ids = Column(JSON, nullable=False, default=dict)
    properties = Column(JSON, nullable=False, default=dict)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # 关系
    assertions = relationship("Assertion", foreign_keys="Assertion.subject_entity_id")


class SourceDocument(Base):
    """源文档模型"""

    __tablename__ = "source_document"

    doc_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    source_name = Column(Text, nullable=False)
    content_hash = Column(Text, nullable=False)
    rights_ref = Column(Text, nullable=True)
    parser_version = Column(Text, nullable=False)
    object_uri = Column(Text, nullable=False)
    doc_metadata = Column(JSON, nullable=False, default=dict)
    embedding = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # 关系
    assertions = relationship("Assertion", backref="source_document")
    events = relationship("CanonicalEvent", backref="source_document")


class Assertion(Base):
    """断言模型"""

    __tablename__ = "assertion"

    assertion_id = Column(Text, primary_key=True)
    subject_entity_id = Column(Text, ForeignKey("entity.entity_id"), nullable=True)
    predicate = Column(Text, nullable=False)
    object_entity_id = Column(Text, nullable=True)
    object_value = Column(JSON, nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    confidence = Column(Numeric, nullable=False)
    source_doc_id = Column(Text, ForeignKey("source_document.doc_id"), nullable=True)
    source_span = Column(JSON, nullable=False, default=dict)
    extractor_version = Column(Text, nullable=False)
    reviewer_status = Column(Text, nullable=False, default="draft")
    reviewer = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    trace_ref = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)


class CanonicalEvent(Base):
    """规范事件模型"""

    __tablename__ = "canonical_event"

    event_id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=True)
    impact_direction = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=False)
    needs_review = Column(Boolean, nullable=False, default=True)
    source_doc_id = Column(Text, ForeignKey("source_document.doc_id"), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    reviewer_status = Column(Text, nullable=False, default="draft")
    reviewer = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ReasoningTrace(Base):
    """推理追踪模型"""

    __tablename__ = "reasoning_trace"

    trace_id = Column(Text, primary_key=True)
    request_type = Column(Text, nullable=False)
    question = Column(Text, nullable=False)
    subject_ids = Column(JSON, nullable=False, default=list)
    retrieved_doc_ids = Column(JSON, nullable=False, default=list)
    retrieved_assertion_ids = Column(JSON, nullable=False, default=list)
    graph_paths = Column(JSON, nullable=False, default=list)
    intermediate_hypotheses = Column(JSON, nullable=False, default=list)
    final_answer = Column(Text, nullable=True)
    provider = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=False)
    total_latency_ms = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AssetSnapshot(Base):
    """资产分析快照模型"""

    __tablename__ = "asset_snapshot"

    snapshot_id = Column(Text, primary_key=True)
    canonical_id = Column(Text, ForeignKey("entity.canonical_id"), nullable=False, index=True)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    financial = Column(JSON, nullable=False, default=dict)
    fund_flow = Column(JSON, nullable=False, default=dict)
    price_volume = Column(JSON, nullable=False, default=dict)
    valuation = Column(JSON, nullable=False, default=dict)
    shareholder = Column(JSON, nullable=False, default=dict)
    industry = Column(JSON, nullable=False, default=dict)
    event_impact = Column(JSON, nullable=False, default=list)
    macro_exposure = Column(JSON, nullable=False, default=dict)
    evidence_refs = Column(JSON, nullable=False, default=list)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AlphaSignalDB(Base):
    """Alpha 信号数据库模型"""

    __tablename__ = "alpha_signal"

    signal_id = Column(Text, primary_key=True)
    discriminator = Column(Text, nullable=False, default="alpha_signal")  # to distinguish between AlphaSignal and EventAlphaSignal
    subject_id = Column(Text, nullable=False, index=True)
    horizon = Column(Text, nullable=False)
    thesis = Column(Text, nullable=False)
    score = Column(Numeric, nullable=False)
    confidence = Column(Numeric, nullable=False)
    scenario_refs = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=list)
    status = Column(Text, nullable=False, default="research_only")
    # EventAlphaSignal specific fields
    event_id = Column(Text, nullable=True, index=True)
    event_type = Column(Text, nullable=True)
    event_time = Column(DateTime(timezone=True), nullable=True)
    impact_path = Column(JSON, nullable=False, default=list)
    industry_impacts = Column(JSON, nullable=False, default=list)
    bullish_companies = Column(JSON, nullable=False, default=list)
    bearish_companies = Column(JSON, nullable=False, default=list)
    diffusion_stage = Column(Text, nullable=True)
    market_regime = Column(Text, nullable=True)
    validation_status = Column(Text, nullable=True)
    validation_metrics = Column(JSON, nullable=False, default=dict)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class TradeCandidateDB(Base):
    """交易候选数据库模型"""

    __tablename__ = "trade_candidate"

    candidate_id = Column(Text, primary_key=True)
    signal_id = Column(Text, ForeignKey("alpha_signal.signal_id"), nullable=False, index=True)
    action = Column(Text, nullable=False)
    sizing_hint = Column(Numeric, nullable=False)
    risk_notes = Column(JSON, nullable=False, default=list)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AgentViewDB(Base):
    """Agent 观点数据库模型"""

    __tablename__ = "agent_view"

    view_id = Column(Text, primary_key=True)
    agent_name = Column(Text, nullable=False)
    agent_role = Column(Text, nullable=False, index=True)
    target_id = Column(Text, nullable=False, index=True)
    view = Column(Text, nullable=False)
    thesis = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=False)
    event_id = Column(Text, nullable=True, index=True)
    reasoning = Column(JSON, nullable=False, default=list)
    evidence_refs = Column(JSON, nullable=False, default=list)
    tool_refs = Column(JSON, nullable=False, default=list)
    memory_refs = Column(JSON, nullable=False, default=list)
    workflow_id = Column(Text, nullable=True)
    evaluation = Column(JSON, nullable=False, default=dict)
    view_metadata = Column(JSON, nullable=False, default=dict, name="metadata")  # use "metadata" in DB but "view_metadata" in model
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class BlackboardConflictDB(Base):
    """黑板冲突数据库模型"""

    __tablename__ = "blackboard_conflict"

    conflict_id = Column(Text, primary_key=True)
    target_id = Column(Text, nullable=False, index=True)
    event_id = Column(Text, nullable=True, index=True)
    view_ids = Column(JSON, nullable=False, default=list)
    summary = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=False)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class TimingDecisionDB(Base):
    """Timing Engine 择时决策数据库模型"""

    __tablename__ = "timing_decision"

    decision_id = Column(Text, primary_key=True)
    signal_id = Column(Text, nullable=True, index=True)
    action = Column(Text, nullable=False)
    readiness_score = Column(Numeric, nullable=False)
    market_regime = Column(Text, nullable=False, default="unknown")
    model_scores = Column(JSON, nullable=False, default=list)
    active_weights = Column(JSON, nullable=False, default=dict)
    blockers = Column(JSON, nullable=False, default=list)
    rationale = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
