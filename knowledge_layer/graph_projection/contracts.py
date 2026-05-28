from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    SUPPLIES = "supplies"  # A供应B
    DEPENDS_ON = "depends_on"  # A依赖B
    SUBSTITUTES = "substitutes"  # A替代B
    COMPLEMENTS = "complements"  # A互补B
    COMPETES_WITH = "competes_with"  # A竞争B
    DERIVES_FROM = "derives_from"  # A衍生自B


class SupplyChainPosition(str, Enum):
    UPSTREAM = "upstream"
    MIDSTREAM = "midstream"
    DOWNSTREAM = "downstream"


class TemporalRelation(BaseModel):
    relation_id: str
    from_entity_id: str
    to_entity_id: str
    relationship_type: RelationshipType
    strength: float = Field(ge=0.0, le=1.0)  # 关系强度
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None  # None 表示仍有效
    chain_position: Optional[SupplyChainPosition] = None
    industry: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IndustryChain(BaseModel):
    chain_id: str
    name: str
    industry: str
    nodes: list[str]  # entity_ids ordered from upstream to downstream
    relations: list[str]  # relation_ids
    as_of: Optional[datetime] = None


class PropagationPath(BaseModel):
    """@deprecated: 使用 core.contracts.industry_chain.PropagationPath 替代。

    旧版传播路径，path 字段为 list[dict]。
    新版使用 steps: list[PropagationStep]，结构更清晰。
    PropagationAnalyzer.analyze_impact_propagation() 现在返回 core 版本。
    """

    path_id: str
    trigger_event_type: str
    affected_chain_id: str
    path: list[
        dict
    ]  # [{"entity_id": "...", "position": "upstream", "expected_lag_days": 5, "impact_direction": "positive"}]
    confidence: float
    historical_evidence: list[str] = Field(default_factory=list)
