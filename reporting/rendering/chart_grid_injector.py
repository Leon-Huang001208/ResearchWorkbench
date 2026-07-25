"""图表网格注入器 — 在 Word 模板中创建或替换图表网格布局.

对应目标 docx 中 2×2 图表矩阵的布局模式：
    ┌──────────────────┬──────────────────┐
    │ 图表：A股走势     │ 图表：涨跌幅比较   │  ← 粗体居中标题行
    │     [chart1]     │     [chart2]     │  ← 图表行
    └──────────────────┴──────────────────┘

使用无边框 Word 表格实现多列布局。
支持 native_chart（原生 Excel 图表）和 matplotlib_image（程序化渲染）两种模式。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from core.contracts.reporting import ChartCellSpec, ChartGridSpec
from core.observability import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from docx.document import Document

try:
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement
    from docx.shared import Inches, Pt

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


class ChartGridInjector:
    """在 Word 模板中创建图表网格布局.

    在占位符段落位置插入无边框表格，
    第一行为标题行（粗体居中），第二行为图表行。

    Usage:
        injector = ChartGridInjector(chart_service)
        injector.inject_at_placeholder(
            doc, placeholder_key="section_2_grid", spec=chart_grid_spec
        )
    """

    # 图表标题样式常量
    TITLE_FONT_SIZE_PT = 10
    TITLE_FONT_NAME = "Microsoft YaHei"

    def __init__(self, chart_service: Any = None) -> None:
        """初始化.

        Args:
            chart_service: ReportProjectChartService 实例（用于渲染图表）.
        """
        self._chart_service = chart_service

    def inject_at_placeholder(
        self,
        doc: "Document",
        placeholder_key: str,
        spec: ChartGridSpec,
        *,
        project_dir: Optional[Path] = None,
    ) -> None:
        """在占位符位置插入图表网格.

        找到文档中 {{placeholder_key}} 所在段落，
        用无边框表格替换该段落，表格包含标题行和图表行。

        Args:
            doc: python-docx Document 对象.
            placeholder_key: 占位符 key.
            spec: 图表网格规格.
            project_dir: 项目目录（用于解析相对路径）.
        """
        if not DOCX_AVAILABLE:
            logger.warning("python-docx 不可用，ChartGridInjector 无法工作")
            return

        placeholder_para = self._find_placeholder_paragraph(doc, placeholder_key)
        if placeholder_para is None:
            logger.warning(
                "未找到图表网格占位符段落",
                extra={"placeholder": placeholder_key},
            )
            return

        # 创建无边框表格
        table = self._create_borderless_table(
            doc, placeholder_para, spec.rows * 2, spec.cols, spec.col_widths
        )

        # 填充每个 cell
        for cell_idx, cell_spec in enumerate(spec.cells):
            row_in_grid = cell_idx // spec.cols
            col_in_grid = cell_idx % spec.cols

            # 表格行索引：偶数行 = 标题行，奇数行 = 图表行
            title_row_idx = row_in_grid * 2
            chart_row_idx = title_row_idx + 1

            # 标题
            title_cell = table.cell(title_row_idx, col_in_grid)
            self._set_cell_title(title_cell, cell_spec.title)

            # 图表
            chart_cell = table.cell(chart_row_idx, col_in_grid)
            self._set_cell_chart(chart_cell, cell_spec, project_dir)

        # 删除占位符段落
        placeholder_para._element.getparent().remove(placeholder_para._element)

        logger.info(
            "ChartGridInjector: 图表网格注入完成",
            extra={
                "placeholder": placeholder_key,
                "rows": spec.rows,
                "cols": spec.cols,
                "cell_count": len(spec.cells),
            },
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _find_placeholder_paragraph(self, doc: "Document", placeholder_key: str) -> Any:
        """在文档中查找包含占位符的段落.

        搜索范围：正文段落 + 表格单元格.

        Args:
            doc: Word Document 对象.
            placeholder_key: 占位符 key.

        Returns:
            找到的 Paragraph 对象或 None.
        """
        patterns = [f"{{{{{placeholder_key}}}}}", f"{{{placeholder_key}}}"]

        # 搜索正文段落
        for para in doc.paragraphs:
            for pattern in patterns:
                if pattern in (para.text or ""):
                    return para

        # 搜索表格中的段落
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        for pattern in patterns:
                            if pattern in (para.text or ""):
                                return para

        return None

    def _create_borderless_table(
        self,
        doc: "Document",
        anchor_paragraph: Any,
        rows: int,
        cols: int,
        col_widths: Optional[List[float]] = None,
    ) -> Any:
        """在锚点段落后创建无边框表格.

        Args:
            doc: Word Document 对象.
            anchor_paragraph: 锚点段落（表格插入在其后）.
            rows: 行数.
            cols: 列数.
            col_widths: 列宽（英寸），None 为均分.

        Returns:
            创建的 Table 对象.
        """
        table = doc.add_table(rows=rows, cols=cols)

        # 将表格移动到锚点段落之后
        anchor_element = anchor_paragraph._element
        anchor_element.addnext(table._tbl)

        # 移除表格边框
        self._remove_table_borders(table)

        # 设置列宽
        if col_widths:
            for col_idx, width in enumerate(col_widths):
                if col_idx < cols:
                    for row in table.rows:
                        row.cells[col_idx].width = Inches(width)

        return table

    @staticmethod
    def _remove_table_borders(table: Any) -> None:
        """移除表格的所有边框."""
        tbl = table._tbl
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement("w:tblPr")
            tbl.insert(0, tblPr)

        borders = OxmlElement("w:tblBorders")
        for border_name in ["top", "left", "bottom", "right", "insideH", "insideV"]:
            border = OxmlElement(f"w:{border_name}")
            border.set(qn("w:val"), "none")
            border.set(qn("w:sz"), "0")
            border.set(qn("w:space"), "0")
            border.set(qn("w:color"), "auto")
            borders.append(border)

        tblPr.append(borders)

    def _set_cell_title(self, cell: Any, title: str) -> None:
        """设置图表网格单元格的标题.

        清除单元格中现有段落，创建粗体居中的标题段落。

        Args:
            cell: Word Table Cell 对象.
            title: 标题文本（格式："图表：xxx"）.
        """
        # 清除单元格现有内容
        for para in cell.paragraphs:
            for run in para.runs:
                run.text = ""

        # 使用第一个段落作为标题
        if cell.paragraphs:
            para = cell.paragraphs[0]
        else:
            para = cell.add_paragraph()

        run = para.add_run(title)
        run.bold = True
        run.font.size = Pt(self.TITLE_FONT_SIZE_PT)
        run.font.name = self.TITLE_FONT_NAME
        para.alignment = 1  # 居中

    def _set_cell_chart(
        self,
        cell: Any,
        cell_spec: ChartCellSpec,
        project_dir: Optional[Path] = None,
    ) -> None:
        """在图表网格单元格中嵌入图表.

        根据 rendering_mode 选择渲染方式：
        - native_chart: 从 Excel 复制原生图表 XML（需要 chart_service）
        - matplotlib_image: 使用 matplotlib 渲染为图片嵌入
        - embedded_image: 直接嵌入已有图片文件

        Args:
            cell: Word Table Cell 对象.
            cell_spec: 图表单元格规格.
            project_dir: 项目目录.
        """
        # 清除单元格现有内容
        for para in cell.paragraphs:
            for run in para.runs:
                run.text = ""

        para = cell.paragraphs[0] if cell.paragraphs else cell.add_paragraph()

        if cell_spec.rendering_mode == "embedded_image":
            self._embed_image_file(para, cell_spec, project_dir)
        elif cell_spec.rendering_mode == "matplotlib_image":
            self._embed_matplotlib_chart(para, cell_spec, project_dir)
        elif cell_spec.rendering_mode == "native_chart":
            logger.info(
                "Native chart mode - 需要 chart_service 支持",
                extra={"chart_id": cell_spec.chart_id},
            )
            # Native chart 需要 chart_service 在外部完成 XML 级操作
            # 此处先放置一个占位标记
            placeholder_run = para.add_run(f"[图表: {cell_spec.title}]")
            placeholder_run.font.size = Pt(9)
            placeholder_run.font.color.rgb = type(
                "RGBColor", (), {"__getattr__": lambda s, n: 0x999999}
            )()

    def _embed_image_file(
        self,
        paragraph: Any,
        cell_spec: ChartCellSpec,
        project_dir: Optional[Path] = None,
    ) -> None:
        """嵌入已有图片文件.

        Args:
            paragraph: Word Paragraph 对象.
            cell_spec: 图表单元格规格.
            project_dir: 项目目录.
        """
        file_path = cell_spec.data_source.file_path
        if not file_path:
            logger.warning("embedded_image 模式缺少 file_path", extra={"chart_id": cell_spec.chart_id})
            return

        if project_dir:
            file_path = str(project_dir / file_path)

        try:
            run = paragraph.add_run()
            run.add_picture(
                file_path,
                width=Inches(cell_spec.width_inches),
                height=Inches(cell_spec.height_inches),
            )
        except FileNotFoundError:
            logger.error("图片文件不存在", extra={"path": file_path})
        except Exception:
            logger.exception("嵌入图片失败", extra={"path": file_path})

    def _embed_matplotlib_chart(
        self,
        paragraph: Any,
        cell_spec: ChartCellSpec,
        project_dir: Optional[Path] = None,
    ) -> None:
        """使用 matplotlib 渲染图表并嵌入.

        委托给 chart_service 生成图表图片，然后嵌入。

        Args:
            paragraph: Word Paragraph 对象.
            cell_spec: 图表单元格规格.
            project_dir: 项目目录.
        """
        chart_bytes = None

        if self._chart_service:
            try:
                chart_bytes = self._chart_service.render_chart_image(
                    chart_id=cell_spec.chart_id,
                    chart_type=cell_spec.chart_type,
                    data_source=cell_spec.data_source,
                    project_dir=project_dir,
                    width_inches=cell_spec.width_inches,
                    height_inches=cell_spec.height_inches,
                )
            except Exception:
                logger.exception(
                    "chart_service 渲染失败",
                    extra={"chart_id": cell_spec.chart_id},
                )

        if chart_bytes:
            try:
                run = paragraph.add_run()
                image_stream = io.BytesIO(chart_bytes)
                run.add_picture(
                    image_stream,
                    width=Inches(cell_spec.width_inches),
                    height=Inches(cell_spec.height_inches),
                )
            except Exception:
                logger.exception("嵌入图表图片失败", extra={"chart_id": cell_spec.chart_id})
        else:
            # Fallback: 显示占位文字
            placeholder_run = paragraph.add_run(f"[图表: {cell_spec.title} — 待生成]")
            placeholder_run.font.size = Pt(9)
            placeholder_run.font.italic = True
