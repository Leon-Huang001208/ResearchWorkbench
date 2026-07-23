"""
Word 渲染器 — 将 Document 渲染为 .docx 格式.

基于 python-docx，逐元素渲染 ContentElement 到 Word 文档，
使用 StyleMapper 将 DesignTokens 映射为 Word 样式参数。

支持特性：
- 所有 12 种 ContentElement 类型的 Word 渲染
- DesignTokens → Word 样式（字体/字号/颜色/间距）
- 表格的条纹样式和自动列宽
- 图表渲染为内嵌图片（通过 matplotlib 生成）
- CalloutElement 渲染为带背景色的边框段落
- 标题自动应用 Word 内置 Heading 样式
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from core.contracts.document import DesignTokens
from core.observability import get_logger
from reporting.rendering.base import DocumentRenderer
from reporting.rendering.style_mapper import StyleMapper

logger = get_logger(__name__)

# python-docx 是必需的 Word 渲染依赖
try:
    import docx
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement
    from docx.shared import Inches, Pt, RGBColor

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

if TYPE_CHECKING:
    from docx.document import Document as DocxDocument

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
        TextRun,
    )
    from core.contracts.document import Document, Section


# ============================================================================
# WordRenderer
# ============================================================================


class WordRenderer(DocumentRenderer):
    """Word (.docx) 文档渲染器.

    Usage:
        doc = Document(title="研报", sections=[...])
        renderer = WordRenderer()
        renderer.render_document(doc, Path("output.docx"))
    """

    def __init__(self, tokens: Optional[DesignTokens] = None) -> None:
        super().__init__(tokens)
        if not DOCX_AVAILABLE:
            raise ImportError(
                "python-docx is required for Word output. " "Install with: pip install python-docx"
            )
        self._doc: Optional["DocxDocument"] = None
        self._mapper: StyleMapper = StyleMapper(self.tokens)

    # ========================================================================
    # 抽象方法实现
    # ========================================================================

    @property
    def format_name(self) -> str:
        return "Word"

    def _begin_document(self, document: "Document") -> None:
        self._doc = docx.Document()

        # 设置默认段落字体
        style = self._doc.styles["Normal"]
        body = self._mapper.word_body_style()
        font = style.font
        font.name = body["font_name"]
        font.size = Pt(body["font_size_pt"])
        font.color.rgb = self._hex_to_rgb(body["color_hex"])
        style.paragraph_format.line_spacing = body["line_spacing"]
        style.paragraph_format.space_after = Pt(body["space_after_pt"])

        # 设置页边距
        for section in self._doc.sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(1.2)
            section.right_margin = Inches(1.2)

    def _end_document(self, document: "Document") -> None:
        """添加页眉页脚."""
        doc = self._doc
        assert doc is not None

        for section in doc.sections:
            # 页眉：文档标题
            header = section.header
            header_para = header.paragraphs[0]
            header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            header_run = header_para.add_run(document.title)
            header_run.font.size = Pt(self.tokens.small_size)
            header_run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

            # 页脚：页码
            footer = section.footer
            footer_para = footer.paragraphs[0]
            footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 插入页码域代码
            self._add_page_number_field(footer_para)

    @staticmethod
    def _add_page_number_field(paragraph: Any) -> None:
        """在段落中插入页码域代码."""
        from docx.oxml.shared import OxmlElement

        run = paragraph.add_run()
        run.font.size = Pt(9)
        fldChar1 = OxmlElement("w:fldChar")
        fldChar1.set(qn("w:fldCharType"), "begin")
        run._r.append(fldChar1)

        run2 = paragraph.add_run()
        run2.font.size = Pt(9)
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = " PAGE "
        run2._r.append(instrText)

        run3 = paragraph.add_run()
        run3.font.size = Pt(9)
        fldChar2 = OxmlElement("w:fldChar")
        fldChar2.set(qn("w:fldCharType"), "end")
        run3._r.append(fldChar2)

    def _finalize(self, output_path: Path) -> None:
        assert self._doc is not None
        self._doc.save(str(output_path))

    def render_to_buffer(self, document: "Document") -> io.BytesIO:
        self.render_document(document, Path("_temp_buffer.docx"))
        assert self._doc is not None
        buf = io.BytesIO()
        self._doc.save(buf)
        return buf

    # ========================================================================
    # 标题页
    # ========================================================================

    def _render_title_page(self, document: "Document") -> None:
        doc = self._doc
        assert doc is not None

        # 空行留白
        for _ in range(6):
            doc.add_paragraph()

        # 主标题
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(document.title)
        run.font.name = self.tokens.heading_font
        run.font.size = Pt(self.tokens.heading_sizes.get(1, 28))
        run.font.color.rgb = self._hex_to_rgb(self.tokens.primary_color)
        run.bold = True

        # 副标题
        if document.subtitle:
            doc.add_paragraph()
            sub_para = doc.add_paragraph()
            sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = sub_para.add_run(document.subtitle)
            run.font.name = self.tokens.body_font
            run.font.size = Pt(self.tokens.heading_sizes.get(3, 16))
            run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

        # 元数据
        if document.metadata:
            doc.add_paragraph()
            for _ in range(2):
                doc.add_paragraph()
            meta_para = doc.add_paragraph()
            meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            meta_parts = []
            if "author" in document.metadata:
                meta_parts.append(f"作者: {document.metadata['author']}")
            if "date" in document.metadata:
                meta_parts.append(f"日期: {document.metadata['date']}")
            if not meta_parts:
                meta_parts.append(f"生成日期: {datetime.now().strftime('%Y-%m-%d')}")
            run = meta_para.add_run(" | ".join(meta_parts))
            run.font.size = Pt(self.tokens.small_size)
            run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

        # 分页
        doc.add_page_break()

        # 插入目录
        self._insert_toc(doc)
        doc.add_page_break()

    def _insert_toc(self, doc: "DocxDocument") -> None:
        """插入自动目录（TOC 域代码）.

        生成 Word TOC 域，用户打开文档后右键 → 更新域即可
        自动生成带页码的目录。
        """
        # 目录标题
        toc_title = doc.add_paragraph()
        toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = toc_title.add_run("目  录")
        run.font.name = self.tokens.heading_font
        run.font.size = Pt(self.tokens.heading_sizes.get(2, 22))
        run.font.color.rgb = self._hex_to_rgb(self.tokens.primary_color)
        run.bold = True
        doc.add_paragraph()

        # TOC 域代码
        para = doc.add_paragraph()
        run = para.add_run()

        # 开始 TOC 域
        fldChar_begin = OxmlElement("w:fldChar")
        fldChar_begin.set(qn("w:fldCharType"), "begin")
        run._r.append(fldChar_begin)

        # TOC 指令
        run2 = para.add_run()
        instrText = OxmlElement("w:instrText")
        instrText.set(qn("xml:space"), "preserve")
        instrText.text = ' TOC \\o "1-3" \\h \\z \\u '
        run2._r.append(instrText)

        # TOC 分隔符
        run3 = para.add_run()
        fldChar_sep = OxmlElement("w:fldChar")
        fldChar_sep.set(qn("w:fldCharType"), "separate")
        run3._r.append(fldChar_sep)

        # 提示文字
        run4 = para.add_run("（右键点击此处 → 更新域 → 更新整个目录）")
        run4.font.italic = True
        run4.font.size = Pt(self.tokens.small_size)
        run4.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

        # 结束 TOC 域
        run5 = para.add_run()
        fldChar_end = OxmlElement("w:fldChar")
        fldChar_end.set(qn("w:fldCharType"), "end")
        run5._r.append(fldChar_end)

    # ========================================================================
    # Section 钩子
    # ========================================================================

    def _begin_section(self, section: "Section") -> None:
        doc = self._doc
        assert doc is not None

        if section.page_break_before and self._ctx.current_section_index > 0:
            doc.add_page_break()

    # ========================================================================
    # 元素渲染方法
    # ========================================================================

    def _render_heading(self, element: "HeadingElement") -> None:
        doc = self._doc
        assert doc is not None

        style = self._mapper.word_heading_style(element.level)
        heading = doc.add_heading(element.text, level=min(element.level, 6))

        # 覆盖样式以匹配 DesignTokens
        for run in heading.runs:
            run.font.name = style["font_name"]
            run.font.size = Pt(style["font_size_pt"])
            run.font.color.rgb = self._hex_to_rgb(style["color_hex"])

    def _render_paragraph(self, element: "ParagraphElement") -> None:
        doc = self._doc
        assert doc is not None

        body = self._mapper.word_body_style()
        para = doc.add_paragraph()

        # 对齐
        para.alignment = self._map_alignment(element.alignment)

        # 行距
        para.paragraph_format.line_spacing = element.line_spacing or body["line_spacing"]

        # 渲染 TextRun 序列
        if element.runs:
            for tr in element.runs:
                self._add_text_run(para, tr)
        else:
            # 空段落占位
            run = para.add_run("")
            run.font.size = Pt(body["font_size_pt"])

    def _render_bullet_list(self, element: "BulletListElement") -> None:
        doc = self._doc
        assert doc is not None

        body = self._mapper.word_body_style()
        for item in element.items:
            para = doc.add_paragraph(style="List Bullet")
            self._render_list_item_runs(para, item, body)

    def _render_ordered_list(self, element: "OrderedListElement") -> None:
        doc = self._doc
        assert doc is not None

        body = self._mapper.word_body_style()
        for idx, item in enumerate(element.items, start=element.start):
            para = doc.add_paragraph(style="List Number")
            self._render_list_item_runs(para, item, body)

    def _render_table(self, element: "TableElement") -> None:
        doc = self._doc
        assert doc is not None

        style_config = self._mapper.word_table_style()
        body = self._mapper.word_body_style()

        # 表格标题
        if element.title:
            title_para = doc.add_paragraph()
            title_run = title_para.add_run(element.title)
            title_run.bold = True
            title_run.font.size = Pt(body["font_size_pt"])

        num_rows = len(element.rows) + (1 if element.headers else 0)
        num_cols = max(
            len(element.headers) if element.headers else 0,
            max((len(row) for row in element.rows), default=0),
        )
        if num_rows == 0 or num_cols == 0:
            return

        table = doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # 表格样式
        if element.style == "striped":
            table.style = "Table Grid"

        # 表头
        if element.headers:
            for col_idx, header_cells in enumerate(element.headers):
                cell = table.cell(0, col_idx)
                cell.text = ""
                para = cell.paragraphs[0]
                for tr in header_cells:
                    run = para.add_run(tr.text)
                    run.bold = True
                    run.font.name = style_config["header_font"]
                    run.font.size = Pt(style_config["header_size_pt"])
                    run.font.color.rgb = self._hex_to_rgb(style_config["header_fg_hex"])
                # 表头背景色
                self._set_cell_shading(cell, style_config["header_bg_hex"])

        # 数据行
        for row_idx, row in enumerate(element.rows):
            for col_idx, cell_runs in enumerate(row):
                if col_idx >= num_cols:
                    break
                cell = table.cell(row_idx + (1 if element.headers else 0), col_idx)
                cell.text = ""
                para = cell.paragraphs[0]
                for tr in cell_runs:
                    run = para.add_run(tr.text)
                    run.font.name = body["font_name"]
                    run.font.size = Pt(body["font_size_pt"])

                # 交替行背景
                if element.style == "striped" and row_idx % 2 == 1:
                    self._set_cell_shading(cell, "#F7FAFC")

        # 列宽（如果指定）
        if element.col_widths:
            total = sum(element.col_widths)
            for col_idx, width in enumerate(element.col_widths):
                if col_idx < num_cols:
                    for row in table.rows:
                        row.cells[col_idx].width = Inches(6.0 * width / total)

    def _render_chart(self, element: "ChartElement") -> None:
        doc = self._doc
        assert doc is not None

        # 如果有预渲染的图片数据，直接嵌入
        if element.image_bytes:
            self._embed_image_bytes(doc, element.image_bytes, element.title or "图表")
            return

        # 否则尝试用 matplotlib 生成图表
        try:
            image_bytes = self._chart_to_image(element)
            self._embed_image_bytes(doc, image_bytes, element.title or "图表")
        except Exception:
            logger.warning(
                "Failed to render chart as image, falling back to table",
                extra={"chart_id": element.chart_id},
            )
            # fallback: 显示为简单表格
            self._render_chart_fallback(element)

    def _render_image(self, element: "ImageElement") -> None:
        doc = self._doc
        assert doc is not None

        if element.image_data:
            self._embed_image_bytes(
                doc,
                element.image_data,
                element.caption or element.alt_text or "图片",
            )

    def _render_quote(self, element: "QuoteElement") -> None:
        doc = self._doc
        assert doc is not None

        body = self._mapper.word_body_style()

        # 引用块：左边框 + 缩进 + 斜体
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Inches(0.5)
        para.paragraph_format.right_indent = Inches(0.5)

        # 添加左边框效果（通过段落底纹）
        pPr = para._element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "12")
        left.set(qn("w:space"), "8")
        left.set(qn("w:color"), self.tokens.primary_color.lstrip("#"))
        pBdr.append(left)
        pPr.append(pBdr)

        run = para.add_run(element.text)
        run.italic = True
        run.font.size = Pt(body["font_size_pt"])
        run.font.color.rgb = self._hex_to_rgb(self.tokens.text_color)

        # 出处
        if element.attribution:
            attr_para = doc.add_paragraph()
            attr_para.paragraph_format.left_indent = Inches(0.5)
            attr_run = attr_para.add_run(element.attribution)
            attr_run.font.size = Pt(self.tokens.small_size)
            attr_run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

    def _render_callout(self, element: "CalloutElement") -> None:
        doc = self._doc
        assert doc is not None

        style = self._mapper.word_callout_style(element.callout_type)

        # 标题行
        if element.title:
            title_para = doc.add_paragraph()
            title_run = title_para.add_run(element.title)
            title_run.bold = True
            title_run.font.size = Pt(style["font_size_pt"] + 1)
            title_run.font.color.rgb = self._hex_to_rgb(self.tokens.primary_color)

        # 内容段落（带背景色）
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Inches(0.2)
        para.paragraph_format.right_indent = Inches(0.2)
        run = para.add_run(element.text)
        run.font.size = Pt(style["font_size_pt"])
        run.font.name = style["font_name"]

        # 段落底纹（背景色）
        self._set_paragraph_shading(para, style["bg_hex"])

    def _render_key_value(self, element: "KeyValueElement") -> None:
        doc = self._doc
        assert doc is not None

        body = self._mapper.word_body_style()
        columns = element.columns

        # 简单的键值对网格
        for i, (key, value) in enumerate(element.pairs):
            if i % columns == 0:
                para = doc.add_paragraph()
                para.paragraph_format.space_after = Pt(2)

            run = para.add_run(f"{key}: ")
            run.bold = True
            run.font.size = Pt(body["font_size_pt"])

            run = para.add_run(value)
            run.font.size = Pt(body["font_size_pt"])

            if (i + 1) % columns != 0 and i < len(element.pairs) - 1:
                para.add_run("  |  ").font.size = Pt(self.tokens.small_size)

    def _render_divider(self, element: "DividerElement") -> None:
        doc = self._doc
        assert doc is not None

        para = doc.add_paragraph()
        pPr = para._element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "4")
        bottom.set(qn("w:color"), self.tokens.border_color.lstrip("#"))
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _render_speaker_notes(self, element: "SpeakerNotesElement") -> None:
        """Word 中渲染为小型灰色注释文本."""
        doc = self._doc
        assert doc is not None

        para = doc.add_paragraph()
        run = para.add_run(f"[演讲者备注] {element.text}")
        run.font.size = Pt(self.tokens.small_size)
        run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)
        run.italic = True

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _add_text_run(self, para: Any, tr: "TextRun") -> None:
        """将 TextRun 转换为 Word 段落中的 run."""
        run = para.add_run(tr.text)

        if tr.bold:
            run.bold = True
        if tr.italic:
            run.italic = True
        if tr.underline:
            run.underline = True
        if tr.color:
            run.font.color.rgb = self._hex_to_rgb(tr.color)
        if tr.size:
            run.font.size = Pt(tr.size)
        if tr.font:
            run.font.name = tr.font
        if tr.hyperlink:
            self._add_hyperlink(para, tr)

    def _add_hyperlink(self, paragraph: Any, tr: "TextRun") -> None:
        """添加超链接到段落."""
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("w:anchor"), tr.hyperlink or "")
        # 简化处理：直接添加为普通 run（python-docx 超链接支持有限）
        # 实际使用时可通过样式暗示

    def _render_list_item_runs(
        self, para: Any, item: "ListItem", body_style: Dict[str, Any]
    ) -> None:
        """渲染列表项的富文本."""
        if item.runs:
            for tr in item.runs:
                self._add_text_run(para, tr)
        else:
            run = para.add_run("")
            run.font.size = Pt(body_style["font_size_pt"])

        # 不支持子列表渲染（python-docx 限制），记录警告
        if item.sub_items:
            logger.debug("Nested list items skipped in Word rendering")

    def _embed_image_bytes(self, doc: "DocxDocument", image_data: bytes, caption: str) -> None:
        """将图片字节数据嵌入 Word 文档."""
        try:
            image_stream = io.BytesIO(image_data)
            doc.add_picture(image_stream, width=Inches(5.5))

            # 图片说明
            if caption:
                cap_para = doc.add_paragraph()
                cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_run = cap_para.add_run(caption)
                cap_run.italic = True
                cap_run.font.size = Pt(self.tokens.small_size)
                cap_run.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

            doc.add_paragraph()  # 间距
        except Exception as e:
            logger.warning("Failed to embed image", extra={"error": str(e)})

    def _chart_to_image(self, element: "ChartElement") -> bytes:
        """使用 matplotlib 将图表数据渲染为 PNG 图片."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            raise RuntimeError("matplotlib is required for chart rendering")

        palette = self._mapper.chart_colors()

        fig, ax = plt.subplots(figsize=(8, 4))
        chart_type = (
            element.chart_type.value
            if hasattr(element.chart_type, "value")
            else str(element.chart_type)
        )

        labels = element.data_labels or []
        series = element.data_series or []

        for i, s in enumerate(series):
            color = palette[i % len(palette)]
            if chart_type in ("line",):
                ax.plot(labels, s, marker="o", color=color, linewidth=2)
            elif chart_type in ("bar",):
                x = range(len(labels))
                width = 0.8 / max(len(series), 1)
                offset = (i - (len(series) - 1) / 2) * width
                ax.bar([v + offset for v in x], s, width, color=color)
            elif chart_type in ("pie",):
                ax.pie(s, labels=labels, colors=palette, autopct="%1.1f%%")
                break
            elif chart_type in ("area",):
                ax.fill_between(range(len(labels)), s, alpha=0.5, color=color)
                ax.plot(labels, s, color=color, linewidth=1)
            elif chart_type in ("scatter",):
                ax.scatter(labels, s, color=color)

        if element.title:
            ax.set_title(element.title, fontsize=12, fontweight="bold")
        if element.source_note:
            fig.text(0.99, 0.01, element.source_note, ha="right", fontsize=8, color="gray")

        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    def _render_chart_fallback(self, element: "ChartElement") -> None:
        """图表渲染失败时的 fallback：显示为简单数据表."""
        doc = self._doc
        assert doc is not None

        if element.title:
            para = doc.add_paragraph()
            run = para.add_run(f"[图表] {element.title}")
            run.italic = True

        if element.data_labels and element.data_series:
            num_cols = len(element.data_labels) + 1
            num_rows = len(element.data_series) + 1
            table = doc.add_table(rows=num_rows, cols=num_cols)

            header_cells = [""] + list(element.data_labels)
            for i, h in enumerate(header_cells):
                table.cell(0, i).text = h

            for row_idx, series in enumerate(element.data_series):
                table.cell(row_idx + 1, 0).text = f"Series {row_idx + 1}"
                for col_idx, val in enumerate(series):
                    table.cell(row_idx + 1, col_idx + 1).text = str(val)

    def _map_alignment(self, alignment: Any) -> Any:
        """将 HorizontalAlignment 映射为 WD_ALIGN_PARAGRAPH."""
        val = alignment.value if hasattr(alignment, "value") else str(alignment)
        mapping = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
        }
        return mapping.get(val, WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> "RGBColor":
        """Hex → RGBColor 对象."""
        hex_color = hex_color.lstrip("#")
        return RGBColor(
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    @staticmethod
    def _set_cell_shading(cell: Any, hex_color: str) -> None:
        """设置表格单元格背景色."""
        hex_color = hex_color.lstrip("#")
        tcPr = cell._tc.get_or_add_tcPr()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), hex_color)
        shading.set(qn("w:val"), "clear")
        tcPr.append(shading)

    @staticmethod
    def _set_paragraph_shading(para: Any, hex_color: str) -> None:
        """设置段落背景色."""
        hex_color = hex_color.lstrip("#")
        pPr = para._element.get_or_add_pPr()
        shading = OxmlElement("w:shd")
        shading.set(qn("w:fill"), hex_color)
        shading.set(qn("w:val"), "clear")
        pPr.append(shading)
