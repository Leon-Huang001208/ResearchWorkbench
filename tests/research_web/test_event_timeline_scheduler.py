"""Synthetic clocks and transports verify source collection without public requests."""

import asyncio
import io
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.event_timeline import TimelineService
from app.research_web.event_timeline.scheduler import CollectionScheduler
from app.research_web.event_timeline.sources import endpoint
from app.research_web.store import Store, StoreError

BLS_HTML = b'<table class="regular-data"><tr><th>Release Date</th><th>Release Time</th></tr><tr><td>Jan. 13, 2026</td><td>08:30 AM</td></tr></table>'


class CollectionSchedulerTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="rwb-event-scheduler-")
        self.addCleanup(temporary.cleanup)
        self.research = SimpleNamespace(store=Store(Path(temporary.name).resolve() / "personal"))
        self.research.event_timeline = TimelineService(self.research)
        self.scheduler = CollectionScheduler(self.research)
        self.research.event_timeline.schedule_binder = self.scheduler.bind
        self.clock = datetime(2026, 5, 1, 12, tzinfo=UTC)

    def enable(self, source="bls_cpi"):
        row = self.research.event_timeline.schedule(
            source,
            {"enabled": True, "expected_revision": 1, "idempotency_key": "schedule-source-0001"},
        )
        return self.research.event_timeline.records.update(
            "source_schedule",
            row["id"],
            {**row["payload"], "next_due": "2026-05-01T00:00:00+00:00"},
            1,
            "schedule-clock-0001",
        )

    def test_constructor_and_disabled_reads_never_arm_or_fetch(self):
        self.assertFalse(self.research.event_timeline.records.folder.exists())
        asyncio.run(self.scheduler.tick(self.clock))
        self.assertFalse(self.research.event_timeline.records.folder.exists())
        self.assertTrue(
            all(
                not row["enabled"] for row in self.research.event_timeline.source_catalog()["items"]
            )
        )

    def test_first_source_schedule_concurrent_requests_are_unique_and_disable_stops_collection(
        self,
    ):
        events = self.research.event_timeline
        both_read = Barrier(2)
        first_finished = Event()

        def bind_after_both_reads(source, body):
            registration = self.scheduler.bind(source, body)
            both_read.wait(timeout=5)
            # Preserve both stale reads without racing the nonblocking retention lock.
            if body["idempotency_key"].endswith("0002") and not first_finished.wait(timeout=5):
                raise TimeoutError("first schedule request did not finish")
            return registration

        def configure(number):
            body = {
                "enabled": True,
                "expected_revision": 1,
                "idempotency_key": f"concurrent-schedule-{number:04d}",
            }
            try:
                return events.schedule("bls_cpi", body), body
            except StoreError as exc:
                return exc, body
            finally:
                if number == 1:
                    first_finished.set()

        with (
            patch.object(events, "schedule_binder", side_effect=bind_after_both_reads),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(executor.map(configure, [1, 2]))

        successful = [(result, body) for result, body in results if isinstance(result, dict)]
        errors = [result.code for result, _ in results if isinstance(result, StoreError)]
        rows = events.records.list("source_schedule")["items"]
        self.assertEqual(len(successful), 1)
        self.assertEqual(errors, ["event_record_exists"])
        self.assertEqual(len(rows), 1)
        original, request = successful[0]
        self.assertEqual(events.schedule("bls_cpi", request), original)

        for number, row in enumerate(rows):
            events.records.update(
                "source_schedule",
                row["id"],
                {**row["payload"], "next_due": "2026-05-01T00:00:00+00:00"},
                row["revision"],
                f"concurrent-schedule-due-{number:04d}",
            )
        current = events.records.list("source_schedule")["items"][0]
        disabled = events.schedule(
            "bls_cpi",
            {
                "enabled": False,
                "expected_revision": current["revision"],
                "idempotency_key": "concurrent-schedule-disable-0001",
            },
        )
        calls = []

        async def reader(source, year, page):
            calls.append(source)
            return endpoint(source, year, page), BLS_HTML

        async def run():
            await self.scheduler.tick(self.clock)
            await self.scheduler.wait_for_idle()

        events.fetcher = reader
        asyncio.run(run())
        self.assertFalse(disabled["payload"]["enabled"])
        self.assertFalse(self.scheduler.has_enabled())
        self.assertEqual(calls, [])
        self.assertEqual(events.records.list("event")["items"], [])

    def test_one_claim_per_due_and_latest_closed_gdelt_day(self):
        self.enable("gdelt")
        calls = []
        fields = ["" for _ in range(58)]
        fields[0], fields[1], fields[6], fields[16], fields[26] = (
            "123",
            "20260430",
            "Actor A",
            "Actor B",
            "010",
        )
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("20260430.export.CSV", "\t".join(fields))

        async def reader(source, year, page):
            calls.append((source, year, page))
            return endpoint(source, year, page), archive.getvalue()

        self.research.event_timeline.fetcher = reader

        async def run():
            await self.scheduler.tick(self.clock)
            await self.scheduler.wait_for_idle()
            await self.scheduler.tick(self.clock)
            await self.scheduler.wait_for_idle()

        asyncio.run(run())
        self.assertEqual(calls, [("gdelt", 2026, 119)])
        self.assertEqual(len(self.research.event_timeline.records.list("event")["items"]), 1)
        row = self.research.event_timeline.records.list("source_schedule")["items"][0]
        self.assertEqual(row["payload"]["collection_claim"]["state"], "completed")
        self.assertEqual(row["payload"]["interval_hours"], 1)

    def test_disable_during_fetch_refuses_publication_and_does_not_resend(self):
        row = self.enable()
        calls = []

        async def run():
            entered, release = asyncio.Event(), asyncio.Event()

            async def reader(source, year, page):
                calls.append(source)
                entered.set()
                await release.wait()
                return endpoint(source, year, page), BLS_HTML

            self.research.event_timeline.fetcher = reader
            await self.scheduler.tick(self.clock)
            await entered.wait()
            current = self.research.event_timeline.records.get("source_schedule", row["id"])
            self.research.event_timeline.schedule(
                "bls_cpi",
                {
                    "enabled": False,
                    "expected_revision": current["revision"],
                    "idempotency_key": "disable-source-0001",
                },
            )
            release.set()
            await self.scheduler.wait_for_idle()
            await self.scheduler.tick(self.clock)

        asyncio.run(run())
        self.assertEqual(calls, ["bls_cpi"])
        self.assertEqual(self.research.event_timeline.records.list("event")["items"], [])

    def test_unknown_claim_requires_reconciliation(self):
        row = self.enable()
        payload = {**row["payload"], "collection_claim": {"id": "unknown", "state": "claimed"}}
        self.research.event_timeline.records.update(
            "source_schedule", row["id"], payload, row["revision"], "unknown-source-0001"
        )

        async def forbidden(*args):
            raise AssertionError("unknown claim must not be retried")

        self.research.event_timeline.fetcher = forbidden
        asyncio.run(self.scheduler.tick(self.clock))
        self.assertEqual(self.research.event_timeline.records.list("source_job")["items"], [])
        with self.assertRaises(StoreError):
            asyncio.run(self.scheduler.tick(datetime(2026, 5, 1)))

    def test_ucdp_schedule_uses_only_declared_dataset_year(self):
        with self.assertRaises(StoreError):
            self.enable("ucdp")
        row = self.research.event_timeline.schedule(
            "ucdp",
            {"enabled": False, "expected_revision": 1, "idempotency_key": "disabled-ucdp-0001"},
        )
        request = self.scheduler._request(row, self.clock)
        self.assertEqual(request["year"], 2025)
        catalog = self.research.event_timeline.source_catalog()["items"]
        ucdp = next(source for source in catalog if source["id"] == "ucdp")
        self.assertEqual(ucdp["historical_end_year"], 2025)
        self.assertFalse(ucdp["future_supported"])
        self.assertTrue(ucdp["requires_token"])
        self.assertIn("page=1", endpoint("ucdp", 2025, 0))
        with self.assertRaises(StoreError):
            endpoint("ucdp", 2026)


if __name__ == "__main__":
    unittest.main()
