"""Reproducible descriptive returns and pre-event matched controls."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date
from math import sqrt
from statistics import mean, median, pstdev
from types import SimpleNamespace

from .contracts import StudyError, number


def observed_calendar(rows):
    """Actual price dates for descriptive windows, never a verified calendar."""
    try:
        return SimpleNamespace(
            sessions=[SimpleNamespace(day=date.fromisoformat(row["day"])) for row in rows]
        )
    except (ValueError, KeyError, TypeError):
        raise StudyError("source_prices_invalid") from None


def independent_episodes(windows):
    """Connected overlapping intervals are a single statistical episode."""
    groups = []
    for window in sorted(windows, key=lambda w: (w["start"], w["end"])):
        if groups and window["start"] <= groups[-1]["end"]:
            groups[-1]["end"] = max(groups[-1]["end"], window["end"])
            groups[-1]["ids"].add(window["episode"])
        else:
            groups.append(
                {"start": window["start"], "end": window["end"], "ids": {window["episode"]}}
            )
    return [
        {
            "id": "|".join(sorted(group["ids"])),
            "start": group["start"],
            "end": group["end"],
            "year": int(group["start"][:4]),
        }
        for group in groups
    ]


def window_returns(windows, rows):
    prices = {r["day"]: r for r in rows}
    if len(prices) != len(rows):
        raise StudyError("duplicate_price_day")
    result = []
    for window in windows:
        start, end = prices.get(window["start"]), prices.get(window["end"])
        row = {**window, "return": None, "status": "missing_prices"}
        if (
            start
            and end
            and start.get(window["start_price"]) is not None
            and end.get(window["end_price"]) is not None
        ):
            a, b = number(start[window["start_price"]]), number(end[window["end_price"]])
            if a <= 0 or b <= 0:
                raise StudyError("price_invalid")
            row.update(
                {
                    "return": str(b / a - 1),
                    "status": "complete",
                    "start_value": str(a),
                    "end_value": str(b),
                    "formula": "end_value/start_value-1",
                }
            )
        result.append(row)
    return result


def summaries(rows):
    result = {}
    for rule in sorted({r["rule"] for r in rows}):
        subset = [r for r in rows if r["rule"] == rule]
        values = [float(r["return"]) for r in subset if r["return"] is not None]
        result[rule] = {
            "n": len(values),
            "missing": len(subset) - len(values),
            "mean": mean(values) if values else None,
            "median": median(values) if values else None,
            "down": sum(v < 0 for v in values),
            "up": sum(v > 0 for v in values),
        }
    return result


def matched_controls(windows, rows, *, prior_only=False, control_days=None, exclusion_windows=()):
    """Same-year ordinary windows, matched on *prior* 20-session trend/volatility.

    All registered event intervals are excluded. Selection never sees candidate
    future returns, and incomplete trailing history yields no control.
    """
    days = [r["day"] for r in rows]
    if days != sorted(set(days)):
        raise StudyError("price_calendar_mismatch")
    closes = [float(number(r["close"])) for r in rows]
    if any(v <= 0 for v in closes):
        raise StudyError("price_invalid")

    def features(i):
        if i < 20:
            return None
        returns = [closes[k] / closes[k - 1] - 1 for k in range(i - 19, i + 1)]
        return closes[i] / closes[i - 20] - 1, pstdev(returns)

    feature_rows = [features(i) for i in range(len(days))]
    years = defaultdict(list)
    for i, day in enumerate(days):
        years[day[:4]].append(i)
    always = [
        w
        for w in [*windows, *exclusion_windows]
        if w["rule"].startswith(("holiday_", "event_")) or w["rule"] == "reopening_gap"
    ]
    rule_intervals = defaultdict(list)
    for window in windows:
        rule_intervals[window["rule"]].append(window)
    occupied_cache = {}
    for rule, intervals in rule_intervals.items():
        occupied_cache[rule] = {
            i
            for w in intervals + always
            for i in range(bisect_left(days, w["start"]), bisect_right(days, w["end"]))
        }
    result = []
    for window in windows:
        first, last = bisect_left(days, window["start"]), bisect_left(days, window["end"])
        if (
            first >= len(days)
            or last >= len(days)
            or days[first] != window["start"]
            or days[last] != window["end"]
        ):
            result.append(
                {
                    "episode": window["episode"],
                    "rule": window["rule"],
                    "control_start": None,
                    "control_end": None,
                    "distance": None,
                    "control_return": None,
                    "status": "event_window_prices_missing",
                }
            )
            continue
        width = last - first
        target = feature_rows[first] if first < len(days) else None
        candidates = []
        # Calendar windows collectively cover every weekday. Excluding their
        # union would leave no ordinary days at all; exclude this hypothesis's
        # windows and actual event/holiday episodes instead.
        occupied = occupied_cache[window["rule"]]
        if target and width > 0:
            for i in years[window["start"][:4]]:
                candidate = feature_rows[i]
                if (
                    candidate is None
                    or i + width >= len(days)
                    or any(k in occupied for k in range(i + 1, i + width + 1))
                ):
                    continue
                if prior_only and days[i + width] >= window["start"]:
                    continue
                if control_days is not None and any(
                    day not in control_days for day in days[i : i + width + 1]
                ):
                    continue
                # Normalize only by pre-event scales; no future-return ranking.
                distance = sqrt(
                    sum(((a - b) / max(abs(a), 0.01)) ** 2 for a, b in zip(target, candidate))
                )
                candidates.append((distance, days[i], i))
        chosen = min(candidates) if candidates else None
        result.append(
            {
                "episode": window["episode"],
                "rule": window["rule"],
                "control_start": days[chosen[2]] if chosen else None,
                "control_end": days[chosen[2] + width] if chosen else None,
                "distance": chosen[0] if chosen else None,
                "control_return": (
                    closes[chosen[2] + width] / closes[chosen[2]] - 1 if chosen else None
                ),
                "control_start_value": closes[chosen[2]] if chosen else None,
                "control_end_value": closes[chosen[2] + width] if chosen else None,
                "pre_event_trend": target[0] if target else None,
                "pre_event_volatility": target[1] if target else None,
                "status": "matched" if chosen else "no_eligible_same_year_control",
            }
        )
    return result
