"""
Memory & Learning Layer 测试

记忆层记录“事件发生后市场如何反应”，为后续 Agent 权重、Timing 权重和策略有效性更新提供事实。
"""

import pytest
from pydantic import ValidationError

from memory_learning import FailureMemory, LearningJournal, MarketEpisode, StrategyMemory


def test_market_episode_records_event_to_return_outcome():
    """事件记忆应保存 Event -> Return 的核心闭环字段"""
    episode = MarketEpisode(
        episode_id="episode_gpt6_001",
        event_id="event_gpt6_launch",
        event_type="ai_model_launch",
        market_regime="ai_growth",
        initial_reaction="光模块和铜连接上涨",
        outcome_horizon="30d",
        outcome_return=0.18,
        outcome_excess_return=0.11,
        timing_action="enter",
        lesson="AI推理叙事在AI成长regime下扩散速度快",
    )

    assert episode.event_id == "event_gpt6_launch"
    assert episode.outcome_excess_return == 0.11
    assert episode.lesson.startswith("AI推理")


def test_learning_journal_indexes_episode_strategy_and_failure_memory():
    """学习日志应能汇总事件、策略和失败记忆"""
    journal = LearningJournal()
    episode = MarketEpisode(
        episode_id="episode_gpu_ban_001",
        event_id="event_gpu_ban",
        event_type="export_control",
        market_regime="ai_growth",
        initial_reaction="国产算力上涨",
        outcome_horizon="20d",
        outcome_return=0.22,
        outcome_excess_return=0.14,
    )
    strategy = StrategyMemory(
        strategy_id="strategy_ai_export_control",
        signal_family="export_control_to_domestic_compute",
        market_regime="ai_growth",
        sample_size=12,
        win_rate=0.67,
        average_excess_return=0.09,
        sharpe_ratio=1.4,
    )
    failure = FailureMemory(
        failure_id="failure_crowding_001",
        source_id="event_sig_001",
        failure_type="timing_error",
        root_cause="高拥挤阶段追高",
        corrective_action="提高crowding blocker权重",
    )

    journal.record_episode(episode)
    journal.record_strategy(strategy)
    journal.record_failure(failure)

    assert journal.get_episode("episode_gpu_ban_001") == episode
    assert journal.list_strategies(market_regime="ai_growth") == [strategy]
    assert journal.list_failures(failure_type="timing_error") == [failure]


def test_learning_journal_summarizes_event_family_performance():
    """学习日志应能按事件类型统计平均超额收益和胜率"""
    journal = LearningJournal()
    journal.record_episode(
        MarketEpisode(
            episode_id="episode_1",
            event_id="event_1",
            event_type="ai_model_launch",
            market_regime="ai_growth",
            initial_reaction="上涨",
            outcome_horizon="20d",
            outcome_return=0.10,
            outcome_excess_return=0.06,
        )
    )
    journal.record_episode(
        MarketEpisode(
            episode_id="episode_2",
            event_id="event_2",
            event_type="ai_model_launch",
            market_regime="risk_off",
            initial_reaction="冲高回落",
            outcome_horizon="20d",
            outcome_return=-0.03,
            outcome_excess_return=-0.05,
        )
    )

    summary = journal.summarize_event_type("ai_model_launch")

    assert summary["sample_size"] == 2
    assert summary["win_rate"] == 0.5
    assert summary["average_excess_return"] == pytest.approx(0.005)


def test_market_episode_rejects_unknown_timing_action():
    """记忆层也必须沿用统一交易节奏 ontology"""
    with pytest.raises(ValidationError):
        MarketEpisode(
            episode_id="bad_episode",
            event_id="event_1",
            event_type="ai_model_launch",
            market_regime="ai_growth",
            initial_reaction="上涨",
            outcome_horizon="20d",
            outcome_return=0.1,
            outcome_excess_return=0.05,
            timing_action="random_trade",
        )
