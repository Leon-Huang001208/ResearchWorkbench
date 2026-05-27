"""数据源模块 — 自动发现并加载所有已注册的数据源。

将一个 .py 文件放入此目录即可注册新的数据源。
该文件在 import 时调用 core.source_registry.register(SourceSpec(...))。
"""

import importlib
import pkgutil

__all__: list[str] = []

for _, modname, _ in pkgutil.iter_modules(__path__):
    if not modname.startswith("_"):
        importlib.import_module(f".{modname}", __name__)
        __all__.append(modname)
