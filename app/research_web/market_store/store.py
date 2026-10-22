"""Warehouse protocol, deterministic reference backend and authorization boundary."""

import json
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime
from typing import Protocol

from core.observability import get_logger

from .models import (
    Batch,
    DatasetIdentity,
    Fact,
    FrozenSnapshot,
    MarketStoreError,
    ReadResult,
    StoreScope,
    batch_document,
    canonical,
    day,
    digest,
    instant,
    merge_snapshots,
    parse_batch,
)
from .operation import checkpoint, record_committed

log = get_logger(__name__)


class MarketStore(Protocol):
    def read_range(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        start: date,
        end: date,
        *,
        as_of: datetime | None = None,
    ) -> ReadResult: ...
    def find_gaps(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        expected_dates: tuple[date, ...],
        *,
        as_of: datetime | None = None,
    ) -> tuple[date, ...]: ...
    def commit_batch(self, scope: StoreScope, dataset: DatasetIdentity, batch: Batch) -> str: ...
    def freeze(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        start: date,
        end: date,
        *,
        as_of: datetime | None = None,
    ) -> FrozenSnapshot: ...
    def export_restore(self, scope: StoreScope, content: bytes) -> FrozenSnapshot: ...
    def version(self, scope: StoreScope, dataset: DatasetIdentity) -> str: ...


