"""Add DataHub source snapshots, complete rows, bars and batch ledger (019)."""

import sqlalchemy as sa
from alembic import op

from core.observability import get_logger

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None
logger = get_logger(__name__)


def upgrade():
    logger.info("migration starting", revision=revision)
    op.create_table(
        "datahub_snapshot",
        sa.Column("snapshot_id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("source", sa.Text(), nullable=False, primary_key=False),
        sa.Column("dataset", sa.Text(), nullable=False, primary_key=False),
        sa.Column("query_hash", sa.Text(), nullable=False, primary_key=False),
        sa.Column("content_hash", sa.Text(), nullable=False, primary_key=False),
        sa.Column("params", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("columns", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("raw_uri", sa.Text(), nullable=False, primary_key=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("quarantined_count", sa.Integer(), nullable=False, primary_key=False),
        sa.UniqueConstraint(
            "source", "dataset", "query_hash", "content_hash", name="uq_datahub_snapshot_content"
        ),
    )
    op.create_index("ix_datahub_snapshot_dataset", "datahub_snapshot", ["dataset"])
    op.create_index("ix_datahub_snapshot_query_hash", "datahub_snapshot", ["query_hash"])
    op.create_index("ix_datahub_snapshot_source", "datahub_snapshot", ["source"])
    op.create_table(
        "datahub_row",
        sa.Column("row_id", sa.Text(), nullable=False, primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Text(),
            sa.ForeignKey("datahub_snapshot.snapshot_id", ondelete="CASCADE"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, primary_key=False),
        sa.Column(
            "asset_id",
            sa.Text(),
            sa.ForeignKey("asset_registry.asset_id", ondelete=None),
            nullable=True,
            primary_key=False,
        ),
        sa.Column("symbol", sa.Text(), nullable=True, primary_key=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("freshness_status", sa.Text(), nullable=False, primary_key=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("units", sa.JSON(), nullable=False, primary_key=False),
        sa.Column("payload", sa.JSON(), nullable=False, primary_key=False),
        sa.UniqueConstraint("snapshot_id", "position", name="uq_datahub_row_position"),
    )
    op.create_index("ix_datahub_row_as_of", "datahub_row", ["as_of"])
    op.create_index("ix_datahub_row_asset_id", "datahub_row", ["asset_id"])
    op.create_index("ix_datahub_row_freshness_status", "datahub_row", ["freshness_status"])
    op.create_index("ix_datahub_row_snapshot_id", "datahub_row", ["snapshot_id"])
    op.create_index("ix_datahub_row_symbol", "datahub_row", ["symbol"])
    op.create_table(
        "datahub_market_bar",
        sa.Column("bar_id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("source", sa.Text(), nullable=False, primary_key=False),
        sa.Column("symbol", sa.Text(), nullable=False, primary_key=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column("cycle", sa.Text(), nullable=False, primary_key=False),
        sa.Column("adjustment", sa.Text(), nullable=False, primary_key=False),
        sa.Column(
            "row_id",
            sa.Text(),
            sa.ForeignKey("datahub_row.row_id", ondelete=None),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("open", sa.Numeric(), nullable=True, primary_key=False),
        sa.Column("high", sa.Numeric(), nullable=True, primary_key=False),
        sa.Column("low", sa.Numeric(), nullable=True, primary_key=False),
        sa.Column("close", sa.Numeric(), nullable=False, primary_key=False),
        sa.Column("volume", sa.Numeric(), nullable=True, primary_key=False),
        sa.Column("amount", sa.Numeric(), nullable=True, primary_key=False),
        sa.UniqueConstraint(
            "source", "symbol", "timestamp", "cycle", "adjustment", name="uq_datahub_bar_identity"
        ),
    )
    op.create_index("ix_datahub_market_bar_symbol", "datahub_market_bar", ["symbol"])
    op.create_index("ix_datahub_market_bar_timestamp", "datahub_market_bar", ["timestamp"])
    op.create_table(
        "datahub_run_item",
        sa.Column("item_id", sa.Text(), nullable=False, primary_key=True),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("scheduled_job.job_id", ondelete="CASCADE"),
            nullable=False,
            primary_key=False,
        ),
        sa.Column("batch_key", sa.Text(), nullable=False, primary_key=False),
        sa.Column(
            "snapshot_id",
            sa.Text(),
            sa.ForeignKey("datahub_snapshot.snapshot_id", ondelete=None),
            nullable=True,
            primary_key=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, primary_key=False),
        sa.Column("error_code", sa.Text(), nullable=True, primary_key=False),
        sa.Column("saved", sa.Integer(), nullable=False, primary_key=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint("job_id", "batch_key", name="uq_datahub_run_batch"),
    )
    op.create_index("ix_datahub_run_item_job_id", "datahub_run_item", ["job_id"])


def downgrade():
    logger.info("migration rollback", revision=revision)
    op.drop_table("datahub_run_item")
    op.drop_table("datahub_market_bar")
    op.drop_table("datahub_row")
    op.drop_table("datahub_snapshot")
