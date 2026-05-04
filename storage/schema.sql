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
