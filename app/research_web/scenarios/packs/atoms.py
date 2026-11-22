"""Owned, public deterministic arithmetic; none of the 18 gated algorithms."""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import defaultdict

from .contracts import DerivedBudget, day, instant, number, require, security


def validate_positions(records, p, cutoff):
    expected = [security(s) for s in p["expected_universe"]]
    expected_set = set(expected)
    require(len(set(expected)) == len(expected), "duplicate_universe")
    target = number(p["target_weight"])
    require(target >= 0, "negative_weight")
    seen, rows, weights = set(), [], []
    unweighted = 0
    for r in records.get("position", []):
        key = security(r["security"])
        require(key in expected_set, "universe_mismatch")
        require(key not in seen, "duplicate_position")
        seen.add(key)
        require(instant(r["snapshot_at"]) <= cutoff, "future_data")
        w = r["weight"]
        if w is None:
            unweighted += 1
        else:
            w = number(w) / (100 if r["weight_unit"] == "percent" else 1)
            require(w >= 0, "negative_weight")
            weights.append(w)
        rows.append({"row_id": r["row_id"], "security": r["security"], "weight": w})
    known = number(math.fsum(weights))
    require(known <= target + 1e-12, "weight_exceeds_target")
    unknown = max(0, number(target - known))
    missing = [{"code": "missing_position", "security": list(s)} for s in expected if s not in seen]
    if unknown > 1e-12:
        missing.append({"code": "unexplained_weight"})
    if unweighted:
        missing.append({"code": "unweighted_position"})
    return (
        rows,
        {
            "known_weight": known,
            "unknown_weight": unknown,
            "unweighted_count": unweighted,
            "expected_count": len(expected),
            "observed_count": len(seen),
        },
        missing,
        [],
        [],
    )


def join_risk_windows(records, p, cutoff):
    positions = [security(s) for s in p["positions"]]
    require(len(set(positions)) == len(positions), "duplicate_position")
    start, end = day(p["window_start"]), day(p["window_end"])
    require(start <= end, "window_invalid")
    coverage = p["category_coverage"]
    require(isinstance(coverage, list), "coverage_scope_required")
    categories = ("risk", "unlock", "insider")
    scopes = set()
    for c in coverage:
        require(
            isinstance(c, dict)
            and set(c)
            == {"security", "category", "window_start", "window_end", "source_ref", "exhaustive"},
            "coverage_scope_invalid",
        )
        require(
            c["category"] in categories and isinstance(c["exhaustive"], bool),
            "coverage_scope_invalid",
        )
        require(
            isinstance(c["source_ref"], str) and 0 < len(c["source_ref"]) <= 4096,
            "coverage_scope_invalid",
        )
        a, b = day(c["window_start"]), day(c["window_end"])
        require(a <= b, "coverage_scope_invalid")
        if c["exhaustive"] and a <= start and b >= end:
            scopes.add((security(c["security"]), c["category"]))
    events, joins = {}, defaultdict(list)
    for r in records.get("risk-event", []):
        key = (security(r["security"]), r["category"], r["event_id"])
        require(instant(r["announced_at"]) <= cutoff, "future_data")
        signature = (r["announced_at"], r["effective_date"])
        require(key not in events or events[key] == signature, "conflicting_event")
        if key in events:
            continue
        events[key] = signature
        if start <= day(r["effective_date"]) <= end:
            joins[key[:2]].append(
                {
                    "row_id": r["row_id"],
                    "event_id": r["event_id"],
                    "effective_date": r["effective_date"],
                    "planned": day(r["effective_date"]) > cutoff.date(),
                }
            )
    missing, rows = [], []
    for s in positions:
        for category in categories:
            covered = (s, category) in scopes
            hits = joins.get((s, category), [])
            if not covered:
                missing.append(
                    {"code": "coverage_unknown", "security": list(s), "category": category}
                )
            rows.append(
                {
                    "security": list(s),
                    "category": category,
                    "events": hits,
                    "observation": (
                        "observed_matches"
                        if hits
                        else ("observed_no_match" if covered else "unknown")
                    ),
                }
            )
    return (
        rows,
        {
            "joined_events": sum(len(x["events"]) for x in rows),
            "unmatched_events": sum(1 for s, _, _ in events if s not in positions),
            "coverage_is_declaration": True,
        },
        missing,
        [],
        ["observed_no_match_is_not_no_risk"],
    )


