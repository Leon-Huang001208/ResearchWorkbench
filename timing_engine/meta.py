"""Meta Timing System。"""

from __future__ import annotations

from typing import Literal

from core.observability import get_logger
from memory_learning.contracts import FailureMemory

from .contracts import MarketRegime, TimingDecision, TimingModelScore

logger = get_logger(__name__)


class MetaTimingEngine:
    """融合多类择时模型，输出交易节奏决策。"""

    BASE_WEIGHTS: dict[str, float] = {
        "regime": 0.20,
        "flow": 0.18,
        "theme_diffusion": 0.14,
        "sentiment": 0.12,
        "market_structure": 0.10,
        "liquidity": 0.10,
        "crowding": 0.08,
        "expectation_gap": 0.06,
        "alpha_decay": 0.02,
    }

    REGIME_WEIGHT_OVERRIDES: dict[str, dict[str, float]] = {
        "hot_money_theme": {
            "sentiment": 0.22,
            "theme_diffusion": 0.20,
            "flow": 0.18,
            "market_structure": 0.12,
            "regime": 0.10,
            "crowding": 0.10,
            "liquidity": 0.05,
            "expectation_gap": 0.03,
        },
        "institutional_trend": {
            "regime": 0.22,
            "flow": 0.20,
            "expectation_gap": 0.16,
            "market_structure": 0.12,
            "theme_diffusion": 0.10,
            "liquidity": 0.10,
            "crowding": 0.06,
            "sentiment": 0.04,
        },
        "risk_off": {
            "regime": 0.28,
            "liquidity": 0.20,
            "flow": 0.18,
            "sentiment": 0.12,
            "crowding": 0.10,
            "market_structure": 0.08,
            "theme_diffusion": 0.04,
        },
    }

    RISK_MODELS = {"crowding", "alpha_decay"}

    def __init__(
        self,
        enter_threshold: float = 0.65,
        wait_threshold: float = 0.48,
        blocker_threshold: float = 0.75,
        weak_support_threshold: float = 0.35,
    ):
        if not 0.0 <= wait_threshold <= enter_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= wait <= enter <= 1")
        self.enter_threshold = enter_threshold
        self.wait_threshold = wait_threshold
        self.blocker_threshold = blocker_threshold
        self.weak_support_threshold = weak_support_threshold

    def evaluate(
        self,
        scores: list[TimingModelScore],
        signal_id: str | None = None,
        market_regime: MarketRegime = "unknown",
    ) -> TimingDecision:
        """融合模型评分，判断现在是否适合交易。"""
        if not scores:
            logger.error("timing evaluation failed: no scores provided", signal_id=signal_id)
            raise ValueError("at least one timing score is required")

        weights = self.weights_for_regime(market_regime)
        readiness = self._readiness_score(scores, weights)
        blockers = self._find_blockers(scores)
        action = self._action(readiness, blockers)
        rationale = self._rationale(scores, readiness, blockers)

        decision = TimingDecision(
            action=action,
            readiness_score=readiness,
            signal_id=signal_id,
            market_regime=market_regime,
            model_scores=scores,
            active_weights=weights,
            blockers=blockers,
            rationale=rationale,
        )
        logger.info(
            "timing decision generated",
            action=decision.action,
            readiness_score=decision.readiness_score,
            signal_id=signal_id,
            market_regime=market_regime,
            blockers=blockers,
        )
        return decision

    def weights_for_regime(self, market_regime: MarketRegime) -> dict[str, float]:
        """根据市场阶段选择 Meta Timing 权重。"""
        weights = self.REGIME_WEIGHT_OVERRIDES.get(market_regime, self.BASE_WEIGHTS)
        return self._normalize_weights(weights)

    def _readiness_score(
        self,
        scores: list[TimingModelScore],
        weights: dict[str, float],
    ) -> float:
        weighted_sum = 0.0
        used_weight = 0.0
        for score in scores:
            weight = weights.get(score.model_name, 0.0)
            if weight == 0.0:
                continue
            support = 1.0 - score.score if score.model_name in self.RISK_MODELS else score.score
            weighted_sum += support * score.confidence * weight
            used_weight += score.confidence * weight

        if used_weight == 0.0:
            logger.error("timing evaluation failed: no usable score weights")
            raise ValueError("at least one timing score must have usable model weight")
        return max(0.0, min(1.0, weighted_sum / used_weight))

    def _find_blockers(self, scores: list[TimingModelScore]) -> list[str]:
        blockers: list[str] = []
        for score in scores:
            if score.model_name in self.RISK_MODELS and score.score >= self.blocker_threshold:
                blockers.append(score.model_name)
            if (
                score.model_name not in self.RISK_MODELS
                and score.score <= self.weak_support_threshold
            ):
                blockers.append(score.model_name)
        return sorted(set(blockers))

    def _action(
        self, readiness: float, blockers: list[str]
    ) -> Literal["enter", "wait", "reduce", "exit", "block"]:
        if "regime" in blockers or "crowding" in blockers:
            return "block"
        if readiness >= self.enter_threshold and not blockers:
            return "enter"
        if readiness >= self.wait_threshold:
            return "wait" if blockers else "enter"
        if blockers:
            return "reduce"
        return "wait"

    @staticmethod
    def _rationale(
        scores: list[TimingModelScore],
        readiness: float,
        blockers: list[str],
    ) -> list[str]:
        rationale = [f"readiness_score={readiness:.3f}"]
        if blockers:
            rationale.append("blockers=" + ",".join(blockers))
        top_scores = sorted(scores, key=lambda item: item.confidence, reverse=True)[:3]
        for score in top_scores:
            rationale.append(f"{score.model_name}: {score.rationale}")
        return rationale

    def apply_failure_lessons(self, failures: list[FailureMemory]) -> dict[str, float]:
        """根据失败记忆调整模型权重。"""
        # Start with base weights
        adjusted_weights = self.BASE_WEIGHTS.copy()

        for failure in failures:
            if failure.failure_type == "crowding_error":
                # Increase crowding weight by 50%
                original = adjusted_weights.get("crowding", 0.08)
                adjusted_weights["crowding"] = original * 1.5
                logger.info(
                    "Increased crowding weight due to failure lesson",
                    failure_id=failure.failure_id,
                    original_weight=original,
                    new_weight=adjusted_weights["crowding"],
                )
            elif failure.failure_type == "timing_error":
                # Reduce regime weight by 20% (as a proxy for timing models)
                original = adjusted_weights.get("regime", 0.2)
                adjusted_weights["regime"] = original * 0.8
                logger.info(
                    "Reduced regime weight due to failure lesson",
                    failure_id=failure.failure_id,
                    original_weight=original,
                    new_weight=adjusted_weights["regime"],
                )

        # Normalize the adjusted weights
        return self._normalize_weights(adjusted_weights)

    @staticmethod
    def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        total = sum(weights.values())
        if total <= 0:
            logger.error("timing weight normalization failed")
            raise ValueError("timing weights must sum to a positive value")
        return {name: weight / total for name, weight in weights.items()}
