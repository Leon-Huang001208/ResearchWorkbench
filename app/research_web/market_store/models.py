"""Immutable, source-qualified research facts and portable frozen manifests."""

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

from core.observability import get_logger

log = get_logger(__name__)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@ -]{0,127}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
MAX_EXPORT_BYTES = 32 * 1024 * 1024


class MarketStoreError(ValueError):
    """Stable warehouse failure; messages must never contain connection secrets."""


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise MarketStoreError("invalid_json_value") from None


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def identifier(value: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise MarketStoreError("invalid_identity")


def hash_value(value: str) -> None:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise MarketStoreError("invalid_digest")


def instant(value: datetime | None, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MarketStoreError("timezone_required")


def day(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise MarketStoreError("date_required")


@dataclass(frozen=True)
class StoreScope:
    owner_id: str
    entitlement_scope: str
    source: str
    config_digest: str

    def __post_init__(self):
        for value in (self.owner_id, self.entitlement_scope, self.source):
            identifier(value)
        hash_value(self.config_digest)

    @property
    def key(self) -> str:
        return digest(canonical(asdict(self)))


@dataclass(frozen=True)
class DatasetIdentity:
    capability: str
    asset: str
    market: str
    frequency: str
    units: str
    adjustment: str
    factor_contract: str
    semantic_digest: str
    metrics: tuple[str, ...] = ("close",)

    def __post_init__(self):
        for value in (
            self.capability,
            self.asset,
            self.market,
            self.frequency,
            self.adjustment,
            self.factor_contract,
        ):
            identifier(value)
        if (
            not isinstance(self.units, str)
            or not self.units
            or len(self.units) > 128
            or any(c in self.units for c in "\n\r\\")
        ):
            raise MarketStoreError("invalid_units")
        hash_value(self.semantic_digest)
        if (
            not isinstance(self.metrics, tuple)
            or not self.metrics
            or len(set(self.metrics)) != len(self.metrics)
        ):
            raise MarketStoreError("explicit_metrics_required")
        for metric in self.metrics:
            identifier(metric)

    @property
    def key(self) -> str:
        return digest(canonical(asdict(self)))


@dataclass(frozen=True)
class RawOriginal:
    payload: bytes

    def __post_init__(self):
        if not isinstance(self.payload, bytes) or len(self.payload) > MAX_EXPORT_BYTES:
            raise MarketStoreError("invalid_original")

    @property
    def sha256(self) -> str:
        return digest(self.payload)


@dataclass(frozen=True)
class Fact:
    metric: str
    business_date: date
    period: str
    value_json: str
    available_at: datetime | None
    ingested_at: datetime
    source_version: str
    raw_hash: str
    dimensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        identifier(self.metric)
        identifier(self.period)
        identifier(self.source_version)
        day(self.business_date)
        instant(self.available_at, optional=True)
        instant(self.ingested_at)
        # datetime equality compares instants, while isoformat preserves offsets.
        # Canonical UTC makes equality, revision identity and audit hashes agree.
        if self.available_at is not None:
            object.__setattr__(self, "available_at", self.available_at.astimezone(UTC))
        object.__setattr__(self, "ingested_at", self.ingested_at.astimezone(UTC))
        hash_value(self.raw_hash)
        if self.available_at is not None and self.available_at > self.ingested_at:
            raise MarketStoreError("availability_after_ingestion")
        if not isinstance(self.dimensions, tuple) or any(
            not isinstance(p, tuple) or len(p) != 2 for p in self.dimensions
        ):
            raise MarketStoreError("invalid_dimensions")
        if tuple(sorted(self.dimensions)) != self.dimensions or len(dict(self.dimensions)) != len(
            self.dimensions
        ):
            raise MarketStoreError("dimensions_not_canonical")
        for key, value in self.dimensions:
            identifier(key)
            identifier(value)
        try:
            value = json.loads(self.value_json)
            encoded = canonical(value).decode("utf-8")
        except (ValueError, TypeError, RecursionError):
            raise MarketStoreError("invalid_fact_value") from None
        object.__setattr__(self, "value_json", encoded)

    @property
    def value(self):
        return json.loads(self.value_json)

    @property
    def logical_key(self) -> tuple:
        return self.business_date, self.metric, self.period, self.dimensions

    @property
    def revision_key(self) -> tuple:
        return self.logical_key, self.source_version

    @property
    def identity(self) -> str:
        return digest(canonical(fact_document(self)))


@dataclass(frozen=True)
class CoverageProof:
    business_date: date
    state: str
    evidence_id: str
    available_at: datetime | None = None

    def __post_init__(self):
        day(self.business_date)
        if self.state not in {"suspended", "prelisting", "nontrading", "unknown"}:
            raise MarketStoreError("invalid_coverage_state")
        identifier(self.evidence_id)
        instant(self.available_at, optional=True)
        if self.available_at is not None:
            object.__setattr__(self, "available_at", self.available_at.astimezone(UTC))


@dataclass(frozen=True)
class Batch:
    facts: tuple[Fact, ...]
    originals: tuple[RawOriginal, ...]
    coverage: tuple[CoverageProof, ...] = ()
    status: str = "succeeded"

    def __post_init__(self):
        for values, kind in (
            (self.facts, Fact),
            (self.originals, RawOriginal),
            (self.coverage, CoverageProof),
        ):
            if not isinstance(values, tuple) or any(not isinstance(v, kind) for v in values):
                raise MarketStoreError("immutable_batch_required")
        if self.status not in {"succeeded", "failed", "cancelled"}:
            raise MarketStoreError("invalid_batch_status")
        if not self.facts and not self.coverage:
            raise MarketStoreError("empty_batch")
        # Identical normalized observations are one fact, including when callers
        # supply the same instant using multiple offsets in a single batch.
        object.__setattr__(self, "facts", tuple(dict.fromkeys(self.facts)))
        object.__setattr__(self, "originals", tuple(dict.fromkeys(self.originals)))
        object.__setattr__(self, "coverage", tuple(dict.fromkeys(self.coverage)))


@dataclass(frozen=True)
class ReadResult:
    facts: tuple[Fact, ...]
    unknown_available_at: tuple[str, ...]
    as_of: datetime | None

    def __post_init__(self):
        instant(self.as_of, optional=True)
        if self.as_of is not None:
            object.__setattr__(self, "as_of", self.as_of.astimezone(UTC))

    @property
    def pit_complete(self) -> bool:
        return not self.unknown_available_at


def fact_document(fact: Fact) -> dict:
    value = asdict(fact)
    value["business_date"] = fact.business_date.isoformat()
    value["available_at"] = fact.available_at.isoformat() if fact.available_at else None
    value["ingested_at"] = fact.ingested_at.isoformat()
    return value


def parse_fact(value: dict) -> Fact:
    value = dict(value)
    value["business_date"] = date.fromisoformat(value["business_date"])
    value["available_at"] = (
        datetime.fromisoformat(value["available_at"]) if value["available_at"] else None
    )
    value["ingested_at"] = datetime.fromisoformat(value["ingested_at"])
    value["dimensions"] = tuple(tuple(p) for p in value["dimensions"])
    return Fact(**value)


def batch_document(batch: Batch) -> dict:
    return {
        "facts": [fact_document(f) for f in batch.facts],
        "originals": [
            {"sha256": r.sha256, "base64": base64.b64encode(r.payload).decode("ascii")}
            for r in batch.originals
        ],
        "coverage": [
            {
                "business_date": p.business_date.isoformat(),
                "state": p.state,
                "evidence_id": p.evidence_id,
                "available_at": p.available_at.isoformat() if p.available_at else None,
            }
            for p in batch.coverage
        ],
        "status": batch.status,
    }


def parse_batch(value: dict) -> Batch:
    originals = tuple(
        RawOriginal(base64.b64decode(r["base64"], validate=True)) for r in value["originals"]
    )
    if any(
        r.sha256 != record["sha256"]
        for r, record in zip(originals, value["originals"], strict=True)
    ):
        raise MarketStoreError("original_digest_mismatch")
    return Batch(
        tuple(parse_fact(f) for f in value["facts"]),
        originals,
        tuple(
            CoverageProof(
                date.fromisoformat(p["business_date"]),
                p["state"],
                p["evidence_id"],
                datetime.fromisoformat(p["available_at"]) if p["available_at"] else None,
            )
            for p in value["coverage"]
        ),
        value["status"],
    )


@dataclass(frozen=True)
class FrozenSnapshot:
    """Canonical bytes contain selected revisions and originals, never filesystem paths."""

    payload: bytes
    digest: str

    def __post_init__(self):
        if (
            not isinstance(self.payload, bytes)
            or len(self.payload) > MAX_EXPORT_BYTES
            or digest(self.payload) != self.digest
        ):
            raise MarketStoreError("snapshot_digest_mismatch")

    def export(self) -> bytes:
        return canonical(
            {
                "format": "market-store-frozen-v1",
                "sha256": self.digest,
                "payload": json.loads(self.payload),
            }
        )

    @classmethod
    def load(cls, content: bytes):
        try:
            if not isinstance(content, bytes) or len(content) > MAX_EXPORT_BYTES:
                raise MarketStoreError("export_limit_exceeded")
            envelope = json.loads(content)
            if envelope["format"] != "market-store-frozen-v1":
                raise MarketStoreError("unsupported_export")
            result = cls(canonical(envelope["payload"]), envelope["sha256"])
            data = json.loads(result.payload)
            StoreScope(**data["scope"])
            dataset = DatasetIdentity(
                **{**data["dataset"], "metrics": tuple(data["dataset"]["metrics"])}
            )
            batch = parse_batch(data["batch"])
            start, end = date.fromisoformat(data["start"]), date.fromisoformat(data["end"])
            as_of = datetime.fromisoformat(data["as_of"]) if data["as_of"] else None
            instant(as_of, optional=True)
            originals = {r.sha256 for r in batch.originals}
            if (
                start > end
                or batch.status != "succeeded"
                or (not batch.facts and not any(p.state != "unknown" for p in batch.coverage))
            ):
                raise MarketStoreError("invalid_snapshot_selection")
            if data["pit_complete"] is not (
                all(f.available_at is not None for f in batch.facts)
                and all(p.available_at is not None for p in batch.coverage)
            ):
                raise MarketStoreError("invalid_snapshot_pit_claim")
            for fact in batch.facts:
                if (
                    not start <= fact.business_date <= end
                    or fact.raw_hash not in originals
                    or fact.metric not in dataset.metrics
                ):
                    raise MarketStoreError("invalid_snapshot_fact")
                if as_of is not None and (fact.available_at is None or fact.available_at > as_of):
                    raise MarketStoreError("invalid_snapshot_pit_claim")
            if len({f.logical_key for f in batch.facts}) != len(batch.facts):
                raise MarketStoreError("duplicate_snapshot_fact")
            for p in batch.coverage:
                if not start <= p.business_date <= end or (
                    as_of is not None and (p.available_at is None or p.available_at > as_of)
                ):
                    raise MarketStoreError("invalid_snapshot_coverage")
            return result
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise MarketStoreError("invalid_snapshot_export") from None


@dataclass(frozen=True)
class SemanticProof:
    snapshot_digests: tuple[str, ...]
    semantic_digest: str
    evidence_id: str

    def __post_init__(self):
        if not isinstance(self.snapshot_digests, tuple) or len(self.snapshot_digests) < 2:
            raise MarketStoreError("proof_sources_required")
        if len(set(self.snapshot_digests)) != len(self.snapshot_digests):
            raise MarketStoreError("duplicate_proof_sources")
        for value in self.snapshot_digests:
            hash_value(value)
        hash_value(self.semantic_digest)
        identifier(self.evidence_id)


def merge_snapshots(
    snapshots: tuple[FrozenSnapshot, ...], proof: SemanticProof | None
) -> FrozenSnapshot:
    """Pure merge; callers must authorize every input before invoking this helper."""
    if (
        proof is None
        or len(snapshots) < 2
        or set(proof.snapshot_digests) != {s.digest for s in snapshots}
    ):
        raise MarketStoreError("semantic_proof_required")
    snapshots = tuple(sorted(snapshots, key=lambda s: s.digest))
    # Validate imported manifests as strictly as restore, before trusting PIT claims.
    documents = [json.loads(FrozenSnapshot.load(s.export()).payload) for s in snapshots]
    if any("input_scopes" in d for d in documents):
        raise MarketStoreError("nested_merge_not_supported")
    first = documents[0]
    if any(
        d["dataset"] != first["dataset"]
        or d["dataset"]["semantic_digest"] != proof.semantic_digest
        or d["as_of"] != first["as_of"]
        for d in documents
    ):
        raise MarketStoreError("dataset_semantics_mismatch")
    facts: dict[tuple, Fact] = {}
    originals = {}
    coverage = {}
    for document in documents:
        for f in parse_batch(document["batch"]).facts:
            if f.logical_key in facts and facts[f.logical_key].value_json != f.value_json:
                log.warning("market_store_merge_conflict")
                raise MarketStoreError("overlapping_fact_conflict")
            if f.logical_key not in facts or f.identity < facts[f.logical_key].identity:
                facts[f.logical_key] = f
        for raw in parse_batch(document["batch"]).originals:
            originals[raw.sha256] = raw
        for proof_item in parse_batch(document["batch"]).coverage:
            key = (
                proof_item.business_date,
                proof_item.state,
                proof_item.evidence_id,
                proof_item.available_at.isoformat() if proof_item.available_at else "",
            )
            coverage[key] = proof_item
    merged = dict(first)
    merged["start"] = min(d["start"] for d in documents)
    merged["end"] = max(d["end"] for d in documents)
    merged["batch"] = batch_document(
        Batch(
            tuple(sorted(facts.values(), key=lambda f: f.logical_key)),
            tuple(originals[k] for k in sorted(originals)),
            tuple(coverage[k] for k in sorted(coverage)),
        )
    )
    proof_document = asdict(proof)
    proof_document["snapshot_digests"] = sorted(proof.snapshot_digests)
    merged["provenance"] = {"inputs": sorted(s.digest for s in snapshots), "proof": proof_document}
    merged["input_scopes"] = [
        d["scope"] for d in sorted(documents, key=lambda d: canonical(d["scope"]))
    ]
    merged["input_manifests"] = [json.loads(s.export()) for s in snapshots]
    merged["pit_complete"] = all(f.available_at is not None for f in facts.values()) and all(
        p.available_at is not None for p in coverage.values()
    )
    payload = canonical(merged)
    return FrozenSnapshot(payload, digest(payload))