class InMemoryMarketStore:
    """Reference backend for tests only. Does not provide production persistence."""

    def __init__(self, *, emit_events=True):
        self._batches: dict[tuple[str, str], tuple[Batch, ...]] = {}
        self._lock = threading.RLock()
        self._emit_events = emit_events

    def _get(self, scope, dataset):
        return self._batches.get((scope.key, dataset.key), ())

    def history(self, scope: StoreScope, dataset: DatasetIdentity) -> tuple[Fact, ...]:
        checkpoint()
        with self._lock:
            return tuple(f for b in self._get(scope, dataset) for f in b.facts)

    def commit_batch(self, scope: StoreScope, dataset: DatasetIdentity, batch: Batch) -> str:
        checkpoint()
        if batch.status != "succeeded":
            raise MarketStoreError("unsuccessful_batch_not_committed")
        with self._lock:
            previous = self._get(scope, dataset)
            originals = {r.sha256: r.payload for b in (*previous, batch) for r in b.originals}
            revisions = {f.revision_key: f for b in previous for f in b.facts}
            ranks = {
                (f.logical_key, f.available_at or f.ingested_at, f.ingested_at): f.value_json
                for b in previous
                for f in b.facts
            }
            for fact in batch.facts:
                rank = (fact.logical_key, fact.available_at or fact.ingested_at, fact.ingested_at)
                if rank in ranks and ranks[rank] != fact.value_json:
                    raise MarketStoreError("ambiguous_revision_order")
                ranks[rank] = fact.value_json
                if fact.metric not in dataset.metrics:
                    raise MarketStoreError("metric_outside_dataset_contract")
                if fact.raw_hash not in originals:
                    raise MarketStoreError("missing_original")
                existing = revisions.get(fact.revision_key)
                if existing is not None and existing != fact:
                    raise MarketStoreError("immutable_revision_conflict")
                revisions[fact.revision_key] = fact
            current = {digest(canonical(batch_document(b))) for b in previous}
            if digest(canonical(batch_document(batch))) not in current:
                checkpoint()
                self._batches[(scope.key, dataset.key)] = (*previous, batch)
                if self._emit_events:
                    log.info(
                        "market_store_batch_committed",
                        fact_count=len(batch.facts),
                        coverage_count=len(batch.coverage),
                    )
            # Do not run a cancellation checkpoint after publication: it would
            # hide a successful commit. Compute the outcome from the actual state.
            version = digest(
                canonical(
                    {
                        "scope": asdict(scope),
                        "dataset": asdict(dataset),
                        "batches": sorted(
                            digest(canonical(batch_document(b))) for b in self._get(scope, dataset)
                        ),
                    }
                )
            )
            record_committed(version)
            return version

    def version(self, scope: StoreScope, dataset: DatasetIdentity) -> str:
        checkpoint()
        with self._lock:
            return digest(
                canonical(
                    {
                        "scope": asdict(scope),
                        "dataset": asdict(dataset),
                        "batches": sorted(
                            digest(canonical(batch_document(b))) for b in self._get(scope, dataset)
                        ),
                    }
                )
            )

    def watermark(self, scope: StoreScope, dataset: DatasetIdentity) -> date | None:
        checkpoint()
        with self._lock:
            days = [f.business_date for b in self._get(scope, dataset) for f in b.facts]
            return max(days) if days else None

    def read_range(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        start: date,
        end: date,
        *,
        as_of: datetime | None = None,
    ) -> ReadResult:
        day(start)
        day(end)
        instant(as_of, optional=True)
        if start > end:
            raise MarketStoreError("invalid_date_range")
        selected: dict[tuple, Fact] = {}
        for fact in self.history(scope, dataset):
            checkpoint()
            if not start <= fact.business_date <= end:
                continue
            if as_of is not None and (fact.available_at is None or fact.available_at > as_of):
                continue
            old = selected.get(fact.logical_key)
            # Public availability determines revision order where it is known.
            # Unknown availability is only visible in explicitly latest exploration.
            rank = (fact.available_at or fact.ingested_at, fact.ingested_at)
            if old is not None:
                old_rank = (old.available_at or old.ingested_at, old.ingested_at)
                if rank == old_rank and old.value_json != fact.value_json:
                    raise MarketStoreError("ambiguous_revision_order")
                if rank < old_rank or (rank == old_rank and fact.identity > old.identity):
                    continue
            selected[fact.logical_key] = fact
        facts = tuple(selected[k] for k in sorted(selected))
        return ReadResult(facts, tuple(f.identity for f in facts if f.available_at is None), as_of)

    def find_gaps(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        expected_dates: tuple[date, ...],
        *,
        as_of: datetime | None = None,
    ) -> tuple[date, ...]:
        if (
            not isinstance(expected_dates, tuple)
            or not expected_dates
            or len(set(expected_dates)) != len(expected_dates)
        ):
            raise MarketStoreError("explicit_expected_dates_required")
        for value in expected_dates:
            day(value)
        result = self.read_range(
            scope, dataset, min(expected_dates), max(expected_dates), as_of=as_of
        )
        metrics: dict[date, set[str]] = {}
        for fact in result.facts:
            metrics.setdefault(fact.business_date, set()).add(fact.metric)
        explained = set()
        with self._lock:
            for batch in self._get(scope, dataset):
                for proof in batch.coverage:
                    if proof.state != "unknown" and (
                        as_of is None
                        or (proof.available_at is not None and proof.available_at <= as_of)
                    ):
                        explained.add(proof.business_date)
        return tuple(
            sorted(
                d
                for d in expected_dates
                if d not in explained and not set(dataset.metrics).issubset(metrics.get(d, set()))
            )
        )

    def freeze(
        self,
        scope: StoreScope,
        dataset: DatasetIdentity,
        start: date,
        end: date,
        *,
        as_of: datetime | None = None,
    ) -> FrozenSnapshot:
        with self._lock:
            result = self.read_range(scope, dataset, start, end, as_of=as_of)
            hashes = {f.raw_hash for f in result.facts}
            originals = {
                r.sha256: r
                for b in self._get(scope, dataset)
                for r in b.originals
                if r.sha256 in hashes
            }
            coverage = {
                canonical(
                    {
                        "date": p.business_date.isoformat(),
                        "state": p.state,
                        "id": p.evidence_id,
                        "at": p.available_at.isoformat() if p.available_at else None,
                    }
                ): p
                for b in self._get(scope, dataset)
                for p in b.coverage
                if start <= p.business_date <= end
                and (as_of is None or (p.available_at is not None and p.available_at <= as_of))
            }
            if not result.facts and not any(p.state != "unknown" for p in coverage.values()):
                raise MarketStoreError("cannot_freeze_empty_selection")
            checkpoint()
            payload = canonical(
                {
                    "scope": asdict(scope),
                    "dataset": asdict(dataset),
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "as_of": result.as_of.isoformat() if result.as_of else None,
                    "pit_complete": result.pit_complete
                    and all(p.available_at is not None for p in coverage.values()),
                    "batch": batch_document(
                        Batch(
                            result.facts,
                            tuple(originals[k] for k in sorted(originals)),
                            tuple(coverage[k] for k in sorted(coverage)),
                        )
                    ),
                }
            )
            return FrozenSnapshot(payload, digest(payload))

    def export_restore(self, scope: StoreScope, content: bytes) -> FrozenSnapshot:
        frozen = FrozenSnapshot.load(content)
        document = json.loads(frozen.payload)
        if document["scope"] != asdict(scope) or "input_scopes" in document:
            raise MarketStoreError("restore_scope_mismatch")
        dataset = DatasetIdentity(
            **{**document["dataset"], "metrics": tuple(document["dataset"]["metrics"])}
        )
        self.commit_batch(scope, dataset, parse_batch(document["batch"]))
        return frozen


