"""Add memory & learning tables

Revision ID: 006
Revises: 005
Create Date: 2026-05-07

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Market episode table
    op.create_table(
        "market_episode",
        sa.Column("episode_id", sa.Text(), primary_key=True),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("market_regime", sa.Text(), nullable=False),
        sa.Column("initial_reaction", sa.Text(), nullable=False),
        sa.Column("outcome_horizon", sa.Text(), nullable=False),
        sa.Column("outcome_return", sa.Numeric(), nullable=False),
        sa.Column("outcome_excess_return", sa.Numeric(), nullable=False),
        sa.Column("timing_action", sa.Text(), nullable=True),
        sa.Column("signal_id", sa.Text(), nullable=True),
        sa.Column("timing_decision_id", sa.Text(), nullable=True),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("lesson", sa.Text(), nullable=True),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    # Indexes for market_episode
    op.create_index("idx_market_episode_event_type", "market_episode", ["event_type"])
    op.create_index("idx_market_episode_market_regime", "market_episode", ["market_regime"])

    # Strategy memory table
    op.create_table(
        "strategy_memory",
        sa.Column("strategy_id", sa.Text(), primary_key=True),
        sa.Column("signal_family", sa.Text(), nullable=False),
        sa.Column("market_regime", sa.Text(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Numeric(), nullable=False),
        sa.Column("average_excess_return", sa.Numeric(), nullable=False),
        sa.Column("sharpe_ratio", sa.Numeric(), nullable=False),
        sa.Column("notes", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    # Indexes for strategy_memory
    op.create_index("idx_strategy_memory_signal_family", "strategy_memory", ["signal_family"])
    op.create_index("idx_strategy_memory_market_regime", "strategy_memory", ["market_regime"])

    # Agent memory table
    op.create_table(
        "agent_memory",
        sa.Column("memory_id", sa.Text(), primary_key=True),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("agent_role", sa.Text(), nullable=False),
        sa.Column("belief", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradiction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    # Indexes for agent_memory
    op.create_index("idx_agent_memory_agent_role", "agent_memory", ["agent_role"])

    # Failure memory table
    op.create_table(
        "failure_memory",
        sa.Column("failure_id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("failure_type", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("corrective_action", sa.Text(), nullable=False),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    # Indexes for failure_memory
    op.create_index("idx_failure_memory_failure_type", "failure_memory", ["failure_type"])
    op.create_index("idx_failure_memory_source_id", "failure_memory", ["source_id"])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("idx_failure_memory_source_id")
    op.drop_index("idx_failure_memory_failure_type")
    op.drop_table("failure_memory")

    op.drop_index("idx_agent_memory_agent_role")
    op.drop_table("agent_memory")

    op.drop_index("idx_strategy_memory_market_regime")
    op.drop_index("idx_strategy_memory_signal_family")
    op.drop_table("strategy_memory")

    op.drop_index("idx_market_episode_market_regime")
    op.drop_index("idx_market_episode_event_type")
    op.drop_table("market_episode")
