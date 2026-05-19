"""
报告生成与现有系统集成模块

此模块提供：
1. SnapshotToPlaceholdersMapper - 将资产分析快照映射到模板占位符
2. API集成 - 与模板渲染API集成
3. 端到端报告生成流程
"""

from reporting.integration.snapshot_mapper import SnapshotToPlaceholdersMapper, get_snapshot_mapper

__all__ = [
    "SnapshotToPlaceholdersMapper",
    "get_snapshot_mapper",
]
