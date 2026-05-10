"""CognitiveBlackboard 记忆应用测试"""
from cognitive_agents.blackboard import CognitiveBlackboard
from cognitive_agents.contracts import AgentView
from memory_learning.contracts import AgentMemory


def test_apply_agent_memory_reduces_confidence_when_contradictions_gt_supports():
    """测试当矛盾数 > 支持数时，降低观点置信度"""
    # Create blackboard
    blackboard = CognitiveBlackboard()
    # Add a view
    view = AgentView(
        view_id="test-view-001",
        agent_name="value_agent",
        agent_role="fundamental",
        target_id="600519.SH",
        view="bullish",
        thesis="Value stocks are undervalued",
        confidence=0.8,
        event_id="test-event-001",
        reasoning=["Test reasoning"],
    )
    blackboard.add_view(view)

    # Create agent memory with more contradictions than supports
    memory = AgentMemory(
        memory_id="test-memory-001",
        agent_name="value_agent",
        agent_role="fundamental",
        belief="Value stocks outperform",
        confidence=0.7,
        support_count=2,
        contradiction_count=5,
    )

    # Apply memory
    blackboard.apply_agent_memory([memory])

    # Check that the view's confidence was reduced
    updated_view = blackboard.list_views()[0]
    assert updated_view.confidence < 0.8
    assert abs(updated_view.confidence - 0.8 * 0.8) < 1e-9  # 20% reduction


def test_apply_agent_memory_does_nothing_when_no_memories():
    """测试当没有记忆时，不做任何操作"""
    blackboard = CognitiveBlackboard()
    view = AgentView(
        view_id="test-view-002",
        agent_name="value_agent",
        agent_role="fundamental",
        target_id="600519.SH",
        view="bullish",
        thesis="Value stocks are undervalued",
        confidence=0.8,
        event_id="test-event-002",
        reasoning=["Test reasoning"],
    )
    blackboard.add_view(view)

    blackboard.apply_agent_memory([])

    # Check that confidence is unchanged
    updated_view = blackboard.list_views()[0]
    assert updated_view.confidence == 0.8
