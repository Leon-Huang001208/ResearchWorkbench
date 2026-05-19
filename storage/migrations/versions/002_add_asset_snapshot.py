"""Add asset snapshot table

Revision ID: 002
Revises: 001
Create Date: 2026-05-03

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 资产分析快照表
    op.create_table(
        "asset_snapshot",
        sa.Column("snapshot_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("as_of", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("financial", JSONB(), nullable=False, server_default="{}"),
        sa.Column("fund_flow", JSONB(), nullable=False, server_default="{}"),
        sa.Column("price_volume", JSONB(), nullable=False, server_default="{}"),
        sa.Column("valuation", JSONB(), nullable=False, server_default="{}"),
        sa.Column("shareholder", JSONB(), nullable=False, server_default="{}"),
        sa.Column("industry", JSONB(), nullable=False, server_default="{}"),
        sa.Column("event_impact", JSONB(), nullable=False, server_default="[]"),
        sa.Column("macro_exposure", JSONB(), nullable=False, server_default="{}"),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )

    # 索引
    op.create_index("idx_asset_snapshot_canonical_id", "asset_snapshot", ["canonical_id"])
    op.create_index("idx_asset_snapshot_as_of", "asset_snapshot", ["as_of"])
    op.create_index(
        "idx_asset_snapshot_canonical_as_of", "asset_snapshot", ["canonical_id", "as_of"]
    )
    op.create_index("idx_asset_snapshot_team_project", "asset_snapshot", ["team_id", "project_id"])


def downgrade() -> None:
    op.drop_index("idx_asset_snapshot_team_project")
    op.drop_index("idx_asset_snapshot_canonical_as_of")
    op.drop_index("idx_asset_snapshot_as_of")
    op.drop_index("idx_asset_snapshot_canonical_id")
    op.drop_table("asset_snapshot")
