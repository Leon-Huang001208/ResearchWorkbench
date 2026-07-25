"""Configuration metadata shared by desktop bootstrap and documentation templates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigurationField:
    """Metadata for a user-configurable runtime environment field."""

    key: str
    default: str
    secret: bool = False
    restart_required: bool = False


DESKTOP_CONFIGURATION_FIELDS = (
    ConfigurationField(
        key="DATABASE_URL",
        default="postgresql+psycopg://user:password@127.0.0.1:5432/alphafoundry",
        secret=True,
        restart_required=True,
    ),
    ConfigurationField(key="LOG_LEVEL", default="INFO"),
    ConfigurationField(key="LLM_EXTRACT_MAX_WORKERS", default="8"),
    ConfigurationField(key="LLM_EXTRACT_CHUNK_SIZE", default="3500"),
    ConfigurationField(key="LLM_EXTRACT_CHUNK_OVERLAP", default="300"),
    ConfigurationField(key="LLM_EXTRACT_MAX_RETRIES", default="2"),
    ConfigurationField(key="LLM_EXTRACT_LONG_TEXT_THRESHOLD", default="1000"),
    ConfigurationField(key="CRAWLER_QUIET_START", default="0"),
    ConfigurationField(key="CRAWLER_QUIET_END", default="6"),
)


def desktop_env_template() -> str:
    """Return the secure first-run desktop configuration template."""
    return """# AlphaFoundry 桌面版配置
# 本文件由桌面版首次启动时生成。桌面端必须连接用户自行安装的 PostgreSQL + pgvector。
# 保存 DATABASE_URL 后重启应用才会切换数据库连接。

# 数据库（PostgreSQL + pgvector；使用 psycopg v3 驱动）
DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/alphafoundry

# 日志级别
LOG_LEVEL=INFO

# LLM 并发提取
LLM_EXTRACT_MAX_WORKERS=8
LLM_EXTRACT_CHUNK_SIZE=3500
LLM_EXTRACT_CHUNK_OVERLAP=300
LLM_EXTRACT_MAX_RETRIES=2
LLM_EXTRACT_LONG_TEXT_THRESHOLD=1000

# ── LLM Provider（按需填写）──
# LLM_PROVIDER_1_NAME=deepseek
# LLM_PROVIDER_1_PROTOCOL=openai_compatible
# LLM_PROVIDER_1_BASE_URL=https://api.example.invalid/v1
# LLM_PROVIDER_1_API_KEY=replace-with-your-api-key

# ── 任务路由 ──
# TASK_EXTRACT_PROVIDER=deepseek
# TASK_EXTRACT_MODEL=deepseek-chat
# TASK_CLASSIFY_PROVIDER=deepseek
# TASK_CLASSIFY_MODEL=deepseek-chat
# TASK_DEFAULT_PROVIDER=deepseek
# TASK_DEFAULT_MODEL=deepseek-chat

# ── 爬虫夜间静默（本地时间整点）──
CRAWLER_QUIET_START=0
CRAWLER_QUIET_END=6
"""
