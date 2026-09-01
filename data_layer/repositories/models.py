from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
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
    discriminator = Column(
        Text, nullable=False, default="alpha_signal"
    )  # to distinguish between AlphaSignal and EventAlphaSignal
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
    view_metadata = Column(
        JSON, nullable=False, default=dict, name="metadata"
    )  # use "metadata" in DB but "view_metadata" in model
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
    event_type = Column(Text, nullable=True, default="unknown", index=True)
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
    published_at = Column(Text, nullable=True)


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


class OutcomeRecordDB(Base):
    """Trade outcome record for outcome journal"""

    __tablename__ = "outcome_record"

    outcome_id = Column(Text, primary_key=True)
    signal_id = Column(Text, nullable=False, index=True)
    candidate_id = Column(Text, nullable=True, index=True)
    entry_time = Column(DateTime(timezone=True), nullable=False)
    exit_time = Column(DateTime(timezone=True), nullable=False)
    entry_price = Column(Numeric, nullable=False)
    exit_price = Column(Numeric, nullable=False)
    return_5d = Column(Numeric, nullable=True)
    return_20d = Column(Numeric, nullable=True)
    return_60d = Column(Numeric, nullable=True)
    benchmark_excess_return = Column(Numeric, nullable=False, default=0.0)
    thesis_success = Column(Boolean, nullable=False)
    failure_classification = Column(Text, nullable=True)
    failure_notes = Column(Text, nullable=True)
    thesis_text = Column(Text, nullable=False)
    propagation_path = Column(JSON, nullable=False, default=list)
    market_regime = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AssetSnapshotModel(Base):
    """Asset analysis snapshot persistent model"""

    __tablename__ = "asset_analysis_snapshot"

    snapshot_id = Column(Text, primary_key=True)
    canonical_id = Column(Text, nullable=False, index=True)
    as_of = Column(DateTime(timezone=True), nullable=False)

    # JSON fields
    financial = Column(JSON, nullable=True)
    fund_flow = Column(JSON, nullable=True)
    price_volume = Column(JSON, nullable=True)
    valuation = Column(JSON, nullable=True)
    shareholder = Column(JSON, nullable=True)
    industry = Column(JSON, nullable=True)
    event_impact = Column(JSON, nullable=True)
    macro_exposure = Column(JSON, nullable=True)
    evidence_refs = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    @classmethod
    def from_contract(cls, contract):
        from core.utils.id_gen import generate_id

        return cls(
            snapshot_id=generate_id(),
            canonical_id=contract.canonical_id,
            as_of=contract.as_of,
            financial=contract.financial,
            fund_flow=contract.fund_flow,
            price_volume=contract.price_volume,
            valuation=contract.valuation,
            shareholder=contract.shareholder,
            industry=contract.industry,
            event_impact=contract.event_impact,
            macro_exposure=contract.macro_exposure,
            evidence_refs=contract.evidence_refs,
        )

    def to_contract(self):
        from core.contracts import AssetAnalysisSnapshot

        return AssetAnalysisSnapshot(
            canonical_id=self.canonical_id,
            as_of=self.as_of,
            financial=self.financial,
            fund_flow=self.fund_flow,
            price_volume=self.price_volume,
            valuation=self.valuation,
            shareholder=self.shareholder,
            industry=self.industry,
            event_impact=self.event_impact,
            macro_exposure=self.macro_exposure,
            evidence_refs=self.evidence_refs,
        )


class StockPriceData(Base):
    """股票历史价格数据（本地真实数据存储）"""

    __tablename__ = "stock_price_data"

    price_id = Column(Text, primary_key=True)
    code = Column(Text, nullable=False, index=True)  # 如 600519.SH
    date = Column(Text, nullable=False, index=True)  # 如 2024-05-01
    open = Column(Numeric, nullable=False)
    high = Column(Numeric, nullable=False)
    low = Column(Numeric, nullable=False)
    close = Column(Numeric, nullable=False)
    volume = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    data_source = Column(Text, nullable=False, default="manual")  # manual, csv
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


# =============================================================================
# Issue #42: AlphaFoundry v1 统一文档表
# =============================================================================


