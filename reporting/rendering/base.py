"""
渲染引擎抽象基类 — DocumentRenderer + RenderContext.

定义所有格式渲染器必须实现的通用接口，以及渲染过程中
传递上下文的 RenderContext 数据结构。
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from core.contracts.document import DesignTokens
from core.observability import get_logger

if TYPE_CHECKING:
    from core.contracts.content_element import (
        BulletListElement,
        CalloutElement,
        ChartElement,
        ContentBlock,
        DividerElement,
        HeadingElement,
        ImageElement,
        KeyValueElement,
        OrderedListElement,
        ParagraphElement,
        QuoteElement,
        SpeakerNotesElement,
        TableElement,
    )
    from core.contracts.document import Document, Section

logger = get_logger(__name__)


# ============================================================================
# RenderContext
# ============================================================================


@dataclass
class RenderContext:
    """渲染上下文 — 在一次 render_document 调用期间传递状态.

    由渲染器内部创建和消费，不暴露给外部调用者。

    Attributes:
        document_title: 文档标题（用于页眉/页脚）.
        current_section_index: 当前正在渲染的章节索引（0-based）.
        total_sections: 总章节数.
        current_block_index: 当前正在渲染的内容块索引.
        slide_number: PPT 当前幻灯片编号（仅 PPTRenderer 使用）.
        output_dir: 输出目录（用于图片等外部资源路径解析）.
        metadata: 调用方可附加的任意上下文数据.
    """

    document_title: str = ""
    current_section_index: int = 0
    total_sections: int = 0
    current_block_index: int = 0
    slide_number: int = 0
    output_dir: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# DocumentRenderer
# ============================================================================


class DocumentRenderer(ABC):
    """格式无关的文档渲染器抽象基类.

    定义了从 Document → 目标格式的完整渲染流程。子类只需实现
    各元素的 _render_* 方法，基类负责遍历 Document 的结构
    （章节 → 内容块 → 内容元素）并分发到对应方法。

    使用方式:
        renderer = WordRenderer(tokens)
        renderer.render_document(doc, Path("output.docx"))

    或流式输出:
        buffer = renderer.render_to_buffer(doc)
        buffer.seek(0)
    """

    def __init__(self, tokens: Optional[DesignTokens] = None) -> None:
        """初始化渲染器.

        Args:
            tokens: 设计令牌。为 None 时使用默认 DesignTokens.
        """
        self.tokens = tokens or DesignTokens()
        self._ctx: RenderContext = RenderContext()

    # ========================================================================
    # 公开 API
    # ========================================================================

    def render_document(
        self,
        document: "Document",
        output_path: Union[str, Path],
    ) -> Path:
        """渲染完整 Document 到文件.

        Args:
            document: 源 Document.
            output_path: 输出文件路径.

        Returns:
            输出文件的 Path.
        """
        from core.contracts.document import Document as Doc

        doc: Doc = document
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.tokens = doc.design_tokens or self.tokens

        self._ctx = RenderContext(
            document_title=doc.title,
            total_sections=len(doc.sections),
            output_dir=output_path.parent,
        )

        self._begin_document(doc)
        self._render_title_page(doc)

        for i, section in enumerate(doc.sections):
            self._ctx.current_section_index = i
            self._begin_section(section)

            for j, block in enumerate(section.blocks):
                self._ctx.current_block_index = j
                self._render_block(block)

            self._end_section(section)

        self._end_document(doc)
        self._finalize(output_path)

        logger.info(
            "Document rendered successfully",
            extra={
                "format": self.format_name,
                "title": doc.title,
                "sections": len(doc.sections),
                "output": str(output_path),
            },
        )
        return output_path

    def render_to_buffer(self, document: "Document") -> io.BytesIO:
        """渲染 Document 到内存缓冲区.

        Args:
            document: 源 Document.

        Returns:
            包含渲染结果的 BytesIO 缓冲区.
        """
        raise NotImplementedError(f"{self.format_name} 不支持流式输出，请使用 render_document")

    # ========================================================================
    # 子类必须实现的属性/方法
    # ========================================================================

    @property
    @abstractmethod
    def format_name(self) -> str:
        """目标格式名称（如 "Word", "PPT", "Markdown"）."""
        ...

    @abstractmethod
    def _begin_document(self, document: "Document") -> None:
        """文档渲染开始 — 创建目标格式的文档对象."""
        ...

    @abstractmethod
    def _end_document(self, document: "Document") -> None:
        """文档渲染结束 — 清理和收尾."""
        ...

    @abstractmethod
    def _finalize(self, output_path: Path) -> None:
        """将渲染结果写入文件."""
        ...

    # ========================================================================
    # 可选覆盖的钩子方法
    # ========================================================================

    def _render_title_page(self, document: "Document") -> None:
        """渲染标题页（封面页）.

        默认实现：不渲染标题页。子类可覆盖以生成封面/标题幻灯片。
        """
        pass

    def _begin_section(self, section: "Section") -> None:
        """章节开始 — 子类可覆盖以添加章节分隔."""
        pass

    def _end_section(self, section: "Section") -> None:
        """章节结束 — 子类可覆盖以添加章节尾."""
        pass

    # ========================================================================
    # 内容块渲染（基类实现遍历逻辑）
    # ========================================================================

    def _render_block(self, block: "ContentBlock") -> None:
        """渲染单个 ContentBlock — 遍历元素并分发.

        子类通常不需要覆盖此方法。若需要自定义块级布局
        （如 Word 的分栏、PPT 的 slide layout），可覆盖。
        """
        from core.contracts.content_element import ContentElementType

        for element in block.elements:
            if not element.visible:
                continue

            etype = element.element_type

            if etype == ContentElementType.HEADING:
                self._render_heading(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.PARAGRAPH:
                self._render_paragraph(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.BULLET_LIST:
                self._render_bullet_list(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.ORDERED_LIST:
                self._render_ordered_list(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.TABLE:
                self._render_table(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.CHART:
                self._render_chart(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.IMAGE:
                self._render_image(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.QUOTE:
                self._render_quote(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.CALLOUT:
                self._render_callout(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.KEY_VALUE:
                self._render_key_value(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.DIVIDER:
                self._render_divider(element)  # type: ignore[arg-type]
            elif etype == ContentElementType.SPEAKER_NOTES:
                self._render_speaker_notes(element)  # type: ignore[arg-type]
            else:
                logger.warning(
                    "Unknown element type, skipped",
                    extra={"element_type": str(etype)},
                )

    # ========================================================================
    # 元素级渲染方法（子类必须实现）
    # ========================================================================

    @abstractmethod
    def _render_heading(self, element: "HeadingElement") -> None:
        """渲染标题元素."""
        ...

    @abstractmethod
    def _render_paragraph(self, element: "ParagraphElement") -> None:
        """渲染段落元素."""
        ...

    @abstractmethod
    def _render_bullet_list(self, element: "BulletListElement") -> None:
        """渲染无序列表."""
        ...

    @abstractmethod
    def _render_ordered_list(self, element: "OrderedListElement") -> None:
        """渲染有序列表."""
        ...

    @abstractmethod
    def _render_table(self, element: "TableElement") -> None:
        """渲染表格."""
        ...

    @abstractmethod
    def _render_chart(self, element: "ChartElement") -> None:
        """渲染图表."""
        ...

    @abstractmethod
    def _render_image(self, element: "ImageElement") -> None:
        """渲染图片."""
        ...

    @abstractmethod
    def _render_quote(self, element: "QuoteElement") -> None:
        """渲染引用块."""
        ...

    @abstractmethod
    def _render_callout(self, element: "CalloutElement") -> None:
        """渲染提示框."""
        ...

    @abstractmethod
    def _render_key_value(self, element: "KeyValueElement") -> None:
        """渲染键值对."""
        ...

    @abstractmethod
    def _render_divider(self, element: "DividerElement") -> None:
        """渲染分隔线."""
        ...

    @abstractmethod
    def _render_speaker_notes(self, element: "SpeakerNotesElement") -> None:
        """渲染演讲者备注."""
        ...


# ============================================================================
# 向后兼容桥接
# ============================================================================


def render_document(
    document: "Document",
    output_path: Union[str, Path],
    format: str = "word",
    tokens: Optional[DesignTokens] = None,
) -> Path:
    """便捷函数 — 按格式名渲染 Document.

    Args:
        document: 源 Document.
        output_path: 输出路径.
        format: 目标格式 ("word" | "ppt" | "markdown").
        tokens: 设计令牌（默认使用 document.design_tokens）.

    Returns:
        输出文件路径.

    Raises:
        ValueError: 不支持的格式.
    """
    fmt = format.lower()
    if fmt in ("word", "docx"):
        from reporting.rendering.word_renderer import WordRenderer

        renderer = WordRenderer(tokens)
    elif fmt in ("ppt", "pptx", "powerpoint"):
        from reporting.rendering.ppt_renderer import PPTRenderer

        renderer = PPTRenderer(tokens)
    elif fmt in ("md", "markdown"):
        from reporting.rendering.markdown_renderer import MarkdownRenderer

        renderer = MarkdownRenderer(tokens)
    else:
        raise ValueError(f"Unsupported format: {format!r}")

    return renderer.render_document(document, output_path)
