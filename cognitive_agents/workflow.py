"""Workflow runner for staged Agent execution."""
from __future__ import annotations

import asyncio
from typing import Protocol

from cognitive_agents.agents.base import AgentContext
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.committee import CommitteeSynthesisService
from cognitive_agents.contracts import (
    AgentRole,
    AgentView,
    AgentWorkflow,
    AgentWorkflowResult,
    CommitteeSynthesis,
)
from core.observability import get_logger

logger = get_logger(__name__)


class WorkflowAgent(Protocol):
    """Minimal agent interface required by the workflow runner."""

    async def analyze(self, context: AgentContext) -> AgentView:
        """Analyze the stage context and return one Agent view."""


class AgentFactoryLike(Protocol):
    """Factory interface accepted by the workflow runner."""

    def create(self, role: AgentRole) -> WorkflowAgent:
        """Create an Agent for the requested role."""


class AgentWorkflowRunner:
    """Run an AgentWorkflow without replacing the existing AgentOrchestrator."""

    def __init__(
        self,
        agent_factory: AgentFactoryLike,
        synthesis_service: CommitteeSynthesisService | None = None,
    ):
        self.agent_factory = agent_factory
        self.synthesis_service = synthesis_service or CommitteeSynthesisService()

    async def run(
        self,
        workflow: AgentWorkflow,
        context: AgentContext,
        blackboard: CognitiveBlackboard,
    ) -> AgentWorkflowResult:
        """Run a workflow stage-by-stage and return views, conflicts, synthesis."""
        all_views: list[AgentView] = []
        synthesis: CommitteeSynthesis | None = None

        for stage in workflow.stages:
            roles = list(stage.agent_roles)
            if not roles:
                continue

            logger.info(
                "running agent workflow stage",
                workflow_id=workflow.workflow_id,
                stage_id=stage.stage_id,
                roles=roles,
                policy=stage.policy,
            )
            if stage.policy == "sequential":
                stage_views = []
                for role in roles:
                    stage_views.append(await self._run_agent(role, workflow, context, blackboard))
            else:
                stage_views = await asyncio.gather(
                    *[self._run_agent(role, workflow, context, blackboard) for role in roles]
                )

            all_views.extend(stage_views)
            if stage.synthesis_after_stage:
                synthesis = self.synthesis_service.synthesize(
                    blackboard.list_views(target_id=workflow.target_id, event_id=workflow.event_id),
                    target_id=workflow.target_id,
                    event_id=workflow.event_id,
                    workflow_id=workflow.workflow_id,
                )

        conflicts = blackboard.find_conflicts()
        if synthesis is None:
            synthesis = self.synthesis_service.synthesize(
                blackboard.list_views(target_id=workflow.target_id, event_id=workflow.event_id),
                target_id=workflow.target_id,
                event_id=workflow.event_id,
                workflow_id=workflow.workflow_id,
            )

        return AgentWorkflowResult(
            workflow_id=workflow.workflow_id,
            target_id=workflow.target_id,
            event_id=workflow.event_id,
            views=all_views,
            conflicts=conflicts,
            synthesis=synthesis,
        )

    async def _run_agent(
        self,
        role: AgentRole,
        workflow: AgentWorkflow,
        context: AgentContext,
        blackboard: CognitiveBlackboard,
    ) -> AgentView:
        agent = self.agent_factory.create(role)
        stage_context = AgentContext(
            target_id=workflow.target_id,
            event_id=workflow.event_id,
            question=workflow.question,
            evidence=context.evidence,
            evidence_bundle=context.evidence_bundle,
            market_data=context.market_data,
            prior_views=blackboard.list_views(
                target_id=workflow.target_id, event_id=workflow.event_id
            ),
        )
        view = await agent.analyze(stage_context)
        if view.target_id != workflow.target_id or view.event_id != workflow.event_id:
            view = view.model_copy(
                update={"target_id": workflow.target_id, "event_id": workflow.event_id}
            )
        if view.workflow_id != workflow.workflow_id:
            view = view.model_copy(update={"workflow_id": workflow.workflow_id})
        blackboard.add_view(view)
        return view
