"""Opt-in indexed PostgreSQL warehouse with immutable incremental manifests.

No import-time connection/DDL. Limits bound one action, never lifetime history.
The factory returns a NEW owned transactional DBAPI connection on every call.
"""

import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime

from core.observability import get_logger

from .models import (
    MAX_EXPORT_BYTES,
    Batch,
    CoverageProof,
    DatasetIdentity,
    Fact,
    FrozenSnapshot,
    MarketStoreError,
    RawOriginal,
    ReadResult,
    batch_document,
    canonical,
    day,
    digest,
    fact_document,
    instant,
    parse_batch,
    parse_fact,
)
from .operation import MarketStoreCancelled, checkpoint, record_committed

log = get_logger(__name__)
MAX_BATCH_FACTS = 10000
MAX_BATCH_BYTES = 32 * 1024 * 1024
MAX_RESULT_FACTS = 10000
MAX_RESULT_BYTES = 32 * 1024 * 1024
SCHEMA_VERSION = 2
DDL = (
    """CREATE TABLE IF NOT EXISTS rwb_market_schema (
        version integer PRIMARY KEY CHECK(version=2))""",
    """CREATE TABLE IF NOT EXISTS rwb_market_originals (
        scope_key text NOT NULL, dataset_key text NOT NULL,
        raw_hash text NOT NULL CHECK(length(raw_hash)=64), payload bytea NOT NULL,
        PRIMARY KEY(scope_key,dataset_key,raw_hash))""",
    """CREATE TABLE IF NOT EXISTS rwb_market_facts (
        scope_key text NOT NULL, dataset_key text NOT NULL,
        fact_id text NOT NULL, logical_key text NOT NULL, revision_key text NOT NULL,
        business_date date NOT NULL, metric text NOT NULL,
        available_at timestamptz, ingested_at timestamptz NOT NULL,
        raw_hash text NOT NULL, document jsonb NOT NULL,
        PRIMARY KEY(scope_key,dataset_key,fact_id),
        UNIQUE(scope_key,dataset_key,revision_key),
        FOREIGN KEY(scope_key,dataset_key,raw_hash)
          REFERENCES rwb_market_originals(scope_key,dataset_key,raw_hash))""",
    """CREATE INDEX IF NOT EXISTS rwb_market_facts_range
        ON rwb_market_facts(scope_key,dataset_key,business_date,available_at)""",
    """CREATE INDEX IF NOT EXISTS rwb_market_facts_revisions
        ON rwb_market_facts(scope_key,dataset_key,logical_key,
          (COALESCE(available_at,ingested_at)) DESC,ingested_at DESC)""",
    """CREATE TABLE IF NOT EXISTS rwb_market_coverage (
        scope_key text NOT NULL, dataset_key text NOT NULL, proof_hash text NOT NULL,
        business_date date NOT NULL, state text NOT NULL, available_at timestamptz,
        document jsonb NOT NULL, PRIMARY KEY(scope_key,dataset_key,proof_hash))""",
    """CREATE INDEX IF NOT EXISTS rwb_market_coverage_range
        ON rwb_market_coverage(scope_key,dataset_key,business_date,available_at)""",
    """CREATE TABLE IF NOT EXISTS rwb_market_batches (
        scope_key text NOT NULL, dataset_key text NOT NULL,
        batch_hash text NOT NULL, parent_version text NOT NULL, version_hash text NOT NULL,
        document jsonb NOT NULL,
        committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(scope_key,dataset_key,batch_hash))""",
    """CREATE TABLE IF NOT EXISTS rwb_market_watermarks (
        scope_key text NOT NULL, dataset_key text NOT NULL,
        high_water_date date, version_hash text NOT NULL,
        scope_document jsonb NOT NULL, dataset_document jsonb NOT NULL,
        PRIMARY KEY(scope_key,dataset_key))""",
    """CREATE TABLE IF NOT EXISTS rwb_market_frozen (
        scope_key text NOT NULL, dataset_key text NOT NULL,
        snapshot_hash text NOT NULL, document jsonb NOT NULL,
        PRIMARY KEY(scope_key,dataset_key,snapshot_hash))""",
)


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _logical(fact):
    return digest(
        canonical(
            {
                "date": fact.business_date.isoformat(),
                "metric": fact.metric,
                "period": fact.period,
                "dimensions": fact.dimensions,
            }
        )
    )


