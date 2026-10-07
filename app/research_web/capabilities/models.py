"""Editable package contracts; validation issues are retained with drafts."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)


class CapabilityError(StoreError):
    def __init__(self, message, code="invalid_capability", status=422):
        super().__init__(message)
        self.code, self.status = code, status


class InputField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    type: Literal["text", "file", "date", "number"] = "text"
    required: bool = True


class MethodPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[str] = Field(default_factory=list, max_length=3)
    recommended: list[str] = Field(default_factory=list, max_length=3)
    excluded: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_sets(self):
        for values in (self.required, self.recommended, self.excluded):
            if len(values) != len(set(values)) or any(
                not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) for value in values
            ):
                raise ValueError("方法策略包含空值或重复项")
        if set(self.required) & set(self.excluded):
            raise ValueError("必需方法不能同时被排除")
        return self


class DataRequirement(BaseModel):
    """Declared business scope; unknown provider semantics cannot satisfy it."""

    model_config = ConfigDict(extra="forbid", strict=True)
    capability: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    dataset: str | None = Field(
        default=None, min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$"
    )
    required: bool = True
    frequency: Literal["daily", "weekly", "monthly", "minute"] | None = None
    adjustment: Literal["none", "qfq", "hfq"] | None = None
    historical_point_in_time: bool = False
    units: dict[str, str] = Field(default_factory=dict, max_length=30)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    omit_sections: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def declared_scope(self):
        from ..datahub.contracts import DATA_CAPABILITIES

        if self.capability not in DATA_CAPABILITIES:
            raise ValueError("未知业务数据能力")
        if (
            (not self.required and not self.omit_sections)
            or any(not section.strip() or len(section) > 120 for section in self.omit_sections)
            or len(self.omit_sections) != len(set(self.omit_sections))
        ):
            raise ValueError("可选依赖必须声明明确的省略章节")
        if self.required and self.omit_sections:
            raise ValueError("硬依赖不得声明静默降级")
        if any(
            not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", field) or not unit.strip() or len(unit) > 80
            for field, unit in self.units.items()
        ):
            raise ValueError("数据单位声明无效")
        return self


def data_preflight(metadata: dict, catalog: dict) -> dict:
    """Read fresh authoritative facts without querying vendors or inferring by name."""

    def result(status, missing=None, omitted=None):
        return {
            "status": status,
            "admitted": status in {"available", "limited"},
            "missing": missing or [],
            "omitted_sections": omitted or [],
        }

    raw = metadata.get("data_requirements")
    if not raw:
        if any(
            isinstance(tool, str) and tool.startswith("datahub_")
            for tool in metadata.get("required_tools", [])
        ):
            return result("unverified", [{"code": "data_contract_missing"}])
        return result("available")
    try:
        if not isinstance(raw, list) or len(raw) > 20:
            raise ValueError("invalid requirement list")
        requirements = [DataRequirement.model_validate(item) for item in raw]
    except (ValueError, ValidationError):
        log.warning("capability_data_contract_invalid")
        return result("unverified", [{"code": "data_contract_invalid"}])
    sources = catalog.get("sources")
    bindings = catalog.get("bindings")
    if not isinstance(sources, list) or not isinstance(bindings, list):
        return result("unverified", [{"code": "data_state_unknown"}])
    by_source = {row.get("id"): row for row in sources if isinstance(row, dict)}
    missing, omitted, blocked = [], [], []
    for requirement in requirements:
        code, admitted = "data_dependency_unavailable", False
        for binding in bindings:
            if (
                not isinstance(binding, dict)
                or binding.get("capability_id") != requirement.capability
            ):
                continue
            if binding.get("implemented") is not True:
                continue
            if requirement.dataset and requirement.dataset not in binding.get("datasets", []):
                continue
            source = by_source.get(binding.get("source_id"), {})
            readiness = source.get("readiness", {})
            keys = (
                "integration_completed",
                "configured",
                "dependency_ready",
                "allowed",
                "callable",
            )
            if any(type(readiness.get(key)) is not bool for key in keys):
                code = "data_state_unknown"
                continue
            if not all(readiness[key] for key in keys):
                continue
            semantics_by_dataset = binding.get("semantics", {})
            semantics = (
                semantics_by_dataset.get(requirement.dataset, {})
                if isinstance(semantics_by_dataset, dict)
                else {}
            )
            if not isinstance(semantics, dict):
                semantics = {}
            checks: list[tuple[str, str]] = []
            if requirement.frequency:
                checks.append(("frequencies", requirement.frequency))
            if requirement.adjustment:
                checks.append(("adjustments", requirement.adjustment))
            mismatch, unknown = False, False
            for key, expected in checks:
                values = semantics.get(key)
                if not isinstance(values, list):
                    unknown = True
                elif expected not in values:
                    mismatch = True
            if requirement.historical_point_in_time:
                actual = semantics.get("historical_point_in_time")
                unknown = unknown or type(actual) is not bool
                mismatch = mismatch or actual is False
            for field, expected in requirement.units.items():
                actual_units = semantics.get("units")
                actual = actual_units.get(field) if isinstance(actual_units, dict) else None
                unknown = unknown or actual is None
                mismatch = mismatch or (actual is not None and actual != expected)
            if requirement.currency:
                actual = semantics.get("currency")
                unknown = unknown or actual is None
                mismatch = mismatch or (actual is not None and actual != requirement.currency)
            if mismatch:
                code = "data_semantics_not_equivalent"
                continue
            if unknown:
                code = "data_semantics_unverified"
                continue
            if readiness.get("health") != "healthy":
                code = "data_probe_required"
                continue
            admitted = True
            break
        if not admitted:
            missing.append(
                {
                    "capability": requirement.capability,
                    "dataset": requirement.dataset,
                    "required": requirement.required,
                    "code": code,
                }
            )
            if requirement.required:
                blocked.append(code)
            else:
                omitted.extend(requirement.omit_sections)
    if blocked:
        unknown_codes = {"data_state_unknown", "data_semantics_unverified", "data_probe_required"}
        return result(
            "unverified" if all(code in unknown_codes for code in blocked) else "unavailable",
            missing,
            omitted,
        )
    return result("limited" if missing else "available", missing, list(dict.fromkeys(omitted)))


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=80)
    inputs: list[InputField] = Field(min_length=1, max_length=30)
    scenarios: list[str] = Field(min_length=1, max_length=30)
    default_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png"]]
    required_tools: list[str] = Field(default_factory=list, max_length=20)
    dependencies: list[str] = Field(default_factory=list, max_length=40)
    method_policy: MethodPolicy = Field(default_factory=MethodPolicy)
    data_requirements: list[DataRequirement] = Field(default_factory=list, max_length=20)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=10000)
    skill_id: str | None = None
    tools: list[str] = Field(default_factory=list, max_length=20)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["skill", "workflow"] = "skill"
    metadata: dict = Field(default_factory=dict)
    instructions: str = Field(default="", max_length=1000000)
    files: list[dict] = Field(default_factory=list, max_length=128)
    steps: list[dict] = Field(default_factory=list, max_length=40)
    reviewed_scripts: list[str] = Field(default_factory=list, max_length=128)


class CopyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)


class VersionInput(BaseModel):
    version: int = Field(ge=1, strict=True)


class CreationInput(BaseModel):
    kind: Literal["skill", "workflow"] = "skill"
    goal: str = Field(min_length=1, max_length=10000)


class ArtifactInput(BaseModel):
    session_id: str
    file_id: str


def issue(code, message, path=None):
    return {"code": code, "message": message, "path": path}
