"""Strict Q-P-g-M-X snapshot contract for dollar liquidity research."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..base import BlockMeta, GapRecord


class DollarModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(DollarModel):
    date: str = Field(min_length=1, max_length=40)
    value: float


class Series(DollarModel):
    label: str = Field(min_length=1, max_length=120)
    unit: str = Field(min_length=1, max_length=40)
    points: list[Point] = Field(min_length=2, max_length=400)


class Metric(DollarModel):
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=80)
    direction: str = Field(min_length=1, max_length=40)
    interpretation: str = Field(min_length=1, max_length=240)
    proxy: bool = False


class DimensionBlock(BlockMeta):
    key: Literal["Q", "P", "g", "M", "X"]
    label: str = Field(min_length=1, max_length=120)
    score: float | None = Field(default=None, ge=-1, le=1)
    summary: str = Field(min_length=1, max_length=320)
    metrics: list[Metric] = Field(min_length=1, max_length=12)
    series: list[Series] = Field(min_length=1, max_length=8)


class ResearchState(DollarModel):
    label: Literal["偏松", "中性", "偏紧", "待核验"]
    score: float | None = Field(default=None, ge=-1, le=1)
    known_subtotal: float = Field(ge=-1, le=1)
    possible_low: float = Field(ge=-1, le=1)
    possible_high: float = Field(ge=-1, le=1)
    confidence: int = Field(ge=0, le=100)
    supports: list[str] = Field(default_factory=list, max_length=10)
    drags: list[str] = Field(default_factory=list, max_length=10)
    next_check: str = Field(min_length=1, max_length=320)


class TransmissionLink(DollarModel):
    source: str
    target: str
    state: str
    explanation: str


class Transmission(BlockMeta):
    links: list[TransmissionLink] = Field(min_length=1, max_length=12)


class Event(DollarModel):
    date: str
    type: str
    title: str
    impact: str
    status: str


class Evidence(DollarModel):
    date: str
    source: str
    observation: str
    use: str
    quality: str
    url: str


class DollarSnapshot(DollarModel):
    schema_version: Literal[1] = 1
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    as_of: str
    fetched_at: str
    status: Literal["偏松", "中性", "偏紧", "待核验"]
    coverage: int = Field(ge=0, le=100)
    quantity_q: DimensionBlock
    price_p: DimensionBlock
    fiscal_g: DimensionBlock
    plumbing_m: DimensionBlock
    cross_border_x: DimensionBlock
    research_state: ResearchState
    transmission: Transmission
    events: list[Event] = Field(default_factory=list, max_length=80)
    evidence: list[Evidence] = Field(default_factory=list, max_length=120)
    gaps: list[GapRecord] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def enforce_verification_gate(self):
        dimensions = (
            self.quantity_q,
            self.price_p,
            self.fiscal_g,
            self.plumbing_m,
            self.cross_border_x,
        )
        incomplete = any(
            block.score is None or block.status in {"missing", "stale"} for block in dimensions
        )
        blocking_gap = any(gap.severity == "high" for gap in self.gaps)
        if (incomplete or blocking_gap) and self.status != "待核验":
            raise ValueError("an uncomputable dollar dimension requires 待核验")
        if self.research_state.label != self.status:
            raise ValueError("research state must match snapshot status")
        if self.research_state.possible_low > self.research_state.possible_high:
            raise ValueError("invalid dollar score range")
        return self
