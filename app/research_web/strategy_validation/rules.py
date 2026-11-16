"""Deterministic event definitions. Rules only see signal-date or lagged columns."""

from dataclasses import dataclass

import pandas as pd

BOUNDARY = 1e-12
MOMENTUM = "lagged_20day_return"
LIQUIDITY = "log_lagged_5day_amount"


@dataclass(frozen=True)
class RuleSample:
    panel: pd.DataFrame
    trigger: pd.Series
    control: pd.Series
    match_trigger: pd.Series
    features: list[str]
    scales: list[float]
    max_distance: float


def volume_stall(panel: pd.DataFrame, data_spec: dict, overrides=None) -> RuleSample:
    rule = {**data_spec["main"], **(overrides or {})}
    distance = f"dist{rule['lookback']}"
    price_stalled = panel["day_return"].ge(rule["day_min"] - BOUNDARY)
    price_stalled &= panel["day_return"].lt(rule["day_max"] - BOUNDARY)
    near_high = panel[distance].between(-1e-10, rule["near"] + 1e-10)
    eligible = panel["base_valid"] & price_stalled & near_high
    high_volume = panel["ratio"].ge(rule["volume_ratio"] - BOUNDARY)
    trigger = eligible & high_volume
    control = eligible & ~trigger & panel["ratio"].ge(rule["control_min_ratio"] - BOUNDARY)
    matching = data_spec["matching"]
    return RuleSample(
        panel,
        trigger,
        control,
        trigger,
        [distance, "day_return", MOMENTUM, LIQUIDITY],
        matching["scales"],
        matching["max_euclidean_distance"],
    )


def moving_average_break(panel: pd.DataFrame, rule: dict, matching: dict) -> RuleSample:
    window = int(rule["window"])
    prior_gap = f"ma{window}_prior_gap"
    close_gap = f"ma{window}_close_gap"
    valid = panel[f"ma{window}_valid"] & panel["base_valid"]
    approached_from_above = valid & panel[prior_gap].ge(-BOUNDARY)
    close_break = panel[close_gap].lt(-BOUNDARY)
    trigger = approached_from_above & close_break

    abs_gap = f"ma{window}_abs_close_gap"
    prepared = panel.assign(**{abs_gap: panel[close_gap].abs()})
    comparable = panel[prior_gap].le(matching["previous_gap_limit"] + BOUNDARY)
    comparable &= prepared[abs_gap].le(matching["absolute_signal_day_gap_limit"] + BOUNDARY)
    match_trigger = trigger & comparable
    control = approached_from_above & comparable & ~close_break
    return RuleSample(
        prepared,
        trigger,
        control,
        match_trigger,
        [prior_gap, "day_return", MOMENTUM, LIQUIDITY, abs_gap],
        matching["scales"],
        matching["max_distance"],
    )


def prepare_sample(panel: pd.DataFrame, rule: dict, config: dict, data_spec: dict) -> RuleSample:
    kind = rule["type"]
    if kind == "volume_stall":
        return volume_stall(panel, data_spec, rule.get("overrides"))
    if kind == "moving_average":
        return moving_average_break(panel, rule, config["moving_average_matching"])
    raise ValueError(f"Unknown rule type {kind!r}")
