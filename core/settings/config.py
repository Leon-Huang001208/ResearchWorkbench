import os
import re
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


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
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 项目根目录
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

    # Runtime environment: dev/prod
    APP_ENV: Literal["dev", "prod"] = "dev"

    # 数据库（postgresql+psycopg:// 显式指定 psycopg v3 驱动，避免 SQLAlchemy 回退到 psycopg2）
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/alphafoundry"

    # ── 多 provider profiles + 任务路由 ──
    PROVIDER_PROFILES: dict[str, ProviderProfile] = Field(default_factory=dict)
    TASK_ROUTES: dict[str, TaskRoute] = Field(default_factory=dict)

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_DIR: Path = PROJECT_ROOT / "logs"

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
    OBJECT_STORAGE_PATH: Path = PROJECT_ROOT / "data" / "objects"

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
    PDF_MARKDOWN_DIR: Path = PROJECT_ROOT / "data" / "markdown"
    PDF_RAW_TEXT_DIR: Path = PROJECT_ROOT / "data" / "raw_text"
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


def resolve_runtime_env_path() -> Path:
    """返回当前运行时应使用的 .env 文件路径。

    优先级：
    1. ALPHAFOUNDRY_DESKTOP_DATA_DIR 环境变量（桌面版 data_dir）
    2. 桌面版默认 data_dir（APPDATA/AlphaFoundry）
    3. 项目根目录 .env（开发模式）
    """
    override = os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR")
    if override:
        return Path(override).expanduser() / ".env"

    # 桌面版：检测是否在 frozen 模式或 ALPHAFOUNDRY_DESKTOP 环境变量
    if os.environ.get("ALPHAFOUNDRY_DESKTOP") or os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR"):
        import platform

        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / "AlphaFoundry" / ".env"
        if system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "AlphaFoundry" / ".env"
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "AlphaFoundry" / ".env"

    # 开发模式：项目根目录下的 .env
    project_root = Path(
        os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT", Path(__file__).parent.parent.parent)
    )
    return project_root / ".env"


settings = Settings()
settings.ensure_dirs()
