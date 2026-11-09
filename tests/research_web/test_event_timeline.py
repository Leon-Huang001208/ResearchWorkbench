"""Synthetic contract tests do not certify live sources or historical PIT coverage."""

import asyncio
import hashlib
import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.research_web.event_timeline import TimelineService
from app.research_web.event_timeline.models import Create
from app.research_web.event_timeline.sources import endpoint, parse
from app.research_web.store import Store, StoreError

BLS_HTML = b'<table class="regular-data"><tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr><tr><td>December 2025</td><td>Jan. 13, 2026</td><td>08:30 AM</td></tr></table>'

# Actual official response excerpt, captured 2026-11-04; full response SHA256
# 005f9fd0196ab93581a53a3c73b11a216b981efa259f5ac06b03c6072ed4a1e3
# https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FED_ACTUAL_ROW = b'<h4>2026 FOMC Meetings</h4><div class="row fomc-meeting" ">\r\n        \r\n            <div class="fomc-meeting__month col-xs-5 col-sm-3 col-md-2"><strong>January</strong></div>\r\n                \r\n            <div class="fomc-meeting__date col-xs-4 col-sm-9 col-md-10 col-lg-1">27-28</div>\r\n            <div class="col-xs-12 col-md-4 col-lg-2">\r\n        \r\n               \r\n               <strong>Statement:</strong><br>\r\n               <a href="/monetarypolicy/files/monetary20260128a1.pdf">PDF</a> | <a href="/newsevents/pressreleases/monetary20260128a.htm">HTML</a><br>\r\n               \r\n                \r\n                <a href="/newsevents/pressreleases/monetary20260128a1.htm">Implementation Note</a>\r\n            </div>\r\n            <div class="col-xs-12 col-md-4 col-lg-3">\r\n                <a href="/monetarypolicy/fomcpressconf20260128.htm">Press Conference</a><br>\r\n                \r\n                <br>\r\n                <a href="/newsevents/pressreleases/monetary20260128b.htm">Statement on Longer-Run Goals and Monetary Policy Strategy</a>\r\n                \r\n            </div>\r\n            <div class="col-xs-12 col-md-4 col-lg-4 fomc-meeting__minutes">\r\n                \r\n                <strong>Minutes:</strong><br>\r\n                \r\n                <a href="/monetarypolicy/files/fomcminutes20260128.pdf">PDF</a> | <a href="/monetarypolicy/fomcminutes20260128.htm">HTML</a>\r\n                <br> (Released February 18, 2026)\r\n                \r\n                \r\n            </div>\r\n        </div>\r\n        \r\n\r\n\r\n\r\n\r\n        '


def service(tmp_path):
    return TimelineService(SimpleNamespace(store=Store(tmp_path / "personal")))


def draft(key="create-event-0001", **changes):
    return {
        "title": "公开会议",
        "category": "macro",
        "occurrence_start": "2026-06-01",
        "markets": ["CN", "US", "HK"],
        "idempotency_key": key,
        **changes,
    }


