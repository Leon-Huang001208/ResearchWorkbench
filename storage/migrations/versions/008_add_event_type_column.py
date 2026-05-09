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
    # 添加 event_type 列到 signal_outcome 表
    op.add_column(
        "signal_outcome",
        sa.Column("event_type", sa.Text(), nullable=True, server_default="unknown")
    )
    # 创建索引
    op.create_index("idx_signal_outcome_event_type", "signal_outcome", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_signal_outcome_event_type", "signal_outcome")
    op.drop_column("signal_outcome", "event_type")
