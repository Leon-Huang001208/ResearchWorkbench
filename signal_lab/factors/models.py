"""Dynamic factor models."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Literal

import numpy as np
import pandas as pd

from core.contracts.factors import DynamicFactorWeights, FactorEvaluation
from core.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FactorScoreResult:
    """Scoring output from a dynamic factor model."""

    raw_scores: dict[str, float]
    normalized_scores: dict[str, float]
    contributions: dict[str, dict[str, float]]
    weights: dict[str, float]


class RollingICWeightedModel:
    """Learn signed dynamic factor weights from rolling IC or RankIC."""

    def __init__(
        self,
        lookback_periods: int = 12,
        metric: Literal["ic", "rank_ic"] = "rank_ic",
    ):
        if lookback_periods <= 0:
            raise ValueError("lookback_periods must be positive")
        self.lookback_periods = lookback_periods
        self.metric = metric
        self._weights = DynamicFactorWeights(
            lookback_periods=lookback_periods,
            metric=metric,
        )

    @property
    def weights(self) -> DynamicFactorWeights:
        """Return the latest fitted weights."""
        return self._weights

    def fit(
        self,
        evaluations: Iterable[FactorEvaluation],
        as_of_date: date | None = None,
    ) -> DynamicFactorWeights:
        """Fit signed weights from recent factor evaluation records."""
        by_factor: dict[str, list[FactorEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            by_factor[evaluation.factor_id].append(evaluation)

        raw_scores: dict[str, float] = {}
        for factor_id, records in by_factor.items():
            records = sorted(
                records,
                key=lambda item: item.as_of_date or date.min,
            )[-self.lookback_periods :]
            metric_values = [float(getattr(record, self.metric)) for record in records]
            if metric_values:
                raw_scores[factor_id] = float(np.mean(metric_values))

        weights = self._normalize_signed(raw_scores)
        self._weights = DynamicFactorWeights(
            as_of_date=as_of_date,
            lookback_periods=self.lookback_periods,
            metric=self.metric,
            weights=weights,
            raw_scores=raw_scores,
        )
        logger.info(
            "rolling factor weights fitted",
            factor_count=len(weights),
            metric=self.metric,
            lookback_periods=self.lookback_periods,
        )
        return self._weights

    def score(self, factor_matrix: pd.DataFrame) -> FactorScoreResult:
        """Score subjects with the latest dynamic weights."""
        if not self._weights.weights:
            raise ValueError("model must be fitted before scoring")

        standardized = self._standardize(factor_matrix)
        raw_scores: dict[str, float] = {}
        contributions: dict[str, dict[str, float]] = {}

        for subject_id, row in standardized.iterrows():
            subject_contributions: dict[str, float] = {}
            total = 0.0
            for factor_id, weight in self._weights.weights.items():
                if factor_id not in row.index:
                    continue
                value = row[factor_id]
                if pd.isna(value):
                    continue
                contribution = float(value) * weight
                subject_contributions[factor_id] = contribution
                total += contribution
            raw_scores[str(subject_id)] = float(total)
            contributions[str(subject_id)] = subject_contributions

        normalized_scores = self._percentile_scores(pd.Series(raw_scores, dtype=float))
        return FactorScoreResult(
            raw_scores=raw_scores,
            normalized_scores=normalized_scores,
            contributions=contributions,
            weights=self._weights.weights,
        )

    @staticmethod
    def _normalize_signed(raw_scores: dict[str, float]) -> dict[str, float]:
        denominator = sum(abs(value) for value in raw_scores.values())
        if denominator == 0:
            return {factor_id: 0.0 for factor_id in raw_scores}
        return {factor_id: value / denominator for factor_id, value in raw_scores.items()}

    @staticmethod
    def _standardize(factor_matrix: pd.DataFrame) -> pd.DataFrame:
        standardized = pd.DataFrame(index=factor_matrix.index)
        for column in factor_matrix.columns:
            series = factor_matrix[column].astype(float)
            mean = series.mean(skipna=True)
            std = series.std(skipna=True, ddof=0)
            if std == 0 or np.isnan(std):
                standardized[column] = 0.0
            else:
                standardized[column] = (series - mean) / std
        return standardized

    @staticmethod
    def _percentile_scores(raw_scores: pd.Series) -> dict[str, float]:
        if raw_scores.empty:
            return {}
        if raw_scores.nunique(dropna=True) <= 1:
            return {str(index): 0.5 for index in raw_scores.index}
        ranks = raw_scores.rank(method="average", pct=True)
        return {str(index): float(value) for index, value in ranks.items()}
