"""Persistence adapter for Research Pack manifests and theme observations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError

from core.contracts.theme_research import (
    ThemeIngestionReport,
    ThemeObservation,
    ThemePackManifest,
)
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import ThemeObservationDB, ThemePackDB

logger = get_logger(__name__)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ThemeResearchRepository(BaseRepository):
    """Own Pack metadata and the one shared theme fact table."""

    def save_manifest(
        self,
        manifest: ThemePackManifest,
        *,
        content_hash: str,
        validation_result: dict[str, Any] | None = None,
    ) -> ThemePackDB:
        """Idempotently persist one versioned manifest without committing."""

        try:
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
                row.compatibility_version = manifest.compatibility_version
                row.status = manifest.status.value
                row.manifest = manifest.model_dump(mode="json")
                row.content_hash = content_hash
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

    def update_pack_status(self, pack_key: str, version: str, status: str) -> None:
        """Persist a validated lifecycle transition."""

        try:
            row = self.db.scalar(
                select(ThemePackDB).where(
                    and_(ThemePackDB.pack_key == pack_key, ThemePackDB.version == version)
                )
            )
            if row is None:
                raise LookupError("theme pack version not persisted")
            row.status = status
            row.updated_at = datetime.now(UTC)
            self.db.flush()
        except SQLAlchemyError as exc:
            logger.error(
                "theme pack status update failed",
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
        ingestion = (row.validation_result or {}).get("ingestion", {})
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
            as_of=_aware(row.as_of),
            observed_at=_aware(row.observed_at),
            available_at=_aware(row.available_at),
            source_refs=row.source_refs,
            freshness_status=row.freshness_status,
            quality_flags=list(row.quality_flags or []),
            source_hash=row.source_hash,
            payload=dict(row.payload or {}),
        )
