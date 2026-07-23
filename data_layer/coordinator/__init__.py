"""
协调器模块

提供多源数据协调功能。
"""

from data_layer.coordinator.multi_source_coordinator import (
    CoordinatorResult,
    MultiSourceCoordinator,
    get_coordinator,
)

__all__ = [
    "MultiSourceCoordinator",
    "CoordinatorResult",
    "get_coordinator",
]
