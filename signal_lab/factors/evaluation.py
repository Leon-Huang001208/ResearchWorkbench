"""Factor evaluation metrics for dynamic multi-factor research."""
from __future__ import annotations

from datetime import date
from typing import Literal, cast

import numpy as np
import pandas as pd

from core.contracts.factors import FactorEvaluation
from core.observability import get_logger

logger = get_logger(__name__)


class FactorEvaluator:
    """Evaluate cross-sectional factor predictive power."""

    def __init__(self, horizon_days: int = 20, decile_fraction: float = 0.1):
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if not 0 < decile_fraction <= 0.5:
            raise ValueError("decile_fraction must be in (0, 0.5]")
        self.horizon_days = horizon_days
        self.decile_fraction = decile_fraction

    def evaluate(
        self,
        factor_matrix: pd.DataFrame,
        forward_returns: pd.Series | pd.DataFrame,
        as_of_date: date | None = None,
        factor_ids: list[str] | None = None,
    ) -> list[FactorEvaluation]:
        """Compute IC, RankIC, and top-bottom spread for each factor."""
        returns = self._extract_returns(forward_returns)
        factor_ids = factor_ids or list(factor_matrix.columns)
        evaluations: list[FactorEvaluation] = []

        for factor_id in factor_ids:
            if factor_id not in factor_matrix.columns:
                logger.warning("factor missing from matrix", factor_id=factor_id)
                continue
            aligned = pd.concat(
                [
                    factor_matrix[factor_id].rename("factor"),
                    returns.rename("forward_return"),
                ],
                axis=1,
                join="inner",
            ).dropna()
            total_subjects = len(factor_matrix.index.intersection(returns.index))
            coverage = len(aligned) / total_subjects if total_subjects else 0.0
            ic = self._correlation(aligned, method="pearson")
            rank_ic = self._correlation(aligned, method="spearman")
            spread = self._decile_spread(aligned)

            evaluations.append(
                FactorEvaluation(
                    factor_id=factor_id,
                    as_of_date=as_of_date,
                    horizon_days=self.horizon_days,
                    sample_size=int(len(aligned)),
                    coverage=float(coverage),
                    ic=ic,
                    rank_ic=rank_ic,
                    decile_spread=spread,
                )
            )

        logger.info(
            "factor evaluation completed",
            factor_count=len(evaluations),
            horizon_days=self.horizon_days,
        )
        return evaluations

    @staticmethod
    def _extract_returns(forward_returns: pd.Series | pd.DataFrame) -> pd.Series:
        if isinstance(forward_returns, pd.Series):
            return forward_returns.astype(float)
        if "forward_return" in forward_returns.columns:
            return forward_returns["forward_return"].astype(float)
        if "fwd_excess_return" in forward_returns.columns:
            return forward_returns["fwd_excess_return"].astype(float)
        if forward_returns.shape[1] == 1:
            return forward_returns.iloc[:, 0].astype(float)
        raise ValueError(
            "forward_returns DataFrame must contain forward_return, "
            "fwd_excess_return, or a single return column"
        )

    @staticmethod
    def _correlation(aligned: pd.DataFrame, method: str) -> float:
        if len(aligned) < 2:
            return 0.0
        corr_method = cast(Literal["pearson", "kendall", "spearman"], method)
        corr = aligned["factor"].corr(aligned["forward_return"], method=corr_method)
        if corr is None or np.isnan(corr):
            return 0.0
        return float(corr)

    def _decile_spread(self, aligned: pd.DataFrame) -> float:
        if aligned.empty:
            return 0.0
        ordered = aligned.sort_values("factor")
        bucket_size = max(1, int(len(ordered) * self.decile_fraction))
        bottom = ordered.head(bucket_size)["forward_return"].mean()
        top = ordered.tail(bucket_size)["forward_return"].mean()
        if np.isnan(top) or np.isnan(bottom):
            return 0.0
        return float(top - bottom)
