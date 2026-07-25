"""Pattern learner for Memory & Learning module.

Identifies patterns from historical market episodes to improve future decisions.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from core.observability import get_logger
from memory_learning.contracts import MarketEpisode

logger = get_logger(__name__)


class PatternLearner:
    """Learns patterns from historical market episodes."""

    def __init__(self) -> None:
        self._episodes_by_type: Dict[str, List[MarketEpisode]] = defaultdict(list)
        self._episodes_by_regime: Dict[str, List[MarketEpisode]] = defaultdict(list)

    def learn_from_episodes(self, episodes: List[MarketEpisode]) -> None:
        """Learn patterns from a list of market episodes."""
        for episode in episodes:
            self._episodes_by_type[episode.event_type].append(episode)
            self._episodes_by_regime[episode.market_regime].append(episode)

        logger.info(
            "learned patterns from episodes",
            total_episodes=len(episodes),
            event_types_count=len(self._episodes_by_type),
            regimes_count=len(self._episodes_by_regime),
        )

    def get_event_type_performance(self, event_type: str) -> Optional[Dict[str, float]]:
        """Get performance statistics for an event type."""
        episodes = self._episodes_by_type.get(event_type, [])
        if not episodes:
            return None

        returns = [e.outcome_return for e in episodes]
        excess_returns = [e.outcome_excess_return for e in episodes]

        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        avg_return = sum(returns) / len(returns)
        avg_excess_return = sum(excess_returns) / len(excess_returns)
        volatility = self._calculate_volatility(returns)
        sharpe = avg_return / volatility if volatility > 0 else 0.0

        return {
            "sample_size": len(episodes),
            "win_rate": win_rate,
            "average_return": avg_return,
            "average_excess_return": avg_excess_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe,
        }

    def get_market_regime_performance(self, market_regime: str) -> Optional[Dict[str, Any]]:
        """Get performance statistics for a market regime."""
        episodes = self._episodes_by_regime.get(market_regime, [])
        if not episodes:
            return None

        event_type_stats: Dict[str, List[float]] = defaultdict(list)
        for episode in episodes:
            event_type_stats[episode.event_type].append(episode.outcome_excess_return)

        best_event_types = sorted(
            event_type_stats.items(),
            key=lambda x: sum(x[1]) / len(x[1]),
            reverse=True,
        )

        returns = [e.outcome_return for e in episodes]
        avg_return = sum(returns) / len(returns)

        return {
            "sample_size": len(episodes),
            "average_return": avg_return,
            "best_event_types": [et for et, _ in best_event_types[:5]],
            "event_type_count": len(event_type_stats),
        }

    def find_similar_episodes(self, event_type: str, top_k: int = 5) -> List[MarketEpisode]:
        """Find the most similar episodes (sorted by performance)."""
        episodes = self._episodes_by_type.get(event_type, [])
        if not episodes:
            return []

        sorted_episodes = sorted(
            episodes,
            key=lambda e: e.outcome_excess_return,
            reverse=True,
        )

        return sorted_episodes[:top_k]

    def get_recommendation(self, event_type: str, market_regime: str) -> Dict[str, Any]:
        """Get a recommendation for a new event based on past patterns."""
        event_performance = self.get_event_type_performance(event_type)
        regime_performance = self.get_market_regime_performance(market_regime)

        recommendation: Dict[str, Any] = {
            "should_trade": False,
            "confidence": 0.0,
            "reason": "",
            "historical_analogy": None,
        }

        if event_performance and event_performance["win_rate"] > 0.5:
            recommendation["should_trade"] = True
            recommendation["confidence"] = event_performance["win_rate"]
            recommendation[
                "reason"
            ] = f"Event type {event_type} has {event_performance['win_rate']:.1%} win rate with {event_performance['average_excess_return']:.1%} avg excess return"

        if regime_performance and event_type in regime_performance.get("best_event_types", []):
            confidence = float(recommendation["confidence"])
            recommendation["confidence"] = min(0.95, confidence + 0.2)
            recommendation["reason"] = (
                str(recommendation["reason"]) + f" and performs well in {market_regime} regime"
            )

        return recommendation

    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate volatility of returns."""
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return float(variance**0.5)
