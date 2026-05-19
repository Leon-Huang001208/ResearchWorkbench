from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 项目根目录
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

    # Runtime environment: dev/prod
    # dev: allows in-memory fallbacks for demo purposes
    # prod: no silent fallback, fail immediately if persistence not configured
    APP_ENV: Literal["dev", "prod"] = "dev"

    # 数据库 (默认推荐 PostgreSQL 用于持久化运行；SQLite 保留用于零配置演示)
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/alphafoundry"

    # 模型网关
    MODEL_PROVIDER: Literal["volcano", "openai_compatible"] = "volcano"
    VOLCANO_API_KEY: str = ""
    VOLCANO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # 默认模型
    DEFAULT_CHAT_MODEL: str = "doubao-seed-2-0-pro-260215"
    DEFAULT_EMBEDDING_MODEL: str = "doubao-embedding-vision-251215"

    # 模型路由（不同任务用不同模型）
    EXTRACTION_MODEL: str = "doubao-seed-2-0-pro-260215"
    CLASSIFICATION_MODEL: str = "doubao-seed-2-0-lite-260428"
    CODE_MODEL: str = "doubao-seed-2-0-code-preview-260215"
    REASONING_MODEL: str = "deepseek-v3-2-251201"

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_DIR: Path = PROJECT_ROOT / "logs"

    # iFinD 数据源
    IFIND_USERNAME: str = ""
    IFIND_PASSWORD: str = ""
    IFIND_BACKEND: Literal["auto", "python_sdk", "http_api"] = "auto"
    IFIND_HTTP_BASE_URL: str = "https://quantapi.10jqka.com.cn"

    # China Stock 数据源
    CHINA_STOCK_ENABLED: bool = True

    # 对象存储
    OBJECT_STORAGE_PATH: Path = PROJECT_ROOT / "data" / "objects"

    # LLM 并发提取配置
    LLM_EXTRACT_MAX_WORKERS: int = 8
    LLM_EXTRACT_CHUNK_SIZE: int = 3500
    LLM_EXTRACT_CHUNK_OVERLAP: int = 300
    LLM_EXTRACT_MAX_RETRIES: int = 2
    LLM_EXTRACT_LONG_TEXT_THRESHOLD: int = 1000

    # PDF 转换输出目录
    PDF_MARKDOWN_DIR: Path = PROJECT_ROOT / "data" / "markdown"
    PDF_RAW_TEXT_DIR: Path = PROJECT_ROOT / "data" / "raw_text"
    # 小于此字节数的内容会同时内联到数据库
    PDF_INLINE_THRESHOLD_BYTES: int = 256 * 1024  # 256 KB

    def ensure_dirs(self) -> None:
        """确保必要的目录存在"""
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.OBJECT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        self.PDF_MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
        self.PDF_RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
