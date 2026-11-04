"""Independent index-event prediction tests, separate from tradable proxy returns."""

import hashlib
import json
from collections import defaultdict
from math import isfinite
from random import Random

from core.observability import get_logger

from .contracts import StudyError
from .events import FORECAST_PROTOCOL, forecast_window_gaps
from .research import matched_controls, window_returns
from .validation import BOOTSTRAP_REPETITIONS, BOOTSTRAP_SEED, holm, sample_gaps

log = get_logger(__name__)
PREDICTION_POLICY = "index-prediction-prior-matched-cluster-v1"


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def prepare_prediction(
    rows,
    windows,
    holdout_days,
    direction,
    *,
    exclusion_windows=(),
    calendar=None,
    events=(),
    deterministic_calendar=False,
):
    """Match without looking beyond the event's information cutoff.

    All outcome endpoints are in the sealed test partition. Controls must have
    finished before the event window and be in the same year; only prior
    twenty-session covariates select the control. No outcome chooses a match.
    """
    if type(direction) is not int or direction not in {-1, 1}:
        raise StudyError("prediction_direction_invalid")
    allowed = set(holdout_days)
    registered = [w for w in windows if w["start"] in allowed and w["end"] in allowed]
    eligible, ineligible = [], []
    for candidate in registered:
        gaps = forecast_window_gaps(
            calendar, candidate, events=events, deterministic_calendar=deterministic_calendar
        )
        if gaps:
            ineligible.append(
                {
                    "episode": candidate["episode"],
                    "rule": candidate["rule"],
                    "start": candidate["start"],
                    "reasons": gaps,
                }
            )
        else:
            eligible.append(candidate)
    returns = window_returns(eligible, rows)
    controls = matched_controls(
        eligible, rows, prior_only=True, control_days=allowed, exclusion_windows=exclusion_windows
    )
    pairs, missing = [], []
    for outcome, control in zip(returns, controls):
        if outcome["status"] != "complete" or control["status"] != "matched":
            missing.append(
                {
                    "episode": outcome["episode"],
                    "rule": outcome["rule"],
                    "start": outcome["start"],
                    "reason": (
                        outcome["status"] if outcome["status"] != "complete" else control["status"]
                    ),
                }
            )
            continue
        signed = direction * (float(outcome["return"]) - control["control_return"])
        if not isfinite(signed):
            raise StudyError("prediction_nonfinite_effect")
        pairs.append(
            {
                "episode": outcome["episode"],
                "rule": outcome["rule"],
                "start": outcome["start"],
                "end": outcome["end"],
                "control_start": control["control_start"],
                "control_end": control["control_end"],
                "event_return": outcome["return"],
                "control_return": control["control_return"],
                "signed_excess": signed,
                "match_distance": control["distance"],
                "pre_event_trend": control["pre_event_trend"],
                "pre_event_volatility": control["pre_event_volatility"],
            }
        )
    data_gaps = (
        sorted({reason for item in ineligible for reason in item["reasons"]})
        if registered and not eligible
        else []
    )
    return {
        "pairs": pairs,
        "missing": missing,
        "eligible_windows": len(registered),
        "forecast_eligible_windows": len(eligible),
        "ineligible_prediction_windows": ineligible,
        "data_gaps": data_gaps,
        "forecast_protocol": FORECAST_PROTOCOL,
        "direction": direction,
        "days": list(holdout_days),
    }


