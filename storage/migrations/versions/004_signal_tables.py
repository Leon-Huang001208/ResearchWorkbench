"""Add signal, trade candidate, agent view, and blackboard conflict tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-07

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alpha signal table
    op.create_table(
        "alpha_signal",
        sa.Column("signal_id", sa.Text(), primary_key=True),
        sa.Column("discriminator", sa.Text(), nullable=False, server_default="alpha_signal"),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("horizon", sa.Text(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("scenario_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False, server_default="research_only"),
        # EventAlphaSignal fields
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=True),
        sa.Column("event_time", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("impact_path", JSONB(), nullable=False, server_default="[]"),
        sa.Column("industry_impacts", JSONB(), nullable=False, server_default="[]"),
        sa.Column("bullish_companies", JSONB(), nullable=False, server_default="[]"),
        sa.Column("bearish_companies", JSONB(), nullable=False, server_default="[]"),
        sa.Column("diffusion_stage", sa.Text(), nullable=True),
        sa.Column("market_regime", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.Text(), nullable=True),
        sa.Column("validation_metrics", JSONB(), nullable=False, server_default="{}"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_alpha_signal_subject_id", "alpha_signal", ["subject_id"])
    op.create_index("idx_alpha_signal_event_id", "alpha_signal", ["event_id"])
    op.create_index("idx_alpha_signal_team_project", "alpha_signal", ["team_id", "project_id"])

    # Trade candidate table
    op.create_table(
        "trade_candidate",
        sa.Column("candidate_id", sa.Text(), primary_key=True),
        sa.Column("signal_id", sa.Text(), sa.ForeignKey("alpha_signal.signal_id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("sizing_hint", sa.Numeric(), nullable=False),
        sa.Column("risk_notes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_trade_candidate_signal_id", "trade_candidate", ["signal_id"])
    op.create_index(
        "idx_trade_candidate_team_project", "trade_candidate", ["team_id", "project_id"]
    )

    # Agent view table
    op.create_table(
        "agent_view",
        sa.Column("view_id", sa.Text(), primary_key=True),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("agent_role", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("view", sa.Text(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("reasoning", JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("tool_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("memory_refs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("workflow_id", sa.Text(), nullable=True),
        sa.Column("evaluation", JSONB(), nullable=False, server_default="{}"),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_agent_view_agent_role", "agent_view", ["agent_role"])
    op.create_index("idx_agent_view_target_id", "agent_view", ["target_id"])
    op.create_index("idx_agent_view_event_id", "agent_view", ["event_id"])
    op.create_index("idx_agent_view_team_project", "agent_view", ["team_id", "project_id"])

    # Blackboard conflict table
    op.create_table(
        "blackboard_conflict",
        sa.Column("conflict_id", sa.Text(), primary_key=True),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("view_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    op.create_index("idx_blackboard_conflict_target_id", "blackboard_conflict", ["target_id"])
    op.create_index("idx_blackboard_conflict_event_id", "blackboard_conflict", ["event_id"])
    op.create_index(
        "idx_blackboard_conflict_team_project", "blackboard_conflict", ["team_id", "project_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_blackboard_conflict_team_project")
    op.drop_index("idx_blackboard_conflict_event_id")
    op.drop_index("idx_blackboard_conflict_target_id")
    op.drop_table("blackboard_conflict")

    op.drop_index("idx_agent_view_team_project")
    op.drop_index("idx_agent_view_event_id")
    op.drop_index("idx_agent_view_target_id")
    op.drop_index("idx_agent_view_agent_role")
    op.drop_table("agent_view")

    op.drop_index("idx_trade_candidate_team_project")
    op.drop_index("idx_trade_candidate_signal_id")
    op.drop_table("trade_candidate")

    op.drop_index("idx_alpha_signal_team_project")
    op.drop_index("idx_alpha_signal_event_id")
    op.drop_index("idx_alpha_signal_subject_id")
    op.drop_table("alpha_signal")
