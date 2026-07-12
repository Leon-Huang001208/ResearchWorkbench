"""系统配置中心 API 契约。"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """禁止额外字段和隐式类型转换的 API 基类。"""

    model_config = ConfigDict(extra="forbid", strict=True)


class SecretState(StrictModel):
    configured: bool = Field(description="是否已经配置秘密值")
    masked_value: str | None = Field(default=None, description="秘密值的掩码")
    value: str | None = Field(
        default=None,
        description="仅供本机系统配置工作台回填密码框的已保存值",
    )


class ProviderView(StrictModel):
    original_name: str
    name: str
    protocol: Literal["openai_compatible", "anthropic", "local"]
    base_url: str
    api_key: SecretState


class TaskRouteModel(StrictModel):
    task: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    provider: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=256)


class LlmSectionView(StrictModel):
    providers: list[ProviderView]
    task_routes: list[TaskRouteModel]


class ZhiQiuAccountView(StrictModel):
    original_name: str
    name: str
    username: str
    password: SecretState


class ZhiQiuSectionView(StrictModel):
    accounts: list[ZhiQiuAccountView]
    enabled: bool
    rotation_strategy: Literal["round_robin", "random", "least_used"]
    max_retries: int
    retry_delay: int
    lease_timeout: int
    max_consecutive_failures: int


class IFindSectionView(StrictModel):
    accounts: list["IFindAccountView"]
    username: str
    password: SecretState
    backend: Literal["auto", "python_sdk", "http_api"]
    http_base_url: str


class IFindAccountView(StrictModel):
    original_name: str
    name: str
    username: str
    password: SecretState


class DatabaseSectionView(StrictModel):
    database_url: SecretState
    restart_required: bool


class AdvancedSectionView(StrictModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_dir: str
    llm_max_workers: int
    llm_max_retries: int
    chunk_size: int
    chunk_overlap: int
    long_text_threshold: int


class ConfigurationSections(StrictModel):
    llm: LlmSectionView
    zhiqiu: ZhiQiuSectionView
    ifind: IFindSectionView
    database: DatabaseSectionView
    advanced: AdvancedSectionView


class ConfigurationSnapshotResponse(StrictModel):
    sections: ConfigurationSections
    readiness: dict[str, bool]
    ready_count: int
    total_count: int


class ProviderUpdate(StrictModel):
    original_name: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    protocol: Literal["openai_compatible", "anthropic", "local"] = "openai_compatible"
    base_url: str = Field(default="", max_length=2048)
    api_key: str | None = Field(default=None, max_length=8192)
    clear_api_key: bool = False


class LlmUpdateRequest(StrictModel):
    providers: list[ProviderUpdate] | None = Field(default=None, max_length=32)
    task_routes: list[TaskRouteModel] | None = Field(default=None, max_length=128)


class ZhiQiuAccountUpdate(StrictModel):
    original_name: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=256)
    password: str | None = Field(default=None, max_length=8192)
    clear_password: bool = False


class ZhiQiuUpdateRequest(StrictModel):
    accounts: list[ZhiQiuAccountUpdate] | None = Field(default=None, max_length=100)
    enabled: bool | None = None
    rotation_strategy: Literal["round_robin", "random", "least_used"] | None = None
    max_retries: int | None = Field(default=None, ge=0, le=20)
    retry_delay: int | None = Field(default=None, ge=0, le=3600)
    lease_timeout: int | None = Field(default=None, ge=1, le=86400)
    max_consecutive_failures: int | None = Field(default=None, ge=1, le=1000)


class IFindUpdateRequest(StrictModel):
    accounts: list["IFindAccountUpdate"] | None = Field(default=None, max_length=100)
    username: str = Field(default="", max_length=256)
    password: str | None = Field(default=None, max_length=8192)
    clear_password: bool = False
    backend: Literal["auto", "python_sdk", "http_api"] | None = None
    http_base_url: str = Field(default="", max_length=2048)


class IFindAccountUpdate(StrictModel):
    original_name: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=256)
    password: str | None = Field(default=None, max_length=8192)
    clear_password: bool = False


class DatabaseUpdateRequest(StrictModel):
    database_url: str = Field(min_length=1, max_length=8192)


class AdvancedUpdateRequest(StrictModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    log_dir: str | None = Field(default=None, min_length=1, max_length=2048)
    llm_max_workers: int | None = Field(default=None, ge=1, le=128)
    llm_max_retries: int | None = Field(default=None, ge=0, le=20)
    chunk_size: int | None = Field(default=None, ge=256, le=100000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=50000)
    long_text_threshold: int | None = Field(default=None, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_chunk_boundaries(self) -> "AdvancedUpdateRequest":
        if (
            self.chunk_size is not None
            and self.chunk_overlap is not None
            and self.chunk_overlap >= self.chunk_size
        ):
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class ConfigurationUpdateResponse(StrictModel):
    section: dict[str, Any]
    applied: bool
    restart_required: bool
    message: str


class ConfigurationTestResponse(StrictModel):
    success: bool
    message: str


SectionName = Literal["llm", "zhiqiu", "ifind", "database", "advanced"]

SECTION_UPDATE_MODELS: dict[str, type[StrictModel]] = {
    "llm": LlmUpdateRequest,
    "zhiqiu": ZhiQiuUpdateRequest,
    "ifind": IFindUpdateRequest,
    "database": DatabaseUpdateRequest,
    "advanced": AdvancedUpdateRequest,
}
