"""Actual provider evidence stays separate from probes, cached data and authority."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.datahub import DataHub
from app.research_web.datahub.broker import Resolution
from app.research_web.datahub.contracts import BusinessQuery, Query
from app.research_web.datahub.providers import ProviderError, Result
from app.research_web.datahub.storage_activity import StorageRunner
from app.research_web.store import Store, StoreError


class ExecutionHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_external_inventory_never_verifies_remote_source(self):
        for parameters in ({}, {"dataset": "catalog"}):
            query = BusinessQuery(
                capability="external_data", source="ext_fred", parameters=parameters
            )
            result = await self.hub._fetch_with_execution_health(self.sid, query, self.digest)
            self.assertTrue(result.rows)
            self.assertEqual(self.hub._latest_execution_health(), {})

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name))
        self.sid = self.store.create("claw", "execution health")["id"]
        self.clock, self.digest, self.allowed = 0.0, "a" * 64, True
        self.hub = DataHub(
            self.store,
            monotonic_clock=lambda: self.clock,
            probe_ttl_seconds=30,
            max_retained_probes=2,
        )
        self.hub.source_configuration_digest = lambda _: self.digest
        self.query = BusinessQuery(
            capability="financials", source="akshare", parameters={"asset": "000001.SZ"}
        )

        def authorize(sid, query, **kwargs):
            if not self.allowed:
                raise StoreError("revoked", "data_capability_unavailable", 503)
            return Resolution(query.source, query, [])

        self.hub._authorize_query = authorize

    async def asyncTearDown(self):
        await self.hub.close()

    async def fetch(self, result=None, query=None, error=None):
        async def provider(*args, **kwargs):
            if error is not None:
                raise error
            return result or Result(rows=[{"metric": 1}], status="complete")

        request = query or self.query
        with patch("app.research_web.datahub.providers.fetch", provider):
            return await self.hub._execute_business(
                self.sid, "call", request, Resolution(request.source, request, [])
            )

    async def test_success_is_capability_scoped_and_never_becomes_a_probe(self):
        await self.fetch()
        evidence = self.hub._latest_execution_health()["akshare"]
        self.assertEqual([item["capability"] for item in evidence], ["financials"])
        self.assertEqual(evidence[0]["status"], "success")
        self.assertFalse(evidence[0]["cache_validates_upstream"])
        self.assertEqual(self.hub._latest_probes(), {})
        self.assertNotIn("market_bars", json.dumps(evidence))

    async def test_catalog_connection_center_retains_probe_and_execution_boundaries(self):
        await self.fetch()
        descriptor = {
            "id": "akshare",
            "name": "AKShare",
            "auth_type": "none",
            "readiness": {
                "configured": True,
                "integration_completed": True,
                "callable": True,
                "health": "untested",
            },
        }
        with patch(
            "app.research_web.datahub.build_catalog",
            side_effect=lambda **kwargs: {"sources": [{**descriptor}]},
        ):
            center = self.hub.connection_center()
            source = center["sources"][0]
            self.assertEqual(source["probe_status"], "untested")
            self.assertTrue(source["execution_verified"])
            self.assertEqual(source["execution_scope"], "listed_capabilities_only")
            self.assertEqual(source["execution_evidence"][0]["capability"], "financials")
            self.clock = 30
            expired = self.hub.connection_center()["sources"][0]
            self.assertFalse(expired["execution_verified"])
            self.assertEqual(expired["execution_evidence"], [])

    async def test_revoked_authority_or_changed_configuration_drops_evidence(self):
        await self.fetch()
        self.allowed = False
        self.assertEqual(self.hub._latest_execution_health(), {})
        self.allowed = True
        await self.fetch()
        self.digest = "b" * 64
        self.assertEqual(self.hub._latest_execution_health(), {})

    async def test_configuration_changed_during_actual_call_not_recorded(self):
        async def changed(*args, **kwargs):
            self.digest = "b" * 64
            return Result(rows=[{"metric": 1}], status="complete")

        with (
            patch("app.research_web.datahub.providers.fetch", changed),
            self.assertRaises(StoreError),
        ):
            await self.hub._execute_business(
                self.sid, "call", self.query, Resolution("akshare", self.query, [])
            )
        self.assertEqual(self.hub._latest_execution_health(), {})

    async def test_translated_legacy_provider_query_uses_original_business_capability(self):
        business = BusinessQuery(
            capability="fund_data",
            source="eastmoney_fund",
            parameters={"dataset": "nav", "code": "000001"},
        )
        translated = Query(source="fund_nav", code="000001")

        async def provider(request, **kwargs):
            self.assertIsInstance(request, Query)
            return Result(rows=[{"nav": 1}], status="complete")

        with patch("app.research_web.datahub.providers.fetch", provider):
            await self.hub._execute_business(
                self.sid, "translated", business, Resolution("eastmoney_fund", translated, [])
            )
        evidence = self.hub._latest_execution_health()["eastmoney_fund"][0]
        self.assertEqual(evidence["capability"], "fund_data")
        self.assertEqual(evidence["status"], "success")

    async def test_authority_read_error_hides_evidence_without_disclosing_exception(self):
        await self.fetch()
        self.hub.source_configuration_digest = lambda _: (_ for _ in ()).throw(
            RuntimeError("private endpoint secret")
        )
        self.assertEqual(self.hub._latest_execution_health(), {})

    async def test_ttl_and_bounded_history(self):
        await self.fetch()
        self.clock = 29
        self.assertIn("akshare", self.hub._latest_execution_health())
        self.clock = 30
        self.assertEqual(self.hub._latest_execution_health(), {})
        for capability in ("financials", "market_activity", "index_data"):
            await self.fetch(query=BusinessQuery(capability=capability, source="akshare"))
        self.assertEqual(len(self.hub._execution_health), 2)

    async def test_partial_failed_empty_and_missing_never_mark_success(self):
        for status, missing, expected in (
            ("partial", [], "partial"),
            ("failed", [], "failed"),
            ("empty", [], "empty"),
            ("complete", ["metric"], "partial"),
        ):
            await self.fetch(
                Result(
                    rows=[{"metric": 1}],
                    status=status,
                    missing=missing,
                    limitations=["secret-token-text"],
                )
            )
            evidence = self.hub._latest_execution_health()["akshare"][0]
            self.assertEqual(evidence["status"], expected)
            self.assertNotIn("secret-token-text", json.dumps(evidence))
            self.assertIn(
                evidence["failure_code"], {"provider_error", "provider_partial", "provider_empty"}
            )

    async def test_unknown_provider_exception_diagnostics_are_fixed_and_redacted(self):
        with self.assertRaises(ProviderError):
            await self.fetch(error=ProviderError("account=secret password=hidden"))
        evidence = self.hub._latest_execution_health()["akshare"][0]
        self.assertEqual(evidence["failure_code"], "provider_error")
        self.assertNotIn("secret", json.dumps(evidence))

    async def test_session_cache_and_receipt_do_not_refresh_upstream_evidence(self):
        calls = []

        async def provider(*args, **kwargs):
            calls.append(1)
            return Result(rows=[{"metric": 1}], raw=[b"{}"], status="complete")

        with patch("app.research_web.datahub.providers.fetch", provider):
            await self.hub.query(self.sid, "initial", self.query)
            before = self.hub._latest_execution_health()
            self.clock = 15
            await self.hub.query(self.sid, "initial", self.query)
            await self.hub.query(self.sid, "cached", self.query)
        self.assertEqual(calls, [1])
        self.assertEqual(self.hub._latest_execution_health(), before)
        self.clock = 30
        self.assertEqual(self.hub._latest_execution_health(), {})

    async def test_warehouse_hit_does_not_create_upstream_evidence(self):
        self.hub.warehouse = SimpleNamespace(
            read=lambda *args: Result(
                rows=[{"metric": 1}], status="complete", metadata={"warehouse_hit": True}
            )
        )
        self.hub.storage_runner = StorageRunner()
        with patch(
            "app.research_web.datahub.providers.fetch", side_effect=AssertionError("no upstream")
        ):
            await self.hub.query(self.sid, "warehouse", self.query)
        self.assertEqual(self.hub._latest_execution_health(), {})
