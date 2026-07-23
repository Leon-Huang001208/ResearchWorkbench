"""内存版学习日志。"""

from __future__ import annotations

from core.observability import get_logger

from .contracts import AgentMemory, FailureMemory, MarketEpisode, StrategyMemory

logger = get_logger(__name__)


class LearningJournal:
    """记录 Episode、Strategy、Agent 和 Failure memory 的最小实现。"""

    def __init__(self) -> None:
        self._episodes: dict[str, MarketEpisode] = {}
        self._strategies: dict[str, StrategyMemory] = {}
        self._agent_memories: dict[str, AgentMemory] = {}
        self._failures: dict[str, FailureMemory] = {}

    def record_episode(self, episode: MarketEpisode) -> MarketEpisode:
        """记录一个事件结果样本。"""
        self._episodes[episode.episode_id] = episode
        logger.info(
            "market episode recorded",
            episode_id=episode.episode_id,
            event_id=episode.event_id,
            event_type=episode.event_type,
            outcome_excess_return=episode.outcome_excess_return,
        )
        return episode

    def get_episode(self, episode_id: str) -> MarketEpisode | None:
        """按 ID 获取事件记忆。"""
        return self._episodes.get(episode_id)

    def list_episodes(
        self,
        event_type: str | None = None,
        market_regime: str | None = None,
    ) -> list[MarketEpisode]:
        """查询事件记忆。"""
        episodes = list(self._episodes.values())
        if event_type is not None:
            episodes = [episode for episode in episodes if episode.event_type == event_type]
        if market_regime is not None:
            episodes = [episode for episode in episodes if episode.market_regime == market_regime]
        return episodes

    def record_strategy(self, strategy: StrategyMemory) -> StrategyMemory:
        """记录策略记忆。"""
        self._strategies[strategy.strategy_id] = strategy
        logger.info(
            "strategy memory recorded",
            strategy_id=strategy.strategy_id,
            signal_family=strategy.signal_family,
            market_regime=strategy.market_regime,
        )
        return strategy

    def list_strategies(
        self,
        signal_family: str | None = None,
        market_regime: str | None = None,
    ) -> list[StrategyMemory]:
        """查询策略记忆。"""
        strategies = list(self._strategies.values())
        if signal_family is not None:
            strategies = [
                strategy for strategy in strategies if strategy.signal_family == signal_family
            ]
        if market_regime is not None:
            strategies = [
                strategy for strategy in strategies if strategy.market_regime == market_regime
            ]
        return strategies

    def record_agent_memory(self, memory: AgentMemory) -> AgentMemory:
        """记录 Agent 长期观点记忆。"""
        self._agent_memories[memory.memory_id] = memory
        logger.info(
            "agent memory recorded",
            memory_id=memory.memory_id,
            agent_name=memory.agent_name,
            agent_role=memory.agent_role,
        )
        return memory

    def list_agent_memories(
        self,
        agent_name: str | None = None,
        agent_role: str | None = None,
    ) -> list[AgentMemory]:
        """查询 Agent 记忆。"""
        memories = list(self._agent_memories.values())
        if agent_name is not None:
            memories = [memory for memory in memories if memory.agent_name == agent_name]
        if agent_role is not None:
            memories = [memory for memory in memories if memory.agent_role == agent_role]
        return memories

    def record_failure(self, failure: FailureMemory) -> FailureMemory:
        """记录失败记忆。"""
        self._failures[failure.failure_id] = failure
        logger.info(
            "failure memory recorded",
            failure_id=failure.failure_id,
            failure_type=failure.failure_type,
            source_id=failure.source_id,
        )
        return failure

    def list_failures(
        self,
        failure_type: str | None = None,
        source_id: str | None = None,
    ) -> list[FailureMemory]:
        """查询失败记忆。"""
        failures = list(self._failures.values())
        if failure_type is not None:
            failures = [failure for failure in failures if failure.failure_type == failure_type]
        if source_id is not None:
            failures = [failure for failure in failures if failure.source_id == source_id]
        return failures

    def summarize_event_type(self, event_type: str) -> dict[str, float | int]:
        """按事件类型汇总 Event -> Return 表现。"""
        episodes = self.list_episodes(event_type=event_type)
        if not episodes:
            return {
                "sample_size": 0,
                "win_rate": 0.0,
                "average_excess_return": 0.0,
            }

        wins = sum(1 for episode in episodes if episode.outcome_excess_return > 0)
        average_excess_return = sum(episode.outcome_excess_return for episode in episodes) / len(
            episodes
        )
        return {
            "sample_size": len(episodes),
            "win_rate": wins / len(episodes),
            "average_excess_return": average_excess_return,
        }
