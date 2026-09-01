"""Business service for Research Pack ingestion and typed theme projections."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from core.contracts.theme_research import (
    DatasetField,
    DatasetManifest,
    IngestionCheckpoint,
    IngestionRowResult,
    PackHealth,
    PackLifecycle,
    ThemeAssetProjection,
    ThemeEventProjection,
    ThemeIngestionReport,
    ThemeKPIProjection,
    ThemeKPIValue,
    ThemeObservation,
    ThemePackManifest,
    ThemeSnapshot,
    ThemeValueChainProjection,
    WorkspacePrefillRequest,
)
from core.observability import get_logger
from data_layer.repositories.theme_research_repository import ThemeResearchRepository
from services.theme_pack_registry import ThemePackRegistry, ThemePackValidationError

logger = get_logger(__name__)

_FORBIDDEN_FILENAMES = frozenset(
    {"driver-summary.csv", "catalysts.csv", "strategy.yml", "strategy.yaml", "orders.csv"}
)
_FORBIDDEN_FIELDS = frozenset(
    {"score_hint", "driver_summary", "target_position", "order_id", "strategy_score"}
)


class ThemePackNotFoundError(LookupError):
    """The requested Research Pack is not registered."""


class ThemeDataUnavailableError(LookupError):
    """No traceable observation is available for a fact projection."""


class ThemeIngestionError(ValueError):
    """The source file itself cannot be scanned safely."""


class ThemeResearchService:
    """Coordinate manifests, immutable observations, and six read models."""

    def __init__(
        self,
        repository: ThemeResearchRepository,
        registry: ThemePackRegistry,
        *,
        now: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self.registry = registry
        self._now = now or (lambda: datetime.now(UTC))

    def sync_manifests(self) -> list[ThemePackManifest]:
        """Validate, enable, and persist every bundled first-party Pack."""

        synced: list[ThemePackManifest] = []
        for manifest in self.registry.discover():
            current = manifest
            if current.status is PackLifecycle.DISCOVERED:
                current = self.registry.transition(current.pack_key, PackLifecycle.VALIDATED)
            if current.status is PackLifecycle.VALIDATED:
                current = self.registry.transition(current.pack_key, PackLifecycle.ENABLED)
            self.repository.save_manifest(
                current,
                content_hash=self.registry.content_hash(current),
                validation_result={"manifest": "valid"},
            )
            synced.append(current)
        logger.info("theme pack catalog synchronized", count=len(synced))
        return synced

    def list_catalog(self) -> list[ThemePackManifest]:
        """Return declared Packs without importing plugin code or fetching data."""

        return self.registry.discover()

    def ingest_file(
        self,
        pack_key: str,
        dataset_key: str,
        path: Path,
        *,
        apply: bool = False,
        checkpoint: IngestionCheckpoint | None = None,
    ) -> ThemeIngestionReport:
        """Scan a CSV deterministically; write accepted facts only with explicit apply."""

        manifest = self._manifest(pack_key)
        source_path = Path(path).resolve()
        try:
            content = source_path.read_bytes()
        except OSError as exc:
            logger.warning(
                "theme source read failed",
                pack_key=pack_key,
                dataset_key=dataset_key,
                error_type=type(exc).__name__,
            )
            raise ThemeIngestionError("theme source cannot be read") from exc
        source_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if checkpoint is not None and checkpoint.source_hash != source_hash:
            raise ThemeIngestionError("checkpoint source hash does not match the source file")
        try:
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(text.splitlines())
            rows = list(reader)
        except (UnicodeError, csv.Error) as exc:
            raise ThemeIngestionError("theme source is not valid UTF-8 CSV") from exc
        header = set(reader.fieldnames or [])
        dataset = next(
            (item for item in manifest.datasets if item.dataset_key == dataset_key),
            None,
        )
        forbidden = source_path.name.lower() in _FORBIDDEN_FILENAMES or bool(
            {name.lower() for name in header} & _FORBIDDEN_FIELDS
        )
        if forbidden or dataset is None:
            report = self._rejected_file_report(
                manifest,
                dataset_key,
                source_hash,
                rows,
                apply=apply,
                error_code="forbidden_lsh_content" if forbidden else "unknown_dataset",
            )
            if apply:
                self._persist_manifest_if_needed(manifest)
                self.repository.record_ingestion_report(report)
            logger.info(
                "theme source rejected",
                pack_key=pack_key,
                dataset_key=dataset_key,
                source_hash=source_hash,
                outcome="rejected",
                reason=report.rows[0].error_code if report.rows else "empty_file",
            )
            return report

        expected_fields = {field.name for field in dataset.fields if field.required}
        if not expected_fields.issubset(header):
            missing = expected_fields - header
            raise ThemeIngestionError(
                f"source header is missing declared fields: {sorted(missing)}"
            )

        results: list[IngestionRowResult] = []
        accepted_observations: list[ThemeObservation] = []
        seen_identity_hashes: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            if checkpoint is not None and row_number <= checkpoint.last_row_number:
                continue
            identity = self._row_identity(dataset, row)
            identity_hash = hashlib.sha256(identity.encode()).hexdigest()
            if identity_hash in seen_identity_hashes or self.repository.observation_exists(
                pack_key,
                dataset_key,
                identity_hash,
                source_hash,
            ):
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=identity_hash,
                        outcome="duplicate",
                    )
                )
                continue
            seen_identity_hashes.add(identity_hash)
            try:
                observation = self._normalize_row(
                    manifest,
                    dataset,
                    row,
                    row_number,
                    identity_hash,
                    source_hash,
                )
            except _RejectedRow as exc:
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=identity_hash,
                        outcome="rejected",
                        error_code=exc.code,
                    )
                )
            except (ValueError, ValidationError) as exc:
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=identity_hash,
                        outcome="quarantined",
                        error_code="invalid_row_semantics",
                    )
                )
                logger.info(
                    "theme row quarantined",
                    pack_key=pack_key,
                    dataset_key=dataset_key,
                    source_hash=source_hash,
                    row_identity_hash=identity_hash,
                    error_type=type(exc).__name__,
                )
            else:
                accepted_observations.append(observation)
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=identity_hash,
                        outcome="accepted",
                    )
                )

        counts = {
            key: sum(result.outcome == key for result in results)
            for key in (
                "accepted",
                "quarantined",
                "rejected",
                "duplicate",
            )
        }
        report = ThemeIngestionReport(
            pack_key=pack_key,
            dataset_key=dataset_key,
            source_hash=source_hash,
            dry_run=not apply,
            applied=len(accepted_observations) if apply else 0,
            rows=results,
            checkpoint=IngestionCheckpoint(
                source_hash=source_hash,
                last_row_number=max((result.row_number for result in results), default=1),
            ),
            **counts,
        )
        if apply:
            try:
                self._persist_manifest_if_needed(manifest)
                for observation in accepted_observations:
                    self.repository.insert_observation(observation)
                self.repository.record_ingestion_report(report)
            except (SQLAlchemyError, LookupError):
                logger.error(
                    "theme ingestion apply failed",
                    pack_key=pack_key,
                    dataset_key=dataset_key,
                    source_hash=source_hash,
                    applied=len(accepted_observations),
                )
                raise
        logger.info(
            "theme source scan completed",
            pack_key=pack_key,
            version=manifest.version,
            dataset_key=dataset_key,
            source_hash=source_hash,
            accepted=report.accepted,
            quarantined=report.quarantined,
            rejected=report.rejected,
            duplicate=report.duplicate,
            dry_run=report.dry_run,
        )
        return report

    def get_snapshot(self, pack_key: str, as_of: datetime | None = None) -> ThemeSnapshot:
        manifest = self._manifest(pack_key)
        point_in_time = self._aware(as_of or self._now())
        observations = self.repository.list_observations(pack_key, as_of=point_in_time)
        if not observations:
            raise ThemeDataUnavailableError(pack_key)
        latest: dict[str, ThemeObservation] = {}
        for observation in observations:
            latest.setdefault(f"{observation.dataset_key}:{observation.metric_key}", observation)
        observed_datasets = {item.dataset_key for item in observations}
        required = {dataset.dataset_key for dataset in manifest.datasets if dataset.required}
        coverage = len(required & observed_datasets) / len(required) if required else 1.0
        freshness = self._aggregate_freshness(list(latest.values()))
        return ThemeSnapshot(
            pack_key=pack_key,
            facts={key: value.model_dump(mode="json") for key, value in latest.items()},
            coverage=coverage,
            as_of=point_in_time,
            observed_at=max(item.observed_at for item in latest.values()),
            available_at=max(item.available_at for item in latest.values()),
            source_refs=self._unique_sources(list(latest.values())),
            freshness_status=freshness,
            quality_flags=sorted({flag for item in latest.values() for flag in item.quality_flags}),
        )

    def get_kpis(self, pack_key: str, as_of: datetime | None = None) -> ThemeKPIProjection:
        manifest = self._manifest(pack_key)
        point_in_time = self._aware(as_of or self._now())
        series: list[ThemeKPIValue] = []
        for definition in manifest.kpis:
            observations = self.repository.list_observations(
                pack_key,
                dataset_key=definition.dataset_key,
                as_of=point_in_time,
            )
            series.extend(
                ThemeKPIValue(
                    kpi_key=definition.kpi_key,
                    name=definition.name,
                    unit=definition.unit,
                    frequency=definition.frequency,
                    observation=observation,
                )
                for observation in observations
                if observation.unit == definition.unit
                or observation.unit.lower() == definition.unit.lower()
            )
        return ThemeKPIProjection(pack_key=pack_key, series=series, as_of=point_in_time)

    def get_value_chain(
        self,
        pack_key: str,
        as_of: datetime | None = None,
    ) -> ThemeValueChainProjection:
        manifest = self._manifest(pack_key)
        return ThemeValueChainProjection(
            pack_key=pack_key,
            nodes=manifest.value_chain,
            as_of=self._aware(as_of or self._now()),
        )

    def get_events(
        self,
        pack_key: str,
        as_of: datetime | None = None,
    ) -> ThemeEventProjection:
        manifest = self._manifest(pack_key)
        point_in_time = self._aware(as_of or self._now())
        observations = self.repository.list_observations(pack_key, as_of=point_in_time)
        events = [
            item
            for item in observations
            if item.dataset_key.endswith("events")
            or item.metric_key in manifest.event_types
            or item.payload.get("record_type") == "event"
        ]
        verified = [
            item
            for item in events
            if any(
                source.tier in {SourceTier.OFFICIAL, SourceTier.LICENSED}
                for source in item.source_refs
            )
            and item.payload.get("verification_status", "verified") == "verified"
        ]
        leads = [item for item in events if item not in verified]
        return ThemeEventProjection(
            pack_key=pack_key,
            verified=verified,
            leads=leads,
            as_of=point_in_time,
        )

    def get_assets(
        self,
        pack_key: str,
        as_of: datetime | None = None,
    ) -> ThemeAssetProjection:
        manifest = self._manifest(pack_key)
        return ThemeAssetProjection(
            pack_key=pack_key,
            assets=manifest.asset_exposures,
            as_of=self._aware(as_of or self._now()),
        )

    def get_health(self, pack_key: str, as_of: datetime | None = None) -> PackHealth:
        manifest = self._manifest(pack_key)
        point_in_time = self._aware(as_of or self._now())
        observations = self.repository.list_observations(pack_key, as_of=point_in_time)
        latest_by_dataset: dict[str, datetime] = {}
        for observation in observations:
            latest_by_dataset.setdefault(observation.dataset_key, observation.available_at)
        coverage: dict[str, float] = {}
        ages: dict[str, float | None] = {}
        flags: list[str] = []
        for dataset in manifest.datasets:
            latest = latest_by_dataset.get(dataset.dataset_key)
            age = max(0.0, (point_in_time - latest).total_seconds()) if latest else None
            ages[dataset.dataset_key] = age
            usable = latest is not None and age is not None and age <= dataset.freshness_seconds
            coverage[dataset.dataset_key] = 1.0 if usable else 0.0
            if dataset.required and not usable:
                flags.append(f"required_dataset_unavailable:{dataset.dataset_key}")
        self._reconcile_health_lifecycle(manifest, flags)
        return PackHealth(
            pack_key=pack_key,
            dataset_coverage=coverage,
            dataset_age_seconds=ages,
            quality_flags=flags,
            **self.repository.ingestion_totals(pack_key),
        )

    def create_research_workspace_request(
        self,
        pack_key: str,
        title: str | None = None,
    ) -> WorkspacePrefillRequest:
        """Build the future Workspace command without writing research or fact tables."""

        manifest = self._manifest(pack_key)
        template_key = manifest.research_template_keys[0]
        request = WorkspacePrefillRequest(
            pack_key=pack_key,
            title=title or f"{manifest.name}主题研究",
            template_key=template_key,
            context={"theme_pack": pack_key},
        )
        logger.info(
            "theme research workspace prefill created",
            pack_key=pack_key,
            template_key=template_key,
        )
        return request

    def _manifest(self, pack_key: str) -> ThemePackManifest:
        try:
            return self.registry.get(pack_key)
        except ThemePackValidationError as exc:
            raise ThemePackNotFoundError(pack_key) from exc

    def _persist_manifest_if_needed(self, manifest: ThemePackManifest) -> None:
        self.repository.save_manifest(
            manifest,
            content_hash=self.registry.content_hash(manifest),
        )

    def _normalize_row(
        self,
        manifest: ThemePackManifest,
        dataset: DatasetManifest,
        row: dict[str, str],
        row_number: int,
        identity_hash: str,
        source_hash: str,
    ) -> ThemeObservation:
        fields = {field.name: field for field in dataset.fields}
        for field in dataset.fields:
            if field.required and not (row.get(field.name) or "").strip():
                if field.name == dataset.unit_field:
                    raise _RejectedRow("numeric_unit_missing")
                raise ValueError(f"required field missing: {field.name}")
        observed_at = self._parse_datetime(
            row[dataset.observed_at_field], fields[dataset.observed_at_field]
        )
        available_at = (
            self._parse_datetime(
                row[dataset.available_at_field], fields[dataset.available_at_field]
            )
            if dataset.available_at_field
            else observed_at
        )
        value = self._parse_value(row[dataset.value_field], fields[dataset.value_field])
        unit = row.get(dataset.unit_field, "").strip() if dataset.unit_field else dataset.fixed_unit
        if isinstance(value, (int, float)) and not unit:
            raise _RejectedRow("numeric_unit_missing")
        source_name = (
            row.get(dataset.source_name_field, "").strip()
            if dataset.source_name_field
            else dataset.source_priority[0]
        ) or dataset.source_priority[0]
        source_url = (
            row.get(dataset.source_url_field, "").strip() if dataset.source_url_field else None
        ) or None
        source = SourceRef(
            source_id=self._slug(source_name),
            name=source_name,
            tier=self._source_tier(source_name, dataset.source_priority),
            content_hash=source_hash,
            source_url=source_url,
        )
        freshness = self._freshness(dataset, row, available_at)
        quality_flags = [] if freshness is FreshnessStatus.FRESH else ["source_reported_not_fresh"]
        return ThemeObservation(
            observation_id=f"theme-observation-{hashlib.sha256(f'{source_hash}:{identity_hash}'.encode()).hexdigest()}",
            pack_key=manifest.pack_key,
            dataset_key=dataset.dataset_key,
            row_identity=identity_hash,
            subject_ref=f"theme:{manifest.pack_key}:{row[dataset.subject_field].strip()}",
            metric_key=row[dataset.metric_field].strip(),
            value=value,
            unit=unit,
            as_of=available_at,
            observed_at=observed_at,
            available_at=available_at,
            source_refs=[source],
            freshness_status=freshness,
            quality_flags=quality_flags,
            source_hash=source_hash,
            payload={
                key: value
                for key, value in row.items()
                if key in fields and key not in _FORBIDDEN_FIELDS
            }
            | {"source_row_number": row_number},
        )

    def _rejected_file_report(
        self,
        manifest: ThemePackManifest,
        dataset_key: str,
        source_hash: str,
        rows: list[dict[str, str]],
        *,
        apply: bool,
        error_code: str,
    ) -> ThemeIngestionReport:
        row_results = []
        for row_number, row in enumerate(rows, start=2):
            safe_identity = "|".join(str(row.get(key, "")) for key in sorted(row))
            row_results.append(
                IngestionRowResult(
                    row_number=row_number,
                    row_identity_hash=hashlib.sha256(safe_identity.encode()).hexdigest(),
                    outcome="rejected",
                    error_code=error_code,
                )
            )
        if not row_results:
            row_results.append(
                IngestionRowResult(
                    row_number=2,
                    row_identity_hash=hashlib.sha256(source_hash.encode()).hexdigest(),
                    outcome="rejected",
                    error_code=error_code,
                )
            )
        return ThemeIngestionReport(
            pack_key=manifest.pack_key,
            dataset_key=dataset_key,
            source_hash=source_hash,
            dry_run=not apply,
            accepted=0,
            quarantined=0,
            rejected=len(row_results),
            duplicate=0,
            applied=0,
            rows=row_results,
            checkpoint=IngestionCheckpoint(
                source_hash=source_hash,
                last_row_number=row_results[-1].row_number,
            ),
        )

    @staticmethod
    def _row_identity(dataset: DatasetManifest, row: dict[str, str]) -> str:
        return "\x1f".join((row.get(field) or "").strip() for field in dataset.identity_fields)

    def _freshness(
        self,
        dataset: DatasetManifest,
        row: dict[str, str],
        available_at: datetime,
    ) -> FreshnessStatus:
        raw = (row.get(dataset.freshness_field, "") if dataset.freshness_field else "").lower()
        if raw in {status.value for status in FreshnessStatus}:
            reported = FreshnessStatus(raw)
            if reported is not FreshnessStatus.FRESH:
                return reported
        age = max(0.0, (self._aware(self._now()) - available_at).total_seconds())
        return FreshnessStatus.FRESH if age <= dataset.freshness_seconds else FreshnessStatus.STALE

    @staticmethod
    def _parse_datetime(value: str, field: DatasetField) -> datetime:
        text = value.strip()
        if field.data_type == "date":
            parsed_date = date.fromisoformat(text[:10])
            return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
        parsed = datetime.fromisoformat(text)
        return ThemeResearchService._aware(parsed)

    @staticmethod
    def _parse_value(value: str, field: DatasetField) -> Any:
        text = value.strip()
        if field.data_type == "number":
            return float(text.replace(",", ""))
        if field.data_type == "integer":
            return int(text.replace(",", ""))
        if field.data_type == "boolean":
            normalized = text.lower()
            if normalized not in {"true", "false", "1", "0", "yes", "no"}:
                raise ValueError("invalid boolean")
            return normalized in {"true", "1", "yes"}
        return text

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(value.lower().split()) or "source"

    @staticmethod
    def _source_tier(source_name: str, priorities: list[str]) -> SourceTier:
        normalized = f"{source_name} {' '.join(priorities)}".lower()
        if any(token in normalized for token in ("official", "exchange", "imf", "lbma", "sge")):
            return SourceTier.OFFICIAL
        if "licensed" in normalized:
            return SourceTier.LICENSED
        return SourceTier.PUBLIC

    @staticmethod
    def _aggregate_freshness(observations: list[ThemeObservation]) -> FreshnessStatus:
        statuses = {item.freshness_status for item in observations}
        for status in (
            FreshnessStatus.QUARANTINED,
            FreshnessStatus.UNAVAILABLE,
            FreshnessStatus.STALE,
            FreshnessStatus.FRESH,
        ):
            if status in statuses:
                return status
        return FreshnessStatus.UNAVAILABLE

    @staticmethod
    def _unique_sources(observations: list[ThemeObservation]) -> list[SourceRef]:
        result: dict[str, SourceRef] = {}
        for observation in observations:
            for source in observation.source_refs:
                key = f"{source.source_id}:{source.content_hash}:{source.source_url}"
                result.setdefault(key, source)
        return list(result.values())

    def _reconcile_health_lifecycle(
        self,
        manifest: ThemePackManifest,
        flags: list[str],
    ) -> None:
        target: PackLifecycle | None = None
        if flags and manifest.status is PackLifecycle.ENABLED:
            target = PackLifecycle.DEGRADED
        elif not flags and manifest.status is PackLifecycle.DEGRADED:
            target = PackLifecycle.ENABLED
        if target is None:
            return
        updated = self.registry.transition(manifest.pack_key, target)
        try:
            self.repository.update_pack_status(
                updated.pack_key, updated.version, updated.status.value
            )
        except LookupError:
            logger.info(
                "theme pack lifecycle not persisted because catalog is not synchronized",
                pack_key=updated.pack_key,
                status=updated.status.value,
            )


class _RejectedRow(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)