def _revision(fact):
    return digest(canonical([_logical(fact), fact.source_version]))


def _proof_document(proof):
    return {
        "business_date": proof.business_date.isoformat(),
        "state": proof.state,
        "evidence_id": proof.evidence_id,
        "available_at": proof.available_at.isoformat() if proof.available_at else None,
    }


class PostgresMarketStore:
    """Indexed append-only facts and originals; explicit migration ownership.

    Runtime roles: SELECT/INSERT on originals/facts/coverage/batches/frozen;
    SELECT/INSERT/UPDATE on watermarks; SELECT on schema. No DDL/DELETE or
    UPDATE on immutable tables. Bootstrap never configures credentials/roles.
    """

    def __init__(self, connection_factory):
        if not callable(connection_factory):
            raise MarketStoreError("connection_factory_required")
        self._connect = connection_factory

    @classmethod
    def from_dsn(cls, dsn):
        def connect():
            try:
                import psycopg

                return psycopg.connect(
                    dsn,
                    connect_timeout=5,
                    options="-c statement_timeout=5000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=10000",
                )
            except ImportError:
                raise MarketStoreError("postgres_driver_unavailable") from None
            except Exception:  # noqa: BLE001 - vendor failures must not disclose credentials.
                raise MarketStoreError("warehouse_database_unavailable") from None

        return cls(connect)

    @contextmanager
    def _transaction(self, *, readonly=False, repeatable=False):
        connection = None
        cursor = None
        try:
            checkpoint()
            connection = self._connect()
            if getattr(connection, "autocommit", False):
                raise MarketStoreError("transactional_connection_required")
            cursor = connection.cursor()
            statement = "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
            if readonly or repeatable:
                statement = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" + (
                    " READ ONLY" if readonly else ""
                )
            cursor.execute(statement)
            checkpoint()
            yield cursor
            checkpoint()
            connection.commit()
            if not readonly:
                record_committed()
        except Exception as exc:  # noqa: BLE001 - redact injected/vendor DBAPI errors.
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:  # noqa: BLE001 - preserve original error, redact cleanup failure.
                    log.error("market_store_database_rollback_failed")
            if isinstance(exc, MarketStoreCancelled):
                raise MarketStoreCancelled(exc.outcome) from None
            log.error("market_store_database_operation_failed")
            safe_codes = {
                "postgres_driver_unavailable",
                "transactional_connection_required",
                "warehouse_batch_limit_exceeded",
                "warehouse_result_limit_exceeded",
                "warehouse_export_limit_exceeded",
                "unsupported_warehouse_schema",
                "stored_identity_mismatch",
                "stored_fact_digest_mismatch",
                "original_digest_mismatch",
                "unsuccessful_batch_not_committed",
                "metric_outside_dataset_contract",
                "missing_original",
                "immutable_revision_conflict",
                "ambiguous_revision_order",
                "cannot_freeze_empty_selection",
                "invalid_date_range",
                "explicit_expected_dates_required",
            }
            if isinstance(exc, MarketStoreError) and str(exc) in safe_codes:
                raise MarketStoreError(str(exc)) from None
            raise MarketStoreError("warehouse_database_operation_failed") from None
        finally:
            for resource in (cursor, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:  # noqa: BLE001 - cleanup must not leak vendor text.
                        log.error("market_store_database_close_failed")

    def bootstrap(self):
        """Fresh indexed-v2 DDL only; refuse implicit migration of legacy v1."""
        with self._transaction() as cursor:
            cursor.execute(
                "SELECT to_regclass('rwb_market_batches') IS NOT NULL, to_regclass('rwb_market_schema') IS NOT NULL"
            )
            old_batches, schema_exists = cursor.fetchone()
            if old_batches and not schema_exists:
                raise MarketStoreError("unsupported_warehouse_schema")
            if schema_exists:
                cursor.execute("SELECT version FROM rwb_market_schema")
                if cursor.fetchall() != [(SCHEMA_VERSION,)]:
                    raise MarketStoreError("unsupported_warehouse_schema")
            for statement in DDL:
                cursor.execute(statement)
            cursor.execute(
                "INSERT INTO rwb_market_schema(version) VALUES (%s) ON CONFLICT DO NOTHING",
                (SCHEMA_VERSION,),
            )
        log.info("market_store_schema_bootstrapped", schema_version=SCHEMA_VERSION)

    @staticmethod
    def _empty_version(scope, dataset):
        return digest(
            canonical({"scope": asdict(scope), "dataset": asdict(dataset), "batches": []})
        )

    @staticmethod
    def _head(cursor, scope, dataset):
        cursor.execute(
            "SELECT high_water_date,version_hash,scope_document,dataset_document FROM rwb_market_watermarks WHERE scope_key=%s AND dataset_key=%s",
            (scope.key, dataset.key),
        )
        row = cursor.fetchone()
        if row and (
            canonical(_json(row[2])) != canonical(asdict(scope))
            or canonical(_json(row[3])) != canonical(asdict(dataset))
        ):
            raise MarketStoreError("stored_identity_mismatch")
        return row

    def version(self, scope, dataset):
        with self._transaction(readonly=True) as cursor:
            head = self._head(cursor, scope, dataset)
            return head[1] if head else self._empty_version(scope, dataset)

    def watermark(self, scope, dataset) -> date | None:
        with self._transaction(readonly=True) as cursor:
            head = self._head(cursor, scope, dataset)
            return head[0] if head else None

    @staticmethod
    def _read_facts(cursor, scope, dataset, start, end, as_of=None, expected_dates=None):
        checkpoint()
        day(start)
        day(end)
        instant(as_of, optional=True)
        if start > end:
            raise MarketStoreError("invalid_date_range")
        conditions = "scope_key=%s AND dataset_key=%s AND business_date>=%s AND business_date<=%s"
        parameters = [scope.key, dataset.key, start, end]
        if as_of is not None:
            conditions += " AND available_at IS NOT NULL AND available_at<=%s"
            parameters.append(as_of)
        if expected_dates is not None:
            conditions += " AND business_date=ANY(%s)"
            parameters.append(list(expected_dates))
        parameters.append(MAX_RESULT_FACTS + 1)
        selection = (
            "SELECT fact_id,document FROM (SELECT fact_id,document,business_date,metric,logical_key,DENSE_RANK() OVER (PARTITION BY logical_key ORDER BY COALESCE(available_at,ingested_at) DESC,ingested_at DESC) AS revision_rank FROM rwb_market_facts WHERE "
            + conditions
            + ") selected WHERE revision_rank=1 ORDER BY business_date,metric,logical_key,fact_id LIMIT %s"
        )
        # Bound bytes in PostgreSQL before fetching documents into the Host.
        # Both queries use the same repeatable-read snapshot, not a racy precheck.
        cursor.execute(
            "SELECT count(*),COALESCE(sum(octet_length(document::text)),0) FROM ("
            + selection
            + ") bounded",
            tuple(parameters),
        )
        count, encoded_size = cursor.fetchone()
        if count > MAX_RESULT_FACTS or encoded_size > MAX_RESULT_BYTES:
            raise MarketStoreError("warehouse_result_limit_exceeded")
        cursor.execute(selection, tuple(parameters))
        rows = cursor.fetchall()
        if len(rows) > MAX_RESULT_FACTS:
            raise MarketStoreError("warehouse_result_limit_exceeded")
        selected: dict[tuple, Fact] = {}
        size = 0
        for identity, document in rows:
            checkpoint()
            document = _json(document)
            size += len(canonical(document))
            if size > MAX_RESULT_BYTES:
                raise MarketStoreError("warehouse_result_limit_exceeded")
            fact = parse_fact(document)
            if fact.identity != identity:
                raise MarketStoreError("stored_fact_digest_mismatch")
            previous = selected.get(fact.logical_key)
            if previous is not None and previous.value_json != fact.value_json:
                raise MarketStoreError("ambiguous_revision_order")
            if previous is None or fact.identity < previous.identity:
                selected[fact.logical_key] = fact
        facts = tuple(selected[key] for key in sorted(selected))
        return ReadResult(facts, tuple(f.identity for f in facts if f.available_at is None), as_of)

    def read_range(self, scope, dataset, start, end, *, as_of=None):
        with self._transaction(readonly=True) as cursor:
            return self._read_facts(cursor, scope, dataset, start, end, as_of)

    def find_gaps(self, scope, dataset, expected_dates, *, as_of=None):
        if (
            not isinstance(expected_dates, tuple)
            or not expected_dates
            or len(set(expected_dates)) != len(expected_dates)
        ):
            raise MarketStoreError("explicit_expected_dates_required")
        if len(expected_dates) > MAX_RESULT_FACTS:
            raise MarketStoreError("warehouse_result_limit_exceeded")
        for value in expected_dates:
            day(value)
        with self._transaction(readonly=True) as cursor:
            result = self._read_facts(
                cursor,
                scope,
                dataset,
                min(expected_dates),
                max(expected_dates),
                as_of,
                expected_dates,
            )
            parameters = [scope.key, dataset.key, list(expected_dates)]
            cutoff = ""
            if as_of is not None:
                cutoff = " AND available_at IS NOT NULL AND available_at<=%s"
                parameters.append(as_of)
            cursor.execute(
                "SELECT DISTINCT business_date FROM rwb_market_coverage WHERE scope_key=%s AND dataset_key=%s AND business_date=ANY(%s) AND state<>'unknown'"
                + cutoff,
                tuple(parameters),
            )
            explained = {row[0] for row in cursor.fetchall()}
            metrics: dict[date, set[str]] = {}
            for fact in result.facts:
                metrics.setdefault(fact.business_date, set()).add(fact.metric)
            return tuple(
                sorted(
                    d
                    for d in expected_dates
                    if d not in explained
                    and not set(dataset.metrics).issubset(metrics.get(d, set()))
                )
            )

    @staticmethod
    def _lock(cursor, scope, dataset):
        key = int(digest((scope.key + dataset.key).encode())[:16], 16)
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (key - 2**64 if key >= 2**63 else key,))

    @staticmethod
    def _prepare(scope, dataset, batch):
        if not isinstance(batch, Batch) or batch.status != "succeeded":
            raise MarketStoreError("unsuccessful_batch_not_committed")
        if max(len(batch.facts), len(batch.originals), len(batch.coverage)) > MAX_BATCH_FACTS:
            raise MarketStoreError("warehouse_batch_limit_exceeded")
        revisions: dict[str, Fact] = {}
        ranks: dict[tuple, str] = {}
        for fact in batch.facts:
            rank = (fact.logical_key, fact.available_at or fact.ingested_at, fact.ingested_at)
            if rank in ranks and ranks[rank] != fact.value_json:
                raise MarketStoreError("ambiguous_revision_order")
            ranks[rank] = fact.value_json
            if fact.metric not in dataset.metrics:
                raise MarketStoreError("metric_outside_dataset_contract")
            previous = revisions.get(_revision(fact))
            if previous is not None and previous != fact:
                raise MarketStoreError("immutable_revision_conflict")
            revisions[_revision(fact)] = fact
        document = {
            "scope": asdict(scope),
            "dataset": asdict(dataset),
            "facts": sorted(f.identity for f in batch.facts),
            "originals": sorted(r.sha256 for r in batch.originals),
            "coverage": sorted(digest(canonical(_proof_document(p))) for p in batch.coverage),
        }
        size = (
            len(canonical(document))
            + sum(len(canonical(fact_document(f))) for f in batch.facts)
            + sum(len(r.payload) for r in batch.originals)
            + sum(len(canonical(_proof_document(p))) for p in batch.coverage)
        )
        if size > MAX_BATCH_BYTES:
            raise MarketStoreError("warehouse_batch_limit_exceeded")
        return digest(canonical(document)), document, revisions

    def _append(self, cursor, scope, dataset, batch):
        batch_hash, manifest, revisions = self._prepare(scope, dataset, batch)
        self._lock(cursor, scope, dataset)
        head = self._head(cursor, scope, dataset)
        parent_version = head[1] if head else self._empty_version(scope, dataset)
        cursor.execute(
            "SELECT version_hash FROM rwb_market_batches WHERE scope_key=%s AND dataset_key=%s AND batch_hash=%s",
            (scope.key, dataset.key, batch_hash),
        )
        if cursor.fetchone() is not None:
            return parent_version
        if batch.facts:
            ordering = [
                {
                    "logical_key": _logical(f),
                    "ordering_at": (f.available_at or f.ingested_at).isoformat(),
                    "ingested_at": f.ingested_at.isoformat(),
                    "value_json": f.value_json,
                }
                for f in batch.facts
            ]
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM jsonb_to_recordset(%s::jsonb) AS incoming("
                "logical_key text, ordering_at timestamptz, ingested_at timestamptz, value_json text) "
                "JOIN rwb_market_facts f ON f.scope_key=%s AND f.dataset_key=%s "
                "AND f.logical_key=incoming.logical_key "
                "AND COALESCE(f.available_at,f.ingested_at)=incoming.ordering_at "
                "AND f.ingested_at=incoming.ingested_at "
                "WHERE f.document->>'value_json' IS DISTINCT FROM incoming.value_json)",
                (canonical(ordering).decode(), scope.key, dataset.key),
            )
            if cursor.fetchone()[0]:
                raise MarketStoreError("ambiguous_revision_order")
        for original in batch.originals:
            checkpoint()
            cursor.execute(
                "INSERT INTO rwb_market_originals(scope_key,dataset_key,raw_hash,payload) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (scope.key, dataset.key, original.sha256, original.payload),
            )
        if batch.facts:
            referenced = sorted({f.raw_hash for f in batch.facts})
            cursor.execute(
                "SELECT raw_hash FROM rwb_market_originals WHERE scope_key=%s AND dataset_key=%s AND raw_hash=ANY(%s)",
                (scope.key, dataset.key, referenced),
            )
            if {row[0] for row in cursor.fetchall()} != set(referenced):
                raise MarketStoreError("missing_original")
            cursor.execute(
                "SELECT revision_key,fact_id,document FROM rwb_market_facts WHERE scope_key=%s AND dataset_key=%s AND revision_key=ANY(%s)",
                (scope.key, dataset.key, list(revisions)),
            )
            for revision_key, fact_id, document in cursor.fetchall():
                stored = parse_fact(_json(document))
                if stored.identity != fact_id:
                    raise MarketStoreError("stored_fact_digest_mismatch")
                if canonical(_json(document)) != canonical(fact_document(revisions[revision_key])):
                    raise MarketStoreError("immutable_revision_conflict")
        for revision_key, fact in revisions.items():
            checkpoint()
            cursor.execute(
                "INSERT INTO rwb_market_facts(scope_key,dataset_key,fact_id,logical_key,revision_key,business_date,metric,available_at,ingested_at,raw_hash,document) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    scope.key,
                    dataset.key,
                    fact.identity,
                    _logical(fact),
                    revision_key,
                    fact.business_date,
                    fact.metric,
                    fact.available_at,
                    fact.ingested_at,
                    fact.raw_hash,
                    canonical(fact_document(fact)).decode(),
                ),
            )
        for proof in batch.coverage:
            checkpoint()
            document = _proof_document(proof)
            cursor.execute(
                "INSERT INTO rwb_market_coverage(scope_key,dataset_key,proof_hash,business_date,state,available_at,document) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    scope.key,
                    dataset.key,
                    digest(canonical(document)),
                    proof.business_date,
                    proof.state,
                    proof.available_at,
                    canonical(document).decode(),
                ),
            )
        version = digest(canonical({"parent": parent_version, "batch": batch_hash}))
        cursor.execute(
            "INSERT INTO rwb_market_batches(scope_key,dataset_key,batch_hash,parent_version,version_hash,document) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                scope.key,
                dataset.key,
                batch_hash,
                parent_version,
                version,
                canonical(manifest).decode(),
            ),
        )
        dates = [f.business_date for f in batch.facts]
        if head and head[0] is not None:
            dates.append(head[0])
        high_water = max(dates) if dates else None
        cursor.execute(
            "INSERT INTO rwb_market_watermarks(scope_key,dataset_key,high_water_date,version_hash,scope_document,dataset_document) VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT (scope_key,dataset_key) DO UPDATE SET high_water_date=EXCLUDED.high_water_date,version_hash=EXCLUDED.version_hash",
            (
                scope.key,
                dataset.key,
                high_water,
                version,
                canonical(asdict(scope)).decode(),
                canonical(asdict(dataset)).decode(),
            ),
        )
        return version

    def commit_batch(self, scope, dataset, batch):
        self._prepare(scope, dataset, batch)
        with self._transaction() as cursor:
            version = self._append(cursor, scope, dataset, batch)
        record_committed(version)
        log.info(
            "market_store_postgres_commit",
            fact_count=len(batch.facts),
            coverage_count=len(batch.coverage),
        )
        return version

    @staticmethod
    def _coverage(cursor, scope, dataset, start, end, as_of):
        parameters = [scope.key, dataset.key, start, end]
        cutoff = ""
        if as_of is not None:
            cutoff = " AND available_at IS NOT NULL AND available_at<=%s"
            parameters.append(as_of)
        parameters.append(MAX_RESULT_FACTS + 1)
        cursor.execute(
            "SELECT document FROM rwb_market_coverage WHERE scope_key=%s AND dataset_key=%s AND business_date>=%s AND business_date<=%s"
            + cutoff
            + " ORDER BY business_date,proof_hash LIMIT %s",
            tuple(parameters),
        )
        rows = cursor.fetchall()
        if len(rows) > MAX_RESULT_FACTS:
            raise MarketStoreError("warehouse_result_limit_exceeded")
        result = []
        for (document,) in rows:
            p = _json(document)
            result.append(
                CoverageProof(
                    date.fromisoformat(p["business_date"]),
                    p["state"],
                    p["evidence_id"],
                    datetime.fromisoformat(p["available_at"]) if p["available_at"] else None,
                )
            )
        return tuple(result)

    @staticmethod
    def _originals(cursor, scope, dataset, hashes):
        parameters = (scope.key, dataset.key, sorted(hashes))
        cursor.execute(
            "SELECT COALESCE(sum(octet_length(payload)),0),count(*) FROM rwb_market_originals WHERE scope_key=%s AND dataset_key=%s AND raw_hash=ANY(%s)",
            parameters,
        )
        size, count = cursor.fetchone()
        if count != len(hashes):
            raise MarketStoreError("missing_original")
        if size > MAX_EXPORT_BYTES:
            raise MarketStoreError("warehouse_export_limit_exceeded")
        cursor.execute(
            "SELECT raw_hash,payload FROM rwb_market_originals WHERE scope_key=%s AND dataset_key=%s AND raw_hash=ANY(%s) ORDER BY raw_hash",
            parameters,
        )
        result = []
        for raw_hash, payload in cursor.fetchall():
            original = RawOriginal(bytes(payload))
            if original.sha256 != raw_hash:
                raise MarketStoreError("original_digest_mismatch")
            result.append(original)
        return tuple(result)

    def freeze(self, scope, dataset, start, end, *, as_of=None):
        with self._transaction(repeatable=True) as cursor:
            result = self._read_facts(cursor, scope, dataset, start, end, as_of)
            originals = self._originals(cursor, scope, dataset, {f.raw_hash for f in result.facts})
            coverage = self._coverage(cursor, scope, dataset, start, end, as_of)
            if not result.facts and not any(p.state != "unknown" for p in coverage):
                raise MarketStoreError("cannot_freeze_empty_selection")
            payload = canonical(
                {
                    "scope": asdict(scope),
                    "dataset": asdict(dataset),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "as_of": result.as_of.isoformat() if result.as_of else None,
                    "pit_complete": result.pit_complete
                    and all(p.available_at is not None for p in coverage),
                    "batch": batch_document(Batch(result.facts, originals, coverage)),
                }
            )
            frozen = FrozenSnapshot(payload, digest(payload))
            if len(frozen.export()) > MAX_EXPORT_BYTES:
                raise MarketStoreError("warehouse_export_limit_exceeded")
            self._save_frozen(cursor, scope, dataset, frozen)
        record_committed(frozen.digest)
        return frozen

    @staticmethod
    def _save_frozen(cursor, scope, dataset, frozen):
        cursor.execute(
            "INSERT INTO rwb_market_frozen(scope_key,dataset_key,snapshot_hash,document) VALUES (%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
            (scope.key, dataset.key, frozen.digest, frozen.payload.decode()),
        )

    def export_restore(self, scope, content):
        frozen = FrozenSnapshot.load(content)
        document = json.loads(frozen.payload)
        if document["scope"] != asdict(scope) or "input_scopes" in document:
            raise MarketStoreError("restore_scope_mismatch")
        dataset = DatasetIdentity(
            **{**document["dataset"], "metrics": tuple(document["dataset"]["metrics"])}
        )
        with self._transaction() as cursor:
            self._append(cursor, scope, dataset, parse_batch(document["batch"]))
            self._save_frozen(cursor, scope, dataset, frozen)
        record_committed(frozen.digest)
        return frozen
