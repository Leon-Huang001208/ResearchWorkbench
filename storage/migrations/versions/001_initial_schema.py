"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-03

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 实体表
    op.create_table(
        "entity",
        sa.Column("entity_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False, unique=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("aliases", JSONB(), nullable=False, server_default="[]"),
        sa.Column("vendor_ids", JSONB(), nullable=False, server_default="{}"),
        sa.Column("properties", JSONB(), nullable=False, server_default="{}"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 源文档表
    op.create_table(
        "source_document",
        sa.Column("doc_id", sa.Text(), primary_key=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("published_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("rights_ref", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("object_uri", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 断言表
    op.create_table(
        "assertion",
        sa.Column("assertion_id", sa.Text(), primary_key=True),
        sa.Column("subject_entity_id", sa.Text(), sa.ForeignKey("entity.entity_id"), nullable=True),
        sa.Column("predicate", sa.Text(), nullable=False),
        sa.Column("object_entity_id", sa.Text(), nullable=True),
        sa.Column("object_value", JSONB(), nullable=True),
        sa.Column("observed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_from", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column(
            "source_doc_id", sa.Text(), sa.ForeignKey("source_document.doc_id"), nullable=True
        ),
        sa.Column("source_span", JSONB(), nullable=False, server_default="{}"),
        sa.Column("extractor_version", sa.Text(), nullable=False),
        sa.Column("reviewer_status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("reviewer", sa.Text(), nullable=True),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trace_ref", sa.Text(), nullable=True),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
    )

    # 规范事件表
    op.create_table(
        "canonical_event",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("event_time", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("impact_direction", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "source_doc_id", sa.Text(), sa.ForeignKey("source_document.doc_id"), nullable=True
        ),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 推理追踪表
    op.create_table(
        "reasoning_trace",
        sa.Column("trace_id", sa.Text(), primary_key=True),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("subject_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("retrieved_doc_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("retrieved_assertion_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("graph_paths", JSONB(), nullable=False, server_default="[]"),
        sa.Column("intermediate_hypotheses", JSONB(), nullable=False, server_default="[]"),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 索引
    op.create_index("idx_entity_canonical_id", "entity", ["canonical_id"])
    op.create_index("idx_entity_type", "entity", ["entity_type"])
    op.create_index("idx_entity_team_project", "entity", ["team_id", "project_id"])

    op.create_index("idx_document_source_type", "source_document", ["source_type"])
    op.create_index("idx_document_published_at", "source_document", ["published_at"])
    op.create_index("idx_document_team_project", "source_document", ["team_id", "project_id"])

    op.create_index("idx_assertion_subject", "assertion", ["subject_entity_id"])
    op.create_index("idx_assertion_source", "assertion", ["source_doc_id"])
    op.create_index("idx_assertion_status", "assertion", ["reviewer_status"])
    op.create_index("idx_assertion_team_project", "assertion", ["team_id", "project_id"])

    op.create_index("idx_event_source", "canonical_event", ["source_doc_id"])
    op.create_index("idx_event_time", "canonical_event", ["event_time"])
    op.create_index("idx_event_team_project", "canonical_event", ["team_id", "project_id"])

    op.create_index("idx_trace_request_type", "reasoning_trace", ["request_type"])
    op.create_index("idx_trace_created_at", "reasoning_trace", ["created_at"])
    op.create_index("idx_trace_team_project", "reasoning_trace", ["team_id", "project_id"])


def downgrade() -> None:
    op.drop_table("reasoning_trace")
    op.drop_table("canonical_event")
    op.drop_table("assertion")
    op.drop_table("source_document")
    op.drop_table("entity")
    op.execute("DROP EXTENSION IF EXISTS vector")
