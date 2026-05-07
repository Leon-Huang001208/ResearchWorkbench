"""认知 Agent 实现测试。"""
import pytest
from unittest.mock import Mock, AsyncMock
from pydantic import BaseModel

from core.interfaces import ModelGateway
from cognitive_agents.agents.base import BaseCognitiveAgent, AgentContext
from cognitive_agents.agents.factory import AgentFactory
from cognitive_agents.agents.orchestrator import AgentOrchestrator
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentView, AgentRole, ViewDirection


class MockModelGateway(ModelGateway):
    """模拟 ModelGateway 用于测试。"""
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ):
        pass

    def embed(self, text: str, model: str | None = None, **kwargs):
        pass

    def structured_output(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.1,
        **kwargs,
    ) -> BaseModel:
        """返回预设的结构化输出。"""
        return AgentView(
            view_id="test-view-id",
            agent_name="test-agent",
            agent_role="news",
            target_id="test-target",
            view="neutral",
            thesis="Test thesis",
            confidence=0.5,
            reasoning=["Test reasoning"],
        )


@pytest.fixture
def model_gateway() -> MockModelGateway:
    """Fixture 提供模拟的 ModelGateway。"""
    return MockModelGateway()


@pytest.fixture
def agent_factory(model_gateway: MockModelGateway) -> AgentFactory:
    """Fixture 提供 AgentFactory。"""
    return AgentFactory(model_gateway)


@pytest.fixture
def blackboard() -> CognitiveBlackboard:
    """Fixture 提供 CognitiveBlackboard。"""
    return CognitiveBlackboard()


@pytest.fixture
def context() -> AgentContext:
    """Fixture 提供 AgentContext。"""
    return AgentContext(
        target_id="AAPL",
        question="Test question",
        evidence=[{"type": "news", "content": "Test news"}],
        market_data={"price": 100},
    )


def test_agent_factory_creation(agent_factory: AgentFactory):
    """测试 AgentFactory 能正确创建各种 Agent。"""
    roles = [
        "news", "social_media", "financial_report", "industry_data",
        "fundamental", "technical", "macro", "industry_chain", "policy", "sentiment",
        "bull", "bear", "skeptic",
        "alpha_validation", "regime", "portfolio",
    ]
    for role in roles:
        agent = agent_factory.create(role)
        assert isinstance(agent, BaseCognitiveAgent)
        assert agent.agent_role == role


@pytest.mark.asyncio
async def test_agent_run(agent_factory: AgentFactory, blackboard: CognitiveBlackboard, context: AgentContext):
    """测试单个 Agent 的 run 方法。"""
    agent = agent_factory.create("news")
    # 因为 BaseCognitiveAgent.analyze 是 abstractmethod，我们需要手动 mock analyze
    mock_view = AgentView(
        view_id="test-view-id",
        agent_name="news_agent",
        agent_role="news",
        target_id=context.target_id,
        view="neutral",
        thesis="Test thesis",
        confidence=0.5,
        reasoning=["Test reasoning"],
    )
    agent.analyze = AsyncMock(return_value=mock_view)
    view = await agent.run(context, blackboard)
    assert view == mock_view
    assert len(blackboard.list_views(target_id=context.target_id)) == 1


@pytest.mark.asyncio
async def test_orchestrator_run_swarm(agent_factory: AgentFactory, blackboard: CognitiveBlackboard, context: AgentContext):
    """测试 AgentOrchestrator 的 run_swarm 方法。"""
    orchestrator = AgentOrchestrator(agent_factory)
    # 先 mock all agents' analyze methods
    original_create = agent_factory.create

    def mock_create(role: AgentRole):
        agent = original_create(role)
        mock_view = AgentView(
            view_id=f"test-{role}-view-id",
            agent_name=agent.agent_name,
            agent_role=agent.agent_role,
            target_id=context.target_id,
            view="neutral",
            thesis=f"Test thesis for {role}",
            confidence=0.5,
            reasoning=[f"Test reasoning for {role}"],
        )
        agent.analyze = AsyncMock(return_value=mock_view)
        return agent

    agent_factory.create = mock_create
    views, conflicts = await orchestrator.run_swarm(context, blackboard)
    assert len(views) > 0
    assert len(blackboard.list_views(target_id=context.target_id)) == len(views)
