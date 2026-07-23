"""reporting.rendering - 通用文档渲染引擎.

提供格式无关的文档渲染抽象层，将统一的 Document 模型渲染为
Word/PPT/Markdown 等目标格式。所有渲染器共享 DesignTokens，
确保跨格式的视觉一致性。

架构：
    Document → DocumentRenderer (abstract)
        ├─ WordRenderer     → .docx
        ├─ PPTRenderer      → .pptx
        └─ MarkdownRenderer → .md
"""

from reporting.rendering.base import DocumentRenderer, RenderContext
from reporting.rendering.style_mapper import StyleMapper

__all__ = [
    "DocumentRenderer",
    "RenderContext",
    "StyleMapper",
]
