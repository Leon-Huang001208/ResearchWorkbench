"""Independent index outcomes never borrow proxy-strategy performance evidence."""

import unittest
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.research_web.event_studies.contracts import Calendar, Session
from app.research_web.event_studies.events import FORECAST_PROTOCOL
from app.research_web.event_studies.prediction import (
    cluster_pairs,
    prepare_prediction,
    validate_prediction_family,
)


def daily_rows():
    first = date(2020, 1, 1)
    days = [
        (first + timedelta(days=i)).isoformat()
        for i in range(366 * 7)
        if (first + timedelta(days=i)).weekday() < 5
    ]
    return [{"day": day, "close": str(100 + i / 100)} for i, day in enumerate(days)]


def window(start="2023-06-20", end="2023-06-21"):
    return {
        "episode": "event",
        "rule": "event_post_5",
        "start": start,
        "end": end,
        "start_price": "close",
        "end_price": "close",
    }


def prediction_context(rows):
    zone = ZoneInfo("America/New_York")
    sessions = [
        Session(
            day=date.fromisoformat(row["day"]),
            opens=datetime.combine(date.fromisoformat(row["day"]), time(9, 30), zone),
            closes=datetime.combine(date.fromisoformat(row["day"]), time(16), zone),
        )
        for row in rows
    ]
    return {
        "calendar": Calendar(
            exchange="XNYS",
            timezone="America/New_York",
            version="synthetic",
            source_ref="synthetic",
            known_at="2020-01-01T00:00:00Z",
            sessions=sessions,
        ),
        "events": [{"id": "event", "known_at": "2019-01-01T00:00:00Z"}],
    }


def prepared_candidate(sign=1):
    rows = daily_rows()
    pairs = []
    for year in range(2020, 2026):
        for month in range(1, 13):
            pairs.append(
                {
                    "episode": f"event:{year}-{month}",
                    "rule": "event_post_5",
                    "start": f"{year}-{month:02d}-20",
                    "end": f"{year}-{month:02d}-21",
                    "control_start": f"{year}-{month:02d}-10",
                    "control_end": f"{year}-{month:02d}-11",
                    "signed_excess": sign * (0.02 + month / 10000),
                }
            )
    return {
        "days": [row["day"] for row in rows],
        "pairs": pairs,
        "missing": [],
        "data_gaps": [],
        "forecast_protocol": FORECAST_PROTOCOL,
    }


class IndexPredictionTests(unittest.TestCase):
    def test_matches_are_completed_before_event_and_ignore_future_prices(self):
        rows = daily_rows()
        holdout = [row["day"] for row in rows]
        a = prepare_prediction(rows, [window()], holdout, 1, **prediction_context(rows))
        self.assertEqual(len(a["pairs"]), 1)
        self.assertLess(a["pairs"][0]["control_end"], "2023-06-20")
        for row in rows:
            if row["day"] > "2023-06-21":
                row["close"] = "10000000"
        self.assertEqual(
            a, prepare_prediction(rows, [window()], holdout, 1, **prediction_context(rows))
        )

    def test_train_and_purged_outcomes_never_become_holdout_controls(self):
        rows = daily_rows()
        holdout = [row["day"] for row in rows if row["day"] >= "2023-06-01"]
        result = prepare_prediction(
            rows,
            [window(), window("2023-05-10", "2023-05-11")],
            holdout,
            1,
            **prediction_context(rows),
        )
        self.assertEqual(result["eligible_windows"], 1)
        self.assertGreaterEqual(result["pairs"][0]["control_start"], holdout[0])
        self.assertGreaterEqual(result["pairs"][0]["control_end"], holdout[0])

    def test_registered_direction_changes_effect_sign_not_control_selection(self):
        rows = daily_rows()
        holdout = [row["day"] for row in rows]
        long = prepare_prediction(rows, [window()], holdout, 1, **prediction_context(rows))[
            "pairs"
        ][0]
        short_effect = prepare_prediction(
            rows, [window()], holdout, -1, **prediction_context(rows)
        )["pairs"][0]
        self.assertEqual(long["control_start"], short_effect["control_start"])
        self.assertAlmostEqual(long["signed_excess"], -short_effect["signed_excess"])

    def test_no_ordinary_prior_sameyear_control_is_reported_not_fabricated(self):
        rows = daily_rows()
        result = prepare_prediction(
            rows,
            [window("2020-01-02", "2020-01-03")],
            [r["day"] for r in rows],
            1,
            **prediction_context(rows),
        )
        self.assertEqual(result["pairs"], [])
        self.assertEqual(result["missing"][0]["reason"], "no_eligible_same_year_control")
        decision = validate_prediction_family({"x": {**result, "data_gaps": []}}, ["x"])["x"]
        self.assertEqual(decision["status"], "INSUFFICIENT_SAMPLE")

    def test_same_event_and_reused_control_cluster_across_markets(self):
        pair = prepared_candidate()["pairs"][0]
        shifted = {**pair, "start": "2020-01-21", "end": "2020-01-22"}
        reused = {**pair, "episode": "unrelated-event", "start": "2020-02-20", "end": "2020-02-21"}
        assignment, groups = cluster_pairs(
            {"CN": {"pairs": [pair, reused]}, "US": {"pairs": [shifted]}}
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(assignment["CN", 0], assignment["US", 0])
        self.assertEqual(assignment["CN", 1], assignment["US", 0])

    def test_merely_shared_closing_endpoint_does_not_merge_disjoint_returns(self):
        pair = prepared_candidate()["pairs"][0]
        following = {
            **pair,
            "episode": "following",
            "start": pair["end"],
            "end": "2020-01-22",
            "control_start": "2020-01-12",
            "control_end": "2020-01-13",
        }
        _, groups = cluster_pairs({"x": {"pairs": [pair, following]}})
        self.assertEqual(len(groups), 2)

    def test_real_index_gate_and_holm_keep_unavailable_hypotheses(self):
        first = prepared_candidate()
        second = deepcopy(first)
        second["proxy_sharpe"] = -1000000  # Not an input to the independent index test.
        decisions = validate_prediction_family(
            {
                "CN": first,
                "US": second,
                "failed": {"data_gaps": ["index_pit_missing"], "pairs": [], "days": []},
            },
            ["CN", "US", "failed"],
        )
        self.assertEqual(decisions["CN"]["status"], "VALIDATED")
        self.assertEqual(decisions["US"]["status"], "VALIDATED")
        self.assertEqual(decisions["failed"]["status"], "DATA_INELIGIBLE")
        self.assertEqual(
            decisions["CN"]["mean_signed_excess"], decisions["US"]["mean_signed_excess"]
        )
        self.assertEqual(decisions["CN"]["clusters_sha256"], decisions["US"]["clusters_sha256"])
        self.assertGreater(decisions["CN"]["holm"]["p_adjusted"], decisions["CN"]["holm"]["p_raw"])

    def test_wrong_direction_fails_even_if_proxy_metrics_are_profitable(self):
        data = prepared_candidate(-1)
        data["proxy_sharpe"] = 1000000
        decision = validate_prediction_family({"x": data}, ["x"])["x"]
        self.assertEqual(decision["status"], "VALIDATION_FAILED")
        self.assertIn("directional_index_excess_not_positive", decision["reasons"])
