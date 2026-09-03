"""DataHub-owned immutable source snapshots, rows, bars, and job batch ledger."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint

from data_layer.repositories.base import Base
from data_layer.repositories.models import utc_now


class DataHubSnapshotDB(Base):
    __tablename__ = "datahub_snapshot"
    snapshot_id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False, index=True)
    dataset = Column(Text, nullable=False, index=True)
    query_hash = Column(Text, nullable=False, index=True)
    content_hash = Column(Text, nullable=False)
    params = Column(JSON, nullable=False)
    columns = Column(JSON, nullable=False)
    raw_uri = Column(Text, nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    available_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_checked_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    row_count = Column(Integer, nullable=False)
    quarantined_count = Column(Integer, nullable=False, default=0)
    __table_args__ = (
        UniqueConstraint(
            "source", "dataset", "query_hash", "content_hash", name="uq_datahub_snapshot_content"
        ),
    )


class DataHubRowDB(Base):
    __tablename__ = "datahub_row"
    row_id = Column(Text, primary_key=True)
    snapshot_id = Column(
        Text,
        ForeignKey("datahub_snapshot.snapshot_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False)
    asset_id = Column(Text, ForeignKey("asset_registry.asset_id"), nullable=True, index=True)
    symbol = Column(Text, nullable=True, index=True)
    as_of = Column(DateTime(timezone=True), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    available_at = Column(DateTime(timezone=True), nullable=False)
    freshness_status = Column(Text, nullable=False, index=True)
    quality_flags = Column(JSON, nullable=False)
    units = Column(JSON, nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("snapshot_id", "position", name="uq_datahub_row_position"),)


class DataHubBarDB(Base):
    __tablename__ = "datahub_market_bar"
    bar_id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False)
    symbol = Column(Text, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    cycle = Column(Text, nullable=False)
    adjustment = Column(Text, nullable=False)
    row_id = Column(Text, ForeignKey("datahub_row.row_id"), nullable=False)
    open = Column(Numeric, nullable=True)
    high = Column(Numeric, nullable=True)
    low = Column(Numeric, nullable=True)
    close = Column(Numeric, nullable=False)
    volume = Column(Numeric, nullable=True)
    amount = Column(Numeric, nullable=True)
    __table_args__ = (
        UniqueConstraint(
            "source", "symbol", "timestamp", "cycle", "adjustment", name="uq_datahub_bar_identity"
        ),
    )


class DataHubRunItemDB(Base):
    __tablename__ = "datahub_run_item"
    item_id = Column(Text, primary_key=True)
    job_id = Column(
        Text, ForeignKey("scheduled_job.job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_key = Column(Text, nullable=False)
    snapshot_id = Column(Text, ForeignKey("datahub_snapshot.snapshot_id"), nullable=True)
    status = Column(Text, nullable=False)
    error_code = Column(Text, nullable=True)
    saved = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (UniqueConstraint("job_id", "batch_key", name="uq_datahub_run_batch"),)