def deduplicate_source_versions(records, p, cutoff):
    groups, versions, missing, lags = {}, {}, [], []
    rows = records.get("source-version", [])
    for r in rows:
        require(r["version_id"] not in versions, "duplicate_version")
        versions[r["version_id"]] = r
        t = r["origin"]["published_at"]
        if r["source_role"] == "unknown":
            missing.append({"code": "source_role_unknown", "row_id": r["row_id"]})
        if r["event_at"] is not None:
            require(instant(r["event_at"]) <= cutoff, "future_data")
        if t is None or not r["full_text_available"]:
            missing.append(
                {
                    "code": "publication_unknown" if t is None else "full_text_missing",
                    "row_id": r["row_id"],
                }
            )
        groups.setdefault(r["content_sha256"], []).append(r)
    for r in rows:
        parent = r["parent_version_id"]
        if parent is not None:
            if parent not in versions:
                missing.append({"code": "parent_missing", "row_id": r["row_id"]})
                continue
            original = versions[parent]
            a, b = original["origin"]["published_at"], r["origin"]["published_at"]
            if r["source_role"] == "reprint" and original["source_role"] == "original" and a and b:
                lag = number((instant(b) - instant(a)).total_seconds())
                require(lag >= 0, "negative_reprint_lag")
                lags.append(
                    {"version_id": r["version_id"], "parent_version_id": parent, "lag_seconds": lag}
                )
    if not rows:
        missing.append({"code": "original_materials_missing"})
    output = []
    for digest, members in groups.items():
        members = sorted(
            members,
            key=lambda r: (
                r["origin"]["published_at"] is None,
                instant(r["origin"]["published_at"]) if r["origin"]["published_at"] else cutoff,
                r["row_id"],
            ),
        )
        output.append(
            {
                "content_sha256": digest,
                "versions": [
                    {
                        "row_id": r["row_id"],
                        "version_id": r["version_id"],
                        "url_ref": r["url_ref"],
                        "language": r["language"],
                        "region": r["region"],
                        "source_role": r["source_role"],
                        "published_at": (
                            instant(r["origin"]["published_at"]).isoformat()
                            if r["origin"]["published_at"]
                            else None
                        ),
                    }
                    for r in members
                ],
            }
        )
    return (
        output,
        {
            "version_groups": len(groups),
            "versions": len(rows),
            "reprint_lags": lags,
            "timeline_row_ids": [
                r["row_id"]
                for r in sorted(
                    rows,
                    key=lambda r: (
                        r["origin"]["published_at"] is None,
                        (
                            instant(r["origin"]["published_at"])
                            if r["origin"]["published_at"]
                            else cutoff
                        ),
                        r["row_id"],
                    ),
                )
            ],
        },
        missing,
        [],
        ["byte_hash_dedupe_only", "questions_and_sentiment_NOT_RUN"],
    )


def financial_key(r):
    return security(r["security"]) + tuple(
        r[k] for k in ("report_period", "basis", "metric", "attribution", "currency", "unit")
    )


