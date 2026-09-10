"""iFinD 数据源集成的惰性公开入口。"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

log = logging.getLogger(__name__)

_IFIND_MODULES = {
    "IFinDClient": "data_layer.adapters.ifind.client",
    "IFinDError": "data_layer.adapters.ifind.exceptions",
    "IFinDAuthError": "data_layer.adapters.ifind.exceptions",
    "IFinDQuotaExceededError": "data_layer.adapters.ifind.exceptions",
    "IFinDDatasourceError": "data_layer.adapters.ifind.exceptions",
    "IFinDSDKNotAvailableError": "data_layer.adapters.ifind.exceptions",
    "IFinDRateLimitError": "data_layer.adapters.ifind.exceptions",
    "IFinDHTTPClient": "data_layer.adapters.ifind.http_client",
    "IFinDSDKClient": "data_layer.adapters.ifind.sdk_client",
    "BackendRouter": "data_layer.adapters.ifind.router",
    "IFinDMapper": "data_layer.adapters.ifind.mappers",
}

__all__ = [
    "IFinDClient",
    "IFinDError",
    "IFinDAuthError",
    "IFinDQuotaExceededError",
    "IFinDDatasourceError",
    "IFinDSDKNotAvailableError",
    "IFinDRateLimitError",
    "IFinDHTTPClient",
    "IFinDSDKClient",
    "BackendRouter",
    "IFinDMapper",
]


def __getattr__(name: str) -> Any:
    """按需装载 HTTP、SDK 或映射层，避免互相引入可选依赖。"""
    module_name = _IFIND_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        value = getattr(import_module(module_name), name)
    except Exception:
        log.exception("ifind_adapter_lazy_import_failed", extra={"adapter": name})
        raise
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
