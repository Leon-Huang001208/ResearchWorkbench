"""Warehouse contracts: deterministic tests, no provider or database connection."""

import dataclasses
import json
import unittest
from datetime import UTC, date, datetime, timedelta, timezone

from app.research_web.market_store import (
    Batch,
    CoverageProof,
    DatasetIdentity,
    Fact,
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    RawOriginal,
    SemanticProof,
    StoreScope,
    merge_snapshots,
)


def at(day):
    return datetime(2026, 1, day, tzinfo=UTC)


SCOPE = StoreScope("alice", "personal-license-1", "wind", "a" * 64)
DATASET = DatasetIdentity("bars", "600000.SH", "CN", "daily", "CNY/share", "raw", "none", "b" * 64)
RAW = RawOriginal(b'{"close":"10"}')


def fact(day=1, value="10", available=2, revision="1", metric="close"):
    return Fact(
        metric=metric,
        business_date=date(2026, 1, day),
        period="2026-01",
        value_json=json.dumps(value),
        available_at=at(available) if available else None,
        ingested_at=at(5),
        source_version=revision,
        raw_hash=RAW.sha256,
    )


def batch(*facts, coverage=(), status="succeeded"):
    return Batch(tuple(facts), (RAW,), tuple(coverage), status=status)


class MarketStoreTests(unittest.TestCase):
    def test_tied_order_different_value_is_rejected_before_publication(self):
        self.commit(batch(fact()))
        before = self.store.version(SCOPE, DATASET)
        with self.assertRaisesRegex(MarketStoreError, "ambiguous_revision_order"):
            self.commit(batch(fact(value="11", revision="other-writer")))
        self.assertEqual(self.store.version(SCOPE, DATASET), before)
        self.assertEqual(self.read().facts[0].value, "10")

    def setUp(self):
        self.store = InMemoryMarketStore()
        self.service = MarketStoreService(self.store, lambda actor, scope, action: actor == "alice")

    def read(self, **kwargs):
        return self.service.read_range(
            "alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31), **kwargs
        )

    def commit(self, value):
        return self.service.commit_batch("alice", SCOPE, DATASET, value)

    def test_append_revision_and_strict_pit(self):
        self.commit(
            batch(fact(), fact(value="11", available=4, revision="2"), fact(day=2, available=None))
        )
        self.assertEqual(self.read(as_of=at(3)).facts[0].value, "10")
        self.assertEqual(len(self.read(as_of=at(3)).facts), 1)
        latest = self.read()
        self.assertEqual(latest.facts[0].value, "11")
        self.assertFalse(latest.pit_complete)
        self.assertEqual(len(self.store.history(SCOPE, DATASET)), 3)

    def test_identity_mutability_and_validation(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            SCOPE.owner_id = "bob"
        with self.assertRaises(MarketStoreError):
            StoreScope("alice", "license", "wind", "not-a-digest")
        with self.assertRaises(MarketStoreError):
            dataclasses.replace(fact(), ingested_at=datetime(2026, 1, 2))
        with self.assertRaises(MarketStoreError):
            dataclasses.replace(fact(), value_json='{"x":NaN}')

    def test_failed_batch_and_missing_original_are_atomic(self):
        before = self.store.version(SCOPE, DATASET)
        for value in (batch(fact(), status="cancelled"), Batch((fact(),), ())):
            with self.assertRaises(MarketStoreError):
                self.commit(value)
        self.assertEqual(self.store.version(SCOPE, DATASET), before)
        self.assertIsNone(self.store.watermark(SCOPE, DATASET))

    def test_internal_gaps_explicit_explanations_and_unknown(self):
        self.commit(
            batch(
                fact(1),
                fact(3),
                coverage=(
                    CoverageProof(date(2026, 1, 2), "suspended", "exchange-notice-1", at(2)),
                ),
            )
        )
        days = tuple(date(2026, 1, d) for d in range(1, 6))
        gaps = self.service.find_gaps("alice", SCOPE, DATASET, days)
        self.assertEqual(gaps, (date(2026, 1, 4), date(2026, 1, 5)))
        with self.assertRaises(MarketStoreError):
            CoverageProof(days[0], "nontrading", "", at(2))
        with self.assertRaises(MarketStoreError):
            self.service.find_gaps("alice", SCOPE, DATASET, ())

    def test_freeze_restore_and_export_integrity(self):
        self.commit(batch(fact()))
        frozen = self.service.freeze(
            "alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31), as_of=at(3)
        )
        exported = frozen.export()
        self.commit(batch(fact(value="12", available=4, revision="3")))
        self.assertEqual(frozen.export(), exported)
        target = MarketStoreService(InMemoryMarketStore(), lambda *args: True)
        restored = target.export_restore("alice", SCOPE, exported)
        self.assertEqual(restored.digest, frozen.digest)
        with self.assertRaises(MarketStoreError):
            target.export_restore("alice", SCOPE, exported.replace(b"close", b"other"))
        with self.assertRaises(MarketStoreError):
            target.export_restore("alice", dataclasses.replace(SCOPE, owner_id="bob"), exported)

    def test_authorization_rechecked_on_cached_reads_and_exports(self):
        enabled = [True]
        service = MarketStoreService(self.store, lambda *args: enabled[0])
        service.commit_batch("alice", SCOPE, DATASET, batch(fact()))
        service.read_range("alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        enabled[0] = False
        with self.assertRaises(MarketStoreError):
            service.read_range("alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        with self.assertRaises(MarketStoreError):
            service.freeze("alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        with self.assertRaises(MarketStoreError):
            MarketStoreService(self.store, None)

    def test_source_and_factor_identities_never_alias(self):
        self.commit(batch(fact()))
        for scope, ds in (
            (dataclasses.replace(SCOPE, source="other"), DATASET),
            (SCOPE, dataclasses.replace(DATASET, adjustment="forward")),
            (SCOPE, dataclasses.replace(DATASET, capability="factors")),
        ):
            self.assertEqual(
                self.store.read_range(scope, ds, date(2026, 1, 1), date(2026, 1, 31)).facts, ()
            )

    def test_cross_source_requires_proof_and_rejects_conflict(self):
        self.commit(batch(fact()))
        first = self.service.freeze("alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        scope2 = dataclasses.replace(SCOPE, source="other")
        self.store.commit_batch(scope2, DATASET, batch(fact(value="11")))
        second = self.store.freeze(scope2, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        with self.assertRaises(MarketStoreError):
            merge_snapshots((first, second), None)
        proof = SemanticProof(
            (first.digest, second.digest), DATASET.semantic_digest, "review-record-1"
        )
        with self.assertRaises(MarketStoreError):
            merge_snapshots((first, second), proof)

    def test_metric_completeness_and_pit_coverage_proof(self):
        dataset = dataclasses.replace(DATASET, metrics=("close", "open"))
        self.store.commit_batch(
            SCOPE,
            dataset,
            batch(fact(), coverage=(CoverageProof(date(2026, 1, 2), "suspended", "notice"),)),
        )
        days = (date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(self.store.find_gaps(SCOPE, dataset, days), (days[0],))
        self.assertEqual(self.store.find_gaps(SCOPE, dataset, days, as_of=at(3)), days)

    def test_import_rejects_false_pit_even_with_recomputed_digest(self):
        from app.research_web.market_store.models import canonical, digest

        self.commit(batch(fact(available=None)))
        frozen = self.service.freeze("alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        envelope = json.loads(frozen.export())
        envelope["payload"]["as_of"] = at(3).isoformat()
        envelope["payload"]["pit_complete"] = True
        envelope["sha256"] = digest(canonical(envelope["payload"]))
        with self.assertRaises(MarketStoreError):
            self.service.export_restore("alice", SCOPE, canonical(envelope))

    def test_same_revision_cannot_overwrite_original(self):
        self.commit(batch(fact()))
        before = self.store.version(SCOPE, DATASET)
        with self.assertRaises(MarketStoreError):
            self.commit(batch(fact(value="12")))
        self.assertEqual(self.store.version(SCOPE, DATASET), before)

    def test_merge_canonical_and_reauthorizes_all_sources(self):
        self.commit(batch(fact()))
        first = self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        other = dataclasses.replace(SCOPE, source="other")
        self.store.commit_batch(other, DATASET, batch(fact()))
        second = self.store.freeze(other, DATASET, date(2026, 1, 1), date(2026, 1, 31))
        proof = SemanticProof(
            tuple(sorted((first.digest, second.digest))), DATASET.semantic_digest, "review-record"
        )
        self.assertEqual(
            merge_snapshots((first, second), proof).digest,
            merge_snapshots((second, first), proof).digest,
        )
        service = MarketStoreService(
            self.store,
            lambda actor, scope, action: scope.source == "wind",
            verify_semantics=lambda proof: True,
        )
        with self.assertRaises(MarketStoreError):
            service.merge_snapshots("alice", (first, second), proof)
        with self.assertRaises(MarketStoreError):
            self.service.merge_snapshots("alice", (first, second), proof)

    def test_merge_preserves_union_range_and_explicit_coverage(self):
        from app.research_web.market_store import FrozenSnapshot

        self.commit(
            batch(fact(), coverage=(CoverageProof(date(2026, 1, 2), "suspended", "notice-2"),))
        )
        first = self.store.freeze(SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2))
        other = dataclasses.replace(SCOPE, source="other")
        self.store.commit_batch(other, DATASET, batch(fact(day=3)))
        second = self.store.freeze(other, DATASET, date(2026, 1, 3), date(2026, 1, 4))
        proof = SemanticProof(
            (first.digest, second.digest), DATASET.semantic_digest, "review-record"
        )
        merged = merge_snapshots((first, second), proof)
        loaded = FrozenSnapshot.load(merged.export())
        document = json.loads(loaded.payload)
        self.assertEqual(document["start"], "2026-01-01")
        self.assertEqual(document["end"], "2026-01-04")
        self.assertEqual(len(document["batch"]["coverage"]), 1)
        self.assertEqual(len(document["input_manifests"]), 2)

    def test_coverage_only_freeze_restore_requires_usable_evidence(self):
        from app.research_web.market_store import FrozenSnapshot

        proof = CoverageProof(date(2026, 1, 1), "nontrading", "exchange-calendar", at(1))
        self.commit(Batch((), (), (proof,)))
        frozen = self.service.freeze(
            "alice", SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 1), as_of=at(3)
        )
        loaded = FrozenSnapshot.load(frozen.export())
        target = InMemoryMarketStore()
        self.assertEqual(target.export_restore(SCOPE, loaded.export()).digest, frozen.digest)
        self.assertEqual(target.find_gaps(SCOPE, DATASET, (date(2026, 1, 1),), as_of=at(3)), ())
        other = dataclasses.replace(SCOPE, owner_id="bob")
        self.store.commit_batch(
            other, DATASET, Batch((), (), (dataclasses.replace(proof, available_at=None),))
        )
        with self.assertRaises(MarketStoreError):
            self.store.freeze(other, DATASET, date(2026, 1, 1), date(2026, 1, 1), as_of=at(3))
        latest = self.store.freeze(other, DATASET, date(2026, 1, 1), date(2026, 1, 1))
        self.assertFalse(json.loads(latest.payload)["pit_complete"])

    def test_equivalent_timezone_facts_and_coverage_have_canonical_identity(self):
        original = fact()
        offset = timezone(timedelta(hours=8))
        equivalent = dataclasses.replace(
            original,
            available_at=original.available_at.astimezone(offset),
            ingested_at=original.ingested_at.astimezone(offset),
        )
        self.assertEqual(equivalent, original)
        self.assertEqual(equivalent.identity, original.identity)
        self.assertEqual(equivalent.available_at.utcoffset(), timedelta(0))
        first_proof = CoverageProof(date(2026, 1, 2), "suspended", "notice", at(2))
        other_proof = dataclasses.replace(first_proof, available_at=at(2).astimezone(offset))
        first = Batch((original,), (RAW,), (first_proof,))
        both = Batch((original, equivalent), (RAW, RAW), (first_proof, other_proof))
        self.assertEqual(first, both)
        version = self.commit(first)
        self.assertEqual(self.commit(Batch((equivalent,), (RAW,), (other_proof,))), version)
        self.assertEqual(self.commit(both), version)
        self.assertEqual(len(self.store.history(SCOPE, DATASET)), 1)
        utc_snapshot = self.store.freeze(
            SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2), as_of=at(3)
        )
        offset_snapshot = self.store.freeze(
            SCOPE, DATASET, date(2026, 1, 1), date(2026, 1, 2), as_of=at(3).astimezone(offset)
        )
        self.assertEqual(utc_snapshot.digest, offset_snapshot.digest)


if __name__ == "__main__":
    unittest.main()
