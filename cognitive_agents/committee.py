"""Committee synthesis for blackboard Agent views."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from cognitive_agents.contracts import AgentView, CommitteeSynthesis, ViewDirection


class CommitteeSynthesisService:
    """Create a deterministic committee summary from AgentView objects."""

    def synthesize(
        self,
        views: Iterable[AgentView],
        target_id: str,
        event_id: str | None = None,
        workflow_id: str | None = None,
    ) -> CommitteeSynthesis:
        view_list = list(views)
        scoped_views = [
            view
            for view in view_list
            if view.target_id == target_id
            and (event_id is None or view.event_id == event_id)
            and (workflow_id is None or view.workflow_id in {workflow_id, None})
        ]
        if not scoped_views:
            return CommitteeSynthesis(
                synthesis_id=self._synthesis_id(target_id, event_id, workflow_id),
                workflow_id=workflow_id,
                target_id=target_id,
                event_id=event_id,
                final_view="unknown",
                confidence=0.0,
                thesis="缺少 Agent 观点，无法形成委员会结论",
                rationale=["No scoped AgentView records were available."],
                metadata={"view_count": 0},
            )

        direction_scores = self._direction_scores(scoped_views)
        final_view = self._final_view(direction_scores)
        confidence = self._confidence(direction_scores)
        lead_view = max(scoped_views, key=lambda view: view.confidence)
        supporting = [
            view.view_id
            for view in scoped_views
            if view.view == final_view or (final_view == "mixed" and view.view in {"bullish", "bearish"})
        ]
        dissenting = [
            view.view_id
            for view in scoped_views
            if view.view not in {final_view, "unknown"}
            and not (final_view == "mixed" and view.view in {"bullish", "bearish"})
        ]

        return CommitteeSynthesis(
            synthesis_id=self._synthesis_id(target_id, event_id, workflow_id),
            workflow_id=workflow_id,
            target_id=target_id,
            event_id=event_id,
            final_view=final_view,
            confidence=confidence,
            thesis=lead_view.thesis,
            rationale=self._rationale(scoped_views, direction_scores, final_view),
            supporting_view_ids=supporting,
            dissenting_view_ids=dissenting,
            assumptions=self._merge_lists(view.assumptions for view in scoped_views),
            risks=self._merge_lists(view.risks for view in scoped_views),
            invalidation_triggers=self._merge_lists(
                view.invalidation_triggers for view in scoped_views
            ),
            recommended_next_checks=self._merge_lists(
                view.recommended_next_checks for view in scoped_views
            ),
            metadata={
                "view_count": len(scoped_views),
                "direction_scores": dict(direction_scores),
                "lead_view_id": lead_view.view_id,
            },
        )

    @staticmethod
    def _direction_scores(views: list[AgentView]) -> dict[ViewDirection, float]:
        scores: dict[ViewDirection, float] = defaultdict(float)
        for view in views:
            scores[view.view] += view.confidence
        return dict(scores)

    @staticmethod
    def _final_view(scores: dict[ViewDirection, float]) -> ViewDirection:
        bullish = scores.get("bullish", 0.0)
        bearish = scores.get("bearish", 0.0)
        if bullish > 0 and bearish > 0:
            total = bullish + bearish
            if total > 0 and abs(bullish - bearish) / total < 0.25:
                return "mixed"

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked:
            return "unknown"
        return ranked[0][0]

    @staticmethod
    def _confidence(scores: dict[ViewDirection, float]) -> float:
        total = sum(scores.values())
        if total <= 0:
            return 0.0
        top = max(scores.values())
        return max(0.0, min(1.0, top / total))

    @staticmethod
    def _rationale(
        views: list[AgentView],
        scores: dict[ViewDirection, float],
        final_view: ViewDirection,
    ) -> list[str]:
        rationale = [
            f"Committee final_view={final_view} from {len(views)} Agent views.",
            f"Direction scores: {dict(scores)}.",
        ]
        high_confidence = [view for view in views if view.confidence >= 0.7]
        if high_confidence:
            rationale.append(
                "High-confidence views: "
                + ", ".join(f"{view.agent_role}:{view.view}" for view in high_confidence)
            )
        return rationale

    @staticmethod
    def _merge_lists(groups: Iterable[list[str]], limit: int = 12) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                if item in seen:
                    continue
                seen.add(item)
                merged.append(item)
                if len(merged) >= limit:
                    return merged
        return merged

    @staticmethod
    def _synthesis_id(target_id: str, event_id: str | None, workflow_id: str | None) -> str:
        target_part = target_id.replace(".", "_")
        event_part = (event_id or "no_event").replace(".", "_")
        workflow_part = (workflow_id or "no_workflow").replace(".", "_")
        return f"synthesis_{workflow_part}_{target_part}_{event_part}"
