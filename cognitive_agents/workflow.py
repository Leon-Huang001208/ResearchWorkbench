"""Workflow runner for staged Agent execution."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Protocol

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
from core.contracts.agent_types import EvidenceItem
from core.observability import get_logger

if TYPE_CHECKING:
    from services.web_search_service import WebSearchService

logger = get_logger(__name__)

# 信息收集阶段 agent 角色——这些角色在 evidence 不足时应触发联网搜索
_INFORMATION_ROLES: set[AgentRole] = {
    "news",
    "social_media",
    "financial_report",
    "industry_data",
}

# evidence 条数低于此阈值时触发联网搜索补充
_MIN_EVIDENCE_THRESHOLD = 2


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
        web_search_service: WebSearchService | None = None,
    ):
        self.agent_factory = agent_factory
        self.synthesis_service = synthesis_service or CommitteeSynthesisService()
        self._web_search: WebSearchService | None = web_search_service

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
        # ── 联网搜索补充 evidence（信息收集阶段，evidence 不足时触发）──
        if (
            self._web_search
            and role in _INFORMATION_ROLES
            and len(stage_context.evidence) < _MIN_EVIDENCE_THRESHOLD
        ):
            await self._enrich_evidence_from_web(stage_context)
        # ── end ──
        view = await agent.analyze(stage_context)
        if view.target_id != workflow.target_id or view.event_id != workflow.event_id:
            view = view.model_copy(
                update={"target_id": workflow.target_id, "event_id": workflow.event_id}
            )
        if view.workflow_id != workflow.workflow_id:
            view = view.model_copy(update={"workflow_id": workflow.workflow_id})
        blackboard.add_view(view)
        return view

    async def _enrich_evidence_from_web(self, context: AgentContext) -> None:
        """信息收集阶段 evidence 不足时联网搜索补充.

        将搜索结果包装为 EvidenceItem（新格式）和 legacy dict（旧格式），
        同时注入 context.evidence_bundle 和 context.evidence，兼容四种信息 Agent
        （NewsAgent/FinancialReportAgent/IndustryDataAgent/SocialMediaAgent）的
        _build_prompt 直接引用 context.evidence 的风格。
        """
        if self._web_search is None:
            return

        try:
            results = self._web_search.search(context.question, max_results=3, fetch_content=False)
        except Exception as e:
            logger.warning(
                "web search enrichment failed",
                question=context.question[:80],
                error=str(e),
            )
            return

        if not results:
            logger.info(
                "web search returned no results for enrichment",
                question=context.question[:80],
            )
            return

        logger.info(
            "enriching agent evidence from web",
            role="information",
            question=context.question[:80],
            web_result_count=len(results),
        )

        new_evidence_items: list[EvidenceItem] = []
        new_legacy_items: list[dict] = []

        for item in results:
            evidence_id = f"web_search_{uuid.uuid4().hex[:12]}"
            summary = (
                (item.content or item.snippet or "")[:500] if item.content or item.snippet else ""
            )
            new_evidence_items.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    ref_id=item.url,
                    ref_type="external",
                    evidence_kind="media",
                    source_type="web_search",
                    source_name=item.source,
                    title=item.title,
                    summary=summary,
                    reliability=0.6,
                    relevance=0.7,
                    payload={"url": item.url, "source": item.source},
                )
            )
            # 旧格式：兼容 Information Agent 的 _build_prompt 直接引用 context.evidence
            new_legacy_items.append(
                {
                    "evidence_id": evidence_id,
                    "ref_id": item.url,
                    "ref_type": "external",
                    "kind": "media",
                    "source_type": "web_search",
                    "title": item.title,
                    "text": item.content or item.snippet or "",
                    "summary": summary,
                    "url": item.url,
                    "confidence": 0.6,
                }
            )

        # 注入新格式（EvidenceBundle）
        if context.evidence_bundle is not None:
            context.evidence_bundle.evidence_items.extend(new_evidence_items)
        else:
            from core.contracts.agent_types import EvidenceBundle as EB

            context.evidence_bundle = EB(
                target_id=context.target_id,
                event_id=context.event_id,
                question=context.question,
                evidence_items=new_evidence_items,
            )

        # 注入旧格式（legacy list[dict]）
        context.evidence.extend(new_legacy_items)
