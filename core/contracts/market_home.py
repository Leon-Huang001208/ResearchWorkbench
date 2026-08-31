"""Facts-only market home contracts and transparent mainline components."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.contracts.platform_shared import FactResponseBase


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
    payload: dict[str, Any] = Field(default_factory=dict)
    degradation: SectionDegradation | None = None


class MarketHomeEnvelope(BaseModel):
    """Facts-only market home response with five explicit sections."""

    trading_day: date
    trading_status: TradingStatus
    sections: list[MarketHomeSection] = Field(min_length=5, max_length=5)


class MarketHomeSnapshot(FactResponseBase):
    """Immutable close or point-in-time projection for historical reads."""

    snapshot_id: str = Field(min_length=1)
    trading_day: date
    snapshot_kind: str
    section_key: MarketHomeSectionKey
    formula_version: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    input_fact_refs: list[str] = Field(default_factory=list)
