"""Declarative Research Pack and theme-observation contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from core.contracts.platform_shared import (
    AssetRef,
    FactResponseBase,
    ObservationEnvelope,
    SourceTier,
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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    data_type: Literal["string", "number", "integer", "boolean", "date", "datetime"]
    required: bool = True


class ObservationFieldMapping(BaseModel):
    """One fact emitted from a long or wide source row."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value_field: str = Field(min_length=1)
    metric_key: str | None = Field(default=None, min_length=1)
    metric_suffix: str | None = Field(default=None, min_length=1)
    unit_field: str | None = Field(default=None, min_length=1)
    fixed_unit: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_mapping(self) -> ObservationFieldMapping:
        if (self.metric_key is None) == (self.metric_suffix is None):
            raise ValueError("mapping requires exactly one of metric_key or metric_suffix")
        if self.unit_field is None and self.fixed_unit is None:
            raise ValueError("mapping requires unit_field or fixed_unit")
        if self.unit_field is not None and self.fixed_unit is not None:
            raise ValueError("mapping cannot declare both unit_field and fixed_unit")
        return self


class DatasetManifest(BaseModel):
    """One source dataset declared by a theme pack."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_key: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    source_priority: list[str] = Field(min_length=1)
    freshness_seconds: int = Field(gt=0)
    required: bool = True
    fields: list[DatasetField] = Field(default_factory=list, min_length=1)
    identity_fields: list[str] = Field(default_factory=list, min_length=1)
    dimension_fields: list[str] = Field(default_factory=list)
    source_row_discriminator: Literal["row_number"] | None = None
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
    verification_field: str | None = None
    source_tiers: dict[str, SourceTier] = Field(default_factory=dict)
    observation_fields: list[ObservationFieldMapping] = Field(default_factory=list)
    emitted_metric_keys: list[str] = Field(default_factory=list)
    market_home_section: Literal["global_context", "market_mainlines"] | None = None

    @model_validator(mode="after")
    def validate_field_mapping(self) -> DatasetManifest:
        """Keep ingestion mappings inside the explicitly declared schema."""

        field_names = {field.name for field in self.fields}
        required_field_names = {field.name for field in self.fields if field.required}
        if len(field_names) != len(self.fields):
            raise ValueError("dataset field names must be unique")
        if len(set(self.identity_fields)) != len(self.identity_fields):
            raise ValueError("dataset identity_fields must be unique")
        if len(set(self.dimension_fields)) != len(self.dimension_fields):
            raise ValueError("dataset dimension_fields must be unique")
        if self.source_row_discriminator is not None and not self.dimension_fields:
            raise ValueError("source row discriminator requires explicit dimension_fields")
        if len(set(self.source_priority)) != len(self.source_priority):
            raise ValueError("dataset source_priority must be unique")
        if any(not source for source in self.source_priority):
            raise ValueError("dataset source_priority must be non-empty")
        tier_names = [name.casefold().strip() for name in self.source_tiers]
        if any(not name for name in tier_names) or len(set(tier_names)) != len(tier_names):
            raise ValueError("dataset source tier names must be non-empty and unique")
        mapped = {
            *self.identity_fields,
            *self.dimension_fields,
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
                self.verification_field,
            )
            if field is not None
        )
        for mapping in self.observation_fields:
            mapped.add(mapping.value_field)
            if mapping.unit_field is not None:
                mapped.add(mapping.unit_field)
        missing = mapped - field_names
        if missing:
            raise ValueError(f"dataset mappings reference undeclared fields: {sorted(missing)}")
        structural_fields = {
            *self.identity_fields,
            *self.dimension_fields,
            self.observed_at_field,
            self.subject_field,
            self.metric_field,
        }
        if self.available_at_field is not None:
            structural_fields.add(self.available_at_field)
        optional_structural = structural_fields - required_field_names
        if optional_structural:
            raise ValueError(
                "identity, dimension, and structural fields must be required: "
                f"{sorted(optional_structural)}"
            )
        if self.unit_field is None and self.fixed_unit is None:
            raise ValueError("dataset requires unit_field or fixed_unit")
        if self.unit_field is not None and self.fixed_unit is not None:
            raise ValueError("dataset cannot declare both unit_field and fixed_unit")
        mapping_keys = [
            mapping.metric_key or f"suffix:{mapping.metric_suffix}"
            for mapping in self.observation_fields
        ]
        if len(set(mapping_keys)) != len(mapping_keys):
            raise ValueError("observation field mappings must be unique")
        if any(not key.strip() for key in self.emitted_metric_keys) or len(
            set(self.emitted_metric_keys)
        ) != len(self.emitted_metric_keys):
            raise ValueError("emitted metric keys must be non-empty and unique")
        return self


class KPIDefinition(BaseModel):
    """Unit-bearing KPI definition used by typed pack projections."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kpi_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    dataset_key: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)


