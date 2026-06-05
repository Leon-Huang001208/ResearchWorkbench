"""Agent 编排器。"""
import asyncio
from typing import List, Tuple

from cognitive_agents.agents.base import AgentContext
from cognitive_agents.agents.factory import AgentFactory
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentRole, AgentView, BlackboardConflict
from core.observability import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """负责按序执行 Agent Swarm 的编排器。

    阶段间串行（信息→认知→对抗→验证），阶段内 Agent 并行执行。
    """

    def __init__(self, agent_factory: AgentFactory):
        self.agent_factory = agent_factory
        # 定义执行顺序：信息类 → 认知类 → 对抗类 → 验证类
        self.execution_order: List[List[AgentRole]] = [
            ["news", "social_media", "financial_report", "industry_data"],
            ["fundamental", "technical", "macro", "industry_chain", "policy", "sentiment"],
            ["bull", "bear", "skeptic"],
            ["alpha_validation", "regime", "portfolio"],
        ]

    async def run_swarm(
        self,
        context: AgentContext,
        blackboard: CognitiveBlackboard,
        agent_roles: List[AgentRole] | None = None,
    ) -> Tuple[List[AgentView], List[BlackboardConflict]]:
        """执行 Agent Swarm，阶段间串行，阶段内并行。"""
        all_views: List[AgentView] = []

        for stage in self.execution_order:
            # 过滤角色
            roles_in_stage = [r for r in stage if agent_roles is None or r in agent_roles]
            if not roles_in_stage:
                continue

            # 阶段内 Agent 并行执行
            async def _run_agent(role: AgentRole) -> AgentView:
                agent = self.agent_factory.create(role)
                updated_context = AgentContext(
                    target_id=context.target_id,
                    event_id=context.event_id,
                    question=context.question,
                    evidence=context.evidence,
                    evidence_bundle=context.evidence_bundle,
                    market_data=context.market_data,
                    prior_views=blackboard.list_views(
                        target_id=context.target_id, event_id=context.event_id
                    ),
                )
                return await agent.run(updated_context, blackboard)

            stage_views = await asyncio.gather(*[_run_agent(role) for role in roles_in_stage])
            all_views.extend(stage_views)

        conflicts = blackboard.find_conflicts()
        return all_views, conflicts
