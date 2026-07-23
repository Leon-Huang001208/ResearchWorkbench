"""核心服务模块——按需导入，避免启动时全量加载。

模块级导入已通过 PEP 562 __getattr__ 改为懒加载：
- from services import AssetAnalysisService  → 懒加载类
- from services import dashboard_service     → 懒加载模块
"""

import importlib
from typing import Any

#: 懒加载映射：属性名 → (模块路径, 类名或 None=模块本身)
_LAZY_MAP: dict[str, tuple[str, str | None]] = {
    # ── 类（from services import ClassName） ──
    "AssetAnalysisService": ("services.asset_analysis_service", "AssetAnalysisService"),
    "SignalService": ("services.signal_service", "SignalService"),
    # ── 模块（from services import module as m） ──
    "dashboard_service": ("services.dashboard_service", None),
    "pdf_conversion_service": ("services.pdf_conversion_service", None),
    "wind_realtime_workbook": ("services.wind_realtime_workbook", None),
    "wind_workbook_manager": ("services.wind_workbook_manager", None),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_MAP:
        raise AttributeError(
            f"module 'services' has no attribute '{name}'. "
            f"Available (lazy): {sorted(_LAZY_MAP.keys())}"
        )

    module_path, class_name = _LAZY_MAP[name]
    module = importlib.import_module(module_path)

    if class_name is not None:
        obj = getattr(module, class_name)
    else:
        obj = module

    # 缓存：下次访问直接返回，不再触发 __getattr__
    globals()[name] = obj
    return obj
