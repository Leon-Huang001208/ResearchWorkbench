from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.observability import get_logger

from .contracts import IndustryChain, RelationshipType, TemporalRelation

logger = get_logger(__name__)

# 将 JSON 文件中的关系类型映射到 RelationshipType 枚举
_JSON_RELATION_MAP: dict[str, RelationshipType] = {
    "supplies": RelationshipType.SUPPLIES,
    "depends_on": RelationshipType.DEPENDS_ON,
    "substitutes": RelationshipType.SUBSTITUTES,
    "complements": RelationshipType.COMPLEMENTS,
    "competes_with": RelationshipType.COMPETES_WITH,
    "derives_from": RelationshipType.DERIVES_FROM,
    # 种子数据中的自定义类型，映射到最近似的标准类型
    "accelerates": RelationshipType.DEPENDS_ON,
    "requires": RelationshipType.DEPENDS_ON,
    "requires_local": RelationshipType.DEPENDS_ON,
    "produced_by": RelationshipType.SUPPLIES,
    "drives": RelationshipType.DEPENDS_ON,
    "drives_demand": RelationshipType.DEPENDS_ON,
    "direct_demand": RelationshipType.DEPENDS_ON,
    "uses": RelationshipType.DEPENDS_ON,
    "supplied_by": RelationshipType.SUPPLIES,
}