class MarketStoreService:
    """Trusted Host boundary. Authorization callback required on every operation.

    actor must come from authenticated server identity, never request body owner_id.
    The callback must verify current source entitlement AND personal/shared permission.
    """

    def __init__(
        self,
        store: MarketStore,
        authorize: Callable[[str, StoreScope, str], bool],
        *,
        verify_semantics=None,
    ):
        if not callable(authorize):
            raise MarketStoreError("authorization_callback_required")
        self._store = store
        self._authorize = authorize
        self._verify_semantics = verify_semantics

    def _check(self, actor, scope, action):
        try:
            permitted = self._authorize(actor, scope, action) is True
        except Exception:  # noqa: BLE001 - untrusted policy callbacks fail closed.
            log.warning("market_store_authorization_failed")
            raise MarketStoreError("warehouse_access_denied") from None
        if not permitted:
            raise MarketStoreError("warehouse_access_denied")

    def read_range(self, actor, scope, dataset, start, end, *, as_of=None):
        self._check(actor, scope, "read")
        return self._store.read_range(scope, dataset, start, end, as_of=as_of)

    def find_gaps(self, actor, scope, dataset, expected_dates, *, as_of=None):
        self._check(actor, scope, "read")
        return self._store.find_gaps(scope, dataset, expected_dates, as_of=as_of)

    def commit_batch(self, actor, scope, dataset, batch):
        self._check(actor, scope, "write")
        return self._store.commit_batch(scope, dataset, batch)

    def version(self, actor, scope, dataset):
        self._check(actor, scope, "read")
        return self._store.version(scope, dataset)

    def freeze(self, actor, scope, dataset, start, end, *, as_of=None):
        self._check(actor, scope, "export")
        return self._store.freeze(scope, dataset, start, end, as_of=as_of)

    def export_restore(self, actor, scope, content):
        self._check(actor, scope, "restore")
        return self._store.export_restore(scope, content)

    def merge_snapshots(self, actor, snapshots, proof):
        for snapshot in snapshots:
            document = json.loads(FrozenSnapshot.load(snapshot.export()).payload)
            self._check(actor, StoreScope(**document["scope"]), "export")
            for scope in document.get("input_scopes", []):
                self._check(actor, StoreScope(**scope), "export")
        try:
            verified = callable(self._verify_semantics) and self._verify_semantics(proof) is True
        except Exception:  # noqa: BLE001 - untrusted proof callbacks fail closed.
            verified = False
            log.warning("market_store_semantic_proof_verification_failed")
        if not verified:
            raise MarketStoreError("verified_semantic_proof_required")
        return merge_snapshots(snapshots, proof)
