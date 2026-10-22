"""Warehouse profiles never connect on save or target the existing business port."""

import json
import time
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace


class WarehouseManagementTests(unittest.TestCase):
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