def compare_qualified_expectations(records, p, cutoff):
    forecasts, rejected, missing, rows = defaultdict(list), [], [], []
    batch = defaultdict(int)
    for values in records.values():
        for record in values:
            batch[security(record["security"])] += 1
    require(len(batch) <= 50, "workload_too_large")
    require(
        all(n <= (5000 if len(batch) == 1 else 1000) for n in batch.values()), "workload_too_large"
    )
    vintage_values, earliest_series, all_vintages = {}, defaultdict(dict), defaultdict(list)
    for f in records.get("forecast", []):
        vintage = instant(f["vintage_at"])
        require(vintage <= cutoff, "future_data")
        key = financial_key(f)
        vintage_key = (key, f["consensus_id"], vintage)
        require(
            vintage_key not in vintage_values or vintage_values[vintage_key] == f["value"],
            "ambiguous_consensus",
        )
        vintage_values[vintage_key] = f["value"]
        earliest = earliest_series[key].get(f["consensus_id"])
        earliest_series[key][f["consensus_id"]] = min(earliest, vintage) if earliest else vintage
        all_vintages[key].append(vintage)
        forecasts[key].append(f)
    earliest_sorted = {key: sorted(series.values()) for key, series in earliest_series.items()}
    for vintages in all_vintages.values():
        vintages.sort()
    actuals = records.get("actual", []) + records.get("guidance", [])
    budget, seen, derived_count = DerivedBudget(), set(), 0
    # Count qualified series and late-forecast rejections without allocating their
    # Cartesian products. This remains bounded by the number of accepted inputs.
    for r in actuals:
        disclosed = instant(r["disclosed_at"])
        require(disclosed <= cutoff, "future_data")
        require(r["origin"]["published_at"] is not None, "disclosure_time_unknown")
        key = financial_key(r)
        require((key, disclosed) not in seen, "duplicate_actual")
        seen.add((key, disclosed))
        lo, hi = (r["value"], r["value"]) if r["kind"] == "actual" else (r["lower"], r["upper"])
        require(lo <= hi, "guidance_range_invalid")
        candidates_count = bisect_left(earliest_sorted.get(key, []), disclosed)
        vintages = all_vintages.get(key, [])
        late_count = len(vintages) - bisect_left(vintages, disclosed)
        derived_count += max(1, candidates_count) + late_count
        budget.preflight(derived_count)
    for r in actuals:
        disclosed = instant(r["disclosed_at"])
        key = financial_key(r)
        lo, hi = (r["value"], r["value"]) if r["kind"] == "actual" else (r["lower"], r["upper"])
        candidates = defaultdict(list)
        for f in forecasts[key]:
            if instant(f["vintage_at"]) < disclosed:
                candidates[f["consensus_id"]].append(f)
            else:
                budget.append(
                    rejected, {"row_id": f["row_id"], "code": "vintage_not_before_disclosure"}
                )
        if not candidates:
            budget.append(missing, {"code": "qualified_consensus_missing", "row_id": r["row_id"]})
        for series, fs in candidates.items():
            latest = max(instant(f["vintage_at"]) for f in fs)
            selected = [f for f in fs if instant(f["vintage_at"]) == latest]
            consensus = number(selected[0]["value"])
            low, high = number(lo - consensus), number(hi - consensus)
            budget.append(
                rows,
                {
                    "row_id": r["row_id"],
                    "forecast_row_ids": [f["row_id"] for f in selected],
                    "consensus_id": series,
                    "consensus": consensus,
                    "absolute_low": low,
                    "absolute_high": high,
                    "relative_low": number(low / consensus) if consensus > 0 else None,
                    "relative_high": number(high / consensus) if consensus > 0 else None,
                    "relative_limitation": None if consensus > 0 else "nonpositive_consensus",
                },
            )
    if not actuals:
        budget.append(missing, {"code": "actual_or_guidance_missing"})
    return rows, {"comparisons": len(rows)}, missing, rejected, ["no_surprise_score"]


def compare_valuation_samples(records, p, cutoff):
    samples = records.get("valuation", [])
    require(len(samples) <= 5000, "workload_too_large")
    current = [r for r in samples if r["row_id"] == p["current_row_id"]]
    require(len(current) == 1, "current_sample_missing")
    current = current[0]
    require(current["value"] > 0, "nonpositive_current_pe")
    current_time = instant(current["observation_at"])
    require(current_time <= cutoff, "future_data")
    require(current["basis"] != "forward", "forward_vintage_required")
    minimum = p["minimum_samples"]
    require(
        isinstance(minimum, int) and not isinstance(minimum, bool) and minimum >= 1,
        "minimum_samples_invalid",
    )
    start, end = instant(p["window_start"]), instant(p["window_end"])
    require(start <= end < current_time, "window_invalid")
    key = lambda r: security(r["security"]) + tuple(
        r[k] for k in ("metric", "basis", "currency", "unit")
    )
    values, dates, rejected = [], {}, []
    for r in samples:
        require(key(r) == key(current), "valuation_basis_mismatch")
        t = instant(r["observation_at"])
        require(t <= cutoff, "future_data")
        if r is current:
            continue
        require(t < current_time, "historical_sample_not_prior")
        if t in dates:
            require(dates[t] == r["value"], "conflicting_sample_date")
            rejected.append({"row_id": r["row_id"], "code": "duplicate_sample_date"})
            continue
        dates[t] = r["value"]
        if not start <= t <= end or r["value"] <= 0:
            rejected.append({"row_id": r["row_id"], "code": "nonpositive_or_outside_window"})
        else:
            values.append(r["value"])
    n = len(values)
    interval = (
        [
            sum(v < current["value"] for v in values) / n,
            sum(v <= current["value"] for v in values) / n,
        ]
        if n >= minimum
        else None
    )
    return (
        [],
        {
            "sample_count": n,
            "current": current["value"],
            "percentile_interval": interval,
            "tie_rule": "[count_less/n,count_less_or_equal/n]",
        },
        [] if interval else [{"code": "samples_insufficient"}],
        rejected,
        ["not_return_probability"],
    )


