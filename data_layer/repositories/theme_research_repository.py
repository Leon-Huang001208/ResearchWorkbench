"""Persistence adapter for Research Pack manifests and theme observations."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import and_, event, func, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from core.contracts.theme_research import (
    PackLifecycle,
    ThemeIngestionReport,
    ThemeObservation,
    ThemePackManifest,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ThemeObservationDB, ThemePackDB

logger = get_logger(__name__)

_SQLITE_LOCKS_GUARD = threading.Lock()
_SQLITE_DATASET_LOCKS: dict[str, threading.RLock] = {}
_PACK_LIFECYCLE_TRANSITIONS: dict[PackLifecycle, frozenset[PackLifecycle]] = {
    PackLifecycle.DISCOVERED: frozenset({PackLifecycle.VALIDATED}),
    PackLifecycle.VALIDATED: frozenset({PackLifecycle.ENABLED, PackLifecycle.DISABLED}),
    PackLifecycle.ENABLED: frozenset({PackLifecycle.DEGRADED, PackLifecycle.DISABLED}),
    PackLifecycle.DEGRADED: frozenset({PackLifecycle.ENABLED, PackLifecycle.DISABLED}),
    PackLifecycle.DISABLED: frozenset(),
}


def _release_sqlite_theme_locks(db, transaction) -> None:
    """Release process-local compatibility locks after the outer transaction."""

    if transaction.parent is not None:
        return
    locks = db.info.pop("theme_research_sqlite_locks", {})
    for lock in reversed(list(locks.values())):
        lock.release()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _manifest_content_hash(manifest: ThemePackManifest) -> str:
    """Compute the repository-owned canonical declaration hash."""

    payload = manifest.model_dump_json(exclude_none=True, exclude={"status"})
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


class ThemeResearchRepository(BaseRepository):
    """Own Pack metadata and the one shared theme fact table."""

    def lock_ingestion_namespace(self, pack_key: str, dataset_key: str) -> None:
        """Serialize one dataset until commit so semantic checks see prior writers."""

        lock_name = f"theme-observation:{pack_key}:{dataset_key}"
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            self._pg_advisory_xact_lock(lock_name)
            return
        if dialect != "sqlite":
            logger.warning(
                "theme ingestion uses process-local compatibility lock",
                dialect=dialect,
                pack_key=pack_key,
                dataset_key=dataset_key,
            )
        held = self.db.info.setdefault("theme_research_sqlite_locks", {})
        if lock_name in held:
            if self.db.in_transaction():
                return
            stale_lock = held.pop(lock_name)
            stale_lock.release()
        if not self.db.info.get("theme_research_lock_listener_registered"):
            event.listen(self.db, "after_transaction_end", _release_sqlite_theme_locks)
            self.db.info["theme_research_lock_listener_registered"] = True
        if not self.db.in_transaction():
            self.db.begin()
        with _SQLITE_LOCKS_GUARD:
            lock = _SQLITE_DATASET_LOCKS.setdefault(lock_name, threading.RLock())
        lock.acquire()
        held[lock_name] = lock

    def lock_observation_identity(
        self,
        pack_key: str,
        dataset_key: str,
        row_identity: str,
    ) -> None:
        """Take a PostgreSQL transaction lock for one semantic fact identity."""

        if self.db.get_bind().dialect.name != "postgresql":
            return
        self._pg_advisory_xact_lock(f"theme-observation:{pack_key}:{dataset_key}:{row_identity}")

    def _pg_advisory_xact_lock(self, lock_name: str) -> None:
        lock_key = int.from_bytes(
            hashlib.sha256(lock_name.encode()).digest()[:8],
            byteorder="big",
            signed=True,
        )
        try:
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": lock_key},
            )
        except SQLAlchemyError as exc:
            logger.error(
                "theme semantic advisory lock failed",
                lock_name=lock_name,
                error_type=type(exc).__name__,
            )
            raise

    def save_manifest(
        self,
        manifest: ThemePackManifest,
        *,
        validation_result: dict[str, Any] | None = None,
    ) -> ThemePackDB:
        """Persist one immutable version using repository-canonical content."""

        try:
            content_hash = _manifest_content_hash(manifest)
            row = self.db.scalar(
                select(ThemePackDB).where(
                    and_(
                        ThemePackDB.pack_key == manifest.pack_key,
                        ThemePackDB.version == manifest.version,
                    )
                )
            )
            now = datetime.now(UTC)
            if row is None:
                row = ThemePackDB(
                    pack_id=f"theme-pack-{uuid4()}",
                    pack_key=manifest.pack_key,
                    version=manifest.version,
                    compatibility_version=manifest.compatibility_version,
                    status=manifest.status.value,
                    manifest=manifest.model_dump(mode="json"),
                    content_hash=content_hash,
                    validation_result=validation_result or {"manifest": "valid"},
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(row)
            else:
                persisted = ThemePackManifest.model_validate(
                    dict(row.manifest or {}) | {"status": row.status}
                )
                persisted_hash = _manifest_content_hash(persisted)
                if persisted_hash != content_hash:
                    logger.warning(
                        "immutable theme pack version conflict",
                        pack_key=manifest.pack_key,
                        version=manifest.version,
                    )
                    raise ValueError("theme pack version is immutable; publish a new version")
                authoritative = manifest.model_copy(update={"status": PackLifecycle(row.status)})
                row.manifest = authoritative.model_dump(mode="json")
                row.content_hash = persisted_hash
                if validation_result is not None:
                    merged_validation = dict(row.validation_result or {})
                    merged_validation.update(validation_result)
                    row.validation_result = merged_validation
                row.updated_at = now
            self.db.flush()
            return row
        except SQLAlchemyError as exc:
            logger.error(
                "theme pack persistence failed",
                pack_key=manifest.pack_key,
                version=manifest.version,
                error_type=type(exc).__name__,
            )
            raise

    def update_pack_status(
        self,
        pack_key: str,
        version: str,
        status: PackLifecycle,
    ) -> None:
        """Persist a validated lifecycle transition."""

        try:
            if not isinstance(status, PackLifecycle):
                raise ValueError("status must be a PackLifecycle value")
            row = self.db.scalar(
                select(ThemePackDB).where(
                    and_(ThemePackDB.pack_key == pack_key, ThemePackDB.version == version)
                )
            )
            if row is None:
                raise LookupError("theme pack version not persisted")
            current = PackLifecycle(row.status)
            if status is not current and status not in _PACK_LIFECYCLE_TRANSITIONS[current]:
                logger.warning(
                    "illegal theme pack lifecycle transition rejected",
                    pack_key=pack_key,
                    version=version,
                    previous_status=current.value,
                    status=status.value,
                )
                raise ValueError(f"invalid lifecycle transition: {current.value} -> {status.value}")
            if status is current:
                return
            result = self.db.execute(
                update(ThemePackDB)
                .where(
                    and_(
                        ThemePackDB.pack_key == pack_key,
                        ThemePackDB.version == version,
                        ThemePackDB.status == current.value,
                    )
                )
                .values(
                    status=status.value,
                    manifest=dict(row.manifest or {}) | {"status": status.value},
                    updated_at=datetime.now(UTC),
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                self.db.expire(row)
                logger.warning(
                    "concurrent theme pack lifecycle transition rejected",
                    pack_key=pack_key,
                    version=version,
                    expected_status=current.value,
                    status=status.value,
                )
                raise ValueError("concurrent lifecycle transition changed expected status")
            self.db.expire(row)
        except SQLAlchemyError as exc:
            logger.error(
                "theme pack status update failed",
                pack_key=pack_key,
                version=version,
                error_type=type(exc).__name__,
            )
            raise

    def get_manifest(
        self,
        pack_key: str,
        version: str | None = None,
    ) -> ThemePackManifest | None:
        """Return the database-authoritative lifecycle for a persisted manifest."""

        try:
            statement = select(ThemePackDB).where(ThemePackDB.pack_key == pack_key)
            if version is not None:
                statement = statement.where(ThemePackDB.version == version)
            row = self.db.scalar(statement.order_by(ThemePackDB.created_at.desc()))
            if row is None:
                return None
            return ThemePackManifest.model_validate(
                dict(row.manifest or {}) | {"status": row.status}
            )
        except (SQLAlchemyError, ValueError) as exc:
            logger.error(
                "theme pack authority read failed",
                pack_key=pack_key,
                version=version,
                error_type=type(exc).__name__,
            )
            raise

    def observation_exists(
        self,
        pack_key: str,
        dataset_key: str,
        row_identity: str,
        source_hash: str,
    ) -> bool:
        """Check the immutable source+row idempotency key."""

        try:
            return (
                self.db.scalar(
                    select(func.count())
                    .select_from(ThemeObservationDB)
                    .where(
                        and_(
                            ThemeObservationDB.pack_key == pack_key,
                            ThemeObservationDB.dataset_key == dataset_key,
                            ThemeObservationDB.row_identity == row_identity,
                            ThemeObservationDB.source_hash == source_hash,
                        )
                    )
                )
                or 0
            ) > 0
        except SQLAlchemyError as exc:
            logger.error(
                "theme observation idempotency query failed",
                pack_key=pack_key,
                dataset_key=dataset_key,
                error_type=type(exc).__name__,
            )
            raise

    def get_observation_by_identity(
        self,
        pack_key: str,
        dataset_key: str,
        row_identity: str,
    ) -> ThemeObservation | None:
        """Find the immutable semantic identity regardless of source-file hash."""

        try:
            row = self.db.scalar(
                select(ThemeObservationDB)
                .where(
                    and_(
                        ThemeObservationDB.pack_key == pack_key,
                        ThemeObservationDB.dataset_key == dataset_key,
                        ThemeObservationDB.row_identity == row_identity,
                    )
                )
                .order_by(
                    ThemeObservationDB.available_at.desc(),
                    ThemeObservationDB.observation_id,
                )
            )
            return self._to_observation(row) if row is not None else None
        except SQLAlchemyError as exc:
            logger.error(
                "theme observation semantic identity query failed",
                pack_key=pack_key,
                dataset_key=dataset_key,
                error_type=type(exc).__name__,
            )
            raise

    def insert_observation(self, observation: ThemeObservation) -> None:
        """Insert an accepted immutable observation without committing."""

        try:
            self.db.add(
                ThemeObservationDB(
                    observation_id=observation.observation_id,
                    pack_key=observation.pack_key,
                    dataset_key=observation.dataset_key,
                    row_identity=observation.row_identity,
                    subject_ref=observation.subject_ref,
                    metric_key=observation.metric_key,
                    value=observation.value,
                    unit=observation.unit,
                    missing_reason=observation.missing_reason,
                    as_of=observation.as_of,
                    observed_at=observation.observed_at,
                    available_at=observation.available_at,
                    source_refs=[
                        source.model_dump(mode="json") for source in observation.source_refs
                    ],
                    freshness_status=observation.freshness_status.value,
                    quality_flags=observation.quality_flags,
                    source_hash=observation.source_hash,
                    payload=observation.payload,
                    created_at=datetime.now(UTC),
                )
            )
            self.db.flush()
        except SQLAlchemyError as exc:
            logger.error(
                "theme observation insert failed",
                pack_key=observation.pack_key,
                dataset_key=observation.dataset_key,
                source_hash=observation.source_hash,
                error_type=type(exc).__name__,
            )
            raise

    def list_observations(
        self,
        pack_key: str,
        *,
        dataset_key: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ThemeObservation]:
        """Read observations available at a point in time."""

        try:
            statement = select(ThemeObservationDB).where(ThemeObservationDB.pack_key == pack_key)
            if dataset_key is not None:
                statement = statement.where(ThemeObservationDB.dataset_key == dataset_key)
            if as_of is not None:
                statement = statement.where(ThemeObservationDB.available_at <= _aware(as_of))
            rows = self.db.scalars(
                statement.order_by(
                    ThemeObservationDB.available_at.desc(),
                    ThemeObservationDB.observation_id,
                )
            ).all()
            return [self._to_observation(row) for row in rows]
        except SQLAlchemyError as exc:
            logger.error(
                "theme observation query failed",
                pack_key=pack_key,
                dataset_key=dataset_key,
                error_type=type(exc).__name__,
            )
            raise

    def count_observations(self, pack_key: str) -> int:
        try:
            return int(
                self.db.scalar(
                    select(func.count())
                    .select_from(ThemeObservationDB)
                    .where(ThemeObservationDB.pack_key == pack_key)
                )
                or 0
            )
        except SQLAlchemyError as exc:
            logger.error(
                "theme observation count failed",
                pack_key=pack_key,
                error_type=type(exc).__name__,
            )
            raise

    def record_ingestion_report(self, report: ThemeIngestionReport) -> None:
        """Persist aggregate outcomes/checkpoint in Pack validation metadata."""

        try:
            row = self.db.scalar(
                select(ThemePackDB)
                .where(ThemePackDB.pack_key == report.pack_key)
                .order_by(ThemePackDB.created_at.desc())
            )
            if row is None:
                raise LookupError("theme pack not persisted")
            validation = dict(row.validation_result or {})
            ingestion = dict(validation.get("ingestion") or {})
            dataset_runs = dict(ingestion.get(report.dataset_key) or {})
            dataset_runs[report.source_hash] = report.model_dump(mode="json", exclude={"rows"})
            ingestion[report.dataset_key] = dataset_runs
            validation["ingestion"] = ingestion
            row.validation_result = validation
            row.updated_at = datetime.now(UTC)
            self.db.flush()
        except SQLAlchemyError as exc:
            logger.error(
                "theme ingestion report persistence failed",
                pack_key=report.pack_key,
                dataset_key=report.dataset_key,
                source_hash=report.source_hash,
                error_type=type(exc).__name__,
            )
            raise

    def ingestion_totals(self, pack_key: str) -> dict[str, int]:
        """Aggregate persisted apply reports for health projection."""

        row = self.db.scalar(
            select(ThemePackDB)
            .where(ThemePackDB.pack_key == pack_key)
            .order_by(ThemePackDB.created_at.desc())
        )
        totals = {"accepted": 0, "quarantined": 0, "rejected": 0, "duplicate": 0}
        if row is None:
            return totals
        validation_result = cast(dict[str, Any], row.validation_result or {})
        ingestion = cast(dict[str, Any], validation_result.get("ingestion", {}))
        for runs in ingestion.values():
            for report in runs.values():
                for key in totals:
                    totals[key] += int(report.get(key, 0))
        return totals

    @staticmethod
    def _to_observation(row: ThemeObservationDB) -> ThemeObservation:
        return ThemeObservation(
            observation_id=row.observation_id,
            pack_key=row.pack_key,
            dataset_key=row.dataset_key,
            row_identity=row.row_identity,
            subject_ref=row.subject_ref,
            metric_key=row.metric_key,
            value=row.value,
            unit=row.unit,
            missing_reason=row.missing_reason,
            as_of=_aware(cast(datetime, row.as_of)),
            observed_at=_aware(cast(datetime, row.observed_at)),
            available_at=_aware(cast(datetime, row.available_at)),
            source_refs=row.source_refs,
            freshness_status=row.freshness_status,
            quality_flags=list(row.quality_flags or []),
            source_hash=row.source_hash,
            payload=dict(row.payload or {}),
        )
