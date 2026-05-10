"""Memory API 测试"""
import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from memory_learning.contracts import (
    MarketEpisode,
    StrategyMemory,
    AgentMemory,
    FailureMemory,
)


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def clean_journal():
    """Reset the journal singleton before each test"""
    # Clear the singleton instance
    from app.api.routes.memory import get_learning_journal
    if hasattr(get_learning_journal, "_instance"):
        delattr(get_learning_journal, "_instance")
    return get_learning_journal()


def test_record_episode(client, clean_journal):
    """测试记录事件记忆"""
    episode = MarketEpisode(
        episode_id="test-episode-001",
        event_id="test-event-001",
        event_type="earnings",
        market_regime="bullish",
        initial_reaction="up",
        outcome_horizon="20d",
        outcome_return=0.05,
        outcome_excess_return=0.03,
    )
    response = client.post(
        "/api/memory/episodes",
        json=episode.model_dump(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == "test-episode-001"
    assert data["event_type"] == "earnings"


def test_list_episodes(client, clean_journal):
    """测试查询事件记忆列表"""
    # First record an episode
    episode = MarketEpisode(
        episode_id="test-episode-002",
        event_id="test-event-002",
        event_type="policy",
        market_regime="risk_off",
        initial_reaction="down",
        outcome_horizon="5d",
        outcome_return=-0.02,
        outcome_excess_return=-0.01,
    )
    client.post("/api/memory/episodes", json=episode.model_dump())
    
    # Then list episodes
    response = client.get("/api/memory/episodes?event_type=policy")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["episode_id"] == "test-episode-002"


def test_get_episode(client, clean_journal):
    """测试获取单个事件记忆"""
    episode = MarketEpisode(
        episode_id="test-episode-003",
        event_id="test-event-003",
        event_type="merger",
        market_regime="bullish",
        initial_reaction="up",
        outcome_horizon="60d",
        outcome_return=0.1,
        outcome_excess_return=0.08,
    )
    client.post("/api/memory/episodes", json=episode.model_dump())
    
    response = client.get("/api/memory/episodes/test-episode-003")
    assert response.status_code == 200
    data = response.json()
    assert data["episode_id"] == "test-episode-003"


def test_record_strategy(client, clean_journal):
    """测试记录策略记忆"""
    strategy = StrategyMemory(
        strategy_id="test-strategy-001",
        signal_family="momentum",
        market_regime="bullish",
        sample_size=100,
        win_rate=0.6,
        average_excess_return=0.02,
        sharpe_ratio=1.2,
    )
    response = client.post(
        "/api/memory/strategies",
        json=strategy.model_dump(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["strategy_id"] == "test-strategy-001"


def test_list_strategies(client, clean_journal):
    """测试查询策略记忆列表"""
    strategy = StrategyMemory(
        strategy_id="test-strategy-002",
        signal_family="value",
        market_regime="bearish",
        sample_size=50,
        win_rate=0.55,
        average_excess_return=0.015,
        sharpe_ratio=1.0,
    )
    client.post("/api/memory/strategies", json=strategy.model_dump())
    
    response = client.get("/api/memory/strategies?signal_family=value")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["strategy_id"] == "test-strategy-002"


def test_record_agent_memory(client, clean_journal):
    """测试记录 Agent 记忆"""
    memory = AgentMemory(
        memory_id="test-agent-memory-001",
        agent_name="value_agent",
        agent_role="analyst",
        belief="Value stocks outperform in bear markets",
        confidence=0.7,
        support_count=5,
        contradiction_count=2,
    )
    response = client.post(
        "/api/memory/agent-memories",
        json=memory.model_dump(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["memory_id"] == "test-agent-memory-001"


def test_list_agent_memories(client, clean_journal):
    """测试查询 Agent 记忆列表"""
    memory = AgentMemory(
        memory_id="test-agent-memory-002",
        agent_name="momentum_agent",
        agent_role="trader",
        belief="Momentum works in bull markets",
        confidence=0.8,
        support_count=8,
        contradiction_count=1,
    )
    client.post("/api/memory/agent-memories", json=memory.model_dump())
    
    response = client.get("/api/memory/agent-memories?agent_name=momentum_agent")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["memory_id"] == "test-agent-memory-002"


def test_record_failure(client, clean_journal):
    """测试记录失败记忆"""
    failure = FailureMemory(
        failure_id="test-failure-001",
        source_id="test-signal-001",
        failure_type="timing_error",
        root_cause="Entered too early",
        corrective_action="Wait for confirmation",
    )
    response = client.post(
        "/api/memory/failures",
        json=failure.model_dump(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["failure_id"] == "test-failure-001"


def test_list_failures(client, clean_journal):
    """测试查询失败记忆列表"""
    failure = FailureMemory(
        failure_id="test-failure-002",
        source_id="test-signal-002",
        failure_type="crowding_error",
        root_cause="Too crowded",
        corrective_action="Avoid crowded trades",
    )
    client.post("/api/memory/failures", json=failure.model_dump())
    
    response = client.get("/api/memory/failures?failure_type=crowding_error")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["failure_id"] == "test-failure-002"


def test_summarize_event_type(client, clean_journal):
    """测试按事件类型汇总统计"""
    # Record two episodes
    episode1 = MarketEpisode(
        episode_id="test-episode-004",
        event_id="test-event-004",
        event_type="earnings",
        market_regime="bullish",
        initial_reaction="up",
        outcome_horizon="20d",
        outcome_return=0.05,
        outcome_excess_return=0.03,
    )
    episode2 = MarketEpisode(
        episode_id="test-episode-005",
        event_id="test-event-005",
        event_type="earnings",
        market_regime="bullish",
        initial_reaction="down",
        outcome_horizon="20d",
        outcome_return=-0.02,
        outcome_excess_return=-0.01,
    )
    client.post("/api/memory/episodes", json=episode1.model_dump())
    client.post("/api/memory/episodes", json=episode2.model_dump())
    
    response = client.get("/api/memory/summarize/earnings")
    assert response.status_code == 200
    data = response.json()
    assert data["sample_size"] == 2
    assert data["win_rate"] == 0.5
    assert abs(data["average_excess_return"] - 0.01) < 1e-9