class DocumentV1DB(Base):
    """
    v1 统一文档表.

    Issue #42: 统一 document schema、JSON 字段规范与 PostgreSQL 建表设计
    """

    __tablename__ = "document_v1"

    doc_id = Column(Text, primary_key=True)

    # 核心字段
    doc_type = Column(Text, nullable=False, index=True)
    source_type = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)

    # 元数据 (JSON)
    doc_metadata = Column(JSON, nullable=False, default=dict)
    source_metadata = Column(JSON, nullable=False, default=dict)

    # 分类 (JSON)
    classification = Column(JSON, nullable=False, default=dict)

    # 质量评分 (JSON)
    quality = Column(JSON, nullable=False, default=dict)

    # 证据概况 (JSON)
    evidence_profile = Column(JSON, nullable=False, default=dict)

    # 时效性 (JSON)
    timeliness = Column(JSON, nullable=False, default=dict)

    # 处理状态 (JSON)
    processing = Column(JSON, nullable=False, default=dict)

    # 审核状态 (JSON)
    review = Column(JSON, nullable=False, default=dict)

    # 额外字段
    extra = Column(JSON, nullable=False, default=dict)

    # 来源关联
    source_name = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    language = Column(Text, nullable=False, default="zh")
    content_hash = Column(Text, nullable=True, index=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        """从 Pydantic 契约创建 ORM 对象"""
        return cls(
            doc_id=contract.doc_id,
            doc_type=contract.doc_type.value,
            source_type=contract.source_type.value,
            title=contract.title,
            summary=contract.summary,
            content=contract.content,
            doc_metadata=contract.doc_metadata,
            source_metadata=contract.source_metadata,
            classification=contract.classification.model_dump() if contract.classification else {},
            quality=contract.quality.model_dump() if contract.quality else {},
            evidence_profile=(
                contract.evidence_profile.model_dump() if contract.evidence_profile else {}
            ),
            timeliness=contract.timeliness.model_dump(mode="json") if contract.timeliness else {},
            processing=contract.processing.model_dump(mode="json") if contract.processing else {},
            review=contract.review.model_dump() if contract.review else {},
            extra=contract.extra,
            source_name=contract.source_name,
            source_url=contract.source_url,
            language=contract.language,
            content_hash=contract.content_hash,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )

    def to_contract(self):
        """转换为 Pydantic 契约"""
        from core.contracts import (
            DocType,
            DocumentClassification,
            DocumentEvidenceProfile,
            DocumentProcessingMeta,
            DocumentQuality,
            DocumentReview,
            DocumentTimeliness,
            DocumentV1,
            SourceType,
        )

        return DocumentV1(
            doc_id=self.doc_id,
            doc_type=DocType(self.doc_type),
            source_type=SourceType(self.source_type),
            title=self.title,
            summary=self.summary,
            content=self.content,
            doc_metadata=self.doc_metadata,
            source_metadata=self.source_metadata,
            classification=(
                DocumentClassification(**self.classification)
                if self.classification
                else DocumentClassification()
            ),
            quality=DocumentQuality(**self.quality) if self.quality else DocumentQuality(),
            evidence_profile=(
                DocumentEvidenceProfile(**self.evidence_profile)
                if self.evidence_profile
                else DocumentEvidenceProfile()
            ),
            timeliness=(
                DocumentTimeliness(**self.timeliness) if self.timeliness else DocumentTimeliness()
            ),
            processing=(
                DocumentProcessingMeta(**self.processing)
                if self.processing
                else DocumentProcessingMeta()
            ),
            review=DocumentReview(**self.review) if self.review else DocumentReview(),
            extra=self.extra,
            source_name=self.source_name,
            source_url=self.source_url,
            language=self.language,
            content_hash=self.content_hash,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DocumentChunkV1DB(Base):
    """
    文档分块表.

    Issue #42: document_chunks 表
    """

    __tablename__ = "document_chunk_v1"

    chunk_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(Text, nullable=False, default="paragraph")
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)

    # 语义信息
    topics = Column(JSON, nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    summary = Column(Text, nullable=True)
    embedding = Column(Text, nullable=True)

    # 元数据
    chunk_metadata = Column(JSON, nullable=False, default=dict, name="metadata")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            chunk_id=contract.chunk_id,
            doc_id=contract.doc_id,
            chunk_index=contract.chunk_index,
            chunk_type=contract.chunk_type,
            title=contract.title,
            content=contract.content,
            start_offset=contract.start_offset,
            end_offset=contract.end_offset,
            token_count=contract.token_count,
            topics=contract.topics,
            entities=contract.entities,
            summary=contract.summary,
            embedding=contract.embedding,
            chunk_metadata=contract.metadata,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import DocumentChunkV1

        return DocumentChunkV1(
            chunk_id=self.chunk_id,
            doc_id=self.doc_id,
            chunk_index=self.chunk_index,
            chunk_type=self.chunk_type,
            title=self.title,
            content=self.content,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            token_count=self.token_count,
            topics=self.topics,
            entities=self.entities,
            summary=self.summary,
            embedding=self.embedding,
            metadata=self.chunk_metadata,
            created_at=self.created_at,
        )


class DocumentTagV1DB(Base):
    """
    文档标签表.

    Issue #42: document_tags 表
    """

    __tablename__ = "document_tag_v1"

    tag_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=False, index=True)
    tag = Column(Text, nullable=False, index=True)
    tag_type = Column(Text, nullable=False, default="topic")
    confidence = Column(Numeric, nullable=True)
    source = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            tag_id=contract.tag_id,
            doc_id=contract.doc_id,
            tag=contract.tag,
            tag_type=contract.tag_type,
            confidence=contract.confidence,
            source=contract.source,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import DocumentTagV1

        return DocumentTagV1(
            tag_id=self.tag_id,
            doc_id=self.doc_id,
            tag=self.tag,
            tag_type=self.tag_type,
            confidence=float(self.confidence) if self.confidence is not None else None,
            source=self.source,
            created_at=self.created_at,
        )


class DocumentSummaryV1DB(Base):
    """
    文档摘要表.

    Issue #42: document_summaries 表
    """

    __tablename__ = "document_summary_v1"

    summary_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=False, index=True)
    summary_type = Column(Text, nullable=False, default="short")
    summary = Column(Text, nullable=False)
    bullet_points = Column(JSON, nullable=False, default=list)
    generator_version = Column(Text, nullable=True)
    quality_score = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            summary_id=contract.summary_id,
            doc_id=contract.doc_id,
            summary_type=contract.summary_type,
            summary=contract.summary,
            bullet_points=contract.bullet_points,
            generator_version=contract.generator_version,
            quality_score=contract.quality_score,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import DocumentSummaryV1

        return DocumentSummaryV1(
            summary_id=self.summary_id,
            doc_id=self.doc_id,
            summary_type=self.summary_type,
            summary=self.summary,
            bullet_points=self.bullet_points,
            generator_version=self.generator_version,
            quality_score=float(self.quality_score) if self.quality_score is not None else None,
            created_at=self.created_at,
        )


