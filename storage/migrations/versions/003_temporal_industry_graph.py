"""Add temporal industry graph tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-07

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 时间化关系表
    op.create_table(
        "temporal_relation",
        sa.Column("relation_id", sa.Text(), primary_key=True),
        sa.Column("from_entity_id", sa.Text(), nullable=False),
        sa.Column("to_entity_id", sa.Text(), nullable=False),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("strength", sa.Numeric(), nullable=False),
        sa.Column("valid_from", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("chain_position", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 产业链表
    op.create_table(
        "industry_chain",
        sa.Column("chain_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("industry", sa.Text(), nullable=False),
        sa.Column("nodes", JSONB(), nullable=False),  # list of entity_ids
        sa.Column("relations", JSONB(), nullable=False),  # list of relation_ids
        sa.Column("as_of", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 索引
    op.create_index(
        "idx_temporal_relation_from_entity", "temporal_relation", ["from_entity_id"]
    )
    op.create_index(
        "idx_temporal_relation_to_entity", "temporal_relation", ["to_entity_id"]
    )
    op.create_index(
        "idx_temporal_relation_type", "temporal_relation", ["relationship_type"]
    )
    op.create_index(
        "idx_temporal_relation_industry", "temporal_relation", ["industry"]
    )
    op.create_index(
        "idx_temporal_relation_valid_period", "temporal_relation", ["valid_from", "valid_to"]
    )

    op.create_index("idx_industry_chain_industry", "industry_chain", ["industry"])
    op.create_index("idx_industry_chain_as_of", "industry_chain", ["as_of"])


def downgrade() -> None:
    op.drop_index("idx_industry_chain_as_of", table_name="industry_chain")
    op.drop_index("idx_industry_chain_industry", table_name="industry_chain")
    op.drop_index("idx_temporal_relation_valid_period", table_name="temporal_relation")
    op.drop_index("idx_temporal_relation_industry", table_name="temporal_relation")
    op.drop_index("idx_temporal_relation_type", table_name="temporal_relation")
    op.drop_index("idx_temporal_relation_to_entity", table_name="temporal_relation")
    op.drop_index("idx_temporal_relation_from_entity", table_name="temporal_relation")
    op.drop_table("industry_chain")
    op.drop_table("temporal_relation")
