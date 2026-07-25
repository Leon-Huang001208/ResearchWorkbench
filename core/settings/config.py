import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.settings.runtime import initialize_runtime_environment, resolve_runtime_context

RUNTIME_CONTEXT = initialize_runtime_environment()
DEFAULT_LOG_DIR = (RUNTIME_CONTEXT.data_dir or RUNTIME_CONTEXT.project_root) / "logs"
DEFAULT_OBJECT_STORAGE_PATH = (
    RUNTIME_CONTEXT.data_dir or RUNTIME_CONTEXT.project_root / "data"
) / "objects"
DEFAULT_PDF_MARKDOWN_DIR = (
    RUNTIME_CONTEXT.data_dir or RUNTIME_CONTEXT.project_root / "data"
) / "markdown"
DEFAULT_PDF_RAW_TEXT_DIR = (
    RUNTIME_CONTEXT.data_dir or RUNTIME_CONTEXT.project_root / "data"
) / "raw_text"


class ProviderProfile(BaseModel):
    """单个 LLM provider 配置"""

    name: str
    protocol: Literal["openai_compatible", "anthropic", "local"] = "openai_compatible"
    base_url: str = ""
    api_key: str = ""


class TaskRoute(BaseModel):
    """任务 → provider + model 路由"""

    provider: str
    model: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # 项目根目录
    PROJECT_ROOT: Path = RUNTIME_CONTEXT.project_root

    # Runtime environment: dev/prod
    APP_ENV: Literal["dev", "prod"] = "dev"

    # API 基础地址。桌面端由 RuntimeContext 在导入应用前设为 8765。
    BACKEND_URL: str = RUNTIME_CONTEXT.backend_url

    # 未配置时使用不可用占位符，避免意外连接到已知的默认数据库账户。
    DATABASE_URL: str = "postgresql+psycopg://invalid:invalid@127.0.0.1:1/alphafoundry"

    # ── 多 provider profiles + 任务路由 ──
    PROVIDER_PROFILES: dict[str, ProviderProfile] = Field(default_factory=dict)
    TASK_ROUTES: dict[str, TaskRoute] = Field(default_factory=dict)

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_DIR: Path = Field(default_factory=lambda: DEFAULT_LOG_DIR)

    # iFinD 数据源
    IFIND_USERNAME: str = ""
    IFIND_PASSWORD: str = ""
    IFIND_BACKEND: Literal["auto", "python_sdk", "http_api"] = "auto"
    IFIND_HTTP_BASE_URL: str = "https://quantapi.10jqka.com.cn"

    # China Stock
    CHINA_STOCK_ENABLED: bool = True

    # 爬虫夜间静默窗口（本地时间，整点小时）
    # 在 [CRAWLER_QUIET_START, CRAWLER_QUIET_END) 时间段内，定时爬取任务全部跳过。
    # 手动触发（API trigger_crawl）不受此限制。
    # 设为相同值（如均为 0）表示禁用静默功能，全天爬取。
    CRAWLER_QUIET_START: int = 20  # 默认 20:00 开始静默
    CRAWLER_QUIET_END: int = 8  # 默认 08:00 结束静默（不含）

    # 对象存储
    OBJECT_STORAGE_PATH: Path = Field(default_factory=lambda: DEFAULT_OBJECT_STORAGE_PATH)

    # Knowledge Worker 配置
    KNOWLEDGE_WORKER_POLL_INTERVAL: float = 3.0
    KNOWLEDGE_WORKER_BATCH_SIZE: int = 10
    KNOWLEDGE_WORKER_MAX_CONCURRENCY: int = 8
    KNOWLEDGE_WORKER_SHUTDOWN_TIMEOUT: int = 30
    KNOWLEDGE_WORKER_MAX_BACKOFF: float = 60.0

    # LLM 并发提取配置
    LLM_EXTRACT_MAX_WORKERS: int = 8
    LLM_EXTRACT_CHUNK_SIZE: int = 3500
    LLM_EXTRACT_CHUNK_OVERLAP: int = 300
    LLM_EXTRACT_MAX_RETRIES: int = 2
    LLM_EXTRACT_LONG_TEXT_THRESHOLD: int = 1000

    # PDF 转换输出目录
    PDF_MARKDOWN_DIR: Path = Field(default_factory=lambda: DEFAULT_PDF_MARKDOWN_DIR)
    PDF_RAW_TEXT_DIR: Path = Field(default_factory=lambda: DEFAULT_PDF_RAW_TEXT_DIR)
    PDF_INLINE_THRESHOLD_BYTES: int = 256 * 1024  # 256 KB
    # PDF 转换策略：auto(三级降级) / mineru / markitdown / raw_text
    PDF_PREFERRED_STRATEGY: str = "auto"
    # 低于此质量分的成功结果会触发降级到下一策略（0.0=禁用阈值过滤）
    PDF_QUALITY_MIN_SCORE: float = 0.0
    # MinerU：是否允许在线下载 HuggingFace 模型（opendatalab/PDF-Extract-Kit-1.0）
    MINERU_ALLOW_MODEL_DOWNLOAD: str = "0"

    # ── 联网搜索（提问优先联网查询）──
    # 搜索后端：tavily / bing，可切换
    WEB_SEARCH_PROVIDER: str = "tavily"
    TAVILY_API_KEY: str = ""
    BING_API_KEY: str = ""
    # API key 池（JSON 数组，优先级高于单 key）：[{"name": "a", "key": "tvly-..."}, ...]
    # 池为空时自动回退到单 key 模式
    WEB_SEARCH_API_KEYS: str = ""
    # key 池策略：round_robin | random | least_used
    WEB_SEARCH_KEY_ROTATION: str = "round_robin"
    # 连续失败 N 次后永久禁用该 key（冷却期满自动解禁）
    WEB_SEARCH_KEY_MAX_FAILURES: int = 5
    # 临时锁定秒数（单次失败后）
    WEB_SEARCH_KEY_LOCK_SECONDS: int = 60
    # 永久禁用冷却期秒数（0=不自动解禁）
    WEB_SEARCH_KEY_COOLDOWN_SECONDS: float = 3600.0
    # 每个 key 的月度积分上限（达到后自动停用，下月 1 号刷新）
    WEB_SEARCH_KEY_QUOTA_LIMIT: int = 1000
    WEB_SEARCH_MAX_RESULTS: int = 5
    # 是否对搜索结果补抓网页正文（False 时只用 API 返回的摘要）
    WEB_SEARCH_FETCH_CONTENT: bool = True
    # 单条正文截断字符数上限
    WEB_SEARCH_MAX_CHARS: int = 2000
    # 请求超时（秒）
    WEB_SEARCH_TIMEOUT: int = 15

    @model_validator(mode="before")
    @classmethod
    def _build_provider_configs(cls, data: Any) -> Any:
        """从环境变量解析 provider profiles 和 task routes"""
        if not isinstance(data, dict):
            return data

        data["PROVIDER_PROFILES"] = cls._parse_provider_profiles_from_env()
        data["TASK_ROUTES"] = cls._parse_task_routes_from_env()
        return data

    @staticmethod
    def _parse_provider_profiles_from_env() -> dict[str, ProviderProfile]:
        """从 LLM_PROVIDER_N_* 环境变量解析 provider profiles"""
        groups: dict[int, dict[str, str]] = {}
        pattern = re.compile(r"^LLM_PROVIDER_(\d+)_(\w+)$")

        for key, value in os.environ.items():
            match = pattern.match(key)
            if not match:
                continue
            index = int(match.group(1))
            field = match.group(2).lower()
            if index not in groups:
                groups[index] = {}
            groups[index][field] = value

        profiles: dict[str, ProviderProfile] = {}
        for index in sorted(groups.keys()):
            group = groups[index]
            name = group.get("name", f"provider_{index}")
            profiles[name] = ProviderProfile(
                name=name,
                protocol=group.get("protocol", "openai_compatible"),  # type: ignore[arg-type]
                base_url=group.get("base_url", ""),
                api_key=group.get("api_key", ""),
            )
        return profiles

    @staticmethod
    def _parse_task_routes_from_env() -> dict[str, TaskRoute]:
        """从 TASK_*_PROVIDER / TASK_*_MODEL 环境变量解析任务路由"""
        provider_pattern = re.compile(r"^TASK_(\w+)_PROVIDER$")
        task_providers: dict[str, str] = {}
        task_models: dict[str, str] = {}

        for key, value in os.environ.items():
            pm = provider_pattern.match(key)
            if pm:
                task_providers[pm.group(1).lower()] = value
            elif key.startswith("TASK_") and key.endswith("_MODEL"):
                task_name = key[5:-6].lower()
                task_models[task_name] = value

        all_tasks = set(task_providers.keys()) | set(task_models.keys())
        routes: dict[str, TaskRoute] = {}
        for task in all_tasks:
            routes[task] = TaskRoute(
                provider=task_providers.get(task, "volcano"),
                model=task_models.get(task, ""),
            )
        return routes

    def ensure_dirs(self) -> None:
        """确保必要的目录存在"""
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.OBJECT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        self.PDF_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
        self.PDF_RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_runtime_env_path(
    *,
    environ: dict[str, str] | None = None,
    project_root: Path | None = None,
) -> Path:
    """返回由 RuntimeContext 统一解析的配置文件路径。

    Web 生产模式默认不读取配置文件，因此调用方需要通过环境变量注入配置。
    """
    context = resolve_runtime_context(environ=environ, project_root=project_root)
    if context.env_path is None:
        raise RuntimeError("web-prod 模式未配置运行时 .env 文件")
    return context.env_path


settings = Settings()
settings.ensure_dirs()