class EventTimelineTests(unittest.TestCase):

    def setUp(self):
        temporary = TemporaryDirectory(prefix="rwb-event-unit-")
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name).resolve()

    def test_lifecycle_admission_and_immutable_freeze(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        row = events.create(draft())
        assert events.create(draft()) == row
        assert row["payload"]["admission"] == "candidate"
        body = {
            "events": [{"id": row["id"], "revision": 1}],
            "label": "冻结样本",
            "idempotency_key": "freeze-event-0001",
        }
        with self.assertRaises(StoreError):
            events.freeze(body)
        decision = {
            "events": body["events"],
            "decision": "confirmed",
            "reason": "已核对",
            "idempotency_key": "confirm-event-0001",
        }
        confirmed = events.decide(decision)["items"][0]
        assert events.decide(decision)["items"][0] == confirmed
        frozen = events.freeze({**body, "events": [{"id": row["id"], "revision": 2}]})
        assert frozen["payload"]["formal_backtest_eligible"] is False
        revised = events.revise(
            row["id"],
            {
                **draft("revise-event-0001"),
                "occurrence_start": "2026-06-03",
                "expected_revision": 2,
                "reason": "日程延期",
            },
        )
        assert revised["payload"]["admission"] == "candidate"
        assert events.records.get("freeze", frozen["id"])["payload"]["events"][0] == confirmed

    def test_bulk_decision_is_atomic_and_stale_ref_refused(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        first, second = (events.create(draft()), events.create(draft("create-event-0002")))
        with self.assertRaises(StoreError):
            events.decide(
                {
                    "events": [
                        {"id": first["id"], "revision": 1},
                        {"id": second["id"], "revision": 2},
                    ],
                    "decision": "confirmed",
                    "reason": "审核",
                    "idempotency_key": "confirm-events-0001",
                }
            )
        assert events.records.get("event", first["id"])["revision"] == 1

    def test_raw_integrity_owner_and_freeze_checks(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        ref = events.archive_evidence(
            b"original", source="fed_fomc", url="https://www.federalreserve.gov/"
        )
        assert events.read_evidence(ref)["bytes"] == b"original"
        assert ref["sha256"] == hashlib.sha256(b"original").hexdigest()
        other = TimelineService(SimpleNamespace(store=Store(tmp_path / "other")))
        with self.assertRaises(StoreError):
            other.read_evidence(ref)
        (events.records.folder / "evidence" / ref["id"] / "raw.bin").write_bytes(b"modified")
        with self.assertRaises(StoreError):
            events.read_evidence(ref)

    def test_merge_and_split_retain_parent_versions(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        first, second = (events.create(draft()), events.create(draft("create-event-0002")))
        merge = {
            "events": [{"id": row["id"], "revision": 1} for row in (first, second)],
            "title": "同一场会议",
            "reason": "两报道指向相同事件",
            "idempotency_key": "merge-events-0001",
        }
        merged = events.merge(merge)
        assert events.merge(merge) == merged
        assert len(merged["event"]["payload"]["parent_refs"]) == 2
        assert events.records.get("event", first["id"], revision=1) == first
        child = {k: v for k, v in draft().items() if k != "idempotency_key"}
        split = events.split(
            merged["event"]["id"],
            {
                "children": [child, {**child, "occurrence_start": "2026-06-02"}],
                "expected_revision": 1,
                "reason": "实际为两场会议",
                "idempotency_key": "split-events-0001",
            },
        )
        assert len(split["children"]) == 2
        assert all(row["payload"]["admission"] == "candidate" for row in split["children"])

    def test_client_cannot_supply_trust_or_unknown_time(self):
        for value in (
            {"admission": "confirmed"},
            {"owner_binding": "foreign"},
            {"formal_backtest_eligible": True},
            {"source_published_at": "1990-01-01"},
            {"date_precision": "minute", "occurrence_start": "2026-06-01T12:00:00"},
        ):
            with self.assertRaises(ValueError):
                Create.model_validate(draft(**value))

    def test_timeline_filters_and_default_source_state(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        events.create(draft())
        assert len(events.timeline(market="CN")["items"]) == 1
        assert not events.timeline(market="JP")["items"]
        assert all(row["enabled"] is False for row in events.source_catalog()["items"])
        assert events.coverage()["complete"] is False
        with self.assertRaises(StoreError):
            events.schedule(
                "fed_fomc",
                {
                    "enabled": True,
                    "interval_hours": 24,
                    "expected_revision": 1,
                    "idempotency_key": "schedule-source-0001",
                },
            )

    def test_fixed_endpoints_and_bounded_synthetic_parsers(self):
        assert endpoint("gdelt", 1990) == "https://data.gdeltproject.org/events/1990.zip"
        assert endpoint("gdelt", 2014, 1).endswith("20140102.export.CSV.zip")
        assert endpoint("gdelt", 2013, 3).endswith("20130401.export.CSV.zip")
        with self.assertRaises(StoreError):
            endpoint("https://localhost/")
        html = b'<h4>2026 FOMC Meetings</h4><div class="fomc-meeting"><div class="fomc-meeting__month">June</div><div class="fomc-meeting__date">16-17*</div></div>'
        parsed = parse("fed_fomc", html)
        assert parsed["events"][0]["occurrence_start"] == "2026-06-16"
        assert parsed["events"][0]["occurrence_end"] == "2026-06-17"
        assert parsed["historical_pit"] is False
        assert parse("bls_cpi", BLS_HTML)["events"][0]["source_published_at"] is None
        with self.assertRaises(StoreError):
            parse("bls_cpi", b"<html>Access denied</html>")

    def test_refresh_is_explicit_idempotent_and_preserves_failure(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        calls = []

        async def reader(source, year, page):
            calls.append(source)
            return (endpoint(source, year, page), BLS_HTML)

        events.fetcher = reader
        assert events.source_catalog() and (not calls)
        body = {"source": "bls_cpi", "idempotency_key": "refresh-source-0001"}
        result = asyncio.run(events.refresh(body))
        assert result["payload"]["state"] == "completed"
        assert asyncio.run(events.refresh(body)) == result
        assert calls == ["bls_cpi"]
        assert events.records.list("event")["items"][0]["payload"]["admission"] == "candidate"
        assert events.coverage()["complete"] is False
        events.fetcher = lambda *_: (_ for _ in ()).throw(
            StoreError("unavailable", "test_failure", 503)
        )
        failed = asyncio.run(events.refresh({**body, "idempotency_key": "refresh-source-0002"}))
        assert failed["payload"]["state"] == "failed"
        assert len(events.records.list("event")["items"]) == 1

    def test_backup_manifest_does_not_write_and_restore_verifies_bytes(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        row = events.create(draft())
        events.archive_evidence(
            b"original", source="fed_fomc", url="https://www.federalreserve.gov/"
        )
        before = set(events.records.root.rglob("*"))
        manifest = events.records.snapshot()
        assert manifest["record_count"] == 1
        assert before == set(events.records.root.rglob("*"))
        backed = events.records.backup_to(tmp_path / "backup")
        events.records.path.unlink()
        events.records.restore_from(tmp_path / "backup", expected_sha256=backed["sha256"])
        assert events.records.get("event", row["id"]) == row
        self.assertTrue(events.records.qualification_status()["required"])
        with self.assertRaises(StoreError):
            events.records.claim_study_ranges(
                [
                    {
                        "scope": "SP500",
                        "start": "2030-01-01",
                        "end": "2030-12-31",
                        "phase": "sealed",
                        "batch_id": "after-unknown-restore",
                    }
                ],
                "after-restore-claim-0001",
            )
        with self.assertRaises(StoreError):
            events.records.claim_once("holdout", "after-unknown-restore", {"attempt": 1})
        (tmp_path / "backup" / "metadata.sqlite3").write_bytes(b"broken")
        with self.assertRaises(StoreError):
            events.records.restore_from(tmp_path / "backup", expected_sha256=backed["sha256"])

    def test_holdout_overlaps_are_atomic_but_disjoint_future_is_allowed(self):
        tmp_path = self.tmp_path
        events = service(tmp_path)
        row = {
            "scope": "SP500",
            "start": "2020-01-01",
            "end": "2020-12-31",
            "phase": "viewed",
            "batch_id": "research",
        }
        events.records.claim_study_ranges([row], "range-viewed-0001")
        events.records.claim_study_ranges(
            [{**row, "batch_id": "research-two"}], "range-viewed-0002"
        )
        with self.assertRaises(StoreError):
            events.records.claim_study_ranges(
                [{**row, "phase": "sealed", "batch_id": "validation"}], "range-sealed-0001"
            )
        future = {
            **row,
            "start": "2021-01-01",
            "end": "2021-12-31",
            "phase": "sealed",
            "batch_id": "validation",
        }
        events.records.claim_study_ranges([future], "range-sealed-0002")
        events.records.claim_study_ranges([{**future, "phase": "opened"}], "range-opened-0001")
        with self.assertRaises(StoreError):
            events.records.claim_study_ranges([{**future, "phase": "opened"}], "range-opened-0002")

    def test_bls_only_release_date_column_is_an_event(self):
        body = b"<footer>Last modified January 20, 2026</footer>" + BLS_HTML
        body += b"<table><tr><td>January 22, 2026</td></tr></table>"
        parsed = parse("bls_cpi", body)
        self.assertEqual([row["occurrence_start"] for row in parsed["events"]], ["2026-01-13"])
        with self.assertRaises(StoreError):
            parse("bls_cpi", b"<footer>January 20, 2026</footer>")

    def test_ucdp_uncertain_dates_remain_intervals(self):
        rows = [
            {
                "id": 1,
                "country": "A",
                "date_start": "2020-01-01",
                "date_end": "2020-01-31",
                "date_prec": 3,
            },
            {
                "id": 2,
                "country": "B",
                "date_start": "2020-02-01",
                "date_end": "2020-02-01",
                "date_prec": 2,
            },
            {
                "id": 3,
                "country": "C",
                "date_start": "2020-03-01",
                "date_end": "2020-03-01",
                "date_prec": 1,
            },
        ]
        events = parse("ucdp", json.dumps({"Result": rows}).encode())["events"]
        self.assertEqual([row["date_precision"] for row in events], ["interval", "unknown", "day"])
        self.assertEqual(events[0]["occurrence_end"], "2020-01-31")
        self.assertFalse(events[0]["event_time_eligible"])
        self.assertIsNone(events[1]["exact_occurrence_date"])
        self.assertTrue(events[2]["event_time_eligible"])

    def test_backup_destination_cannot_overlap_account_or_alias(self):
        events = service(self.tmp_path)
        events.create(draft())
        before = set(events.records.root.rglob("*"))
        for destination in (
            events.records.folder / "backup",
            events.records.root / "backup",
            events.records.root.parent,
        ):
            with self.assertRaises(StoreError):
                events.records.backup_to(destination)
        alias = self.tmp_path / "alias"
        alias.symlink_to(events.records.folder, target_is_directory=True)
        with self.assertRaises(StoreError):
            events.records.backup_to(alias / "nested")
        self.assertEqual(before, set(events.records.root.rglob("*")))

    def test_threaded_import_keeps_active_lease_until_cancel_drains(self):
        events = service(self.tmp_path)
        entered, release = threading.Event(), threading.Event()
        process = events._process_source
        worker_threads = []

        def delayed(*args):
            worker_threads.append(threading.get_ident())
            entered.set()
            if not release.wait(2):
                raise AssertionError("test worker did not receive release")
            return process(*args)

        async def reader(source, year, page):
            return endpoint(source, year, page), BLS_HTML

        events._process_source = delayed
        events.fetcher = reader

        async def run():
            task = asyncio.create_task(
                events.refresh({"source": "bls_cpi", "idempotency_key": "cancel-source-0001"})
            )
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            self.assertNotEqual(worker_threads[0], threading.get_ident())
            task.cancel()
            await asyncio.sleep(0)
            self.assertTrue(events.active)
            self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(run())
        self.assertFalse(events.active)
        self.assertEqual(events.records.list("event")["items"], [])
        self.assertEqual(
            events.records.list("source_job")["items"][0]["payload"]["state"], "interrupted"
        )

    def test_restore_cannot_erase_opened_holdout_or_idempotency_history(self):
        events = service(self.tmp_path)
        row = {
            "scope": "SP500",
            "start": "2020-01-01",
            "end": "2020-12-31",
            "phase": "sealed",
            "batch_id": "validation",
        }
        events.records.claim_study_ranges([row], "restore-sealed-0001")
        backup = events.records.backup_to(self.tmp_path / "before-opening")
        opened = events.records.claim_study_ranges(
            [{**row, "phase": "opened"}], "restore-opened-0001"
        )
        events.records.claim_once("holdout", "compute:validation", {"used": True})
        with self.assertRaises(StoreError) as error:
            events.records.restore_from(
                self.tmp_path / "before-opening", expected_sha256=backup["sha256"]
            )
        self.assertEqual(error.exception.code, "event_restore_history_rollback")
        self.assertEqual(
            events.records.claim_study_ranges([{**row, "phase": "opened"}], "restore-opened-0001"),
            opened,
        )
        with self.assertRaises(StoreError):
            events.records.claim_study_ranges([{**row, "phase": "opened"}], "restore-opened-0002")
        with self.assertRaises(StoreError):
            events.records.claim_once("holdout", "compute:validation", {"used": True})
        self.assertFalse(events.records.qualification_status()["required"])

    def test_elapsed_calendar_dates_do_not_confirm_occurrence(self):
        events = parse("bls_cpi", BLS_HTML)["events"]
        self.assertEqual(events[0]["lifecycle"], "announced")
        self.assertEqual(events[0]["occurrence_evidence"], "schedule_only")
        fed = parse(
            "fed_fomc",
            b'<h4>2020 FOMC Meetings</h4><div class="fomc-meeting"><div class="fomc-meeting__month">January</div><div class="fomc-meeting__date">28-29</div></div>',
        )["events"]
        self.assertEqual(fed[0]["lifecycle"], "announced")

    def test_actual_fed_row_excludes_minutes_release_and_footer_dates(self):
        rows = parse("fed_fomc", FED_ACTUAL_ROW)["events"]
        self.assertEqual(
            [(row["occurrence_start"], row["occurrence_end"]) for row in rows],
            [("2026-01-27", "2026-01-28")],
        )
        self.assertEqual(rows[0]["lifecycle"], "announced")
        self.assertIsNone(rows[0]["source_published_at"])


if __name__ == "__main__":
    unittest.main()
