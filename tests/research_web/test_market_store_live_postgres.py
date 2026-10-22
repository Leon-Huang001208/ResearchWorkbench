"""Opt-in disposable PostgreSQL acceptance, strictly private Unix sockets.

RWB_MARKET_STORE_LIVE_PG=1 enables an OWNED tempfile cluster. Existing services,
TCP listeners, external disks and production configuration are never touched.
Requires already installed initdb/pg_ctl and psycopg; installs nothing.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from test_market_store import DATASET, SCOPE, at, batch, fact

from app.research_web.market_store import (
    Batch,
    CoverageProof,
    MarketStoreCancelled,
    MarketStoreError,
    OperationContext,
    PostgresMarketStore,
    RawOriginal,
    operation_context,
)
from app.research_web.market_store.models import batch_document, canonical, digest


def reverse_hash_reference_batch():
    original_hash = digest(canonical(batch_document(batch(fact()))))
    for index in range(1000):
        candidate = Batch((fact(day=2, revision=f"rev-{index}"),), ())
        if digest(canonical(batch_document(candidate))) < original_hash:
            return candidate
    raise AssertionError("reverse hash fixture not found")


class HookConnection:
    """Fault/cancellation injection around a real owned DBAPI connection."""

    def __init__(self, real, *, after_execute=None, after_commit=None):
        self.real = real
        self.after_execute = after_execute
        self.after_commit = after_commit

    def __getattr__(self, name):
        return getattr(self.real, name)

    def cursor(self):
        outer = self

        class HookCursor:
            def __init__(self):
                self.real = outer.real.cursor()

            def __getattr__(self, name):
                return getattr(self.real, name)

            def execute(self, statement, parameters=None):
                result = self.real.execute(statement, parameters)
                if outer.after_execute:
                    outer.after_execute(statement)
                return result

        return HookCursor()

    def commit(self):
        self.real.commit()
        if self.after_commit:
            self.after_commit()


@unittest.skipUnless(
    os.environ.get("RWB_MARKET_STORE_LIVE_PG") == "1",
    "explicit disposable PostgreSQL gate not enabled",
)
class LivePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg

        cls.psycopg = psycopg
        cls.initdb = shutil.which("initdb")
        cls.pg_ctl = shutil.which("pg_ctl")
        if not cls.initdb or not cls.pg_ctl:
            raise RuntimeError("PostgreSQL test binaries unavailable")
        cls.temporary = tempfile.TemporaryDirectory(prefix="rwb-market-pg-")
        cls.root = Path(cls.temporary.name)
        cls.data = cls.root / "data"
        cls.socket = cls.root / "socket"
        cls.socket.mkdir(mode=0o700)
        cls.port = 65473  # Private directory isolates socket; listen_addresses is empty.
        cls.started = False
        try:
            cls.run_pg(
                [cls.initdb, "-D", str(cls.data), "--auth=trust", "--no-locale", "-E", "UTF8"]
            )
            cls.start()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def run_pg(cls, args):
        result = subprocess.run(args, capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise RuntimeError("disposable_postgres_command_failed")

    @classmethod
    def start(cls):
        options = f"-h '' -k {cls.socket} -p {cls.port} -c shared_buffers=16MB -c max_connections=8 -c max_wal_size=64MB -c min_wal_size=32MB"
        cls.run_pg(
            [
                cls.pg_ctl,
                "-D",
                str(cls.data),
                "-o",
                options,
                "-l",
                str(cls.root / "postgres.log"),
                "-w",
                "-t",
                "15",
                "start",
            ]
        )
        cls.started = True

    @classmethod
    def tearDownClass(cls):
        if cls.started:
            cls.run_pg([cls.pg_ctl, "-D", str(cls.data), "-m", "fast", "-w", "stop"])
            cls.started = False
        cls.temporary.cleanup()
        if cls.root.exists():
            raise RuntimeError("disposable_postgres_cleanup_incomplete")
        print(
            "market_store_pg_isolation: owned_pgdata_removed=true owned_pg_stopped=true tcp_disabled=true fsync=on"
        )

    def connect(self, database=None, **kwargs):
        return self.psycopg.connect(
            host=str(self.socket), port=self.port, dbname=database or self.database, **kwargs
        )

    def setUp(self):
        self.database = "rwb_market_test_" + uuid4().hex
        with self.connect("postgres", autocommit=True) as connection:
            connection.execute(
                self.psycopg.sql.SQL("CREATE DATABASE {}").format(
                    self.psycopg.sql.Identifier(self.database)
                )
            )
        self.store = PostgresMarketStore(self.connect)
        self.store.bootstrap()

    def tearDown(self):
        with self.connect("postgres", autocommit=True) as connection:
            connection.execute(
                self.psycopg.sql.SQL("DROP DATABASE {}").format(
                    self.psycopg.sql.Identifier(self.database)
                )
            )

    def test_restart_pit_and_logical_restore(self):
        version = self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        frozen = self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31), as_of=at(3))
        self.run_pg([self.pg_ctl, "-D", str(self.data), "-m", "fast", "-w", "stop"])
        type(self).started = False
        self.start()
        reopened = PostgresMarketStore(self.connect)
        self.assertEqual(reopened.version(SCOPE, DATASET), version)
        reopened.commit_batch(SCOPE, DATASET, batch(fact(value="12", available=4, revision="2")))
        self.assertEqual(
            reopened.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31), as_of=at(3))
            .facts[0]
            .value,
            "10",
        )
        self.assertEqual(frozen.digest, reopened.export_restore(SCOPE, frozen.export()).digest)
        with self.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_frozen").fetchone()[0], 1
            )

    def test_concurrent_tied_revisions_reject_one_writer_without_poisoning_reads(self):
        barrier = Barrier(2)

        def write(value):
            backend = PostgresMarketStore(self.connect)
            barrier.wait(timeout=5)
            try:
                backend.commit_batch(SCOPE, DATASET, batch(fact(value=value, revision=value)))
                return "committed"
            except MarketStoreError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(write, ("10", "11")))
        self.assertCountEqual(results, ["committed", "ambiguous_revision_order"])
        latest = self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(len(latest.facts), 1)
        self.assertIn(latest.facts[0].value, ("10", "11"))

    def test_real_watermark_failure_rolls_back_all_rows(self):
        with self.connect() as connection:
            connection.execute(
                "CREATE FUNCTION reject_watermark() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected'; END $$"
            )
            connection.execute(
                "CREATE TRIGGER reject_watermark BEFORE INSERT ON rwb_market_watermarks FOR EACH ROW EXECUTE FUNCTION reject_watermark()"
            )
        with self.assertRaises(MarketStoreError):
            self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        with self.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_batches").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_watermarks").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_originals").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_facts").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_coverage").fetchone()[0], 0
            )

    def test_logical_export_restores_into_empty_database(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact(), fact(day=3)))
        frozen = self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 3), as_of=at(3))
        target_name = "rwb_restore_" + uuid4().hex
        with self.connect("postgres", autocommit=True) as connection:
            connection.execute(
                self.psycopg.sql.SQL("CREATE DATABASE {}").format(
                    self.psycopg.sql.Identifier(target_name)
                )
            )
        try:
            target = PostgresMarketStore(lambda: self.connect(target_name))
            target.bootstrap()
            self.assertEqual(target.export_restore(SCOPE, frozen.export()).digest, frozen.digest)
            restored = target.freeze(
                SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 3), as_of=at(3)
            )
            self.assertEqual(restored.digest, frozen.digest)
        finally:
            with self.connect("postgres", autocommit=True) as connection:
                connection.execute(
                    self.psycopg.sql.SQL("DROP DATABASE {}").format(
                        self.psycopg.sql.Identifier(target_name)
                    )
                )

    def test_reference_only_batch_reverse_hash_restart_read_version_freeze(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        second = reverse_hash_reference_batch()
        version = self.store.commit_batch(SCOPE, DATASET, second)
        self.run_pg([self.pg_ctl, "-D", str(self.data), "-m", "fast", "-w", "stop"])
        type(self).started = False
        self.start()
        reopened = PostgresMarketStore(self.connect)
        self.assertEqual(reopened.version(SCOPE, DATASET), version)
        rows = reopened.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(len(rows.facts), 2)
        frozen = reopened.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(len(json.loads(frozen.payload)["batch"]["originals"]), 1)

    def test_history_larger_than_64_mib_does_not_block_narrow_updates(self):
        start = date(2024, 1, 1)
        for index in range(66):
            original = RawOriginal(bytes([index]) * (1024 * 1024))
            observation = dataclasses.replace(
                fact(), business_date=start + timedelta(days=index), raw_hash=original.sha256
            )
            self.store.commit_batch(SCOPE, DATASET, Batch((observation,), (original,)))
        rows = self.store.read_range(SCOPE, DATASET, start, start)
        self.assertEqual(len(rows.facts), 1)
        self.assertEqual(
            len(
                json.loads(self.store.freeze(SCOPE, DATASET, start, start).payload)["batch"][
                    "originals"
                ]
            ),
            1,
        )
        self.store.commit_batch(
            SCOPE,
            DATASET,
            Batch(
                (
                    dataclasses.replace(
                        fact(), business_date=start + timedelta(days=67), raw_hash=original.sha256
                    ),
                ),
                (),
            ),
        )
        self.assertEqual(self.store.watermark(SCOPE, DATASET), start + timedelta(days=67))

    def test_runtime_role_cannot_update_or_delete_original_batches(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact()))
        with self.connect() as connection:
            connection.execute("CREATE ROLE rwb_market_test_runtime NOLOGIN")
            connection.execute(
                "GRANT SELECT,INSERT ON rwb_market_batches,rwb_market_frozen,rwb_market_originals,rwb_market_facts,rwb_market_coverage TO rwb_market_test_runtime"
            )
            connection.execute(
                "GRANT SELECT,INSERT,UPDATE ON rwb_market_watermarks TO rwb_market_test_runtime"
            )
        try:
            for statement in (
                "UPDATE rwb_market_batches SET document='{}'::jsonb",
                "DELETE FROM rwb_market_batches",
                "UPDATE rwb_market_originals SET payload='x'::bytea",
                "DELETE FROM rwb_market_originals",
                "UPDATE rwb_market_facts SET document='{}'::jsonb",
                "DELETE FROM rwb_market_facts",
                "DELETE FROM rwb_market_coverage",
            ):
                with self.connect() as connection:
                    connection.execute("SET ROLE rwb_market_test_runtime")
                    with self.assertRaises(self.psycopg.errors.InsufficientPrivilege):
                        connection.execute(statement)
                    connection.rollback()
        finally:
            with self.connect() as connection:
                connection.execute("DROP OWNED BY rwb_market_test_runtime")
                connection.execute("DROP ROLE rwb_market_test_runtime")

    def test_database_connections_do_not_listen_on_tcp(self):
        with self.connect() as connection:
            self.assertEqual(connection.execute("SHOW listen_addresses").fetchone()[0], "")
            self.assertEqual(connection.execute("SHOW fsync").fetchone()[0], "on")

    def test_cancel_before_commit_rolls_back_all_indexed_state(self):
        context = OperationContext()

        def cancel_after_watermark(statement):
            if statement.startswith("INSERT INTO rwb_market_watermarks"):
                context.cancel()

        target = PostgresMarketStore(
            lambda: HookConnection(self.connect(), after_execute=cancel_after_watermark)
        )
        with operation_context(context), self.assertRaises(MarketStoreCancelled):
            target.commit_batch(
                SCOPE,
                DATASET,
                batch(
                    fact(),
                    coverage=(CoverageProof(date(2026, 1, 2), "suspended", "notice", at(2)),),
                ),
            )
        self.assertFalse(context.committed)
        self.assertIsNone(self.store.watermark(SCOPE, DATASET))
        with self.connect() as connection:
            for table in (
                "rwb_market_originals",
                "rwb_market_facts",
                "rwb_market_coverage",
                "rwb_market_batches",
                "rwb_market_watermarks",
            ):
                self.assertEqual(
                    connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0
                )
        # A different operation remains usable after the cancelled worker drains.
        with operation_context(OperationContext()):
            self.store.commit_batch(SCOPE, DATASET, batch(fact()))

    def test_cancel_after_real_commit_keeps_committed_receipt(self):
        context = OperationContext()
        target = PostgresMarketStore(
            lambda: HookConnection(self.connect(), after_commit=context.cancel)
        )
        with operation_context(context):
            version = target.commit_batch(SCOPE, DATASET, batch(fact()))
        self.assertTrue(context.committed)
        self.assertTrue(context.outcome.cancelled)
        self.assertEqual(context.outcome.result, version)
        self.assertEqual(self.store.version(SCOPE, DATASET), version)

    def test_coverage_only_export_restore_and_strict_pit(self):
        current = date(2026, 1, 1)
        proof = CoverageProof(current, "nontrading", "exchange-calendar", at(1))
        self.store.commit_batch(SCOPE, DATASET, Batch((), (), (proof,)))
        frozen = self.store.freeze(SCOPE, DATASET, current, current, as_of=at(3))
        self.assertEqual(len(json.loads(frozen.payload)["batch"]["facts"]), 0)
        self.assertEqual(self.store.export_restore(SCOPE, frozen.export()).digest, frozen.digest)
        self.assertEqual(self.store.find_gaps(SCOPE, DATASET, (current,), as_of=at(3)), ())
        other = dataclasses.replace(SCOPE, owner_id="bob")
        self.store.commit_batch(
            other, DATASET, Batch((), (), (dataclasses.replace(proof, available_at=None),))
        )
        with self.assertRaises(MarketStoreError):
            self.store.freeze(other, DATASET, current, current, as_of=at(3))
        self.assertFalse(
            json.loads(self.store.freeze(other, DATASET, current, current).payload)["pit_complete"]
        )

    def test_incremental_versions_idempotency_and_concurrent_writes(self):
        initial = batch(fact())
        first = self.store.commit_batch(SCOPE, DATASET, initial)
        self.assertEqual(self.store.commit_batch(SCOPE, DATASET, initial), first)
        barrier = Barrier(2)

        def append(day):
            barrier.wait(timeout=5)
            return self.store.commit_batch(SCOPE, DATASET, Batch((fact(day=day),), ()))

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(append, d) for d in (2, 3)]
            versions = [future.result(timeout=15) for future in futures]
        final = self.store.version(SCOPE, DATASET)
        self.assertIn(final, versions)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT parent_version,version_hash FROM rwb_market_batches"
            ).fetchall()
            self.assertEqual(len(rows), 3)
            parents = {parent for parent, _ in rows}
            self.assertIn(first, parents)
            self.assertEqual(len(parents), 3)
        self.assertEqual(
            len(self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 3)).facts), 3
        )
        self.assertEqual(self.store.watermark(SCOPE, DATASET), date(2026, 1, 3))

    def test_single_response_limit_does_not_block_future_narrow_operations(self):
        self.store.commit_batch(SCOPE, DATASET, batch(fact(day=1), fact(day=2)))
        with patch("app.research_web.market_store.postgres.MAX_RESULT_FACTS", 1):
            with self.assertRaises(MarketStoreError):
                self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
            self.store.commit_batch(SCOPE, DATASET, Batch((fact(day=3),), ()))
            self.assertEqual(
                len(
                    self.store.read_range(SCOPE, DATASET, date(2026, 1, 3), date(2026, 1, 3)).facts
                ),
                1,
            )

    def test_bootstrap_refuses_legacy_history_without_schema_marker(self):
        with self.connect() as connection:
            connection.execute("DROP TABLE rwb_market_schema")
        with self.assertRaisesRegex(MarketStoreError, "unsupported_warehouse_schema"):
            self.store.bootstrap()
        with self.connect() as connection:
            self.assertIsNone(
                connection.execute("SELECT to_regclass('rwb_market_schema')").fetchone()[0]
            )

    def test_real_range_index_plan_and_unknown_available_at_exclusion(self):
        history = [
            dataclasses.replace(fact(), business_date=date(2020, 1, 1) + timedelta(days=index))
            for index in range(300)
        ]
        self.store.commit_batch(
            SCOPE, DATASET, batch(fact(), fact(day=2, available=None), *history)
        )
        pit = self.store.read_range(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2), as_of=at(3))
        self.assertEqual(len(pit.facts), 1)
        self.assertFalse(
            self.store.read_range(SCOPE, DATASET, date(2026, 1, 2), date(2026, 1, 2)).pit_complete
        )
        with self.connect() as connection:
            connection.execute("ANALYZE rwb_market_facts")
            plan = connection.execute(
                "EXPLAIN (FORMAT JSON) SELECT fact_id,document FROM rwb_market_facts WHERE scope_key=%s AND dataset_key=%s AND business_date>=%s AND business_date<=%s AND available_at<=%s",
                (SCOPE.key, DATASET.key, date(2026, 1, 1), date(2026, 1, 2), at(3)),
            ).fetchone()[0]
            rendered = json.dumps(plan)
            self.assertIn("rwb_market_facts_range", rendered)
            self.assertIn("business_date", rendered)

    def test_equivalent_offsets_do_not_advance_version_or_dangle_manifest_ids(self):
        from test_market_store import RAW

        original = fact()
        offset = timezone(timedelta(hours=8))
        equivalent = dataclasses.replace(
            original,
            available_at=original.available_at.astimezone(offset),
            ingested_at=original.ingested_at.astimezone(offset),
        )
        proof = CoverageProof(date(2026, 1, 2), "suspended", "notice", at(2))
        offset_proof = dataclasses.replace(proof, available_at=at(2).astimezone(offset))
        version = self.store.commit_batch(SCOPE, DATASET, Batch((original,), (RAW,), (proof,)))
        self.assertEqual(
            self.store.commit_batch(SCOPE, DATASET, Batch((equivalent,), (RAW,), (offset_proof,))),
            version,
        )
        self.assertEqual(
            self.store.commit_batch(
                SCOPE, DATASET, Batch((original, equivalent), (RAW, RAW), (proof, offset_proof))
            ),
            version,
        )
        before = self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2), as_of=at(3))
        with self.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_batches").fetchone()[0], 1
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_facts").fetchone()[0], 1
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM rwb_market_coverage").fetchone()[0], 1
            )
            self.assertEqual(
                connection.execute("SELECT payload FROM rwb_market_originals").fetchone()[0],
                RAW.payload,
            )
            dangling = connection.execute(
                "SELECT count(*) FROM rwb_market_batches b CROSS JOIN LATERAL jsonb_array_elements_text(b.document->'facts') referenced(fact_id) LEFT JOIN rwb_market_facts f ON f.scope_key=b.scope_key AND f.dataset_key=b.dataset_key AND f.fact_id=referenced.fact_id WHERE f.fact_id IS NULL"
            ).fetchone()[0]
            self.assertEqual(dangling, 0)
        self.run_pg([self.pg_ctl, "-D", str(self.data), "-m", "fast", "-w", "stop"])
        type(self).started = False
        self.start()
        reopened = PostgresMarketStore(self.connect)
        after = reopened.freeze(
            SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2), as_of=at(3).astimezone(offset)
        )
        self.assertEqual(before.digest, after.digest)
        self.assertEqual(reopened.export_restore(SCOPE, before.export()).digest, before.digest)
        self.assertEqual(reopened.version(SCOPE, DATASET), version)

    @unittest.skipUnless(
        os.environ.get("RWB_MARKET_STORE_LIVE_DATA") == "1",
        "explicit bounded free vendor acceptance not enabled",
    )
    def test_native_financial_and_index_snapshots_survive_database_restart(self):
        import asyncio
        from datetime import UTC, datetime
        from types import SimpleNamespace

        from app.research_web.datahub.contracts import BusinessQuery
        from app.research_web.datahub.providers_akshare import fetch
        from app.research_web.datahub.providers_external import fetch as fetch_external
        from app.research_web.datahub.research_warehouse import ResearchWarehouse

        root = self.root / ("native-snapshots-" + uuid4().hex)
        root.mkdir(mode=0o700)
        keyring = SimpleNamespace(get_password=lambda *_args: None)
        factory = lambda *_args: PostgresMarketStore(self.connect)
        warehouse = ResearchWarehouse(root, keyring=keyring, backend_factory=factory)
        saved = warehouse.save(
            {
                "host": str(self.socket),
                "port": self.port,
                "database": self.database,
                "username": "research",
                "sslmode": "disable",
            }
        )
        warehouse.initialize(saved["profile_id"], self.database)
        captured = []
        for source, capability, parameters, expected in (
            (
                "akshare",
                "financials",
                {"asset": "000001.SZ", "statements": ["metrics"], "periods": ["2024-12-31"]},
                1,
            ),
            (
                "akshare",
                "market_bars",
                {
                    "asset": "000001.SH",
                    "asset_type": "index",
                    "frequency": "daily",
                    "adjustment": "none",
                    "start_date": "2025-01-02",
                    "end_date": "2025-01-03",
                },
                2,
            ),
            (
                "ext_worldbank",
                "external_data",
                {
                    "dataset": "inflation",
                    "arguments_json": json.dumps({"query": {"date": "2023:2024", "per_page": 2}}),
                },
                2,
            ),
        ):
            query = BusinessQuery(capability=capability, source=source, parameters=parameters)
            result = asyncio.run((fetch if source == "akshare" else fetch_external)(query))
            self.assertIn(result.status, {"complete", "snapshot"}, result.limitations)
            self.assertEqual(len(result.rows), expected)
            self.assertIsNotNone(warehouse.ingest(query, source, "f" * 64, result))
            cutoff = datetime.now(UTC)
            historical = query.model_copy(update={"as_of": cutoff, "purpose": "research"})
            read = warehouse.read(historical, source, "f" * 64)
            self.assertEqual(read.rows, result.rows)
            self.assertFalse(read.metadata["formal_backtest_eligible"])
            self.assertEqual(read.metadata["availability_basis"], "first_observed")
            captured.append((historical, read.raw, read.rows))
        self.run_pg([self.pg_ctl, "-D", str(self.data), "-m", "fast", "-w", "stop"])
        type(self).started = False
        self.start()
        reopened = ResearchWarehouse(root, keyring=keyring, backend_factory=factory)
        for query, originals, rows in captured:
            read = reopened.read(query, query.source, "f" * 64)
            self.assertEqual(read.raw, originals)
            self.assertEqual(read.rows, rows)
            self.assertTrue(read.metadata["warehouse_hit"])

    @unittest.skipUnless(
        os.environ.get("RWB_MARKET_STORE_LIVE_DATA") == "1",
        "explicit bounded free vendor acceptance not enabled",
    )
    def test_host_warehouse_configuration_incremental_fill_and_restart(self):
        from fastapi.testclient import TestClient
        from test_api import NativeFixture

        from app.research_web.datahub import providers
        from app.research_web.datahub.research_warehouse import ResearchWarehouse
        from app.research_web.main import create_app
        from app.research_web.service import ResearchService
        from app.research_web.store import Store

        async def offline():
            return None

        secrets = {}

        def get_secret(service, account):
            return secrets.get((service, account))

        with (
            patch("keyring.get_password", get_secret),
            patch(
                "keyring.set_password",
                lambda service, account, value: secrets.__setitem__((service, account), value),
            ),
            patch(
                "keyring.delete_password",
                lambda service, account: secrets.pop((service, account), None),
            ),
        ):
            native = NativeFixture()
            service = ResearchService(native, Store(self.root / ("host-" + uuid4().hex)))
            service.frameworks.start = offline
            service.mcp_registry.start = offline
            service.report_workflows.start = offline
            calls = []
            original_fetch = providers.fetch

            async def tracked_fetch(query, **kwargs):
                calls.append(dict(query.parameters))
                return await original_fetch(query, **kwargs)

            with self.connect() as connection:
                username = connection.execute("SELECT current_user").fetchone()[0]
            with (
                TestClient(create_app(service)) as client,
                patch.object(providers, "fetch", tracked_fetch),
            ):
                service.connected = {"mux", "host"}
                saved = client.post(
                    "/api/research/data/warehouse",
                    json={
                        "operation": "save",
                        "configuration": {
                            "host": str(self.socket),
                            "port": self.port,
                            "database": self.database,
                            "username": username,
                            "sslmode": "disable",
                        },
                    },
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertFalse(saved.json()["enabled"])
                initialized = client.post(
                    "/api/research/data/warehouse",
                    json={
                        "operation": "initialize",
                        "profile_id": saved.json()["profile_id"],
                        "database_confirmation": self.database,
                    },
                )
                self.assertEqual(initialized.status_code, 200, initialized.text)
                sid = client.post("/api/research/sessions", json={"mode": "claw"}).json()["id"]
                headers = {"X-Research-Data-Key": service.datahub.control["token"]}

                def query(call_id, end, refresh=False):
                    response = client.post(
                        "/api/research/internal/data/business-query",
                        headers=headers,
                        json={
                            "session_id": sid,
                            "call_id": call_id,
                            "query": {
                                "capability": "market_bars",
                                "source": "akshare",
                                "refresh": refresh,
                                "parameters": {
                                    "asset": "000001.SZ",
                                    "asset_type": "stock",
                                    "frequency": "daily",
                                    "adjustment": "none",
                                    "start_date": "2025-01-02",
                                    "end_date": end,
                                },
                            },
                        },
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    return response.json()

                first = query("bounded-initial", "2025-01-06", True)
                self.assertEqual(first["status"], "complete", first.get("limitations"))
                self.assertTrue(first["provider_metadata"]["warehouse_persisted"])
                extended = query("bounded-tail", "2025-01-10")
                self.assertTrue(extended["data_success"])
                self.assertEqual(extended["row_count"], 7)
                self.assertTrue(extended["provider_metadata"]["warehouse_incremental"])
                self.assertEqual(len(calls), 2)
                self.assertGreaterEqual(calls[1]["start_date"], "2025-01-06")
                self.run_pg([self.pg_ctl, "-D", str(self.data), "-m", "fast", "-w", "stop"])
                type(self).started = False
                self.start()
                service.datahub.warehouse = ResearchWarehouse(
                    service.store.root, keyring=service.datahub.connections.keyring
                )

                async def no_network(*_args, **_kwargs):
                    raise AssertionError("restart database hit must not fetch")

                with (
                    patch.object(providers, "fetch", no_network),
                    patch("app.research_web.datahub.providers_akshare.fetch", no_network),
                ):
                    restored = query("after-owned-pg-restart", "2025-01-10")
                self.assertTrue(restored["provider_metadata"]["warehouse_hit"])
                self.assertEqual(restored["row_count"], 7)
                self.assertFalse(any(method == "session.prompt" for method, _ in native.calls))
                print(
                    json.dumps(
                        {
                            "acceptance": "real-host-private-control-free-data-postgres",
                            "initial_rows": first["row_count"],
                            "extended_rows": extended["row_count"],
                            "actual_vendor_queries": len(calls),
                            "restart_database_hit": True,
                            "model_calls": 0,
                        }
                    )
                )