def cluster_pairs(candidates):
    """Shared event identity or overlapping outcomes/control windows move together.

    Strict interval overlap excludes a merely shared closing-price endpoint.
    The sweep joins transitive overlaps without a quadratic market-pair scan.
    """
    entries = [
        (key, i, pair)
        for key in sorted(candidates)
        for i, pair in enumerate(candidates[key].get("pairs", []))
    ]
    parent = list(range(len(entries)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i, j):
        a, b = root(i), root(j)
        if a != b:
            parent[max(a, b)] = min(a, b)

    episodes, intervals = {}, []
    for i, (_, _, pair) in enumerate(entries):
        episode = pair["episode"]
        if episode in episodes:
            join(i, episodes[episode])
        else:
            episodes[episode] = i
        intervals.extend(
            [(pair["start"], pair["end"], i), (pair["control_start"], pair["control_end"], i)]
        )
    previous, end = None, None
    for first, last, i in sorted(intervals):
        if previous is not None and first < end:
            join(previous, i)
            end = max(end, last)
        else:
            previous, end = i, last
    members = defaultdict(list)
    for i, (key, position, pair) in enumerate(entries):
        members[root(i)].append((key, position, pair))
    assignment, descriptions = {}, {}
    for group in members.values():
        identity = fingerprint(
            sorted(
                {
                    (p["episode"], p["start"], p["end"], p["control_start"], p["control_end"])
                    for _, _, p in group
                }
            )
        )
        descriptions[identity] = {
            "start": min(p["start"] for _, _, p in group),
            "end": max(p["end"] for _, _, p in group),
            "episodes": sorted({p["episode"] for _, _, p in group}),
        }
        for key, position, _ in group:
            assignment[key, position] = identity
    return assignment, descriptions


def validate_prediction_family(candidates, all_trial_ids):
    """Frozen-family, one-sided cluster-bootstrap test of signed index excess.

    Failed/unavailable registered overlay hypotheses remain in Holm's family.
    No proxy price, strategy Sharpe or execution fee is an input to this test.
    """
    if set(candidates) - set(all_trial_ids) or len(set(all_trial_ids)) != len(all_trial_ids):
        raise StudyError("prediction_family_invalid")
    assignment, descriptions = cluster_pairs(candidates)
    grouped, means, samples = {}, {}, {}
    for key in all_trial_ids:
        data = candidates.get(key, {"pairs": [], "days": []})
        values = defaultdict(list)
        for i, pair in enumerate(data.get("pairs", [])):
            value = pair["signed_excess"]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(value)
            ):
                raise StudyError("prediction_nonfinite_effect")
            values[assignment[key, i]].append(value)
        grouped[key] = {cluster: sum(effect) / len(effect) for cluster, effect in values.items()}
        means[key] = sum(grouped[key].values()) / len(grouped[key]) if grouped[key] else None
        samples[key] = []
    labels = sorted(descriptions)
    rng = Random(BOOTSTRAP_SEED)
    attempted = BOOTSTRAP_REPETITIONS if len(labels) >= 2 else 0
    if attempted:
        for _ in range(attempted):
            counts = defaultdict(int)
            for label in rng.choices(labels, k=len(labels)):
                counts[label] += 1
            for key, clusters in grouped.items():
                weight = sum(n for label, n in counts.items() if label in clusters)
                if weight:
                    samples[key].append(
                        sum(clusters[label] * n for label, n in counts.items() if label in clusters)
                        / weight
                    )
    pvalues, bounds = {}, {}
    for key in all_trial_ids:
        observed, draws = means[key], samples[key]
        if observed is None or observed <= 0 or not draws:
            pvalues[key], bounds[key] = None, None
        else:
            pvalues[key] = (1 + sum(value - observed >= observed for value in draws)) / (
                len(draws) + 1
            )
            bounds[key] = sorted(draws)[int(0.05 * (len(draws) - 1))]
    correction = holm(pvalues)
    output = {}
    for key in all_trial_ids:
        data = candidates.get(key, {})
        clusters = grouped[key]
        episodes = [
            {"id": cluster, "year": int(descriptions[cluster]["start"][:4])} for cluster in clusters
        ]
        reasons = list(data.get("data_gaps", []))
        if data.get("forecast_protocol") != FORECAST_PROTOCOL:
            reasons.append("prediction_forecast_protocol_missing")
        if reasons:
            status = "DATA_INELIGIBLE"
        else:
            reasons = sample_gaps(data.get("days", []), event=True, event_episodes=episodes)
            if reasons:
                status = "INSUFFICIENT_SAMPLE"
            else:
                if means[key] is None or means[key] <= 0:
                    reasons.append("directional_index_excess_not_positive")
                if bounds[key] is None or bounds[key] <= 0:
                    reasons.append("index_excess_lower_confidence_not_positive")
                if not correction[key]["rejected"]:
                    reasons.append("family_adjusted_index_excess_not_significant")
                status = "VALIDATION_FAILED" if reasons else "VALIDATED"
        output[key] = {
            "schema": "index-prediction-v1",
            "policy_version": PREDICTION_POLICY,
            "forecast_protocol": FORECAST_PROTOCOL,
            "status": status,
            "reasons": reasons,
            "matched_pairs": len(data.get("pairs", [])),
            "independent_clusters": len(clusters),
            "cluster_years": sorted({e["year"] for e in episodes}),
            "mean_signed_excess": means[key],
            "lower_95_one_sided": bounds[key],
            "holm": correction[key],
            "pairs_sha256": fingerprint(data.get("pairs", [])),
            "clusters_sha256": fingerprint(
                {cluster: descriptions[cluster] for cluster in sorted(clusters)}
            ),
            "bootstrap": {
                "repetitions": attempted,
                "required_repetitions": BOOTSTRAP_REPETITIONS,
                "valid_draws": len(samples[key]),
                "seed": BOOTSTRAP_SEED,
                "method": "prior_matched_synchronous_connected_cluster_bootstrap",
            },
            "missing_windows": data.get("missing", []),
            "ineligible_prediction_windows": data.get("ineligible_prediction_windows", []),
            "pairs": data.get("pairs", []),
        }
    log.info("event_index_prediction_family_evaluated", hypotheses=len(all_trial_ids))
    return output
