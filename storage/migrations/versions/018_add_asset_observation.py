"""Add watchlists, deterministic alerts, and persistent notifications.

Revision ID: 018
Revises: 017
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the five personal-observation tables."""

    op.create_table(
        "watchlist",
        sa.Column("watchlist_id", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("watchlist_id"),
        sa.UniqueConstraint("profile_id", "name", name="uq_watchlist_profile_name"),
    )
    op.create_index("ix_watchlist_profile_id", "watchlist", ["profile_id"])

    op.create_table(
        "watchlist_item",
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("watchlist_id", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlist.watchlist_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["asset_registry.asset_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("item_id"),
        sa.UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_item_asset"),
    )
    op.create_index("ix_watchlist_item_watchlist_id", "watchlist_item", ["watchlist_id"])
    op.create_index("ix_watchlist_item_asset_id", "watchlist_item", ["asset_id"])

    op.create_table(
        "alert_rule",
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("metric_type", sa.Text(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("threshold", sa.JSON(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("required_freshness", sa.Text(), nullable=False, server_default="fresh"),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("state", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["asset_registry.asset_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id"),
    )
    op.create_index("ix_alert_rule_asset_id", "alert_rule", ["asset_id"])
    op.create_index("ix_alert_rule_metric_type", "alert_rule", ["metric_type"])
    op.create_index("ix_alert_rule_status", "alert_rule", ["status"])

    op.create_table(
        "alert_event",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rule.rule_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("dedupe_key", name="uq_alert_event_dedupe_key"),
    )
    op.create_index("ix_alert_event_rule_id", "alert_event", ["rule_id"])
    op.create_index("ix_alert_event_observation_id", "alert_event", ["observation_id"])
    op.create_index("ix_alert_event_status", "alert_event", ["status"])
    op.create_index("ix_alert_event_triggered_at", "alert_event", ["triggered_at"])
    op.create_index(
        "uq_alert_event_rule_active",
        "alert_event",
        ["rule_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged')"),
        sqlite_where=sa.text("status IN ('open', 'acknowledged')"),
    )

    op.create_table(
        "notification",
        sa.Column("notification_id", sa.Text(), nullable=False),
        sa.Column("alert_event_id", sa.Text(), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("delivery_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("delivery_claim_token", sa.Text(), nullable=True),
        sa.Column("delivery_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["alert_event_id"], ["alert_event.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_index("ix_notification_alert_event_id", "notification", ["alert_event_id"])
    op.create_index("ix_notification_profile_id", "notification", ["profile_id"])
    op.create_index("ix_notification_status", "notification", ["status"])
    op.create_index("ix_notification_created_at", "notification", ["created_at"])


def downgrade() -> None:
    """Drop personal-observation tables in reverse dependency order."""

    op.drop_table("notification")
    op.drop_table("alert_event")
    op.drop_table("alert_rule")
    op.drop_table("watchlist_item")
    op.drop_table("watchlist")
