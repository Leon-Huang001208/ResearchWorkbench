"""Response models that document shape only.

These models are attached through ``responses={200: {"model": ...}}`` (or the
matching success code), which FastAPI uses **only** when building the OpenAPI
schema. They are deliberately *not* passed as ``response_model``: that would
validate and filter live responses, which would silently drop fields the
current handlers return (for example legacy keys kept for old clients).

Rule for this module: every field listed here must exist in the real handler
output. Fields that a handler may omit are typed ``| None`` and default to
``None`` so the schema never claims a field is always present.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Doc(BaseModel):
    """Base for documentation-only models."""

    model_config = ConfigDict(extra="allow")


class DatasetCard(_Doc):
    """Frozen dataset projection returned once a query completes."""

    dataset_id: str | None = None
    name: str | None = None
    capability: str | None = None
    source: str | None = None
    provider: str | None = None
    status: str | None = None
    row_count: int | None = None
    as_of: str | None = None
    retrieved_at: str | None = None
    actual_range: dict[str, Any] | None = None
    missing: list[Any] | None = None
    limitations: list[str] | None = None
    files: list[dict[str, Any]] | None = None


class DeskQueryRecord(_Doc):
    """Public projection of one desk query (``_public_query`` allowlist)."""

    id: str
    status: Literal["running", "completed", "failed", "cancelled"] | str
    section: Literal["market", "assets", "funds", "industry", "documents", "reports"] | str
    session_id: str
    capability: str
    source: str
    created_at: float
    completed_at: float | None = None
    duration_ms: int | None = None
    failure_code: str | None = None
    dataset: DatasetCard | None = None


class DeskQueryList(_Doc):
    """``GET /data/queries`` envelope."""

    items: list[DeskQueryRecord] = Field(default_factory=list)


class ErrorBody(_Doc):
    """Stable error envelope raised by ``StoreError``."""

    code: str
    message: str


class ErrorEnvelope(_Doc):
    error: ErrorBody


class BlockCard(_Doc):
    """One asset block inside an observation (``public_observation``)."""

    dataset: DatasetCard | None = None
    requested_source: str | None = None
    requested_range: dict[str, Any] | None = None
    status: str | None = None
    failure_code: str | None = None
    progress: dict[str, Any] | None = None


class RequestParameters(_Doc):
    """The subset of the original request that survives to the public view."""

    start_date: str | None = None
    end_date: str | None = None
    frequency: Literal["daily", "weekly", "monthly"] | str | None = None
    adjustment: Literal["none", "qfq", "hfq"] | str | None = None
    section_sources: dict[str, str] = Field(default_factory=dict)
    section_ranges: dict[str, dict[str, str]] = Field(default_factory=dict)


class AssetObservation(_Doc):
    """Public projection of one asset observation.

    ``request``, ``refresh_keys`` and ``history_generation`` are removed by the
    serializer; internal idempotency keys and raw provider payloads never appear.
    """

    id: str
    asset: str
    asset_type: str
    source: str | None = None
    created_at: float | None = None
    updated_at: float | None = None
    request_parameters: RequestParameters
    blocks: dict[str, BlockCard] = Field(default_factory=dict)
    dataset_ids: list[str] = Field(default_factory=list)
    history_job: dict[str, Any] | None = None


class AssetObservationList(_Doc):
    """``GET /assets/observations`` envelope."""

    items: list[AssetObservation] = Field(default_factory=list)
