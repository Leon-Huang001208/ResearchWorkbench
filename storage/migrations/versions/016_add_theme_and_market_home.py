"""Add Research Pack manifests and immutable market-home snapshots.

Revision ID: 016
Revises: 015
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the two theme and facts-only home tables."""

    op.create_table(
        "theme_pack",
        sa.Column("pack_id", sa.Text(), nullable=False),
        sa.Column("pack_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("compatibility_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("pack_id"),
        sa.UniqueConstraint("pack_key", "version", name="uq_theme_pack_version"),
    )
    op.create_index("ix_theme_pack_pack_key", "theme_pack", ["pack_key"])
    op.create_index("ix_theme_pack_status", "theme_pack", ["status"])
    op.create_index("ix_theme_pack_content_hash", "theme_pack", ["content_hash"])

    op.create_table(
        "market_home_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("snapshot_kind", sa.Text(), nullable=False),
        sa.Column("section_key", sa.Text(), nullable=False),
        sa.Column("formula_version", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("freshness_status", sa.Text(), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("input_fact_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "trading_day",
            "snapshot_kind",
            "section_key",
            "formula_version",
            name="uq_market_home_snapshot_identity",
        ),
    )
    for column in (
        "trading_day",
        "snapshot_kind",
        "section_key",
        "as_of",
        "freshness_status",
    ):
        op.create_index(f"ix_market_home_snapshot_{column}", "market_home_snapshot", [column])


def downgrade() -> None:
    """Drop theme and market-home tables."""

    op.drop_table("market_home_snapshot")
    op.drop_table("theme_pack")
