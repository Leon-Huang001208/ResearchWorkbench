"""PDF and Crawl State Schema

Revision ID: 002_pdf_crawl_state
Revises: 002
Create Date: 2026-05-11

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "002_pdf_crawl_state"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PDF 制品表
    op.create_table(
        "pdf_artifact_v1",
        sa.Column("pdf_id", sa.Text(), primary_key=True),
        sa.Column("doc_id", sa.Text(), sa.ForeignKey("document_v1.doc_id"), nullable=True),
        sa.Column("source_obj_id", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_hash_sha256", sa.Text(), nullable=False),
        sa.Column("file_hash_md5", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_broker", sa.Text(), nullable=True),
        sa.Column("source_author", sa.Text(), nullable=True),
        sa.Column("source_publish_date", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("fetch_timestamp", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("fetch_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("fetch_strategy", sa.Text(), nullable=True),
        sa.Column("fetch_duration_ms", sa.Integer(), nullable=True),
        sa.Column("parse_version", sa.Text(), nullable=True),
        sa.Column("parse_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("parse_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("parsed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("pdf_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("extra", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_pdf_artifact_doc_id", "pdf_artifact_v1", ["doc_id"])
    op.create_index("idx_pdf_artifact_source_obj_id", "pdf_artifact_v1", ["source_obj_id"])
    op.create_index("idx_pdf_artifact_source_type", "pdf_artifact_v1", ["source_type"])
    op.create_index("idx_pdf_artifact_hash", "pdf_artifact_v1", ["file_hash_sha256"])

    # PDF 转换结果表
    op.create_table(
        "pdf_conversion_v1",
        sa.Column("conversion_id", sa.Text(), primary_key=True),
        sa.Column("pdf_id", sa.Text(), sa.ForeignKey("pdf_artifact_v1.pdf_id"), nullable=False),
        sa.Column("conversion_strategy", sa.Text(), nullable=False),
        sa.Column("strategy_version", sa.Text(), nullable=True),
        sa.Column("strategy_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("markdown_path", sa.Text(), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=True),
        sa.Column("raw_text_path", sa.Text(), nullable=True),
        sa.Column("raw_text_content", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("conversion_duration_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Numeric(), nullable=True),
        sa.Column("has_tables", sa.Boolean(), nullable=True),
        sa.Column("has_images", sa.Boolean(), nullable=True),
        sa.Column("has_code_blocks", sa.Boolean(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_pdf_conversion_pdf_id", "pdf_conversion_v1", ["pdf_id"])
    op.create_index("idx_pdf_conversion_strategy", "pdf_conversion_v1", ["conversion_strategy"])
    op.create_index("idx_pdf_conversion_status", "pdf_conversion_v1", ["status"])

    # 爬虫状态表
    op.create_table(
        "crawl_state_v1",
        sa.Column("state_id", sa.Text(), primary_key=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("watermark_id", sa.Text(), nullable=True),
        sa.Column("watermark_timestamp", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("watermark_metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.Column("dedupe_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("crawl_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("crawl_mode", sa.Text(), nullable=False, server_default="incremental"),
        sa.Column("last_run_id", sa.Text(), nullable=True),
        sa.Column("last_run_start", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_end", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("extra", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_crawl_state_source_type", "crawl_state_v1", ["source_type"])
    op.create_index("idx_crawl_state_source_name", "crawl_state_v1", ["source_name"])
    op.create_index("idx_crawl_state_dedupe_key", "crawl_state_v1", ["dedupe_key"])

    # 已处理项目表
    op.create_table(
        "processed_item_v1",
        sa.Column("item_id", sa.Text(), primary_key=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("first_seen_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("first_processed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("process_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("crawl_run_id", sa.Text(), nullable=True),
        sa.Column("doc_id", sa.Text(), nullable=True),
        sa.Column("extra", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_processed_item_source_type", "processed_item_v1", ["source_type"])
    op.create_index("idx_processed_item_source_name", "processed_item_v1", ["source_name"])
    op.create_index("idx_processed_item_item_type", "processed_item_v1", ["item_type"])
    op.create_index("idx_processed_item_hash", "processed_item_v1", ["content_hash"])
    op.create_index("idx_processed_item_crawl_run", "processed_item_v1", ["crawl_run_id"])
    op.create_index("idx_processed_item_doc_id", "processed_item_v1", ["doc_id"])


def downgrade() -> None:
    op.drop_table("processed_item_v1")
    op.drop_table("crawl_state_v1")
    op.drop_table("pdf_conversion_v1")
    op.drop_table("pdf_artifact_v1")
