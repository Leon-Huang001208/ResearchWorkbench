"""Outcome Protocol 集成测试。

测试信号创建 -> 结果记录 -> summary 更新的端到端流程。
"""
import uuid
from datetime import datetime, timezone

import pytest

from core.contracts.outcomes import SignalOutcome
from memory_learning.journal import LearningJournal
from services.outcome_service import OutcomeService


def _make_outcome(**overrides) -> SignalOutcome:
    """创建测试用 SignalOutcome"""
    defaults = dict(
        outcome_id=str(uuid.uuid4()),
        event_id="event_gpt6_launch",
        signal_id=f"signal_{uuid.uuid4().hex[:8]}",
        subject_id="600000.SH",
        event_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        timing_action="enter",
        entry_rule="momentum_breakout",
        horizon="20d",
        benchmark="CSI300",
        outcome_return=0.18,
        outcome_excess_return=0.11,
        max_drawdown=0.05,
        decay=0.02,
        failure_reason=None,
        lesson=None,
        metadata={
            "event_type": "ai_model_launch",
            "strategy_family": "event_driven",
            "market_regime": "ai_growth",
            "initial_reaction": "光模块上涨",
        },
    )
    defaults.update(overrides)
    return SignalOutcome(**defaults)


class TestSignalOutcomeContract:
    """SignalOutcome 契约测试"""

    def test_create_outcome_with_all_fields(self):
        outcome = _make_outcome()
        assert outcome.event_id == "event_gpt6_launch"
        assert outcome.timing_action == "enter"
        assert outcome.horizon == "20d"
        assert outcome.outcome_excess_return == 0.11
        assert outcome.max_drawdown == 0.05
        assert outcome.decay == 0.02
        assert outcome.metadata.get("event_type") == "ai_model_launch"

    def test_create_outcome_with_minimal_fields(self):
        outcome = SignalOutcome(
            outcome_id="outcome_min",
            event_id="event_1",
            signal_id="signal_1",
            subject_id="000001.SZ",
            event_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        assert outcome.timing_action == "wait"
        assert outcome.horizon == "20d"
        assert outcome.outcome_return == 0.0
        assert outcome.outcome_excess_return == 0.0
        assert outcome.max_drawdown is None
        assert outcome.decay is None
        assert outcome.failure_reason is None
        assert outcome.lesson is None

    def test_outcome_with_failure(self):
        outcome = _make_outcome(
            outcome_return=-0.08,
            outcome_excess_return=-0.12,
            max_drawdown=0.15,
            failure_reason="wrong_thesis",
            lesson="AI叙事在risk_off regime下不可靠",
        )
        assert outcome.failure_reason == "wrong_thesis"
        assert outcome.lesson is not None


class TestOutcomeServiceRecordAndQuery:
    """OutcomeService 记录和查询测试"""

    def test_record_outcome_and_retrieve(self):
        service = OutcomeService()
        outcome = _make_outcome()
        recorded = service.record_outcome(outcome)

        # 应自动设置 evaluated_at
        assert recorded.evaluated_at is not None

        # 通过 outcome_id 查询
        retrieved = service.get_outcome(outcome.outcome_id)
        assert retrieved is not None
        assert retrieved.signal_id == outcome.signal_id
        assert retrieved.outcome_excess_return == 0.11

    def test_record_outcome_and_query_by_signal(self):
        service = OutcomeService()
        outcome = _make_outcome()
        service.record_outcome(outcome)

        retrieved = service.get_outcome_by_signal(outcome.signal_id)
        assert retrieved is not None
        assert retrieved.outcome_id == outcome.outcome_id

    def test_query_nonexistent_signal_returns_none(self):
        service = OutcomeService()
        result = service.get_outcome_by_signal("nonexistent_signal")
        assert result is None


class TestOutcomeServiceAggregate:
    """OutcomeService 聚合查询测试"""

    def test_list_outcomes_by_event_type(self):
        service = OutcomeService()
        o1 = _make_outcome(
            metadata={
                "event_type": "ai_model_launch",
                "strategy_family": "event_driven",
                "market_regime": "ai_growth",
                "initial_reaction": "上涨",
            }
        )
        o2 = _make_outcome(
            metadata={
                "event_type": "export_control",
                "strategy_family": "macro_defensive",
                "market_regime": "risk_off",
                "initial_reaction": "下跌",
            }
        )
        service.record_outcome(o1)
        service.record_outcome(o2)

        ai_outcomes = service.list_outcomes(event_type="ai_model_launch")
        assert len(ai_outcomes) == 1
        assert ai_outcomes[0].metadata["event_type"] == "ai_model_launch"

    def test_list_outcomes_by_strategy_family(self):
        service = OutcomeService()
        o1 = _make_outcome(
            metadata={
                "event_type": "ai_model_launch",
                "strategy_family": "event_driven",
                "market_regime": "ai_growth",
                "initial_reaction": "上涨",
            }
        )
        o2 = _make_outcome(
            metadata={
                "event_type": "export_control",
                "strategy_family": "macro_defensive",
                "market_regime": "risk_off",
                "initial_reaction": "下跌",
            }
        )
        service.record_outcome(o1)
        service.record_outcome(o2)

        macro_outcomes = service.list_outcomes(strategy_family="macro_defensive")
        assert len(macro_outcomes) == 1
        assert macro_outcomes[0].metadata["strategy_family"] == "macro_defensive"


class TestOutcomeServiceLessonUpdate:
    """OutcomeService 教训更新测试"""

    def test_update_lesson(self):
        service = OutcomeService()
        outcome = _make_outcome()
        service.record_outcome(outcome)

        updated = service.update_lesson(outcome.outcome_id, "AI叙事在risk_off regime下不可靠")
        assert updated is not None
        assert updated.lesson == "AI叙事在risk_off regime下不可靠"

    def test_update_lesson_nonexistent_outcome(self):
        service = OutcomeService()
        result = service.update_lesson("nonexistent_id", "some lesson")
        assert result is None


class TestOutcomeSyncsToJournal:
    """OutcomeService 同步到 LearningJournal 测试"""

    def test_record_outcome_creates_episode_in_journal(self):
        journal = LearningJournal()
        service = OutcomeService(journal=journal)
        outcome = _make_outcome()
        service.record_outcome(outcome)

        # Journal 中应有一个对应的 episode
        episode_id = f"episode_{outcome.outcome_id}"
        episode = journal.get_episode(episode_id)
        assert episode is not None
        assert episode.event_id == outcome.event_id
        assert episode.outcome_return == outcome.outcome_return
        assert episode.outcome_excess_return == outcome.outcome_excess_return
        assert episode.timing_action == outcome.timing_action
        assert episode.signal_id == outcome.signal_id

    def test_update_lesson_syncs_to_journal_episode(self):
        journal = LearningJournal()
        service = OutcomeService(journal=journal)
        outcome = _make_outcome()
        service.record_outcome(outcome)

        # 更新教训
        service.update_lesson(outcome.outcome_id, "新增教训")

        episode_id = f"episode_{outcome.outcome_id}"
        episode = journal.get_episode(episode_id)
        assert episode is not None
        assert episode.lesson == "新增教训"

    def test_journal_uses_outcome_protocol_fields(self):
        """验证 LearningJournal 中的 episode 使用 outcome 协议字段"""
        journal = LearningJournal()
        service = OutcomeService(journal=journal)
        outcome = _make_outcome(
            timing_action="exit",
            horizon="60d",
            outcome_return=0.25,
            outcome_excess_return=0.18,
            failure_reason="timing_error",
            lesson="进入太晚退出太早",
        )
        service.record_outcome(outcome)

        episode_id = f"episode_{outcome.outcome_id}"
        episode = journal.get_episode(episode_id)
        assert episode is not None
        assert episode.timing_action == "exit"
        assert episode.outcome_horizon == "60d"
        assert episode.outcome_return == 0.25
        assert episode.outcome_excess_return == 0.18
        assert episode.failed_reason == "timing_error"
        assert episode.lesson == "进入太晚退出太早"


class TestEndToEndOutcomeSummary:
    """端到端测试：信号创建 -> 结果记录 -> summary 更新"""

    def test_signal_to_outcome_to_summary(self):
        """从信号创建到结果记录再到 summary 的完整流程"""
        journal = LearningJournal()
        service = OutcomeService(journal=journal)

        # 记录多个同类型的 outcome
        for i in range(3):
            outcome = _make_outcome(
                outcome_return=0.10 + i * 0.02,
                outcome_excess_return=0.05 + i * 0.01,
                metadata={
                    "event_type": "ai_model_launch",
                    "strategy_family": "event_driven",
                    "market_regime": "ai_growth",
                    "initial_reaction": "上涨",
                },
            )
            service.record_outcome(outcome)

        # 记录一个不同类型的 outcome
        outcome_other = _make_outcome(
            outcome_return=-0.05,
            outcome_excess_return=-0.08,
            metadata={
                "event_type": "export_control",
                "strategy_family": "macro_defensive",
                "market_regime": "risk_off",
                "initial_reaction": "下跌",
            },
        )
        service.record_outcome(outcome_other)

        # 通过 journal summarize 验证 summary
        summary = journal.summarize_event_type("ai_model_launch")
        assert summary["sample_size"] == 3
        assert summary["win_rate"] == 1.0  # 三个都是正超额收益
        assert summary["average_excess_return"] == pytest.approx(0.06)

        summary_other = journal.summarize_event_type("export_control")
        assert summary_other["sample_size"] == 1
        assert summary_other["win_rate"] == 0.0  # 负超额收益

    def test_outcomes_aggregatable_by_strategy_family(self):
        """结果可按策略家族聚合"""
        service = OutcomeService()

        for i in range(2):
            outcome = _make_outcome(
                metadata={
                    "event_type": "ai_model_launch",
                    "strategy_family": "event_driven",
                    "market_regime": "ai_growth",
                    "initial_reaction": "上涨",
                }
            )
            service.record_outcome(outcome)

        for i in range(2):
            outcome = _make_outcome(
                metadata={
                    "event_type": "policy_change",
                    "strategy_family": "momentum",
                    "market_regime": "neutral",
                    "initial_reaction": "震荡",
                }
            )
            service.record_outcome(outcome)

        event_driven = service.list_outcomes(strategy_family="event_driven")
        momentum = service.list_outcomes(strategy_family="momentum")

        assert len(event_driven) == 2
        assert len(momentum) == 2
