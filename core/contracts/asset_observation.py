"""Asset observation, peer set, watchlist, alert, and notification contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from core.contracts.platform_shared import AssetRef, FactResponseBase, FreshnessStatus


class AssetSnapshotEnvelope(FactResponseBase):
    """Unified fact response for stock, index, ETF, and active fund details."""

    asset: AssetRef
    identifiers: list[str] = Field(default_factory=list)
    market_data: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    type_payload: dict[str, Any] = Field(default_factory=dict)


class PeerSet(BaseModel):
    """Transparent peer-selection rule and resulting sample."""

    peer_set_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    asset_refs: list[AssetRef] = Field(default_factory=list)
    as_of: AwareDatetime


class Watchlist(BaseModel):
    """Named, profile-scoped collection of canonical assets."""

    watchlist_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class WatchlistItem(BaseModel):
    """Watchlist entry identified only by stable canonical asset ID."""

    item_id: str = Field(min_length=1)
    watchlist_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    note: str | None = None
    created_at: AwareDatetime


class AlertOperator(str, Enum):
    """Supported deterministic alert comparison operators."""

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    PCT_CHANGE = "pct_change"


class AlertRuleStatus(str, Enum):
    """Lifecycle state of an alert rule."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class AlertRule(BaseModel):
    """Unit-aware rule evaluated only against usable fact observations."""

    rule_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    metric_type: Literal[
        "price", "nav", "change", "flow", "valuation", "holding", "announcement", "theme_event"
    ]
    metric_key: str = Field(min_length=1)
    operator: AlertOperator
    threshold: float | int | str
    unit: str | None = None
    required_freshness: FreshnessStatus = FreshnessStatus.FRESH
    cooldown_seconds: int = Field(ge=0, default=0)
    status: AlertRuleStatus = AlertRuleStatus.DRAFT

    @model_validator(mode="after")
    def validate_threshold(self) -> AlertRule:
        """Require units for numeric thresholds and fresh-only evaluation."""

        is_numeric = isinstance(self.threshold, (int, float)) and not isinstance(
            self.threshold, bool
        )
        if is_numeric and not self.unit:
            raise ValueError("numeric threshold requires unit")
        if self.required_freshness is not FreshnessStatus.FRESH:
            raise ValueError("alert evaluation requires fresh data")
        return self


class AlertEvaluationStatus(str, Enum):
    """Outcome of one rule evaluation."""

    NOT_MATCHED = "not_matched"
    TRIGGERED = "triggered"
    DEDUPLICATED = "deduplicated"
    SKIPPED_DATA_STALE = "skipped_data_stale"
    SKIPPED_DATA_UNAVAILABLE = "skipped_data_unavailable"
    SKIPPED_RULE_NOT_ELIGIBLE = "skipped_rule_not_eligible"
    FAILED_UNIT_MISMATCH = "failed_unit_mismatch"


class AlertEvaluation(BaseModel):
    """Auditable result of evaluating an alert rule."""

    rule_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    status: AlertEvaluationStatus
    evaluated_at: AwareDatetime
    alert_event_id: str | None = None
    notification_id: str | None = None


class AlertEventStatus(str, Enum):
    """Lifecycle of one false-to-true alert cycle."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertEvent(BaseModel):
    """Persisted false-to-true edge with deduplication identity."""

    event_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    dedupe_key: str = Field(min_length=1)
    status: AlertEventStatus = AlertEventStatus.OPEN
    triggered_at: AwareDatetime
    acknowledged_at: AwareDatetime | None = None
    resolved_at: AwareDatetime | None = None


class NotificationStatus(str, Enum):
    """In-app authority and optional desktop delivery projection states."""

    PENDING = "pending"
    IN_APP_DELIVERED = "in_app_delivered"
    DESKTOP_DELIVERING = "desktop_delivering"
    DESKTOP_DELIVERED = "desktop_delivered"
    DESKTOP_PERMISSION_DENIED = "desktop_permission_denied"
    DESKTOP_FAILED = "desktop_failed"


class Notification(BaseModel):
    """Safe persisted inbox message independent of desktop permission."""

    notification_id: str = Field(min_length=1)
    alert_event_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=500)
    status: NotificationStatus = NotificationStatus.PENDING
    delivery_claim_token: str | None = None
    delivery_claimed_at: AwareDatetime | None = None
    delivery_attempt: int = Field(default=0, ge=0)
    created_at: AwareDatetime
    delivered_at: AwareDatetime | None = None


class AlertBatchEvaluationSummary(BaseModel):
    """Aggregate outcome for one server-side due-alert evaluation batch."""

    evaluated: int = Field(ge=0)
    triggered: int = Field(ge=0)
    deduplicated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)
