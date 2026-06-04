"""GraphDataService — 用真实实体/关系/传播路径数据丰富行业图谱。

数据稀疏时返回 placeholder + 提示，不报错。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from core.observability import get_logger
from memory_learning.journal import LearningJournal

logger = get_logger(__name__)

EvidenceStrength = Literal["high", "medium", "low", "none"]


def _compute_evidence_strength(count: int) -> EvidenceStrength:
    """根据证据数量计算证据强度。"""
    if count >= 5:
        return "high"
    elif count >= 3:
        return "medium"
    elif count >= 1:
        return "low"
    return "none"


class GraphDataService:
    """从真实存储获取实体、关系和传播路径，丰富图谱视图。"""

    def __init__(
        self,
        event_repository: Optional[Any] = None,
        outcome_repository: Optional[Any] = None,
        entity_repository: Optional[Any] = None,
        journal: Optional[LearningJournal] = None,
    ):
        self._event_repo = event_repository
        self._outcome_repo = outcome_repository
        self._entity_repo = entity_repository
        self._journal = journal

    # ── 真实实体 ──────────────────────────────────────────

    def get_real_entities(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """从存储获取真实实体和关系。

        Args:
            event_type: 按事件类型过滤关联实体
            limit: 返回数量限制

        Returns:
            实体列表，每条包含 entity_id, name, type, real_entity=True
        """
        entities = []

        # 尝试从事件中提取实体
        if self._event_repo is not None and event_type:
            try:
                events = self._event_repo.list(limit=limit)
                if event_type:
                    events = [e for e in events if e.event_type == event_type]

                seen_entity_ids = set()
                for event in events:
                    for entity in getattr(event, "entities", []):
                        eid = entity.get("entity_id", "")
                        if eid and eid not in seen_entity_ids:
                            seen_entity_ids.add(eid)
                            entities.append(
                                {
                                    "entity_id": eid,
                                    "name": entity.get("name", eid),
                                    "type": entity.get("type", "unknown"),
                                    "real_entity": True,
                                }
                            )
            except Exception as exc:
                logger.warning("failed to extract entities from events", error=str(exc))

        # 尝试从实体仓储获取
        if not entities and self._entity_repo is not None:
            try:
                domain_entities = self._entity_repo.list(limit=limit)
                entities = [
                    {
                        "entity_id": e.canonical_id,
                        "name": e.name_zh or e.name_en or e.symbol or e.canonical_id,
                        "type": e.asset_type,
                        "real_entity": True,
                    }
                    for e in domain_entities
                ]
            except Exception as exc:
                logger.warning("failed to get entities from repository", error=str(exc))

        if not entities:
            logger.debug("no real entities available, returning empty list")

        return entities[:limit]

    # ── 传播路径 ──────────────────────────────────────────

    def get_propagation_paths(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """从存储获取传播路径。

        Args:
            event_type: 按事件类型过滤
            limit: 返回数量限制

        Returns:
            传播路径列表，每条包含 event_type, path (实体链), evidence_count, evidence_strength
        """
        paths = []

        if self._journal is not None:
            try:
                episodes = self._journal.list_episodes(event_type=event_type)
                # 按 event_type 分组
                by_type: Dict[str, List[Any]] = {}
                for ep in episodes:
                    by_type.setdefault(ep.event_type, []).append(ep)

                for etype, eps in by_type.items():
                    if not eps:
                        continue
                    # 从 episode 构建传播路径
                    path_entities = []
                    for ep in eps:
                        if ep.signal_id and ep.signal_id not in path_entities:
                            path_entities.append(ep.signal_id)

                    evidence_count = len(eps)
                    paths.append(
                        {
                            "event_type": etype,
                            "path": path_entities[:10],
                            "evidence_count": evidence_count,
                            "evidence_strength": _compute_evidence_strength(evidence_count),
                            "realized_outcomes": [
                                {
                                    "episode_id": ep.episode_id,
                                    "outcome_return": ep.outcome_return,
                                    "outcome_excess_return": ep.outcome_excess_return,
                                    "timing_action": ep.timing_action,
                                    "market_regime": ep.market_regime,
                                }
                                for ep in eps[:10]
                            ],
                        }
                    )
            except Exception as exc:
                logger.warning("failed to get propagation paths from journal", error=str(exc))

        # 尝试从事件仓储补充传播路径
        if not paths and self._event_repo is not None:
            try:
                events = self._event_repo.list(limit=limit)
                if event_type:
                    events = [e for e in events if e.event_type == event_type]

                events_by_type: Dict[str, List[Any]] = {}
                for event in events:
                    events_by_type.setdefault(event.event_type, []).append(event)

                for etype, evts in events_by_type.items():
                    entity_ids = []
                    for event in evts:
                        for entity in getattr(event, "entities", []):
                            eid = entity.get("entity_id", "")
                            if eid and eid not in entity_ids:
                                entity_ids.append(eid)

                    evidence_count = len(evts)
                    paths.append(
                        {
                            "event_type": etype,
                            "path": entity_ids[:10],
                            "evidence_count": evidence_count,
                            "evidence_strength": _compute_evidence_strength(evidence_count),
                            "realized_outcomes": [],
                        }
                    )
            except Exception as exc:
                logger.warning("failed to get propagation paths from events", error=str(exc))

        if not paths:
            logger.debug("no propagation paths available, returning empty list with hint")
            return [{"hint": "No historical data available; showing placeholder", "path": []}]

        return paths[:limit]

    # ── Outcome 路径 ──────────────────────────────────────

    def get_outcome_paths(
        self,
        subject_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """从 Outcome 记录获取实现路径。

        Args:
            subject_id: 主体ID过滤
            event_type: 事件类型过滤
            limit: 返回数量限制

        Returns:
            Outcome 路径列表
        """
        if self._outcome_repo is None:
            logger.debug("no outcome repository configured, returning empty paths")
            return []

        try:
            outcomes = self._outcome_repo.list(
                event_type=event_type,
                limit=limit,
            )

            if subject_id:
                outcomes = [o for o in outcomes if o.subject_id == subject_id]

            # 按 subject_id 分组
            by_subject: Dict[str, List[Any]] = {}
            for o in outcomes:
                by_subject.setdefault(o.subject_id, []).append(o)

            result = []
            for sid, os in by_subject.items():
                evidence_count = len(os)
                result.append(
                    {
                        "subject_id": sid,
                        "outcomes": [
                            {
                                "outcome_id": o.outcome_id,
                                "event_id": o.event_id,
                                "timing_action": o.timing_action,
                                "outcome_return": o.outcome_return,
                                "outcome_excess_return": o.outcome_excess_return,
                                "lesson": o.lesson,
                            }
                            for o in os[:10]
                        ],
                        "evidence_count": evidence_count,
                        "evidence_strength": _compute_evidence_strength(evidence_count),
                    }
                )

            return result[:limit]
        except Exception as exc:
            logger.warning("failed to get outcome paths, returning empty", error=str(exc))
            return []

    # ── 图谱丰富 ──────────────────────────────────────────

    def enrich_graph(
        self,
        graph_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """用真实数据丰富图谱视图。

        Args:
            graph_type: 图谱类型 (industry_chain, propagation, outcome)
            params: 参数字典 (industry, event_id, subject_id, event_type 等)

        Returns:
            丰富后的图谱数据，包含 nodes, edges, propagation_paths, outcome_paths
        """
        params = params or {}
        event_type = params.get("event_type")
        subject_id = params.get("subject_id")

        nodes = self.get_real_entities(event_type=event_type)
        propagation_paths = self.get_propagation_paths(event_type=event_type)
        outcome_paths = self.get_outcome_paths(
            subject_id=subject_id,
            event_type=event_type,
        )

        # 构建边：从传播路径中提取
        edges = []
        for path_data in propagation_paths:
            path = path_data.get("path", [])
            if isinstance(path, list) and len(path) > 1:
                for i in range(len(path) - 1):
                    edges.append(
                        {
                            "source": path[i],
                            "target": path[i + 1],
                            "evidence_count": path_data.get("evidence_count", 0),
                            "evidence_strength": path_data.get("evidence_strength", "none"),
                            "real_edge": True,
                        }
                    )

        # 标记节点中无真实数据的为 placeholder
        if not nodes:
            nodes = [
                {"hint": "No real entity data available; showing placeholder", "real_entity": False}
            ]

        enriched = {
            "graph_type": graph_type,
            "nodes": nodes,
            "edges": edges,
            "propagation_paths": propagation_paths,
            "outcome_paths": outcome_paths,
            "data_source": "real"
            if (nodes and nodes[0].get("real_entity", False))
            else "placeholder",
        }

        logger.info(
            "graph enriched",
            graph_type=graph_type,
            nodes_count=len(nodes),
            edges_count=len(edges),
            data_source=enriched["data_source"],
        )

        return enriched
