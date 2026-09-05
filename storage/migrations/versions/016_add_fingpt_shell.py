"""Add FinGPT governance index without duplicating DSH conversation bodies.

Revision ID: 016
Revises: 015
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("fingpt_session_index", sa.Column("dsh_session_id", sa.Text(), primary_key=True), sa.Column("task_id", sa.Text()), sa.Column("title", sa.Text()), sa.Column("status", sa.Text(), nullable=False), sa.Column("sync_cursor", sa.Integer(), nullable=False), sa.Column("session_metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_fingpt_session_index_task_id", "fingpt_session_index", ["task_id"])
    op.create_index("ix_fingpt_session_index_status", "fingpt_session_index", ["status"])
    op.create_table("fingpt_task", sa.Column("task_id", sa.Text(), primary_key=True), sa.Column("preset_id", sa.Text()), sa.Column("title", sa.Text(), nullable=False), sa.Column("status", sa.Text(), nullable=False), sa.Column("dsh_session_id", sa.Text()), sa.Column("workflow_run_id", sa.Text(), sa.ForeignKey("runtime_workflow_run.run_id")), sa.Column("launch_id", sa.Text(), unique=True), sa.Column("launch_expires_at", sa.DateTime(timezone=True)), sa.Column("launch_consumed_at", sa.DateTime(timezone=True)), sa.Column("task_metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("preset_id", "status", "dsh_session_id", "workflow_run_id", "launch_id"):
        op.create_index(f"ix_fingpt_task_{column}", "fingpt_task", [column])
    op.create_table("fingpt_sync_event", sa.Column("event_key", sa.Text(), primary_key=True), sa.Column("dsh_session_id", sa.Text(), sa.ForeignKey("fingpt_session_index.dsh_session_id"), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("event_type", sa.Text(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_fingpt_sync_event_dsh_session_id", "fingpt_sync_event", ["dsh_session_id"])
    op.create_table("fingpt_evidence_reference", sa.Column("reference_id", sa.Text(), primary_key=True), sa.Column("task_id", sa.Text(), sa.ForeignKey("fingpt_task.task_id")), sa.Column("dsh_session_id", sa.Text()), sa.Column("source_ref", sa.Text(), nullable=False), sa.Column("source_name", sa.Text(), nullable=False), sa.Column("provenance", sa.Text(), nullable=False), sa.Column("captured_evidence_id", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_fingpt_evidence_reference_task_id", "fingpt_evidence_reference", ["task_id"])
    op.create_table("fingpt_artifact_link", sa.Column("link_id", sa.Text(), primary_key=True), sa.Column("task_id", sa.Text(), sa.ForeignKey("fingpt_task.task_id"), nullable=False), sa.Column("artifact_id", sa.Text(), sa.ForeignKey("runtime_artifact.artifact_id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("task_id", "artifact_id", name="uq_fingpt_task_artifact"))
    op.create_index("ix_fingpt_artifact_link_task_id", "fingpt_artifact_link", ["task_id"])
    op.create_index("ix_fingpt_artifact_link_artifact_id", "fingpt_artifact_link", ["artifact_id"])


def downgrade() -> None:
    for table in ("fingpt_artifact_link", "fingpt_evidence_reference", "fingpt_sync_event", "fingpt_task", "fingpt_session_index"):
        op.drop_table(table)