class EntityMentionV1DB(Base):
    """
    实体提及表.

    Issue #42: document_entity_mentions 表
    """

    __tablename__ = "document_entity_mention_v1"

    mention_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=False, index=True)
    chunk_id = Column(Text, nullable=True, index=True)
    entity_id = Column(Text, ForeignKey("entity.entity_id"), nullable=True, index=True)
    entity_name = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False, index=True)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    context = Column(Text, nullable=True)
    confidence = Column(Numeric, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            mention_id=contract.mention_id,
            doc_id=contract.doc_id,
            chunk_id=contract.chunk_id,
            entity_id=contract.entity_id,
            entity_name=contract.entity_name,
            entity_type=contract.entity_type,
            start_offset=contract.start_offset,
            end_offset=contract.end_offset,
            context=contract.context,
            confidence=contract.confidence,
            is_primary=contract.is_primary,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import EntityMentionV1

        return EntityMentionV1(
            mention_id=self.mention_id,
            doc_id=self.doc_id,
            chunk_id=self.chunk_id,
            entity_id=self.entity_id,
            entity_name=self.entity_name,
            entity_type=self.entity_type,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            context=self.context,
            confidence=float(self.confidence) if self.confidence is not None else None,
            is_primary=self.is_primary,
            created_at=self.created_at,
        )


class DocumentEventV1DB(Base):
    """
    文档事件表 - 与现有 canonical_event 集成.

    Issue #42: events 表
    """

    __tablename__ = "document_event_v1"

    event_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=False, index=True)
    canonical_event_id = Column(
        Text, ForeignKey("canonical_event.event_id"), nullable=True, index=True
    )
    event_type = Column(Text, nullable=False, index=True)
    event_time = Column(DateTime(timezone=True), nullable=True)
    subject_entity = Column(Text, nullable=True)
    object_entity = Column(Text, nullable=True)
    event_summary = Column(Text, nullable=False)
    impact_direction = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    confidence = Column(Numeric, nullable=True)
    extra = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            event_id=contract.event_id,
            doc_id=contract.doc_id,
            canonical_event_id=contract.canonical_event_id,
            event_type=contract.event_type,
            event_time=contract.event_time,
            subject_entity=contract.subject_entity,
            object_entity=contract.object_entity,
            event_summary=contract.event_summary,
            impact_direction=contract.impact_direction,
            evidence_text=contract.evidence_text,
            confidence=contract.confidence,
            extra=contract.extra,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import DocumentEventV1

        return DocumentEventV1(
            event_id=self.event_id,
            doc_id=self.doc_id,
            canonical_event_id=self.canonical_event_id,
            event_type=self.event_type,
            event_time=self.event_time,
            subject_entity=self.subject_entity,
            object_entity=self.object_entity,
            event_summary=self.event_summary,
            impact_direction=self.impact_direction,
            evidence_text=self.evidence_text,
            confidence=float(self.confidence) if self.confidence is not None else None,
            extra=self.extra,
            created_at=self.created_at,
        )


class CrawlRunV1DB(Base):
    """
    抓取运行记录表.

    Issue #42: crawl_runs 表
    """

    __tablename__ = "crawl_run_v1"

    run_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    error_log = Column(Text, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            run_id=contract.run_id,
            source_type=contract.source_type.value,
            status=contract.status,
            started_at=contract.started_at,
            completed_at=contract.completed_at,
            success_count=contract.success_count,
            failure_count=contract.failure_count,
            skipped_count=contract.skipped_count,
            error_log=contract.error_log,
            config=contract.config,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import CrawlRunV1, SourceType

        return CrawlRunV1(
            run_id=self.run_id,
            source_type=SourceType(self.source_type),
            status=self.status,
            started_at=self.started_at,
            completed_at=self.completed_at,
            success_count=self.success_count,
            failure_count=self.failure_count,
            skipped_count=self.skipped_count,
            error_log=self.error_log,
            config=self.config,
            created_at=self.created_at,
        )


class SourceCursorV1DB(Base):
    """
    来源游标表 - 用于增量抓取.

    Issue #42: source_cursors 表
    """

    __tablename__ = "source_cursor_v1"

    cursor_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True)
    last_successful_crawl_time = Column(DateTime(timezone=True), nullable=True)
    last_source_doc_id = Column(Text, nullable=True)
    lookback_window_minutes = Column(Integer, nullable=False, default=60)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    is_paused = Column(Boolean, nullable=False, default=False)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            cursor_id=contract.cursor_id,
            source_type=contract.source_type.value,
            source_name=contract.source_name,
            last_successful_crawl_time=contract.last_successful_crawl_time,
            last_source_doc_id=contract.last_source_doc_id,
            lookback_window_minutes=contract.lookback_window_minutes,
            consecutive_failures=contract.consecutive_failures,
            is_paused=contract.is_paused,
            config=contract.config,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )

    def to_contract(self):
        from core.contracts import SourceCursorV1, SourceType

        return SourceCursorV1(
            cursor_id=self.cursor_id,
            source_type=SourceType(self.source_type),
            source_name=self.source_name,
            last_successful_crawl_time=self.last_successful_crawl_time,
            last_source_doc_id=self.last_source_doc_id,
            lookback_window_minutes=self.lookback_window_minutes,
            consecutive_failures=self.consecutive_failures,
            is_paused=self.is_paused,
            config=self.config,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ReportRunV1DB(Base):
    """
    报告运行记录表.

    Issue #42: report_runs 表
    """

    __tablename__ = "report_run_v1"

    run_id = Column(Text, primary_key=True)
    report_type = Column(Text, nullable=False, index=True)
    report_template = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="pending")
    config = Column(JSON, nullable=False, default=dict)
    document_ids = Column(JSON, nullable=False, default=list)
    signal_ids = Column(JSON, nullable=False, default=list)
    output_path = Column(Text, nullable=True)
    error_log = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}

    @classmethod
    def from_contract(cls, contract):
        return cls(
            run_id=contract.run_id,
            report_type=contract.report_type,
            report_template=contract.report_template,
            status=contract.status,
            config=contract.config,
            document_ids=contract.document_ids,
            signal_ids=contract.signal_ids,
            output_path=contract.output_path,
            error_log=contract.error_log,
            started_at=contract.started_at,
            completed_at=contract.completed_at,
            created_at=contract.created_at,
        )

    def to_contract(self):
        from core.contracts import ReportRunV1

        return ReportRunV1(
            run_id=self.run_id,
            report_type=self.report_type,
            report_template=self.report_template,
            status=self.status,
            config=self.config,
            document_ids=self.document_ids,
            signal_ids=self.signal_ids,
            output_path=self.output_path,
            error_log=self.error_log,
            started_at=self.started_at,
            completed_at=self.completed_at,
            created_at=self.created_at,
        )


