"""Dynamic factor visualization payload service.

The first UI slice is intentionally read-only and deterministic. It uses the
dynamic factor MVP components to generate an auditable demo payload until a
durable Factor Store and production factor data are available.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from core.contracts.factors import FactorCategory, FactorDefinition, FactorEvaluation, FactorValue
from core.observability import get_logger
from signal_lab.factors.evaluation import FactorEvaluator
from signal_lab.factors.fusion import EventFactorFusion
from signal_lab.factors.matrix import FactorMatrixBuilder
from signal_lab.factors.models import RollingICWeightedModel

logger = get_logger(__name__)


class DynamicFactorVisualizationService:
    """Build Signal Lab visualization payloads for dynamic factor alpha."""

    def build_overview(self) -> dict[str, Any]:
        """Return a complete alpha-control-room payload for the WebUI."""
        as_of_date = date.today()
        definitions = self._factor_definitions()
        values = self._factor_values(as_of_date)
        matrix = FactorMatrixBuilder(definitions).build(values, as_of_date=as_of_date)
        forward_returns = self._sample_forward_returns(matrix.index)
        evaluations = FactorEvaluator(horizon_days=20).evaluate(
            matrix,
            forward_returns,
            as_of_date=as_of_date,
        )

        historical_evaluations = self._historical_evaluations(matrix, forward_returns, as_of_date)
        dynamic_model = RollingICWeightedModel(lookback_periods=5)
        dynamic_weights = dynamic_model.fit(historical_evaluations, as_of_date=as_of_date)
        score_result = dynamic_model.score(matrix)

        event_scores = self._event_scores(matrix)
        timing_readiness = self._timing_readiness(matrix.index)
        risk_penalties = self._risk_penalties(matrix)
        fusion = EventFactorFusion().fuse(
            factor_scores=pd.Series(score_result.normalized_scores),
            event_scores=event_scores,
            timing_readiness=timing_readiness,
            risk_penalties=risk_penalties,
        )

        payload = {
            "success": True,
            "data_mode": "demo",
            "as_of_date": as_of_date.isoformat(),
            "note": "当前为动态多因子 MVP 可视化样例；接入 Factor Store 后替换为真实点时数据。",
            "closed_loop_steps": self._closed_loop_steps(),
            "factor_definitions": [
                definition.model_dump(mode="json") for definition in definitions
            ],
            "factor_matrix": self._matrix_payload(matrix, as_of_date),
            "evaluations": [self._evaluation_payload(item) for item in evaluations],
            "dynamic_weights": {
                "as_of_date": as_of_date.isoformat(),
                "metric": dynamic_weights.metric,
                "lookback_periods": dynamic_weights.lookback_periods,
                "weights": dynamic_weights.weights,
                "raw_scores": dynamic_weights.raw_scores,
                "absolute_weight_sum": dynamic_weights.absolute_weight_sum(),
            },
            "factor_scores": self._score_payload(
                score_result.raw_scores, score_result.normalized_scores
            ),
            "factor_contributions": score_result.contributions,
            "fusion_results": self._fusion_payload(fusion),
        }
        logger.info(
            "dynamic factor visualization overview built",
            subject_count=len(matrix.index),
            factor_count=len(matrix.columns),
        )
        return payload

    @staticmethod
    def _factor_definitions() -> list[FactorDefinition]:
        return [
            FactorDefinition(
                factor_id="event_expectation_gap",
                name="事件预期差",
                category=FactorCategory.EVENT,
                direction="positive",
                description="市场预期与事件推理之间的差距",
                horizon_days=20,
            ),
            FactorDefinition(
                factor_id="momentum_20d",
                name="20日动量",
                category=FactorCategory.MOMENTUM,
                direction="positive",
                description="近 20 个交易日相对强度",
                horizon_days=20,
            ),
            FactorDefinition(
                factor_id="quality_roe",
                name="ROE质量",
                category=FactorCategory.QUALITY,
                direction="positive",
                description="盈利质量代理因子",
                horizon_days=20,
            ),
            FactorDefinition(
                factor_id="crowding",
                name="拥挤度",
                category=FactorCategory.CROWDING,
                direction="negative",
                description="交易和叙事拥挤风险",
                horizon_days=20,
            ),
        ]

    @staticmethod
    def _factor_values(as_of_date: date) -> list[FactorValue]:
        available_at = datetime.combine(as_of_date, datetime.min.time()).replace(
            hour=15,
            minute=30,
            tzinfo=timezone.utc,
        )
        sample = {
            "AI光模块龙头": {
                "event_expectation_gap": 0.92,
                "momentum_20d": 0.74,
                "quality_roe": 0.66,
                "crowding": 0.58,
            },
            "液冷设备公司": {
                "event_expectation_gap": 0.76,
                "momentum_20d": 0.42,
                "quality_roe": 0.61,
                "crowding": 0.32,
            },
            "铜连接补涨股": {
                "event_expectation_gap": 0.68,
                "momentum_20d": 0.51,
                "quality_roe": 0.48,
                "crowding": 0.24,
            },
            "高位拥挤概念股": {
                "event_expectation_gap": 0.81,
                "momentum_20d": 0.88,
                "quality_roe": 0.40,
                "crowding": 0.91,
            },
            "低相关稳健标的": {
                "event_expectation_gap": 0.36,
                "momentum_20d": 0.28,
                "quality_roe": 0.72,
                "crowding": 0.18,
            },
        }

        values: list[FactorValue] = []
        for subject_id, factor_values in sample.items():
            for factor_id, value in factor_values.items():
                values.append(
                    FactorValue(
                        factor_id=factor_id,
                        subject_id=subject_id,
                        as_of_date=as_of_date,
                        value=value,
                        available_at=available_at,
                        source="dynamic_factor_visualization_demo",
                    )
                )
        return values

    @staticmethod
    def _sample_forward_returns(index: pd.Index) -> pd.Series:
        returns = {
            "AI光模块龙头": 0.082,
            "液冷设备公司": 0.057,
            "铜连接补涨股": 0.044,
            "高位拥挤概念股": 0.012,
            "低相关稳健标的": 0.018,
        }
        return pd.Series({subject: returns.get(str(subject), 0.0) for subject in index})

    def _historical_evaluations(
        self,
        matrix: pd.DataFrame,
        forward_returns: pd.Series,
        as_of_date: date,
    ) -> list[FactorEvaluation]:
        evaluations: list[FactorEvaluation] = []
        evaluator = FactorEvaluator(horizon_days=20)
        for offset in range(5):
            shifted_returns = forward_returns * (1.0 - offset * 0.04)
            shifted_returns.loc["高位拥挤概念股"] -= 0.01 * offset
            evaluations.extend(
                evaluator.evaluate(
                    matrix,
                    shifted_returns,
                    as_of_date=as_of_date - timedelta(days=offset + 1),
                )
            )
        return evaluations

    @staticmethod
    def _event_scores(matrix: pd.DataFrame) -> pd.Series:
        return matrix["event_expectation_gap"].rank(method="average", pct=True)

    @staticmethod
    def _timing_readiness(index: pd.Index) -> pd.Series:
        return (
            pd.Series(
                {
                    "AI光模块龙头": 0.68,
                    "液冷设备公司": 0.73,
                    "铜连接补涨股": 0.71,
                    "高位拥挤概念股": 0.48,
                    "低相关稳健标的": 0.55,
                }
            )
            .reindex(index)
            .fillna(0.5)
        )

    @staticmethod
    def _risk_penalties(matrix: pd.DataFrame) -> pd.DataFrame:
        crowding = matrix["crowding"].clip(0.0, 1.0)
        skeptic = (1.0 - matrix["quality_roe"]).clip(0.0, 1.0) * 0.55
        alpha_decay = (matrix["momentum_20d"] * matrix["crowding"]).clip(0.0, 1.0)
        return pd.DataFrame(
            {
                "crowding_blocker": crowding,
                "skeptic_risk_score": skeptic,
                "alpha_decay_score": alpha_decay,
            },
            index=matrix.index,
        )

    @staticmethod
    def _closed_loop_steps() -> list[dict[str, Any]]:
        return [
            {"step": "Event", "label": "事件信号", "status": "ready", "metric": "5 subjects"},
            {"step": "Factor", "label": "动态因子", "status": "ready", "metric": "4 factors"},
            {"step": "Validation", "label": "IC/RankIC", "status": "ready", "metric": "20d"},
            {"step": "Timing", "label": "择时门控", "status": "ready", "metric": "readiness"},
            {"step": "Fusion", "label": "Alpha融合", "status": "ready", "metric": "final score"},
            {"step": "Portfolio", "label": "组合输入", "status": "next", "metric": "待接入"},
            {"step": "Outcome", "label": "结果记忆", "status": "next", "metric": "待接入"},
        ]

    @staticmethod
    def _matrix_payload(matrix: pd.DataFrame, as_of_date: date) -> dict[str, Any]:
        return {
            "as_of_date": as_of_date.isoformat(),
            "subjects": [str(item) for item in matrix.index],
            "factors": [str(item) for item in matrix.columns],
            "rows": [
                {
                    "subject_id": str(subject_id),
                    **{
                        str(factor_id): None if pd.isna(value) else float(value)
                        for factor_id, value in row.items()
                    },
                }
                for subject_id, row in matrix.iterrows()
            ],
        }

    @staticmethod
    def _evaluation_payload(evaluation: FactorEvaluation) -> dict[str, Any]:
        payload = evaluation.model_dump(mode="json")
        for key in ["ic", "rank_ic", "decile_spread", "coverage"]:
            payload[key] = round(float(payload[key]), 6)
        return payload

    @staticmethod
    def _score_payload(
        raw_scores: dict[str, float],
        normalized_scores: dict[str, float],
    ) -> list[dict[str, Any]]:
        return [
            {
                "subject_id": subject_id,
                "raw_score": round(float(raw_scores.get(subject_id, 0.0)), 6),
                "normalized_score": round(float(normalized_score), 6),
            }
            for subject_id, normalized_score in sorted(
                normalized_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

    @staticmethod
    def _fusion_payload(fusion: pd.DataFrame) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for subject_id, row in fusion.iterrows():
            rows.append(
                {
                    "subject_id": str(subject_id),
                    "factor_alpha_score": round(float(row["factor_alpha_score"]), 6),
                    "event_alpha_score": round(float(row["event_alpha_score"]), 6),
                    "timing_readiness": round(float(row["timing_readiness"]), 6),
                    "risk_penalty": round(float(row["risk_penalty"]), 6),
                    "final_alpha_score": round(float(row["final_alpha_score"]), 6),
                    "top_contributors": list(row["top_contributors"]),
                }
            )
        return rows
