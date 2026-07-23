"""Add Wind data tables (wind_consensus_estimate, wind_margin_trading, wind_block_trade, wind_daily_bar)

Revision ID: 010
Revises: 009
Create Date: 2025-06-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # wind_consensus_estimate: Wind 一致预期数据
    op.create_table(
        "wind_consensus_estimate",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cons_net_profit", sa.Numeric(), nullable=True),
        sa.Column("cons_eps", sa.Numeric(), nullable=True),
        sa.Column("cons_revenue", sa.Numeric(), nullable=True),
        sa.Column("target_price", sa.Numeric(), nullable=True),
        sa.Column("rating", sa.Numeric(), nullable=True),
        sa.Column("rating_num", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="wind"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "trade_date", "source", name="uq_wind_consensus_symbol_date_source"
        ),
    )
    op.create_index("ix_wind_consensus_symbol", "wind_consensus_estimate", ["symbol"])
    op.create_index("ix_wind_consensus_trade_date", "wind_consensus_estimate", ["trade_date"])

    # wind_margin_trading: Wind 融资融券数据
    op.create_table(
        "wind_margin_trading",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("margin_balance", sa.Numeric(), nullable=True),
        sa.Column("short_balance", sa.Numeric(), nullable=True),
        sa.Column("margin_buy", sa.Numeric(), nullable=True),
        sa.Column("margin_repay", sa.Numeric(), nullable=True),
        sa.Column("short_sell_vol", sa.Numeric(), nullable=True),
        sa.Column("short_repay_vol", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="wind"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "trade_date", "source", name="uq_wind_margin_symbol_date_source"
        ),
    )
    op.create_index("ix_wind_margin_symbol", "wind_margin_trading", ["symbol"])
    op.create_index("ix_wind_margin_trade_date", "wind_margin_trading", ["trade_date"])

    # wind_block_trade: Wind 龙虎榜数据
    op.create_table(
        "wind_block_trade",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lhb_buy_amt", sa.Numeric(), nullable=True),
        sa.Column("lhb_sell_amt", sa.Numeric(), nullable=True),
        sa.Column("lhb_buy_seat", sa.Text(), nullable=True),
        sa.Column("lhb_sell_seat", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="wind"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "trade_date", "source", name="uq_wind_block_symbol_date_source"
        ),
    )
    op.create_index("ix_wind_block_symbol", "wind_block_trade", ["symbol"])
    op.create_index("ix_wind_block_trade_date", "wind_block_trade", ["trade_date"])

    # wind_daily_bar: Wind 日行情数据（含 Wind 独家字段 adj_close, adj_factor, vwap）
    op.create_table(
        "wind_daily_bar",
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
        sa.Column("adj_close", sa.Numeric(), nullable=True),
        sa.Column("adj_factor", sa.Numeric(), nullable=True),
        sa.Column("vwap", sa.Numeric(), nullable=True),
        sa.Column("pct_change", sa.Numeric(), nullable=True),
        sa.Column("amplitude", sa.Numeric(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="wind"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "trade_date", "source", name="uq_wind_daily_bar_symbol_date_source"
        ),
    )
    op.create_index("ix_wind_daily_bar_symbol", "wind_daily_bar", ["symbol"])
    op.create_index("ix_wind_daily_bar_trade_date", "wind_daily_bar", ["trade_date"])


def downgrade() -> None:
    op.drop_table("wind_daily_bar")
    op.drop_table("wind_block_trade")
    op.drop_table("wind_margin_trading")
    op.drop_table("wind_consensus_estimate")
