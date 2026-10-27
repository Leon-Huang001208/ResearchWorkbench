"""Limited counts, disclosed holdings and calendar arithmetic, without scores."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from itertools import pairwise

from .contracts import DerivedBudget, day, instant, number, require, security


def sentiment_counts(records, p, cutoff):
    rows, missing, seen = [], [], set()
    for r in records.get("sentiment-counts", []):
        key = tuple(r[k] for k in ("market", "session_date", "universe_hash", "regime_id"))
        require(key not in seen, "duplicate_universe_counts")
        seen.add(key)
        require(day(r["session_date"]) <= cutoff.date(), "future_data")
        expected, observed = r["expected_count"], r["observed_count"]
        require(observed + r["unknown"] == expected, "count_denominator_mismatch")
        require(r["up"] + r["down"] + r["flat"] == observed, "count_partition_mismatch")
        require(
            r["limit_up"] + r["opened_limit"] == r["limit_touched"] <= observed,
            "limit_count_mismatch",
        )
        out = {
            "row_id": r["row_id"],
            "market": key[0],
            "session_date": key[1],
            "universe_hash": key[2],
            "regime_id": key[3],
            "expected_count": expected,
            "observed_count": observed,
            "unknown": r["unknown"],
        }
        for name in ("up", "down", "limit_up"):
            out[name + "_ratio"] = r[name] / expected if expected else None
        out["opened_limit_ratio"] = (
            r["opened_limit"] / r["limit_touched"] if r["limit_touched"] else None
        )
        if r["unknown"] or not expected or not r["limit_touched"]:
            missing.append({"code": "counts_partial_or_zero_denominator", "row_id": r["row_id"]})
        rows.append(out)
    if not rows:
        missing.append({"code": "counts_missing"})
    return (
        rows,
        {"strata": len(rows)},
        missing,
        [],
        ["no_sentiment_score", "flows_and_seats_not_computed"],
    )


def report_period_key(period):
    require(isinstance(period, str), "report_periods_invalid")
    match = re.fullmatch(r"([0-9]{4})(?:Q([1-4])|(FY))", period)
    require(match is not None and int(match[1]) >= 1, "report_periods_invalid")
    return int(match[1]), int(match[2]) if match[2] else 4


def disclosed_ownership(records, p, cutoff):
    periods = p["report_periods"]
    require(
        isinstance(periods, list)
        and all(isinstance(x, str) for x in periods)
        and len(set(periods)) == len(periods),
        "report_periods_invalid",
    )
    keys = [report_period_key(period) for period in periods]
    require(len(set(keys)) == len(keys), "report_periods_invalid")
    periods = sorted(periods, key=report_period_key)
    period_index = {period: index for index, period in enumerate(periods)}
    groups, seen, rows, missing = defaultdict(list), set(), [], []
    for r in records.get("holder-disclosure", []):
        require(instant(r["disclosed_at"]) <= cutoff, "future_data")
        require(r["report_period"] in periods, "report_period_mismatch")
        key = (security(r["security"]), r["report_period"], r["holder_id"])
        require(key not in seen, "duplicate_holder_disclosure")
        seen.add(key)
        shares = number(r["shares"] * (10000 if r["unit"] == "10k-share" else 1))
        require(shares >= 0, "negative_shares")
        f = r["float_shares"]
        if f is not None:
            f = number(f * (10000 if r["float_unit"] == "10k-share" else 1))
            require(f >= 0, "negative_float")
        out = {
            "row_id": r["row_id"],
            "security": r["security"],
            "report_period": r["report_period"],
            "holder_id": r["holder_id"],
            "shares": shares,
            "float_shares": f,
            "disclosed_float_fraction": number(shares / f) if f and shares <= f else None,
            "change_shares": None,
            "change_fraction_points": None,
        }
        if f is None or f == 0 or shares > f:
            missing.append({"code": "float_missing_or_overcoverage", "row_id": r["row_id"]})
        groups[(key[0], r["holder_id"])].append(out)
        rows.append(out)
    for members in groups.values():
        members.sort(key=lambda x: period_index[x["report_period"]])
        for previous, current in pairwise(members):
            if (
                period_index[current["report_period"]]
                != period_index[previous["report_period"]] + 1
            ):
                continue
            current["change_shares"] = number(current["shares"] - previous["shares"])
            a, b = previous["disclosed_float_fraction"], current["disclosed_float_fraction"]
            if a is not None and b is not None:
                current["change_fraction_points"] = number(b - a)
    declared = p.get("disjoint_holder_ids", [])
    require(
        isinstance(declared, list)
        and all(isinstance(x, str) and x for x in declared)
        and len(set(declared)) == len(declared),
        "holder_disjointness_invalid",
    )
    missing_budget = DerivedBudget()
    identities = {identity for identity, _ in groups}
    # Reject an oversized disclosure grid before allocating the cross product.
    missing_budget.preflight(max(len(groups), len(identities) * len(declared)) * len(periods))
    required_groups = set(groups)
    for identity in identities:
        for holder in declared:
            if (identity, holder) not in required_groups:
                missing_budget.preflight((len(required_groups) + 1) * len(periods))
                required_groups.add((identity, holder))
    for identity, holder in sorted(required_groups):
        for period in periods:
            if (identity, period, holder) not in seen:
                missing_budget.append(
                    missing,
                    {
                        "code": "holder_period_missing",
                        "security": list(identity),
                        "holder_id": holder,
                        "report_period": period,
                    },
                )
    period_groups = defaultdict(list)
    for row in rows:
        period_groups[(security(row["security"]), row["report_period"])].append(row)
    totals = []
    for (identity, period), members in period_groups.items():
        covered = all(x["holder_id"] in declared for x in members)
        floats = {x["float_shares"] for x in members}
        require(len(floats) <= 1, "float_basis_mismatch")
        shares = number(math.fsum(x["shares"] for x in members)) if covered else None
        f = next(iter(floats))
        ratio = None
        if covered and f and shares <= f:
            ratio = number(shares / f)
        elif covered and f and shares > f:
            missing.append(
                {
                    "code": "aggregate_overcoverage",
                    "security": list(identity),
                    "report_period": period,
                }
            )
        if not covered:
            missing.append(
                {
                    "code": "holder_disjointness_unknown",
                    "security": list(identity),
                    "report_period": period,
                }
            )
        totals.append(
            {
                "security": list(identity),
                "report_period": period,
                "shares": shares,
                "disclosed_float_fraction": ratio,
                "disjointness_is_declaration": True,
            }
        )
    if not rows:
        missing.append({"code": "holder_disclosures_missing"})
    return (
        rows,
        {
            "total_shares": number(math.fsum(x["shares"] for x in rows)),
            "aggregate_fraction": None,
            "period_totals": totals,
            "report_period_order": periods,
        },
        missing,
        [],
        ["disclosed_subset_only", "holder_disjointness_not_verified", "fund_penetration_blocked"],
    )


def earnings_calendar(records, p, cutoff):
    expected = [security(s) for s in p["expected_universe"]]
    require(len(set(expected)) == len(expected), "duplicate_universe")
    selected, history = {}, defaultdict(list)
    for r in records.get("report-calendar", []):
        s = security(r["security"])
        require(s in expected, "universe_mismatch")
        require(r["report_period"] == p["report_period"], "report_period_mismatch")
        day(r["planned_date"])
        actual = r["actual_disclosed_at"]
        require(actual is None or instant(actual) <= cutoff, "future_data")
        require(r["origin"]["published_at"] is not None, "disclosure_time_unknown")
        require(
            all(x["plan_version"] != r["plan_version"] for x in history[s]),
            "duplicate_plan_version",
        )
        history[s].append(r)
        if s not in selected or selected[s]["plan_version"] < r["plan_version"]:
            selected[s] = r
    rows, missing, actuals = [], [], 0
    for s in expected:
        if s not in selected:
            missing.append({"code": "calendar_missing", "security": list(s)})
            continue
        r = selected[s]
        actuals += r["actual_disclosed_at"] is not None
        rows.append(
            {
                "row_id": r["row_id"],
                "security": r["security"],
                "report_period": r["report_period"],
                "plan_version": r["plan_version"],
                "planned_date": r["planned_date"],
                "actual_disclosed_at": r["actual_disclosed_at"],
                "supersedes_row_id": r["supersedes_row_id"],
                "history_row_ids": [x["row_id"] for x in history[s]],
            }
        )
    return (
        rows,
        {
            "expected_count": len(expected),
            "actual_count": actuals,
            "disclosed_fraction": actuals / len(expected) if expected else None,
        },
        missing,
        [],
        ["calendar_not_probability", "growth_monitor_blocked"],
    )