class IndustryGraphStore:
    """内存存储实现时间化产业链图谱"""

    def __init__(self):
        self._relations: dict[str, TemporalRelation] = {}
        self._chains: dict[str, IndustryChain] = {}
        # 邻接表: from_entity_id -> list[relation_id]
        self._adjacency: dict[str, list[str]] = {}
        # 反向邻接表: to_entity_id -> list[relation_id]
        self._reverse_adjacency: dict[str, list[str]] = {}

    def add_relation(self, relation: TemporalRelation) -> TemporalRelation:
        self._relations[relation.relation_id] = relation

        # 更新邻接表
        if relation.from_entity_id not in self._adjacency:
            self._adjacency[relation.from_entity_id] = []
        self._adjacency[relation.from_entity_id].append(relation.relation_id)

        # 更新反向邻接表
        if relation.to_entity_id not in self._reverse_adjacency:
            self._reverse_adjacency[relation.to_entity_id] = []
        self._reverse_adjacency[relation.to_entity_id].append(relation.relation_id)

        logger.debug(
            "Added relation",
            relation_id=relation.relation_id,
            from_entity=relation.from_entity_id,
            to_entity=relation.to_entity_id,
        )
        return relation

    def remove_relation(self, relation_id: str) -> bool:
        if relation_id not in self._relations:
            return False

        relation = self._relations.pop(relation_id)

        # 从邻接表移除
        if relation.from_entity_id in self._adjacency:
            if relation_id in self._adjacency[relation.from_entity_id]:
                self._adjacency[relation.from_entity_id].remove(relation_id)

        # 从反向邻接表移除
        if relation.to_entity_id in self._reverse_adjacency:
            if relation_id in self._reverse_adjacency[relation.to_entity_id]:
                self._reverse_adjacency[relation.to_entity_id].remove(relation_id)

        logger.debug("Removed relation", relation_id=relation_id)
        return True

    def get_relation(self, relation_id: str) -> Optional[TemporalRelation]:
        return self._relations.get(relation_id)

    def find_relations(
        self,
        from_entity: Optional[str] = None,
        to_entity: Optional[str] = None,
        rel_type: Optional[RelationshipType] = None,
        at_time: Optional[datetime] = None,
    ) -> List[TemporalRelation]:
        results = []

        for relation in self._relations.values():
            if from_entity is not None and relation.from_entity_id != from_entity:
                continue
            if to_entity is not None and relation.to_entity_id != to_entity:
                continue
            if rel_type is not None and relation.relationship_type != rel_type:
                continue
            if at_time is not None:
                # Check if relation is valid at this time
                if relation.valid_from is not None and at_time < relation.valid_from:
                    continue
                if relation.valid_to is not None and at_time > relation.valid_to:
                    continue
            results.append(relation)

        return results

    def add_chain(self, chain: IndustryChain) -> IndustryChain:
        self._chains[chain.chain_id] = chain
        logger.debug("Added industry chain", chain_id=chain.chain_id, name=chain.name)
        return chain

    def get_chain(self, chain_id: str) -> Optional[IndustryChain]:
        return self._chains.get(chain_id)

    def find_chains(self, industry: Optional[str] = None) -> List[IndustryChain]:
        if industry is None:
            return list(self._chains.values())
        return [chain for chain in self._chains.values() if chain.industry == industry]

    def get_upstream(
        self, entity_id: str, at_time: Optional[datetime] = None
    ) -> List[TemporalRelation]:
        """Get all relations where this entity is the downstream (to_entity), i.e., upstream suppliers/dependencies"""
        relation_ids = self._reverse_adjacency.get(entity_id, [])
        relations = [self._relations[rid] for rid in relation_ids if rid in self._relations]

        if at_time is not None:
            relations = [
                r
                for r in relations
                if (r.valid_from is None or at_time >= r.valid_from)
                and (r.valid_to is None or at_time <= r.valid_to)
            ]

        return relations

    def get_downstream(
        self, entity_id: str, at_time: Optional[datetime] = None
    ) -> List[TemporalRelation]:
        """Get all relations where this entity is the upstream (from_entity), i.e., downstream customers/dependents"""
        relation_ids = self._adjacency.get(entity_id, [])
        relations = [self._relations[rid] for rid in relation_ids if rid in self._relations]

        if at_time is not None:
            relations = [
                r
                for r in relations
                if (r.valid_from is None or at_time >= r.valid_from)
                and (r.valid_to is None or at_time <= r.valid_to)
            ]

        return relations

    def shortest_path(
        self, from_entity: str, to_entity: str, at_time: Optional[datetime] = None
    ) -> List[str]:
        """BFS to find the shortest path between two entities"""
        if from_entity == to_entity:
            return [from_entity]

        visited = {}
        queue = deque()
        queue.append((from_entity, []))
        visited[from_entity] = True

        while queue:
            current_entity, path = queue.popleft()
            current_path = path + [current_entity]

            # Get all downstream relations from current entity
            downstream = self.get_downstream(current_entity, at_time)

            for relation in downstream:
                next_entity = relation.to_entity_id
                if next_entity == to_entity:
                    return current_path + [next_entity]

                if next_entity not in visited:
                    visited[next_entity] = True
                    queue.append((next_entity, current_path))

        # No path found
        return []

    def load_from_json(self, file_path: str | Path) -> tuple[IndustryChain, list[TemporalRelation]]:
        """从 JSON 文件加载产业链数据。

        解析 data/industry_graphs/ 下的 JSON 文件，将其节点和边
        转换为 IndustryChain + TemporalRelation。已有的关系和链
        会被覆盖（add_relation / add_chain 使用相同 ID 时会更新）。

        Returns:
            (loaded_chain, loaded_relations)
        """
        file_path = Path(file_path)
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        graph_id = data["graph_id"]
        name = data.get("name", graph_id)
        industry = data.get("industry", "")
        node_ids: list[str] = [n["node_id"] for n in data.get("nodes", [])]

        relation_ids: list[str] = []
        relations: list[TemporalRelation] = []

        for edge in data.get("edges", []):
            rel_id = f"{graph_id}:{edge['from_node']}-{edge['to_node']}"
            rel_type_str = edge.get("relationship_type", "depends_on")
            rel_type = _JSON_RELATION_MAP.get(rel_type_str, RelationshipType.DEPENDS_ON)

            relation = TemporalRelation(
                relation_id=rel_id,
                from_entity_id=edge["from_node"],
                to_entity_id=edge["to_node"],
                relationship_type=rel_type,
                strength=edge.get("strength", 0.5),
                industry=data.get("industry", ""),
            )
            self.add_relation(relation)
            relation_ids.append(rel_id)
            relations.append(relation)

        chain = IndustryChain(
            chain_id=graph_id,
            name=name,
            industry=industry or name,
            nodes=node_ids,
            relations=relation_ids,
        )
        self.add_chain(chain)

        logger.info(
            "Loaded industry chain from JSON",
            chain_id=graph_id,
            name=name,
            nodes=len(node_ids),
            edges=len(relations),
        )
        return chain, relations

    def load_all_seed_data(
        self, data_dir: str | Path = "data/industry_graphs"
    ) -> list[IndustryChain]:
        """加载 data_dir 下所有 JSON 种子数据到本 store。

        Returns:
            加载的所有 IndustryChain 列表。
        """
        data_dir = Path(data_dir)
        chains: list[IndustryChain] = []
        for json_file in sorted(data_dir.glob("*.json")):
            chain, _ = self.load_from_json(json_file)
            chains.append(chain)
        return chains
