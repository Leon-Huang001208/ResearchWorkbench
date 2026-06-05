"""Agent workflow and committee synthesis tests."""
from __future__ import annotations

import pytest

from cognitive_agents import (
    AgentView,
    AgentWorkflow,
    AgentWorkflowRunner,
    AgentWorkflowStage,
    CognitiveBlackboard,
    CommitteeSynthesisService,
)
from cognitive_agents.agents.base import AgentContext


class _FakeAgent:
    def __init__(self, role: str, view: str, confidence: float):
        self.agent_role = role
        self.agent_name = f"{role}_agent"
        self._view = view
        self._confidence = confidence

    async def analyze(self, context: AgentContext) -> AgentView:
        return AgentView(
            view_id=f"view_{self.agent_role}",
            agent_name=self.agent_name,
            agent_role=self.agent_role,
            target_id=context.target_id,
            event_id=context.event_id,
            view=self._view,
            thesis=f"{self.agent_role} thesis",
            confidence=self._confidence,
            reasoning=[f"{self.agent_role} reasoning"],
            assumptions=[f"{self.agent_role} assumption"],
            risks=[f"{self.agent_role} risk"],
            invalidation_triggers=[f"{self.agent_role} invalidation"],
            recommended_next_checks=[f"{self.agent_role} next check"],
        )


class _FakeFactory:
    def __init__(self):
        self._views = {
            "macro": ("bullish", 0.8),
            "fundamental": ("bullish", 0.7),
            "technical": ("bearish", 0.4),
        }

    def create(self, role: str) -> _FakeAgent:
        view, confidence = self._views[role]
        return _FakeAgent(role, view, confidence)


def test_committee_synthesis_detects_balanced_bull_bear_as_mixed():
    service = CommitteeSynthesisService()
    views = [
        AgentView(
            view_id="view_bull",
            agent_name="bull_agent",
            agent_role="bull",
            target_id="300308.SZ",
            view="bullish",
            thesis="订单上修",
            confidence=0.8,
            assumptions=["需求持续"],
            risks=["估值偏高"],
            invalidation_triggers=["订单取消"],
            recommended_next_checks=["检查公告"],
        ),
        AgentView(
            view_id="view_bear",
            agent_name="bear_agent",
            agent_role="bear",
            target_id="300308.SZ",
            view="bearish",
            thesis="交易拥挤",
            confidence=0.75,
            risks=["拥挤回撤"],
        ),
    ]

    synthesis = service.synthesize(
        views,
        target_id="300308.SZ",
        event_id=None,
        workflow_id="workflow_research_committee_v1",
    )

    assert synthesis.final_view == "mixed"
    assert synthesis.confidence == pytest.approx(0.8 / 1.55)
    assert set(synthesis.supporting_view_ids) == {"view_bull", "view_bear"}
    assert "需求持续" in synthesis.assumptions
    assert "拥挤回撤" in synthesis.risks


@pytest.mark.asyncio
async def test_agent_workflow_runner_sets_workflow_id_and_synthesizes():
    workflow = AgentWorkflow(
        workflow_id="workflow_unit_test",
        target_id="300308.SZ",
        event_id="event_ai",
        question="AI算力事件是否值得跟踪？",
        stages=[
            AgentWorkflowStage(
                stage_id="research",
                label="多维分析",
                agent_roles=["macro", "fundamental", "technical"],
                synthesis_after_stage=True,
            )
        ],
    )
    blackboard = CognitiveBlackboard()
    runner = AgentWorkflowRunner(agent_factory=_FakeFactory())
    context = AgentContext(
        target_id="300308.SZ",
        event_id="event_ai",
        question="AI算力事件是否值得跟踪？",
        evidence=[{"ref_id": "assertion_001", "summary": "订单增长"}],
    )

    result = await runner.run(workflow, context, blackboard)

    assert result.workflow_id == "workflow_unit_test"
    assert len(result.views) == 3
    assert all(view.workflow_id == "workflow_unit_test" for view in result.views)
    assert len(blackboard.list_views(target_id="300308.SZ", event_id="event_ai")) == 3
    assert result.synthesis is not None
    assert result.synthesis.final_view == "bullish"
    assert result.synthesis.metadata["view_count"] == 3
