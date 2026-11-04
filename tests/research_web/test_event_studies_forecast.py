"""Forecast eligibility uses the window's actual starting price timestamp."""

import unittest
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.research_web.event_studies.calendars import event_windows
from app.research_web.event_studies.events import forecast_window_gaps
from app.research_web.event_studies.service import StudyBundle, StudyService
from app.research_web.market_scoring.profiles import PROFILE_VERSION
from tests.research_web.test_event_studies import bars, calendar, proxy
from tests.research_web.test_event_studies_service import Records


class ForecastKnowledgeTests(unittest.TestCase):
    def test_knowledge_one_minute_after_start_close_is_late_even_before_window_end(self):
        cal = calendar(80)
        selected = next(
            w
            for w in event_windows(
                cal, [{"id": "scheduled", "start": "2024-02-10", "end": "2024-02-18"}]
            )
            if w["rule"] == "event_pre_5"
        )
        session = next(s for s in cal.sessions if s.day.isoformat() == selected["start"])
        late = [
            {"id": "scheduled", "known_at": (session.closes + timedelta(minutes=1)).isoformat()}
        ]
        self.assertEqual(
            forecast_window_gaps(cal, selected, events=late),
            ["event_first_known_after_prediction_start"],
        )
        early = [{"id": "scheduled", "known_at": (session.closes - timedelta(days=30)).isoformat()}]
        self.assertEqual(forecast_window_gaps(cal, selected, events=early), [])

    def test_open_and_close_start_prices_have_distinct_real_information_cutoffs(self):
        cal = calendar(80)
        selected = {
            "episode": "event",
            "start": cal.sessions[30].day.isoformat(),
            "end": cal.sessions[35].day.isoformat(),
            "start_price": "close",
        }
        known = [
            {
                "id": "event",
                "known_at": (cal.sessions[30].opens + timedelta(minutes=30)).isoformat(),
            }
        ]
        self.assertEqual(forecast_window_gaps(cal, selected, events=known), [])
        self.assertEqual(
            forecast_window_gaps(cal, {**selected, "start_price": "open"}, events=known),
            ["event_first_known_after_prediction_start"],
        )
        self.assertEqual(
            forecast_window_gaps(cal, selected, events=[{"id": "event", "known_at": None}]),
            ["event_knowledge_unknown_at_prediction_start"],
        )

    def test_calendar_capture_is_not_a_boundary_announcement_at_the_start_price(self):
        cal = calendar(80)
        selected = {
            "episode": "month",
            "start": cal.sessions[30].day.isoformat(),
            "end": cal.sessions[35].day.isoformat(),
            "start_price": "close",
        }
        self.assertEqual(
            forecast_window_gaps(cal, selected, deterministic_calendar=True),
            ["calendar_schedule_not_known_at_prediction_start"],
        )
        announced = cal.model_copy(
            update={
                "announcement_known_at": datetime(2020, 1, 1, tzinfo=UTC),
                "announcement_version_ref": "synthetic-schedule",
            }
        )
        self.assertEqual(forecast_window_gaps(announced, selected, deterministic_calendar=True), [])


def event_study(captured):
    records = Records()
    records.revision_recorded_at = lambda kind, identifier, revision: captured
    cal = calendar(400, date(2019, 1, 1)).model_copy(
        update={
            "announcement_known_at": datetime(2018, 1, 1, tzinfo=UTC),
            "announcement_version_ref": "synthetic-calendar",
        }
    )
    instrument = proxy(cal)
    instrument = instrument.model_copy(
        update={
            "known_at": datetime(2018, 1, 1, tzinfo=UTC),
            "rules": [
                rule.model_copy(update={"known_at": datetime(2018, 1, 1, tzinfo=UTC)})
                for rule in instrument.rules
            ],
        }
    )
    prices = bars(cal)
    signals = {row["day"]: ".5" for row in prices}
    bundle = StudyBundle(
        index_id="SP500",
        rows=prices,
        data_digest="a" * 64,
        calendar=cal,
        proxy=instrument,
        index_rows=deepcopy(prices),
        index_calendar=cal,
        index_data_digest="b" * 64,
        index_qualification_receipts=("synthetic-index-pit",),
        signals=signals,
        base_signals=signals,
        signal_receipts={
            row["day"]: {"known_at": row["known_at"], "source_ref": "synthetic-signal"}
            for row in prices
        },
        qualification_receipts=("synthetic-proxy-and-factor-pit",),
        data_gaps=(),
    )
    source = records.create("prices", {"source": "synthetic"}, "synthetic-price-source")
    event = records.create(
        "event",
        {
            "admission": "confirmed",
            "category": "sports",
            "date_precision": "day",
            "occurrence_start": "2020-04-20",
            "occurrence_end": "2020-04-27",
            "lifecycle": "announced",
            "source_published_at": None,
            "evidence_refs": [],
        },
        "synthetic-scheduled-event",
    )
    frozen = records.create(
        "freeze",
        {"event_refs": [{"id": event["id"], "revision": 1}], "evidence_refs": []},
        "synthetic-scheduled-freeze",
    )
    service = StudyService(
        SimpleNamespace(
            event_timeline=SimpleNamespace(records=records),
            resolve_event_study_bundle=lambda ref: bundle,
        )
    )
    study = service.create(
        {
            "title": "Synthetic scheduled event",
            "index_id": "SP500",
            "profile_version": PROFILE_VERSION,
            "role": "event_overlay",
            "family": "sports",
            "direction": 1,
            "rule": "event_pre_5",
            "hypothesis": "predeclared-pre-five",
            "bundle_ref": {"id": source["id"], "revision": 1},
            "frozen_event_ref": {"id": frozen["id"], "revision": 1},
        },
        "synthetic-event-study",
    )
    return service, study


class ServiceForecastTests(unittest.TestCase):
    def test_late_known_event_is_descriptive_but_not_an_index_forecast(self):
        service, study = event_study("2020-04-15T12:00:00Z")
        self.assertIn(
            "event_first_known_after_prediction_start", service.preflight(study["id"])["reasons"]
        )
        batch = service.seal([study["id"]], "late-event-seal")
        result = service.evaluate(batch["id"], "late-event-evaluate")["items"][0]["payload"][
            "validation"
        ]
        self.assertEqual(result["index_prediction"]["status"], "DATA_INELIGIBLE")
        self.assertIn(
            "event_first_known_after_prediction_start", result["index_prediction"]["reasons"]
        )
        self.assertEqual(result["index_prediction"]["matched_pairs"], 0)

    def test_future_preannounced_event_without_publication_time_passes_temporal_gate(self):
        service, study = event_study("2019-12-01T12:00:00Z")
        preflight = service.preflight(study["id"])
        self.assertNotIn("event_first_known_after_prediction_start", preflight["reasons"])
        self.assertNotIn("event_knowledge_unknown_at_prediction_start", preflight["reasons"])
        batch = service.seal([study["id"]], "scheduled-event-seal")
        result = service.evaluate(batch["id"], "scheduled-event-evaluate")["items"][0]["payload"][
            "validation"
        ]
        self.assertEqual(result["index_prediction"]["status"], "INSUFFICIENT_SAMPLE")
        self.assertGreater(result["index_prediction"]["matched_pairs"], 0)
