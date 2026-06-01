from datetime import date, datetime, timezone

import pandas as pd

from core.contracts.factors import FactorCategory, FactorDefinition, FactorValue
from signal_lab.factors.evaluation import FactorEvaluator
from signal_lab.factors.fusion import EventFactorFusion
from signal_lab.factors.matrix import FactorMatrixBuilder
from signal_lab.factors.models import RollingICWeightedModel


def test_factor_matrix_builder_pivots_point_in_time_values():
    definitions = [
        FactorDefinition(
            factor_id="momentum_20d",
            name="20日动量",
            category=FactorCategory.MOMENTUM,
            direction="positive",
        ),
        FactorDefinition(
            factor_id="crowding",
            name="拥挤度",
            category=FactorCategory.CROWDING,
            direction="negative",
        ),
    ]
    as_of = date(2026, 5, 28)
    values = [
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000001.SZ",
            as_of_date=as_of,
            value=0.12,
            available_at=datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="crowding",
            subject_id="000001.SZ",
            as_of_date=as_of,
            value=0.80,
            available_at=datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000002.SZ",
            as_of_date=as_of,
            value=0.05,
            available_at=datetime(2026, 5, 28, 15, 30, tzinfo=timezone.utc),
        ),
        FactorValue(
            factor_id="momentum_20d",
            subject_id="000001.SZ",
            as_of_date=date(2026, 5, 27),
            value=-0.20,
            available_at=datetime(2026, 5, 27, 15, 30, tzinfo=timezone.utc),
        ),
    ]

    matrix = FactorMatrixBuilder(definitions).build(values, as_of_date=as_of)

    assert list(matrix.index) == ["000001.SZ", "000002.SZ"]
    assert list(matrix.columns) == ["momentum_20d", "crowding"]
    assert matrix.loc["000001.SZ", "momentum_20d"] == 0.12
    assert pd.isna(matrix.loc["000002.SZ", "crowding"])


def test_factor_evaluator_computes_ic_rank_ic_and_decile_spread():
    subjects = [f"stock_{i:02d}" for i in range(10)]
    factor_matrix = pd.DataFrame(
        {"event_expectation_gap": list(range(10))},
        index=subjects,
    )
    forward_returns = pd.Series(
        [value / 100 for value in range(10)],
        index=subjects,
        name="fwd_excess_return_20d",
    )

    evaluation = FactorEvaluator(horizon_days=20).evaluate(
        factor_matrix,
        forward_returns,
    )[0]

    assert evaluation.factor_id == "event_expectation_gap"
    assert evaluation.sample_size == 10
    assert evaluation.coverage == 1.0
    assert evaluation.ic > 0.99
    assert evaluation.rank_ic > 0.99
    assert evaluation.decile_spread > 0


def test_rolling_ic_weighted_model_learns_dynamic_signed_weights_and_scores():
    evaluations = []
    for as_of in [date(2026, 5, 24), date(2026, 5, 25), date(2026, 5, 26)]:
        evaluations.extend(
            FactorEvaluator(horizon_days=20).evaluate(
                pd.DataFrame(
                    {
                        "event_expectation_gap": [0.1, 0.3, 0.7, 0.9],
                        "crowding": [0.9, 0.8, 0.2, 0.1],
                    },
                    index=["a", "b", "c", "d"],
                ),
                pd.Series([0.01, 0.02, 0.06, 0.08], index=["a", "b", "c", "d"]),
                as_of_date=as_of,
            )
        )

    model = RollingICWeightedModel(lookback_periods=3)
    weights = model.fit(evaluations)

    assert weights.weights["event_expectation_gap"] > 0
    assert weights.weights["crowding"] < 0
    assert round(sum(abs(value) for value in weights.weights.values()), 10) == 1.0

    result = model.score(
        pd.DataFrame(
            {
                "event_expectation_gap": [0.1, 0.9],
                "crowding": [0.9, 0.1],
            },
            index=["weak", "strong"],
        )
    )

    assert result.normalized_scores["strong"] > result.normalized_scores["weak"]
    assert "event_expectation_gap" in result.contributions["strong"]


def test_event_factor_fusion_combines_event_factor_timing_and_risk():
    fusion = EventFactorFusion()
    factor_scores = pd.Series({"weak": 0.20, "strong": 0.80})
    event_scores = pd.Series({"weak": 0.30, "strong": 0.90})
    risk_penalties = pd.DataFrame(
        {
            "crowding_blocker": {"weak": 0.10, "strong": 0.20},
            "skeptic_risk_score": {"weak": 0.20, "strong": 0.10},
            "alpha_decay_score": {"weak": 0.10, "strong": 0.10},
        }
    )

    fused = fusion.fuse(
        factor_scores=factor_scores,
        event_scores=event_scores,
        timing_readiness=pd.Series({"weak": 0.40, "strong": 0.75}),
        risk_penalties=risk_penalties,
    )

    assert fused.loc["strong", "final_alpha_score"] > fused.loc["weak", "final_alpha_score"]
    assert 0 <= fused.loc["strong", "final_alpha_score"] <= 1
    assert fused.loc["strong", "top_contributors"][0] in {
        "event_alpha_score",
        "factor_alpha_score",
        "timing_readiness",
    }
