"""Add factor store tables (factor_definition, factor_value, factor_evaluation, dynamic_factor_weight)

Revision ID: 011
Revises: 010
Create Date: 2026-06-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # factor_definition: 因子元数据定义
    op.create_table(
        "factor_definition",
        sa.Column("factor_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False, server_default="positive"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("refresh_frequency", sa.Text(), nullable=False, server_default="1d"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("factor_id"),
    )
    op.create_index("ix_factor_def_category", "factor_definition", ["category"])

    # factor_value: 点时因子观察值（大表，核心查询路径）
    op.create_table(
        "factor_value",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("factor_id", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "factor_id",
            "subject_id",
            "as_of_date",
            name="uq_factor_value_factor_subject_date",
        ),
    )
    op.create_index("ix_factor_value_factor_id", "factor_value", ["factor_id"])
    op.create_index("ix_factor_value_subject_id", "factor_value", ["subject_id"])
    op.create_index("ix_factor_value_as_of_date", "factor_value", ["as_of_date"])
    op.create_index(
        "ix_factor_value_factor_date",
        "factor_value",
        ["factor_id", "as_of_date"],
    )

    # factor_evaluation: 因子评估指标
    op.create_table(
        "factor_evaluation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("factor_id", sa.Text(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("ic", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rank_ic", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("decile_spread", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "factor_id",
            "as_of_date",
            "horizon_days",
            name="uq_factor_eval_factor_date_horizon",
        ),
    )
    op.create_index("ix_factor_eval_factor_id", "factor_evaluation", ["factor_id"])
    op.create_index("ix_factor_eval_as_of_date", "factor_evaluation", ["as_of_date"])

    # dynamic_factor_weight: 动态因子权重快照
    op.create_table(
        "dynamic_factor_weight",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("lookback_periods", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("metric", sa.Text(), nullable=False, server_default="rank_ic"),
        sa.Column("weights", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("raw_scores", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "as_of_date",
            "metric",
            name="uq_factor_weight_date_metric",
        ),
    )
    op.create_index("ix_factor_weight_as_of_date", "dynamic_factor_weight", ["as_of_date"])


def downgrade() -> None:
    op.drop_table("dynamic_factor_weight")
    op.drop_table("factor_evaluation")
    op.drop_table("factor_value")
    op.drop_table("factor_definition")