class ResearchRunDB(Base):
    """Persistent source of truth for an evidence-first research execution."""

    __tablename__ = "research_run"

    run_id = Column(Text, primary_key=True)
    template_key = Column(Text, nullable=False, index=True)
    target_id = Column(Text, nullable=False, index=True)
    subject_type = Column(Text, nullable=False, default="security", index=True)
    subject_payload = Column(JSON, nullable=False, default=dict)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    question = Column(Text, nullable=False)
    attachment_refs = Column(JSON, nullable=False, default=list)
    evidence_inputs = Column(JSON, nullable=False, default=list)
    source_plan = Column(JSON, nullable=False, default=dict)
    status = Column(Text, nullable=False, default="draft", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    resume_from = Column(Text, nullable=True)
    blocked_reasons = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ResearchTaskDB(Base):
    """Durable task snapshot for a ResearchRun graph execution."""

    __tablename__ = "research_task"

    task_id = Column(Text, primary_key=True)
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=False, index=True)
    task_key = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    resume_from = Column(Text, nullable=True)
    state_snapshot = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResearchArtifactDB(Base):
    """Immutable materialized output of a research stage."""

    __tablename__ = "research_artifact"

    artifact_id = Column(Text, primary_key=True)
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=False, index=True)
    artifact_type = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("run_id", "artifact_type", name="uq_research_artifact_type"),
    )


class ResearchClaimDB(Base):
    """Claim-to-evidence association created by a ResearchRun."""

    __tablename__ = "research_claim"

    claim_id = Column(Text, primary_key=True)
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=False, index=True)
    category = Column(Text, nullable=False)
    text = Column(Text, nullable=False)
    evidence_refs = Column(JSON, nullable=False, default=list)
    numeric_context = Column(JSON, nullable=False, default=dict)
    conflict_status = Column(Text, nullable=False, default="clear")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResearchQualityGateDB(Base):
    """Latest quality-gate evaluation for a ResearchRun."""

    __tablename__ = "research_quality_gate"

    gate_id = Column(Text, primary_key=True)
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=False, index=True)
    gate_key = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False)
    severity = Column(Text, nullable=False, default="error")
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    checked_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("run_id", "gate_key", name="uq_research_quality_gate"),)


# =============================================================================
# AF-AUTO-002-07: PDF 元数据表与转换结果表
# =============================================================================


class PDFArtifactV1DB(Base):
    """
    PDF 制品表 - 存储下载的 PDF 文件元数据.

    AF-AUTO-002-05: ZQ PDF First Report Ingestion
    """

    __tablename__ = "pdf_artifact_v1"

    pdf_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=True, index=True)
    source_obj_id = Column(Text, nullable=True, index=True)

    # 文件信息
    file_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash_sha256 = Column(Text, nullable=False, index=True)
    file_hash_md5 = Column(Text, nullable=True)

    # 来源信息
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    source_broker = Column(Text, nullable=True)
    source_author = Column(Text, nullable=True)
    source_publish_date = Column(DateTime(timezone=True), nullable=True)

    # 抓取元数据
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False)
    fetch_config = Column(JSON, nullable=False, default=dict)
    fetch_strategy = Column(Text, nullable=True)
    fetch_duration_ms = Column(Integer, nullable=True)

    # 解析元数据
    parse_version = Column(Text, nullable=True)
    parse_config = Column(JSON, nullable=False, default=dict)
    parse_status = Column(Text, nullable=False, default="pending")
    parse_error = Column(Text, nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)

    # 额外元数据
    pdf_metadata = Column(JSON, nullable=False, default=dict)  # PDF 自身元数据
    extra = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class PDFConversionV1DB(Base):
    """
    PDF 转换结果表 - 存储 PDF 转换为 Markdown 或文本的结果.

    AF-AUTO-002-06: PDF to Markdown Conversion Pipeline
    """

    __tablename__ = "pdf_conversion_v1"

    conversion_id = Column(Text, primary_key=True)
    pdf_id = Column(Text, ForeignKey("pdf_artifact_v1.pdf_id"), nullable=False, index=True)

    # 转换策略信息
    conversion_strategy = Column(Text, nullable=False, index=True)
    strategy_version = Column(Text, nullable=True)
    strategy_config = Column(JSON, nullable=False, default=dict)

    # 转换结果
    markdown_path = Column(Text, nullable=True)
    markdown_content = Column(Text, nullable=True)  # 内联存储（小文件）
    raw_text_path = Column(Text, nullable=True)
    raw_text_content = Column(Text, nullable=True)  # 内联存储（小文件）

    # 转换统计
    page_count = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    conversion_duration_ms = Column(Integer, nullable=True)

    # 质量指标
    quality_score = Column(Numeric, nullable=True)
    has_tables = Column(Boolean, nullable=True)
    has_images = Column(Boolean, nullable=True)
    has_code_blocks = Column(Boolean, nullable=True)

    # 状态
    status = Column(Text, nullable=False, default="pending", index=True)
    error_log = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = {"extend_existing": True}


class CrawlStateV1DB(Base):
    """
    爬虫状态表 - 持久化存储爬虫状态、水位线、去重信息.

    AF-AUTO-002-03: Incremental Fetch Until Known
    """

    __tablename__ = "crawl_state_v1"

    state_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True, index=True)

    # 水位线信息
    watermark_id = Column(Text, nullable=True)
    watermark_timestamp = Column(DateTime(timezone=True), nullable=True)
    watermark_metadata = Column(JSON, nullable=False, default=dict)

    # 去重信息
    dedupe_key = Column(Text, nullable=True, index=True)
    dedupe_count = Column(Integer, nullable=False, default=0)

    # 爬虫统计
    total_fetched = Column(Integer, nullable=False, default=0)
    total_skipped = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)

    # 爬虫配置
    crawl_config = Column(JSON, nullable=False, default=dict)
    crawl_mode = Column(Text, nullable=False, default="incremental")  # full|incremental

    # 会话信息
    last_run_id = Column(Text, nullable=True)
    last_run_start = Column(DateTime(timezone=True), nullable=True)
    last_run_end = Column(DateTime(timezone=True), nullable=True)

    # 暂停控制
    is_paused = Column(Boolean, nullable=False, default=False)
    pause_reason = Column(Text, nullable=True)

    extra = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class ProcessedItemV1DB(Base):
    """
    已处理项目表 - 用于去重，支持快速检查项目是否已处理.

    AF-AUTO-002-03: Incremental Fetch Until Known
    """

    __tablename__ = "processed_item_v1"

    item_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True, index=True)

    # 项目元数据
    item_type = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)
    content_hash = Column(Text, nullable=True, index=True)

    # 处理信息
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    first_processed_at = Column(DateTime(timezone=True), nullable=True)
    process_count = Column(Integer, nullable=False, default=1)

    # 来源关联
    crawl_run_id = Column(Text, nullable=True, index=True)
    doc_id = Column(Text, nullable=True, index=True)

    extra = Column(JSON, nullable=False, default=dict)

    __table_args__ = {"extend_existing": True}


