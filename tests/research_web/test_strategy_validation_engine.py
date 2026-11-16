"""Contracts for research-only signals, matched controls and executable exits."""

import json

import numpy as np
import pandas as pd
import pytest

from app.research_web.strategy_validation import engine
from app.research_web.strategy_validation.analysis import (
    TradingDayBootstrap,
    evaluate_rule,
    event_rows,
)
from app.research_web.strategy_validation.market import (
    add_moving_average_features,
    complete_future_rows,
    round_a_share_limit,
)
from app.research_web.strategy_validation.rules import (
    RuleSample,
    moving_average_break,
    volume_stall,
)


def test_volume_threshold_is_inclusive_and_day_return_cap_is_strict():
    panel = pd.DataFrame(
        {
            "base_valid": [True] * 4,
            "dist20": [0.01] * 4,
            "day_return": [0.0, 0.009, 0.01, 0.002],
            "ratio": [1.3, 1.29, 1.5, 1.4],
        }
    )
    spec = {
        "main": {
            "lookback": 20,
            "near": 0.02,
            "day_min": 0,
            "day_max": 0.01,
            "volume_ratio": 1.3,
            "control_min_ratio": 0,
        },
        "matching": {"scales": [0.01, 0.005, 0.1, 1], "max_euclidean_distance": 2.5},
    }
    sample = volume_stall(panel, spec)
    assert sample.trigger.tolist() == [True, False, False, True]
    assert sample.control.tolist() == [False, True, False, False]
    assert volume_stall(panel, spec, {"volume_ratio": 1.4}).trigger.tolist() == [
        False,
        False,
        False,
        True,
    ]


def test_close_break_starts_at_or_above_prior_average_and_waits_for_close():
    panel = pd.DataFrame(
        {
            "base_valid": [True] * 5,
            "ma5_valid": [True, True, True, True, False],
            "ma5_prior_gap": [0.0, -0.01, 0.02, 0.04, 0.0],
            "ma5_close_gap": [-0.01, -0.01, 0.0, -0.02, -0.01],
        }
    )
    matching = {
        "previous_gap_limit": 0.03,
        "absolute_signal_day_gap_limit": 0.025,
        "scales": [0.015, 0.02, 0.1, 1, 0.015],
        "max_distance": 2.5,
    }
    sample = moving_average_break(panel, {"window": 5}, matching)
    assert sample.trigger.tolist() == [True, False, False, True, False]
    assert sample.match_trigger.tolist() == [True, False, False, False, False]
    assert sample.control.tolist() == [False, False, True, False, False]


def test_controls_are_chosen_before_reading_future_and_remain_visible_when_outcome_missing():
    dates = pd.Index(["2024-01-02", "2024-01-03"])
    panel = pd.DataFrame(
        {
            "date": [dates[0], dates[0], dates[0], dates[1], dates[0], dates[1]],
            "ticker": [
                "sh.600000",
                "sh.600001",
                "sh.600002",
                "sh.600003",
                "sz.000001",
                "sz.000002",
            ],
            "exchange": ["sh", "sh", "sh", "sh", "sz", "sz"],
            "distance": [0.0, 0.1, 0.2, 0.0, 0.0, 0.0],
            "hold5": [-0.03, np.nan, -0.5, 0.01, -0.02, 0.0],
            "exit5_bps0": [0.03, np.nan, np.nan, np.nan, np.nan, 1e-13],
            "next_open_fill_assumed": [True, False, True, True, False, True],
        }
    )
    trigger = pd.Series([True, False, False, True, False, True])
    sample = RuleSample(panel, trigger, ~trigger, trigger, ["distance"], [1.0], 2.5)
    bootstrap = TradingDayBootstrap(
        dates, {"bootstrap_block_sessions": 1, "bootstrap_trials": 100, "bootstrap_seed": 17}
    )
    summary, events = evaluate_rule(sample, "volume_stall", 5, bootstrap)
    first, second, third = list(event_rows([events]))
    assert first["control_ticker"] == "sh.600001"
    assert first["control_return"] is None and first["match_distance"] == 0.1
    assert second["control_ticker"] is None and second["sell_advantage"] is None
    assert third["control_ticker"] is None
    assert summary["matched"] == {
        "n": 0,
        "trigger_mean": None,
        "control_mean": None,
        "mean": None,
        "ci95": [None, None],
    }
    assert summary["sale"]["events"] == 1 and summary["sale"]["n"] == 2
    assert summary["downside"]["events"] == 1 and summary["downside"]["n"] == 3
    json.dumps({"summary": summary, "row": first}, allow_nan=False)


def test_window_ends_do_not_reuse_last_trading_day_and_price_limit_rounds_to_fen():
    present = pd.Series([True, False, True, True, True])
    assert complete_future_rows(present, 2).tolist() == [False, False, True, False, False]
    assert round_a_share_limit(pd.Series([10.05, 13.55])).tolist() == [9.05, 12.2]
    features = pd.DataFrame(index=range(5))
    add_moving_average_features(
        features, pd.Series([10, 11, 12, 9, np.nan]), pd.Series(True, index=range(5)), (3,)
    )
    assert features.loc[3, "ma3_prior_gap"] == pytest.approx(12 / 11 - 1)
    assert features.loc[3, "ma3_close_gap"] == pytest.approx(9 / ((11 + 12 + 9) / 3) - 1)
    assert not features.loc[2, "ma3_valid"] and not features.loc[4, "ma3_valid"]


def test_rejects_configuration_outside_supported_research_contract(tmp_path):
    for config in (
        {"issuer": "open"},
        {"rules": []},
        {"rules": ["sma5_close", "sma5_close"]},
        {"horizon": True},
        {"sell_cost_bps": 2.5},
        {"volume_ratio": 6.0},
    ):
        with pytest.raises(ValueError, match=r"(?i)strategy validation"):
            engine.run_validation(tmp_path, config)
