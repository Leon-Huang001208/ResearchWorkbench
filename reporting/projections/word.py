"""Word 文档投影 - 将报告输出为 Word 格式.

Supports both simple Word generation and template-based generation
with placeholder replacement.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import docx as _docx_mod  # noqa: F401 – re-exported on demand
except ImportError:
    _docx_mod = None  # type: ignore[assignment]

from core.contracts import SectionOutput, TableSpec
from core.observability import get_logger

logger = get_logger(__name__)


class WordProjection:
    """Word 报告投影.

    Supports both simple Word generation and template-based generation
    with placeholder replacement.
    """

    def __init__(self):
        self._has_docx = self._check_docx()

    def _check_docx(self) -> bool:
        """检查 python-docx 是否可用."""
        return _docx_mod is not None

    def save(
        self,
        output_path: Path | str,
        title: str,
        sections: list[SectionOutput],
        metadata: dict[str, Any] | None = None,
    ):
        """保存为 Word 文档.

        Args:
            output_path: Output file path.
            title: Report title.
            sections: List of section outputs.
            metadata: Additional metadata.
        """
        if not self._has_docx:
            raise ImportError(
                "python-docx is required for Word output. "
                "Please install it with: pip install python-docx"
            )

        from docx import Document
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        from docx.shared import Pt

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = Document()

        # 标题
        title_para = doc.add_heading(title, level=0)
        title_para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # 元数据
        if metadata:
            info_para = doc.add_paragraph()
            for key, value in metadata.items():
                run = info_para.add_run(f"{key}: {value}\n")
                run.font.size = Pt(10)
                run.font.italic = True

        # 生成时间
        time_para = doc.add_paragraph()
        time_run = time_para.add_run(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        time_run.font.size = Pt(9)
        time_run.font.italic = True

        doc.add_paragraph()

        # 段落内容
        for section in sections:
            # 段落标题
            doc.add_heading(section.key.replace("_", " ").title(), level=2)

            # 段落内容
            content_para = doc.add_paragraph(section.content)
            content_para.paragraph_format.line_spacing = 1.5

            # 证据引用
            if section.evidence_refs:
                ref_para = doc.add_paragraph()
                ref_run = ref_para.add_run("参考文献:")
                ref_run.bold = True
                for ref in section.evidence_refs:
                    doc.add_paragraph(f"[{ref}] 来源待补充", style="List Bullet")

            # 警告
            if section.warnings:
                warning_para = doc.add_paragraph()
                warning_run = warning_para.add_run("⚠️ 警告:")
                warning_run.bold = True
                from docx.shared import RGBColor

                warning_run.font.color.rgb = RGBColor(255, 0, 0)
                for warning in section.warnings:
                    doc.add_paragraph(warning, style="List Bullet")

            doc.add_paragraph()

        doc.save(str(output_path))
        logger.info(f"Saved Word report to: {output_path}")

    def save_from_template(
        self,
        output_path: Path | str,
        template_path: Path | str,
        sections: List[SectionOutput],
        placeholders: Optional[Dict[str, str]] = None,
        tables: Optional[List[TableSpec]] = None,
        chart_images: Optional[Dict[str, bytes]] = None,
    ):
        """从模板保存 Word 文档.

        Replaces placeholders in a Word template with content.

        Args:
            output_path: Output file path.
            template_path: Path to Word template.
            sections: List of section outputs.
            placeholders: Additional placeholder mappings.
            tables: List of table specifications.
            chart_images: Dict of chart ID to image bytes.
        """
        if not self._has_docx:
            raise ImportError(
                "python-docx is required for Word output. "
                "Please install it with: pip install python-docx"
            )

        from docx import Document

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        template_path = Path(template_path)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        doc = Document(str(template_path))

        # Build placeholder map
        placeholder_map = dict(placeholders or {})

        # Add section content to placeholder map
        for section in sections:
            placeholder_map[section.key] = section.content
            if section.placeholder:
                placeholder_map[section.placeholder] = section.content

        # Replace placeholders in paragraphs
        self._replace_placeholders_in_document(doc, placeholder_map)

        # Add tables
        if tables:
            self._add_tables_to_document(doc, tables)

        # Add chart images
        if chart_images:
            self._add_chart_images_to_document(doc, chart_images)

        doc.save(str(output_path))
        logger.info(f"Saved Word report from template to: {output_path}")

    def _replace_placeholders_in_document(
        self,
        doc: Any,
        placeholder_map: Dict[str, str],
    ):
        """在文档中替换占位符.

        Args:
            doc: Word Document object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        # Replace in paragraphs
        for paragraph in doc.paragraphs:
            self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

        # Replace in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

        # Replace in headers and footers
        for section in doc.sections:
            header = section.header
            for paragraph in header.paragraphs:
                self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

            footer = section.footer
            for paragraph in footer.paragraphs:
                self._replace_placeholders_in_paragraph(paragraph, placeholder_map)

    def _replace_placeholders_in_paragraph(
        self,
        paragraph: Any,
        placeholder_map: Dict[str, str],
    ):
        """在段落中替换占位符.

        Args:
            paragraph: Word Paragraph object.
            placeholder_map: Mapping of placeholder to replacement text.
        """
        for placeholder, replacement in placeholder_map.items():
            # Support both {{placeholder}} and placeholder formats
            patterns = [
                f"{{{{{placeholder}}}}}",
                f"{{{placeholder}}}",
                placeholder,
            ]

            for pattern in patterns:
                if pattern in paragraph.text:
                    # Simple replacement - replace entire text
                    if paragraph.text.strip() == pattern.strip():
                        # Clear existing runs and add new one
                        for run in paragraph.runs:
                            run.clear()
                        if paragraph.runs:
                            paragraph.runs[0].text = replacement
                        else:
                            paragraph.add_run(replacement)
                    else:
                        # Replace within text
                        full_text = paragraph.text
                        new_text = full_text.replace(pattern, replacement)
                        if new_text != full_text:
                            # Recreate the paragraph
                            runs = list(paragraph.runs)
                            # Save formatting from first run
                            first_run = runs[0] if runs else None

                            # Clear existing runs
                            for run in runs:
                                run.clear()

                            # Add new text with saved formatting
                            if paragraph.runs:
                                paragraph.runs[0].text = new_text
                            else:
                                new_run = paragraph.add_run(new_text)
                                if first_run:
                                    new_run.bold = first_run.bold
                                    new_run.italic = first_run.italic
                                    new_run.underline = first_run.underline
                                    if first_run.font.size:
                                        new_run.font.size = first_run.font.size
                                    if first_run.font.color and first_run.font.color.rgb:
                                        new_run.font.color.rgb = first_run.font.color.rgb

    def _add_tables_to_document(
        self,
        doc: Any,
        tables: List[TableSpec],
    ):
        """向文档添加表格.

        Args:
            doc: Word Document object.
            tables: List of table specifications.
        """
        for table_spec in tables:
            # Find placeholder or add at end
            if table_spec.placeholder:
                inserted = self._insert_table_at_placeholder(doc, table_spec)
                if inserted:
                    continue

            # Add at end as fallback
            doc.add_heading(table_spec.title, level=3)

            # Create table
            num_rows = len(table_spec.rows) + 1  # +1 for header
            num_cols = (
                len(table_spec.headers)
                if table_spec.headers
                else (len(table_spec.rows[0]) if table_spec.rows else 1)
            )

            table = doc.add_table(rows=num_rows, cols=num_cols)
            table.style = "Table Grid"

            # Add header
            if table_spec.headers:
                for idx, header in enumerate(table_spec.headers):
                    table.rows[0].cells[idx].text = header

            # Add data
            for row_idx, row_data in enumerate(table_spec.rows):
                for col_idx, cell_data in enumerate(row_data):
                    table.rows[row_idx + 1].cells[col_idx].text = str(cell_data)

            doc.add_paragraph()

    def _insert_table_at_placeholder(
        self,
        doc: Any,
        table_spec: TableSpec,
    ) -> bool:
        """在占位符处插入表格.

        Args:
            doc: Word Document object.
            table_spec: Table specification.

        Returns:
            True if inserted successfully.
        """
        if not table_spec.placeholder:
            return False

        placeholder = table_spec.placeholder
        patterns = [f"{{{{{placeholder}}}}}", f"{{{placeholder}}}", placeholder]

        for para_idx, paragraph in enumerate(doc.paragraphs):
            for pattern in patterns:
                if pattern in paragraph.text:
                    # Found placeholder
                    paragraph.clear()

                    # Add table after this paragraph
                    # First find the paragraph index
                    paragraphs = list(doc.paragraphs)
                    for idx, p in enumerate(paragraphs):
                        if p == paragraph:
                            # Create table
                            num_rows = len(table_spec.rows) + 1
                            num_cols = (
                                len(table_spec.headers)
                                if table_spec.headers
                                else (len(table_spec.rows[0]) if table_spec.rows else 1)
                            )

                            # Insert table at correct position
                            table = doc.add_table(rows=num_rows, cols=num_cols)
                            table.style = "Table Grid"

                            # Add header
                            if table_spec.headers:
                                for h_idx, header in enumerate(table_spec.headers):
                                    table.rows[0].cells[h_idx].text = header

                            # Add data
                            for row_idx, row_data in enumerate(table_spec.rows):
                                for col_idx, cell_data in enumerate(row_data):
                                    table.rows[row_idx + 1].cells[col_idx].text = str(cell_data)

                            return True

        return False

    def _add_chart_images_to_document(
        self,
        doc: Any,
        chart_images: Dict[str, bytes],
    ):
        """向文档添加图表图片.

        Args:
            doc: Word Document object.
            chart_images: Dict of chart ID to image bytes.
        """
        from io import BytesIO
        from docx.shared import Inches

        for chart_id, image_bytes in chart_images.items():
            # Look for placeholder
            placeholder_found = False
            patterns = [f"{{{{{chart_id}}}}}", f"{{{chart_id}}}", chart_id]

            for paragraph in doc.paragraphs:
                for pattern in patterns:
                    if pattern in paragraph.text:
                        # Replace placeholder with image
                        paragraph.clear()
                        image_stream = BytesIO(image_bytes)
                        run = paragraph.add_run()
                        run.add_picture(image_stream, width=Inches(4.5))
                        placeholder_found = True
                        break
                if placeholder_found:
                    break

            if not placeholder_found:
                # Add at end
                doc.add_paragraph(f"Chart: {chart_id}")
                image_stream = BytesIO(image_bytes)
                doc.add_picture(image_stream, width=Inches(4.5))
                doc.add_paragraph()
