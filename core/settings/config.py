from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 项目根目录
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent

    # 数据库 (默认使用 PostgreSQL；也支持 SQLite，比如 "sqlite:///./data/alphafoundry.db")
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/alphafoundry"

    # 模型网关
    MODEL_PROVIDER: Literal["volcano", "openai_compatible"] = "volcano"
    VOLCANO_API_KEY: str = ""
    VOLCANO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # 默认模型
    DEFAULT_CHAT_MODEL: str = "gpt-4"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-ada-002"

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_DIR: Path = PROJECT_ROOT / "logs"

    # 对象存储
    OBJECT_STORAGE_PATH: Path = PROJECT_ROOT / "data" / "objects"

    def ensure_dirs(self) -> None:
        """确保必要的目录存在"""
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.OBJECT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
