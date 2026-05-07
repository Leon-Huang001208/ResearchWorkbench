"""认知 Agent 基类与共享数据结构。"""
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from core.observability import get_logger
from core.interfaces import ModelGateway
from cognitive_agents.contracts import AgentView, AgentRole
from cognitive_agents.blackboard import CognitiveBlackboard

logger = get_logger(__name__)


class AgentContext(BaseModel):
    """Agent 执行上下文。"""
    target_id: str           # 标的ID
    event_id: str | None = None  # 关联事件ID
    question: str            # 分析问题
    evidence: list[dict] = Field(default_factory=list)  # 证据（断言、事件等）
    market_data: dict = Field(default_factory=dict)      # 市场数据快照
    prior_views: list[AgentView] = Field(default_factory=list)  # 黑板已有观点


class BaseCognitiveAgent(ABC):
    """认知 Agent 抽象基类。"""
    def __init__(self, model_gateway: ModelGateway, agent_name: str, agent_role: AgentRole):
        self.model_gateway = model_gateway
        self.agent_name = agent_name
        self.agent_role = agent_role

    @abstractmethod
    async def analyze(self, context: AgentContext) -> AgentView:
        """核心分析逻辑，由子类实现。"""
        pass

    async def run(self, context: AgentContext, blackboard: CognitiveBlackboard) -> AgentView:
        """执行分析并写入黑板。"""
        logger.info(
            "running cognitive agent",
            agent_name=self.agent_name,
            agent_role=self.agent_role,
            target_id=context.target_id,
            event_id=context.event_id,
        )
        view = await self.analyze(context)
        blackboard.add_view(view)
        return view
