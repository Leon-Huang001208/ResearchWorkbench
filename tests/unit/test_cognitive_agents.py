"""
认知 Agent 层测试

Agent 不能互相自由聊天；它们通过统一 schema 向黑板写入观点。
"""
import pytest
from pydantic import ValidationError

from cognitive_agents import AgentView, CognitiveBlackboard


def test_blackboard_stores_agent_views_with_unified_schema():
    """黑板应保存统一结构的 Agent 观点"""
    blackboard = CognitiveBlackboard()
    view = AgentView(
        view_id="view_fundamental_001",
        agent_name="fundamental_agent",
        agent_role="fundamental",
        target_id="300308.SZ",
        event_id="event_ai_inference",
        view="bullish",
        thesis="800G需求超预期，盈利弹性提升",
        reasoning=["订单能见度提高", "产能利用率改善"],
        evidence_refs=["assertion_001"],
        confidence=0.72,
    )

    blackboard.add_view(view)

    assert blackboard.list_views(target_id="300308.SZ") == [view]
    assert blackboard.list_views(event_id="event_ai_inference") == [view]


def test_blackboard_detects_bull_bear_conflicts_for_same_target_and_event():
    """黑板应识别同一标的同一事件下的多空冲突"""
    blackboard = CognitiveBlackboard()
    blackboard.add_view(
        AgentView(
            view_id="view_bull_001",
            agent_name="bull_agent",
            agent_role="bull",
            target_id="300308.SZ",
            event_id="event_ai_inference",
            view="bullish",
            thesis="推理需求提升带来订单上修",
            confidence=0.75,
        )
    )
    blackboard.add_view(
        AgentView(
            view_id="view_bear_001",
            agent_name="flow_agent",
            agent_role="sentiment",
            target_id="300308.SZ",
            event_id="event_ai_inference",
            view="bearish",
            thesis="机构仓位过高，短期交易拥挤",
            confidence=0.64,
        )
    )

    conflicts = blackboard.find_conflicts()

    assert len(conflicts) == 1
    assert conflicts[0].target_id == "300308.SZ"
    assert conflicts[0].event_id == "event_ai_inference"
    assert set(conflicts[0].view_ids) == {"view_bull_001", "view_bear_001"}


def test_low_confidence_views_do_not_create_conflicts():
    """低置信度观点不应制造噪音冲突"""
    blackboard = CognitiveBlackboard(conflict_confidence_threshold=0.6)
    blackboard.add_view(
        AgentView(
            view_id="view_bull_001",
            agent_name="bull_agent",
            agent_role="bull",
            target_id="300308.SZ",
            view="bullish",
            thesis="存在订单上修可能",
            confidence=0.75,
        )
    )
    blackboard.add_view(
        AgentView(
            view_id="view_bear_001",
            agent_name="bear_agent",
            agent_role="bear",
            target_id="300308.SZ",
            view="bearish",
            thesis="交易热度偏高，但证据不足",
            confidence=0.41,
        )
    )

    assert blackboard.find_conflicts() == []


def test_agent_view_rejects_unknown_roles():
    """Agent 角色必须来自统一 ontology"""
    with pytest.raises(ValidationError):
        AgentView(
            view_id="view_bad_001",
            agent_name="random_chat_agent",
            agent_role="chatbot",
            target_id="300308.SZ",
            view="bullish",
            thesis="随便聊聊",
            confidence=0.7,
        )
