"""Dynamic factor model contracts.

These contracts describe point-in-time factor definitions, factor values,
evaluation records, and dynamic factor weights.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FactorCategory(str, Enum):
    """Top-level factor taxonomy used by the dynamic factor layer."""

    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    RISK = "risk"
    LIQUIDITY = "liquidity"
    FLOW = "flow"
    SENTIMENT = "sentiment"
    CROWDING = "crowding"
    EVENT = "event"
    NARRATIVE = "narrative"
    TIMING = "timing"


FactorDirection = Literal["positive", "negative", "neutral"]


class FactorDefinition(BaseModel):
    """Metadata for one reproducible factor."""

    model_config = ConfigDict(extra="forbid")

    factor_id: str = Field(description="Stable machine-readable factor id")
    name: str = Field(description="Human-readable factor name")
    category: FactorCategory = Field(description="Factor taxonomy bucket")
    direction: FactorDirection = Field(
        default="positive",
        description="Whether larger raw values are expected to be positive, negative, or neutral",
    )
    description: str = Field(default="", description="Factor description")
    version: str = Field(default="v1", description="Factor definition version")
    horizon_days: int | None = Field(
        default=None,
        ge=1,
        description="Primary evaluation horizon if the factor is horizon-specific",
    )
    refresh_frequency: str = Field(default="1d", description="Expected refresh frequency")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("factor_id")
    @classmethod
    def factor_id_must_not_be_empty(cls, value: str) -> str:
        """Reject empty factor identifiers."""
        value = value.strip()
        if not value:
            raise ValueError("factor_id must not be empty")
        return value


class FactorValue(BaseModel):
    """Point-in-time factor observation for one subject."""

    model_config = ConfigDict(extra="forbid")

    factor_id: str = Field(description="Factor id matching FactorDefinition.factor_id")
    subject_id: str = Field(description="Tradable subject id, e.g. stock ticker")
    as_of_date: date = Field(description="Trading date the factor value belongs to")
    value: float | None = Field(default=None, description="Factor value; None means missing")
    available_at: datetime | None = Field(
        default=None,
        description="When this value became available to the system",
    )
    source: str | None = Field(default=None, description="Data source or pipeline stage")
    metadata: dict[str, Any] = Field(default_factory=dict)


class FactorEvaluation(BaseModel):
    """Evaluation metrics for one factor at one date or window."""

    model_config = ConfigDict(extra="forbid")

    factor_id: str
    as_of_date: date | None = None
    horizon_days: int = Field(default=20, ge=1)
    sample_size: int = Field(default=0, ge=0)
    coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    ic: float = Field(default=0.0)
    rank_ic: float = Field(default=0.0)
    decile_spread: float = Field(default=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DynamicFactorWeights(BaseModel):
    """Signed dynamic weights learned from historical factor evaluations."""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date | None = None
    lookback_periods: int = Field(default=12, ge=1)
    metric: Literal["ic", "rank_ic"] = "rank_ic"
    weights: dict[str, float] = Field(default_factory=dict)
    raw_scores: dict[str, float] = Field(default_factory=dict)

    def absolute_weight_sum(self) -> float:
        """Return the L1 norm of the signed weights."""
        return float(sum(abs(value) for value in self.weights.values()))
