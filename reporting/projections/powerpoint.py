"""PowerPoint 演示文稿投影 - 将报告输出为 PPTX 格式

Supports both simple PowerPoint generation and template-based generation
with placeholder replacement.
"""
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.contracts import SectionOutput, TableSpec
from core.observability import get_logger

logger = get_logger(__name__)

# Check if python-pptx is available
try:
    import pptx
    from pptx import Presentation
    from pptx.util import Inches, Pt

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False
    Presentation = None


class PowerPointProjection:
    """PowerPoint 演示文稿投影

    Supports both simple PowerPoint generation and template-based generation
    with placeholder replacement.
    """

    def __init__(self):
        self._has_pptx = PPTX_AVAILABLE

    def _check_pptx(self) -> bool:
        """检查 python-pptx 是否可用"""
        return self._has_pptx

    def save(
        self,
        output_path: Path | str,
        title: str,
        sections: List[SectionOutput],
        metadata: Dict[str, Any] | None = None,
    ):
        """保存为 PowerPoint 演示文稿

        Args:
            output_path: Output file path.
            title: Report title.
            sections: List of section outputs.
            metadata: Additional metadata.
        """
        if not self._has_pptx:
            raise ImportError(
                "python-pptx is required for PowerPoint output. "
                "Please install it with: pip install python-pptx"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        prs = Presentation()

        # Title slide
        slide_layout = prs.slide_layouts[0]  # Title slide layout
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = title

        # Metadata on subtitle if available
        if metadata:
            subtitle = slide.placeholders[1]
            subtitle.text = ", ".join([f"{k}: {v}" for k, v in metadata.items()])

        # Content slides
        for section in sections:
            # Section slide
            slide_layout = prs.slide_layouts[1]  # Title and Content
            slide = prs.slides.add_slide(slide_layout)
            slide.shapes.title.text = section.title

            # Content
            content_placeholder = slide.placeholders[1]
            tf = content_placeholder.text_frame
            tf.text = section.content

            # Add warnings if any
            if section.warnings:
                p = tf.add_paragraph()
                p.text = "⚠️ Warnings:"
                p.font.bold = True
                for warning in section.warnings:
                    p = tf.add_paragraph()
                    p.text = f"• {warning}"
                    p.level = 1

        prs.save(str(output_path))
        logger.info(f"Saved PowerPoint to: {output_path}")

    def save_from_template(
        self,
        output_path: Path | str,
        template_path: Path | str,
        sections: List[SectionOutput],
        placeholders: Optional[Dict[str, str]] = None,
        tables: Optional[List[TableSpec]] = None,
        chart_images: Optional[Dict[str, bytes]] = None,
    ):
        """从模板保存 PowerPoint 演示文稿

        Replaces placeholders in a PowerPoint template with content.

        Args:
            output_path: Output file path.
            template_path: Path to PowerPoint template.
            sections: List of section outputs.
            placeholders: Additional placeholder mappings.
            tables: List of table specifications.
            chart_images: Dict of chart ID to image bytes.
        """
        if not self._has_pptx:
            raise ImportError(
                "python-pptx is required for PowerPoint output. "
                "Please install it with: pip install python-pptx"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template_path = Path(template_path)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        prs = Presentation(str(template_path))

        # Build placeholder map
        placeholder_map = dict(placeholders or {})

        # Add section content to placeholder map
        for section in sections:
            placeholder_map[section.key] = section.content

        # Replace placeholders in presentation
        self._replace_placeholders_in_presentation(prs, placeholder_map)

        # Add tables
        if tables:
            self._add_tables_to_presentation(prs, tables)

        # Add chart images
        if chart_images:
            self._add_chart_images_to_presentation(prs, chart_images)

        prs.save(str(output_path))
        logger.info(f"Saved PowerPoint from template to: {output_path}")

    def _replace_placeholders_in_presentation(
        self,
        prs: Any,
        placeholder_map: Dict[str, str],
    ):
        """在演示文稿中替换占位符

        Args:
            prs: PowerPoint Presentation object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        for slide in prs.slides:
            # Replace in shapes
            for shape in slide.shapes:
                if shape.has_text_frame:
                    self._replace_placeholders_in_text_frame(shape.text_frame, placeholder_map)
                if shape.has_table:
                    self._replace_placeholders_in_table(shape.table, placeholder_map)

    def _replace_placeholders_in_text_frame(
        self,
        text_frame: Any,
        placeholder_map: Dict[str, str],
    ):
        """在文本框中替换占位符

        Args:
            text_frame: PowerPoint TextFrame object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        for paragraph in text_frame.paragraphs:
            self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

    def _replace_placeholders_in_paragraph(
        self,
        paragraph: Any,
        placeholder_map: Dict[str, str],
    ):
        """在段落中替换占位符

        Args:
            paragraph: PowerPoint Paragraph object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        original_text = paragraph.text
        if not original_text:
            return

        # Replace placeholders in text
        new_text = original_text
        for placeholder, replacement in placeholder_map.items():
            # Support both {{placeholder}} and {placeholder} formats
            patterns = [
                f"{{{{{placeholder}}}}}",
                f"{{{placeholder}}}",
            ]
            for pattern in patterns:
                if pattern in new_text:
                    new_text = new_text.replace(pattern, replacement)

        # Only update if text changed
        if new_text != original_text:
            # Clear all runs
            for run in paragraph.runs:
                run.text = ""

            # Set new text on first run if available, else add new run
            if paragraph.runs:
                paragraph.runs[0].text = new_text
            else:
                paragraph.add_run().text = new_text

    def _replace_placeholders_in_table(
        self,
        table: Any,
        placeholder_map: Dict[str, str],
    ):
        """在表格中替换占位符

        Args:
            table: PowerPoint Table object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

    def _add_tables_to_presentation(
        self,
        prs: Any,
        tables: List[TableSpec],
    ):
        """向演示文稿添加表格

        Args:
            prs: PowerPoint Presentation object.
            tables: List of table specifications.
        """
        for table_spec in tables:
            # Find placeholder or add new slide
            found = False
            if table_spec.placeholder:
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            text = shape.text_frame.text
                            patterns = [
                                f"{{{{{table_spec.placeholder}}}}}",
                                f"{{{table_spec.placeholder}}}",
                            ]
                            for pattern in patterns:
                                if pattern in text:
                                    # Clear the placeholder
                                    shape.text_frame.text = ""
                                    # Add table at this position
                                    self._add_table_to_slide(slide, table_spec, shape)
                                    found = True
                                    break
                        if found:
                            break
                    if found:
                        break

            if not found:
                # Add new slide with table
                slide_layout = prs.slide_layouts[5]  # Blank slide
                slide = prs.slides.add_slide(slide_layout)

                # Add title
                title_box = slide.shapes.title
                if title_box:
                    title_box.text = table_spec.title
                else:
                    # Add title shape manually
                    left = Inches(0.5)
                    top = Inches(0.3)
                    width = Inches(9)
                    height = Inches(0.8)
                    title_shape = slide.shapes.add_textbox(left, top, width, height)
                    title_shape.text_frame.text = table_spec.title
                    title_shape.text_frame.paragraphs[0].font.size = Pt(32)
                    title_shape.text_frame.paragraphs[0].font.bold = True

                # Add table
                self._add_table_to_slide(slide, table_spec)

    def _add_table_to_slide(
        self,
        slide: Any,
        table_spec: TableSpec,
        anchor_shape: Any = None,
    ):
        """向幻灯片添加表格

        Args:
            slide: PowerPoint Slide object.
            table_spec: Table specification.
            anchor_shape: Optional shape to anchor position.
        """
        if anchor_shape:
            left = anchor_shape.left
            top = anchor_shape.top
            width = anchor_shape.width
            height = anchor_shape.height
        else:
            left = Inches(0.5)
            top = Inches(1.5)
            width = Inches(9)
            height = Inches(4)

        num_rows = len(table_spec.rows) + 1  # +1 for header
        num_cols = (
            len(table_spec.headers)
            if table_spec.headers
            else (len(table_spec.rows[0]) if table_spec.rows else 1)
        )

        table = slide.shapes.add_table(num_rows, num_cols, left, top, width, height).table

        # Add header
        if table_spec.headers:
            for idx, header in enumerate(table_spec.headers):
                cell = table.cell(0, idx)
                cell.text = header
                cell.fill.solid()
                cell.fill.fore_color.rgb = pptx.dml.color.RGBColor(200, 200, 200)
                for paragraph in cell.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.bold = True

        # Add data
        for row_idx, row_data in enumerate(table_spec.rows):
            for col_idx, cell_data in enumerate(row_data):
                table.cell(row_idx + 1, col_idx).text = str(cell_data)

    def _add_chart_images_to_presentation(
        self,
        prs: Any,
        chart_images: Dict[str, bytes],
    ):
        """向演示文稿添加图表图片

        Args:
            prs: PowerPoint Presentation object.
            chart_images: Dict of chart ID to image bytes.
        """
        for chart_id, image_bytes in chart_images.items():
            # Look for placeholder
            placeholder_found = False
            patterns = [f"{{{{{chart_id}}}}}", f"{{{chart_id}}}", chart_id]

            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        text = shape.text_frame.text
                        for pattern in patterns:
                            if pattern in text:
                                # Replace placeholder with image
                                left = shape.left
                                top = shape.top
                                width = Inches(4.5)
                                height = Inches(3.0)

                                # Clear placeholder
                                shape.text_frame.text = ""

                                # Add picture
                                image_stream = BytesIO(image_bytes)
                                slide.shapes.add_picture(image_stream, left, top, width, height)
                                placeholder_found = True
                                break
                    if placeholder_found:
                        break
                if placeholder_found:
                    break

            if not placeholder_found:
                # Add new slide with image
                slide_layout = prs.slide_layouts[5]  # Blank slide
                slide = prs.slides.add_slide(slide_layout)

                left = Inches(1.0)
                top = Inches(1.0)
                width = Inches(8.0)
                height = Inches(5.0)

                image_stream = BytesIO(image_bytes)
                slide.shapes.add_picture(image_stream, left, top, width, height)
