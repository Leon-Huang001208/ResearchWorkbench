from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class MappingStrength(float, Enum):
    """映射强度评分定义"""
    DIRECT_IMPACT = 0.9  # 直接收入/订单影响
    STRONG_LINKAGE = 0.7  # 强供应链关联
    SECONDARY_LINKAGE = 0.5  # 二级关联
    THEMATIC_ASSOCIATION = 0.3  # 主题关联


class IndustryNode(BaseModel):
    """产业链节点定义"""
    node_id: str
    name: str
    industry: str
    symbol: Optional[str] = None  # 对应的A股代码（如果是公司节点）
    is_company: bool = False
    metadata: Dict = Field(default_factory=dict)


class IndustryEdge(BaseModel):
    """产业链边关系定义"""
    from_node: str
    to_node: str
    relationship_type: str  # e.g., "supplies", "uses", "competes"
    strength: float = MappingStrength.STRONG_LINKAGE
    metadata: Dict = Field(default_factory=dict)


class IndustryGraph(BaseModel):
    """产业链图结构"""
    graph_id: str
    name: str
    description: str
    nodes: List[IndustryNode] = Field(default_factory=list)
    edges: List[IndustryEdge] = Field(default_factory=list)
    
    def get_node(self, node_id: str) -> Optional[IndustryNode]:
        """根据ID获取节点"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def get_outgoing_edges(self, node_id: str) -> List[IndustryEdge]:
        """获取从指定节点出发的所有边"""
        return [edge for edge in self.edges if edge.from_node == node_id]


class PropagationStep(BaseModel):
    """产业链传播路径步骤"""
    node_id: str
    node_name: str
    impact: str
    mapping_strength: float
    symbol: Optional[str] = None


class PropagationPath(BaseModel):
    """完整的产业链传播路径"""
    steps: List[PropagationStep] = Field(default_factory=list)
    overall_strength: float = 0.0
    
    def calculate_overall_strength(self) -> float:
        """计算整体传播强度（取几何平均）"""
        if not self.steps:
            return 0.0
        product = 1.0
        for step in self.steps:
            product *= step.mapping_strength
        return product ** (1 / len(self.steps))


class ThesisCard(BaseModel):
    """结构化投资主题卡片"""
    thesis_id: str
    event_summary: str
    propagation_path: PropagationPath
    target_symbol: str
    target_name: str
    mapping_reason: str
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    invalidation_conditions: List[str] = Field(default_factory=list)
    overall_confidence: float
    impact_direction: str  # "positive", "negative", "mixed"
    created_at: str
