"""Shared event precision and authoritative revision-availability projection."""

import unittest

from app.research_web.event_studies.calendars import event_windows
from app.research_web.event_studies.events import availability_floor, project_event
from tests.research_web.test_event_studies import calendar


def event(**changes):
    return {
        "date_precision": "minute",
        "occurrence_start": "2024-06-03T01:00:00Z",
        "occurrence_end": "2024-06-03T04:00:00Z",
        "source_published_at": "2024-01-01T00:00:00Z",
        "category": "macro",
        "lifecycle": "occurred",
        **changes,
    }


class SharedEventProjectionTests(unittest.TestCase):
    def test_interval_unknown_month_and_explicit_ineligible_time_never_project(self):
        for precision in ("interval", "unknown", "month", None):
            self.assertIsNone(project_event(event(date_precision=precision), "SP500"))
        self.assertIsNone(project_event(event(event_time_eligible=False), "SP500"))
        for state in ("cancelled", "scenario"):
            self.assertIsNone(project_event(event(lifecycle=state), "SP500"))

    def test_us_dst_and_hong_kong_cross_day_share_the_same_projection(self):
        us = project_event(event(), "SP500", identifier="a" * 32, revision=2)
        self.assertEqual((us["start"], us["end"]), ("2024-06-02", "2024-06-03"))
        self.assertEqual(us["source_start_utc"], "2024-06-03T01:00:00+00:00")
        hk = project_event(
            event(occurrence_start="2024-06-03T20:00:00Z", occurrence_end=None), "HSI"
        )
        self.assertEqual((hk["start"], hk["end"]), ("2024-06-04", "2024-06-04"))

    def test_day_precision_preserves_literal_dates_without_making_midnight(self):
        projected = project_event(
            event(date_precision="day", occurrence_start="2024-06-03", occurrence_end=None), "HSI"
        )
        self.assertEqual(projected["start"], "2024-06-03")
        self.assertIsNone(projected["source_start_utc"])

    def test_publication_and_payload_first_observed_cannot_backdate_missing_revision_receipt(self):
        projected = project_event(
            event(first_observed="1994-01-01T00:00:00Z", known_at="1994-01-01T00:00:00Z"), "SP500"
        )
        self.assertIsNone(projected["known_at"])
        self.assertIsNone(availability_floor(None, ["2024-01-01T00:00:00Z"]))

    def test_future_announced_event_is_known_after_server_capture_without_publication_timestamp(
        self,
    ):
        projected = project_event(
            event(
                date_precision="day",
                occurrence_start="2027-06-01",
                occurrence_end=None,
                source_published_at=None,
            ),
            "SSE",
            known_floor="2026-11-04T10:00:00Z",
        )
        self.assertEqual(projected["known_at"], "2026-11-04T10:00:00+00:00")
        self.assertEqual(projected["publication_time_status"], "missing_or_imprecise")

    def test_authoritative_revision_archive_and_publication_times_use_latest_bound(self):
        floor = availability_floor("2026-11-04T10:00:00Z", ["2026-11-04T11:00:00Z"])
        self.assertEqual(floor, "2026-11-04T11:00:00+00:00")
        projected = project_event(
            event(source_published_at="2026-11-04T12:00:00Z"), "SSE", known_floor=floor
        )
        self.assertEqual(projected["known_at"], "2026-11-04T12:00:00+00:00")
        old_publication = project_event(
            event(source_published_at="1994-01-01T00:00:00Z"), "SSE", known_floor=floor
        )
        self.assertEqual(old_publication["known_at"], floor)

    def test_revised_information_cannot_reuse_old_first_observed_timestamp(self):
        value = event(first_observed="1994-01-01T00:00:00Z")
        original = project_event(value, "SP500", revision=1, known_floor="2026-11-04T10:00:00Z")
        revised = project_event(
            {**value, "occurrence_start": "2027-06-01T01:00:00Z", "occurrence_end": None},
            "SP500",
            revision=2,
            known_floor="2026-11-06T10:00:00Z",
        )
        self.assertGreater(revised["known_at"], original["known_at"])
        self.assertGreater(revised["known_at"], "2026-11-05T23:59:59+00:00")

    def test_imprecise_or_invalid_publication_does_not_destroy_valid_capture_receipt(self):
        for published in (None, "2024-01-01", "not-a-date"):
            projected = project_event(
                event(source_published_at=published), "SP500", known_floor="2026-11-04T10:00:00Z"
            )
            self.assertEqual(projected["known_at"], "2026-11-04T10:00:00+00:00")

    def test_ongoing_unknown_end_preserves_pre_windows_without_inventing_during_or_post(self):
        projected = project_event(
            event(
                date_precision="day",
                occurrence_start="2024-02-10",
                occurrence_end=None,
                lifecycle="ongoing",
            ),
            "SP500",
            identifier="ongoing",
            revision=1,
        )
        self.assertFalse(projected["end_known"])
        self.assertIsNone(projected["end"])
        self.assertIsNone(projected["source_occurrence_end"])
        self.assertIsNone(projected["source_end_utc"])
        windows = event_windows(calendar(80), [projected])
        self.assertEqual({window["rule"] for window in windows}, {"event_pre_5", "event_pre_10"})
        self.assertTrue(all(window["event_end_known"] is False for window in windows))

    def test_punctual_occurred_event_may_implicitly_end_on_its_known_single_day(self):
        projected = project_event(
            event(
                date_precision="day",
                occurrence_start="2024-02-10",
                occurrence_end=None,
                lifecycle="occurred",
            ),
            "SP500",
            identifier="punctual",
            revision=1,
        )
        self.assertTrue(projected["end_known"])
        self.assertEqual(projected["end"], "2024-02-10")
        self.assertIsNone(projected["source_occurrence_end"])
        self.assertIn(
            "event_post_5", {window["rule"] for window in event_windows(calendar(80), [projected])}
        )
