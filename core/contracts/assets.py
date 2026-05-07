from datetime import datetime
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from data_layer.indicators.models import TechnicalIndicators
else:
    TechnicalIndicators = Any


class AssetAnalysisSnapshot(BaseModel):
    """资产分析快照 - 标准化的资产分析数据结构"""

    canonical_id: str
    as_of: datetime
    financial: dict[str, Any] = Field(default_factory=dict)
    fund_flow: dict[str, Any] = Field(default_factory=dict)
    price_volume: dict[str, Any] = Field(default_factory=dict)
    valuation: dict[str, Any] = Field(default_factory=dict)
    shareholder: dict[str, Any] = Field(default_factory=dict)
    industry: dict[str, Any] = Field(default_factory=dict)
    event_impact: list[str] = Field(default_factory=list)
    macro_exposure: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    technical: TechnicalIndicators | dict[str, Any] | None = Field(default_factory=dict)
    sentiment: dict[str, Any] | None = Field(default_factory=dict)
