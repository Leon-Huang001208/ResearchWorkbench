"""Deterministic runtime fallback and backward-compatible query contracts."""

import asyncio
import hashlib
import json
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError, Result


class QueryPolicyTests(unittest.TestCase):
    def test_default_policy_preserves_existing_business_fingerprint(self):
        query = BusinessQuery(capability="market_bars", parameters={"asset": "000001.SZ"})
        legacy = {
            "capability": "market_bars",
            "source": "auto",
            "allow_fallback": False,
            "parameters": {"asset": "000001.SZ"},
        }
        expected = hashlib.sha256(
            json.dumps(["business-1.0.0", legacy], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        self.assertEqual(query.fingerprint(), expected)

    def test_display_policy_changes_fingerprint_and_cannot_relax_research(self):
        query = BusinessQuery(capability="financials", purpose="display", quality="allow_stale")
        self.assertEqual(query.purpose, "display")
        self.assertNotEqual(
            query.fingerprint(), BusinessQuery(capability="financials").fingerprint()
        )
        with self.assertRaises(ValueError):
            BusinessQuery(capability="financials", purpose="backtest", quality="allow_stale")


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_close_cancellation_waits_before_draining_other_owners(self):
        from types import SimpleNamespace

        from app.research_web.datahub import DataHub
        from app.research_web.store import Store

        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def sdk(_sources):
            entered.set()
            await release.wait()

        async def wind():
            calls.append("wind_api")

        async def storage():
            calls.append("storage")

        with tempfile.TemporaryDirectory() as root:
            hub = DataHub(Store(Path(root)))
            hub.storage_runner = SimpleNamespace(close=storage)
            with (
                patch("app.research_web.datahub.worker_activity.drain_sources", sdk),
                patch("app.research_web.datahub.providers_wind_api.wait_for_idle", wind),
            ):
                closing = asyncio.create_task(hub.close())
                await entered.wait()
                for _ in range(2):
                    closing.cancel()
                    await asyncio.sleep(0)
                self.assertFalse(closing.done())
                self.assertEqual(calls, [])
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await closing
            self.assertEqual(calls, ["wind_api", "storage"])

    async def test_close_drains_independent_resources_even_when_sdk_witness_fails(self):
        from types import SimpleNamespace

        from app.research_web.datahub import DataHub
        from app.research_web.store import Store

        calls = []

        async def sdk(sources):
            calls.append(("sdk", tuple(sources)))
            raise ProviderError("provider_cleanup_unconfirmed")

        async def wind():
            calls.append(("wind_api",))

        async def storage():
            calls.append(("storage",))

        with tempfile.TemporaryDirectory() as root:
            hub = DataHub(Store(Path(root)))
            hub.storage_runner = SimpleNamespace(close=storage)
            with (
                patch("app.research_web.datahub.worker_activity.drain_sources", sdk),
                patch("app.research_web.datahub.providers_wind_api.wait_for_idle", wind),
                self.assertRaisesRegex(ProviderError, "provider_cleanup_unconfirmed"),
            ):
                await hub.close()
            self.assertEqual(len([call for call in calls if call[0] == "sdk"]), 4)
            self.assertIn(("wind_api",), calls)
            self.assertIn(("storage",), calls)

    async def test_deadline_drains_storage_without_turning_into_user_cancel(self):
        import time

        from app.research_web.datahub.reliability import execute
        from app.research_web.datahub.storage_activity import StorageRunner

        runner = StorageRunner()

        async def fetch(_candidate):
            await runner.run(time.sleep, 0.04)
            return Result(status="complete")

        try:
            result, _ = await execute(
                resolve=lambda _: "one", fetch=fetch, source_id=lambda value: value, budget=0.005
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.limitations, ["deadline"])
            self.assertFalse(runner.active)
        finally:
            await runner.close()

    async def test_shared_deadline_bounds_all_attempts(self):
        from app.research_web.datahub.reliability import execute

        calls = []

        async def fetch(candidate):
            calls.append(candidate)
            await asyncio.sleep(0.1)
            return Result(status="complete")

        result, _ = await execute(
            resolve=lambda _: "one", fetch=fetch, source_id=lambda value: value, budget=0.01
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.limitations, ["deadline"])
        self.assertEqual(calls, ["one"])

    async def test_failed_result_switches_source_and_keeps_audit(self):
        from app.research_web.datahub.reliability import execute

        called = []

        async def fetch(candidate):
            called.append(candidate)
            return (
                Result(status="failed", limitations=["vendor_unreachable"])
                if candidate == "one"
                else Result(status="complete", rows=[{"value": 1}])
            )

        def resolve(excluded):
            return next((s for s in ["one", "two"] if s not in excluded), None)

        result, selected = await execute(
            resolve=resolve, fetch=fetch, source_id=lambda value: value
        )
        self.assertEqual(called, ["one", "two"])
        self.assertEqual(selected, "two")
        self.assertEqual(result.status, "complete")
        self.assertEqual([a["source"] for a in result.attempted_sources], called)

    async def test_cancellation_and_sensitive_failure_never_trigger_retry(self):
        from app.research_web.datahub.reliability import execute

        for failure in [asyncio.CancelledError(), ProviderError("credential_reflected")]:
            calls = []

            async def fetch(candidate, calls=calls, failure=failure):
                calls.append(candidate)
                raise failure

            with self.assertRaises(type(failure)):
                await execute(resolve=lambda _: "one", fetch=fetch, source_id=lambda value: value)
            self.assertEqual(calls, ["one"])

    async def test_empty_is_a_valid_terminal_result(self):
        from app.research_web.datahub.reliability import execute

        calls = []

        async def fetch(candidate):
            calls.append(candidate)
            return Result(status="empty", pagination_complete=True)

        result, _ = await execute(
            resolve=lambda _: "one", fetch=fetch, source_id=lambda value: value
        )
        self.assertEqual(result.status, "empty")
        self.assertEqual(calls, ["one"])

    async def test_no_reissue_when_resolver_returns_an_exhausted_source(self):
        from app.research_web.datahub.reliability import execute

        calls = []

        async def fetch(candidate):
            calls.append(candidate)
            return Result(status="failed", limitations=["provider_busy"])

        result, _ = await execute(
            resolve=lambda _: "one", fetch=fetch, source_id=lambda value: value
        )
        self.assertEqual(calls, ["one"])
        self.assertEqual(result.status, "failed")


class HealthTests(unittest.TestCase):
    def test_circuit_is_configuration_scoped_and_recovers_after_cooldown(self):
        from app.research_web.datahub.reliability import CircuitBreaker

        now = [0.0]
        health = CircuitBreaker(clock=lambda: now[0], threshold=2, cooldown=10)
        key = ("source", "market_bars", "config-1")
        health.record(key, accepted=False, code="vendor_unreachable")
        self.assertTrue(health.available(key))
        health.record(key, accepted=False, code="vendor_unreachable")
        self.assertFalse(health.available(key))
        self.assertTrue(health.available(("source", "market_bars", "config-2")))
        now[0] = 11
        self.assertTrue(health.available(key))
        health.record(key, accepted=True, code=None)
        self.assertEqual(health.snapshot()[0]["failures"], 0)


class WorkerWitnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_akshare_and_wind_workers_remain_active_until_real_completion(self):
        from app.research_web.datahub import worker_activity

        for source in ("akshare", "wind"):
            future = Future()
            with patch.object(
                worker_activity, "source_futures", lambda _, future=future: (future,)
            ):
                task = asyncio.create_task(worker_activity.drain_sources({source}))
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                future.set_result(None)
                await task

    async def test_cleanup_uncertainty_is_not_reported_as_idle(self):
        from app.research_web.datahub import providers_wind, worker_activity

        with patch.object(providers_wind, "_WIND_POISONED", True), self.assertRaises(ProviderError):
            worker_activity.active_futures()


class DataHubExecutionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from app.research_web.datahub import DataHub
        from app.research_web.datahub.broker import Resolution
        from app.research_web.store import Store, StoreError

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))
        self.sid = self.store.create("claw", "runtime execution")["id"]
        self.hub = DataHub(self.store)
        self.hub.source_configuration_digest = lambda _: "a" * 64

        def authorize(sid, query, **kwargs):
            excluded = kwargs.get("excluded_sources", frozenset())
            candidates = [query.source] if query.source != "auto" else ["tinysoft", "wind"]
            for source in candidates:
                if source not in excluded:
                    return Resolution(
                        source,
                        query.model_copy(update={"source": source}),
                        [{"source": source, "status": "selected", "reason": None}],
                    )
            raise StoreError("没有可用来源", "data_capability_unavailable", 503)

        self.hub._authorize_query = authorize

    async def asyncTearDown(self):
        await self.hub.close()

    async def test_foreground_deadline_returns_while_storage_keeps_real_capacity(self):
        import threading
        from types import SimpleNamespace

        from app.research_web.datahub.storage_activity import StorageRunner
        from app.research_web.store import StoreError

        entered, release = threading.Event(), threading.Event()

        def slow_read(*_args):
            entered.set()
            release.wait(2)

        self.hub.warehouse = SimpleNamespace(read=slow_read)
        self.hub.storage_runner = StorageRunner()
        with (
            patch("app.research_web.datahub.TOTAL_DEADLINE", 0.01),
            self.assertRaises(StoreError) as error,
        ):
            await self.hub.query(
                self.sid, "bounded-storage", BusinessQuery(capability="market_bars", source="wind")
            )
        self.assertTrue(entered.is_set())
        self.assertEqual(error.exception.code, "data_query_deadline")
        self.assertTrue(self.hub.storage_runner.active)
        owned = self.hub.tasks[(self.sid, "bounded-storage")]
        self.assertFalse(owned.done())
        release.set()
        await asyncio.gather(owned, return_exceptions=True)
        self.assertFalse(self.hub.storage_runner.active)
        receipt = self.hub.snapshots.receipt(self.sid, "bounded-storage")
        self.assertEqual(receipt["failure_code"], "deadline")

    async def test_runtime_failure_uses_backup_and_preserves_idempotency(self):
        calls = []

        async def fetch(query, **_kwargs):
            calls.append(query.source)
            return (
                Result(status="failed", limitations=["vendor_unreachable"])
                if query.source == "tinysoft"
                else Result(status="complete", rows=[{"date": "2026-01-02", "close": 1}])
            )

        query = BusinessQuery(
            capability="market_bars",
            parameters={
                "asset": "000001.SZ",
                "asset_type": "stock",
                "frequency": "1d",
                "adjustment": "none",
            },
        )
        with patch("app.research_web.datahub.providers.fetch", fetch):
            result = await self.hub.query(self.sid, "fallback", query)
            repeated = await self.hub.query(self.sid, "fallback", query)
        self.assertEqual(calls, ["tinysoft", "wind"])
        self.assertEqual(result["provider"], "wind")
        self.assertTrue(result["data_success"])
        self.assertEqual(result["dataset_id"], repeated["dataset_id"])
        self.assertEqual(len(result["provider_metadata"]["execution_attempts"]), 2)

    async def test_explicit_source_and_historical_time_are_never_silently_changed(self):
        from app.research_web.store import StoreError

        calls = []

        async def fetch(query, **_kwargs):
            calls.append(query.source)
            return Result(status="failed", limitations=["vendor_unreachable"])

        with patch("app.research_web.datahub.providers.fetch", fetch):
            result = await self.hub.query(
                self.sid, "fixed", BusinessQuery(capability="financials", source="wind")
            )
            self.assertFalse(result["data_success"])
            with self.assertRaises(StoreError) as error:
                await self.hub.query(
                    self.sid,
                    "pit",
                    BusinessQuery(capability="financials", as_of="2020-01-01T00:00:00Z"),
                )
        self.assertEqual(calls, ["wind"])
        self.assertEqual(error.exception.code, "data_pit_unavailable")


if __name__ == "__main__":
    unittest.main()
