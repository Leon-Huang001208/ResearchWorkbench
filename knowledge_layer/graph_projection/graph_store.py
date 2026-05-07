from collections import deque
from datetime import datetime
from typing import Optional, List
from core.observability import get_logger
from .contracts import (
    TemporalRelation,
    IndustryChain,
    RelationshipType,
    SupplyChainPosition,
)

logger = get_logger(__name__)


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
