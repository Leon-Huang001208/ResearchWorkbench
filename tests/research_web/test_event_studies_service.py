"""Reference-only study service contracts; real storage is covered by timeline tests."""

import asyncio
import hashlib
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.research_web.event_studies import service as service_module
from app.research_web.event_studies.contracts import StudyError, StudySpec
from app.research_web.event_studies.service import StudyService, digest
from app.research_web.market_scoring.profiles import PROFILE_VERSION
from app.research_web.store import StoreError


def _copy_implementation_sources(target):
    root = Path(service_module.__file__).parents[1]
    paths = [
        *root.joinpath("event_studies").glob("*.py"),
        *root.joinpath("market_scoring").glob("*.py"),
        root / "event_host_inputs.py",
        root / "event_datahub_bridge.py",
    ]
    for source in paths:
        destination = target / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return {source.relative_to(root).as_posix() for source in paths}


def test_sealed_implementation_digest_includes_host_and_all_scoring_sources(tmp_path, monkeypatch):
    expected = _copy_implementation_sources(tmp_path)
    assert set(service_module.implementation_sources()) == expected
    original = service_module.implementation_digest()
    monkeypatch.setattr(service_module, "IMPLEMENTATION_ROOT", tmp_path)
    assert service_module.implementation_digest() == original
    path = tmp_path / "market_scoring/engine.py"
    path.write_bytes(path.read_bytes() + b"\n# synthetic compiler revision\n")
    assert service_module.implementation_digest() != original


def test_scoring_compiler_change_is_rejected_before_opening_or_computation(tmp_path, monkeypatch):
    _copy_implementation_sources(tmp_path)
    monkeypatch.setattr(service_module, "IMPLEMENTATION_ROOT", tmp_path)
    fixture = ServiceTests(methodName="runTest")
    fixture.setUp()
    study = fixture.service.create(fixture.spec(), "implementation-study")
    batch = fixture.service.seal([study["id"]], "implementation-seal")
    ranges_before = list(fixture.records.ranges)
    claims_before = dict(fixture.records.claims)
    path = tmp_path / "event_host_inputs.py"
    path.write_bytes(path.read_bytes() + b"\n# synthetic Host compiler revision\n")
    with pytest.raises(StudyError, match="sealed_implementation_changed"):
        fixture.service.evaluate(batch["id"], "implementation-evaluate")
    assert fixture.records.ranges == ranges_before
    assert fixture.records.claims == claims_before


