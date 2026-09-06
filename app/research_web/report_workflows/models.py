"""Strict domain contracts for versioned Report Workflow packages."""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..store import StoreError


class WorkflowError(StoreError):
    """Safe product error raised by the Report Workflow boundary."""

    def __init__(
        self, message: str, code: str = "invalid_report_workflow", status: int = 422
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class StrictModel(BaseModel):
    # API payloads use JSON strings for enums, while the Enum declarations keep
    # each value closed and reject unknown states.
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class WorkflowResourceRole(str, Enum):
    WORKFLOW = "workflow"
    TEMPLATE = "template"
    WORKBOOK = "workbook"
    ASSET = "asset"
    MAPPING = "mapping"
    VALIDATION = "validation"
    REFRESH_MANIFEST = "refresh_manifest"


class WorkbookFormulaProvider(str, Enum):
    NONE = "none"
    WIND = "wind_excel"
    IFIND = "ifind_excel"
    MIXED = "mixed"


class WorkbookProvider(str, Enum):
    WIND = "wind_excel"
    IFIND = "ifind_excel"


class ReportBlockKind(str, Enum):
    NARRATIVE = "narrative"
    TABLE = "table"
    CHART = "chart"
    WORKBOOK = "workbook"
    APPENDIX = "appendix"


class DeliveryFormat(str, Enum):
    MD = "md"
    HTML = "html"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PNG = "png"
    PDF = "pdf"


class ScheduleKind(str, Enum):
    MANUAL = "manual"
    ONCE = "once"
    WEEKLY = "weekly"


class RefreshStatus(str, Enum):
    READY = "ready"
    BLOCKED_DATA = "blocked_data"


class WorkflowResource(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    role: WorkflowResourceRole
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0, le=128 * 1024 * 1024)


class WorkbookProviderRequirement(StrictModel):
    provider: WorkbookProvider
    required: bool = True
    equivalent_datahub_mapping: str | None = Field(default=None, max_length=240)

    @field_validator("equivalent_datahub_mapping")
    @classmethod
    def mapping_must_be_a_package_resource(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.startswith("mappings/") or not value.endswith((".yaml", ".yml", ".json"))
        ):
            raise ValueError("等价 DataHub mapping 必须位于 mappings/ 下")
        return value


class WorkbookRefreshPolicy(StrictModel):
    workbook: str = Field(min_length=1, max_length=240)
    providers: list[WorkbookProviderRequirement] = Field(default_factory=list, max_length=2)
    required_cells: list[str] = Field(default_factory=list, max_length=256)
    required_date_cell: str | None = Field(default=None, max_length=160)
    required_date: date | None = None
    max_age_days: int | None = Field(default=None, ge=0, le=3660)
    reject_zero_cells: list[str] = Field(default_factory=list, max_length=256)
    stability_checks: int = Field(default=2, ge=1, le=20)
    poll_interval_seconds: float = Field(default=0.25, ge=0, le=30)
    timeout_seconds: float = Field(default=30, gt=0, le=900)

    @field_validator("workbook")
    @classmethod
    def workbook_is_scoped(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value.startswith("workbooks/")
            or not value.lower().endswith(".xlsx")
            or path.is_absolute()
            or "\\" in value
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("工作簿必须是 workbooks/ 下的 xlsx 文件")
        return value

    @field_validator("required_cells", "reject_zero_cells")
    @classmethod
    def cells_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any("!" not in item for item in value):
            raise ValueError("单元格引用必须唯一且包含工作表名称")
        return value

    @model_validator(mode="after")
    def date_fields_are_paired(self) -> WorkbookRefreshPolicy:
        has_date_rule = self.required_date is not None or self.max_age_days is not None
        if (self.required_date_cell is None) != (not has_date_rule):
            raise ValueError("日期规则必须声明 required_date_cell 与日期下限或最大陈旧天数")
        providers = [item.provider for item in self.providers]
        if len(providers) != len(set(providers)):
            raise ValueError("Provider 不能重复声明")
        return self


class ReportBlock(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    kind: ReportBlockKind
    required: bool = True
    source_refs: list[str] = Field(default_factory=list, max_length=64)


class DeliveryContract(StrictModel):
    formats: list[DeliveryFormat] = Field(min_length=1, max_length=7)
    required_artifacts: list[str] = Field(default_factory=list, max_length=32)
    block_on_data_failure: bool = True

    @field_validator("formats")
    @classmethod
    def formats_are_unique(cls, value: list[DeliveryFormat]) -> list[DeliveryFormat]:
        if len(value) != len(set(value)):
            raise ValueError("交付格式不能重复")
        return value


class WorkflowSchedule(StrictModel):
    kind: ScheduleKind = ScheduleKind.MANUAL
    enabled: bool = False
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    once_at: str | None = Field(default=None, max_length=64)
    weekday: int | None = Field(default=None, ge=0, le=6)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)

    @model_validator(mode="after")
    def validate_shape(self) -> WorkflowSchedule:
        if self.kind is ScheduleKind.MANUAL and self.enabled:
            raise ValueError("手动 Workflow 不能启用自动调度")
        if self.kind is ScheduleKind.ONCE and self.enabled and not self.once_at:
            raise ValueError("一次性调度必须声明 once_at")
        if (
            self.kind is ScheduleKind.WEEKLY
            and self.enabled
            and any(value is None for value in (self.weekday, self.hour, self.minute))
        ):
            raise ValueError("每周调度必须声明 weekday/hour/minute")
        return self


class ReportWorkflowManifest(StrictModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    workflow_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    version: int = Field(ge=1)
    providers: list[WorkbookProviderRequirement] = Field(default_factory=list, max_length=2)
    resources: list[WorkflowResource] = Field(default_factory=list, max_length=512)
    workbook_policies: list[WorkbookRefreshPolicy] = Field(default_factory=list, max_length=64)
    blocks: list[ReportBlock] = Field(default_factory=list, max_length=128)
    delivery: DeliveryContract
    schedule: WorkflowSchedule = Field(default_factory=WorkflowSchedule)

    @model_validator(mode="after")
    def validate_unique_contracts(self) -> ReportWorkflowManifest:
        provider_ids = [item.provider for item in self.providers]
        resource_paths = [item.path for item in self.resources]
        workbook_paths = [item.workbook for item in self.workbook_policies]
        block_ids = [item.id for item in self.blocks]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("Provider 不能重复声明")
        if len(resource_paths) != len(set(resource_paths)):
            raise ValueError("资源路径不能重复")
        if len(workbook_paths) != len(set(workbook_paths)):
            raise ValueError("工作簿策略不能重复")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("报告区块标识不能重复")
        return self


class WorkbookRefreshResult(StrictModel):
    status: RefreshStatus
    code: str | None = Field(default=None, max_length=80)
    provider: str | None = Field(default=None, max_length=40)
    resource: WorkflowResource | None = None
    manifest_path: str | None = None
    issues: list[dict[str, str]] = Field(default_factory=list, max_length=256)
