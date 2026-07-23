"""
Markdown 渲染器 — 将 Document 渲染为 .md 格式.

纯文本渲染器，无外部依赖，主要用于：
- 内容预览和调试
- 管道中间产物检查
- 快速生成可读的纯文本报告

所有 DesignTokens 的视觉样式信息被映射为 Markdown 的语义标记
（标题级别 → # 数量，bold → **text**，等）。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from core.contracts.document import DesignTokens
from core.observability import get_logger
from reporting.rendering.base import DocumentRenderer
from reporting.rendering.style_mapper import StyleMapper

logger = get_logger(__name__)

if TYPE_CHECKING:
    from core.contracts.content_element import (
        BulletListElement,
        CalloutElement,
        ChartElement,
        DividerElement,
        HeadingElement,
        ImageElement,
        KeyValueElement,
        ListItem,
        OrderedListElement,
        ParagraphElement,
        QuoteElement,
        SpeakerNotesElement,
        TableElement,
    )
    from core.contracts.document import Document, Section


class MarkdownRenderer(DocumentRenderer):
    """Markdown (.md) 文档渲染器.

    Usage:
        doc = Document(title="报告", sections=[...])
        renderer = MarkdownRenderer()
        renderer.render_document(doc, Path("output.md"))
    """

    def __init__(self, tokens: Optional[DesignTokens] = None) -> None:
        super().__init__(tokens)
        self._mapper: StyleMapper = StyleMapper(self.tokens)
        self._lines: List[str] = []

    # ========================================================================
    # 抽象方法实现
    # ========================================================================

    @property
    def format_name(self) -> str:
        return "Markdown"

    def _begin_document(self, document: "Document") -> None:
        self._lines = []

    def _end_document(self, document: "Document") -> None:
        """文档结束 — 添加页脚."""
        if document.metadata:
            self._lines.append("")
            self._lines.append("---")
            for key, value in document.metadata.items():
                self._lines.append(f"*{key}*: {value}")

    def _finalize(self, output_path: Path) -> None:
        output_path.write_text("\n".join(self._lines), encoding="utf-8")
        logger.info(
            "Markdown rendered",
            extra={"lines": len(self._lines), "output": str(output_path)},
        )

    def render_to_buffer(self, document: "Document") -> io.BytesIO:
        self.render_document(document, Path("_temp_buffer.md"))
        return io.BytesIO("\n".join(self._lines).encode("utf-8"))

    # ========================================================================
    # 标题页
    # ========================================================================

    def _render_title_page(self, document: "Document") -> None:
        self._lines.append(f"# {document.title}")
        if document.subtitle:
            self._lines.append(f"*{document.subtitle}*")
        self._lines.append("")

    # ========================================================================
    # Section 钩子
    # ========================================================================

    def _begin_section(self, section: "Section") -> None:
        if section.page_break_before:
            self._lines.append("")
            self._lines.append("---")
            self._lines.append("")

    # ========================================================================
    # 元素渲染方法
    # ========================================================================

    def _render_heading(self, element: "HeadingElement") -> None:
        prefix = "#" * min(element.level, 6)
        self._lines.append(f"{prefix} {element.text}")
        self._lines.append("")

    def _render_paragraph(self, element: "ParagraphElement") -> None:
        if element.runs:
            text = ""
            for tr in element.runs:
                t = tr.text
                if tr.bold:
                    t = f"**{t}**"
                if tr.italic:
                    t = f"*{t}*"
                if tr.hyperlink:
                    t = f"[{t}]({tr.hyperlink})"
                text += t
            self._lines.append(text)
        self._lines.append("")

    def _render_bullet_list(self, element: "BulletListElement") -> None:
        for item in element.items:
            self._render_list_item(item, "- ")
        self._lines.append("")

    def _render_ordered_list(self, element: "OrderedListElement") -> None:
        for idx, item in enumerate(element.items, start=element.start):
            self._render_list_item(item, f"{idx}. ")
        self._lines.append("")

    def _render_table(self, element: "TableElement") -> None:
        rows: List[List[str]] = []

        if element.headers:
            rows.append(["".join(r.text for r in cells) for cells in element.headers])
            # 分隔线
            rows.append(["---" for _ in element.headers])
        else:
            # 无表头时用第一行数据宽度
            first_width = max((len(row) for row in element.rows), default=0)
            rows.append(["" for _ in range(first_width)])
            rows.append(["---" for _ in range(first_width)])

        for row in element.rows:
            rows.append(["".join(r.text for r in cells) for cells in row])

        for row in rows:
            self._lines.append("| " + " | ".join(str(c) for c in row) + " |")
        self._lines.append("")

    def _render_chart(self, element: "ChartElement") -> None:
        title = element.title or element.chart_id
        self._lines.append(f"> **[图表] {title}**")
        if element.source_note:
            self._lines.append(f"> *{element.source_note}*")

        if element.data_labels and element.data_series:
            self._lines.append("")
            self._lines.append("| Series | " + " | ".join(element.data_labels) + " |")
            self._lines.append("| --- | " + " | ".join(["---"] * len(element.data_labels)) + " |")
            for i, series in enumerate(element.data_series):
                self._lines.append(
                    f"| Series {i + 1} | " + " | ".join(str(v) for v in series) + " |"
                )
        self._lines.append("")

    def _render_image(self, element: "ImageElement") -> None:
        alt = element.alt_text or element.caption or "image"
        self._lines.append(f"![{alt}]({alt})")
        if element.caption:
            self._lines.append(f"*{element.caption}*")
        self._lines.append("")

    def _render_quote(self, element: "QuoteElement") -> None:
        self._lines.append(f"> {element.text}")
        if element.attribution:
            self._lines.append(f"> {element.attribution}")
        self._lines.append("")

    def _render_callout(self, element: "CalloutElement") -> None:
        ct = (
            element.callout_type.value
            if hasattr(element.callout_type, "value")
            else str(element.callout_type)
        )
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "tip": "💡",
            "key_finding": "🔑",
        }
        emoji = emoji_map.get(ct, "📌")
        title = element.title or ct.replace("_", " ").title()
        self._lines.append(f"> **{emoji} {title}**")
        self._lines.append(f"> {element.text}")
        self._lines.append("")

    def _render_key_value(self, element: "KeyValueElement") -> None:
        for key, value in element.pairs:
            self._lines.append(f"- **{key}**: {value}")
        self._lines.append("")

    def _render_divider(self, element: "DividerElement") -> None:
        self._lines.append("---")
        self._lines.append("")

    def _render_speaker_notes(self, element: "SpeakerNotesElement") -> None:
        self._lines.append(f"> 🎤 *[演讲者备注]* {element.text}")
        self._lines.append("")

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _render_list_item(self, item: "ListItem", prefix: str, indent: int = 0) -> None:
        """递归渲染列表项."""
        indent_str = "  " * indent
        text = "".join(r.text for r in item.runs) if item.runs else ""
        self._lines.append(f"{indent_str}{prefix}{text}")

        if item.sub_items:
            for sub in item.sub_items:
                self._render_list_item(sub, "- ", indent + 1)
