"""DBAPI contract tests; real PostgreSQL acceptance is a separate bounded gate."""

import copy
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from test_market_store import DATASET, SCOPE, batch, fact

from app.research_web.market_store import MarketStoreError, PostgresMarketStore


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, args=None):
        self.connection.calls.append((sql, args))
        if self.connection.fail_on and self.connection.fail_on in sql:
            raise RuntimeError("postgresql://secret:password@host/private")
        self.rows = []
        state = self.connection.pending
        if sql.startswith("SET TRANSACTION"):
            self.connection.pending = copy.deepcopy(self.connection.tables)
        elif sql.startswith("SELECT to_regclass"):
            self.rows = [(False, False)]
        elif sql.startswith("SELECT version FROM rwb_market_schema"):
            self.rows = [(2,)]
        elif sql.startswith("SELECT high_water_date"):
            row = state["heads"].get(tuple(args))
            self.rows = [row] if row else []
        elif sql.startswith("SELECT version_hash FROM rwb_market_batches"):
            row = state["batches"].get(tuple(args))
            self.rows = [(row[4],)] if row else []
        elif sql.startswith("SELECT EXISTS(SELECT 1 FROM jsonb_to_recordset"):
            incoming = json.loads(args[0])
            conflict = any(
                tuple(row[:2]) == tuple(args[1:3])
                and row[3] == item["logical_key"]
                and (row[7] or row[8]) == datetime.fromisoformat(item["ordering_at"])
                and row[8] == datetime.fromisoformat(item["ingested_at"])
                and json.loads(row[-1])["value_json"] != item["value_json"]
                for row in state["facts"].values()
                for item in incoming
            )
            self.rows = [(conflict,)]
        elif sql.startswith("INSERT INTO rwb_market_originals"):
            state["originals"].setdefault(tuple(args[:3]), args[3])
        elif sql.startswith("SELECT raw_hash FROM rwb_market_originals"):
            self.rows = [(h,) for h in args[2] if (*args[:2], h) in state["originals"]]
        elif sql.startswith("SELECT revision_key,fact_id,document"):
            self.rows = [
                (key, state["facts"][(*args[:2], key)][2], state["facts"][(*args[:2], key)][-1])
                for key in args[2]
                if (*args[:2], key) in state["facts"]
            ]
        elif sql.startswith("INSERT INTO rwb_market_facts"):
            state["facts"].setdefault((*args[:2], args[4]), args)
        elif sql.startswith("INSERT INTO rwb_market_batches"):
            state["batches"].setdefault(tuple(args[:3]), args)
        elif sql.startswith("INSERT INTO rwb_market_watermarks"):
            state["heads"][tuple(args[:2])] = (
                args[2],
                args[3],
                json.loads(args[4]),
                json.loads(args[5]),
            )
        elif sql.startswith("SELECT fact_id,document"):
            rows = [
                row
                for key, row in state["facts"].items()
                if key[:2] == tuple(args[:2]) and args[2] <= row[5] <= args[3]
            ]
            self.rows = [(row[2], json.loads(row[-1])) for row in rows]
        elif sql.startswith("SELECT count(*),COALESCE"):
            self.rows = [(0, self.connection.forced_result_bytes)]
        elif sql.startswith("SELECT COALESCE(sum"):
            payloads = [
                state["originals"][(*args[:2], h)]
                for h in args[2]
                if (*args[:2], h) in state["originals"]
            ]
            self.rows = [(sum(len(p) for p in payloads), len(payloads))]
        elif sql.startswith("SELECT raw_hash,payload"):
            self.rows = [
                (h, state["originals"][(*args[:2], h)])
                for h in args[2]
                if (*args[:2], h) in state["originals"]
            ]

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def close(self):
        pass


class Connection:
    def __init__(self):
        self.calls = []
        self.tables = {"heads": {}, "batches": {}, "facts": {}, "originals": {}}
        self.pending = copy.deepcopy(self.tables)
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0
        self.fail_on = None
        self.forced_result_bytes = 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.tables = self.pending
        self.commits += 1

    def rollback(self):
        self.pending = copy.deepcopy(self.tables)
        self.rollbacks += 1

    def close(self):
        self.closed += 1

    @property
    def documents(self):
        return list(self.tables["batches"].values())


