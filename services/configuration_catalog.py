"""Static, value-free metadata for the unified configuration experience."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def _freeze_catalog(value: Any) -> Any:
    """Recursively make the module-level catalog immutable."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_catalog(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_catalog(item) for item in value)
    return value


def _json_safe_copy(value: Any) -> Any:
    """Return a detached copy while converting immutable sequences to lists."""
    if isinstance(value, Mapping):
        return {key: _json_safe_copy(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe_copy(item) for item in value]
    return value


CONFIGURATION_CATALOG = _freeze_catalog(
    {
        "sections": [
            {
                "key": "llm",
                "label": "大语言模型",
                "scope": "runtime",
                "platforms": ["desktop", "web"],
                "restart_required": False,
                "testable": True,
                "fields": [
                    {
                        "key": "providers",
                        "label": "模型服务商",
                        "kind": "collection",
                        "environment_keys": [
                            "LLM_PROVIDER_*_NAME",
                            "LLM_PROVIDER_*_PROTOCOL",
                            "LLM_PROVIDER_*_BASE_URL",
                            "LLM_PROVIDER_*_API_KEY",
                        ],
                    },
                    {
                        "key": "task_routes",
                        "label": "任务模型路由",
                        "kind": "collection",
                        "environment_keys": ["TASK_*_PROVIDER", "TASK_*_MODEL"],
                    },
                ],
            },
            {
                "key": "zhiqiu",
                "label": "知秋",
                "scope": "integration",
                "platforms": ["desktop", "web"],
                "restart_required": False,
                "testable": True,
                "fields": [
                    {
                        "key": "accounts",
                        "label": "知秋账号",
                        "kind": "collection",
                        "environment_keys": ["ZQ_ACCOUNTS_JSON"],
                    },
                    {
                        "key": "rotation_enabled",
                        "label": "启用账号轮换",
                        "kind": "boolean",
                        "environment_keys": ["ZQ_ROTATION_ENABLED"],
                    },
                    {
                        "key": "rotation_strategy",
                        "label": "账号轮换策略",
                        "kind": "select",
                        "environment_keys": ["ZQ_ROTATION_STRATEGY"],
                    },
                    {
                        "key": "max_retries",
                        "label": "最大重试次数",
                        "kind": "number",
                        "environment_keys": ["ZQ_MAX_RETRIES"],
                    },
                    {
                        "key": "retry_delay",
                        "label": "重试间隔",
                        "kind": "number",
                        "environment_keys": ["ZQ_RETRY_DELAY"],
                    },
                    {
                        "key": "lease_timeout",
                        "label": "账号租约超时",
                        "kind": "number",
                        "environment_keys": ["ZQ_LEASE_TIMEOUT"],
                    },
                    {
                        "key": "max_consecutive_failures",
                        "label": "最大连续失败次数",
                        "kind": "number",
                        "environment_keys": ["ZQ_MAX_CONSECUTIVE_FAILURES"],
                    },
                ],
            },
            {
                "key": "ifind",
                "label": "iFinD",
                "scope": "integration",
                "platforms": ["desktop", "web"],
                "restart_required": False,
                "testable": True,
                "fields": [
                    {
                        "key": "accounts",
                        "label": "iFinD 账号",
                        "kind": "collection",
                        "environment_keys": ["IFIND_ACCOUNTS_JSON"],
                    },
                    {
                        "key": "username",
                        "label": "用户名",
                        "kind": "text",
                        "environment_keys": ["IFIND_USERNAME"],
                    },
                    {
                        "key": "password",
                        "label": "密码",
                        "kind": "secret",
                        "environment_keys": ["IFIND_PASSWORD"],
                    },
                    {
                        "key": "backend",
                        "label": "连接后端",
                        "kind": "select",
                        "environment_keys": ["IFIND_BACKEND"],
                    },
                    {
                        "key": "http_base_url",
                        "label": "HTTP 服务地址",
                        "kind": "url",
                        "environment_keys": ["IFIND_HTTP_BASE_URL"],
                    },
                ],
            },
            {
                "key": "database",
                "label": "数据库",
                "scope": "storage",
                "platforms": ["desktop", "web"],
                "restart_required": True,
                "testable": True,
                "fields": [
                    {
                        "key": "database_url",
                        "label": "数据库连接地址",
                        "kind": "secret",
                        "environment_keys": ["DATABASE_URL"],
                    }
                ],
            },
            {
                "key": "advanced",
                "label": "高级设置",
                "scope": "runtime",
                "platforms": ["desktop", "web"],
                "restart_required": True,
                "testable": False,
                "fields": [
                    {
                        "key": "log_level",
                        "label": "日志级别",
                        "kind": "select",
                        "environment_keys": ["LOG_LEVEL"],
                    },
                    {
                        "key": "log_dir",
                        "label": "日志目录",
                        "kind": "text",
                        "environment_keys": ["LOG_DIR"],
                    },
                    {
                        "key": "llm_max_workers",
                        "label": "模型最大并发数",
                        "kind": "number",
                        "environment_keys": ["LLM_EXTRACT_MAX_WORKERS"],
                    },
                    {
                        "key": "llm_max_retries",
                        "label": "模型最大重试次数",
                        "kind": "number",
                        "environment_keys": ["LLM_EXTRACT_MAX_RETRIES"],
                    },
                    {
                        "key": "chunk_size",
                        "label": "文本分块大小",
                        "kind": "number",
                        "environment_keys": ["LLM_EXTRACT_CHUNK_SIZE"],
                    },
                    {
                        "key": "chunk_overlap",
                        "label": "文本分块重叠",
                        "kind": "number",
                        "environment_keys": ["LLM_EXTRACT_CHUNK_OVERLAP"],
                    },
                    {
                        "key": "long_text_threshold",
                        "label": "长文本阈值",
                        "kind": "number",
                        "environment_keys": ["LLM_EXTRACT_LONG_TEXT_THRESHOLD"],
                    },
                ],
            },
            {
                "key": "web_search",
                "label": "网页搜索",
                "scope": "integration",
                "platforms": ["desktop", "web"],
                "restart_required": False,
                "testable": True,
                "fields": [
                    {
                        "key": "accounts",
                        "label": "搜索 API 密钥",
                        "kind": "collection",
                        "environment_keys": ["WEB_SEARCH_API_KEYS"],
                    },
                    {
                        "key": "provider",
                        "label": "搜索服务商",
                        "kind": "select",
                        "environment_keys": ["WEB_SEARCH_PROVIDER"],
                    },
                    {
                        "key": "rotation_strategy",
                        "label": "密钥轮换策略",
                        "kind": "select",
                        "environment_keys": ["WEB_SEARCH_KEY_ROTATION"],
                    },
                    {
                        "key": "quota_limit",
                        "label": "密钥额度上限",
                        "kind": "number",
                        "environment_keys": ["WEB_SEARCH_KEY_QUOTA_LIMIT"],
                    },
                    {
                        "key": "max_results",
                        "label": "最大结果数",
                        "kind": "number",
                        "environment_keys": ["WEB_SEARCH_MAX_RESULTS"],
                    },
                    {
                        "key": "timeout",
                        "label": "搜索超时",
                        "kind": "number",
                        "environment_keys": ["WEB_SEARCH_TIMEOUT"],
                    },
                ],
            },
        ]
    }
)


def get_configuration_catalog() -> dict[str, Any]:
    """Return a fresh JSON-safe copy of the static configuration catalog."""
    return _json_safe_copy(CONFIGURATION_CATALOG)


__all__ = ["CONFIGURATION_CATALOG", "get_configuration_catalog"]
