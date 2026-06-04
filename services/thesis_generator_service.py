import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.contracts.events import CanonicalEvent
from core.contracts.industry_chain import (
    IndustryGraph,
    IndustryNode,
    PropagationPath,
    PropagationStep,
    ThesisCard,
)
from core.observability import get_logger

logger = get_logger(__name__)


DATA_DIR = Path(__file__).parent.parent / "data" / "industry_graphs"


class ThesisGeneratorService:
    """主题生成服务：将事件转换为结构化投资主题，包含产业链传播和A股映射"""

    def __init__(self) -> None:
        self._loaded_graphs: Dict[str, IndustryGraph] = {}
        self._load_all_industry_graphs()

    def _load_all_industry_graphs(self) -> None:
        """加载所有预定义的产业链图"""
        if not DATA_DIR.exists():
            logger.error(f"Industry graph directory not found at {DATA_DIR}")
            return

        for json_file in DATA_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    graph = IndustryGraph(**data)
                    self._loaded_graphs[graph.graph_id] = graph
                    logger.info(
                        f"Loaded industry graph: {graph.graph_id} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)"
                    )
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {str(e)}")

    def list_graphs(self) -> List[dict]:
        """列出所有已加载的产业链图"""
        return [
            {
                "graph_id": g.graph_id,
                "name": g.name,
                "description": g.description,
                "node_count": len(g.nodes),
            }
            for g in self._loaded_graphs.values()
        ]

    def get_graph(self, graph_id: str) -> Optional[IndustryGraph]:
        """获取指定产业链图"""
        return self._loaded_graphs.get(graph_id)

    def generate_theses_from_event(
        self, event: CanonicalEvent, graph_id: Optional[str] = None
    ) -> List[ThesisCard]:
        """从事件生成多个投资主题卡片"""
        theses: List[ThesisCard] = []

        # Determine which graphs to use
        target_graphs = []
        if graph_id and graph_id in self._loaded_graphs:
            target_graphs.append(self._loaded_graphs[graph_id])
        else:
            # If no graph specified, use all graphs that match impacted industries
            for g in self._loaded_graphs.values():
                target_graphs.append(g)

        for graph in target_graphs:
            # Find starting nodes that match the event impacted industries
            starting_nodes = self._find_starting_nodes(event, graph)

            for start_node in starting_nodes:
                # Propagate through the graph to find all reachable company nodes
                paths = self._propagate_from_node(start_node, graph, max_depth=4)

                for path in paths:
                    if not path.steps:
                        continue

                    # Get the last step which should be a company node
                    last_step = path.steps[-1]
                    if not last_step.symbol:
                        continue

                    # Generate thesis card
                    thesis = self._build_thesis_card(event, path, last_step)
                    theses.append(thesis)

        logger.info(f"Generated {len(theses)} thesis cards for event {event.event_id}")
        return theses

    def _find_starting_nodes(
        self, event: CanonicalEvent, graph: IndustryGraph
    ) -> List[IndustryNode]:
        """找到和事件匹配的起始节点"""
        starting_nodes = []

        impacted_industries = [i.lower() for i in event.impacted_industries]

        for node in graph.nodes:
            if not node.is_company:
                # Check if node industry matches impacted industries
                node_industry = node.industry.lower()
                matches_industry = any(
                    ii in node_industry or node_industry in ii for ii in impacted_industries
                )
                if matches_industry or not impacted_industries:
                    starting_nodes.append(node)

        return starting_nodes

    def _propagate_from_node(
        self, start_node: IndustryNode, graph: IndustryGraph, max_depth: int
    ) -> List[PropagationPath]:
        """从起始节点传播，找到所有可能的路径到公司节点"""
        paths: List[PropagationPath] = []

        def dfs(current_node_id: str, current_path: List[PropagationStep], visited: set):
            if len(current_path) > max_depth:
                return

            current_node = graph.get_node(current_node_id)
            if not current_node:
                return

            # If current node is a company, add the path
            if current_node.is_company and current_node.symbol:
                path = PropagationPath(steps=current_path.copy())
                path.overall_strength = path.calculate_overall_strength()
                paths.append(path)

            # Continue propagating
            edges = graph.get_outgoing_edges(current_node_id)
            for edge in edges:
                if edge.to_node in visited:
                    continue

                next_node = graph.get_node(edge.to_node)
                if not next_node:
                    continue

                step = PropagationStep(
                    node_id=next_node.node_id,
                    node_name=next_node.name,
                    impact=f"{current_node.name} {edge.relationship_type} {next_node.name}",
                    mapping_strength=edge.strength,
                    symbol=next_node.symbol if next_node.is_company else None,
                )

                visited.add(edge.to_node)
                current_path.append(step)
                dfs(edge.to_node, current_path, visited)
                current_path.pop()
                visited.remove(edge.to_node)

        initial_step = PropagationStep(
            node_id=start_node.node_id,
            node_name=start_node.name,
            impact="Starting point from event",
            mapping_strength=1.0,
            symbol=start_node.symbol if start_node.is_company else None,
        )

        visited = set([start_node.node_id])
        dfs(start_node.node_id, [initial_step], visited)

        return paths

    def _build_thesis_card(
        self, event: CanonicalEvent, path: PropagationPath, last_step: PropagationStep
    ) -> ThesisCard:
        """构建最终的主题卡片"""
        target_symbol = last_step.symbol
        target_name = last_step.node_name

        # Build mapping reason
        mapping_reason = " -> ".join([step.node_name for step in path.steps])

        # Calculate overall confidence
        overall_confidence = path.overall_strength * event.confidence

        # Build the thesis
        thesis = ThesisCard(
            thesis_id=str(uuid.uuid4()),
            event_summary=event.summary or event.title,
            propagation_path=path,
            target_symbol=target_symbol,
            target_name=target_name,
            mapping_reason=f"Propagation path: {mapping_reason}",
            supporting_evidence=[
                f"Original event confidence: {event.confidence:.2f}",
                f"Linkage strength: {path.overall_strength:.2f}",
            ],
            contradicting_evidence=[],
            invalidation_conditions=["Event does not materialize", "Propagation chain breaks"],
            overall_confidence=overall_confidence,
            impact_direction=event.impact_direction,
            created_at=datetime.utcnow().isoformat(),
        )

        return thesis


# Module-level singleton
_thesis_generator_service: Optional[ThesisGeneratorService] = None


def get_thesis_generator_service() -> ThesisGeneratorService:
    """Get the singleton instance of ThesisGeneratorService"""
    global _thesis_generator_service
    if _thesis_generator_service is None:
        _thesis_generator_service = ThesisGeneratorService()
    return _thesis_generator_service
