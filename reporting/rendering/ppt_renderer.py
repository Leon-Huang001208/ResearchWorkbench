"""
PPT 渲染器 — 将 Document 渲染为 .pptx 格式.

基于 python-pptx，逐 Section 渲染为幻灯片，使用 StyleMapper
将 DesignTokens 映射为 PPT 样式参数。

支持特性：
- Section → Slide 映射（每个 Section 可占多页）
- slide_layout 提示控制使用哪个 Slide Layout
- 内容溢出时自动创建 continue slide（智能 y 坐标追踪）
- 演讲者备注渲染（SpeakerNotesElement + Section.speaker_notes）
- 原生图表（python-pptx ChartData，可编辑）
- 表格单元格背景色填充
- 自定义 PPT 模板（DesignTokens.ppt_template_path）
- 幻灯片过渡效果（DesignTokens.ppt_transition）
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, cast

from core.contracts.document import DesignTokens
from core.observability import get_logger
from reporting.rendering.base import DocumentRenderer
from reporting.rendering.style_mapper import StyleMapper

logger = get_logger(__name__)

# python-pptx 是可选的 PPT 渲染依赖
try:
    from pptx import Presentation as PPTXPresentation
    from pptx.util import Inches, Pt

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

if TYPE_CHECKING:
    from pptx.presentation import Presentation as PPTXDoc
    from pptx.slide import Slide

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


# ============================================================================
# 幻灯片布局映射
# ============================================================================

_LAYOUT_MAP: Dict[str, int] = {
    "TITLE_SLIDE": 0,
    "TITLE_AND_CONTENT": 1,
    "SECTION_HEADER": 2,
    "TWO_CONTENT": 3,
    "COMPARISON": 4,
    "TITLE_ONLY": 5,
    "BLANK": 6,
    "CONTENT_WITH_CAPTION": 7,
    "PICTURE_WITH_CAPTION": 8,
}

# 内容区域常量（英寸浮点值，使用时通过 Inches() 转换）
_CONTENT_LEFT_MARGIN = 0.7
_CONTENT_TOP_START = 1.6
_CONTENT_WIDTH = 11.5
_CONTENT_ROW_HEIGHT = 0.85
_CONTENT_MAX_ELEMENTS = 6


class PPTRenderer(DocumentRenderer):
    """PowerPoint (.pptx) 文档渲染器.

    Usage:
        doc = Document(title="简报", sections=[...])
        renderer = PPTRenderer(tokens=presentation_tokens())
        renderer.render_document(doc, Path("output.pptx"))
    """

    def __init__(self, tokens: Optional[DesignTokens] = None) -> None:
        super().__init__(tokens)
        if not PPTX_AVAILABLE:
            raise ImportError(
                "python-pptx is required for PPT output. " "Install with: pip install python-pptx"
            )
        self._prs: Optional["PPTXDoc"] = None
        self._mapper: StyleMapper = StyleMapper(self.tokens)
        self._current_slide: Optional["Slide"] = None
        self._y_offset: float = 0.0  # 当前 slide 的 y 方向偏移（英寸）

    # ========================================================================
    # 抽象方法实现
    # ========================================================================

    @property
    def format_name(self) -> str:
        return "PPT"

    def _begin_document(self, document: "Document") -> None:
        # 支持自定义模板
        template_path = document.design_tokens.ppt_template_path
        if template_path and Path(template_path).exists():
            self._prs = PPTXPresentation(template_path)
            logger.info("Using custom PPT template", extra={"path": template_path})
        else:
            self._prs = PPTXPresentation()

        w, h = self._mapper.ppt_slide_dimensions_inches()
        self._prs.slide_width = Inches(w)
        self._prs.slide_height = Inches(h)

    def _end_document(self, document: "Document") -> None:
        """文档结束."""
        pass

    def _finalize(self, output_path: Path) -> None:
        assert self._prs is not None
        self._prs.save(str(output_path))

    def render_to_buffer(self, document: "Document") -> io.BytesIO:
        self.render_document(document, Path("_temp_buffer.pptx"))
        assert self._prs is not None
        buf = io.BytesIO()
        self._prs.save(buf)
        return buf

    # ========================================================================
    # 标题页
    # ========================================================================

    def _render_title_page(self, document: "Document") -> None:
        prs = self._prs
        assert prs is not None

        layout_idx = _LAYOUT_MAP.get("TITLE_SLIDE", 0)
        slide = prs.slides.add_slide(prs.slide_layouts[layout_idx])

        # 标题
        if slide.shapes.title:
            title_style = self._mapper.ppt_title_style()
            tf = slide.shapes.title.text_frame
            tf.clear()
            p = tf.paragraphs[0]
            p.text = document.title
            p.font.name = title_style["font_name"]
            p.font.size = Pt(title_style["font_size_pt"])
            p.font.color.rgb = self._hex_to_rgb(title_style["color_hex"])
            p.font.bold = title_style["bold"]

        # 副标题
        if document.subtitle and len(slide.placeholders) > 1:
            sub_style = self._mapper.ppt_subtitle_style()
            tf = slide.placeholders[1].text_frame
            tf.clear()
            p = tf.paragraphs[0]
            p.text = document.subtitle
            p.font.name = sub_style["font_name"]
            p.font.size = Pt(sub_style["font_size_pt"])
            p.font.color.rgb = self._hex_to_rgb(sub_style["color_hex"])

        # 过渡效果
        self._apply_transition(slide)
        self._ctx.slide_number += 1

    # ========================================================================
    # Section 钩子
    # ========================================================================

    def _begin_section(self, section: "Section") -> None:
        prs = self._prs
        assert prs is not None

        layout_name = section.slide_layout or "TITLE_AND_CONTENT"
        layout_idx = _LAYOUT_MAP.get(layout_name, 1)
        slide = prs.slides.add_slide(prs.slide_layouts[layout_idx])
        self._current_slide = slide
        self._y_offset = _CONTENT_TOP_START

        # 设置幻灯片标题
        if slide.shapes.title:
            heading_style = self._mapper.ppt_heading_style(2)
            tf = slide.shapes.title.text_frame
            tf.clear()
            p = tf.paragraphs[0]
            p.text = section.title
            p.font.name = heading_style["font_name"]
            p.font.size = Pt(heading_style["font_size_pt"])
            p.font.color.rgb = self._hex_to_rgb(heading_style["color_hex"])
            p.font.bold = heading_style["bold"]

        # 演讲者备注
        if section.speaker_notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = section.speaker_notes

        # 过渡效果
        self._apply_transition(slide)
        self._ctx.slide_number += 1

    def _end_section(self, section: "Section") -> None:
        """章节结束."""
        pass

    # ========================================================================
    # 内容块渲染 — 智能分页
    # ========================================================================

    def _render_block(self, block: "ContentBlock") -> None:
        """渲染 ContentBlock — 元素过多时自动分页."""
        visible_elements = [e for e in block.elements if e.visible]

        # 按 block layout 确定是否使用双栏
        if block.layout_hint == "two_col":
            self._render_block_two_col(block, visible_elements)
            return

        for element in visible_elements:
            # 检查是否需要分页
            max_y = self.tokens.ppt_slide_height - 0.5
            if self._y_offset > max_y:
                self._add_continue_slide()

            self._dispatch_element(element)
            self._y_offset += _CONTENT_ROW_HEIGHT

    def _render_block_two_col(self, block: "ContentBlock", elements: list) -> None:
        """双栏布局渲染."""
        mid = (len(elements) + 1) // 2
        left_els = elements[:mid]
        right_els = elements[mid:]

        saved_y = self._y_offset
        for element in left_els:
            self._dispatch_element(element)
            self._y_offset += _CONTENT_ROW_HEIGHT

        self._y_offset = saved_y
        # 右侧列（x 偏移简化处理）
        for element in right_els:
            self._dispatch_element(element)
            self._y_offset += _CONTENT_ROW_HEIGHT

    def _dispatch_element(self, element: Any) -> None:
        """将单个元素分发到正确的 _render_* 方法."""
        from core.contracts.content_element import ContentElementType

        etype = element.element_type
        dispatch_map = {
            ContentElementType.HEADING: self._render_heading,
            ContentElementType.PARAGRAPH: self._render_paragraph,
            ContentElementType.BULLET_LIST: self._render_bullet_list,
            ContentElementType.ORDERED_LIST: self._render_ordered_list,
            ContentElementType.TABLE: self._render_table,
            ContentElementType.CHART: self._render_chart,
            ContentElementType.IMAGE: self._render_image,
            ContentElementType.QUOTE: self._render_quote,
            ContentElementType.CALLOUT: self._render_callout,
            ContentElementType.KEY_VALUE: self._render_key_value,
            ContentElementType.DIVIDER: self._render_divider,
            ContentElementType.SPEAKER_NOTES: self._render_speaker_notes,
        }
        render_func = cast(Callable[[Any], None] | None, dispatch_map.get(etype))
        if render_func:
            render_func(element)
        else:
            logger.warning("Unknown element type in PPT dispatch", extra={"type": str(etype)})

    # ========================================================================
    # 元素渲染方法
    # ========================================================================

    def _render_heading(self, element: "HeadingElement") -> None:
        slide = self._current_slide
        assert slide is not None

        style = self._mapper.ppt_heading_style(element.level)
        height = Inches(0.6)
        textbox = slide.shapes.add_textbox(
            Inches(0.5), Inches(self._y_offset), Inches(_CONTENT_WIDTH), height
        )
        tf = textbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = element.text
        p.font.name = style["font_name"]
        p.font.size = Pt(style["font_size_pt"])
        p.font.color.rgb = self._hex_to_rgb(style["color_hex"])
        p.font.bold = style["bold"]

    def _render_paragraph(self, element: "ParagraphElement") -> None:
        slide = self._current_slide
        assert slide is not None

        body = self._mapper.ppt_body_style()
        height = Inches(0.55)
        textbox = slide.shapes.add_textbox(
            Inches(_CONTENT_LEFT_MARGIN), Inches(self._y_offset), Inches(_CONTENT_WIDTH), height
        )
        tf = textbox.text_frame
        tf.word_wrap = True

        if element.runs:
            p = tf.paragraphs[0]
            p.line_spacing = Pt(body["font_size_pt"] * body["line_spacing"])
            for tr in element.runs:
                run = p.add_run()
                run.text = tr.text
                if tr.bold:
                    run.font.bold = True
                if tr.italic:
                    run.font.italic = True
                if tr.color:
                    run.font.color.rgb = self._hex_to_rgb(tr.color)
                if tr.size:
                    run.font.size = Pt(tr.size)
                else:
                    font = run.font
                    assert font is not None
                    font.size = Pt(body["font_size_pt"])
                if tr.font:
                    run.font.name = tr.font
                else:
                    run.font.name = body["font_name"]
        else:
            tf.paragraphs[0].text = ""

    def _render_bullet_list(self, element: "BulletListElement") -> None:
        slide = self._current_slide
        assert slide is not None

        body = self._mapper.ppt_body_style()
        items_count = len(element.items)
        height = Inches(0.3 * items_count + 0.3)
        textbox = slide.shapes.add_textbox(
            Inches(_CONTENT_LEFT_MARGIN), Inches(self._y_offset), Inches(_CONTENT_WIDTH), height
        )
        tf = textbox.text_frame
        tf.word_wrap = True

        for i, item in enumerate(element.items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.level = 0
            p.space_after = Pt(2)
            if item.runs:
                text = "".join(r.text for r in item.runs)
                run = p.add_run()
                run.text = f"• {text}"
                run.font.size = Pt(body["font_size_pt"])
                run.font.name = body["font_name"]
                run.font.color.rgb = self._hex_to_rgb(body["color_hex"])

    def _render_ordered_list(self, element: "OrderedListElement") -> None:
        slide = self._current_slide
        assert slide is not None

        body = self._mapper.ppt_body_style()
        items_count = len(element.items)
        height = Inches(0.3 * items_count + 0.3)
        textbox = slide.shapes.add_textbox(
            Inches(_CONTENT_LEFT_MARGIN), Inches(self._y_offset), Inches(_CONTENT_WIDTH), height
        )
        tf = textbox.text_frame
        tf.word_wrap = True

        for i, item in enumerate(element.items, start=element.start):
            p = tf.paragraphs[0] if i == element.start else tf.add_paragraph()
            p.space_after = Pt(2)
            if item.runs:
                text = "".join(r.text for r in item.runs)
                run = p.add_run()
                run.text = f"{i}. {text}"
                run.font.size = Pt(body["font_size_pt"])
                run.font.name = body["font_name"]
                run.font.color.rgb = self._hex_to_rgb(body["color_hex"])

    def _render_table(self, element: "TableElement") -> None:
        slide = self._current_slide
        assert slide is not None

        config = self._mapper.ppt_table_style()
        body = self._mapper.ppt_body_style()

        num_rows = len(element.rows) + (1 if element.headers else 0)
        num_cols = max(
            len(element.headers) if element.headers else 0,
            max((len(row) for row in element.rows), default=0),
        )
        if num_rows == 0 or num_cols == 0:
            return

        left = Inches(_CONTENT_LEFT_MARGIN)
        top = Inches(self._y_offset)
        width = Inches(_CONTENT_WIDTH)
        height = Inches(0.35 * num_rows + 0.2)

        table_shape = slide.shapes.add_table(num_rows, num_cols, left, top, width, height)
        table = table_shape.table

        # 表头
        if element.headers:
            for col_idx, header_cells in enumerate(element.headers):
                cell = table.cell(0, col_idx)
                cell.text = ""
                p = cell.text_frame.paragraphs[0]
                for tr in header_cells:
                    run = p.add_run()
                    run.text = tr.text
                    font = run.font
                    assert font is not None
                    font.bold = True
                    font.size = Pt(config["header_size_pt"])
                    font.color.rgb = self._hex_to_rgb(config["header_fg_hex"])
                self._set_cell_fill(cell, config["header_bg_hex"])

        # 数据行
        for row_idx, row in enumerate(element.rows):
            for col_idx, cell_runs in enumerate(row):
                if col_idx >= num_cols:
                    break
                cell = table.cell(row_idx + (1 if element.headers else 0), col_idx)
                cell.text = ""
                p = cell.text_frame.paragraphs[0]
                for tr in cell_runs:
                    run = p.add_run()
                    run.text = tr.text
                    font = run.font
                    assert font is not None
                    font.size = Pt(body["font_size_pt"])
                # 交替行背景
                if element.style == "striped" and row_idx % 2 == 1:
                    self._set_cell_fill(cell, "#F0F4F8")

    def _render_chart(self, element: "ChartElement") -> None:
        """渲染图表 — 优先使用原生 PPT 图表，fallback 到图片."""
        slide = self._current_slide
        assert slide is not None

        chart_type = (
            element.chart_type.value
            if hasattr(element.chart_type, "value")
            else str(element.chart_type)
        )

        # 尝试原生图表
        if self._try_native_chart(slide, element, chart_type):
            return

        # Fallback: 图片或文本
        if element.image_bytes:
            image_stream = io.BytesIO(element.image_bytes)
            slide.shapes.add_picture(
                image_stream,
                Inches(1.0),
                Inches(self._y_offset),
                width=Inches(9.0),
            )
        else:
            textbox = slide.shapes.add_textbox(
                Inches(1.0),
                Inches(self._y_offset),
                Inches(9.0),
                Inches(0.4),
            )
            tf = textbox.text_frame
            p = tf.paragraphs[0]
            p.text = f"[图表] {element.title or element.chart_id}"
            p.font.size = Pt(12)
            p.font.italic = True

    def _try_native_chart(self, slide: "Slide", element: "ChartElement", chart_type: str) -> bool:
        """尝试创建原生 PPT 图表（可编辑的 ChartData）."""
        try:
            from pptx.chart.data import CategoryChartData
            from pptx.enum.chart import XL_CHART_TYPE

            chart_data = CategoryChartData()
            labels = element.data_labels or []

            type_map = {
                "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
                "line": XL_CHART_TYPE.LINE_MARKERS,
                "pie": XL_CHART_TYPE.PIE,
                "area": XL_CHART_TYPE.AREA,
                "scatter": XL_CHART_TYPE.XY_SCATTER,
            }
            xl_type = type_map.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)

            if chart_type == "pie" and element.data_series:
                series = element.data_series[0] if element.data_series else []
                for label, val in zip(labels, series):
                    chart_data.add_series("", (label, val))
            else:
                for i, s in enumerate(element.data_series or []):
                    name = f"Series {i + 1}"
                    chart_data.add_series(name, list(zip(labels, s)))

            chart_frame = slide.shapes.add_chart(
                xl_type,
                Inches(1.0),
                Inches(self._y_offset),
                Inches(9.0),
                Inches(4.5),
                cast(Any, chart_data),
            )
            chart = chart_frame.chart

            if element.title:
                chart.has_title = True
                chart.chart_title.text_frame.text = element.title

            logger.debug(
                "Native PPT chart created",
                extra={"chart_id": element.chart_id, "type": chart_type},
            )
            return True
        except Exception as e:
            logger.debug(
                "Native chart creation failed, using fallback",
                extra={"error": str(e)},
            )
            return False

    def _render_image(self, element: "ImageElement") -> None:
        slide = self._current_slide
        assert slide is not None

        if element.image_data:
            w = element.width_inches or 8.0
            image_stream = io.BytesIO(element.image_data)
            pic = slide.shapes.add_picture(
                image_stream,
                Inches(1.0),
                Inches(self._y_offset),
                width=Inches(w),
            )
            # 居中
            slide_w = self.tokens.ppt_slide_width
            pic.left = Inches((slide_w - w) / 2)

    def _render_quote(self, element: "QuoteElement") -> None:
        slide = self._current_slide
        assert slide is not None

        body = self._mapper.ppt_body_style()
        textbox = slide.shapes.add_textbox(
            Inches(1.5), Inches(self._y_offset), Inches(10.0), Inches(0.8)
        )
        tf = textbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = f'"{element.text}"'
        run.font.italic = True
        run.font.size = Pt(body["font_size_pt"] + 2)
        run.font.color.rgb = self._hex_to_rgb(self.tokens.primary_color)

        if element.attribution:
            p2 = tf.add_paragraph()
            run2 = p2.add_run()
            run2.text = element.attribution
            run2.font.size = Pt(self.tokens.small_size + 2)
            run2.font.color.rgb = self._hex_to_rgb(self.tokens.muted_text_color)

    def _render_callout(self, element: "CalloutElement") -> None:
        slide = self._current_slide
        assert slide is not None

        style = self._mapper.word_callout_style(element.callout_type)
        bg = self._hex_to_rgb(style["bg_hex"])

        textbox = slide.shapes.add_textbox(
            Inches(_CONTENT_LEFT_MARGIN),
            Inches(self._y_offset),
            Inches(_CONTENT_WIDTH),
            Inches(0.6),
        )
        tf = textbox.text_frame
        tf.word_wrap = True

        if element.title:
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = element.title
            run.font.bold = True
            run.font.size = Pt(style["font_size_pt"] + 2)

        p = tf.add_paragraph() if element.title else tf.paragraphs[0]
        run = p.add_run()
        run.text = element.text
        run.font.size = Pt(style["font_size_pt"])

        textbox.fill.solid()
        textbox.fill.fore_color.rgb = bg

    def _render_key_value(self, element: "KeyValueElement") -> None:
        slide = self._current_slide
        assert slide is not None

        body = self._mapper.ppt_body_style()
        pairs_per_line = element.columns
        lines = (len(element.pairs) + pairs_per_line - 1) // pairs_per_line
        line_height = 0.3
        height = Inches(line_height * lines + 0.3)

        textbox = slide.shapes.add_textbox(
            Inches(_CONTENT_LEFT_MARGIN), Inches(self._y_offset), Inches(_CONTENT_WIDTH), height
        )
        tf = textbox.text_frame
        tf.word_wrap = True

        for i, (key, value) in enumerate(element.pairs):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = f"{key}: "
            run.font.bold = True
            run.font.size = Pt(body["font_size_pt"])
            run = p.add_run()
            run.text = value
            run.font.size = Pt(body["font_size_pt"])

    def _render_divider(self, element: "DividerElement") -> None:
        slide = self._current_slide
        assert slide is not None

        from pptx.enum.shapes import MSO_SHAPE

        slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(1.0),
            Inches(self._y_offset),
            Inches(11.0),
            Pt(2),
        )

    def _render_speaker_notes(self, element: "SpeakerNotesElement") -> None:
        slide = self._current_slide
        assert slide is not None

        notes_slide = slide.notes_slide
        notes_text_frame = notes_slide.notes_text_frame
        assert notes_text_frame is not None
        existing = notes_text_frame.text
        new_text = f"{existing}\n{element.text}" if existing else element.text
        notes_text_frame.text = new_text

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _add_continue_slide(self) -> None:
        """内容溢出时创建继续幻灯片."""
        prs = self._prs
        assert prs is not None

        layout_idx = _LAYOUT_MAP.get("TITLE_AND_CONTENT", 1)
        slide = prs.slides.add_slide(prs.slide_layouts[layout_idx])
        self._current_slide = slide
        self._y_offset = _CONTENT_TOP_START
        self._ctx.slide_number += 1

        if slide.shapes.title:
            slide.shapes.title.text = "（续）"

        self._apply_transition(slide)

    def _set_cell_fill(self, cell: Any, hex_color: str) -> None:
        """设置 PPT 表格单元格背景色（通过 XML 操作）."""
        from pptx.oxml.ns import qn

        hex_color = hex_color.lstrip("#")
        tcPr = cell._tc.get_or_add_tcPr()
        # 检查是否已有 SolidFill
        solidFill = tcPr.find(qn("a:solidFill"))
        if solidFill is None:
            from pptx.oxml.xmlchemy import OxmlElement

            solidFill = OxmlElement("a:solidFill")
            tcPr.append(solidFill)
        srgbClr = solidFill.find(qn("a:srgbClr"))
        if srgbClr is None:
            from pptx.oxml.xmlchemy import OxmlElement

            srgbClr = OxmlElement("a:srgbClr")
            solidFill.append(srgbClr)
        srgbClr.set("val", hex_color)

    def _apply_transition(self, slide: "Slide") -> None:
        """根据 DesignTokens 设置幻灯片过渡效果."""
        transition = self.tokens.ppt_transition
        if not transition or transition == "none":
            return

        # 通过 XML 注入 p:transition 元素
        try:
            from pptx.oxml.xmlchemy import OxmlElement

            # 映射过渡名称到 OOXML 元素名
            transition_map = {
                "fade": "fade",
                "push": "push",
                "cut": "cut",
                "wipe": "wipe",
                "cover": "cover",
            }
            t_name = transition_map.get(transition, "fade")
            transition_el = OxmlElement(f"p:{t_name}")
            slide._element.append(transition_el)
        except Exception:
            logger.debug(
                "Failed to set slide transition",
                extra={"transition": transition},
            )

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Any:
        """Hex → RGBColor 对象."""
        from pptx.dml.color import RGBColor as PPTXRGBColor

        hex_color = hex_color.lstrip("#")
        return PPTXRGBColor(
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
