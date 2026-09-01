"""Declarative Research Pack and theme-observation contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from core.contracts.platform_shared import (
    AssetRef,
    FactResponseBase,
    ObservationEnvelope,
)


class PackLifecycle(str, Enum):
    """Validated lifecycle of a Research Pack."""

    DISCOVERED = "discovered"
    VALIDATED = "validated"
    ENABLED = "enabled"
    DEGRADED = "degraded"
    DISABLED = "disabled"


PluginPermission = Literal["normalize", "validate", "derive"]


class DatasetField(BaseModel):
    """One typed CSV/connector field declared by a dataset."""

    name: str = Field(min_length=1)
    data_type: Literal["string", "number", "integer", "boolean", "date", "datetime"]
    required: bool = True


class DatasetManifest(BaseModel):
    """One source dataset declared by a theme pack."""

    dataset_key: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    source_priority: list[str] = Field(default_factory=list)
    freshness_seconds: int = Field(gt=0)
    required: bool = True
    fields: list[DatasetField] = Field(default_factory=list, min_length=1)
    identity_fields: list[str] = Field(default_factory=list, min_length=1)
    observed_at_field: str = Field(min_length=1)
    available_at_field: str | None = None
    subject_field: str = Field(min_length=1)
    metric_field: str = Field(min_length=1)
    value_field: str = Field(min_length=1)
    unit_field: str | None = None
    fixed_unit: str | None = None
    source_name_field: str | None = None
    source_url_field: str | None = None
    freshness_field: str | None = None

    @model_validator(mode="after")
    def validate_field_mapping(self) -> DatasetManifest:
        """Keep ingestion mappings inside the explicitly declared schema."""

        field_names = {field.name for field in self.fields}
        mapped = {
            *self.identity_fields,
            self.observed_at_field,
            self.subject_field,
            self.metric_field,
            self.value_field,
        }
        mapped.update(
            field
            for field in (
                self.available_at_field,
                self.unit_field,
                self.source_name_field,
                self.source_url_field,
                self.freshness_field,
            )
            if field is not None
        )
        missing = mapped - field_names
        if missing:
            raise ValueError(f"dataset mappings reference undeclared fields: {sorted(missing)}")
        if self.unit_field is None and self.fixed_unit is None:
            raise ValueError("dataset requires unit_field or fixed_unit")
        return self


class KPIDefinition(BaseModel):
    """Unit-bearing KPI definition used by typed pack projections."""

    kpi_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    dataset_key: str = Field(min_length=1)


class ValueChainNode(BaseModel):
    """Declared node in a pack's evidence-backed value chain."""

    node_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class ThemeAssetExposure(BaseModel):
    """Evidence-backed relationship between a theme and an existing asset."""

    asset: AssetRef
    exposure_type: str = Field(min_length=1)
    rationale_ref: str = Field(min_length=1)


class ThemePackManifest(BaseModel):
    """Versioned and permission-bounded declaration of a Research Pack."""

    pack_key: str = Field(min_length=1)
    kind: Literal["theme_research"] = "theme_research"
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    compatibility_version: str = Field(min_length=1)
    status: PackLifecycle
    boundary: str = Field(min_length=1)
    datasets: list[DatasetManifest] = Field(default_factory=list)
    kpis: list[KPIDefinition] = Field(default_factory=list)
    value_chain: list[ValueChainNode] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    asset_exposures: list[ThemeAssetExposure] = Field(default_factory=list)
    research_template_keys: list[str] = Field(default_factory=list)
    plugin_permissions: list[PluginPermission] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kpi_datasets(self) -> ThemePackManifest:
        """Reject KPIs that point at datasets absent from the manifest."""

        dataset_keys = {dataset.dataset_key for dataset in self.datasets}
        missing = {kpi.dataset_key for kpi in self.kpis} - dataset_keys
        if missing:
            raise ValueError(f"KPI references unknown datasets: {sorted(missing)}")
        return self


class ThemeObservation(ObservationEnvelope):
    """Only persisted fact shape shared by every theme pack."""

    pack_key: str = Field(min_length=1)
    dataset_key: str = Field(min_length=1)
    row_identity: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)


class ThemeSnapshot(FactResponseBase):
    """Typed, read-only projection of a theme at one point in time."""

    pack_key: str = Field(min_length=1)
    facts: dict[str, Any] = Field(default_factory=dict)
    coverage: float = Field(ge=0.0, le=1.0)


class PackHealth(BaseModel):
    """Coverage and import outcomes for a theme pack."""

    pack_key: str = Field(min_length=1)
    dataset_coverage: dict[str, float] = Field(default_factory=dict)
    accepted: int = Field(ge=0, default=0)
    quarantined: int = Field(ge=0, default=0)
    rejected: int = Field(ge=0, default=0)
    duplicate: int = Field(ge=0, default=0)
    dataset_age_seconds: dict[str, float | None] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)


class ThemeKPIValue(BaseModel):
    """One unit-bearing KPI point backed by a persisted observation."""

    kpi_key: str
    name: str
    unit: str
    frequency: str
    observation: ThemeObservation


class ThemeKPIProjection(BaseModel):
    """Typed KPI series read model."""

    pack_key: str
    series: list[ThemeKPIValue]
    as_of: AwareDatetime


class ThemeValueChainProjection(BaseModel):
    """Manifest-declared value-chain nodes with evidence references."""

    pack_key: str
    nodes: list[ValueChainNode]
    as_of: AwareDatetime


class ThemeEventProjection(BaseModel):
    """Verified events and unverified leads remain visibly separated."""

    pack_key: str
    verified: list[ThemeObservation]
    leads: list[ThemeObservation]
    as_of: AwareDatetime


class ThemeAssetProjection(BaseModel):
    """Asset exposure projection that never copies asset facts."""

    pack_key: str
    assets: list[ThemeAssetExposure]
    as_of: AwareDatetime


class WorkspacePrefillRequest(BaseModel):
    """Safe hand-off to the research module; it does not write theme facts."""

    pack_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    template_key: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class IngestionCheckpoint(BaseModel):
    """Restart token for a deterministic source file scan."""

    source_hash: str = Field(min_length=1)
    last_row_number: int = Field(ge=1)


class IngestionRowResult(BaseModel):
    """Safe row-level outcome without embedding unvalidated source content."""

    row_number: int = Field(ge=2)
    row_identity_hash: str = Field(min_length=1)
    outcome: Literal["accepted", "quarantined", "rejected", "duplicate"]
    error_code: str | None = None


class ThemeIngestionReport(BaseModel):
    """Dry-run/apply report for one immutable source file."""

    pack_key: str
    dataset_key: str
    source_hash: str
    dry_run: bool
    accepted: int = Field(ge=0)
    quarantined: int = Field(ge=0)
    rejected: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    applied: int = Field(ge=0)
    rows: list[IngestionRowResult]
    checkpoint: IngestionCheckpoint
