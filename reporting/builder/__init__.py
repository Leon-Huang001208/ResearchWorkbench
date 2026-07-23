"""reporting.builder - 统一报告流水线.

将报告生成拆分为三个独立阶段：
    Build → Validate → Render

ContentBuilder 负责将各种输入（模板/研究产出/字典）转换为
统一的 Document 模型，UnifiedPipeline 串联整个流程。
"""

from reporting.builder.content_builder import ContentBuilder
from reporting.builder.pipeline import UnifiedPipeline

__all__ = [
    "ContentBuilder",
    "UnifiedPipeline",
]
