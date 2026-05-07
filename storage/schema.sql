-- AlphaFoundry 数据库架构
-- PostgreSQL + pgvector

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 实体表
CREATE TABLE IF NOT EXISTS entity (
    entity_id TEXT PRIMARY KEY,
    canonical_id TEXT UNIQUE NOT NULL,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    vendor_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 源文档表
CREATE TABLE IF NOT EXISTS source_document (
    doc_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    title TEXT,
    published_at TIMESTAMPTZ,
    source_name TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    rights_ref TEXT,
    parser_version TEXT NOT NULL,
    object_uri TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 断言表
CREATE TABLE IF NOT EXISTS assertion (
    assertion_id TEXT PRIMARY KEY,
    subject_entity_id TEXT REFERENCES entity(entity_id),
    predicate TEXT NOT NULL,
    object_entity_id TEXT,
    object_value JSONB,
    observed_at TIMESTAMPTZ,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    confidence NUMERIC NOT NULL,
    source_doc_id TEXT REFERENCES source_document(doc_id),
    source_span JSONB NOT NULL,
    extractor_version TEXT NOT NULL,
    reviewer_status TEXT NOT NULL DEFAULT 'draft',
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    trace_ref TEXT,
    team_id TEXT,
    project_id TEXT
);

-- 规范事件表
CREATE TABLE IF NOT EXISTS canonical_event (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    event_time TIMESTAMPTZ,
    impact_direction TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    needs_review BOOLEAN NOT NULL DEFAULT true,
    source_doc_id TEXT REFERENCES source_document(doc_id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 推理追踪表
CREATE TABLE IF NOT EXISTS reasoning_trace (
    trace_id TEXT PRIMARY KEY,
    request_type TEXT NOT NULL,
    question TEXT NOT NULL,
    subject_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieved_doc_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieved_assertion_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    graph_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
    intermediate_hypotheses JSONB NOT NULL DEFAULT '[]'::jsonb,
    final_answer TEXT,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    total_latency_ms INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_entity_canonical_id ON entity(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_team_project ON entity(team_id, project_id);

CREATE INDEX IF NOT EXISTS idx_document_source_type ON source_document(source_type);
CREATE INDEX IF NOT EXISTS idx_document_published_at ON source_document(published_at);
CREATE INDEX IF NOT EXISTS idx_document_team_project ON source_document(team_id, project_id);
CREATE INDEX IF NOT EXISTS idx_document_embedding ON source_document USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_assertion_subject ON assertion(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_assertion_source ON assertion(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_assertion_status ON assertion(reviewer_status);
CREATE INDEX IF NOT EXISTS idx_assertion_team_project ON assertion(team_id, project_id);

CREATE INDEX IF NOT EXISTS idx_event_source ON canonical_event(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_event_time ON canonical_event(event_time);
CREATE INDEX IF NOT EXISTS idx_event_team_project ON canonical_event(team_id, project_id);

CREATE INDEX IF NOT EXISTS idx_trace_request_type ON reasoning_trace(request_type);
CREATE INDEX IF NOT EXISTS idx_trace_created_at ON reasoning_trace(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trace_team_project ON reasoning_trace(team_id, project_id);

-- 资产分析快照表
CREATE TABLE IF NOT EXISTS asset_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    financial JSONB NOT NULL DEFAULT '{}'::jsonb,
    fund_flow JSONB NOT NULL DEFAULT '{}'::jsonb,
    price_volume JSONB NOT NULL DEFAULT '{}'::jsonb,
    valuation JSONB NOT NULL DEFAULT '{}'::jsonb,
    shareholder JSONB NOT NULL DEFAULT '{}'::jsonb,
    industry JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_impact JSONB NOT NULL DEFAULT '[]'::jsonb,
    macro_exposure JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asset_snapshot_canonical_id ON asset_snapshot(canonical_id);
CREATE INDEX IF NOT EXISTS idx_asset_snapshot_as_of ON asset_snapshot(as_of);
CREATE INDEX IF NOT EXISTS idx_asset_snapshot_canonical_as_of ON asset_snapshot(canonical_id, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_asset_snapshot_team_project ON asset_snapshot(team_id, project_id);

-- 时间化产业链关系表
CREATE TABLE IF NOT EXISTS temporal_relation (
    relation_id TEXT PRIMARY KEY,
    from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    strength NUMERIC NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    chain_position TEXT,
    industry TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_temporal_relation_from_entity ON temporal_relation(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_temporal_relation_to_entity ON temporal_relation(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_temporal_relation_type ON temporal_relation(relationship_type);
CREATE INDEX IF NOT EXISTS idx_temporal_relation_industry ON temporal_relation(industry);
CREATE INDEX IF NOT EXISTS idx_temporal_relation_valid_period ON temporal_relation(valid_from, valid_to);

-- 产业链表
CREATE TABLE IF NOT EXISTS industry_chain (
    chain_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    nodes JSONB NOT NULL,
    relations JSONB NOT NULL,
    as_of TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_industry_chain_industry ON industry_chain(industry);
CREATE INDEX IF NOT EXISTS idx_industry_chain_as_of ON industry_chain(as_of);

-- 更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- entity 表更新触发器
CREATE TRIGGER update_entity_updated_at BEFORE UPDATE ON entity
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- alpha_signal 表更新触发器
CREATE TRIGGER update_alpha_signal_updated_at BEFORE UPDATE ON alpha_signal
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Alpha 信号表
CREATE TABLE IF NOT EXISTS alpha_signal (
    signal_id TEXT PRIMARY KEY,
    discriminator TEXT NOT NULL DEFAULT 'alpha_signal',
    subject_id TEXT NOT NULL,
    horizon TEXT NOT NULL,
    thesis TEXT NOT NULL,
    score NUMERIC NOT NULL,
    confidence NUMERIC NOT NULL,
    scenario_refs JSONB NOT NULL DEFAULT '[]',
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'research_only',
    event_id TEXT,
    event_type TEXT,
    event_time TIMESTAMPTZ,
    impact_path JSONB NOT NULL DEFAULT '[]',
    industry_impacts JSONB NOT NULL DEFAULT '[]',
    bullish_companies JSONB NOT NULL DEFAULT '[]',
    bearish_companies JSONB NOT NULL DEFAULT '[]',
    diffusion_stage TEXT,
    market_regime TEXT,
    validation_status TEXT,
    validation_metrics JSONB NOT NULL DEFAULT '{}',
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alpha_signal_subject_id ON alpha_signal(subject_id);
CREATE INDEX IF NOT EXISTS idx_alpha_signal_event_id ON alpha_signal(event_id);
CREATE INDEX IF NOT EXISTS idx_alpha_signal_team_project ON alpha_signal(team_id, project_id);

-- 交易候选表
CREATE TABLE IF NOT EXISTS trade_candidate (
    candidate_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL REFERENCES alpha_signal(signal_id),
    action TEXT NOT NULL,
    sizing_hint NUMERIC NOT NULL,
    risk_notes JSONB NOT NULL DEFAULT '[]',
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_candidate_signal_id ON trade_candidate(signal_id);
CREATE INDEX IF NOT EXISTS idx_trade_candidate_team_project ON trade_candidate(team_id, project_id);

-- Agent 观点表
CREATE TABLE IF NOT EXISTS agent_view (
    view_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    target_id TEXT NOT NULL,
    view TEXT NOT NULL,
    thesis TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    event_id TEXT,
    reasoning JSONB NOT NULL DEFAULT '[]',
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    tool_refs JSONB NOT NULL DEFAULT '[]',
    memory_refs JSONB NOT NULL DEFAULT '[]',
    workflow_id TEXT,
    evaluation JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_view_agent_role ON agent_view(agent_role);
CREATE INDEX IF NOT EXISTS idx_agent_view_target_id ON agent_view(target_id);
CREATE INDEX IF NOT EXISTS idx_agent_view_event_id ON agent_view(event_id);
CREATE INDEX IF NOT EXISTS idx_agent_view_team_project ON agent_view(team_id, project_id);

-- 黑板冲突表
CREATE TABLE IF NOT EXISTS blackboard_conflict (
    conflict_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    event_id TEXT,
    view_ids JSONB NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    team_id TEXT,
    project_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blackboard_conflict_target_id ON blackboard_conflict(target_id);
CREATE INDEX IF NOT EXISTS idx_blackboard_conflict_event_id ON blackboard_conflict(event_id);
CREATE INDEX IF NOT EXISTS idx_blackboard_conflict_team_project ON blackboard_conflict(team_id, project_id);

-- Timing Engine 择时决策表
CREATE TABLE IF NOT EXISTS timing_decision (
    decision_id TEXT PRIMARY KEY,
    signal_id TEXT,
    action TEXT NOT NULL,
    readiness_score NUMERIC NOT NULL,
    market_regime TEXT NOT NULL DEFAULT 'unknown',
    model_scores JSONB NOT NULL DEFAULT '[]',
    active_weights JSONB NOT NULL DEFAULT '{}',
    blockers JSONB NOT NULL DEFAULT '[]',
    rationale JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timing_decision_signal_id ON timing_decision(signal_id);
CREATE INDEX IF NOT EXISTS idx_timing_decision_action ON timing_decision(action);
CREATE INDEX IF NOT EXISTS idx_timing_decision_created_at ON timing_decision(created_at DESC);

-- Memory & Learning 模块表
-- 市场事件记忆表
CREATE TABLE IF NOT EXISTS market_episode (
    episode_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    market_regime TEXT NOT NULL,
    initial_reaction TEXT NOT NULL,
    outcome_horizon TEXT NOT NULL,
    outcome_return NUMERIC NOT NULL,
    outcome_excess_return NUMERIC NOT NULL,
    timing_action TEXT,
    signal_id TEXT,
    timing_decision_id TEXT,
    failed_reason TEXT,
    lesson TEXT,
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_episode_event_type ON market_episode(event_type);
CREATE INDEX IF NOT EXISTS idx_market_episode_market_regime ON market_episode(market_regime);

-- 策略记忆表
CREATE TABLE IF NOT EXISTS strategy_memory (
    strategy_id TEXT PRIMARY KEY,
    signal_family TEXT NOT NULL,
    market_regime TEXT NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC NOT NULL,
    average_excess_return NUMERIC NOT NULL,
    sharpe_ratio NUMERIC NOT NULL,
    notes JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_signal_family ON strategy_memory(signal_family);
CREATE INDEX IF NOT EXISTS idx_strategy_memory_market_regime ON strategy_memory(market_regime);

-- Agent 记忆表
CREATE TABLE IF NOT EXISTS agent_memory (
    memory_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    belief TEXT NOT NULL,
    confidence NUMERIC NOT NULL,
    support_count INTEGER NOT NULL DEFAULT 0,
    contradiction_count INTEGER NOT NULL DEFAULT 0,
    last_updated_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_role ON agent_memory(agent_role);

-- 失败记忆表
CREATE TABLE IF NOT EXISTS failure_memory (
    failure_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    corrective_action TEXT NOT NULL,
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_failure_memory_failure_type ON failure_memory(failure_type);
CREATE INDEX IF NOT EXISTS idx_failure_memory_source_id ON failure_memory(source_id);
