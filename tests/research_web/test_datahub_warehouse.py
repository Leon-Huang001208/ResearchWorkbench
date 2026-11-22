"""Warehouse-first routing never turns incomplete or unauthorized history into a hit."""

import json
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.market_store import (
    Batch,
    DatasetIdentity,
    Fact,
    InMemoryMarketStore,
    MarketStoreService,
    RawOriginal,
    StoreScope,
)


class WarehouseBridgeTests(unittest.TestCase):
    def setUp(self):
        from app.research_web.datahub.warehouse import WarehouseBinding, WarehouseBridge

        self.allowed = True
        self.backend = InMemoryMarketStore()
        service = MarketStoreService(self.backend, lambda *_: self.allowed)
        self.scope = StoreScope("alice", "personal", "wind", "a" * 64)
        self.dataset = DatasetIdentity(
            "market_bars", "000001.SZ", "CN", "daily", "CNY/share", "none", "raw-v1", "b" * 64
        )
        self.expected = (date(2026, 1, 2), date(2026, 1, 5))

        def normalize(result, previous):
            known = {f.revision_key: f for f in previous.facts}
            facts, originals = [], []
            for row in result.rows:
                original = RawOriginal(json.dumps(row, sort_keys=True).encode())
                new = Fact(
                    "close",
                    date.fromisoformat(row["date"]),
                    "daily",
                    json.dumps(row["close"]),
                    datetime(2026, 1, 6, tzinfo=UTC),
                    datetime(2026, 1, 7, tzinfo=UTC),
                    original.sha256,
                    original.sha256,
                )
                facts.append(known.get(new.revision_key, new))
                originals.append(original)
            return Batch(tuple(facts), tuple(originals))

        self.bridge = WarehouseBridge(
            service,
            lambda query, source, digest: WarehouseBinding(
                "alice", self.scope, self.dataset, self.expected, normalize
            ),
        )
        self.query = BusinessQuery(
            capability="market_bars",
            source="wind",
            parameters={"asset": "000001.SZ", "start_date": "2026-01-02", "end_date": "2026-01-05"},
        )

    def test_requires_complete_expected_calendar_and_current_authority(self):
        self.assertIsNone(self.bridge.read(self.query, "wind", "a" * 64))
        self.bridge.ingest(
            self.query,
            "wind",
            "a" * 64,
            Result(status="complete", rows=[{"date": "2026-01-02", "close": 1}]),
        )
        self.assertIsNone(self.bridge.read(self.query, "wind", "a" * 64))
        self.bridge.ingest(
            self.query,
            "wind",
            "a" * 64,
            Result(status="complete", rows=[{"date": "2026-01-05", "close": 2}]),
        )
        hit = self.bridge.read(self.query, "wind", "a" * 64)
        self.assertEqual([row["close"] for row in hit.rows], [1, 2])
        self.assertTrue(hit.metadata["warehouse_hit"])
        self.allowed = False
        with self.assertRaises(ValueError):
            self.bridge.read(self.query, "wind", "a" * 64)

    def test_configuration_change_and_unknown_pit_cannot_bypass_policy(self):
        with self.assertRaises(ValueError):
            self.bridge.read(self.query, "wind", "c" * 64)
        self.bridge.ingest(
            self.query,
            "wind",
            "a" * 64,
            Result(
                status="complete",
                rows=[{"date": "2026-01-02", "close": 1}, {"date": "2026-01-05", "close": 2}],
            ),
        )
        past = self.query.model_copy(
            update={"as_of": datetime(2026, 1, 5, tzinfo=UTC), "purpose": "backtest"}
        )
        self.assertIsNone(self.bridge.read(past, "wind", "a" * 64))

    def test_repeated_ingestion_preserves_original_revision_and_version(self):
        result = Result(status="complete", rows=[{"date": "2026-01-02", "close": 1}])
        first = self.bridge.ingest(self.query, "wind", "a" * 64, result)
        second = self.bridge.ingest(self.query, "wind", "a" * 64, result)
        self.assertEqual(first, second)

    def test_gap_planner_checks_internal_days_and_refreshes_revisions(self):
        query = self.query.model_copy(
            update={
                "parameters": {**self.query.parameters, "frequency": "daily", "adjustment": "none"}
            }
        )
        self.bridge.ingest(
            query,
            "wind",
            "a" * 64,
            Result(status="complete", rows=[{"date": "2026-01-05", "close": 2}]),
        )
        plans = self.bridge.missing_queries(query, "wind", "a" * 64)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].parameters["start_date"], "2026-01-02")
        self.assertEqual(plans[0].parameters["end_date"], "2026-01-02")
        self.assertFalse(plans[0].allow_fallback)
        self.assertIsNone(
            self.bridge.missing_queries(
                query.model_copy(update={"refresh": True}), "wind", "a" * 64
            )
        )
        self.allowed = False
        with self.assertRaises(ValueError):
            self.bridge.missing_queries(query, "wind", "a" * 64)


class DataHubWarehouseTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_gap_cannot_publish_complete_empty_window(self):
        from app.research_web.datahub import DataHub
        from app.research_web.datahub.broker import Resolution
        from app.research_web.store import Store

        fixture = WarehouseBridgeTests()
        fixture.setUp()
        query = fixture.query.model_copy(
            update={
                "parameters": {
                    **fixture.query.parameters,
                    "frequency": "daily",
                    "adjustment": "none",
                }
            }
        )
        fixture.bridge.ingest(
            query,
            "wind",
            "a" * 64,
            Result(status="complete", rows=[{"date": "2026-01-02", "close": 1}]),
        )
        with TemporaryDirectory() as directory:
            store = Store(Path(directory))
            sid = store.create("claw", "incomplete gap")["id"]
            hub = DataHub(store, warehouse=fixture.bridge)
            hub.source_configuration_digest = lambda _: "a" * 64
            hub._authorize_query = lambda _sid, query, **_kwargs: Resolution("wind", query, [])
            requested = []

            async def fetch(query, **_kwargs):
                requested.append(query.parameters["start_date"])
                return Result(status="empty", pagination_complete=True)

            try:
                with patch("app.research_web.datahub.providers.fetch", fetch):
                    result = await hub.query(sid, "empty-gap", query)
                self.assertEqual(requested, ["2026-01-05"])
                self.assertEqual(result["status"], "partial")
                self.assertFalse(result["data_success"])
                self.assertIsNone(fixture.bridge.read(query, "wind", "a" * 64))
                stored = fixture.backend.read_range(
                    fixture.scope, fixture.dataset, *fixture.bridge._window(query)
                )
                self.assertEqual(len(stored.facts), 1)
            finally:
                await hub.close()

    async def test_real_datahub_reads_store_before_fetch_and_preserves_pit_boundary(self):
        from app.research_web.datahub import DataHub
        from app.research_web.datahub.broker import Resolution
        from app.research_web.store import Store, StoreError

        fixture = WarehouseBridgeTests(
            "test_requires_complete_expected_calendar_and_current_authority"
        )
        fixture.setUp()
        with TemporaryDirectory() as directory:
            store = Store(Path(directory))
            sid = store.create("claw", "warehouse")["id"]
            hub = DataHub(store, warehouse=fixture.bridge)
            hub.source_configuration_digest = lambda _: "a" * 64
            hub._authorize_query = lambda _sid, query, **kwargs: Resolution(
                "wind",
                query.model_copy(update={"source": "wind"}),
                [{"source": "wind", "status": "selected", "reason": None}],
            )
            calls = []

            async def fetch(query, **kwargs):
                calls.append(query.source)
                return Result(
                    status="complete",
                    rows=[{"date": "2026-01-02", "close": 1}, {"date": "2026-01-05", "close": 2}],
                )

            try:
                with patch("app.research_web.datahub.providers.fetch", fetch):
                    first = await hub.query(sid, "initial", fixture.query)
                    second = await hub.query(sid, "from-database", fixture.query)
                    as_of = fixture.query.model_copy(
                        update={"as_of": datetime(2026, 1, 7, tzinfo=UTC), "purpose": "backtest"}
                    )
                    history = await hub.query(sid, "known-at-time", as_of)
                    self.assertTrue(first["provider_metadata"]["warehouse_persisted"])
                    self.assertTrue(second["provider_metadata"]["warehouse_hit"])
                    self.assertTrue(history["provider_metadata"]["historical_point_in_time"])
                    self.assertEqual(calls, ["wind"])
                    fixture.allowed = False
                    with self.assertRaises(StoreError):
                        await hub.query(sid, "revoked", fixture.query)
                    self.assertEqual(calls, ["wind"])
            finally:
                await hub.close()


if __name__ == "__main__":
    unittest.main()
