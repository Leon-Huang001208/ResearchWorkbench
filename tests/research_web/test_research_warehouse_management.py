"""Warehouse profiles never connect on save or target the existing business port."""

import json
import time
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace


class WarehouseManagementTests(unittest.TestCase):
    def test_default_host_broker_captures_bounded_nav_with_semantic_gaps(self):
        import asyncio
        from unittest.mock import patch

        import httpx
        from test_api import NativeFixture

        from app.research_web.datahub import catalog, providers
        from app.research_web.datahub.contracts import BusinessQuery
        from app.research_web.datahub.research_warehouse import ResearchWarehouse
        from app.research_web.market_store import InMemoryMarketStore, MarketStoreError
        from app.research_web.mcp_registry.service import MCPRegistryService
        from app.research_web.service import ResearchService
        from app.research_web.store import Store, StoreError

        class Backend(InMemoryMarketStore):
            def bootstrap(self):
                pass

        async def exercise(root):
            backend = Backend()
            native = NativeFixture()
            with patch.object(ResearchWarehouse, "_postgres", staticmethod(lambda *_: backend)):
                host = ResearchService(
                    native,
                    Store(root),
                    mcp_registry=MCPRegistryService(root, keyring_backend=memory_keyring),
                    mcp_keyring_backend=memory_keyring,
                    delivery_keyring_backend=memory_keyring,
                )
            hub = host.datahub
            warehouse = hub.warehouse
            self.assertIsInstance(warehouse, ResearchWarehouse)
            saved = warehouse.save(
                {
                    "host": "127.0.0.1",
                    "database": "rwb_market_nav",
                    "username": "research",
                    "sslmode": "disable",
                }
            )
            warehouse.initialize(saved["profile_id"], "rwb_market_nav")
            sid = host.store.create("claw", "NAV capture")["id"]
            request = BusinessQuery(
                capability="fund_data",
                source="eastmoney_fund",
                purpose="display",
                quality="allow_stale",
                parameters={
                    "dataset": "nav",
                    "code": "510050",
                    "start_date": "2025-01-02",
                    "end_date": "2025-01-03",
                },
            )
            raw = json.dumps(
                {
                    "ErrCode": 0,
                    "Data": {
                        "LSJZList": [
                            {
                                "FSRQ": day,
                                "DWJZ": "1.23",
                                "LJJZ": "2.34",
                                "JZZZL": "0.5",
                                "FHSP": "",
                            }
                            for day in ("2025-01-03", "2025-01-02")
                        ]
                    },
                    "TotalCount": 2,
                    "PageIndex": 1,
                    "PageSize": 100,
                }
            ).encode()
            calls = []
            original_fetch = providers.fetch

            async def fetch(query, **kwargs):
                calls.append(query)
                if len(calls) > 1:
                    raise providers.ProviderError("vendor_call_blocked")
                return await original_fetch(
                    query, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=raw))
                )

            try:
                with patch.object(providers, "fetch", fetch):
                    first = await hub.query(sid, "nav-first", request)
                    second = await hub.query(sid, "nav-db-hit", request)
                    self.assertTrue(first["provider_metadata"]["warehouse_persisted"])
                    self.assertTrue(second["provider_metadata"]["warehouse_hit"])
                    self.assertEqual(second["row_count"], 2)
                    self.assertFalse(second["data_success"])
                    self.assertFalse(second["provider_metadata"]["quality_accepted"])
                    self.assertFalse(second["provider_metadata"]["formal_backtest_eligible"])
                    self.assertEqual(len(calls), 1)
                    old_digest = hub.source_configuration_digest("eastmoney_fund")
                    binding = warehouse._snapshot_series(request, "eastmoney_fund", old_digest)
                    with (
                        patch.object(catalog, "DISABLED", catalog.DISABLED | {"eastmoney_fund"}),
                        self.assertRaises(StoreError),
                    ):
                        await hub.query(sid, "nav-revoked", request)
                    self.assertEqual(len(calls), 1)
                    with patch.object(
                        hub.connections, "configuration_revision", return_value="new-source-epoch"
                    ):
                        self.assertNotEqual(
                            hub.source_configuration_digest("eastmoney_fund"), old_digest
                        )
                        self.assertIsNone(
                            warehouse.read(
                                request,
                                "eastmoney_fund",
                                hub.source_configuration_digest("eastmoney_fund"),
                            )
                        )
                        with self.assertRaises(StoreError):
                            hub._authorize_query(
                                sid,
                                request,
                                cached=True,
                                provider="eastmoney_fund",
                                authorization_fingerprint=old_digest,
                            )
                    warehouse.disable(saved["profile_id"])
                    with self.assertRaisesRegex(MarketStoreError, "warehouse_access_denied"):
                        binding[0].read(binding[1])
                self.assertFalse(any(method == "session.prompt" for method, _ in native.calls))
            finally:
                await hub.close()

        secrets = {}
        memory_keyring = SimpleNamespace(
            get_password=lambda service, account: secrets.get((service, account)),
            set_password=lambda service, account, value: secrets.__setitem__(
                (service, account), value
            ),
            delete_password=lambda service, account: secrets.pop((service, account), None),
        )
        with (
            TemporaryDirectory() as directory,
            patch(
                "app.research_web.datahub.connections.default_credential_backend",
                return_value=memory_keyring,
            ),
            patch(
                "app.research_web.credential_backend.SystemKeyringBackend.get_password",
                side_effect=AssertionError("host_credentials_forbidden"),
            ) as real_get,
            patch(
                "app.research_web.credential_backend.SystemKeyringBackend.set_password",
                side_effect=AssertionError("host_credentials_forbidden"),
            ) as real_set,
            patch(
                "app.research_web.credential_backend.SystemKeyringBackend.delete_password",
                side_effect=AssertionError("host_credentials_forbidden"),
            ) as real_delete,
            patch(
                "app.research_web.credential_backend.PrivateFileCredentialBackend.__init__",
                side_effect=AssertionError("host_credentials_forbidden"),
            ) as real_file_backend,
            patch("keyring.get_password", lambda service, account: secrets.get((service, account))),
            patch(
                "keyring.set_password",
                lambda service, account, value: secrets.__setitem__((service, account), value),
            ),
            patch(
                "keyring.delete_password",
                lambda service, account: secrets.pop((service, account), None),
            ),
        ):
            asyncio.run(exercise(Path(directory)))
            for ambient in (real_get, real_set, real_delete, real_file_backend):
                ambient.assert_not_called()

    def test_canonical_stock_identity_is_checked_before_any_source_commit(self):
        from app.research_web.datahub.contracts import BusinessQuery
        from app.research_web.datahub.providers import Result
        from app.research_web.datahub.research_warehouse import FIELDS, ResearchWarehouse
        from app.research_web.market_store import InMemoryMarketStore, MarketStoreError

        class Backend(InMemoryMarketStore):
            commits = 0

            def bootstrap(self):
                pass

            def commit_batch(self, *args):
                self.commits += 1
                return super().commit_batch(*args)

        backend = Backend()
        with TemporaryDirectory() as directory:
            warehouse = ResearchWarehouse(
                Path(directory),
                keyring=SimpleNamespace(get_password=lambda *_: None),
                backend_factory=lambda *_: backend,
            )
            status = warehouse.save(
                {
                    "host": "127.0.0.1",
                    "database": "rwb_market_identity",
                    "username": "research",
                    "sslmode": "disable",
                }
            )
            warehouse.initialize(status["profile_id"], "rwb_market_identity")
            warehouse._calendars.append(
                {
                    "start": date(2025, 1, 2),
                    "end": date(2025, 1, 2),
                    "days": {date(2025, 1, 2): True},
                    "hash": "b" * 64,
                    "cutoff": None,
                }
            )

            def request(asset, source, asset_type="stock"):
                return BusinessQuery(
                    capability="market_bars",
                    source=source,
                    parameters={
                        "asset": asset,
                        "asset_type": asset_type,
                        "frequency": "daily",
                        "adjustment": "none",
                        "start_date": "2025-01-02",
                        "end_date": "2025-01-02",
                    },
                )

            def result(asset):
                return Result(
                    status="complete",
                    rows=[
                        {
                            "asset": asset,
                            "date": "2025-01-02",
                            "open": 10.0,
                            "high": 10.0,
                            "low": 10.0,
                            "close": 10.0,
                            "volume": 100.0,
                            "turnover": 1000.0,
                        }
                    ],
                    fields=FIELDS,
                    raw=[b"original"],
                )

            for source in ("akshare", "baostock", "wind"):
                for asset in ("000001.SH", "510050.SH", "600000.SZ", "000001.BJ"):
                    with (
                        self.subTest(source=source, asset=asset),
                        self.assertRaisesRegex(
                            MarketStoreError, "^warehouse_security_identity_unverified$"
                        ),
                    ):
                        warehouse.ingest(request(asset, source), source, "a" * 64, result(asset))
            self.assertEqual(backend.commits, 0)
            for asset in ("600000.SH", "000001.SZ", "600519"):
                self.assertIsNotNone(
                    warehouse.ingest(request(asset, "akshare"), "akshare", "a" * 64, result(asset))
                )
            self.assertEqual(backend.commits, 3)
            for asset, kind in (("000001.SH", "index"), ("510050.SH", "etf")):
                self.assertIsNone(
                    warehouse._bridge(request(asset, "akshare", kind), "akshare", "a" * 64)
                )

    def test_raw_binding_preserves_rows_and_repeated_fill_version(self):
        from app.research_web.datahub.contracts import BusinessQuery
        from app.research_web.datahub.providers import Result
        from app.research_web.datahub.research_warehouse import FIELDS, ResearchWarehouse
        from app.research_web.market_store import InMemoryMarketStore

        class Backend(InMemoryMarketStore):
            def bootstrap(self):
                pass

        backend = Backend()
        keyring = SimpleNamespace(get_password=lambda *_args: None)
        with TemporaryDirectory() as directory:
            warehouse = ResearchWarehouse(
                Path(directory), keyring=keyring, backend_factory=lambda *_args: backend
            )
            status = warehouse.save(
                {
                    "host": "127.0.0.1",
                    "port": 55432,
                    "database": "rwb_market_isolated",
                    "username": "research",
                    "sslmode": "disable",
                }
            )
            warehouse.initialize(status["profile_id"], "rwb_market_isolated")
            warehouse._calendars.append(
                {
                    "start": date(2025, 1, 2),
                    "end": date(2025, 1, 3),
                    "days": {date(2025, 1, 2): True, date(2025, 1, 3): True},
                    "hash": "b" * 64,
                    "cutoff": None,
                    "expires": time.monotonic() + 60,
                }
            )
            query = BusinessQuery(
                capability="market_bars",
                source="akshare",
                parameters={
                    "asset": "000001.SZ",
                    "asset_type": "stock",
                    "frequency": "daily",
                    "adjustment": "none",
                    "start_date": "2025-01-02",
                    "end_date": "2025-01-03",
                },
            )
            rows = [
                {
                    "asset": "000001.SZ",
                    "date": day,
                    "open": 10.0,
                    "high": 12.0,
                    "low": 9.0,
                    "close": 11.0,
                    "volume": 1000.0,
                    "turnover": 11000.0,
                    "turnover_rate_pct": 2.0,
                }
                for day in ("2025-01-02", "2025-01-03")
            ]
            result = Result(
                status="complete", rows=rows, fields=FIELDS, raw=[json.dumps(rows).encode()]
            )
            first = warehouse.ingest(query, "akshare", "a" * 64, result)
            second = warehouse.ingest(query, "akshare", "a" * 64, result)
            self.assertEqual(first, second)
            self.assertEqual(warehouse.read(query, "akshare", "a" * 64).rows, rows)
            from dataclasses import replace
            from datetime import UTC, datetime

            from app.research_web.market_store import MarketStoreError

            unverified = replace(result, fields={})
            with self.assertRaisesRegex(MarketStoreError, "warehouse_units_unverified"):
                warehouse.ingest(query, "akshare", "a" * 64, unverified)
            self.assertIsNotNone(
                warehouse.ingest(
                    query.model_copy(update={"source": "tinysoft"}),
                    "tinysoft",
                    "b" * 64,
                    unverified,
                )
            )
            native = warehouse.read(
                query.model_copy(update={"source": "tinysoft", "as_of": datetime.now(UTC)}),
                "tinysoft",
                "b" * 64,
            )
            self.assertEqual(native.fields, {})
            self.assertFalse(native.metadata["formal_backtest_eligible"])
            self.assertFalse(native.metadata["quality_accepted"])
            warehouse.disable(status["profile_id"])
            self.assertIsNone(warehouse.read(query, "akshare", "a" * 64))

    def test_save_is_nonconnecting_and_password_is_not_in_profile(self):
        from app.research_web.datahub.research_warehouse import ResearchWarehouse

        values, calls = {}, []
        keyring = SimpleNamespace(
            get_password=lambda service, account: values.get((service, account)),
            set_password=lambda service, account, value: values.__setitem__(
                (service, account), value
            ),
            delete_password=lambda service, account: values.pop((service, account), None),
        )
        with TemporaryDirectory() as directory:
            warehouse = ResearchWarehouse(
                Path(directory),
                keyring=keyring,
                backend_factory=lambda profile, password: calls.append((profile, password)),
            )
            self.assertFalse(warehouse.status()["configured"])
            result = warehouse.save(
                {
                    "host": "127.0.0.1",
                    "port": 55432,
                    "database": "rwb_market_isolated",
                    "username": "research",
                    "password": "fixture-secret",
                    "sslmode": "disable",
                }
            )
            self.assertFalse(result["enabled"])
            self.assertEqual(calls, [])
            profile = next(Path(directory).rglob("warehouse.json")).read_text()
            self.assertNotIn("fixture-secret", profile)
            self.assertTrue(result["password_configured"])

    def test_existing_business_port_and_unrelated_database_are_rejected(self):
        from app.research_web.datahub.research_warehouse import WarehouseConfiguration

        for update in ({"port": 5432}, {"database": "business"}):
            with self.assertRaises(ValueError):
                WarehouseConfiguration.model_validate(
                    {
                        "host": "127.0.0.1",
                        "port": 55432,
                        "database": "rwb_market_isolated",
                        "username": "research",
                        "sslmode": "disable",
                        **update,
                    }
                )
