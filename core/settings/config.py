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

    # 数据库
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/alphafoundry"

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


settings = Settings()
settings.ensure_dirs()
