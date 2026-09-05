"""Business service for Research Pack ingestion and typed theme projections."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from core.contracts.market_home import MarketHomeSectionKey
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
from data_layer.repositories.market_home_invalidation import (
    record_market_home_fact_update,
)
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
        for declared in self.registry.discover():
            persisted = self.repository.get_manifest(declared.pack_key, declared.version)
            current = persisted or declared
            if persisted is None and current.status is PackLifecycle.DISCOVERED:
                current = self.registry.transition(current.pack_key, PackLifecycle.VALIDATED)
            if persisted is None and current.status is PackLifecycle.VALIDATED:
                current = self.registry.transition(current.pack_key, PackLifecycle.ENABLED)
            self.repository.save_manifest(
                current,
                validation_result={"manifest": "valid"},
            )
            synced.append(current)
        logger.info("theme pack catalog synchronized", count=len(synced))
        return synced

    def list_catalog(self) -> list[ThemePackManifest]:
        """Return declared Packs without importing plugin code or fetching data."""

        manifests = []
        for declared in self.registry.discover():
            manifests.append(
                self.repository.get_manifest(declared.pack_key, declared.version) or declared
            )
        return manifests

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

        try:
            declared = self.registry.get(pack_key)
        except ThemePackValidationError as exc:
            raise ThemePackNotFoundError(pack_key) from exc
        if apply:
            self.repository.lock_ingestion_namespace(pack_key, dataset_key)
        manifest = self.repository.get_manifest(declared.pack_key, declared.version) or declared
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
        ingestion_mode = "apply" if apply else "dry-run"
        if checkpoint is not None and checkpoint.source_hash != source_hash:
            raise ThemeIngestionError("checkpoint source hash does not match the source file")
        if checkpoint is not None and checkpoint.mode != ingestion_mode:
            raise ThemeIngestionError("checkpoint mode does not match the ingestion mode")
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
        seen_observations: dict[str, ThemeObservation] = {}
        for row_number, row in enumerate(rows, start=2):
            if checkpoint is not None and row_number <= checkpoint.last_row_number:
                continue
            base_identity = self._row_identity(dataset, row)
            fallback_hash = hashlib.sha256(base_identity.encode()).hexdigest()
            try:
                observations = self._normalize_row(
                    manifest,
                    dataset,
                    row,
                    row_number,
                    source_hash,
                )
            except _RejectedRow as exc:
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=fallback_hash,
                        outcome="rejected",
                        error_code=exc.code,
                    )
                )
            except (ValueError, ValidationError) as exc:
                results.append(
                    IngestionRowResult(
                        row_number=row_number,
                        row_identity_hash=fallback_hash,
                        outcome="quarantined",
                        error_code="invalid_row_semantics",
                    )
                )
                logger.info(
                    "theme row quarantined",
                    pack_key=pack_key,
                    dataset_key=dataset_key,
                    source_hash=source_hash,
                    row_identity_hash=fallback_hash,
                    error_type=type(exc).__name__,
                )
            else:
                if not observations:
                    results.append(
                        IngestionRowResult(
                            row_number=row_number,
                            row_identity_hash=fallback_hash,
                            outcome="quarantined",
                            error_code="no_observation_values",
                        )
                    )
                    continue
                for observation in observations:
                    if apply:
                        self.repository.lock_observation_identity(
                            pack_key,
                            dataset_key,
                            observation.row_identity,
                        )
                    existing = seen_observations.get(observation.row_identity)
                    if existing is None:
                        existing = self.repository.get_observation_by_identity(
                            pack_key,
                            dataset_key,
                            observation.row_identity,
                        )
                    if existing is not None:
                        if self._same_normalized_payload(existing, observation):
                            outcome = "duplicate"
                            error_code = None
                        else:
                            outcome = "quarantined"
                            error_code = "identity_payload_conflict"
                        results.append(
                            IngestionRowResult(
                                row_number=row_number,
                                row_identity_hash=observation.row_identity,
                                outcome=outcome,
                                error_code=error_code,
                            )
                        )
                        continue
                    seen_observations[observation.row_identity] = observation
                    accepted_observations.append(observation)
                    results.append(
                        IngestionRowResult(
                            row_number=row_number,
                            row_identity_hash=observation.row_identity,
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
                mode=ingestion_mode,
                last_row_number=max(
                    (result.row_number for result in results),
                    default=checkpoint.last_row_number if checkpoint is not None else 1,
                ),
            ),
            **counts,
        )
        if apply:
            try:
                self._persist_manifest_if_needed(manifest)
                for observation in accepted_observations:
                    self.repository.insert_observation(observation)
                self.repository.record_ingestion_report(report)
                sections = self._market_home_sections(dataset)
                if sections and accepted_observations:
                    record_market_home_fact_update(
                        self.repository.db,
                        sections,
                        as_of=max(
                            observation.available_at for observation in accepted_observations
                        ),
                        idempotency_key=(f"theme:{pack_key}:{dataset_key}:{source_hash}"),
                    )
            except (SQLAlchemyError, LookupError, ValueError):
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
        latest = self._select_latest_facts(observations)
        datasets = {dataset.dataset_key: dataset for dataset in manifest.datasets}
        latest = {
            key: self._with_effective_freshness(
                observation,
                datasets.get(observation.dataset_key),
                point_in_time,
            )
            for key, observation in latest.items()
        }
        selected_by_dataset: dict[str, list[ThemeObservation]] = {}
        for observation in latest.values():
            selected_by_dataset.setdefault(observation.dataset_key, []).append(observation)
        usable_datasets = {
            dataset_key
            for dataset_key, selected in selected_by_dataset.items()
            if selected
            and all(
                self._effective_freshness(item, datasets.get(dataset_key), point_in_time)
                is FreshnessStatus.FRESH
                for item in selected
            )
        }
        required = {dataset.dataset_key for dataset in manifest.datasets if dataset.required}
        coverage = len(required & usable_datasets) / len(required) if required else 1.0
        freshness = self._aggregate_freshness(
            [
                self._effective_freshness(item, datasets.get(item.dataset_key), point_in_time)
                for item in latest.values()
            ]
        )
        return ThemeSnapshot(
            pack_key=pack_key,
            facts={key: value.model_dump(mode="json") for key, value in latest.items()},
            coverage=coverage,
            as_of=max(item.as_of for item in latest.values()),
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
        datasets = {dataset.dataset_key: dataset for dataset in manifest.datasets}
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
                    observation=self._with_effective_freshness(
                        observation,
                        datasets.get(observation.dataset_key),
                        point_in_time,
                    ),
                )
                for observation in observations
                if observation.metric_key == definition.metric_key
                and observation.unit is not None
                and observation.unit.casefold() == definition.unit.casefold()
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
        datasets = {dataset.dataset_key: dataset for dataset in manifest.datasets}
        events = [
            self._with_effective_freshness(
                item,
                datasets.get(item.dataset_key),
                point_in_time,
            )
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
            and item.payload.get("verification_status") == "verified"
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
        selected = self._select_latest_facts(observations)
        selected_by_dataset: dict[str, list[ThemeObservation]] = {}
        for observation in selected.values():
            selected_by_dataset.setdefault(observation.dataset_key, []).append(observation)
        coverage: dict[str, float] = {}
        ages: dict[str, float | None] = {}
        flags: list[str] = []
        for dataset in manifest.datasets:
            dataset_facts = selected_by_dataset.get(dataset.dataset_key, [])
            fact_ages = [
                max(0.0, (point_in_time - fact.available_at).total_seconds())
                for fact in dataset_facts
            ]
            age = max(fact_ages) if fact_ages else None
            ages[dataset.dataset_key] = age
            usable = bool(dataset_facts) and all(
                self._effective_freshness(fact, dataset, point_in_time) is FreshnessStatus.FRESH
                for fact in dataset_facts
            )
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
            declared = self.registry.get(pack_key)
            return self.repository.get_manifest(declared.pack_key, declared.version) or declared
        except ThemePackValidationError as exc:
            raise ThemePackNotFoundError(pack_key) from exc

    def _persist_manifest_if_needed(self, manifest: ThemePackManifest) -> None:
        self.repository.save_manifest(
            manifest,
        )

    def _normalize_row(
        self,
        manifest: ThemePackManifest,
        dataset: DatasetManifest,
        row: dict[str, str],
        row_number: int,
        source_hash: str,
    ) -> list[ThemeObservation]:
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
            tier=self._source_tier(source_name, dataset.source_tiers),
            content_hash=source_hash,
            source_url=source_url,
        )
        freshness = self._freshness(dataset, row, available_at)
        quality_flags = [] if freshness is FreshnessStatus.FRESH else ["source_reported_not_fresh"]
        normalized_payload = {
            name: self._normalize_payload_value(row.get(name, ""), field)
            for name, field in fields.items()
            if name not in _FORBIDDEN_FIELDS and (row.get(name) or "").strip()
        }
        if dataset.verification_field:
            normalized_payload["verification_status"] = (
                row.get(dataset.verification_field, "").strip().lower()
            )
        normalized_payload["source_row_number"] = row_number
        identity_values = [normalized_payload[field] for field in dataset.identity_fields]
        if dataset.source_row_discriminator == "row_number":
            identity_values.append(row_number)
        base_identity = json.dumps(
            identity_values,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        subject_ref = f"theme:{manifest.pack_key}:{row[dataset.subject_field].strip()}"
        if dataset.dimension_fields:
            dimensions = [
                f"{field}={quote(str(normalized_payload[field]), safe='')}"
                for field in dataset.dimension_fields
            ]
            if dataset.source_row_discriminator == "row_number":
                dimensions.append(f"source_row_number={row_number}")
            dimension_key = "|".join(dimensions)
            normalized_payload["dimension_key"] = dimension_key
            subject_ref = f"theme:{manifest.pack_key}:{dataset.dataset_key}:{dimension_key}"
        base_metric = row[dataset.metric_field].strip()
        mappings: list[tuple[str, str, str | None, str | None]] = []
        if dataset.observation_fields:
            for mapping in dataset.observation_fields:
                metric_key = mapping.metric_key or f"{base_metric}.{mapping.metric_suffix}"
                mappings.append(
                    (
                        mapping.value_field,
                        metric_key,
                        mapping.unit_field,
                        mapping.fixed_unit,
                    )
                )
        else:
            mappings.append(
                (
                    dataset.value_field,
                    base_metric,
                    dataset.unit_field,
                    dataset.fixed_unit,
                )
            )

        observations: list[ThemeObservation] = []
        for value_field, metric_key, unit_field, fixed_unit in mappings:
            raw_value = (row.get(value_field) or "").strip()
            if not raw_value:
                continue
            value = self._parse_value(raw_value, fields[value_field])
            unit = (row.get(unit_field, "").strip() if unit_field else fixed_unit) or None
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not unit:
                raise _RejectedRow("numeric_unit_missing")
            identity_hash = hashlib.sha256(f"{base_identity}\x1f{metric_key}".encode()).hexdigest()
            observations.append(
                ThemeObservation(
                    observation_id=(
                        "theme-observation-"
                        + hashlib.sha256(f"{source_hash}:{identity_hash}".encode()).hexdigest()
                    ),
                    pack_key=manifest.pack_key,
                    dataset_key=dataset.dataset_key,
                    row_identity=identity_hash,
                    subject_ref=subject_ref,
                    metric_key=metric_key,
                    value=value,
                    unit=unit,
                    as_of=observed_at,
                    observed_at=observed_at,
                    available_at=available_at,
                    source_refs=[source],
                    freshness_status=freshness,
                    quality_flags=quality_flags,
                    source_hash=source_hash,
                    payload=dict(normalized_payload),
                )
            )
        return observations

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
                mode="apply" if apply else "dry-run",
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
            return FreshnessStatus(raw)
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
            return float(text.replace(",", "").removesuffix("%"))
        if field.data_type == "integer":
            return int(text.replace(",", ""))
        if field.data_type == "boolean":
            normalized = text.lower()
            if normalized not in {"true", "false", "1", "0", "yes", "no"}:
                raise ValueError("invalid boolean")
            return normalized in {"true", "1", "yes"}
        return text

    @staticmethod
    def _normalize_payload_value(value: str, field: DatasetField) -> Any:
        """Canonicalize every declared source field before deduplication."""

        if field.data_type in {"date", "datetime"}:
            return ThemeResearchService._parse_datetime(value, field).isoformat()
        return ThemeResearchService._parse_value(value, field)

    @staticmethod
    def _same_normalized_payload(
        left: ThemeObservation,
        right: ThemeObservation,
    ) -> bool:
        """Compare semantic facts while ignoring file hash and physical row position."""

        def canonical(observation: ThemeObservation) -> dict[str, Any]:
            payload = {
                key: value
                for key, value in observation.payload.items()
                if key != "source_row_number"
            }
            sources = [
                {
                    "source_id": source.source_id,
                    "name": source.name,
                    "tier": source.tier.value,
                    "source_url": source.source_url,
                }
                for source in observation.source_refs
            ]
            semantic = {
                "subject_ref": observation.subject_ref,
                "metric_key": observation.metric_key,
                "value": observation.value,
                "unit": observation.unit,
                "as_of": observation.as_of.isoformat(),
                "observed_at": observation.observed_at.isoformat(),
                "available_at": observation.available_at.isoformat(),
                "sources": sources,
                "payload": payload,
            }
            return semantic

        return canonical(left) == canonical(right)

    @staticmethod
    def _market_home_sections(
        dataset: DatasetManifest,
    ) -> set[MarketHomeSectionKey]:
        """Map only explicitly participating theme facts to home invalidations."""

        sections: set[MarketHomeSectionKey] = set()
        if dataset.market_home_section is not None:
            sections.add(MarketHomeSectionKey(dataset.market_home_section))
        if dataset.dataset_key == "market_home_global":
            sections.add(MarketHomeSectionKey.GLOBAL_CONTEXT)
        if dataset.dataset_key == "market_home_mainline":
            sections.add(MarketHomeSectionKey.MARKET_MAINLINES)
        return sections

    @staticmethod
    def _select_latest_facts(
        observations: list[ThemeObservation],
    ) -> dict[str, ThemeObservation]:
        """Select the newest fact period, then its newest admissible publication."""

        selected: dict[str, ThemeObservation] = {}
        for observation in observations:
            key = (
                f"{observation.dataset_key}:{observation.subject_ref}:" f"{observation.metric_key}"
            )
            current = selected.get(key)
            if current is None or (
                observation.as_of,
                observation.available_at,
                observation.observation_id,
            ) > (
                current.as_of,
                current.available_at,
                current.observation_id,
            ):
                selected[key] = observation
        return selected

    @staticmethod
    def _effective_freshness(
        observation: ThemeObservation,
        dataset: DatasetManifest | None,
        point_in_time: datetime,
    ) -> FreshnessStatus:
        if observation.freshness_status is not FreshnessStatus.FRESH:
            return observation.freshness_status
        if dataset is None:
            return FreshnessStatus.UNAVAILABLE
        age = max(0.0, (point_in_time - observation.available_at).total_seconds())
        if age > dataset.freshness_seconds:
            return FreshnessStatus.STALE
        return FreshnessStatus.FRESH

    @classmethod
    def _with_effective_freshness(
        cls,
        observation: ThemeObservation,
        dataset: DatasetManifest | None,
        point_in_time: datetime,
    ) -> ThemeObservation:
        """Project SLA freshness without mutating the stored source observation."""

        effective = cls._effective_freshness(observation, dataset, point_in_time)
        if effective is observation.freshness_status:
            return observation
        flags = list(observation.quality_flags)
        if "dataset_sla_stale" not in flags:
            flags.append("dataset_sla_stale")
        return observation.model_copy(
            update={"freshness_status": effective, "quality_flags": flags}
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join(value.lower().split()) or "source"

    @staticmethod
    def _source_tier(
        source_name: str,
        declared_tiers: dict[str, SourceTier],
    ) -> SourceTier:
        normalized = source_name.casefold().strip()
        exact_tiers = {key.casefold().strip(): value for key, value in declared_tiers.items()}
        if normalized in exact_tiers:
            return exact_tiers[normalized]
        return SourceTier.PUBLIC

    @staticmethod
    def _aggregate_freshness(statuses: list[FreshnessStatus]) -> FreshnessStatus:
        unique_statuses = set(statuses)
        for status in (
            FreshnessStatus.QUARANTINED,
            FreshnessStatus.UNAVAILABLE,
            FreshnessStatus.STALE,
            FreshnessStatus.FRESH,
        ):
            if status in unique_statuses:
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
        updated = manifest.model_copy(update={"status": target})
        try:
            self.repository.update_pack_status(updated.pack_key, updated.version, updated.status)
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
