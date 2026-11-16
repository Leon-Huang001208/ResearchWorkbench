"""Run research-only exit comparisons on an imported, frozen daily sample."""

import math
from collections.abc import Iterable, Mapping
from pathlib import Path

from core.observability import get_logger

from .analysis import TradingDayBootstrap, evaluate_rule, event_rows
from .market import load_panel
from .rules import prepare_sample

log = get_logger(__name__)

MA_WINDOWS = {"sma5_close": 5, "sma10_close": 10, "sma20_close": 20}
RULE_IDS = ("volume_stall", *MA_WINDOWS)
DEFAULTS = {
    "rules": RULE_IDS,
    "horizon": 5,
    "volume_ratio": 1.3,
    "high_window": 20,
    "near_high_pct": 2.0,
    "ma_previous_gap_pct": 3.0,
    "ma_close_gap_pct": 2.5,
    "sell_cost_bps": 10,
}


def _config(config: Mapping) -> dict:
    if config.keys() - DEFAULTS.keys():
        raise ValueError("Unknown strategy validation parameter")
    checked = {**DEFAULTS, **config}
    rules = checked["rules"]
    if (
        not isinstance(rules, (tuple, list))
        or not rules
        or not all(isinstance(rule, str) and rule in RULE_IDS for rule in rules)
        or len(set(rules)) != len(rules)
    ):
        raise ValueError("Select unique strategy validation rules")
    for name, allowed in (("horizon", (1, 5, 10)), ("high_window", (20, 60))):
        value = checked[name]
        if type(value) is not int or value not in allowed:
            raise ValueError(f"Unexpected {name} for strategy validation")
    for name, lower, upper in (
        ("volume_ratio", 1, 5),
        ("near_high_pct", 0.1, 20),
        ("ma_previous_gap_pct", 0.1, 20),
        ("ma_close_gap_pct", 0.1, 20),
    ):
        value = checked[name]
        if (
            type(value) not in (float, int)
            or not lower <= value <= upper
            or not math.isfinite(value)
        ):
            raise ValueError(f"Unexpected {name} for strategy validation")
    cost = checked["sell_cost_bps"]
    if type(cost) is not int or not 0 <= cost <= 100:
        raise ValueError("Unexpected sell_cost_bps for strategy validation")
    return checked


def run_validation(dataset_dir: Path, config: dict) -> tuple[dict, Iterable[dict]]:
    """Return one horizon's summary and event rows, with returns as decimal ratios."""
    checked = _config(config)
    dataset_dir = Path(dataset_dir)
    spec_path = dataset_dir / "data-spec.json"
    data_dir = dataset_dir if (dataset_dir / "source.json").exists() else dataset_dir / "data"
    horizon = checked["horizon"]
    rules = checked["rules"]
    windows = tuple(MA_WINDOWS[rule] for rule in rules if rule in MA_WINDOWS)
    try:
        panel, dates, coverage, spec = load_panel(
            data_dir, spec_path, windows, horizon, checked["sell_cost_bps"]
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        log.warning("strategy_validation_source_rejected", error_type=type(exc).__name__)
        raise ValueError("The frozen research dataset could not be verified") from exc

    matching = {
        "previous_gap_limit": checked["ma_previous_gap_pct"] / 100,
        "absolute_signal_day_gap_limit": checked["ma_close_gap_pct"] / 100,
        "scales": [0.015, 0.02, 0.10, 1.0, 0.015],
        "max_distance": 2.5,
    }
    summaries, event_batches = [], []
    bootstrap_by_trials = {}
    for rule_id in rules:
        if rule_id == "volume_stall":
            trials = spec["bootstrap_trials"]
            rule = {
                "type": "volume_stall",
                "overrides": {
                    "lookback": checked["high_window"],
                    "near": checked["near_high_pct"] / 100,
                    "volume_ratio": checked["volume_ratio"],
                },
            }
        else:
            trials = 12_000
            rule = {"type": "moving_average", "window": MA_WINDOWS[rule_id]}
        sample = prepare_sample(panel, rule, {"moving_average_matching": matching}, spec)
        if trials not in bootstrap_by_trials:
            bootstrap_by_trials[trials] = TradingDayBootstrap(
                dates, {**spec, "bootstrap_trials": trials}
            )
        summary, events = evaluate_rule(sample, rule_id, horizon, bootstrap_by_trials[trials])
        summaries.append(summary)
        event_batches.append(events)

    public_coverage = {
        key: coverage[key]
        for key in (
            "raw_rows",
            "usable_rows",
            "suspended_rows",
            "bad_return_rows",
            "missing_data_tickers",
            "missing_expected_rows",
            "source",
        )
    }
    public_coverage.update(
        ticker_count=len(coverage["per_stock"]),
        analysis_days=len(dates),
        first_market_session=str(dates[0]),
        last_market_session=str(dates[-1]),
        research_only=True,
    )
    return {"rules": summaries, "coverage": public_coverage}, event_rows(event_batches)
