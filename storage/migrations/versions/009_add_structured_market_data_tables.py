"""Add structured market data tables (AF-AUTO-007)

Revision ID: 009
Revises: 008
Create Date: 2026-05-19

"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # stock_master: 股票基础信息
    op.create_table(
        "stock_master",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("raw_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("market", sa.Text(), nullable=True),
        sa.Column("industry_level1", sa.Text(), nullable=True),
        sa.Column("industry_level2", sa.Text(), nullable=True),
        sa.Column("industry_level3", sa.Text(), nullable=True),
        sa.Column("list_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index("ix_stock_master_raw_code", "stock_master", ["raw_code"])

    # stock_daily_bar: 日行情
    op.create_table(
        "stock_daily_bar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=True),
        sa.Column("high", sa.Numeric(), nullable=True),
        sa.Column("low", sa.Numeric(), nullable=True),
        sa.Column("close", sa.Numeric(), nullable=True),
        sa.Column("volume", sa.Numeric(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("turnover", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "trade_date",
            "source",
            name="uq_stock_daily_bar_symbol_date_source",
        ),
    )
    op.create_index("ix_stock_daily_bar_symbol", "stock_daily_bar", ["symbol"])
    op.create_index("ix_stock_daily_bar_trade_date", "stock_daily_bar", ["trade_date"])

    # stock_quote_snapshot: 实时行情快照
    op.create_table(
        "stock_quote_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("quote_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_price", sa.Numeric(), nullable=True),
        sa.Column("change_pct", sa.Numeric(), nullable=True),
        sa.Column("volume", sa.Numeric(), nullable=True),
        sa.Column("amount", sa.Numeric(), nullable=True),
        sa.Column("turnover", sa.Numeric(), nullable=True),
        sa.Column("pe", sa.Numeric(), nullable=True),
        sa.Column("pb", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_quote_snapshot_symbol", "stock_quote_snapshot", ["symbol"])
    op.create_index(
        "ix_stock_quote_snapshot_quote_time",
        "stock_quote_snapshot",
        ["quote_time"],
    )

    # stock_financial_metric: 财务指标
    op.create_table(
        "stock_financial_metric",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("report_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_type", sa.Text(), nullable=True),
        sa.Column("total_revenue", sa.Numeric(), nullable=True),
        sa.Column("net_profit", sa.Numeric(), nullable=True),
        sa.Column("total_assets", sa.Numeric(), nullable=True),
        sa.Column("total_liabilities", sa.Numeric(), nullable=True),
        sa.Column("equity", sa.Numeric(), nullable=True),
        sa.Column("roe", sa.Numeric(), nullable=True),
        sa.Column("roa", sa.Numeric(), nullable=True),
        sa.Column("gross_margin", sa.Numeric(), nullable=True),
        sa.Column("net_margin", sa.Numeric(), nullable=True),
        sa.Column("debt_ratio", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_financial_metric_symbol", "stock_financial_metric", ["symbol"])
    op.create_index(
        "ix_stock_financial_metric_report_date",
        "stock_financial_metric",
        ["report_date"],
    )

    # stock_valuation: 估值指标
    op.create_table(
        "stock_valuation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pe_ttm", sa.Numeric(), nullable=True),
        sa.Column("pe_dynamic", sa.Numeric(), nullable=True),
        sa.Column("pb", sa.Numeric(), nullable=True),
        sa.Column("ps", sa.Numeric(), nullable=True),
        sa.Column("market_cap", sa.Numeric(), nullable=True),
        sa.Column("float_market_cap", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_valuation_symbol", "stock_valuation", ["symbol"])
    op.create_index("ix_stock_valuation_as_of", "stock_valuation", ["as_of"])

    # stock_shareholder: 股东信息
    op.create_table(
        "stock_shareholder",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("report_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("holder_name", sa.Text(), nullable=False),
        sa.Column("holder_rank", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Numeric(), nullable=True),
        sa.Column("holding_pct", sa.Numeric(), nullable=True),
        sa.Column("holder_type", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_shareholder_symbol", "stock_shareholder", ["symbol"])
    op.create_index("ix_stock_shareholder_report_date", "stock_shareholder", ["report_date"])

    # index_component: 指数成分
    op.create_table(
        "index_component",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_symbol", sa.Text(), nullable=False),
        sa.Column("component_symbol", sa.Text(), nullable=False),
        sa.Column("component_name", sa.Text(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_index_component_index_symbol", "index_component", ["index_symbol"])
    op.create_index(
        "ix_index_component_component_symbol",
        "index_component",
        ["component_symbol"],
    )

    # etl_run: ETL 运行记录
    op.create_table(
        "etl_run",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("job_name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_normalized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_etl_run_job_name", "etl_run", ["job_name"])
    op.create_index("ix_etl_run_source", "etl_run", ["source"])


def downgrade() -> None:
    op.drop_table("etl_run")
    op.drop_table("index_component")
    op.drop_table("stock_shareholder")
    op.drop_table("stock_valuation")
    op.drop_table("stock_financial_metric")
    op.drop_table("stock_quote_snapshot")
    op.drop_table("stock_daily_bar")
    op.drop_table("stock_master")
