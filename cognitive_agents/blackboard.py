"""共享认知黑板。"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from core.observability import get_logger
from memory_learning.contracts import AgentMemory

from .contracts import AgentView, BlackboardConflict

logger = get_logger(__name__)


class CognitiveBlackboard:
    """Agent Swarm 的共享记忆入口。

    Agent 不直接互聊；它们只向黑板写入 AgentView。下游的 Skeptic、
    Alpha Validation 和 Portfolio 模块消费这些结构化观点。
    """

    def __init__(self, conflict_confidence_threshold: float = 0.6):
        if not 0.0 <= conflict_confidence_threshold <= 1.0:
            raise ValueError("conflict_confidence_threshold must be between 0 and 1")
        self.conflict_confidence_threshold = conflict_confidence_threshold
        self._views: dict[str, AgentView] = {}

    def add_view(self, view: AgentView) -> AgentView:
        """写入或覆盖一个 Agent 观点。"""
        self._views[view.view_id] = view
        logger.info(
            "agent view added to cognitive blackboard",
            view_id=view.view_id,
            agent_role=view.agent_role,
            target_id=view.target_id,
            event_id=view.event_id,
            confidence=view.confidence,
        )
        return view

    def list_views(
        self,
        target_id: str | None = None,
        event_id: str | None = None,
        agent_role: str | None = None,
    ) -> list[AgentView]:
        """按标的、事件或 Agent 角色查询观点。"""
        views = list(self._views.values())
        if target_id is not None:
            views = [view for view in views if view.target_id == target_id]
        if event_id is not None:
            views = [view for view in views if view.event_id == event_id]
        if agent_role is not None:
            views = [view for view in views if view.agent_role == agent_role]
        return views

    def find_conflicts(self) -> list[BlackboardConflict]:
        """识别同一标的/事件上的高置信度多空冲突。"""
        conflicts: list[BlackboardConflict] = []
        for key, views in self._group_by_target_event(self._views.values()).items():
            eligible = [
                view for view in views if view.confidence >= self.conflict_confidence_threshold
            ]
            bullish = [view for view in eligible if view.view == "bullish"]
            bearish = [view for view in eligible if view.view == "bearish"]
            if not bullish or not bearish:
                continue

            target_id, event_id = key
            conflict_views = bullish + bearish
            avg_confidence = sum(view.confidence for view in conflict_views) / len(conflict_views)
            conflict = BlackboardConflict(
                conflict_id=self._conflict_id(target_id, event_id),
                target_id=target_id,
                event_id=event_id,
                view_ids=[view.view_id for view in conflict_views],
                summary=(
                    f"{target_id} has bullish and bearish views"
                    + (f" on {event_id}" if event_id else "")
                ),
                severity=self._severity(avg_confidence),
                confidence=avg_confidence,
            )
            conflicts.append(conflict)
            logger.info(
                "cognitive blackboard conflict detected",
                conflict_id=conflict.conflict_id,
                target_id=target_id,
                event_id=event_id,
                confidence=avg_confidence,
            )
        return conflicts

    @staticmethod
    def _group_by_target_event(
        views: Iterable[AgentView],
    ) -> dict[tuple[str, str | None], list[AgentView]]:
        grouped: dict[tuple[str, str | None], list[AgentView]] = defaultdict(list)
        for view in views:
            grouped[(view.target_id, view.event_id)].append(view)
        return dict(grouped)

    @staticmethod
    def _conflict_id(target_id: str, event_id: str | None) -> str:
        event_part = event_id or "no_event"
        normalized_target = target_id.replace(".", "_")
        normalized_event = event_part.replace(".", "_")
        return f"conflict_{normalized_target}_{normalized_event}"

    def apply_agent_memory(self, agent_memories: list[AgentMemory]) -> None:
        """将 Agent 长期记忆应用到黑板，调整 confidence 权重。"""
        if not self._views:
            logger.debug("No views on blackboard, skipping agent memory application")
            return

        # Build a memory index by agent name + role
        memory_index: dict[tuple[str, str], AgentMemory] = {}
        for memory in agent_memories:
            key = (memory.agent_name, memory.agent_role)
            memory_index[key] = memory

        # Iterate over views and adjust confidence
        for view_id, view in self._views.items():
            key = (view.agent_name, view.agent_role)
            if key not in memory_index:
                continue

            memory = memory_index[key]
            # If contradiction count > support count, reduce confidence
            if memory.contradiction_count > memory.support_count:
                original_confidence = view.confidence
                # Reduce confidence by 20% (capped at 0.1)
                new_confidence = max(0.1, original_confidence * 0.8)
                # Create updated view
                updated_view = AgentView(
                    view_id=view.view_id,
                    agent_name=view.agent_name,
                    agent_role=view.agent_role,
                    target_id=view.target_id,
                    event_id=view.event_id,
                    view=view.view,
                    thesis=view.thesis,
                    confidence=new_confidence,
                    reasoning=view.reasoning
                    + [
                        f"Adjusted confidence from {original_confidence:.2f} to {new_confidence:.2f} based on agent memory (contradictions > supports)"
                    ],
                    evidence_refs=view.evidence_refs,
                    metadata=view.metadata,
                )
                self._views[view_id] = updated_view
                logger.info(
                    "Adjusted view confidence based on agent memory",
                    view_id=view_id,
                    agent_name=view.agent_name,
                    agent_role=view.agent_role,
                    original_confidence=original_confidence,
                    new_confidence=new_confidence,
                )

    @staticmethod
    def _severity(confidence: float) -> str:
        if confidence >= 0.75:
            return "high"
        if confidence >= 0.65:
            return "medium"
        return "low"
