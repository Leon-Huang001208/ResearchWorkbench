"""Declarative Research Pack and theme-observation contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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


class DatasetManifest(BaseModel):
    """One source dataset declared by a theme pack."""

    dataset_key: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    source_priority: list[str] = Field(default_factory=list)
    freshness_seconds: int = Field(gt=0)
    required: bool = True


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


class ThemeAssetExposure(BaseModel):
    """Evidence-backed relationship between a theme and an existing asset."""

    asset: AssetRef
    exposure_type: str = Field(min_length=1)
    rationale_ref: str = Field(min_length=1)


class ThemePackManifest(BaseModel):
    """Versioned and permission-bounded declaration of a Research Pack."""

    pack_key: str = Field(min_length=1)
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
