"""Frozen chronological validation policy; failed trials stay in the test family."""

from collections import defaultdict
from datetime import date
from math import isfinite, sqrt
from random import Random

from .contracts import POLICY, StudyError

BOOTSTRAP_REPETITIONS = 10000
BOOTSTRAP_SEED = 20261104


def chronological_split(days, *, horizon=20):
    if days != sorted(set(days)) or horizon != 20:
        raise StudyError("split_contract_invalid")
    try:
        if any(date.fromisoformat(day).isoformat() != day for day in days):
            raise ValueError
    except (ValueError, TypeError):
        raise StudyError("split_contract_invalid") from None
    first, second = len(days) * 60 // 100, len(days) * 80 // 100
    return {
        "train": days[: max(0, first - horizon)],
        "validation": days[first : max(first, second - horizon)],
        "holdout": days[second:],
        "purged": days[max(0, first - horizon) : first]
        + days[max(first, second - horizon) : second],
        "policy": POLICY,
        "horizon": horizon,
    }


def holm(pvalues, alpha=0.05):
    if not pvalues:
        return {}
    entries = sorted((1.0 if p is None else float(p), key) for key, p in pvalues.items())
    if any(not 0 <= p <= 1 for p, _ in entries):
        raise StudyError("invalid_p_value")
    result, adjusted = {}, 0
    for i, (p, key) in enumerate(entries):
        adjusted = max(adjusted, min(1, (len(entries) - i) * p))
        result[key] = {"p_raw": p, "p_adjusted": adjusted, "rejected": adjusted < alpha}
    return result


def _sharpe(n, total, squares):
    if n < 2:
        return None
    avg = total / n
    variance = max(0.0, squares / n - avg * avg)
    return avg / sqrt(variance) * sqrt(252) if variance > 1e-20 else None


def bootstrap_family(candidates, *, episode_keys=None):
    """Paired centred block bootstrap with synchronous draws across the family.

    candidates maps trial id to {days, strategy, comparator}. Each strategy and
    comparator contains equally timed net daily returns. A common union session
    axis supplies twenty-session blocks; episode keys override the block key so
    all markets/windows of one independent event move together.
    """
    union = sorted({day for c in candidates.values() for day in c["days"]})
    shared = {day: f"sessions:{i // 20}" for i, day in enumerate(union)}
    if episode_keys:
        shared.update(episode_keys)
    blocks, totals = {}, {}
    for key, candidate in candidates.items():
        days, a, b = candidate["days"], candidate["strategy"], candidate["comparator"]
        if len(days) != len(a) or len(a) != len(b) or days != sorted(set(days)):
            raise StudyError("paired_bootstrap_alignment_invalid")
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not isfinite(v) for v in a + b
        ):
            raise StudyError("paired_bootstrap_nonfinite_return")
        grouped = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
        for day, first, second in zip(days, a, b):
            row = grouped[shared[day]]
            row[0] += 1
            row[1] += first
            row[2] += first * first
            row[3] += second
            row[4] += second * second
        blocks[key] = grouped
        sums = [sum(row[i] for row in grouped.values()) for i in range(5)]
        sa, sb = _sharpe(*sums[:3]), _sharpe(sums[0], sums[3], sums[4])
        totals[key] = sa - sb if sa is not None and sb is not None else None
    labels = sorted({label for grouped in blocks.values() for label in grouped})
    if len(labels) < 2:
        return {
            key: {"p_value": None, "difference": totals[key], "blocks": len(labels)}
            for key in candidates
        }
    exceed, valid = dict.fromkeys(candidates, 0), dict.fromkeys(candidates, 0)
    rng = Random(BOOTSTRAP_SEED)
    for _ in range(BOOTSTRAP_REPETITIONS):
        counts = defaultdict(int)
        for label in rng.choices(labels, k=len(labels)):
            counts[label] += 1
        for key, grouped in blocks.items():
            observed = totals[key]
            if observed is None or observed <= 0:
                continue
            sums = [
                sum(grouped[label][i] * n for label, n in counts.items() if label in grouped)
                for i in range(5)
            ]
            sa, sb = _sharpe(*sums[:3]), _sharpe(sums[0], sums[3], sums[4])
            if sa is not None and sb is not None:
                valid[key] += 1
                exceed[key] += sa - sb - observed >= observed
    return {
        key: {
            "p_value": (exceed[key] + 1) / (valid[key] + 1) if valid[key] else None,
            "difference": totals[key],
            "blocks": len(blocks[key]),
            "repetitions": BOOTSTRAP_REPETITIONS,
            "seed": BOOTSTRAP_SEED,
            "method": "paired_centred_synchronous_block_bootstrap",
        }
        for key in candidates
    }


def sample_gaps(days, *, event_episodes=(), event=False):
    dates = [date.fromisoformat(day) for day in days]
    years = sorted({day.year for day in dates})
    full_years = [
        year
        for year in years
        if min(d for d in dates if d.year == year) <= date(year, 1, 7)
        and max(d for d in dates if d.year == year) >= date(year, 12, 24)
    ]
    reasons = []
    if len(full_years) < 3 or len(days) // 20 < 30:
        reasons.append("holdout_requires_three_full_years_and_thirty_blocks")
    if event:
        episodes = {(e["id"], e["year"]) for e in event_episodes}
        if len({e[0] for e in episodes}) < 20 or len({e[1] for e in episodes}) < 5:
            reasons.append("event_holdout_requires_twenty_independent_episodes_across_five_years")
    return reasons


def assess(trials):
    """Pure final gate; caller supplies host-reconstructed, frozen test results."""
    pvalues = {key: value.get("bootstrap", {}).get("p_value") for key, value in trials.items()}
    correction = holm(pvalues)
    results = {}
    for key, trial in trials.items():
        reasons = list(trial.get("data_gaps", []))
        if reasons:
            status = "DATA_INELIGIBLE"
        else:
            reasons = sample_gaps(
                trial["days"],
                event_episodes=trial.get("event_episodes", []),
                event=trial.get("event", False),
            )
            if reasons:
                status = "INSUFFICIENT_SAMPLE"
            else:
                for cost in ("normal", "stress"):
                    first, second = trial[cost]["strategy"], trial[cost]["comparator"]
                    if (
                        first["sharpe"] is None
                        or second["sharpe"] is None
                        or first["sharpe"] <= second["sharpe"]
                    ):
                        reasons.append(f"{cost}_sharpe_not_improved")
                    if first["cagr"] < second["cagr"]:
                        reasons.append(f"{cost}_net_return_worse")
                    if first["max_drawdown"] > second["max_drawdown"]:
                        reasons.append(f"{cost}_drawdown_worse")
                if not correction[key]["rejected"]:
                    reasons.append("family_adjusted_sharpe_not_significant")
                status = "VALIDATION_FAILED" if reasons else "VALIDATED"
        results[key] = {
            "status": status,
            "reasons": reasons,
            "policy_version": POLICY,
            "holm": correction[key],
            "bootstrap": trial.get("bootstrap", {}),
        }
    return results
