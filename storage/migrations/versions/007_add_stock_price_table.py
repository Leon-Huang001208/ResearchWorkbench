"""Add stock price data table

Revision ID: 007
Revises: 006
Create Date: 2026-05-09

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 stock_price_data 表
    op.create_table(
        "stock_price_data",
        sa.Column("price_id", sa.Text(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("date", sa.Text(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.Numeric(), nullable=True),
        sa.Column("turnover", sa.Numeric(), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False, server_default="manual"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")
        ),
    )
    # 创建索引
    op.create_index("idx_stock_price_code", "stock_price_data", ["code"])
    op.create_index("idx_stock_price_date", "stock_price_data", ["date"])


def downgrade() -> None:
    op.drop_index("idx_stock_price_date", "stock_price_data")
    op.drop_index("idx_stock_price_code", "stock_price_data")
    op.drop_table("stock_price_data")
