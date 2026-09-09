"""Add runtime-neutral workflow ledger and immutable artifacts.

Revision ID: 019
Revises: 018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("runtime_workflow_run", sa.Column("run_id", sa.Text(), primary_key=True), sa.Column("workflow_id", sa.Text(), nullable=False), sa.Column("workflow_version", sa.Text(), nullable=False), sa.Column("runtime_id", sa.Text(), nullable=False), sa.Column("request_payload", sa.JSON(), nullable=False), sa.Column("workflow_payload", sa.JSON(), nullable=False), sa.Column("status", sa.Text(), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_runtime_workflow_run_workflow_id", "runtime_workflow_run", ["workflow_id"])
    op.create_index("ix_runtime_workflow_run_runtime_id", "runtime_workflow_run", ["runtime_id"])
    op.create_index("ix_runtime_workflow_run_status", "runtime_workflow_run", ["status"])
    op.create_table("runtime_workflow_step", sa.Column("step_execution_id", sa.Text(), primary_key=True), sa.Column("run_id", sa.Text(), sa.ForeignKey("runtime_workflow_run.run_id"), nullable=False), sa.Column("step_id", sa.Text(), nullable=False), sa.Column("capability_id", sa.Text(), nullable=False), sa.Column("status", sa.Text(), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False), sa.Column("output_payload", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("run_id", "step_id", name="uq_runtime_workflow_step"))
    op.create_index("ix_runtime_workflow_step_run_id", "runtime_workflow_step", ["run_id"])
    op.create_table("runtime_event", sa.Column("event_id", sa.Text(), primary_key=True), sa.Column("run_id", sa.Text(), sa.ForeignKey("runtime_workflow_run.run_id"), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("event_type", sa.Text(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("run_id", "sequence", name="uq_runtime_event_sequence"))
    op.create_index("ix_runtime_event_run_id", "runtime_event", ["run_id"])
    op.create_table("runtime_evidence", sa.Column("evidence_id", sa.Text(), primary_key=True), sa.Column("run_id", sa.Text(), sa.ForeignKey("runtime_workflow_run.run_id"), nullable=False), sa.Column("source_ref", sa.Text(), nullable=False), sa.Column("source_name", sa.Text(), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("observed_at", sa.DateTime(timezone=True)), sa.Column("conflict", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_runtime_evidence_run_id", "runtime_evidence", ["run_id"])
    op.create_table("runtime_artifact", sa.Column("artifact_id", sa.Text(), primary_key=True), sa.Column("run_id", sa.Text(), sa.ForeignKey("runtime_workflow_run.run_id"), nullable=False), sa.Column("artifact_type", sa.Text(), nullable=False), sa.Column("content_hash", sa.Text(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("run_id", "artifact_type", "content_hash", name="uq_runtime_artifact_hash"))
    op.create_index("ix_runtime_artifact_run_id", "runtime_artifact", ["run_id"])


def downgrade() -> None:
    for table in ("runtime_artifact", "runtime_evidence", "runtime_event", "runtime_workflow_step", "runtime_workflow_run"):
        op.drop_table(table)
