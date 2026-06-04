"""数据源注册中心 — 所有爬取数据源的自描述注册表。

每个数据源通过 register(SourceSpec(...)) 声明自身。所有消费者从注册表读取，
不再需要硬编码的 if/elif 分支或配置列表。

添加新数据源 = 在 data_sources/ 目录下创建一个新 .py 文件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType


@dataclass(frozen=True)
class SourceSpec:
    """数据源的完整自描述。

    每个活跃的爬取来源在启动时通过 register() 注册一个 SourceSpec 实例。
    所有调度、适配器派发、文档分类、检索权重等下游逻辑都从 SourceSpec 读取，
    而不是依赖硬编码的分支或字典。
    """

    source_type: SourceType
    source_name: str  # 人类可读名称，如 "财联社"

    # 适配器派发
    adapter_class: str  # 完全限定导入路径，如 "data_layer.adapters.cls_adapter.CLSAdapter"
    adapter_kwargs: Dict[str, Any] = field(default_factory=dict)

    # 调度配置
    interval_minutes: int = 60
    enabled: bool = True
    backfill_enabled: bool = True
    backfill_interval_hours: int = 24
    deep_backfill_enabled: bool = False
    days_per_crawl: int = 1
    max_docs: Optional[int] = None

    # 文档分类
    doc_type: DocType = DocType.NEWS
    reliability: SourceReliabilityLevel = SourceReliabilityLevel.ESTABLISHED_MEDIA

    # 深度回补系列 — 同一系列的来源共享深度回补逻辑
    # None = 无深度回补, "cls" = 财联社, "cnstock" = 中国证券网, "zq" = 知丘
    backfill_family: Optional[str] = None

    # 检索权重 (供 retrieval.py 使用)
    retrieval_weight: float = 1.0

    # 多源降级路由 — 同一 fallback_group 内按 fallback_priority 升序尝试
    fallback_group: Optional[str] = None
    fallback_priority: int = 100


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

_registry: Dict[SourceType, SourceSpec] = {}
_on_register_hooks: List[Callable[[SourceSpec], None]] = []


def register(spec: SourceSpec) -> None:
    """注册一个数据源。由 data_sources/ 下的模块在 import 时调用。"""
    if spec.source_type in _registry:
        raise ValueError(
            f"SourceType {spec.source_type.value} already registered: "
            f"{_registry[spec.source_type].source_name}"
        )
    _registry[spec.source_type] = spec
    for hook in _on_register_hooks:
        hook(spec)


def on_register(hook: Callable[[SourceSpec], None]) -> Callable[[SourceSpec], None]:
    """注册回调 — 每次 register() 被调用时触发。用于需要动态感知新来源的消费者。"""
    _on_register_hooks.append(hook)
    return hook


def _ensure_discovered() -> None:
    """如果注册表为空，触发数据源自动发现。"""
    if _registry:
        return
    try:
        import data_sources  # noqa: F401
    except ImportError:
        pass


def get(source_type: SourceType) -> Optional[SourceSpec]:
    """获取单个来源的 spec。"""
    _ensure_discovered()
    return _registry.get(source_type)


def get_all() -> List[SourceSpec]:
    """获取所有已注册来源 (不含顺序保证)。"""
    _ensure_discovered()
    return list(_registry.values())


def get_enabled() -> List[SourceSpec]:
    """获取所有 enabled=True 的来源。"""
    _ensure_discovered()
    return [s for s in _registry.values() if s.enabled]


def get_by_family(family: str) -> List[SourceSpec]:
    """获取属于同一 backfill_family 的所有来源。"""
    _ensure_discovered()
    return [s for s in _registry.values() if s.backfill_family == family]


def is_registered(source_type: SourceType) -> bool:
    """来源是否已注册。"""
    _ensure_discovered()
    return source_type in _registry


def get_fallback_groups() -> Dict[str, List[SourceSpec]]:
    """获取按优先级排序的多源降级组。"""
    _ensure_discovered()
    groups: Dict[str, List[SourceSpec]] = {}
    for spec in _registry.values():
        if spec.fallback_group is None:
            continue
        groups.setdefault(spec.fallback_group, []).append(spec)

    return {
        group: sorted(specs, key=lambda spec: spec.fallback_priority)
        for group, specs in groups.items()
    }
