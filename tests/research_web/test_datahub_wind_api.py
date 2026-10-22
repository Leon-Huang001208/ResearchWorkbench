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
    build_weekly_data_contract,
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

    def test_missing_tail_is_explicit_and_interior_gap_is_rejected(self):
        sdk = FakeSDK()
        original = sdk.wsd

        def missing_tail(*args):
            result = original(*args)
            result.Data = [[100.0, None]]
            return result

        sdk.wsd = missing_tail
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        result = asyncio.run(provider.fetch(self.query()))
        self.assertEqual(result["rows"][-1]["date"], "2026-10-22")
        self.assertEqual(result["missing_dates"], ["2026-10-23"])
        self.assertIsNone(result["raw_payload"]["Data"][0][-1])

        def interior_gap(*args):
            result = original(*args)
            result.Data = [[None, 101.0]]
            return result

        sdk.wsd = interior_gap
        with self.assertRaisesRegex(Exception, "interior_or_all"):
            asyncio.run(provider.fetch(self.query()))

    def test_full_collector_ends_us_queries_at_last_closed_session(self):
        from datetime import date, timedelta

        from app.research_web.report_workflows.weekly_data import load_weekly_mapping

        def days(start, end):
            result = []
            current, last = date.fromisoformat(start), date.fromisoformat(end)
            while current <= last:
                if current.weekday() < 5:
                    result.append(datetime.combine(current, datetime.min.time()))
                current += timedelta(days=1)
            return result

        class CalendarSDK(FakeSDK):
            def tdays(self, start, end, options):
                return SimpleNamespace(
                    ErrorCode=0, Codes=[], Fields=["date"], Times=[], Data=[days(start, end)]
                )

            def wsd(self, asset, field, start, end, options):
                self.calls.append((asset, field, start, end, options))
                dates = days(start, end)
                return SimpleNamespace(
                    ErrorCode=0,
                    Codes=[asset],
                    Fields=[field.upper()],
                    Times=dates,
                    Data=[[100.0] * len(dates)],
                )

            def edb(self, asset, start, end, options):
                return self.wsd(asset, "close", start, end, options)

            def wset(self, *_args):
                return SimpleNamespace(
                    ErrorCode=0,
                    Codes=[],
                    Fields=["date", "country", "indicator", "importance"],
                    Times=[],
                    Data=[[datetime(2026, 10, 26)], ["合成市场"], ["合成事件"], ["重要"]],
                )

        calendars = {
            market: {
                "semantics_verified": True,
                "wind_calendar": "SSE",
                "timezone": "Asia/Shanghai",
                "close_time": "15:00",
            }
            for market in load_weekly_mapping()["calendars"]
        }
        calendars["US"] = {
            "semantics_verified": True,
            "wind_calendar": "NYSE",
            "timezone": "America/New_York",
            "close_time": "16:00",
        }
        economic = {
            "semantics_verified": True,
            "method": "wset",
            "dataset": "synthetic_calendar",
            "start_parameter": "startdate",
            "end_parameter": "enddate",
            "fields": {key: key for key in ("date", "country", "indicator", "importance")},
        }
        sdk = CalendarSDK()
        provider = WindClientAPIProvider(
            sdk_factory=lambda: sdk, calendar_contracts=calendars, economic_contract=economic
        )
        result = asyncio.run(
            provider.collect(build_weekly_data_contract("2026-10-23T15:30:00+08:00"))
        )
        self.assertEqual(result["assessment"]["issues"], ["weekly_api_equivalence_unverified"])
        us_assets = {
            spec["asset"] for spec in load_weekly_mapping()["series"] if spec["market"] == "US"
        }
        self.assertTrue(us_assets)
        self.assertTrue(all(call[3] == "2026-10-22" for call in sdk.calls if call[0] in us_assets))

    def test_economic_calendar_is_not_a_guessed_wset_call(self):
        sdk = FakeSDK()
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        request = self.query().model_copy(update={"kind": "economic_calendar", "series_id": None})
        with self.assertRaisesRegex(Exception, "economic_calendar_contract_unverified"):
            asyncio.run(provider.fetch(request))
        self.assertEqual(sdk.calls, [])

    def test_reviewed_calendar_and_economic_contract_have_a_real_sdk_path(self):
        sdk = FakeSDK()
        sdk.tdays = lambda *_args: SimpleNamespace(
            ErrorCode=0,
            Codes=[],
            Fields=["date"],
            Times=[],
            Data=[[datetime(2026, 10, 22), datetime(2026, 10, 23)]],
        )
        sdk.wset = lambda dataset, options: SimpleNamespace(
            ErrorCode=0,
            Codes=[],
            Fields=["date", "country", "indicator", "importance"],
            Times=[],
            Data=[[datetime(2026, 10, 26)], ["合成市场"], ["合成事件"], [3]],
        )
        provider = WindClientAPIProvider(
            sdk_factory=lambda: sdk,
            calendar_contracts={
                "CN": {
                    "semantics_verified": True,
                    "wind_calendar": "SSE",
                    "timezone": "Asia/Shanghai",
                    "close_time": "15:00",
                }
            },
            economic_contract={
                "semantics_verified": True,
                "method": "wset",
                "dataset": "synthetic_calendar",
                "start_parameter": "startdate",
                "end_parameter": "enddate",
                "fields": {key: key for key in ("date", "country", "indicator", "importance")},
                "importance_values": {"3": "重要"},
            },
        )
        calendar = asyncio.run(
            provider.fetch(
                WindAPIQuery(
                    kind="calendar",
                    market="CN",
                    start_date="2026-10-19",
                    end_date="2026-10-23",
                    cutoff="2026-10-23T15:30:00+08:00",
                )
            )
        )
        self.assertEqual(calendar["completed_dates"][-1], "2026-10-23")
        self.assertEqual(calendar["session_closes"]["2026-10-23"], "2026-10-23T15:00:00+08:00")
        economic = asyncio.run(
            provider.fetch(
                WindAPIQuery(
                    kind="economic_calendar",
                    start_date="2026-10-26",
                    end_date="2026-11-01",
                    cutoff="2026-10-23T15:30:00+08:00",
                )
            )
        )
        self.assertEqual(economic["events"][0]["importance"], "重要")

    def test_source_contract_must_match_published_resource_bytes(self):
        import hashlib
        import json

        from app.research_web.report_workflows.weekly_data import (
            MAPPING_SHA256,
            load_weekly_mapping,
        )
        from app.research_web.report_workflows.weekly_sources import (
            SOURCE_CONTRACT,
            load_run_source_contract,
        )

        config = {
            "schema_version": 1,
            "mapping_sha256": MAPPING_SHA256,
            "verification": {"status": "reviewed", "evidence_sha256": "c" * 64},
            "calendars": {
                market: {
                    "semantics_verified": True,
                    "wind_calendar": "SSE",
                    "timezone": "Asia/Shanghai",
                    "close_time": "15:00",
                }
                for market in load_weekly_mapping()["calendars"]
            },
            "economic_calendar": {
                "semantics_verified": True,
                "method": "wset",
                "dataset": "synthetic_calendar",
                "start_parameter": "startdate",
                "end_parameter": "enddate",
                "fields": {key: key for key in ("date", "country", "indicator", "importance")},
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "mappings").mkdir()
            raw = json.dumps(config).encode()
            target = root / SOURCE_CONTRACT
            target.write_bytes(raw)
            manifest = {
                "resources": [{"path": SOURCE_CONTRACT, "sha256": hashlib.sha256(raw).hexdigest()}]
            }
            loaded, identity = load_run_source_contract(root, manifest)
            self.assertEqual(loaded["economic_calendar"]["dataset"], "synthetic_calendar")
            self.assertEqual(identity, hashlib.sha256(raw).hexdigest())
            target.write_bytes(raw + b" ")
            with self.assertRaises(StoreError):
                load_run_source_contract(root, manifest)

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

    def test_report_contract_keeps_ordinary_excel_source_callable(self):
        from unittest.mock import patch

        import pandas as pd

        from app.research_web.datahub.broker import resolve
        from app.research_web.datahub.catalog import build_catalog
        from app.research_web.datahub.contracts import BusinessQuery
        from app.research_web.datahub.providers_wind import fetch

        class ExcelAdapter:
            def is_available(self):
                return True

            def fetch_daily_quotes(self, **_kwargs):
                return pd.DataFrame([{"code": "600519.SH", "date": "2026-10-21", "close": 1500.0}])

            def close(self):
                return None

        statuses = {"wind": {"configured": True, "preferred_adapter": "excel"}}
        ordinary = BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={
                "asset": "600519.SH",
                "asset_type": "stock",
                "start_date": "2026-10-21",
                "end_date": "2026-10-21",
            },
        )
        with patch(
            "app.research_web.datahub.catalog._dependency_status", return_value=(True, None)
        ):
            selected = resolve(ordinary, connection_statuses=statuses, environ={})
            before = next(
                item
                for item in build_catalog(connection_statuses=statuses, environ={})["sources"]
                if item["id"] == "wind"
            )
            with self.assertRaises(StoreError):
                resolve_report_weekly(self.query(), connection_statuses=statuses, environ={})
            private = resolve_report_weekly(
                self.query(),
                connection_statuses=statuses,
                environ={},
                report_contract_selected=True,
            )
            result = asyncio.run(fetch(selected.query, adapter=ExcelAdapter()))
            after = next(
                item
                for item in build_catalog(connection_statuses=statuses, environ={})["sources"]
                if item["id"] == "wind"
            )
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.rows[0]["close"], 1500.0)
        self.assertEqual(private.attempted_sources[0]["reason"], "published_report_contract")
        self.assertTrue(before["readiness"]["callable"])
        self.assertEqual(after["readiness"], before["readiness"])
        self.assertEqual(statuses["wind"]["preferred_adapter"], "excel")

    def test_report_api_uses_own_health_but_preserves_source_authorization(self):
        from unittest.mock import patch

        from app.research_web.datahub import catalog

        statuses = {"wind": {"configured": True, "preferred_adapter": "excel"}}
        probes = {"wind": {"health": "unavailable", "failure_code": "excel_missing"}}
        selected = resolve_report_weekly(
            self.query(),
            probes=probes,
            connection_statuses=statuses,
            environ={},
            report_contract_selected=True,
        )
        self.assertEqual(selected.provider_id, "wind")
        sdk = FakeSDK()
        provider = WindClientAPIProvider(sdk_factory=lambda: sdk)
        self.assertEqual(asyncio.run(provider.fetch(self.query()))["rows"][-1]["value"], 101.0)
        sdk.isconnected = lambda: False
        with self.assertRaisesRegex(Exception, "wind_api_not_logged_in"):
            asyncio.run(provider.fetch(self.query()))
        with patch.object(catalog, "DISABLED", {*catalog.DISABLED, "wind"}):
            with self.assertRaises(StoreError) as denied:
                resolve_report_weekly(
                    self.query(),
                    probes=probes,
                    connection_statuses=statuses,
                    environ={},
                    report_contract_selected=True,
                )
            self.assertEqual(denied.exception.code, "weekly_source_unavailable")
        for status in (
            {"configured": False, "preferred_adapter": "excel"},
            {"configured": True, "preferred_adapter": "excel", "credential_store_available": False},
        ):
            with self.assertRaises(StoreError):
                resolve_report_weekly(
                    self.query(),
                    connection_statuses={"wind": status},
                    environ={},
                    report_contract_selected=True,
                )

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

    def test_default_first_calibration_uses_real_workbooks_then_reuses_proof(self):
        import hashlib
        import json
        import runpy

        from app.research_web.datahub import DataHub
        from app.research_web.report_workflows.weekly_data import (
            MAPPING_SHA256,
            assess_weekly_snapshot,
            materialize_weekly_workbooks,
        )
        from app.research_web.report_workflows.weekly_sources import (
            SOURCE_CONTRACT,
            freeze_weekly_workbook_dates,
        )

        fixtures = runpy.run_path(str(Path(__file__).with_name("test_report_weekly_data.py")))
        synthetic_snapshot = fixtures["synthetic_snapshot"]
        contract = build_weekly_data_contract("2026-10-23T15:30:00+08:00")

        class SyntheticAPI:
            def __init__(self, *, different_history=False):
                self.different_history = different_history

            def readiness(self):
                return {"dependency_ready": True, "sdk_identity_sha256": "f" * 64}

            async def collect(self, contract, **_kwargs):
                snapshot = synthetic_snapshot(contract)
                snapshot["source"] = "wind_client_api"
                for series in snapshot["series"].values():
                    series["source"] = "wind_client_api"
                if self.different_history:
                    for series_id, series in snapshot["series"].items():
                        if series_id.startswith("history_"):
                            for row in series["rows"]:
                                row["value"] = "101"
                return {
                    "contract": contract,
                    "snapshot": snapshot,
                    "assessment": assess_weekly_snapshot(snapshot, contract),
                }

        async def run(root):
            store = Store(root)
            sid = store.create("claw", "first-calibration-fixture")["id"]
            run_id = "a" * 32
            store.session(sid)["report_workflow"] = {
                "workflow_id": "huaan-etf-weekly",
                "version": 1,
                "run_id": run_id,
            }
            run_root = root / "report-workflows" / "runs" / run_id
            (run_root / "workbooks").mkdir(parents=True)
            (run_root / "snapshots").mkdir()
            (run_root / "mappings").mkdir()
            snapshot = synthetic_snapshot(contract)
            (run_root / "snapshots/report-data.json").write_text(json.dumps(snapshot))
            fixtures["WeeklyDataTests"].make_workbooks(run_root)
            resources = [
                {"path": "workbooks/" + name}
                for name in ("周报数据.xlsx", "周报图表.xlsx", "全球经济日历.xlsx")
            ]
            manifest = {
                "workflow_id": "huaan-etf-weekly",
                "version": 1,
                "resources": resources,
                "weekly_production": {"policy_id": "huaan-etf-weekly-v1"},
            }
            materialize_weekly_workbooks(snapshot, run_root, manifest)
            config = {
                "schema_version": 1,
                "mapping_sha256": MAPPING_SHA256,
                "verification": {"status": "reviewed", "evidence_sha256": "c" * 64},
                "calendars": {
                    market: {
                        "semantics_verified": True,
                        "wind_calendar": "SSE",
                        "timezone": "Asia/Shanghai",
                        "close_time": "10:00",
                    }
                    for market in snapshot["calendars"]
                },
                "economic_calendar": {
                    "semantics_verified": True,
                    "method": "wset",
                    "dataset": "synthetic_calendar",
                    "start_parameter": "startdate",
                    "end_parameter": "enddate",
                    "fields": {key: key for key in ("date", "country", "indicator", "importance")},
                },
            }
            raw = json.dumps(config).encode()
            (run_root / SOURCE_CONTRACT).write_bytes(raw)
            resources.append({"path": SOURCE_CONTRACT, "sha256": hashlib.sha256(raw).hexdigest()})
            hub = DataHub(store)
            hub.connections.statuses = lambda: {
                "wind": {
                    "configured": True,
                    "preferred_adapter": "excel",
                    "credential_store_available": True,
                }
            }
            configuration = ["d" * 64]
            hub.source_configuration_digest = lambda _source: configuration[0]
            prepared = []

            async def prepare_excel():
                prepared.append(True)
                freeze_weekly_workbook_dates(run_root, manifest, contract)
                refreshes = run_root / "refresh-manifests"
                refreshes.mkdir(exist_ok=True)
                for logical in ("workbooks/周报数据.xlsx", "workbooks/周报图表.xlsx"):
                    sha = hashlib.sha256((run_root / logical).read_bytes()).hexdigest()
                    (
                        refreshes / (hashlib.sha256(logical.encode()).hexdigest() + ".json")
                    ).write_text(
                        json.dumps(
                            {
                                "status": "ready",
                                "provider": "wind_excel",
                                "workbook": logical,
                                "output_sha256": sha,
                            }
                        )
                    )
                return {"fixture_only": True}

            # No verification_receipts argument: exercise the actual default
            # branch, reading real fixture XLSX bytes rather than mocking capture.
            without_report_policy = {**manifest, "weekly_production": None}
            with self.assertRaises(StoreError) as disabled:
                await hub.collect_report_weekly(
                    sid,
                    "no-report-policy",
                    contract["cutoff"],
                    provider=SyntheticAPI(),
                    run_root=run_root,
                    manifest=without_report_policy,
                    prepare_excel=prepare_excel,
                )
            self.assertEqual(disabled.exception.code, "weekly_client_api_not_selected")
            self.assertEqual(prepared, [])
            first = await hub.collect_report_weekly(
                sid,
                "first",
                contract["cutoff"],
                provider=SyntheticAPI(),
                run_root=run_root,
                manifest=manifest,
                prepare_excel=prepare_excel,
            )
            self.assertEqual(first["assessment"]["issues"], [])
            self.assertEqual(first["assessment"]["status"], "passed")
            self.assertEqual(len(prepared), 1)
            next_contract = build_weekly_data_contract("2026-10-30T15:30:00+08:00")
            second = await hub.collect_report_weekly(
                sid,
                "second",
                next_contract["cutoff"],
                provider=SyntheticAPI(),
                run_root=run_root,
                manifest=manifest,
            )
            self.assertEqual(second["assessment"]["status"], "passed")
            self.assertEqual(len(prepared), 1)
            configuration[0] = "e" * 64
            with self.assertRaises(StoreError) as error:
                await hub.collect_report_weekly(
                    sid,
                    "changed",
                    next_contract["cutoff"],
                    provider=SyntheticAPI(),
                    run_root=run_root,
                    manifest=manifest,
                )
            self.assertEqual(error.exception.code, "weekly_calibration_required")
            mixed = await hub.collect_report_weekly(
                sid,
                "mixed",
                contract["cutoff"],
                provider=SyntheticAPI(different_history=True),
                run_root=run_root,
                manifest=manifest,
                prepare_excel=prepare_excel,
            )
            self.assertEqual(mixed["assessment"]["issues"], [])
            self.assertEqual(mixed["snapshot"]["source_groups"]["wind_excel"], ["history"])
            self.assertIn("domestic", mixed["snapshot"]["source_groups"]["wind_client_api"])
            self.assertEqual(
                mixed["snapshot"]["series"]["history_gold_london"]["rows"][0]["value"], "100.0"
            )
            await hub.close()

        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(run(Path(temporary)))


if __name__ == "__main__":
    unittest.main()
