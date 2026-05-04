from datetime import datetime

from pydantic import BaseModel, Field


class AssetAnalysisSnapshot(BaseModel):
    """资产分析快照 - 标准化的资产分析数据结构"""

    canonical_id: str
    as_of: datetime
    financial: dict = Field(default_factory=dict)
    fund_flow: dict = Field(default_factory=dict)
    price_volume: dict = Field(default_factory=dict)
    valuation: dict = Field(default_factory=dict)
    shareholder: dict = Field(default_factory=dict)
    industry: dict = Field(default_factory=dict)
    event_impact: list[str] = Field(default_factory=list)
    macro_exposure: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
