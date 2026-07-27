"""reporting.builder.strategies - 文档构建策略.

每种策略定义了一种从输入源 → Document 的构建路径：
- from_research: 深度研究编译器产出 → Document
"""

from reporting.builder.strategies.from_research import ResearchStrategy

__all__ = [
    "ResearchStrategy",
]
