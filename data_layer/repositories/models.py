from datetime import datetime, timezone

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
    date = Column(Text, nullable=False, index=True)   # 如 2024-05-01
    open = Column(Numeric, nullable=False)
    high = Column(Numeric, nullable=False)
    low = Column(Numeric, nullable=False)
    close = Column(Numeric, nullable=False)
    volume = Column(Numeric, nullable=True)
    turnover = Column(Numeric, nullable=True)
    data_source = Column(Text, nullable=False, default="manual")  # manual, csv
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        {'extend_existing': True}
    )


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

    __table_args__ = (
        {'extend_existing': True}
    )

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
            evidence_profile=contract.evidence_profile.model_dump() if contract.evidence_profile else {},
            timeliness=contract.timeliness.model_dump() if contract.timeliness else {},
            processing=contract.processing.model_dump() if contract.processing else {},
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
            DocumentV1, DocumentClassification, DocumentQuality,
            DocumentEvidenceProfile, DocumentTimeliness,
            DocumentProcessingMeta, DocumentReview,
            DocType, SourceType
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
            classification=DocumentClassification(**self.classification) if self.classification else DocumentClassification(),
            quality=DocumentQuality(**self.quality) if self.quality else DocumentQuality(),
            evidence_profile=DocumentEvidenceProfile(**self.evidence_profile) if self.evidence_profile else DocumentEvidenceProfile(),
            timeliness=DocumentTimeliness(**self.timeliness) if self.timeliness else DocumentTimeliness(),
            processing=DocumentProcessingMeta(**self.processing) if self.processing else DocumentProcessingMeta(),
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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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
    canonical_event_id = Column(Text, ForeignKey("canonical_event.event_id"), nullable=True, index=True)
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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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

    __table_args__ = (
        {'extend_existing': True}
    )

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

