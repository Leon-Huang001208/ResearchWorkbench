"""数据适配器的惰性公开入口。"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

log = logging.getLogger(__name__)

_ADAPTER_MODULES = {
    "BaseDataAdapter": "data_layer.adapters.base",
    "IFinDAdapter": "data_layer.adapters.ifind_adapter",
    "ChinaStockAdapter": "data_layer.adapters.china_stock_adapter",
    "AKShareAdapter": "data_layer.adapters.akshare_adapter",
    "BaoStockAdapter": "data_layer.adapters.baostock_adapter",
    "YahooAdapter": "data_layer.adapters.yahoo_adapter",
    "LocalDataAdapter": "data_layer.adapters.local_data_adapter",
    "CLSAdapter": "data_layer.adapters.cls_adapter",
    "CninfoAdapter": "data_layer.adapters.cninfo_adapter",
    "CNStockAdapter": "data_layer.adapters.cnstock_adapter",
    "ZQAdapter": "data_layer.adapters.zq_adapter",
    "WindAdapter": "data_layer.adapters.wind.wind_adapter",
}

__all__ = [
    "BaseDataAdapter",
    "IFinDAdapter",
    "ChinaStockAdapter",
    "AKShareAdapter",
    "BaoStockAdapter",
    "YahooAdapter",
    "LocalDataAdapter",
    "CLSAdapter",
    "CninfoAdapter",
    "CNStockAdapter",
    "ZQAdapter",
    "WindAdapter",
]


def __getattr__(name: str) -> Any:
    """只在调用方请求具体适配器时装载其依赖。"""
    module_name = _ADAPTER_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        value = getattr(import_module(module_name), name)
    except Exception:
        log.exception("data_adapter_lazy_import_failed", extra={"adapter": name})
        raise
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
