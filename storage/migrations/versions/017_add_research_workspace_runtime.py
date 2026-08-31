"""Add research workspaces, bounded runtimes, Skills, teams, and notes.

Revision ID: 017
Revises: 016
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the eight additive research-runtime tables."""

    op.create_table(
        "research_workspace",
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_index("ix_research_workspace_project_id", "research_workspace", ["project_id"])
    op.create_index("ix_research_workspace_status", "research_workspace", ["status"])

    op.create_table(
        "research_session",
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["research_workspace.workspace_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_research_session_idempotency_key"),
    )
    for column in ("workspace_id", "run_id", "mode", "status"):
        op.create_index(f"ix_research_session_{column}", "research_session", [column])

    op.create_table(
        "research_message",
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("content_ref", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["research_session.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint(
            "session_id", "idempotency_key", name="uq_research_message_idempotency"
        ),
    )
    op.create_index("ix_research_message_session_id", "research_message", ["session_id"])
    op.create_index("ix_research_message_created_at", "research_message", ["created_at"])

    op.create_table(
        "runtime_provider",
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("config_ref", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("provider_id"),
    )
    op.create_index("ix_runtime_provider_provider_type", "runtime_provider", ["provider_type"])
    op.create_index("ix_runtime_provider_status", "runtime_provider", ["status"])
    op.create_index("ix_runtime_provider_checked_at", "runtime_provider", ["checked_at"])

    op.create_table(
        "skill_definition",
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("skill_key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("manifest", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("allowed_tools", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("skill_id"),
        sa.UniqueConstraint("skill_key", "version", name="uq_skill_definition_version"),
    )
    op.create_index("ix_skill_definition_skill_key", "skill_definition", ["skill_key"])
    op.create_index("ix_skill_definition_status", "skill_definition", ["status"])
    op.create_index("ix_skill_definition_content_hash", "skill_definition", ["content_hash"])

    op.create_table(
        "agent_team",
        sa.Column("team_id", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("supervisor_role", sa.Text(), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("budget", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("skill_keys", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["research_workspace.workspace_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("team_id"),
    )
    op.create_index("ix_agent_team_workspace_id", "agent_team", ["workspace_id"])
    op.create_index("ix_agent_team_status", "agent_team", ["status"])

    op.create_table(
        "agent_schedule",
        sa.Column("schedule_id", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=False),
        sa.Column("scheduled_job_id", sa.Text(), nullable=True),
        sa.Column("cron_expression", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("allow_concurrent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("coalesce_policy", sa.Text(), nullable=False, server_default="latest"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["team_id"], ["agent_team.team_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scheduled_job_id"], ["scheduled_job.job_id"]),
        sa.PrimaryKeyConstraint("schedule_id"),
    )
    op.create_index("ix_agent_schedule_team_id", "agent_schedule", ["team_id"])
    op.create_index("ix_agent_schedule_scheduled_job_id", "agent_schedule", ["scheduled_job_id"])
    op.create_index("ix_agent_schedule_status", "agent_schedule", ["status"])
    op.create_index("ix_agent_schedule_next_run_at", "agent_schedule", ["next_run_at"])

    op.create_table(
        "research_note",
        sa.Column("note_id", sa.Text(), nullable=False),
        sa.Column("note_key", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("claim_id", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("paragraph_ref", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["research_workspace.workspace_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.ForeignKeyConstraint(["claim_id"], ["research_claim.claim_id"]),
        sa.PrimaryKeyConstraint("note_id"),
        sa.CheckConstraint(
            "(source_kind = 'claim' AND claim_id IS NOT NULL AND run_id IS NULL "
            "AND paragraph_ref IS NULL) OR "
            "(source_kind = 'paragraph' AND claim_id IS NULL AND run_id IS NOT NULL "
            "AND paragraph_ref IS NOT NULL)",
            name="ck_research_note_source_shape",
        ),
        sa.UniqueConstraint(
            "workspace_id", "note_key", "revision", name="uq_research_note_revision"
        ),
    )
    op.create_index("ix_research_note_workspace_id", "research_note", ["workspace_id"])
    op.create_index("ix_research_note_run_id", "research_note", ["run_id"])
    op.create_index("ix_research_note_claim_id", "research_note", ["claim_id"])
    op.create_index("ix_research_note_created_at", "research_note", ["created_at"])


def downgrade() -> None:
    """Drop research-runtime tables in reverse dependency order."""

    op.drop_table("research_note")
    op.drop_table("agent_schedule")
    op.drop_table("agent_team")
    op.drop_table("skill_definition")
    op.drop_table("runtime_provider")
    op.drop_table("research_message")
    op.drop_table("research_session")
    op.drop_table("research_workspace")
