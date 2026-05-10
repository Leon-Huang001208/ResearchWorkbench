"""Add timing_decision table for Timing Engine

Revision ID: 005
Revises: 004
Create Date: 2026-05-07

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Timing decision table
    op.create_table(
        "timing_decision",
        sa.Column("decision_id", sa.Text(), primary_key=True),
        sa.Column("signal_id", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("readiness_score", sa.Numeric(), nullable=False),
        sa.Column("market_regime", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("model_scores", JSONB(), nullable=False, server_default="[]"),
        sa.Column("active_weights", JSONB(), nullable=False, server_default="{}"),
        sa.Column("blockers", JSONB(), nullable=False, server_default="[]"),
        sa.Column("rationale", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_timing_decision_signal_id", "timing_decision", ["signal_id"])
    op.create_index("idx_timing_decision_action", "timing_decision", ["action"])
    op.create_index("idx_timing_decision_created_at", "timing_decision", ["created_at DESC"])


def downgrade() -> None:
    op.drop_index("idx_timing_decision_created_at")
    op.drop_index("idx_timing_decision_action")
    op.drop_index("idx_timing_decision_signal_id")
    op.drop_table("timing_decision")
