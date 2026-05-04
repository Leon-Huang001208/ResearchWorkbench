from datetime import datetime

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from data_layer.repositories.base import Base


class Entity(Base):
    """实体模型"""

    __tablename__ = "entity"

    entity_id = Column(Text, primary_key=True)
    canonical_id = Column(Text, unique=True, nullable=False)
    entity_type = Column(Text, nullable=False)
    canonical_name = Column(Text, nullable=False)
    aliases = Column(JSONB, nullable=False, server_default="[]")
    vendor_ids = Column(JSONB, nullable=False, server_default="{}")
    properties = Column(JSONB, nullable=False, server_default="{}")
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    # 关系
    assertions = relationship("Assertion", foreign_keys="Assertion.subject_entity_id")


class SourceDocument(Base):
    """源文档模型"""

    __tablename__ = "source_document"

    doc_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    published_at = Column(TIMESTAMP(timezone=True), nullable=True)
    source_name = Column(Text, nullable=False)
    content_hash = Column(Text, nullable=False)
    rights_ref = Column(Text, nullable=True)
    parser_version = Column(Text, nullable=False)
    object_uri = Column(Text, nullable=False)
    metadata = Column(JSONB, nullable=False, server_default="{}")
    embedding = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

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
    object_value = Column(JSONB, nullable=True)
    observed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    valid_from = Column(TIMESTAMP(timezone=True), nullable=True)
    valid_to = Column(TIMESTAMP(timezone=True), nullable=True)
    confidence = Column(Numeric, nullable=False)
    source_doc_id = Column(Text, ForeignKey("source_document.doc_id"), nullable=True)
    source_span = Column(JSONB, nullable=False, server_default="{}")
    extractor_version = Column(Text, nullable=False)
    reviewer_status = Column(Text, nullable=False, server_default="draft")
    reviewer = Column(Text, nullable=True)
    reviewed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    trace_ref = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)


class CanonicalEvent(Base):
    """规范事件模型"""

    __tablename__ = "canonical_event"

    event_id = Column(Text, primary_key=True)
    event_type = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    event_time = Column(TIMESTAMP(timezone=True), nullable=True)
    impact_direction = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=False)
    needs_review = Column(Boolean, nullable=False, server_default="true")
    source_doc_id = Column(Text, ForeignKey("source_document.doc_id"), nullable=True)
    payload = Column(JSONB, nullable=False, server_default="{}")
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class ReasoningTrace(Base):
    """推理追踪模型"""

    __tablename__ = "reasoning_trace"

    trace_id = Column(Text, primary_key=True)
    request_type = Column(Text, nullable=False)
    question = Column(Text, nullable=False)
    subject_ids = Column(JSONB, nullable=False, server_default="[]")
    retrieved_doc_ids = Column(JSONB, nullable=False, server_default="[]")
    retrieved_assertion_ids = Column(JSONB, nullable=False, server_default="[]")
    graph_paths = Column(JSONB, nullable=False, server_default="[]")
    intermediate_hypotheses = Column(JSONB, nullable=False, server_default="[]")
    final_answer = Column(Text, nullable=True)
    provider = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=False)
    total_latency_ms = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)


class AssetSnapshot(Base):
    """资产分析快照模型"""

    __tablename__ = "asset_snapshot"

    snapshot_id = Column(Text, primary_key=True)
    canonical_id = Column(Text, ForeignKey("entity.canonical_id"), nullable=False, index=True)
    as_of = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    financial = Column(JSONB, nullable=False, server_default="{}")
    fund_flow = Column(JSONB, nullable=False, server_default="{}")
    price_volume = Column(JSONB, nullable=False, server_default="{}")
    valuation = Column(JSONB, nullable=False, server_default="{}")
    shareholder = Column(JSONB, nullable=False, server_default="{}")
    industry = Column(JSONB, nullable=False, server_default="{}")
    event_impact = Column(JSONB, nullable=False, server_default="[]")
    macro_exposure = Column(JSONB, nullable=False, server_default="{}")
    evidence_refs = Column(JSONB, nullable=False, server_default="[]")
    team_id = Column(Text, nullable=True)
    project_id = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