# =============================================================================
# AF-AUTO-007: 市场结构化事实表
# =============================================================================


class StockMasterDB(Base):
    """股票基础信息表"""

    __tablename__ = "stock_master"

    symbol = Column(Text, primary_key=True)
    raw_code = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    exchange = Column(Text, nullable=True)
    market = Column(Text, nullable=True)
    industry_level1 = Column(Text, nullable=True)
    industry_level2 = Column(Text, nullable=True)
    industry_level3 = Column(Text, nullable=True)
    list_date = Column(DateTime(timezone=True), nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class StockDailyBarDB(Base):
    """日行情表"""

    __tablename__ = "stock_daily_bar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False, index=True)
    trade_date = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=True)
    volume = Column(Numeric, nullable=True)
    amount = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_date",
            "source",
            name="uq_stock_daily_bar_symbol_date_source",
        ),
        {"extend_existing": True},
    )


class StockQuoteSnapshotDB(Base):
    """实时行情快照表"""

    __tablename__ = "stock_quote_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False, index=True)
    quote_time = Column(DateTime(timezone=True), nullable=False, index=True)
    last_price = Column(Numeric, nullable=True)
    change_pct = Column(Numeric, nullable=True)
    volume = Column(Numeric, nullable=True)
    amount = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    pe = Column(Numeric, nullable=True)
    pb = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class StockFinancialMetricDB(Base):
    """财务指标表"""

    __tablename__ = "stock_financial_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False, index=True)
    report_date = Column(DateTime(timezone=True), nullable=False, index=True)
    report_type = Column(Text, nullable=True)
    total_revenue = Column(Numeric, nullable=True)
    net_profit = Column(Numeric, nullable=True)
    total_assets = Column(Numeric, nullable=True)
    total_liabilities = Column(Numeric, nullable=True)
    equity = Column(Numeric, nullable=True)
    roe = Column(Numeric, nullable=True)
    roa = Column(Numeric, nullable=True)
    gross_margin = Column(Numeric, nullable=True)
    net_margin = Column(Numeric, nullable=True)
    debt_ratio = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class StockValuationDB(Base):
    """估值指标表"""

    __tablename__ = "stock_valuation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False, index=True)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    pe_ttm = Column(Numeric, nullable=True)
    pe_dynamic = Column(Numeric, nullable=True)
    pb = Column(Numeric, nullable=True)
    ps = Column(Numeric, nullable=True)
    market_cap = Column(Numeric, nullable=True)
    float_market_cap = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class StockShareholderDB(Base):
    """股东信息表"""

    __tablename__ = "stock_shareholder"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False, index=True)
    report_date = Column(DateTime(timezone=True), nullable=False, index=True)
    holder_name = Column(Text, nullable=False)
    holder_rank = Column(Integer, nullable=True)
    shares = Column(Numeric, nullable=True)
    holding_pct = Column(Numeric, nullable=True)
    holder_type = Column(Text, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class IndexProviderDB(Base):
    """指数发布方表"""

    __tablename__ = "index_provider"

    provider_code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    official_site = Column(Text, nullable=True)
    source_priority = Column(Integer, nullable=False, default=100)
    raw_payload = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class IndexMasterDB(Base):
    """指数主数据表"""

    __tablename__ = "index_master"

    index_id = Column(Text, primary_key=True)
    provider_code = Column(Text, nullable=False, index=True)
    official_code = Column(Text, nullable=False, index=True)
    wind_code = Column(Text, nullable=True, index=True)
    name_cn = Column(Text, nullable=False)
    name_en = Column(Text, nullable=True)
    market = Column(Text, nullable=True)
    currency = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    launch_date = Column(DateTime(timezone=True), nullable=True)
    base_date = Column(DateTime(timezone=True), nullable=True)
    base_value = Column(Numeric, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    raw_payload = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "provider_code",
            "official_code",
            name="uq_index_master_provider_official_code",
        ),
        {"extend_existing": True},
    )


class IndexComponentSnapshotDB(Base):
    """指数成分权重快照表"""

    __tablename__ = "index_component_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_id = Column(Text, nullable=False, index=True)
    index_symbol = Column(Text, nullable=False, index=True)
    provider_code = Column(Text, nullable=False, index=True)
    component_symbol = Column(Text, nullable=False, index=True)
    component_name = Column(Text, nullable=True)
    market = Column(Text, nullable=True)
    weight = Column(Numeric, nullable=True)
    weight_pct = Column(Numeric, nullable=True)
    rank = Column(Integer, nullable=True)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    trade_date = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(Text, nullable=False, default="unknown")
    source_scope = Column(Text, nullable=False, default="full")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "index_id",
            "trade_date",
            "component_symbol",
            "source",
            name="uq_index_component_snapshot_identity",
        ),
        {"extend_existing": True},
    )


class ETFMasterDB(Base):
    """ETF 主数据表"""

    __tablename__ = "etf_master"

    etf_symbol = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    exchange = Column(Text, nullable=True)
    market = Column(Text, nullable=True)
    fund_manager = Column(Text, nullable=True)
    listed_date = Column(DateTime(timezone=True), nullable=True)
    currency = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


class IndexETFLinkDB(Base):
    """指数与 ETF 跟踪关系表"""

    __tablename__ = "index_etf_link"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_id = Column(Text, nullable=False, index=True)
    etf_symbol = Column(Text, nullable=False, index=True)
    tracking_role = Column(Text, nullable=False, default="tracking")
    link_source = Column(Text, nullable=False, default="unknown")
    confidence = Column(Numeric, nullable=True)
    raw_payload = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "index_id",
            "etf_symbol",
            "link_source",
            name="uq_index_etf_link_identity",
        ),
        {"extend_existing": True},
    )


