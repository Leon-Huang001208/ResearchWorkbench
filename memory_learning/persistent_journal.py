"""Persistent implementation of LearningJournal using database storage."""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from core.observability import get_logger
from data_layer.repositories.memory_repository import MemoryRepositoryImpl

from .contracts import AgentMemory, FailureMemory, MarketEpisode, StrategyMemory

logger = get_logger(__name__)


class PersistentLearningJournal:
    """Persistent version of LearningJournal that stores all entities in PostgreSQL.

    Provides the same interface as the in-memory LearningJournal for compatibility,
    but delegates all operations to the persistent memory repository.
    """

    def __init__(self, memory_repository: MemoryRepositoryImpl):
        self._repo = memory_repository

    def record_episode(self, episode: MarketEpisode) -> MarketEpisode:
        """Record a market episode in the database."""
        return self._repo.save_episode(episode)

    def get_episode(self, episode_id: str) -> Optional[MarketEpisode]:
        """Get a market episode by ID from the database."""
        return self._repo.get_episode(episode_id)

    def list_episodes(
        self,
        event_type: Optional[str] = None,
        market_regime: Optional[str] = None,
    ) -> List[MarketEpisode]:
        """List market episodes from the database with optional filtering."""
        return self._repo.list_episodes(
            event_type=event_type,
            market_regime=market_regime,
        )

    def record_strategy(self, strategy: StrategyMemory) -> StrategyMemory:
        """Record a strategy memory in the database."""
        return self._repo.save_strategy(strategy)

    def list_strategies(
        self,
        signal_family: Optional[str] = None,
        market_regime: Optional[str] = None,
    ) -> List[StrategyMemory]:
        """List strategy memories from the database with optional filtering."""
        return self._repo.list_strategies(
            signal_family=signal_family,
            market_regime=market_regime,
        )

    def record_agent_memory(self, memory: AgentMemory) -> AgentMemory:
        """Record an agent memory in the database."""
        return self._repo.save_agent_memory(memory)

    def list_agent_memories(
        self,
        agent_name: Optional[str] = None,
        agent_role: Optional[str] = None,
    ) -> List[AgentMemory]:
        """List agent memories from the database with optional filtering."""
        return self._repo.list_agent_memories(
            agent_name=agent_name,
            agent_role=agent_role,
        )

    def record_failure(self, failure: FailureMemory) -> FailureMemory:
        """Record a failure memory in the database."""
        return self._repo.save_failure(failure)

    def list_failures(
        self,
        failure_type: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[FailureMemory]:
        """List failure memories from the database with optional filtering."""
        return self._repo.list_failures(
            failure_type=failure_type,
            source_id=source_id,
        )

    def summarize_event_type(self, event_type: str) -> Dict[str, Union[float, int]]:
        """Summarize statistics for a given event type from the database."""
        return self._repo.summarize_event_type(event_type)
