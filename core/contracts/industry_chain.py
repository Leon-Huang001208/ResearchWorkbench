"""
Core contracts for industry chain-related data structures.

This module defines Pydantic models for industry chain graphs, nodes, edges,
propagation paths, and thesis cards, standardizing the representation of
industry chain relationships and impact propagation in AlphaFoundry.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MappingStrength(float, Enum):
    """映射强度评分定义.

    Enumeration of mapping strength scores, representing different levels
    of impact or linkage between industry chain nodes.

    Attributes:
        DIRECT_IMPACT: Direct revenue/order impact (0.9).
        STRONG_LINKAGE: Strong supply chain linkage (0.7).
        SECONDARY_LINKAGE: Secondary linkage (0.5).
        THEMATIC_ASSOCIATION: Thematic association (0.3).
    """

    DIRECT_IMPACT = 0.9  # 直接收入/订单影响
    STRONG_LINKAGE = 0.7  # 强供应链关联
    SECONDARY_LINKAGE = 0.5  # 二级关联
    THEMATIC_ASSOCIATION = 0.3  # 主题关联


class IndustryNode(BaseModel):
    """产业链节点定义.

    Represents a node in the industry chain graph, including node ID, name,
    industry, symbol (if a company), whether it's a company, and metadata.

    Attributes:
        node_id: Unique identifier for the node.
        name: Name of the node.
        industry: Industry that the node belongs to.
        symbol: Ticker symbol (if the node is a company, e.g., A-share code).
        is_company: Whether the node represents a company (True) or not (False).
        metadata: Additional metadata as a dictionary.
    """

    node_id: str = Field(description="Unique identifier for the node")
    name: str = Field(description="Name of the node")
    industry: str = Field(description="Industry that the node belongs to")
    symbol: Optional[str] = Field(
        default=None, description="Ticker symbol (if the node is a company)"
    )
    is_company: bool = Field(default=False, description="Whether the node represents a company")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class IndustryEdge(BaseModel):
    """产业链边关系定义.

    Represents an edge (relationship) between two nodes in the industry chain graph,
    including source node, target node, relationship type, strength, and metadata.

    Attributes:
        from_node: Unique identifier of the source node.
        to_node: Unique identifier of the target node.
        relationship_type: Type of relationship (e.g., "supplies", "uses", "competes").
        strength: Strength of the relationship (default: MappingStrength.STRONG_LINKAGE).
        metadata: Additional metadata as a dictionary.
    """

    from_node: str = Field(description="Unique identifier of the source node")
    to_node: str = Field(description="Unique identifier of the target node")
    relationship_type: str = Field(
        description="Type of relationship (e.g., supplies, uses, competes)"
    )
    strength: float = Field(
        default=MappingStrength.STRONG_LINKAGE, description="Strength of the relationship"
    )
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class IndustryGraph(BaseModel):
    """产业链图结构.

    Represents an industry chain graph, including graph ID, name, description,
    nodes, and edges. Also provides methods to get nodes and outgoing edges.

    Attributes:
        graph_id: Unique identifier for the graph.
        name: Name of the graph.
        description: Description of the graph.
        nodes: List of industry nodes in the graph.
        edges: List of industry edges in the graph.
    """

    graph_id: str = Field(description="Unique identifier for the graph")
    name: str = Field(description="Name of the graph")
    description: str = Field(description="Description of the graph")
    nodes: List[IndustryNode] = Field(default_factory=list, description="List of industry nodes")
    edges: List[IndustryEdge] = Field(default_factory=list, description="List of industry edges")

    def get_node(self, node_id: str) -> Optional[IndustryNode]:
        """根据ID获取节点.

        Retrieves a node from the graph by its unique identifier.

        Args:
            node_id: Unique identifier of the node to retrieve.

        Returns:
            The IndustryNode if found, None otherwise.
        """
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_outgoing_edges(self, node_id: str) -> List[IndustryEdge]:
        """获取从指定节点出发的所有边.

        Retrieves all edges that start from the specified node.

        Args:
            node_id: Unique identifier of the source node.

        Returns:
            List of IndustryEdge objects starting from the specified node.
        """
        return [edge for edge in self.edges if edge.from_node == node_id]


class PropagationStep(BaseModel):
    """产业链传播路径步骤.

    Represents a single step in an industry chain propagation path, including
    node ID, node name, impact, mapping strength, and symbol (if applicable).

    Attributes:
        node_id: Unique identifier of the node in this step.
        node_name: Name of the node in this step.
        impact: Description of the impact on this node.
        mapping_strength: Strength of the mapping/linkage for this step.
        symbol: Ticker symbol of the node (if applicable).
    """

    node_id: str = Field(description="Unique identifier of the node in this step")
    node_name: str = Field(description="Name of the node in this step")
    impact: str = Field(description="Description of the impact on this node")
    mapping_strength: float = Field(description="Strength of the mapping/linkage for this step")
    symbol: Optional[str] = Field(
        default=None, description="Ticker symbol of the node (if applicable)"
    )


class PropagationPath(BaseModel):
    """完整的产业链传播路径.

    Represents a complete industry chain propagation path, including steps
    and overall strength. Also provides a method to calculate the overall
    strength as the geometric mean of step strengths.

    Attributes:
        steps: List of propagation steps in the path.
        overall_strength: Overall strength of the propagation path (default 0.0).
    """

    steps: List[PropagationStep] = Field(
        default_factory=list, description="List of propagation steps"
    )
    overall_strength: float = Field(
        default=0.0, description="Overall strength of the propagation path"
    )

    def calculate_overall_strength(self) -> float:
        """计算整体传播强度（取几何平均）.

        Calculates the overall strength of the propagation path as the
        geometric mean of the mapping strengths of each step.

        Returns:
            The geometric mean of step strengths (0.0 if there are no steps).
        """
        if not self.steps:
            return 0.0
        product = 1.0
        for step in self.steps:
            product *= step.mapping_strength
        return float(product ** (1 / len(self.steps)))


class ThesisCard(BaseModel):
    """结构化投资主题卡片.

    Represents a structured investment thesis card, including thesis ID, event summary,
    propagation path, target symbol/name, mapping reason, supporting/contradicting
    evidence, invalidation conditions, overall confidence, impact direction, and
    creation timestamp.

    Attributes:
        thesis_id: Unique identifier for the thesis.
        event_summary: Summary of the event that triggered the thesis.
        propagation_path: Propagation path for the thesis.
        target_symbol: Ticker symbol of the target asset.
        target_name: Name of the target asset.
        mapping_reason: Reason for mapping the event to the target.
        supporting_evidence: List of supporting evidence references.
        contradicting_evidence: List of contradicting evidence references.
        invalidation_conditions: List of conditions that would invalidate the thesis.
        overall_confidence: Overall confidence score (0.0 to 1.0) for the thesis.
        impact_direction: Direction of impact ("positive", "negative", "mixed").
        created_at: Timestamp when the thesis was created (as a string).
    """

    thesis_id: str = Field(description="Unique identifier for the thesis")
    event_summary: str = Field(description="Summary of the event that triggered the thesis")
    propagation_path: PropagationPath = Field(description="Propagation path for the thesis")
    target_symbol: str = Field(description="Ticker symbol of the target asset")
    target_name: str = Field(description="Name of the target asset")
    mapping_reason: str = Field(description="Reason for mapping the event to the target")
    supporting_evidence: List[str] = Field(
        default_factory=list, description="List of supporting evidence references"
    )
    contradicting_evidence: List[str] = Field(
        default_factory=list, description="List of contradicting evidence references"
    )
    invalidation_conditions: List[str] = Field(
        default_factory=list, description="List of invalidation conditions"
    )
    overall_confidence: float = Field(description="Overall confidence score (0.0 to 1.0)")
    impact_direction: str = Field(description="Direction of impact (positive, negative, mixed)")
    created_at: str = Field(description="Timestamp when the thesis was created")
