"""reporting.content - 通用内容模型适配器层.

提供旧格式（SectionOutput/FactCard/CompiledReport）到新统一
内容模型（Document/Section/ContentElement）的转换适配器。
"""

from reporting.content.adapter import ContentAdapter

__all__ = [
    "ContentAdapter",
]
