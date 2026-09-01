"""Facts-only market home contracts and transparent mainline components."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from core.contracts.platform_shared import FactResponseBase, FreshnessStatus, SourceRef


class TradingStatus(str, Enum):
    """A-share trading-session state used by market home."""

    PRE_OPEN = "pre_open"
    OPEN = "open"
    LUNCH_BREAK = "lunch_break"
    CLOSED = "closed"
    NON_TRADING_DAY = "non_trading_day"


class MarketHomeSectionKey(str, Enum):
    """The five fixed facts-only market home sections."""

    GLOBAL_CONTEXT = "global_context"
    A_SHARE_STATUS = "a_share_status"
    MARKET_MAINLINES = "market_mainlines"
    IMPORTANT_EVENTS = "important_events"
    ASSET_MOVES = "asset_moves"


class SectionStatus(str, Enum):
    """Independent readiness state of one home section."""

    READY = "ready"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"


class SectionDegradation(BaseModel):
    """Stable partial-failure description for one market section."""

    error_code: str = Field(min_length=1)
    retryable: bool
    missing_components: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class MainlineCandidate:
    """Internal facts projection consumed by the versioned mainline formula."""

    theme_key: str
    label: str
    return_value: float
    turnover_change: float
    breadth: float
    verified_event_density: float


class MainlineCandidateBatch(FactResponseBase):
    """Quality-gated same-watermark inputs plus explicit rejected components."""

    candidates: list[MainlineCandidate] = Field(default_factory=list)
    missing_components: list[str] = Field(default_factory=list)


class MainlineComponents(BaseModel):
    """Versioned inputs to the transparent market-mainline score."""

    return_percentile: float = Field(ge=0.0, le=100.0)
    turnover_change_percentile: float = Field(ge=0.0, le=100.0)
    breadth_percentile: float = Field(ge=0.0, le=100.0)
    event_density_percentile: float = Field(ge=0.0, le=100.0)
    sample_size: int = Field(gt=0)
    formula_version: str = "mainline-v1"


class MainlineRank(BaseModel):
    """Ranked theme with every score component exposed."""

    theme_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    direction: str
    score: float = Field(ge=0.0, le=100.0)
    components: MainlineComponents


class MarketHomeSection(FactResponseBase):
    """Independently degradable, source-backed home section."""

    section_key: MarketHomeSectionKey
    status: SectionStatus
    age_seconds: float = Field(default=0.0, ge=0.0)
    source_refs: list[SourceRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    degradation: SectionDegradation | None = None

    @model_validator(mode="after")
    def validate_failure_provenance(self) -> MarketHomeSection:
        """Allow no source only for an explicitly unavailable section."""

        is_unavailable = (
            self.status == SectionStatus.UNAVAILABLE
            and self.freshness_status == FreshnessStatus.UNAVAILABLE
        )
        if not self.source_refs and not is_unavailable:
            raise ValueError("source_refs are required unless section is unavailable")
        return self


class MarketHomeEnvelope(BaseModel):
    """Facts-only market home response with five explicit sections."""

    trading_day: date
    trading_status: TradingStatus
    sections: list[MarketHomeSection] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_section_set(self) -> MarketHomeEnvelope:
        """Require every fixed facts-only section exactly once."""

        expected = set(MarketHomeSectionKey)
        actual = {section.section_key for section in self.sections}
        if actual != expected or len(self.sections) != len(expected):
            raise ValueError("market home requires every fixed section exactly once")
        return self


class MarketHomeSnapshot(FactResponseBase):
    """Immutable close or point-in-time projection for historical reads."""

    snapshot_id: str = Field(min_length=1)
    trading_day: date
    snapshot_kind: str
    section_key: MarketHomeSectionKey
    formula_version: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    input_fact_refs: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_snapshot_provenance(self) -> MarketHomeSnapshot:
        """Permit an empty source list only for a captured unavailable failure."""

        if not self.source_refs and self.freshness_status != FreshnessStatus.UNAVAILABLE:
            raise ValueError("source_refs are required unless snapshot is unavailable")
        return self


class MarketHomeInvalidationEvent(BaseModel):
    """Small durable SSE reference that never embeds a section payload."""

    event_id: str = Field(min_length=1)
    section_key: MarketHomeSectionKey
    as_of: AwareDatetime
