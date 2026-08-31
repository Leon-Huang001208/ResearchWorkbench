"""Shared identity, provenance, freshness, event, and scheduling contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetType(str, Enum):
    """Asset classes supported by the merged observation surface."""

    STOCK = "stock"
    INDEX = "index"
    ETF = "etf"
    ACTIVE_FUND = "active_fund"


class FreshnessStatus(str, Enum):
    """Point-in-time usability of a fact response."""

    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    QUARANTINED = "quarantined"


class SourceTier(str, Enum):
    """Trust tier of a traceable source."""

    LICENSED = "licensed"
    OFFICIAL = "official"
    PUBLIC = "public"
    USER = "user"


class AssetRef(BaseModel):
    """Stable internal asset identity without duplicating asset facts."""

    model_config = ConfigDict(frozen=True)

    asset_id: str = Field(min_length=1)
    asset_type: AssetType
    display_name: str | None = None


class AssetIdentifier(BaseModel):
    """Time-bounded vendor or market identifier for an asset."""

    model_config = ConfigDict(frozen=True)

    asset_id: str = Field(min_length=1)
    scheme: str = Field(min_length=1)
    value: str = Field(min_length=1)
    market: str = Field(min_length=1)
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def validate_validity_window(self) -> AssetIdentifier:
        """Reject an identifier whose validity interval runs backwards."""

        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class SourceRef(BaseModel):
    """Safe, credential-free pointer to the origin of a fact."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tier: SourceTier
    content_hash: str | None = None
    source_url: str | None = None

    @model_validator(mode="after")
    def validate_traceability(self) -> SourceRef:
        """Require immutable content identity or a controlled source URL."""

        if not self.content_hash and not self.source_url:
            raise ValueError("content_hash or source_url is required")
        if self.source_url and not self.source_url.startswith(("https://", "http://")):
            raise ValueError("source_url must use http or https")
        return self


class FactResponseBase(BaseModel):
    """Mandatory temporal and provenance context for every fact response."""

    as_of: datetime
    observed_at: datetime
    available_at: datetime
    source_refs: list[SourceRef] = Field(min_length=1)
    freshness_status: FreshnessStatus
    quality_flags: list[str]

    @model_validator(mode="after")
    def validate_time_order(self) -> FactResponseBase:
        """Ensure a fact cannot become available before it was observed."""

        if self.available_at < self.observed_at:
            raise ValueError("available_at must be on or after observed_at")
        return self


class ObservationEnvelope(FactResponseBase):
    """Typed fact observation with explicit missing-value and unit semantics."""

    observation_id: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    value: int | float | str | bool | None
    unit: str | None = None
    missing_reason: str | None = None
    source_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_value_semantics(self) -> ObservationEnvelope:
        """Keep numeric units and missing values unambiguous."""

        is_numeric = isinstance(self.value, (int, float)) and not isinstance(self.value, bool)
        if is_numeric and not self.unit:
            raise ValueError("numeric value requires unit")
        if self.value is None and not self.missing_reason:
            raise ValueError("missing value requires missing_reason")
        if self.value is not None and self.missing_reason is not None:
            raise ValueError("missing_reason is only valid when value is missing")
        return self


class DomainEvent(BaseModel):
    """Durable domain-event record; transports carry only its reference."""

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    occurred_at: datetime
    payload_ref: str = Field(min_length=1)
    aggregate_type: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    sequence: int = Field(ge=0)


class ScheduledJobStatus(str, Enum):
    """Durable scheduler state owned by PostgreSQL."""

    IDLE = "idle"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"


class ScheduledJob(BaseModel):
    """Single-flight scheduled work with lease and idempotency semantics."""

    job_id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: ScheduledJobStatus = ScheduledJobStatus.IDLE
    scheduled_for: datetime
    allow_concurrent: bool = False
    coalesce_policy: str = "latest"
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_single_flight(self) -> ScheduledJob:
        """Keep the coordinator on the approved no-reentry/latest policy."""

        if self.allow_concurrent:
            raise ValueError("scheduled jobs do not allow concurrent reentry")
        if self.coalesce_policy != "latest":
            raise ValueError("scheduled jobs must coalesce to latest")
        if (self.lease_owner is None) != (self.lease_expires_at is None):
            raise ValueError("lease_owner and lease_expires_at must be set together")
        return self
