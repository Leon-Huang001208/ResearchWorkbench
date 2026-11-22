"""Estimate matched forward returns and the value of selling an existing holding."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from core.observability import get_logger

log = get_logger(__name__)
FLAT_TOLERANCE = 1e-12


class TradingDayBootstrap:
    """Resample circular blocks of exchange sessions, retaining each date's events."""

    def __init__(self, dates: pd.Index, spec: Mapping):
        self.dates = dates
        n = len(dates)
        length = min(n, spec["bootstrap_block_sessions"])
        trials = spec["bootstrap_trials"]
        if n == 0 or length < 1 or trials < 1:
            raise ValueError("Bootstrap requires trading days, positive block size and trials")
        blocks = (n + length - 1) // length
        rng = np.random.default_rng(spec["bootstrap_seed"])
        starts = rng.integers(0, n, size=(trials, blocks))
        indices = ((starts[:, :, None] + np.arange(length)).reshape(trials, -1)[:, :n]) % n
        # Reuse the same calendar draws for every endpoint and its binary indicators.
        self.weights = np.array([np.bincount(row, minlength=n) for row in indices], dtype=float)

    def means(self, values: pd.Series) -> np.ndarray:
        clean = values.dropna()
        if clean.empty:
            return np.array([])
        if not np.isfinite(clean.to_numpy(dtype=float)).all():
            raise ValueError("Outcome contains a non-finite value")
        daily = clean.groupby(level=0).agg(["sum", "count"]).reindex(self.dates, fill_value=0)
        counts = self.weights @ daily["count"].to_numpy(dtype=float)
        totals = self.weights @ daily["sum"].to_numpy(dtype=float)
        observed = counts > 0
        return totals[observed] / counts[observed]


def _interval(draws: np.ndarray, level: float = 0.95) -> list:
    if draws.size == 0:
        return [None, None]
    alpha = (1.0 - level) / 2.0
    return np.quantile(draws, [alpha, 1.0 - alpha]).tolist()


def _rate(indicator: pd.Series, bootstrap: TradingDayBootstrap) -> dict:
    return {
        "n": int(indicator.size),
        "events": int(indicator.sum()),
        "rate": float(indicator.mean()) if indicator.size else None,
        "ci95": _interval(bootstrap.means(indicator)),
    }


def make_pairs(
    frame: pd.DataFrame,
    trigger: pd.Series,
    control: pd.Series,
    features: Sequence[str],
    scales: np.ndarray,
    max_distance: float,
) -> pd.DataFrame:
    """Pair on signal-date information, with reusable same-date exchange controls."""
    candidates = frame.loc[trigger | control]
    vectors = candidates[list(features)].to_numpy(dtype=float) / scales
    if not np.isfinite(vectors).all():
        raise ValueError("Matching features must be finite on eligible events")
    scaled = pd.DataFrame(vectors, index=candidates.index)
    pairs = []
    for _, group in candidates.groupby(["date", "exchange"], sort=False):
        case_index = group.index[trigger.loc[group.index]]
        control_index = group.index[control.loc[group.index]]
        if case_index.empty or control_index.empty:
            continue
        left = scaled.loc[case_index].to_numpy()
        right = scaled.loc[control_index].to_numpy()
        distances = np.sqrt(((left[:, None, :] - right[None, :, :]) ** 2).sum(axis=2))
        for row, nearest in enumerate(distances.argmin(axis=1)):
            distance = float(distances[row, nearest])
            if distance <= max_distance:
                pairs.append((case_index[row], control_index[nearest], distance))
    return pd.DataFrame(pairs, columns=["event_index", "control_index", "distance"])


def _pair_outcomes(frame: pd.DataFrame, pairs: pd.DataFrame, horizon: int) -> pd.DataFrame:
    hold = f"hold{horizon}"
    cases = frame.loc[pairs["event_index"], ["date", hold]].reset_index(drop=True)
    controls = frame.loc[pairs["control_index"], hold].to_numpy()
    observed = cases.rename(columns={hold: "trigger"}).assign(control=controls).dropna()
    observed["spread"] = observed["trigger"] - observed["control"]
    return observed.set_index("date")


def _mean(values: pd.Series):
    return float(values.mean()) if not values.empty else None


def _not_missing(value):
    return None if pd.isna(value) else value


def evaluate_rule(
    sample, rule_id: str, horizon: int, bootstrap: TradingDayBootstrap
) -> tuple[dict, pd.DataFrame]:
    """Freeze matches before inspecting any outcome and keep unmatched events."""
    frame = sample.panel
    trigger, control, treated = sample.trigger, sample.control, sample.match_trigger
    if (trigger & control).any() or (treated & ~trigger).any():
        raise ValueError("Strategy validation masks overlap or contain ineligible triggers")
    scales = np.asarray(sample.scales, dtype=float)
    pairs = make_pairs(frame, treated, control, sample.features, scales, sample.max_distance)
    hold = f"hold{horizon}"
    exit_diff = f"exit{horizon}_bps0"
    cases = frame.loc[trigger, ["date", "ticker", "next_open_fill_assumed", hold, exit_diff]]
    dated = cases.set_index("date")
    held = dated[hold].dropna()
    sold = dated[exit_diff].dropna()
    matched = _pair_outcomes(frame, pairs, horizon)
    control_outcomes = frame.loc[pairs["control_index"], ["ticker", hold]]
    links = pd.DataFrame(
        {
            "control_ticker": control_outcomes["ticker"].to_numpy(),
            "control_return": control_outcomes[hold].to_numpy(),
            "match_distance": pairs["distance"].to_numpy(),
        },
        index=pairs["event_index"],
    )
    events = cases.rename(
        columns={
            hold: "hold_return",
            exit_diff: "sell_advantage",
            "next_open_fill_assumed": "open_executable",
        }
    ).join(links)
    events.insert(0, "rule", rule_id)
    log.info(
        "strategy_validation_rule_evaluated",
        rule=rule_id,
        horizon=horizon,
        triggers=len(events),
        matched=len(matched),
        comparable_sales=len(sold),
    )
    return {
        "id": rule_id,
        "signal_count": len(events),
        "downside": _rate(held < -FLAT_TOLERANCE, bootstrap),
        "sale": {
            **_rate(sold > FLAT_TOLERANCE, bootstrap),
            "mean": _mean(sold),
            "ci_effect": _interval(bootstrap.means(sold)),
        },
        "matched": {
            "n": len(matched),
            "trigger_mean": _mean(matched["trigger"]),
            "control_mean": _mean(matched["control"]),
            "mean": _mean(matched["spread"]),
            "ci95": _interval(bootstrap.means(matched["spread"])),
        },
    }, events


def event_rows(batches):
    """Yield records independent of the calculation panel for bounded persistence."""
    for batch in batches:
        names = list(batch.columns)
        for row in batch.itertuples(index=False, name=None):
            yield {key: _not_missing(value) for key, value in zip(names, row, strict=True)}
