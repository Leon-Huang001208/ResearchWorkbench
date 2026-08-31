"""Add merged-platform fact core, durable events, and scheduler coordination.

Revision ID: 015
Revises: 014
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the five shared fact-kernel tables."""

    op.create_table(
        "asset_registry",
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index("ix_asset_registry_asset_type", "asset_registry", ["asset_type"])
    op.create_index("ix_asset_registry_status", "asset_registry", ["status"])

    op.create_table(
        "asset_identifier",
        sa.Column("identifier_id", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("scheme", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["asset_registry.asset_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("identifier_id"),
        sa.UniqueConstraint(
            "scheme", "value", "market", "valid_from", name="uq_asset_identifier_identity"
        ),
    )
    for column in ("asset_id", "scheme", "value", "valid_from", "valid_to"):
        op.create_index(f"ix_asset_identifier_{column}", "asset_identifier", [column])

    op.create_table(
        "theme_observation",
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("pack_key", sa.Text(), nullable=False),
        sa.Column("dataset_key", sa.Text(), nullable=False),
        sa.Column("row_identity", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("missing_reason", sa.Text(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("freshness_status", sa.Text(), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("observation_id"),
        sa.UniqueConstraint(
            "pack_key",
            "dataset_key",
            "row_identity",
            "source_hash",
            name="uq_theme_observation_source_row",
        ),
    )
    for column in (
        "pack_key",
        "dataset_key",
        "subject_ref",
        "metric_key",
        "as_of",
        "observed_at",
        "available_at",
        "freshness_status",
        "source_hash",
    ):
        op.create_index(f"ix_theme_observation_{column}", "theme_observation", [column])

    op.create_table(
        "scheduled_job",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="idle"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allow_concurrent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("coalesce_policy", sa.Text(), nullable=False, server_default="latest"),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("owner", "idempotency_key", name="uq_scheduled_job_idempotency"),
    )
    for column in (
        "owner",
        "job_type",
        "status",
        "scheduled_for",
        "lease_owner",
        "lease_expires_at",
    ):
        op.create_index(f"ix_scheduled_job_{column}", "scheduled_job", [column])

    op.create_table(
        "domain_event",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_domain_event_idempotency"),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "sequence",
            name="uq_domain_event_aggregate_sequence",
        ),
    )
    for column in (
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "occurred_at",
        "published_at",
    ):
        op.create_index(f"ix_domain_event_{column}", "domain_event", [column])


def downgrade() -> None:
    """Drop the fact-kernel tables in dependency-safe order."""

    op.drop_table("domain_event")
    op.drop_table("scheduled_job")
    op.drop_table("theme_observation")
    op.drop_table("asset_identifier")
    op.drop_table("asset_registry")
