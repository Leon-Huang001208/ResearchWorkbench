"""Word 文档投影 - 将报告输出为 Word 格式"""
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import docx as _docx_mod  # noqa: F401 – re-exported on demand
except ImportError:
    _docx_mod = None  # type: ignore[assignment]

from core.contracts import SectionOutput
from core.observability import get_logger

logger = get_logger(__name__)


class WordProjection:
    """Word 报告投影"""

    def __init__(self):
        self._has_docx = self._check_docx()

    def _check_docx(self) -> bool:
        """检查 python-docx 是否可用"""
        try:
            import docx

            return True
        except ImportError:
            logger.warning("python-docx not installed, Word output disabled")
            return False

    def save(
        self,
        output_path: Path | str,
        title: str,
        sections: list[SectionOutput],
        metadata: dict[str, Any] | None = None,
    ):
        """保存为 Word 文档"""
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
