"""Add normalized ResearchSubject fields while preserving target_id.

Revision ID: 014
Revises: 013
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_run",
        sa.Column("subject_type", sa.Text(), nullable=False, server_default="security"),
    )
    op.add_column(
        "research_run",
        sa.Column("subject_payload", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_research_run_subject_type", "research_run", ["subject_type"])


def downgrade() -> None:
    op.drop_index("ix_research_run_subject_type", table_name="research_run")
    op.drop_column("research_run", "subject_payload")
    op.drop_column("research_run", "subject_type")
