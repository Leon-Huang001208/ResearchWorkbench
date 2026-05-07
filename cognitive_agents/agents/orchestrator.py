"""Agent 编排器。"""
from typing import List, Tuple

from core.observability import get_logger
from cognitive_agents.agents.base import AgentContext
from cognitive_agents.contracts import AgentView, AgentRole, BlackboardConflict
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.agents.factory import AgentFactory

logger = get_logger(__name__)


class AgentOrchestrator:
    """负责按序执行 Agent Swarm 的编排器。"""
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
        """执行 Agent Swarm。"""
        all_views: List[AgentView] = []
        for stage in self.execution_order:
            for role in stage:
                if agent_roles and role not in agent_roles:
                    continue
                agent = self.agent_factory.create(role)
                # 更新 context 的 prior_views
                updated_context = AgentContext(
                    target_id=context.target_id,
                    event_id=context.event_id,
                    question=context.question,
                    evidence=context.evidence,
                    market_data=context.market_data,
                    prior_views=blackboard.list_views(target_id=context.target_id, event_id=context.event_id),
                )
                view = await agent.run(updated_context, blackboard)
                all_views.append(view)
        conflicts = blackboard.find_conflicts()
        return all_views, conflicts
