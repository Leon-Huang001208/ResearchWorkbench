"""Add event_type column to signal_outcome

Revision ID: 008
Revises: 007
Create Date: 2026-05-09

"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some installations reached Alembic after the legacy ORM bootstrap had
    # created this table, while clean databases do not have it in revisions
    # 001-007. Keep the compatibility alteration conditional so a fresh graph
    # can still advance to the authoritative merged-platform migrations.
    inspector = sa.inspect(op.get_bind())
    if "signal_outcome" not in inspector.get_table_names():
        return
    # 添加 event_type 列到 signal_outcome 表
    op.add_column(
        "signal_outcome",
        sa.Column("event_type", sa.Text(), nullable=True, server_default="unknown"),
    )
    # 创建索引
    op.create_index("idx_signal_outcome_event_type", "signal_outcome", ["event_type"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "signal_outcome" not in inspector.get_table_names():
        return
    op.drop_index("idx_signal_outcome_event_type", "signal_outcome")
    op.drop_column("signal_outcome", "event_type")
