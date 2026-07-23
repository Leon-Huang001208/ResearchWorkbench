"""
认知Agent集成测试 - 测试认知Agent完整集成流程
"""

import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from cognitive_agents.agents import AgentContext, AgentFactory, AgentOrchestrator
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentView, BlackboardConflict
from core.interfaces import ModelGateway


@pytest.fixture
def mock_model_gateway():
    """Create mock model gateway."""
    mock_gateway = Mock(spec=ModelGateway)
    mock_gateway.generate = AsyncMock(return_value="Mock model response")
    return mock_gateway


@pytest.fixture
def agent_factory(mock_model_gateway):
    """Create AgentFactory instance."""
    return AgentFactory(model_gateway=mock_model_gateway)


@pytest.fixture
def blackboard():
    """Create empty CognitiveBlackboard instance."""
    return CognitiveBlackboard()


@pytest.fixture
def test_context():
    """Create test agent context."""
    return AgentContext(
        target_id="asset:maotai:600519",
        event_id="evt-test-001",
        question="分析贵州茅台2026年一季度财报对股价的影响",
        evidence=[{"content": "贵州茅台2026Q1净利润同比增长28%"}],
        market_data={"current_price": 1700},
        prior_views=[],
    )


@pytest.mark.integration
class TestAgentFactoryIntegration:
    """测试AgentFactory创建所有Agent"""

    def test_factory_has_correct_number_of_agents(self, agent_factory):
        """验证工厂注册了正好16种Agent"""
        assert len(agent_factory.registry) == 16

    def test_can_create_all_16_agents(self, agent_factory):
        """测试可以创建所有16种Agent"""
        for role in agent_factory.registry.keys():
            agent = agent_factory.create(role)
            assert agent is not None
            assert agent.agent_role == role

    def test_create_unknown_agent_raises_error(self, agent_factory):
        """测试创建未知Agent抛出正确错误"""
        with pytest.raises(ValueError, match="Unknown agent role"):
            agent_factory.create("unknown_role")


@pytest.mark.integration
class TestAgentOrchestratorIntegration:
    """测试AgentOrchestrator编排流程"""

    def test_orchestrator_follows_correct_execution_order(self, agent_factory):
        """验证编排器遵循正确执行顺序：information → cognitive → adversarial → validation"""
        orchestrator = AgentOrchestrator(agent_factory)
        assert len(orchestrator.execution_order) == 4
        # Stage 0: information agents (4)
        assert len(orchestrator.execution_order[0]) == 4
        # Stage 1: cognitive agents (6)
        assert len(orchestrator.execution_order[1]) == 6
        # Stage 2: adversarial agents (3)
        assert len(orchestrator.execution_order[2]) == 3
        # Stage 3: validation agents (3)
        assert len(orchestrator.execution_order[3]) == 3
        # Total 4+6+3+3=16 = all agents
        assert sum(len(stage) for stage in orchestrator.execution_order) == 16

    @pytest.mark.asyncio
    async def test_orchestrator_runs_all_stages(
        self, agent_factory, blackboard, test_context, mock_model_gateway
    ):
        """测试编排器运行完整流程，结果写入黑板"""
        orchestrator = AgentOrchestrator(agent_factory)

        # Mock agent_factory.create to return agents with mocked analyze methods
        original_create = agent_factory.create

        def mock_create(role):
            agent = original_create(role)
            view = AgentView(
                view_id=f"view-{role}",
                agent_name=f"{role}_agent",
                agent_role=role,
                target_id=test_context.target_id,
                event_id=test_context.event_id,
                view="neutral",
                thesis=f"{role} analysis result",
                confidence=0.8,
                reasoning=[],
            )
            agent.analyze = AsyncMock(return_value=view)
            return agent

        agent_factory.create = mock_create

        # Execute full swarm
        views, conflicts = await orchestrator.run_swarm(test_context, blackboard)

        # Verify all 16 agents ran
        assert len(views) == 16
        # Verify all views are written to blackboard
        blackboard_views = blackboard.list_views(
            target_id=test_context.target_id, event_id=test_context.event_id
        )
        assert len(blackboard_views) == 16


@pytest.mark.integration
class TestCognitiveBlackboardIntegration:
    """测试CognitiveBlackboard写入和冲突检测"""

    def test_blackboard_writes_and_reads_correctly(self, blackboard, test_context):
        """测试Agent产出写入黑板正确"""
        # Add two views
        view1 = AgentView(
            view_id=f"view-{uuid.uuid4().hex[:8]}",
            agent_name="bull_agent",
            agent_role="bull",
            target_id=test_context.target_id,
            event_id=test_context.event_id,
            view="bullish",
            thesis="净利润增长推动股价上涨",
            confidence=0.8,
            reasoning=[],
        )
        view2 = AgentView(
            view_id=f"view-{uuid.uuid4().hex[:8]}",
            agent_name="bear_agent",
            agent_role="bear",
            target_id=test_context.target_id,
            event_id=test_context.event_id,
            view="bearish",
            thesis="估值已经过高，增长已经price in",
            confidence=0.7,
            reasoning=[],
        )

        blackboard.add_view(view1)
        blackboard.add_view(view2)

        # Verify reads
        stored_views = blackboard.list_views(
            target_id=test_context.target_id, event_id=test_context.event_id
        )
        assert len(stored_views) == 2
        assert any(v.view == "bullish" for v in stored_views)
        assert any(v.view == "bearish" for v in stored_views)

    def test_conflict_detection_finds_directional_conflicts(self, blackboard, test_context):
        """测试冲突检测能端到端检测出方向冲突"""
        # Add conflicting views (opposite directions)
        view_bull = AgentView(
            view_id=f"view-{uuid.uuid4().hex[:8]}",
            agent_name="bull_agent",
            agent_role="bull",
            target_id=test_context.target_id,
            event_id=test_context.event_id,
            view="bullish",
            thesis="净利润增长推动股价上涨",
            confidence=0.8,
            reasoning=[],
        )
        view_bear = AgentView(
            view_id=f"view-{uuid.uuid4().hex[:8]}",
            agent_name="bear_agent",
            agent_role="bear",
            target_id=test_context.target_id,
            event_id=test_context.event_id,
            view="bearish",
            thesis="估值已经过高，增长已经price in，股价会下跌",
            confidence=0.7,
            reasoning=[],
        )

        blackboard.add_view(view_bull)
        blackboard.add_view(view_bear)

        # Detect conflicts
        conflicts = blackboard.find_conflicts()

        # Should find at least one conflict
        assert len(conflicts) >= 1
        conflict = conflicts[0]
        assert isinstance(conflict, BlackboardConflict)
        assert "bullish" in conflict.summary and "bearish" in conflict.summary
        assert conflict.severity in ("medium", "high")

    def test_no_conflicts_when_all_views_align(self, blackboard, test_context, agent_factory):
        """测试当所有观点方向一致时不检测出冲突"""
        # Add all positive views (using valid agent roles)
        valid_roles = list(agent_factory.registry.keys())[:3]
        for i, role in enumerate(valid_roles):
            view = AgentView(
                view_id=f"view-{uuid.uuid4().hex[:8]}",
                agent_name=f"{role}_agent",
                agent_role=role,
                target_id=test_context.target_id,
                event_id=test_context.event_id,
                view="bullish",
                thesis=f"Positive view {i}",
                confidence=0.7 + (i * 0.05),
                reasoning=[],
            )
            blackboard.add_view(view)

        conflicts = blackboard.find_conflicts()
        # No directional conflicts
        assert len(conflicts) == 0