class ETFDailyMetricDB(Base):
    """ETF 日度规模与资金流指标表"""

    __tablename__ = "etf_daily_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    etf_symbol = Column(Text, nullable=False, index=True)
    trade_date = Column(DateTime(timezone=True), nullable=False, index=True)
    nav = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=True)
    shares_outstanding = Column(Numeric, nullable=True)
    aum = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    premium_discount_pct = Column(Numeric, nullable=True)
    net_flow_amount = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="unknown")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "etf_symbol",
            "trade_date",
            "source",
            name="uq_etf_daily_metric_symbol_date_source",
        ),
        {"extend_existing": True},
    )


class ETLRunDB(Base):
    """ETL 运行记录表"""

    __tablename__ = "etl_run"

    run_id = Column(Text, primary_key=True)
    job_name = Column(Text, nullable=False, index=True)
    source = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    items_fetched = Column(Integer, nullable=False, default=0)
    items_normalized = Column(Integer, nullable=False, default=0)
    items_saved = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = {"extend_existing": True}


# ─── Wind Excel 数据表 ────────────────────────────────


class WindConsensusEstimateDB(Base):
    """Wind 一致预期数据"""

    __tablename__ = "wind_consensus_estimate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False)
    trade_date = Column(DateTime(timezone=True), nullable=False)
    cons_net_profit = Column(Numeric, nullable=True)
    cons_eps = Column(Numeric, nullable=True)
    cons_revenue = Column(Numeric, nullable=True)
    target_price = Column(Numeric, nullable=True)
    rating = Column(Numeric, nullable=True)
    rating_num = Column(Integer, nullable=True)
    source = Column(Text, nullable=False, default="wind")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class WindMarginTradingDB(Base):
    """Wind 融资融券数据"""

    __tablename__ = "wind_margin_trading"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False)
    trade_date = Column(DateTime(timezone=True), nullable=False)
    margin_balance = Column(Numeric, nullable=True)
    short_balance = Column(Numeric, nullable=True)
    margin_buy = Column(Numeric, nullable=True)
    margin_repay = Column(Numeric, nullable=True)
    short_sell_vol = Column(Numeric, nullable=True)
    short_repay_vol = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="wind")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class WindBlockTradeDB(Base):
    """Wind 龙虎榜数据"""

    __tablename__ = "wind_block_trade"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False)
    trade_date = Column(DateTime(timezone=True), nullable=False)
    lhb_buy_amt = Column(Numeric, nullable=True)
    lhb_sell_amt = Column(Numeric, nullable=True)
    lhb_buy_seat = Column(Text, nullable=True)
    lhb_sell_seat = Column(Text, nullable=True)
    source = Column(Text, nullable=False, default="wind")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class WindDailyBarDB(Base):
    """Wind 日行情数据（含 Wind 独家字段：adj_close, adj_factor, vwap）"""

    __tablename__ = "wind_daily_bar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(Text, nullable=False)
    trade_date = Column(DateTime(timezone=True), nullable=False)
    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=True)
    volume = Column(Numeric, nullable=True)
    amount = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    adj_close = Column(Numeric, nullable=True)
    adj_factor = Column(Numeric, nullable=True)
    vwap = Column(Numeric, nullable=True)
    pct_change = Column(Numeric, nullable=True)
    amplitude = Column(Numeric, nullable=True)
    source = Column(Text, nullable=False, default="wind")
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# ─── Dynamic Factor Store ─────────────────────────────────


