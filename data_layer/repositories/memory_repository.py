"""Memory repository implementation for Memory & Learning module."""
import json
from typing import List, Optional, Dict, Union

from sqlalchemy import select, text, and_
from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from memory_learning.contracts import (
    MarketEpisode,
    StrategyMemory,
    AgentMemory,
    FailureMemory,
)

logger = get_logger(__name__)


class MemoryRepositoryImpl(BaseRepository):
    """Memory repository implementation for persisting Memory & Learning data."""

    def __init__(self, db: Optional[Session] = None):
        super().__init__(db)

    def save_episode(self, episode: MarketEpisode) -> MarketEpisode:
        """Save a market episode to the database."""
        query = text("""
            INSERT INTO market_episode (
                episode_id, event_id, event_type, market_regime, initial_reaction,
                outcome_horizon, outcome_return, outcome_excess_return, timing_action,
                signal_id, timing_decision_id, failed_reason, lesson, evidence_refs, metadata
            ) VALUES (
                :episode_id, :event_id, :event_type, :market_regime, :initial_reaction,
                :outcome_horizon, :outcome_return, :outcome_excess_return, :timing_action,
                :signal_id, :timing_decision_id, :failed_reason, :lesson, :evidence_refs, :metadata
            )
            ON CONFLICT (episode_id) DO UPDATE SET
                event_id = EXCLUDED.event_id,
                event_type = EXCLUDED.event_type,
                market_regime = EXCLUDED.market_regime,
                initial_reaction = EXCLUDED.initial_reaction,
                outcome_horizon = EXCLUDED.outcome_horizon,
                outcome_return = EXCLUDED.outcome_return,
                outcome_excess_return = EXCLUDED.outcome_excess_return,
                timing_action = EXCLUDED.timing_action,
                signal_id = EXCLUDED.signal_id,
                timing_decision_id = EXCLUDED.timing_decision_id,
                failed_reason = EXCLUDED.failed_reason,
                lesson = EXCLUDED.lesson,
                evidence_refs = EXCLUDED.evidence_refs,
                metadata = EXCLUDED.metadata
            RETURNING episode_id;
        """)
        params = {
            "episode_id": episode.episode_id,
            "event_id": episode.event_id,
            "event_type": episode.event_type,
            "market_regime": episode.market_regime,
            "initial_reaction": episode.initial_reaction,
            "outcome_horizon": episode.outcome_horizon,
            "outcome_return": episode.outcome_return,
            "outcome_excess_return": episode.outcome_excess_return,
            "timing_action": episode.timing_action,
            "signal_id": episode.signal_id,
            "timing_decision_id": episode.timing_decision_id,
            "failed_reason": episode.failed_reason,
            "lesson": episode.lesson,
            "evidence_refs": json.dumps(episode.evidence_refs),
            "metadata": json.dumps(episode.metadata),
        }
        with self.db.begin():
            result = self.db.execute(query, params)
            result.fetchone()
        return episode

    def get_episode(self, episode_id: str) -> Optional[MarketEpisode]:
        """Get a market episode by ID."""
        query = text("""
            SELECT
                episode_id, event_id, event_type, market_regime, initial_reaction,
                outcome_horizon, outcome_return, outcome_excess_return, timing_action,
                signal_id, timing_decision_id, failed_reason, lesson, evidence_refs, metadata
            FROM market_episode
            WHERE episode_id = :episode_id;
        """)
        result = self.db.execute(query, {"episode_id": episode_id})
        row = result.fetchone()
        if not row:
            return None

        return MarketEpisode(
            episode_id=row[0],
            event_id=row[1],
            event_type=row[2],
            market_regime=row[3],
            initial_reaction=row[4],
            outcome_horizon=row[5],
            outcome_return=float(row[6]),
            outcome_excess_return=float(row[7]),
            timing_action=row[8],
            signal_id=row[9],
            timing_decision_id=row[10],
            failed_reason=row[11],
            lesson=row[12],
            evidence_refs=json.loads(row[13]) if isinstance(row[13], str) else row[13],
            metadata=json.loads(row[14]) if isinstance(row[14], str) else row[14],
        )

    def list_episodes(
        self,
        event_type: Optional[str] = None,
        market_regime: Optional[str] = None,
        limit: int = 100,
    ) -> List[MarketEpisode]:
        """List market episodes with optional filtering."""
        conditions = []
        params = {}
        if event_type:
            conditions.append("event_type = :event_type")
            params["event_type"] = event_type
        if market_regime:
            conditions.append("market_regime = :market_regime")
            params["market_regime"] = market_regime

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = text(f"""
            SELECT
                episode_id, event_id, event_type, market_regime, initial_reaction,
                outcome_horizon, outcome_return, outcome_excess_return, timing_action,
                signal_id, timing_decision_id, failed_reason, lesson, evidence_refs, metadata
            FROM market_episode
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit;
        """)
        params["limit"] = limit

        results = self.db.execute(query, params)
        episodes = []
        for row in results:
            episodes.append(MarketEpisode(
                episode_id=row[0],
                event_id=row[1],
                event_type=row[2],
                market_regime=row[3],
                initial_reaction=row[4],
                outcome_horizon=row[5],
                outcome_return=float(row[6]),
                outcome_excess_return=float(row[7]),
                timing_action=row[8],
                signal_id=row[9],
                timing_decision_id=row[10],
                failed_reason=row[11],
                lesson=row[12],
                evidence_refs=json.loads(row[13]) if isinstance(row[13], str) else row[13],
                metadata=json.loads(row[14]) if isinstance(row[14], str) else row[14],
            ))
        return episodes

    def save_strategy(self, strategy: StrategyMemory) -> StrategyMemory:
        """Save a strategy memory to the database."""
        query = text("""
            INSERT INTO strategy_memory (
                strategy_id, signal_family, market_regime, sample_size,
                win_rate, average_excess_return, sharpe_ratio, notes
            ) VALUES (
                :strategy_id, :signal_family, :market_regime, :sample_size,
                :win_rate, :average_excess_return, :sharpe_ratio, :notes
            )
            ON CONFLICT (strategy_id) DO UPDATE SET
                signal_family = EXCLUDED.signal_family,
                market_regime = EXCLUDED.market_regime,
                sample_size = EXCLUDED.sample_size,
                win_rate = EXCLUDED.win_rate,
                average_excess_return = EXCLUDED.average_excess_return,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                notes = EXCLUDED.notes
            RETURNING strategy_id;
        """)
        params = {
            "strategy_id": strategy.strategy_id,
            "signal_family": strategy.signal_family,
            "market_regime": strategy.market_regime,
            "sample_size": strategy.sample_size,
            "win_rate": strategy.win_rate,
            "average_excess_return": strategy.average_excess_return,
            "sharpe_ratio": strategy.sharpe_ratio,
            "notes": json.dumps(strategy.notes),
        }
        with self.db.begin():
            result = self.db.execute(query, params)
            result.fetchone()
        return strategy

    def list_strategies(
        self,
        signal_family: Optional[str] = None,
        market_regime: Optional[str] = None,
    ) -> List[StrategyMemory]:
        """List strategy memories with optional filtering."""
        conditions = []
        params = {}
        if signal_family:
            conditions.append("signal_family = :signal_family")
            params["signal_family"] = signal_family
        if market_regime:
            conditions.append("market_regime = :market_regime")
            params["market_regime"] = market_regime

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = text(f"""
            SELECT
                strategy_id, signal_family, market_regime, sample_size,
                win_rate, average_excess_return, sharpe_ratio, notes
            FROM strategy_memory
            {where_clause}
            ORDER BY created_at DESC;
        """)

        results = self.db.execute(query, params)
        strategies = []
        for row in results:
            strategies.append(StrategyMemory(
                strategy_id=row[0],
                signal_family=row[1],
                market_regime=row[2],
                sample_size=row[3],
                win_rate=float(row[4]),
                average_excess_return=float(row[5]),
                sharpe_ratio=float(row[6]),
                notes=json.loads(row[7]) if isinstance(row[7], str) else row[7],
            ))
        return strategies

    def save_agent_memory(self, memory: AgentMemory) -> AgentMemory:
        """Save an agent memory to the database."""
        query = text("""
            INSERT INTO agent_memory (
                memory_id, agent_name, agent_role, belief, confidence,
                support_count, contradiction_count, last_updated_reason
            ) VALUES (
                :memory_id, :agent_name, :agent_role, :belief, :confidence,
                :support_count, :contradiction_count, :last_updated_reason
            )
            ON CONFLICT (memory_id) DO UPDATE SET
                agent_name = EXCLUDED.agent_name,
                agent_role = EXCLUDED.agent_role,
                belief = EXCLUDED.belief,
                confidence = EXCLUDED.confidence,
                support_count = EXCLUDED.support_count,
                contradiction_count = EXCLUDED.contradiction_count,
                last_updated_reason = EXCLUDED.last_updated_reason
            RETURNING memory_id;
        """)
        params = {
            "memory_id": memory.memory_id,
            "agent_name": memory.agent_name,
            "agent_role": memory.agent_role,
            "belief": memory.belief,
            "confidence": memory.confidence,
            "support_count": memory.support_count,
            "contradiction_count": memory.contradiction_count,
            "last_updated_reason": memory.last_updated_reason,
        }
        with self.db.begin():
            result = self.db.execute(query, params)
            result.fetchone()
        return memory

    def list_agent_memories(
        self,
        agent_name: Optional[str] = None,
        agent_role: Optional[str] = None,
    ) -> List[AgentMemory]:
        """List agent memories with optional filtering."""
        conditions = []
        params = {}
        if agent_name:
            conditions.append("agent_name = :agent_name")
            params["agent_name"] = agent_name
        if agent_role:
            conditions.append("agent_role = :agent_role")
            params["agent_role"] = agent_role

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = text(f"""
            SELECT
                memory_id, agent_name, agent_role, belief, confidence,
                support_count, contradiction_count, last_updated_reason
            FROM agent_memory
            {where_clause}
            ORDER BY created_at DESC;
        """)

        results = self.db.execute(query, params)
        memories = []
        for row in results:
            memories.append(AgentMemory(
                memory_id=row[0],
                agent_name=row[1],
                agent_role=row[2],
                belief=row[3],
                confidence=float(row[4]),
                support_count=row[5],
                contradiction_count=row[6],
                last_updated_reason=row[7],
            ))
        return memories

    def save_failure(self, failure: FailureMemory) -> FailureMemory:
        """Save a failure memory to the database."""
        query = text("""
            INSERT INTO failure_memory (
                failure_id, source_id, failure_type, root_cause,
                corrective_action, evidence_refs
            ) VALUES (
                :failure_id, :source_id, :failure_type, :root_cause,
                :corrective_action, :evidence_refs
            )
            ON CONFLICT (failure_id) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                failure_type = EXCLUDED.failure_type,
                root_cause = EXCLUDED.root_cause,
                corrective_action = EXCLUDED.corrective_action,
                evidence_refs = EXCLUDED.evidence_refs
            RETURNING failure_id;
        """)
        params = {
            "failure_id": failure.failure_id,
            "source_id": failure.source_id,
            "failure_type": failure.failure_type,
            "root_cause": failure.root_cause,
            "corrective_action": failure.corrective_action,
            "evidence_refs": json.dumps(failure.evidence_refs),
        }
        with self.db.begin():
            result = self.db.execute(query, params)
            result.fetchone()
        return failure

    def list_failures(
        self,
        failure_type: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[FailureMemory]:
        """List failure memories with optional filtering."""
        conditions = []
        params = {}
        if failure_type:
            conditions.append("failure_type = :failure_type")
            params["failure_type"] = failure_type
        if source_id:
            conditions.append("source_id = :source_id")
            params["source_id"] = source_id

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = text(f"""
            SELECT
                failure_id, source_id, failure_type, root_cause,
                corrective_action, evidence_refs
            FROM failure_memory
            {where_clause}
            ORDER BY created_at DESC;
        """)

        results = self.db.execute(query, params)
        failures = []
        for row in results:
            failures.append(FailureMemory(
                failure_id=row[0],
                source_id=row[1],
                failure_type=row[2],
                root_cause=row[3],
                corrective_action=row[4],
                evidence_refs=json.loads(row[5]) if isinstance(row[5], str) else row[5],
            ))
        return failures

    def summarize_event_type(self, event_type: str) -> Dict[str, Union[float, int]]:
        """Summarize statistics for a given event type.

        Returns:
            dict with:
                - total_episodes: int
                - average_return: float
                - average_excess_return: float
                - positive_rate: float (proportion of positive outcome returns)
        """
        query = text("""
            SELECT
                COUNT(*) AS total_episodes,
                AVG(outcome_return) AS average_return,
                AVG(outcome_excess_return) AS average_excess_return,
                CAST(SUM(CASE WHEN outcome_return > 0 THEN 1 ELSE 0 END) AS FLOAT) / CAST(COUNT(*) AS FLOAT) AS positive_rate
            FROM market_episode
            WHERE event_type = :event_type;
        """)
        result = self.db.execute(query, {"event_type": event_type})
        row = result.fetchone()

        if not row or row[0] == 0:
            return {
                "total_episodes": 0,
                "average_return": 0.0,
                "average_excess_return": 0.0,
                "positive_rate": 0.0,
            }

        return {
            "total_episodes": int(row[0]),
            "average_return": float(row[1]) if row[1] is not None else 0.0,
            "average_excess_return": float(row[2]) if row[2] is not None else 0.0,
            "positive_rate": float(row[3]) if row[3] is not None else 0.0,
        }