def align_event_trading_day(records, p, cutoff):
    release = instant(p["release_at"])
    require(release <= cutoff, "future_data")
    pre, post = p["pre_sessions"], p["post_sessions"]
    require(
        all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 5000 for x in (pre, post)),
        "session_window_invalid",
    )
    sessions = sorted(records.get("exchange-session", []), key=lambda r: instant(r["open_at"]))
    require(len(sessions) <= 5000, "workload_too_large")
    seen, last, markets = set(), None, set()
    for r in sessions:
        a, b = instant(r["open_at"]), instant(r["close_at"])
        require(a < b and (last is None or a > last), "session_overlap")
        require(r["session_date"] not in seen, "duplicate_session")
        seen.add(r["session_date"])
        day(r["session_date"])
        markets.add(r["market"])
        last = b
    require(len(markets) <= 1, "calendar_market_mismatch")
    index = next((i for i, r in enumerate(sessions) if instant(r["close_at"]) > release), None)
    if index is None:
        return (
            [],
            {"event_date": None, "return_algorithm": "comparison_receipt_required"},
            [{"code": "calendar_insufficient"}],
            [],
            ["alignment_only"],
        )
    missing, output = [], []
    if index < pre:
        missing.append({"code": "pre_sessions_missing"})
    if index + post >= len(sessions):
        missing.append({"code": "post_sessions_missing"})
    session_lookup = {s["session_date"]: s for s in sessions}
    series = defaultdict(dict)
    identities = defaultdict(set)
    for r in records.get("daily-price", []):
        s = security(r["security"])
        role = "benchmark" if s[2] == "index" else "target"
        identities[role].add(s)
        require(s[1] in markets, "calendar_market_mismatch")
        require(r["adjustment"] == p["adjustment"], "adjustment_mismatch")
        require(
            r["unit"] == ("points" if role == "benchmark" else f"{s[3]}_per_share"),
            "price_unit_mismatch",
        )
        require(r["close"] > 0, "nonpositive_price")
        d = r["session_date"]
        require(d in seen, "price_outside_calendar")
        require(d not in series[role], "duplicate_price_date")
        session = session_lookup[d]
        require(instant(session["close_at"]) <= cutoff, "future_data")
        series[role][d] = r
    require(all(len(x) == 1 for x in identities.values()), "price_security_mismatch")
    require(all(len(x) <= 5000 for x in series.values()), "workload_too_large")
    for session in sessions[max(0, index - pre) : index + post + 1]:
        d = session["session_date"]
        future = instant(session["close_at"]) > cutoff
        row = {"session_date": d, "future_window": future}
        for role in ("target", "benchmark"):
            r = series[role].get(d)
            ok = bool(r and r["tradable"] and not future)
            row[role + "_covered"] = ok
            if not ok:
                missing.append(
                    {
                        "code": "future_window" if future else role + "_missing_or_untradable",
                        "session_date": d,
                    }
                )
        output.append(row)
    return (
        output,
        {
            "event_date": sessions[index]["session_date"],
            "return_algorithm": "comparison_receipt_required",
        },
        missing,
        [],
        ["alignment_only", "old_event_return_blocked"],
    )
