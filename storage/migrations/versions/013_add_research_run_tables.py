"""Add evidence-first Research Run persistence.

Revision ID: 013
Revises: 012
Create Date: 2026-08-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_run",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("template_key", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("attachment_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evidence_inputs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_plan", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resume_from", sa.Text(), nullable=True),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_research_run_template_key", "research_run", ["template_key"])
    op.create_index("ix_research_run_target_id", "research_run", ["target_id"])
    op.create_index("ix_research_run_as_of", "research_run", ["as_of"])
    op.create_index("ix_research_run_status", "research_run", ["status"])

    op.create_table(
        "research_task",
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("task_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resume_from", sa.Text(), nullable=True),
        sa.Column("state_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_research_task_run_id", "research_task", ["run_id"])

    op.create_table(
        "research_artifact",
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint("run_id", "artifact_type", name="uq_research_artifact_type"),
    )
    op.create_index("ix_research_artifact_run_id", "research_artifact", ["run_id"])

    op.create_table(
        "research_claim",
        sa.Column("claim_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("numeric_context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("conflict_status", sa.Text(), nullable=False, server_default="clear"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.PrimaryKeyConstraint("claim_id"),
    )
    op.create_index("ix_research_claim_run_id", "research_claim", ["run_id"])

    op.create_table(
        "research_quality_gate",
        sa.Column("gate_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("gate_key", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="error"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["research_run.run_id"]),
        sa.PrimaryKeyConstraint("gate_id"),
        sa.UniqueConstraint("run_id", "gate_key", name="uq_research_quality_gate"),
    )
    op.create_index("ix_research_quality_gate_run_id", "research_quality_gate", ["run_id"])


def downgrade() -> None:
    op.drop_table("research_quality_gate")
    op.drop_table("research_claim")
    op.drop_table("research_artifact")
    op.drop_table("research_task")
    op.drop_table("research_run")