class PostgresTests(unittest.TestCase):
    def test_conflicting_order_rolls_back_without_replacing_head(self):
        version = self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        with self.assertRaisesRegex(MarketStoreError, "ambiguous_revision_order"):
            self.store.commit_batch(SCOPE, DATASET, batch(fact(value="11", revision="other")))
        self.assertEqual(self.store.version(SCOPE, DATASET), version)
        self.assertEqual(len(self.connection.tables["facts"]), 1)

    def setUp(self):
        self.connection = Connection()
        self.store = PostgresMarketStore(lambda: self.connection)

    def test_no_implicit_bootstrap_on_read(self):
        self.store.version(SCOPE, DATASET)
        self.assertFalse(any("CREATE" in q for q, _ in self.connection.calls))
        self.store.bootstrap()
        self.assertTrue(any("CREATE TABLE" in q for q, _ in self.connection.calls))

    def test_transaction_and_parameterized_scope_and_watermark(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        queries = self.connection.calls
        self.assertTrue(any("pg_advisory_xact_lock" in q for q, _ in queries))
        self.assertTrue(any("INSERT INTO rwb_market_watermarks" in q for q, _ in queries))
        self.assertTrue(any("INSERT INTO rwb_market_batches" in q for q, _ in queries))
        for query, _ in queries:
            self.assertNotIn(SCOPE.owner_id, query)
            self.assertNotIn(SCOPE.key, query)
        self.assertEqual(self.connection.commits, 1)

    def test_failure_rolls_back_batch_and_does_not_expose_dsn(self):
        self.connection.fail_on = "INSERT INTO rwb_market_watermarks"
        with self.assertRaises(MarketStoreError) as raised:
            self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        self.assertNotIn("password", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)
        self.assertEqual(self.connection.documents, [])
        self.assertEqual(self.connection.rollbacks, 1)

    def test_replay_preserves_versions_and_originals(self):
        expected = self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        self.assertEqual(self.store.version(SCOPE, DATASET), expected)

    def test_reference_only_batch_survives_reverse_hash_order(self):
        from datetime import date

        from test_market_store_live_postgres import reverse_hash_reference_batch

        self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        second = reverse_hash_reference_batch()
        version = self.store.commit_batch(SCOPE, DATASET, second)
        self.assertEqual(self.store.version(SCOPE, DATASET), version)
        self.assertEqual(
            len(self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2)).facts), 2
        )
        self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))

    def test_restore_persists_frozen_manifest_in_same_transaction(self):
        from datetime import date

        from app.research_web.market_store import InMemoryMarketStore

        source = InMemoryMarketStore()
        source.commit_batch(SCOPE, DATASET, batch(fact()))
        frozen = source.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        self.connection.fail_on = "INSERT INTO rwb_market_frozen"
        with self.assertRaises(MarketStoreError):
            self.store.export_restore(SCOPE, frozen.export())
        self.assertEqual(self.connection.documents, [])
        self.assertEqual(self.connection.rollbacks, 1)

    def test_limits_apply_to_one_batch_not_accumulated_history(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        with patch("app.research_web.market_store.postgres.MAX_BATCH_FACTS", 1):
            self.store.commit_batch(SCOPE, DATASET, batch(fact(day=2)))
            with self.assertRaises(MarketStoreError):
                self.store.commit_batch(SCOPE, DATASET, batch(fact(day=3), fact(day=4)))
        self.assertEqual(len(self.connection.documents), 2)

    def test_range_and_version_queries_never_replay_batch_documents(self):
        from datetime import date

        self.store.version(SCOPE, DATASET)
        self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        queries = [q for q, _ in self.connection.calls]
        self.assertFalse(any("FROM rwb_market_batches" in q for q in queries))
        self.assertTrue(any("business_date>=%s AND business_date<=%s" in q for q in queries))

    def test_oversized_result_is_rejected_before_document_transfer(self):
        from datetime import date

        self.connection.forced_result_bytes = 33 * 1024 * 1024
        with self.assertRaisesRegex(MarketStoreError, "warehouse_result_limit_exceeded"):
            self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        self.assertFalse(
            any(q.startswith("SELECT fact_id,document") for q, _ in self.connection.calls)
        )


if __name__ == "__main__":
    unittest.main()
