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


class SignalOutcomeDB(Base):
    """事件信号结果评估数据库模型"""

    __tablename__ = "signal_outcome"

    outcome_id = Column(Text, primary_key=True)
    event_id = Column(Text, nullable=False, index=True)
    signal_id = Column(Text, nullable=False, index=True)
    subject_id = Column(Text, nullable=False, index=True)
    event_date = Column(DateTime(timezone=True), nullable=False)
    timing_action = Column(Text, nullable=False, default="wait")
    entry_rule = Column(Text, nullable=True)
    horizon = Column(Text, nullable=False, default="20d")
    benchmark = Column(Text, nullable=True)
    outcome_return = Column(Numeric, nullable=False, default=0.0)
    outcome_excess_return = Column(Numeric, nullable=False, default=0.0)
    max_drawdown = Column(Numeric, nullable=True)
    decay = Column(Numeric, nullable=True)
    failure_reason = Column(Text, nullable=True)
    lesson = Column(Text, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    outcome_metadata = Column(JSON, nullable=False, default=dict, name="metadata")
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
    active_weights = Column(JSON, nullable=False, default=list)
    blockers = Column(JSON, nullable=False, default=list)
    rationale = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class IngestionQueueItemDB(Base):
    """统一摄取队列数据库模型"""

    __tablename__ = "ingestion_queue_item"

    item_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_id = Column(Text, nullable=True)
    raw_content = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    priority = Column(Integer, nullable=False, default=0)
    status = Column(Text, nullable=False, default="pending", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    dedup_hash = Column(Text, nullable=True, unique=True, index=True)


class ReplayJobDB(Base):
    """回放任务数据库模型"""

    __tablename__ = "replay_job"

    job_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    event_filter = Column(JSON, nullable=True)
    max_events = Column(Integer, nullable=False, default=100)
    status = Column(Text, nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ReplayResultDB(Base):
    """回放结果数据库模型"""

    __tablename__ = "replay_result"

    id = Column(Text, primary_key=True)
    job_id = Column(Text, nullable=False, index=True)
    event_id = Column(Text, nullable=False)
    signal_id = Column(Text, nullable=True)
    outcome_id = Column(Text, nullable=True)
    event_type = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False)
    signal_score = Column(Numeric, nullable=True)
    signal_confidence = Column(Numeric, nullable=True)
    timing_action = Column(Text, nullable=True)
    outcome_return = Column(Numeric, nullable=True)
    outcome_excess_return = Column(Numeric, nullable=True)
    max_drawdown = Column(Numeric, nullable=True)
    decay = Column(Numeric, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class PortfolioProposalDB(Base):
    """组合提案数据库模型"""

    __tablename__ = "portfolio_proposal"

    proposal_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    candidates = Column(JSON, nullable=False, default=list)
    allocations = Column(JSON, nullable=False, default=dict)
    constraints_applied = Column(JSON, nullable=False, default=list)
    excluded_signals = Column(JSON, nullable=False, default=list)
    rationale = Column(JSON, nullable=False, default=dict)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AuditLogDB(Base):
    """审计日志数据库模型"""

    __tablename__ = "audit_log"

    log_id = Column(Text, primary_key=True)
    entity_type = Column(Text, nullable=False, index=True)
    entity_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)
    actor = Column(Text, nullable=False, default="system")
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class PaperPortfolioDB(Base):
    """模拟组合数据库模型"""

    __tablename__ = "paper_portfolio"

    portfolio_id = Column(Text, primary_key=True)
    proposal_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active")
    assumptions = Column(JSON, nullable=False, default=dict)
    current_snapshot = Column(JSON, nullable=True)
    snapshots = Column(JSON, nullable=False, default=list)
    rebalance_events = Column(JSON, nullable=False, default=list)
    portfolio_metadata = Column(JSON, nullable=False, default=dict, name="metadata")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class SimulationResultDB(Base):
    """模拟结果数据库模型"""

    __tablename__ = "simulation_result"

    result_id = Column(Text, primary_key=True)
    portfolio_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    mode = Column(Text, nullable=False, default="replay")
    assumptions = Column(JSON, nullable=False, default=dict)
    performance = Column(JSON, nullable=False, default=dict)
    benchmark_comparisons = Column(JSON, nullable=False, default=list)
    nav_series = Column(JSON, nullable=False, default=list)
    rebalance_count = Column(Integer, nullable=False, default=0)
    total_turnover = Column(Numeric, nullable=False, default=0.0)
    result_metadata = Column(JSON, nullable=False, default=dict, name="metadata")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class StrategyVersionDB(Base):
    """策略版本数据库模型"""

    __tablename__ = "strategy_version"
    __table_args__ = {"extend_existing": True}

    version_id = Column(Text, primary_key=True)
    component_type = Column(Text, nullable=False, index=True)
    component_name = Column(Text, nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    content_hash = Column(Text, nullable=False, default="")
    parent_version_id = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by = Column(Text, nullable=False, default="system")
    tags = Column(JSON, nullable=False, default=list)


class ExperimentRecordDB(Base):
    """实验记录数据库模型"""

    __tablename__ = "experiment_record"
    __table_args__ = {"extend_existing": True}

    experiment_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    strategy_version_ids = Column(JSON, nullable=False, default=list)
    experiment_type = Column(Text, nullable=False, default="signal")
    entity_id = Column(Text, nullable=True, index=True)
    metrics = Column(JSON, nullable=False, default=dict)
    status = Column(Text, nullable=False, default="running", index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    experiment_metadata = Column(JSON, nullable=False, default=dict, name="metadata")


class HealthMetricsDB(Base):
    """健康指标数据库模型"""

    __tablename__ = "health_metrics"

    metric_id = Column(Text, primary_key=True)
    subsystem = Column(Text, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    throughput = Column(Numeric, nullable=False, default=0.0)
    error_rate = Column(Numeric, nullable=False, default=0.0)
    avg_latency_ms = Column(Numeric, nullable=False, default=0.0)
    p99_latency_ms = Column(Numeric, nullable=False, default=0.0)
    queue_depth = Column(Integer, nullable=False, default=0)
    items_processed = Column(Integer, nullable=False, default=0)
    items_failed = Column(Integer, nullable=False, default=0)
    extra = Column(JSON, nullable=False, default=dict)


class DriftReportDB(Base):
    """漂移报告数据库模型"""

    __tablename__ = "drift_report"

    report_id = Column(Text, primary_key=True)
    dimension = Column(Text, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    baseline_window_start = Column(DateTime(timezone=True), nullable=False)
    baseline_window_end = Column(DateTime(timezone=True), nullable=False)
    current_window_start = Column(DateTime(timezone=True), nullable=False)
    current_window_end = Column(DateTime(timezone=True), nullable=False)
    drift_score = Column(Numeric, nullable=False, default=0.0)
    is_drift = Column(Boolean, nullable=False, default=False)
    threshold = Column(Numeric, nullable=False, default=0.0)
    baseline_distribution = Column(JSON, nullable=False, default=dict)
    current_distribution = Column(JSON, nullable=False, default=dict)
    details = Column(JSON, nullable=False, default=dict)


class AlertThresholdDB(Base):
    """告警阈值数据库模型"""

    __tablename__ = "alert_threshold"

    threshold_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    subsystem = Column(Text, nullable=True)
    dimension = Column(Text, nullable=True)
    metric_field = Column(Text, nullable=True)
    operator = Column(Text, nullable=False, default="gte")
    value = Column(Numeric, nullable=False, default=0.0)
    severity = Column(Text, nullable=False, default="warning")
    cooldown_minutes = Column(Integer, nullable=False, default=30)
    enabled = Column(Boolean, nullable=False, default=True)


class AlertPayloadDB(Base):
    """告警记录数据库模型"""

    __tablename__ = "alert_payload"

    alert_id = Column(Text, primary_key=True)
    threshold_id = Column(Text, nullable=False, index=True)
    severity = Column(Text, nullable=False, default="warning")
    status = Column(Text, nullable=False, default="open", index=True)
    subsystem = Column(Text, nullable=True)
    dimension = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    observed_value = Column(Numeric, nullable=False, default=0.0)
    threshold_value = Column(Numeric, nullable=False, default=0.0)
    triggered_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    alert_metadata = Column(JSON, nullable=False, default=dict, name="metadata")


class IncidentRecordDB(Base):
    """事件记录数据库模型"""

    __tablename__ = "incident_record"

    incident_id = Column(Text, primary_key=True)
    alert_id = Column(Text, nullable=False, index=True)
    subsystem = Column(Text, nullable=False, index=True)
    severity = Column(Text, nullable=False, default="warning")
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    incident_metadata = Column(JSON, nullable=False, default=dict, name="metadata")


class DecisionWorkspaceDB(Base):
    """决策工作区数据库模型"""

    __tablename__ = "decision_workspace"

    workspace_id = Column(Text, primary_key=True)
    workspace_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Text, nullable=False, default="open", index=True)
    candidate_ids = Column(JSON, nullable=False, default=list)
    team_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_by = Column(Text, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)


class AnalystDecisionDB(Base):
    """分析师决策数据库模型"""

    __tablename__ = "analyst_decision"

    decision_id = Column(Text, primary_key=True)
    workspace_id = Column(Text, nullable=False, index=True)
    candidate_id = Column(Text, nullable=False, index=True)
    candidate_type = Column(Text, nullable=False)
    previous_status = Column(Text, nullable=False)
    final_action_type = Column(Text, nullable=False)
    action_by = Column(Text, nullable=False)
    action_at = Column(DateTime(timezone=True), nullable=False)
    rationale = Column(Text, nullable=True)
    changes = Column(JSON, nullable=True)
    revision_history = Column(JSON, nullable=False, default=list)
    is_closed = Column(Boolean, nullable=False, default=False)


class DecisionAuditDB(Base):
    """决策审计数据库模型"""

    __tablename__ = "decision_audit"

    audit_id = Column(Text, primary_key=True)
    decision_id = Column(Text, nullable=False, index=True)
    action = Column(Text, nullable=False)
    actor = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    before_state = Column(JSON, nullable=False)
    after_state = Column(JSON, nullable=False)
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)


class PostMortemRecordDB(Base):
    """决策复盘数据库模型"""

    __tablename__ = "post_mortem_record"

    post_mortem_id = Column(Text, primary_key=True)
    decision_id = Column(Text, nullable=False, index=True)
    original_decision = Column(Text, nullable=False)
    realized_outcome = Column(Text, nullable=False)
    outcome_metrics = Column(JSON, nullable=False, default=dict)
    learning_points = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    linked_signal_accuracy = Column(Numeric, nullable=True)