class FactorDefinitionDB(Base):
    """因子元数据定义"""

    __tablename__ = "factor_definition"

    factor_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    direction = Column(Text, nullable=False, default="positive")
    description = Column(Text, nullable=False, default="")
    version = Column(Text, nullable=False, default="v1")
    horizon_days = Column(Integer, nullable=True)
    refresh_frequency = Column(Text, nullable=False, default="1d")
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class FactorValueDB(Base):
    """点时因子观察值"""

    __tablename__ = "factor_value"
    __table_args__ = (
        UniqueConstraint(
            "factor_id",
            "subject_id",
            "as_of_date",
            name="uq_factor_value_factor_subject_date",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(Text, nullable=False)
    subject_id = Column(Text, nullable=False)
    as_of_date = Column(Date, nullable=False)
    value = Column(Numeric, nullable=True)
    available_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(Text, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class FactorEvaluationDB(Base):
    """因子评估指标"""

    __tablename__ = "factor_evaluation"
    __table_args__ = (
        UniqueConstraint(
            "factor_id",
            "as_of_date",
            "horizon_days",
            name="uq_factor_eval_factor_date_horizon",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(Text, nullable=False)
    as_of_date = Column(Date, nullable=True)
    horizon_days = Column(Integer, nullable=False, default=20)
    sample_size = Column(Integer, nullable=False, default=0)
    coverage = Column(Float, nullable=False, default=0.0)
    ic = Column(Float, nullable=False, default=0.0)
    rank_ic = Column(Float, nullable=False, default=0.0)
    decile_spread = Column(Float, nullable=False, default=0.0)
    meta = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class DynamicFactorWeightDB(Base):
    """动态因子权重快照"""

    __tablename__ = "dynamic_factor_weight"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date",
            "metric",
            name="uq_dynamic_weight_date_metric",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    as_of_date = Column(Date, nullable=True)
    lookback_periods = Column(Integer, nullable=False, default=12)
    metric = Column(Text, nullable=False, default="rank_ic")
    weights = Column(JSON, nullable=False, default=dict)
    raw_scores = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


# =============================================================================
# AlphaFoundry x LSH merged platform: shared fact kernel and product modules
# =============================================================================


class AssetRegistryDB(Base):
    """Canonical identity that maps to existing asset fact tables."""

    __tablename__ = "asset_registry"

    asset_id = Column(Text, primary_key=True)
    asset_type = Column(Text, nullable=False, index=True)
    canonical_name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active", index=True)
    registry_metadata = Column(JSON, nullable=False, default=dict, name="metadata")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AssetIdentifierDB(Base):
    """Time-bounded vendor or market code for a canonical asset."""

    __tablename__ = "asset_identifier"

    identifier_id = Column(Text, primary_key=True)
    asset_id = Column(
        Text, ForeignKey("asset_registry.asset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheme = Column(Text, nullable=False, index=True)
    value = Column(Text, nullable=False, index=True)
    market = Column(Text, nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False, index=True)
    valid_to = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        UniqueConstraint(
            "scheme",
            "value",
            "market",
            "valid_from",
            name="uq_asset_identifier_identity",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_asset_identifier_valid_window",
        ),
        ExcludeConstraint(
            (scheme, "="),
            (value, "="),
            (market, "="),
            (func.tstzrange(valid_from, valid_to, "[)"), "&&"),
            name="ex_asset_identifier_no_overlap",
            using="gist",
        ).ddl_if(dialect="postgresql"),
    )


class ThemeObservationDB(Base):
    """Only persisted fact table shared by every Research Pack."""

    __tablename__ = "theme_observation"
    __table_args__ = (
        UniqueConstraint(
            "pack_key",
            "dataset_key",
            "row_identity",
            "source_hash",
            name="uq_theme_observation_source_row",
        ),
    )

    observation_id = Column(Text, primary_key=True)
    pack_key = Column(Text, nullable=False, index=True)
    dataset_key = Column(Text, nullable=False, index=True)
    row_identity = Column(Text, nullable=False)
    subject_ref = Column(Text, nullable=False, index=True)
    metric_key = Column(Text, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    unit = Column(Text, nullable=True)
    missing_reason = Column(Text, nullable=True)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    available_at = Column(DateTime(timezone=True), nullable=False, index=True)
    source_refs = Column(JSON, nullable=False, default=list)
    freshness_status = Column(Text, nullable=False, index=True)
    quality_flags = Column(JSON, nullable=False, default=list)
    source_hash = Column(Text, nullable=False, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ScheduledJobDB(Base):
    """PostgreSQL-coordinated single-flight scheduled work."""

    __tablename__ = "scheduled_job"
    __table_args__ = (
        UniqueConstraint("owner", "idempotency_key", name="uq_scheduled_job_idempotency"),
        CheckConstraint(
            "allow_concurrent = false",
            name="ck_scheduled_job_allow_concurrent_false",
        ),
        CheckConstraint(
            "coalesce_policy = 'latest'",
            name="ck_scheduled_job_coalesce_latest",
        ),
        CheckConstraint(
            "(lease_owner IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_scheduled_job_lease_pair",
        ),
    )

    job_id = Column(Text, primary_key=True)
    owner = Column(Text, nullable=False, index=True)
    job_type = Column(Text, nullable=False, index=True)
    idempotency_key = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="idle", index=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    allow_concurrent = Column(Boolean, nullable=False, default=False)
    coalesce_policy = Column(Text, nullable=False, default="latest")
    lease_owner = Column(Text, nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    attempt = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False, default=dict)
    last_error_code = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class DomainEventDB(Base):
    """Durable event authority; in-process buses are delivery adapters only."""

    __tablename__ = "domain_event"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_domain_event_idempotency"),
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "sequence",
            name="uq_domain_event_aggregate_sequence",
        ),
    )

    event_id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False, index=True)
    aggregate_type = Column(Text, nullable=False, index=True)
    aggregate_id = Column(Text, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    payload_ref = Column(Text, nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ThemePackDB(Base):
    """Versioned manifest and validation result for a Research Pack."""

    __tablename__ = "theme_pack"
    __table_args__ = (UniqueConstraint("pack_key", "version", name="uq_theme_pack_version"),)

    pack_id = Column(Text, primary_key=True)
    pack_key = Column(Text, nullable=False, index=True)
    version = Column(Text, nullable=False)
    compatibility_version = Column(Text, nullable=False)
    status = Column(Text, nullable=False, index=True)
    manifest = Column(JSON, nullable=False, default=dict)
    content_hash = Column(Text, nullable=False, index=True)
    validation_result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class MarketHomeSnapshotDB(Base):
    """Immutable market-home section snapshot for historical reads."""

    __tablename__ = "market_home_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "trading_day",
            "snapshot_kind",
            "section_key",
            "formula_version",
            name="uq_market_home_snapshot_identity",
        ),
    )

    snapshot_id = Column(Text, primary_key=True)
    trading_day = Column(Date, nullable=False, index=True)
    snapshot_kind = Column(Text, nullable=False, index=True)
    section_key = Column(Text, nullable=False, index=True)
    formula_version = Column(Text, nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    available_at = Column(DateTime(timezone=True), nullable=False)
    source_refs = Column(JSON, nullable=False, default=list)
    freshness_status = Column(Text, nullable=False, index=True)
    quality_flags = Column(JSON, nullable=False, default=list)
    payload = Column(JSON, nullable=False, default=dict)
    input_fact_refs = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResearchWorkspaceDB(Base):
    """Project-isolated home for research sessions, runs, and notes."""

    __tablename__ = "research_workspace"

    workspace_id = Column(Text, primary_key=True)
    project_id = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    archived_at = Column(DateTime(timezone=True), nullable=True)


class ResearchSessionDB(Base):
    """Temporary or workspace-scoped persisted conversation."""

    __tablename__ = "research_session"
    __table_args__ = (
        CheckConstraint(
            "(mode = 'workspace' AND workspace_id IS NOT NULL "
            "AND length(trim(workspace_id)) > 0) OR "
            "(mode = 'temporary' AND workspace_id IS NULL)",
            name="ck_research_session_scope",
        ),
    )

    session_id = Column(Text, primary_key=True)
    workspace_id = Column(
        Text,
        ForeignKey("research_workspace.workspace_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=True, index=True)
    mode = Column(Text, nullable=False, index=True)
    status = Column(Text, nullable=False, default="active", index=True)
    idempotency_key = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResearchMessageDB(Base):
    """Idempotent message whose workspace scope is derived from its session."""

    __tablename__ = "research_message"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_research_message_idempotency"),
        CheckConstraint(
            "(content IS NOT NULL AND length(trim(content)) > 0 AND content_ref IS NULL) OR "
            "(content IS NULL AND content_ref IS NOT NULL "
            "AND length(trim(content_ref)) > 0)",
            name="ck_research_message_content_source",
        ),
    )

    message_id = Column(Text, primary_key=True)
    session_id = Column(
        Text,
        ForeignKey("research_session.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    content_ref = Column(Text, nullable=True)
    idempotency_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class RuntimeProviderDB(Base):
    """Research runtime capability and health declaration without secrets."""

    __tablename__ = "runtime_provider"

    provider_id = Column(Text, primary_key=True)
    provider_type = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    capabilities = Column(JSON, nullable=False, default=list)
    status = Column(Text, nullable=False, index=True)
    config_ref = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class SkillDefinitionDB(Base):
    """Versioned persisted SkillManifest."""

    __tablename__ = "skill_definition"
    __table_args__ = (UniqueConstraint("skill_key", "version", name="uq_skill_definition_version"),)

    skill_id = Column(Text, primary_key=True)
    skill_key = Column(Text, nullable=False, index=True)
    version = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="draft", index=True)
    manifest = Column(JSON, nullable=False, default=dict)
    allowed_tools = Column(JSON, nullable=False, default=list)
    content_hash = Column(Text, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AgentTeamDB(Base):
    """Supervisor-led Agent Team with persisted hard bounds."""

    __tablename__ = "agent_team"

    team_id = Column(Text, primary_key=True)
    workspace_id = Column(
        Text,
        ForeignKey("research_workspace.workspace_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(Text, nullable=False)
    supervisor_role = Column(Text, nullable=False)
    roles = Column(JSON, nullable=False, default=list)
    budget = Column(JSON, nullable=False, default=dict)
    skill_keys = Column(JSON, nullable=False, default=list)
    status = Column(Text, nullable=False, default="draft", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AgentScheduleDB(Base):
    """Team schedule delegating lease ownership to scheduled_job."""

    __tablename__ = "agent_schedule"
    __table_args__ = (
        CheckConstraint(
            "allow_concurrent = false",
            name="ck_agent_schedule_allow_concurrent_false",
        ),
        CheckConstraint(
            "coalesce_policy = 'latest'",
            name="ck_agent_schedule_coalesce_latest",
        ),
    )

    schedule_id = Column(Text, primary_key=True)
    team_id = Column(
        Text, ForeignKey("agent_team.team_id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_job_id = Column(Text, ForeignKey("scheduled_job.job_id"), nullable=True, index=True)
    cron_expression = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="active", index=True)
    allow_concurrent = Column(Boolean, nullable=False, default=False)
    coalesce_policy = Column(Text, nullable=False, default="latest")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class ResearchNoteDB(Base):
    """Immutable revision with exactly one Claim or paragraph source shape."""

    __tablename__ = "research_note"
    __table_args__ = (
        UniqueConstraint("workspace_id", "note_key", "revision", name="uq_research_note_revision"),
        CheckConstraint(
            "(source_kind = 'claim' AND claim_id IS NOT NULL AND run_id IS NULL "
            "AND paragraph_ref IS NULL) OR "
            "(source_kind = 'paragraph' AND claim_id IS NULL AND run_id IS NOT NULL "
            "AND paragraph_ref IS NOT NULL)",
            name="ck_research_note_source_shape",
        ),
    )

    note_id = Column(Text, primary_key=True)
    note_key = Column(Text, nullable=False)
    workspace_id = Column(
        Text,
        ForeignKey("research_workspace.workspace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(Text, ForeignKey("research_run.run_id"), nullable=True, index=True)
    claim_id = Column(Text, ForeignKey("research_claim.claim_id"), nullable=True, index=True)
    revision = Column(Integer, nullable=False)
    source_kind = Column(Text, nullable=False)
    paragraph_ref = Column(Text, nullable=True)
    summary = Column(Text, nullable=False)
    pinned = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class WatchlistDB(Base):
    """Named local-profile asset collection."""

    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_watchlist_profile_name"),)

    watchlist_id = Column(Text, primary_key=True)
    profile_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class WatchlistItemDB(Base):
    """Watchlist membership keyed by canonical asset identity."""

    __tablename__ = "watchlist_item"
    __table_args__ = (UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_item_asset"),)

    item_id = Column(Text, primary_key=True)
    watchlist_id = Column(
        Text, ForeignKey("watchlist.watchlist_id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id = Column(
        Text, ForeignKey("asset_registry.asset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False, default=0)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AlertRuleDB(Base):
    """Unit-aware deterministic alert rule for one canonical asset."""

    __tablename__ = "alert_rule"

    rule_id = Column(Text, primary_key=True)
    asset_id = Column(
        Text, ForeignKey("asset_registry.asset_id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_type = Column(Text, nullable=False, index=True)
    metric_key = Column(Text, nullable=False)
    operator = Column(Text, nullable=False)
    threshold = Column(JSON, nullable=False)
    unit = Column(Text, nullable=True)
    required_freshness = Column(Text, nullable=False, default="fresh")
    cooldown_seconds = Column(Integer, nullable=False, default=0)
    status = Column(Text, nullable=False, default="draft", index=True)
    state = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AlertEventDB(Base):
    """Persisted false-to-true alert edge and lifecycle."""

    __tablename__ = "alert_event"
    __table_args__ = (
        Index(
            "uq_alert_event_rule_active",
            "rule_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged')"),
            sqlite_where=text("status IN ('open', 'acknowledged')"),
        ),
    )

    event_id = Column(Text, primary_key=True)
    rule_id = Column(
        Text, ForeignKey("alert_rule.rule_id", ondelete="CASCADE"), nullable=False, index=True
    )
    observation_id = Column(Text, nullable=False, index=True)
    dedupe_key = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, default="open", index=True)
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class NotificationDB(Base):
    """Authoritative in-app notification with optional desktop delivery state."""

    __tablename__ = "notification"

    notification_id = Column(Text, primary_key=True)
    alert_event_id = Column(
        Text, ForeignKey("alert_event.event_id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending", index=True)
    delivery_metadata = Column(JSON, nullable=False, default=dict)
    delivery_claim_token = Column(Text, nullable=True)
    delivery_claimed_at = Column(DateTime(timezone=True), nullable=True)
    delivery_attempt = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
