"""Strict Goldar snapshot contract; domain fields intentionally remain specific."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..base import BlockMeta, GapRecord, SourceRecord


class GoldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metric(GoldModel):
    label: str
    value: str
    direction: str
    interpretation: str


class Factor(GoldModel):
    label: str
    value: float = Field(ge=-1, le=1)


class PricePoint(GoldModel):
    label: str
    value: float = Field(gt=0)


class MarketContext(BlockMeta):
    price: float = Field(gt=0)
    change_percent: float
    range_low: float = Field(gt=0)
    range_high: float = Field(gt=0)
    series: list[PricePoint] = Field(min_length=2, max_length=60)


class PricingDrivers(BlockMeta):
    factors: list[Factor] = Field(min_length=1, max_length=8)
    relationships: list[Metric] = Field(min_length=1, max_length=10)


class DemandCategory(GoldModel):
    label: str
    current: float = Field(ge=0)
    previous: float = Field(ge=0)


class FlowMetric(GoldModel):
    label: str
    value: str
    note: str


class SupplyDemand(BlockMeta):
    categories: list[DemandCategory] = Field(min_length=1, max_length=8)
    flows: list[FlowMetric] = Field(default_factory=list, max_length=8)


class Regime(GoldModel):
    label: str
    fit: str
    reason: str


class CycleMacro(BlockMeta):
    policy_phase: str
    regimes: list[Regime] = Field(min_length=1, max_length=8)


class PositionMetric(GoldModel):
    label: str
    value: str
    note: str


class Strike(GoldModel):
    label: str
    value: float = Field(ge=0)
    side: Literal["support", "neutral", "pressure"]


class OptionsPositioning(BlockMeta):
    positioning: list[PositionMetric] = Field(default_factory=list, max_length=8)
    strikes: list[Strike] = Field(min_length=1, max_length=10)


class ResearchState(GoldModel):
    label: Literal["偏强", "中性", "偏弱", "待核验"]
    score: float = Field(ge=-1, le=1)
    confidence: int = Field(ge=0, le=100)
    supports: list[str] = Field(default_factory=list, max_length=10)
    drags: list[str] = Field(default_factory=list, max_length=10)
    next_check: str


class Scenario(GoldModel):
    label: str
    gold: str
    equities: str
    bonds: str
    note: str


class AllocationContext(BlockMeta):
    diversification_note: str
    drawdown_note: str
    scenarios: list[Scenario] = Field(min_length=1, max_length=8)


class Event(GoldModel):
    date: str
    type: str
    title: str
    impact: str
    status: str


class Evidence(GoldModel):
    date: str
    source: str
    observation: str
    use: str
    quality: str
    url: str


class GoldSnapshot(GoldModel):
    schema_version: Literal[1] = 1
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    as_of: str
    fetched_at: str
    status: Literal["偏强", "中性", "偏弱", "待核验"]
    coverage: int = Field(ge=0, le=100)
    market_context: MarketContext
    pricing_drivers: PricingDrivers
    supply_demand: SupplyDemand
    cycle_macro: CycleMacro
    options: OptionsPositioning
    research_state: ResearchState
    allocation_context: AllocationContext
    events: list[Event] = Field(default_factory=list, max_length=50)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)
    gaps: list[GapRecord] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def enforce_verification_gate(self):
        critical = (self.market_context, self.pricing_drivers, self.supply_demand)
        has_blocking_gap = any(gap.severity == "high" for gap in self.gaps)
        degraded = any(block.status in {"missing", "stale"} for block in critical)
        if (has_blocking_gap or degraded) and self.status != "待核验":
            raise ValueError("critical gaps require 待核验")
        if self.research_state.label != self.status:
            raise ValueError("research state must match snapshot status")
        return self


__all__ = ["GapRecord", "GoldSnapshot", "SourceRecord"]