class ValueChainNode(BaseModel):
    """Declared node in a pack's evidence-backed value chain."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    node_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class ThemeAssetExposure(BaseModel):
    """Evidence-backed relationship between a theme and an existing asset."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset: AssetRef
    exposure_type: str = Field(min_length=1)
    rationale_ref: str = Field(min_length=1)


class PluginBinding(BaseModel):
    """Reference to a trusted, versioned in-process transform."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    plugin_id: str = Field(pattern=r"^builtin\.[a-z0-9_.-]+\.v[0-9]+$")
    operation: PluginPermission


class ThemePackManifest(BaseModel):
    """Versioned and permission-bounded declaration of a Research Pack."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pack_key: str = Field(min_length=1)
    kind: Literal["theme_research"] = "theme_research"
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    compatibility_version: str = Field(min_length=1)
    status: PackLifecycle
    boundary: str = Field(min_length=1)
    datasets: list[DatasetManifest] = Field(min_length=1)
    kpis: list[KPIDefinition] = Field(min_length=1)
    value_chain: list[ValueChainNode] = Field(min_length=1)
    event_types: list[str] = Field(min_length=1)
    asset_exposures: list[ThemeAssetExposure] = Field(min_length=1)
    research_template_keys: list[str] = Field(min_length=1)
    plugins: list[PluginBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kpi_datasets(self) -> ThemePackManifest:
        """Reject KPIs that point at datasets absent from the manifest."""

        dataset_key_list = [dataset.dataset_key for dataset in self.datasets]
        dataset_keys = set(dataset_key_list)
        if len(dataset_keys) != len(dataset_key_list):
            raise ValueError("dataset keys must be unique")
        kpi_keys = [kpi.kpi_key for kpi in self.kpis]
        if len(set(kpi_keys)) != len(kpi_keys):
            raise ValueError("KPI keys must be unique")
        node_keys = [node.node_key for node in self.value_chain]
        if len(set(node_keys)) != len(node_keys):
            raise ValueError("value-chain node keys must be unique")
        for name, values in (
            ("event types", self.event_types),
            ("research templates", self.research_template_keys),
        ):
            if any(not value.strip() for value in values) or len(set(values)) != len(values):
                raise ValueError(f"{name} must be non-empty and unique")
        asset_ids = [item.asset.asset_id for item in self.asset_exposures]
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("asset exposures must be unique")
        plugin_ids = [binding.plugin_id for binding in self.plugins]
        if len(set(plugin_ids)) != len(plugin_ids):
            raise ValueError("plugin IDs must be unique")
        missing = {kpi.dataset_key for kpi in self.kpis} - dataset_keys
        if missing:
            raise ValueError(f"KPI references unknown datasets: {sorted(missing)}")
        datasets = {dataset.dataset_key: dataset for dataset in self.datasets}
        impossible_metrics = {
            f"{kpi.dataset_key}:{kpi.metric_key}"
            for kpi in self.kpis
            if kpi.metric_key
            not in {
                *datasets[kpi.dataset_key].emitted_metric_keys,
                *(
                    mapping.metric_key
                    for mapping in datasets[kpi.dataset_key].observation_fields
                    if mapping.metric_key is not None
                ),
            }
        }
        if impossible_metrics:
            raise ValueError(
                f"KPI metrics are not emitted by their datasets: {sorted(impossible_metrics)}"
            )
        evidence_datasets = {
            reference.removeprefix("dataset:")
            for node in self.value_chain
            for reference in node.evidence_refs
            if reference.startswith("dataset:")
        }
        invalid_evidence = evidence_datasets - dataset_keys
        if invalid_evidence:
            raise ValueError(f"value-chain references unknown datasets: {sorted(invalid_evidence)}")
        if any(
            not reference.startswith("dataset:")
            for node in self.value_chain
            for reference in node.evidence_refs
        ):
            raise ValueError("value-chain evidence references must use dataset:<key>")
        rationale_prefix = f"manifest:{self.pack_key}:"
        rationale_entities = {
            *dataset_keys,
            *kpi_keys,
            *node_keys,
            *self.event_types,
            *self.research_template_keys,
        }
        for exposure in self.asset_exposures:
            if not exposure.rationale_ref.startswith(rationale_prefix):
                raise ValueError("asset rationale_ref must reference this manifest")
            entity = exposure.rationale_ref.removeprefix(rationale_prefix)
            if entity not in rationale_entities:
                raise ValueError("asset rationale_ref must reference a declared entity")
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
    mode: Literal["dry-run", "apply"]


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
    model_config = ConfigDict(extra="forbid")
