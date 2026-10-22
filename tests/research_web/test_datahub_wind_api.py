"""Wind Client API boundaries with injected SDK; no terminal or credential access."""

import asyncio
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.research_web.datahub.broker import resolve_report_weekly
from app.research_web.datahub.providers_wind_api import (
    WindAPIQuery,
    WindClientAPIProvider,
    activity_witness,
    wait_for_idle,
)
from app.research_web.report_workflows.weekly_data import (
    sample_snapshot,
)
from app.research_web.store import Store, StoreError


class FakeSDK:
    def __init__(self):
        self.calls = []

    def isconnected(self):
        return True

    def wsd(self, asset, field, start, end, options):
        self.calls.append((asset, field, start, end, options))
        return SimpleNamespace(
            ErrorCode=0,
            Codes=[asset],
            Fields=[field.upper()],
            Times=[datetime(2026, 10, 22), datetime(2026, 10, 23)],
            Data=[[100.0, 101.0]],
        )


class WindAPITests(unittest.TestCase):
    def query(self, series_id="domestic_000300"):
        return WindAPIQuery(
            kind="series",
            series_id=series_id,
            start_date="2026-10-19",
            end_date="2026-10-23",
            cutoff="2026-10-23T15:30:00+08:00",
        )

    def test_unknown_series_fails_before_sdk_factory(self):
        calls = []
        provider = WindClientAPIProvider(sdk_factory=lambda: calls.append(True))
        with self.assertRaisesRegex(ValueError, "series"):
            asyncio.run(provider.fetch(self.query("arbitrary_symbol")))
        self.assertEqual(calls, [])

    def test_closed_daily_request_preserves_raw_and_identity(self):
        sdk = FakeSDK()
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        result = asyncio.run(provider.fetch(self.query()))
        self.assertEqual(sdk.calls[0][0:2], ("000300.SH", "close"))
        self.assertEqual(result["rows"][-1]["value"], 101.0)
        self.assertEqual(result["source"], "wind_client_api")
        self.assertEqual(len(result["raw_sha256"]), 64)
        self.assertFalse(result["equivalence_verified"])

    def test_vendor_identity_mismatch_is_not_accepted(self):
        sdk = FakeSDK()
        original = sdk.wsd

        def mismatched(*args):
            result = original(*args)
            result.Codes = ["000905.SH"]
            return result

        sdk.wsd = mismatched
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        with self.assertRaisesRegex(Exception, "identity"):
            asyncio.run(provider.fetch(self.query()))

    def test_economic_calendar_is_not_a_guessed_wset_call(self):
        sdk = FakeSDK()
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        request = self.query().model_copy(update={"kind": "economic_calendar", "series_id": None})
        with self.assertRaisesRegex(Exception, "economic_calendar_contract_unverified"):
            asyncio.run(provider.fetch(request))
        self.assertEqual(sdk.calls, [])

    def test_timeout_keeps_capacity_until_real_vendor_returns(self):
        started, release = threading.Event(), threading.Event()
        sdk = FakeSDK()
        original = sdk.wsd

        def blocked(*args):
            started.set()
            release.wait(2)
            return original(*args)

        sdk.wsd = blocked
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk, deadline_seconds=0.01)

        async def run():
            try:
                with self.assertRaisesRegex(Exception, "wind_api_timeout"):
                    await provider.fetch(self.query())
                self.assertTrue(started.is_set())
                self.assertTrue(activity_witness()["active"])
                with self.assertRaisesRegex(Exception, "wind_api_busy"):
                    await provider.fetch(self.query())
            finally:
                release.set()
                await wait_for_idle()
            self.assertFalse(activity_witness()["active"])

        asyncio.run(run())

    def test_explicit_client_api_configuration_required_before_sdk(self):
        for statuses in ({}, {"wind": {"configured": True, "preferred_adapter": "excel"}}):
            with self.assertRaises(StoreError):
                resolve_report_weekly(self.query(), connection_statuses=statuses, environ={})

    def test_private_collector_reuses_snapshot_and_never_adds_a_dsh_tool(self):
        from app.research_web.datahub import DataHub
        from app.research_web.datahub.contracts import BUSINESS_TOOLS

        class FakeCollector:
            calls = 0

            def readiness(self):
                return {"dependency_ready": True}

            async def collect(self, contract, **_kwargs):
                self.calls += 1
                snapshot = sample_snapshot(contract)
                snapshot["limitations"] = ["synthetic_no_live_data"]
                return {
                    "contract": contract,
                    "snapshot": snapshot,
                    "assessment": {"status": "blocked_data", "issues": ["synthetic_no_live_data"]},
                }

        async def run(root):
            store = Store(root)
            sid = store.create("claw", "weekly-fixture")["id"]
            hub = DataHub(store)
            hub.connections.statuses = lambda: {
                "wind": {
                    "configured": True,
                    "preferred_adapter": "client_api",
                    "credential_store_available": True,
                }
            }
            hub.source_configuration_digest = lambda _source: "a" * 64
            adapter = FakeCollector()
            first = await hub.collect_report_weekly(
                sid, "weekly-1", "2026-10-23T15:30:00+08:00", provider=adapter
            )
            second = await hub.collect_report_weekly(
                sid, "weekly-1", "2026-10-23T15:30:00+08:00", provider=adapter
            )
            self.assertEqual(adapter.calls, 1)
            self.assertEqual(
                first["datasets"][0]["dataset_id"], second["datasets"][0]["dataset_id"]
            )
            self.assertEqual(second["assessment"]["status"], "blocked_data")
            other = store.create("claw", "copy-fixture")["id"]
            copied = hub.snapshots.copy_selected(sid, other, [first["datasets"][0]["dataset_id"]])
            self.assertEqual(copied[0]["query"]["capability"], "report_weekly")
            await hub.close()

        with tempfile.TemporaryDirectory() as root:
            asyncio.run(run(Path(root)))
        self.assertNotIn("report_weekly", BUSINESS_TOOLS)


if __name__ == "__main__":
    unittest.main()
