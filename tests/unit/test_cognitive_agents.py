"""
认知 Agent 层测试

Agent 不能互相自由聊天；它们通过统一 schema 向黑板写入观点。
"""
import pytest
from pydantic import ValidationError

from cognitive_agents import AgentView, CognitiveBlackboard, EvidenceBundle
from cognitive_agents.agents.base import AgentContext
from cognitive_agents.agents.cognitive.fundamental_agent import FundamentalAgent
from memory_learning.contracts import AgentMemory


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


def test_agent_context_builds_evidence_bundle_from_legacy_evidence():
    """旧版 loose evidence 输入应自动转换为统一证据包"""
    context = AgentContext(
        target_id="300308.SZ",
        event_id="event_ai_inference",
        question="AI算力需求是否支持光模块机会？",
        evidence=[
            {
                "assertion_id": "assertion_001",
                "source_type": "zhiqiu_reports",
                "kind": "research",
                "summary": "800G光模块需求超预期",
                "confidence": 0.82,
            },
            {
                "doc_id": "doc_cninfo_001",
                "source_type": "cninfo",
                "kind": "unexpected_kind",
                "content": "公司披露订单增长",
                "confidence": 5,
            },
        ],
        market_data={"pe_ttm": 42.0},
    )

    bundle = context.get_evidence_bundle()

    assert isinstance(bundle, EvidenceBundle)
    assert bundle.target_id == "300308.SZ"
    assert bundle.event_id == "event_ai_inference"
    assert bundle.market_snapshot == {"pe_ttm": 42.0}
    assert bundle.evidence_items[0].ref_id == "assertion_001"
    assert bundle.evidence_items[0].evidence_kind == "research"
    assert bundle.evidence_items[1].evidence_kind == "other"
    assert bundle.evidence_items[1].reliability == 1.0


def test_fundamental_agent_prompt_includes_role_sop_and_evidence_bundle():
    """基本面 Agent prompt 应包含 SOP 和统一证据包"""
    agent = FundamentalAgent(model_gateway=None)
    context = AgentContext(
        target_id="300308.SZ",
        event_id="event_ai_inference",
        question="订单是否能转化为利润？",
        evidence=[
            {
                "evidence_id": "ev_001",
                "ref_id": "assertion_001",
                "source_type": "cninfo",
                "evidence_kind": "official",
                "summary": "公司公告披露订单增长",
                "confidence": 0.9,
            }
        ],
    )

    prompt = agent._build_prompt(context)

    assert "判断事件或主题是否能转化为收入、利润、现金流、估值或预期修正" in prompt
    assert "区分官方事实、研究观点和未经验证的市场传闻" in prompt
    assert "assertion_001" in prompt
    assert "invalidation_triggers" in prompt


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


def test_blackboard_memory_adjustment_preserves_agent_view_extensions():
    """记忆降权不应丢失 SOP 输出字段"""
    blackboard = CognitiveBlackboard()
    blackboard.add_view(
        AgentView(
            view_id="view_fundamental_001",
            agent_name="fundamental_agent",
            agent_role="fundamental",
            target_id="300308.SZ",
            view="bullish",
            thesis="订单增长带来盈利弹性",
            confidence=0.8,
            assumptions=["订单能确认收入"],
            risks=["毛利率下滑"],
            invalidation_triggers=["公告订单取消"],
            recommended_next_checks=["检查下一期财报合同负债"],
            evidence_refs=["assertion_001"],
            tool_refs=["wind_adapter"],
            memory_refs=["memory_001"],
            workflow_id="workflow_001",
            evaluation={"fundamental_quality": 0.72},
        )
    )

    blackboard.apply_agent_memory(
        [
            AgentMemory(
                memory_id="memory_001",
                agent_name="fundamental_agent",
                agent_role="fundamental",
                belief="该 Agent 近期高估订单兑现速度",
                confidence=0.7,
                support_count=1,
                contradiction_count=3,
            )
        ]
    )

    [view] = blackboard.list_views(target_id="300308.SZ")
    assert view.confidence == pytest.approx(0.64)
    assert view.assumptions == ["订单能确认收入"]
    assert view.risks == ["毛利率下滑"]
    assert view.invalidation_triggers == ["公告订单取消"]
    assert view.recommended_next_checks == ["检查下一期财报合同负债"]
    assert view.tool_refs == ["wind_adapter"]
    assert view.workflow_id == "workflow_001"
    assert view.evaluation == {"fundamental_quality": 0.72}


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