class Records:
    def __init__(self):
        self.rows, self.requests, self.claims, self.ranges = {}, {}, {}, []
        self.reconciliation_required = False

    def qualification_status(self):
        return {
            "required": self.reconciliation_required,
            "code": (
                "qualification_reconciliation_required" if self.reconciliation_required else None
            ),
        }

    def create(self, kind, payload, key):
        return self.batch([{"kind": kind, "payload": payload}], key)[0]

    def batch(self, ops, key, *, intent=None, scope=None, guard=None):
        if guard:
            guard()
        scoped = (scope or (ops[0]["kind"] if len(ops) == 1 else "batch"), key)
        identity = digest(ops if intent is None else intent)
        if scoped in self.requests:
            old, result = self.requests[scoped]
            if old != identity:
                raise StoreError("conflict", "event_idempotency_conflict", 409)
            return result
        result = []
        for op in ops:
            identifier = (
                op.get("new_id") or digest([op["kind"], op["payload"], len(self.rows)])[:32]
            )
            row = {"id": identifier, "revision": 1, "payload": op["payload"]}
            self.rows[op["kind"], identifier] = row
            result.append(row)
        self.requests[scoped] = identity, result
        return result

    def get(self, kind, identity, revision=None):
        if (kind, identity) not in self.rows:
            raise StoreError("missing", "event_record_not_found", 404)
        row = self.rows[kind, identity]
        if revision is not None and row["revision"] != revision:
            raise StoreError("revision", "event_revision_conflict", 409)
        return row

    def update(self, kind, identity, payload, expected_revision, key, *, guard=None):
        if guard:
            guard()
        row = self.get(kind, identity)
        if row["revision"] != expected_revision:
            raise StoreError("revision", "event_revision_conflict", 409)
        result = {"id": identity, "revision": row["revision"] + 1, "payload": payload}
        self.rows[kind, identity] = result
        return result

    def list(self, kind, limit=100, cursor=None):
        return {
            "items": [row for (k, _), row in self.rows.items() if k == kind][:limit],
            "next_cursor": None,
        }

    def claim_once(self, kind, identity, payload):
        if (kind, identity) in self.claims:
            raise StoreError("claim", "event_claim_conflict", 409)
        self.claims[kind, identity] = payload

    def claim_study_ranges(self, ranges, key):
        if key in self.claims:
            return
        for row in ranges:
            matches = [
                r
                for r in self.ranges
                if r["scope"] == row["scope"]
                and r["start"] <= row["end"]
                and r["end"] >= row["start"]
            ]
            if row["phase"] == "viewed" and all(r["phase"] == "viewed" for r in matches):
                continue
            if (
                row["phase"] == "opened"
                and matches
                and all(
                    r["phase"] == "sealed" and r["batch_id"] == row["batch_id"] for r in matches
                )
            ):
                continue
            if matches:
                raise StoreError("range", "event_holdout_range_reused", 409)
        self.ranges.extend(ranges)
        self.claims[key] = ranges


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.records = Records()
        days = [date(2020, 1, 1) + timedelta(days=i) for i in range(150)]
        rows = [
            {
                "day": day.isoformat(),
                "open": str(100 + i),
                "close": str(100 + i),
                "historical_eligible": True,
            }
            for i, day in enumerate(days)
            if day.weekday() < 5
        ]
        raw = json.dumps({"index_id": "SP500", "rows": rows, "historical_eligible": True}).encode()
        ref = {"id": "a" * 32, "sha256": hashlib.sha256(raw).hexdigest()}
        self.price = self.records.create(
            "prices", {"evidence_ref": ref, "historical_eligible": True}, "source-0001"
        )
        self.research = SimpleNamespace(
            event_timeline=SimpleNamespace(
                records=self.records,
                read_evidence=lambda reference: {"bytes": raw, "manifest": {"source": "DataHub"}},
            )
        )
        self.service = StudyService(self.research)

    def spec(self, **updates):
        return {
            "title": "Calendar test",
            "role": "calendar_overlay",
            "index_id": "SP500",
            "profile_version": PROFILE_VERSION,
            "hypothesis": "fixed-calendar-windows-v1",
            "family": "month_end",
            "direction": 1,
            "rule": "month_end_1",
            "bundle_ref": {"id": self.price["id"], "revision": 1},
            **updates,
        }

    def test_browser_arrays_or_pit_flags_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.create(self.spec(rows=[], pit_verified=True), "create-0001")

    def test_source_metadata_does_not_grant_pit_or_trading_qualification(self):
        study = self.service.create(self.spec(), "create-0001")
        result = self.service.preflight(study["id"])
        self.assertEqual(result["status"], "DATA_INELIGIBLE")
        self.assertIn("historical_point_in_time_not_verified", result["reasons"])

    def test_observed_calendar_produces_real_descriptive_results_and_failed_trials(self):
        study = self.service.create(self.spec(), "create-0001")
        run = self.service.analyze(study["id"], "analyze-0001")
        self.assertTrue(run["payload"]["summary"])
        self.assertEqual(run["payload"]["calendar_basis"], "observed_price_dates_only")
        self.assertEqual(run["payload"]["validation"]["status"], "DATA_INELIGIBLE")
        other = self.service.create(
            self.spec(family="holiday", rule="holiday_pre_5"), "create-holiday"
        )
        self.service.analyze(other["id"], "analyze-holiday")
        trials = self.records.list("trial")["items"]
        self.assertTrue(
            any(r["payload"].get("status") == "missing_or_insufficient_data" for r in trials)
        )
        self.assertEqual(run, self.service.analyze(study["id"], "analyze-0001"))

    def test_viewing_history_burns_its_untouched_test_status(self):
        study = self.service.create(self.spec(), "create-0001")
        self.service.analyze(study["id"], "analyze-0001")
        with self.assertRaisesRegex(StoreError, "range"):
            self.service.seal([study["id"]], "seal-0001")

    def test_family_cannot_omit_registered_failure(self):
        first = self.service.create(self.spec(), "create-0001")
        self.service.create(self.spec(hypothesis="another-registered-hypothesis"), "create-0002")
        with self.assertRaisesRegex(StudyError, "registered_trials_omitted"):
            self.service.seal([first["id"]], "seal-0001")

    def test_frozen_negative_family_returns_exact_idempotent_receipt(self):
        study = self.service.create(self.spec(), "create-0001")
        batch = self.service.seal([study["id"]], "seal-0001")
        result = self.service.evaluate(batch["id"], "evaluate-0001")
        report = result["items"][0]["payload"]["validation"]
        self.assertEqual(report["status"], "DATA_INELIGIBLE")
        self.assertEqual(result, self.service.evaluate(batch["id"], "evaluate-0001"))
        with self.assertRaisesRegex(StudyError, "reconciliation"):
            self.service.evaluate(batch["id"], "evaluate-0002")

    def test_host_callback_cannot_return_client_style_boolean_bundle(self):
        self.research.resolve_event_study_bundle = lambda ref: {"historical_eligible": True}
        with self.assertRaisesRegex(StudyError, "trusted_study_bundle_invalid"):
            self.service.create(self.spec(), "create-0001")

    def test_source_catalog_is_resolved_by_host(self):
        self.research.available_event_sources = lambda: {
            "items": [{"session_id": "owned", "dataset_id": "daily"}]
        }
        self.assertEqual(self.service.list()["source_choices"][0]["session_id"], "owned")

    def test_direction_and_exact_rule_are_frozen_before_formal_validation(self):
        with self.assertRaises(ValidationError):
            self.service.create(self.spec(direction=True), "invalid-direction")
        with self.assertRaises(ValidationError):
            self.service.create(self.spec(rule="holiday_pre_5"), "invalid-family-rule")
        study = self.service.create(self.spec(rule=None), "exploratory-family")
        with self.assertRaisesRegex(StudyError, "exact_registered_rule"):
            self.service.seal([study["id"]], "formal-seal-key")

    def test_stored_exports_are_deterministic_and_do_not_reopen_or_reanalyze(self):
        study = self.service.create(self.spec(), "create-0001")
        run = self.service.analyze(study["id"], "analyze-0001")
        count = len(self.records.ranges)
        first, kind = self.service.export(run["id"], "json")
        second, _ = self.service.export(run["id"], "json")
        self.assertEqual(first, second)
        self.assertEqual(kind, "application/json")
        self.assertEqual(len(self.records.ranges), count)
        self.assertTrue(json.loads(first)["payload"]["windows"][0]["formula"])
        self.assertEqual(self.service.runs(study["id"])["items"][0]["id"], run["id"])
        self.assertEqual(self.service.run(run["id"]), run)
        with self.assertRaises(StoreError):
            self.service.export("../../other-account", "json")

    def test_csv_uses_shared_formula_escape_and_source_summary_hides_private_paths(self):
        study = self.service.create(self.spec(), "create-0001")
        run = self.service.analyze(study["id"], "analyze-0001")
        self.records.rows["prices", self.price["id"]]["payload"][
            "private_path"
        ] = "/private/secret-owner"
        self.assertNotIn(
            "private_path", self.service._source_summary(StudySpec.model_validate(self.spec()))
        )
        payload = {
            **run["payload"],
            "windows": [{"episode": "=DANGEROUS()", "rule": "month_end_1", "return": "-0.01"}],
        }
        stored = self.records.create("study_run", payload, "formula-source-run")
        raw, kind = self.service.export(stored["id"], "csv")
        text = raw.decode("utf-8-sig")
        self.assertIn("'=DANGEROUS()", text)
        self.assertIn("-0.01", text)
        self.assertEqual(kind, "text/csv; charset=utf-8")

    def test_activity_is_cold_initialized_and_tracks_thread_until_actual_exit(self):
        entered, release = Event(), Event()

        def compute():
            with self.service.activity():
                entered.set()
                release.wait(2)

        self.assertFalse(self.service.active)

        worker = Thread(target=compute)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.service.active)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(self.service.active)
        with self.assertRaises(ValueError), self.service.activity():
            raise ValueError("synthetic failure")
        self.assertFalse(self.service.active)

    def test_restore_barrier_blocks_sealing_and_opening_before_any_claim(self):
        study = self.service.create(self.spec(), "create-restore-barrier")
        self.records.reconciliation_required = True
        with self.assertRaises(StoreError):
            self.service.seal([study["id"]], "restore-seal-key")
        self.assertEqual(self.records.ranges, [])
        self.records.reconciliation_required = False
        batch = self.service.seal([study["id"]], "restore-seal-key")
        self.records.reconciliation_required = True
        before = len(self.records.ranges)
        with self.assertRaises(StoreError):
            self.service.evaluate(batch["id"], "restore-evaluate-key")
        self.assertEqual(len(self.records.ranges), before)
        self.assertEqual(self.service.preflight(study["id"])["status"], "DATA_INELIGIBLE")

    def frozen_spec(
        self,
        index_id,
        start,
        end=None,
        precision="minute",
        published_at="2024-01-01T00:00:00Z",
        lifecycle="occurred",
    ):
        event = self.records.create(
            "event",
            {
                "admission": "confirmed",
                "date_precision": precision,
                "lifecycle": lifecycle,
                "category": "sports",
                "occurrence_start": start,
                "occurrence_end": end,
                "source_published_at": published_at,
            },
            f"timezone-event-{index_id}",
        )
        frozen = self.records.create(
            "freeze",
            {"event_refs": [{"id": event["id"], "revision": 1}], "evidence_refs": []},
            f"timezone-freeze-{index_id}",
        )
        spec = StudySpec.model_validate(
            self.spec(
                index_id=index_id,
                role="event_overlay",
                family="sports",
                rule="event_during",
                frozen_event_ref={"id": frozen["id"], "revision": 1},
            )
        )
        return spec, event

    def test_minute_event_projects_to_each_markets_local_date_without_rewriting_source(self):
        spec, original = self.frozen_spec("SP500", "2024-06-03T01:00:00Z", "2024-06-03T04:00:00Z")
        source_copy = json.loads(json.dumps(original))
        projected = self.service._frozen_events(spec)[0]
        self.assertEqual((projected["start"], projected["end"]), ("2024-06-02", "2024-06-03"))
        self.assertEqual(projected["market_timezone"], "America/New_York")
        self.assertEqual(projected["source_start_utc"], "2024-06-03T01:00:00+00:00")
        self.assertEqual(
            projected["source_occurrence_start"], original["payload"]["occurrence_start"]
        )
        self.assertEqual(self.records.get("event", original["id"]), source_copy)
        hk_spec, _ = self.frozen_spec("HSI", "2024-06-03T20:00:00Z", "2024-06-03T21:00:00Z")
        hk = self.service._frozen_events(hk_spec)[0]
        self.assertEqual((hk["start"], hk["end"]), ("2024-06-04", "2024-06-04"))
        self.assertEqual(hk["market_timezone"], "Asia/Hong_Kong")

    def test_day_precision_does_not_invent_midnight_or_month_first_day(self):
        spec, _ = self.frozen_spec("SP500", "2024-06-03", precision="day")
        projected = self.service._frozen_events(spec)[0]
        self.assertEqual(projected["start"], "2024-06-03")
        self.assertIsNone(projected["source_start_utc"])
        month, _ = self.frozen_spec("HSI", "2024-06", precision="month")
        with self.assertRaisesRegex(StudyError, "event_daily_window_ineligible"):
            self.service._frozen_events(month)

    def test_frozen_future_event_uses_exact_server_revision_capture_when_publication_unknown(self):
        spec, record = self.frozen_spec("SP500", "2027-06-01", precision="day", published_at=None)
        self.assertIsNone(self.service._frozen_events(spec)[0]["known_at"])
        self.records.revision_recorded_at = (
            lambda kind, identifier, revision: "2026-11-04T10:00:00Z"
        )
        projected = self.service._frozen_events(spec)[0]
        self.assertEqual(projected["known_at"], "2026-11-04T10:00:00+00:00")
        self.assertEqual(projected["revision"], record["revision"])

    def test_frozen_revised_date_receives_new_revision_known_floor(self):
        spec, record = self.frozen_spec("SP500", "2027-06-01", precision="day")
        self.records.revision_recorded_at = lambda kind, identifier, revision: {
            1: "2026-11-04T10:00:00Z",
            2: "2026-11-06T10:00:00Z",
        }[revision]
        original = self.service._frozen_events(spec)[0]
        updated = self.records.update(
            "event",
            record["id"],
            {
                **record["payload"],
                "occurrence_start": "2028-06-01",
                "first_observed": "1994-01-01T00:00:00Z",
            },
            1,
            "revised-event-date",
        )
        frozen = self.records.create(
            "freeze",
            {
                "event_refs": [{"id": updated["id"], "revision": updated["revision"]}],
                "evidence_refs": [],
            },
            "revised-event-freeze",
        )
        revised_spec = StudySpec.model_validate(
            {
                **spec.model_dump(mode="json"),
                "frozen_event_ref": {"id": frozen["id"], "revision": 1},
            }
        )
        revised = self.service._frozen_events(revised_spec)[0]
        self.assertEqual(revised["start"], "2028-06-01")
        self.assertGreater(revised["known_at"], original["known_at"])
        self.assertEqual(revised["known_at"], "2026-11-06T10:00:00+00:00")

    def test_ongoing_event_post_rule_is_ineligible_while_pre_rule_can_be_described(self):
        spec, _ = self.frozen_spec("SP500", "2020-03-01", precision="day", lifecycle="ongoing")
        post = spec.model_copy(update={"rule": "event_post_5"})
        study = self.service.create(post.model_dump(mode="json"), "ongoing-post-study")
        self.assertIn(
            "event_end_unknown_for_selected_window", self.service.preflight(study["id"])["reasons"]
        )
        with self.assertRaisesRegex(StudyError, "event_end_unknown_for_selected_window"):
            self.service.seal([study["id"]], "ongoing-post-seal")
        pre = spec.model_copy(update={"rule": "event_pre_5"})
        preceding = self.service.create(pre.model_dump(mode="json"), "ongoing-pre-study")
        run = self.service.analyze(preceding["id"], "ongoing-pre-analyze")
        self.assertEqual({window["rule"] for window in run["payload"]["windows"]}, {"event_pre_5"})


class RequestCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_request_preserves_busy_worker_witness(self):
        from app.research_web.event_studies.routes import operation

        selected = StudyService(SimpleNamespace())
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(research=SimpleNamespace(event_studies=selected))
            )
        )
        entered, release, finished = Event(), Event(), Event()

        def compute():
            entered.set()
            try:
                release.wait(2)
                return {"status": "done"}
            finally:
                finished.set()

        task = asyncio.create_task(operation(request, compute))
        try:
            for _ in range(200):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(entered.is_set())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(selected.active)
        finally:
            release.set()
            for _ in range(200):
                if finished.is_set() and not selected.active:
                    break
                await asyncio.sleep(0.01)
        self.assertTrue(finished.is_set())
        self.assertFalse(selected.active)
