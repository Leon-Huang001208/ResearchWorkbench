"""Add index structure and ETF metric tables

Revision ID: 011
Revises: 010
Create Date: 2026-06-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "index_provider",
        sa.Column("provider_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("official_site", sa.Text(), nullable=True),
        sa.Column("source_priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("provider_code"),
    )

    op.create_table(
        "index_master",
        sa.Column("index_id", sa.Text(), nullable=False),
        sa.Column("provider_code", sa.Text(), nullable=False),
        sa.Column("official_code", sa.Text(), nullable=False),
        sa.Column("wind_code", sa.Text(), nullable=True),
        sa.Column("name_cn", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("launch_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("base_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("base_value", sa.Numeric(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("index_id"),
        sa.UniqueConstraint(
            "provider_code",
            "official_code",
            name="uq_index_master_provider_official_code",
        ),
    )
    op.create_index("ix_index_master_provider_code", "index_master", ["provider_code"])
    op.create_index("ix_index_master_official_code", "index_master", ["official_code"])
    op.create_index("ix_index_master_wind_code", "index_master", ["wind_code"])

    op.create_table(
        "index_component_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_id", sa.Text(), nullable=False),
        sa.Column("index_symbol", sa.Text(), nullable=False),
        sa.Column("provider_code", sa.Text(), nullable=False),
        sa.Column("component_symbol", sa.Text(), nullable=False),
        sa.Column("component_name", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.Column("weight_pct", sa.Numeric(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("source_scope", sa.Text(), nullable=False, server_default="full"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "index_id",
            "trade_date",
            "component_symbol",
            "source",
            name="uq_index_component_snapshot_identity",
        ),
    )
    op.create_index("ix_index_component_snapshot_index_id", "index_component_snapshot", ["index_id"])
    op.create_index(
        "ix_index_component_snapshot_index_symbol",
        "index_component_snapshot",
        ["index_symbol"],
    )
    op.create_index(
        "ix_index_component_snapshot_provider_code",
        "index_component_snapshot",
        ["provider_code"],
    )
    op.create_index(
        "ix_index_component_snapshot_component_symbol",
        "index_component_snapshot",
        ["component_symbol"],
    )
    op.create_index("ix_index_component_snapshot_as_of", "index_component_snapshot", ["as_of"])
    op.create_index(
        "ix_index_component_snapshot_trade_date",
        "index_component_snapshot",
        ["trade_date"],
    )

    _copy_legacy_index_components()

    op.create_table(
        "etf_master",
        sa.Column("etf_symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("fund_manager", sa.Text(), nullable=True),
        sa.Column("listed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("etf_symbol"),
    )

    op.create_table(
        "index_etf_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_id", sa.Text(), nullable=False),
        sa.Column("etf_symbol", sa.Text(), nullable=False),
        sa.Column("tracking_role", sa.Text(), nullable=False, server_default="tracking"),
        sa.Column("link_source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "index_id",
            "etf_symbol",
            "link_source",
            name="uq_index_etf_link_identity",
        ),
    )
    op.create_index("ix_index_etf_link_index_id", "index_etf_link", ["index_id"])
    op.create_index("ix_index_etf_link_etf_symbol", "index_etf_link", ["etf_symbol"])

    op.create_table(
        "etf_daily_metric",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("etf_symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nav", sa.Numeric(), nullable=True),
        sa.Column("close", sa.Numeric(), nullable=True),
        sa.Column("shares_outstanding", sa.Numeric(), nullable=True),
        sa.Column("aum", sa.Numeric(), nullable=True),
        sa.Column("turnover", sa.Numeric(), nullable=True),
        sa.Column("premium_discount_pct", sa.Numeric(), nullable=True),
        sa.Column("net_flow_amount", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "etf_symbol",
            "trade_date",
            "source",
            name="uq_etf_daily_metric_symbol_date_source",
        ),
    )
    op.create_index("ix_etf_daily_metric_etf_symbol", "etf_daily_metric", ["etf_symbol"])
    op.create_index("ix_etf_daily_metric_trade_date", "etf_daily_metric", ["trade_date"])


def downgrade() -> None:
    op.drop_table("etf_daily_metric")
    op.drop_table("index_etf_link")
    op.drop_table("etf_master")
    op.drop_table("index_component_snapshot")
    op.drop_table("index_master")
    op.drop_table("index_provider")


def _copy_legacy_index_components() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "index_component" not in inspector.get_table_names():
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO index_component_snapshot (
                index_id,
                index_symbol,
                provider_code,
                component_symbol,
                component_name,
                weight,
                weight_pct,
                as_of,
                trade_date,
                source,
                source_scope,
                raw_payload,
                created_at
            )
            SELECT
                source || ':' || index_symbol,
                index_symbol,
                source,
                component_symbol,
                component_name,
                weight,
                weight,
                as_of,
                as_of,
                source,
                'legacy',
                raw_payload,
                created_at
            FROM index_component
            ON CONFLICT DO NOTHING
            """
        )
    )
