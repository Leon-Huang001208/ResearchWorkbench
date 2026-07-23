"""Outcome Service — 事件信号结果评估服务。

记录信号结果、查询结果、更新教训，并同步更新 LearningJournal。
"""

from datetime import datetime, timezone
from typing import List, Optional

from core.contracts.outcomes import SignalOutcome
from core.observability import get_logger
from core.settings.config import settings
from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl
from memory_learning.contracts import MarketEpisode
from memory_learning.journal import LearningJournal

logger = get_logger(__name__)


class OutcomeService:
    """事件信号结果评估服务"""

    def __init__(
        self,
        repository: Optional[OutcomeRepositoryImpl] = None,
        journal: Optional[LearningJournal] = None,
    ):
        self.repository = repository
        self.journal = journal or LearningJournal()
        self._outcomes: dict[str, SignalOutcome] = {}  # fallback if no repo

        if settings.APP_ENV == "prod" and self.repository is None:
            raise RuntimeError(
                "OutcomeService: No repository provided in production mode (APP_ENV=prod). "
                "In-memory fallback is not allowed in production for durable persistence."
            )

    def record_outcome(self, outcome: SignalOutcome) -> SignalOutcome:
        """记录信号结果评估。

        同时同步更新 LearningJournal 中的 MarketEpisode。
        """
        if outcome.evaluated_at is None:
            outcome = outcome.model_copy(update={"evaluated_at": datetime.now(timezone.utc)})

        if self.repository:
            outcome = self.repository.save(outcome)
        else:
            self._outcomes[outcome.outcome_id] = outcome

        logger.info(
            "outcome recorded",
            outcome_id=outcome.outcome_id,
            signal_id=outcome.signal_id,
            event_id=outcome.event_id,
            outcome_excess_return=outcome.outcome_excess_return,
        )

        # 同步更新 LearningJournal 中的 MarketEpisode
        self._sync_to_journal(outcome)

        return outcome

    def get_outcome(self, outcome_id: str) -> Optional[SignalOutcome]:
        """按 outcome_id 获取结果评估"""
        if self.repository:
            return self.repository.get(outcome_id)
        return self._outcomes.get(outcome_id)

    def get_outcome_by_signal(self, signal_id: str) -> Optional[SignalOutcome]:
        """按 signal_id 获取结果评估"""
        if self.repository:
            return self.repository.get_by_signal_id(signal_id)
        for outcome in self._outcomes.values():
            if outcome.signal_id == signal_id:
                return outcome
        return None

    def list_outcomes(
        self,
        event_type: Optional[str] = None,
        strategy_family: Optional[str] = None,
        limit: int = 100,
    ) -> List[SignalOutcome]:
        """聚合查询结果评估"""
        if self.repository:
            return self.repository.list(
                event_type=event_type,
                strategy_family=strategy_family,
                limit=limit,
            )
        outcomes = list(self._outcomes.values())
        if event_type is not None:
            outcomes = [o for o in outcomes if o.metadata.get("event_type") == event_type]
        if strategy_family is not None:
            outcomes = [o for o in outcomes if o.metadata.get("strategy_family") == strategy_family]
        return outcomes[:limit]

    def update_lesson(self, outcome_id: str, lesson: str) -> Optional[SignalOutcome]:
        """更新教训字段"""
        if self.repository:
            outcome = self.repository.update_lesson(outcome_id, lesson)
        else:
            outcome = self._outcomes.get(outcome_id)
            if outcome is not None:
                outcome = outcome.model_copy(update={"lesson": lesson})
                self._outcomes[outcome_id] = outcome

        if outcome is not None:
            logger.info("lesson updated", outcome_id=outcome_id)
            # 同步更新 journal 中对应的 episode
            self._sync_lesson_to_journal(outcome)
        else:
            logger.warning("outcome not found for lesson update", outcome_id=outcome_id)

        return outcome

    def _sync_to_journal(self, outcome: SignalOutcome) -> None:
        """将结果评估同步到 LearningJournal 的 MarketEpisode。

        使用 outcome 协议数据创建/更新 MarketEpisode，
        让 Memory 层使用此协议而非 ad-hoc 字段。
        """
        episode_id = f"episode_{outcome.outcome_id}"
        episode = MarketEpisode(
            episode_id=episode_id,
            event_id=outcome.event_id,
            event_type=outcome.metadata.get("event_type", "unknown"),
            market_regime=outcome.metadata.get("market_regime", "unknown"),
            initial_reaction=outcome.metadata.get("initial_reaction", ""),
            outcome_horizon=outcome.horizon,
            outcome_return=outcome.outcome_return,
            outcome_excess_return=outcome.outcome_excess_return,
            timing_action=outcome.timing_action,
            signal_id=outcome.signal_id,
            failed_reason=outcome.failure_reason,
            lesson=outcome.lesson,
        )
        self.journal.record_episode(episode)
        logger.info(
            "outcome synced to journal",
            outcome_id=outcome.outcome_id,
            episode_id=episode_id,
        )

    def _sync_lesson_to_journal(self, outcome: SignalOutcome) -> None:
        """教训更新时同步到 journal 中的 episode"""
        episode_id = f"episode_{outcome.outcome_id}"
        existing = self.journal.get_episode(episode_id)
        if existing is not None:
            updated = existing.model_copy(update={"lesson": outcome.lesson})
            self.journal.record_episode(updated)
            logger.info(
                "lesson synced to journal episode",
                episode_id=episode_id,
            )
