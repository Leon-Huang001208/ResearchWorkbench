"""Frozen validation family, overlapping episodes and matched-control regressions."""

import unittest
from datetime import date, timedelta

from app.research_web.event_studies.contracts import Calendar, Session, StudyError
from app.research_web.event_studies.research import (
    independent_episodes,
    matched_controls,
    window_returns,
)
from app.research_web.event_studies.validation import assess, bootstrap_family, sample_gaps
from tests.research_web.test_event_studies import calendar


class ValidationTests(unittest.TestCase):
    def days(self, years=4):
        first = date(2020, 1, 1)
        return [
            (first + timedelta(days=i)).isoformat()
            for i in range(years * 366)
            if (first + timedelta(days=i)).weekday() < 5
        ]

    def test_sample_statuses_are_distinct_and_missing_data_precedes_statistics(self):
        days = self.days()
        result = assess(
            {
                "no_data": {"days": [], "data_gaps": ["no_pit"]},
                "small": {"days": days[:40], "data_gaps": []},
            }
        )
        self.assertEqual(result["no_data"]["status"], "DATA_INELIGIBLE")
        self.assertEqual(result["small"]["status"], "INSUFFICIENT_SAMPLE")

    def test_event_requires_independent_episodes_in_five_years(self):
        days = self.days(6)
        episodes = [{"id": f"event-{i}", "year": 2020 + i % 5} for i in range(20)]
        self.assertEqual(sample_gaps(days, event_episodes=episodes, event=True), [])
        self.assertTrue(
            sample_gaps(days, event_episodes=[{"id": "one", "year": 2020}] * 20, event=True)
        )

    def test_holm_counts_failed_candidates_and_stress_vetoes(self):
        good = {"sharpe": 1.0, "cagr": 0.1, "max_drawdown": 0.1}
        base = {"sharpe": 0.5, "cagr": 0.09, "max_drawdown": 0.2}
        trial = {
            "days": self.days(),
            "data_gaps": [],
            "bootstrap": {"p_value": 0.02},
            "normal": {"strategy": good, "comparator": base},
            "stress": {"strategy": good, "comparator": base},
        }
        self.assertEqual(assess({"x": trial})["x"]["status"], "VALIDATED")
        family = {
            "x": trial,
            "failed1": {"data_gaps": ["missing"]},
            "failed2": {"data_gaps": ["missing"]},
        }
        self.assertEqual(assess(family)["x"]["status"], "VALIDATION_FAILED")
        trial["stress"]["strategy"] = {**good, "max_drawdown": 0.3}
        self.assertIn("stress_drawdown_worse", assess({"x": trial})["x"]["reasons"])

    def test_overlaps_are_single_statistical_episode(self):
        windows = [
            {"start": "2024-01-01", "end": "2024-01-10", "episode": "war"},
            {"start": "2024-01-09", "end": "2024-01-20", "episode": "policy"},
            {"start": "2024-02-01", "end": "2024-02-02", "episode": "other"},
        ]
        groups = independent_episodes(windows)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["id"], "policy|war")

    def test_reopening_gap_uses_open_not_close(self):
        result = window_returns(
            [
                {
                    "rule": "reopening_gap",
                    "start": "2024-01-01",
                    "end": "2024-01-03",
                    "start_price": "close",
                    "end_price": "open",
                }
            ],
            [
                {"day": "2024-01-01", "close": "100"},
                {"day": "2024-01-03", "open": "105", "close": "90"},
            ],
        )
        self.assertEqual(result[0]["return"], "0.05")

    def test_control_selection_never_ranks_future_return(self):
        days = self.days(1)[:120]
        rows = [{"day": day, "close": str(100 + i)} for i, day in enumerate(days)]
        window = {"rule": "event_post_5", "start": days[70], "end": days[75], "episode": "e"}
        a = matched_controls([window], rows)
        chosen = days.index(a[0]["control_start"])
        self.assertLessEqual(chosen, len(days) - 6)
        # Changing only the matched future endpoint must not change matching.
        rows[chosen + 5]["close"] = "100000"
        b = matched_controls([window], rows)
        # An earlier candidate's future may enter a later candidate's past.
        # Freeze the candidate universe to earlier windows for a decisive check.
        self.assertEqual(a[0]["control_start"], b[0]["control_start"])

    def test_bootstrap_rejects_nonfinite_data(self):
        with self.assertRaisesRegex(StudyError, "nonfinite"):
            bootstrap_family(
                {"x": {"days": ["2024-01-01"], "strategy": [float("nan")], "comparator": [0.0]}}
            )

    def test_paired_identical_strategies_cannot_be_significant(self):
        days = self.days(1)[:80]
        values = [0.001 if i % 3 else -0.001 for i in range(len(days))]
        result = bootstrap_family(
            {
                "a": {"days": days, "strategy": values, "comparator": values},
                "b": {"days": days, "strategy": values, "comparator": values},
            }
        )
        self.assertIsNone(result["a"]["p_value"])
        self.assertEqual(result["a"]["difference"], 0.0)
        self.assertEqual(result["a"], result["b"])

    def test_capture_timestamp_never_supplies_calendar_announcement(self):
        cal = calendar(80)
        self.assertIsNone(cal.sessions[0].known_at)
        self.assertIsNone(cal.announcement_known_at)
        with self.assertRaises(ValueError):
            Session(**{**cal.sessions[0].model_dump(), "known_at": "2020-01-01T00:00:00Z"})
        with self.assertRaises(ValueError):
            Calendar(**{**cal.model_dump(), "announcement_known_at": "2020-01-01T00:00:00Z"})
