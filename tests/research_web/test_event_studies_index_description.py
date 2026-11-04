"""Index descriptions must not silently consume a tradable proxy's prices or calendar."""

import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.research_web.event_studies.contracts import StudyError
from app.research_web.event_studies.service import StudyBundle, StudyService
from app.research_web.market_scoring.profiles import PROFILE_VERSION
from tests.research_web.test_event_studies import calendar, proxy
from tests.research_web.test_event_studies_service import Records


def qualified_bundle():
    index_cal = calendar(80, date(2024, 1, 1))
    proxy_cal = calendar(40, date(2024, 2, 1))
    index_rows = [
        {"day": session.day.isoformat(), "close": str(Decimal(100) * Decimal("1.01") ** i)}
        for i, session in enumerate(index_cal.sessions)
    ]
    proxy_rows = [
        {"day": session.day.isoformat(), "close": str(Decimal(100) * Decimal(".98") ** i)}
        for i, session in enumerate(proxy_cal.sessions)
    ]
    return StudyBundle(
        index_id="SP500",
        rows=proxy_rows,
        data_digest="b" * 64,
        calendar=proxy_cal,
        proxy=proxy(proxy_cal),
        calendar_basis="synthetic_proxy_calendar",
        index_rows=index_rows,
        index_data_digest="a" * 64,
        index_calendar=index_cal,
        index_calendar_basis="synthetic_index_calendar",
        index_qualification_receipts=("synthetic-index-proof",),
        qualification_receipts=("synthetic-proxy-proof",),
        data_gaps=(),
    )


def registered(bundle):
    records = Records()
    source = records.create(
        "prices", {"source_kind": "synthetic-index-input"}, "index-description-source"
    )
    service = StudyService(
        SimpleNamespace(
            event_timeline=SimpleNamespace(records=records),
            resolve_event_study_bundle=lambda ref: bundle,
        )
    )
    study = service.create(
        {
            "title": "Index description",
            "role": "calendar_overlay",
            "index_id": "SP500",
            "profile_version": PROFILE_VERSION,
            "family": "month_end",
            "direction": 1,
            "rule": "month_end_1",
            "hypothesis": "registered-index-calendar",
            "bundle_ref": {"id": source["id"], "revision": 1},
        },
        "index-description-study",
    )
    return service, study, records


class IndexDescriptionTests(unittest.TestCase):
    def test_actual_qualified_bundle_describes_index_return_calendar_and_range_not_etf(self):
        bundle = qualified_bundle()
        service, study, records = registered(bundle)
        run = service.analyze(study["id"], "index-only-description")["payload"]
        self.assertAlmostEqual(run["summary"]["month_end_1"]["mean"], 0.01, places=7)
        self.assertEqual(run["calendar_basis"], "synthetic_index_calendar")
        self.assertEqual(run["data_digest"], "a" * 64)
        self.assertEqual(run["proxy_data_digest"], "b" * 64)
        self.assertTrue(any(row["end"] == "2024-01-31" for row in run["windows"]))
        self.assertEqual(records.ranges[0]["start"], bundle.index_rows[0]["day"])
        self.assertEqual(records.ranges[0]["end"], bundle.index_rows[-1]["day"])
        preflight = service.preflight(study["id"])
        self.assertEqual(preflight["historical_rows"], 80)
        self.assertEqual(preflight["coverage_start"], "2024-01-01")
        self.assertEqual(preflight["proxy_coverage"]["coverage_start"], "2024-02-01")

    def test_missing_index_cannot_fall_back_to_etf_even_with_trusted_proxy_bundle(self):
        bundle = replace(
            qualified_bundle(), index_rows=[], index_calendar=None, index_data_digest=""
        )
        service, study, records = registered(bundle)
        with self.assertRaisesRegex(StudyError, "index_evidence_missing"):
            service.analyze(study["id"], "missing-index-description")
        self.assertEqual(records.ranges, [])
        preflight = service.preflight(study["id"])
        self.assertIn("index_evidence_missing", preflight["reasons"])
        self.assertEqual(preflight["historical_rows"], 0)
        self.assertIsNone(preflight["coverage_start"])

    def test_legacy_research_only_index_without_proxy_keeps_documented_fallback(self):
        original = qualified_bundle()
        bundle = replace(
            original,
            proxy=None,
            rows=original.index_rows,
            data_digest="a" * 64,
            calendar=original.index_calendar,
            calendar_basis="legacy_index_calendar",
            index_rows=[],
            index_data_digest="",
            index_calendar=None,
            index_calendar_basis=None,
            data_gaps=("historical_point_in_time_not_verified",),
        )
        service, study, _ = registered(bundle)
        run = service.analyze(study["id"], "legacy-index-description")["payload"]
        self.assertAlmostEqual(run["summary"]["month_end_1"]["mean"], 0.01, places=7)
        self.assertEqual(run["calendar_basis"], "legacy_index_calendar")
        self.assertIsNone(run["proxy_data_digest"])

    def test_explicit_index_without_any_proxy_rows_can_still_generate_description(self):
        bundle = replace(
            qualified_bundle(),
            proxy=None,
            rows=[],
            data_digest="",
            calendar=None,
            data_gaps=("tradable_proxy_not_qualified",),
        )
        service, study, _ = registered(bundle)
        run = service.analyze(study["id"], "empty-proxy-index-description")["payload"]
        self.assertAlmostEqual(run["summary"]["month_end_1"]["mean"], 0.01, places=7)
        self.assertEqual(run["validation"]["evidence_sha256"], "a" * 64)
        self.assertEqual(run["calendar_basis"], "synthetic_index_calendar")
