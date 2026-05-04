"""Markdown 投影 - 将报告输出为 Markdown 格式"""
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import SectionOutput
from core.observability import get_logger

logger = get_logger(__name__)


class MarkdownProjection:
    """Markdown 报告投影"""

    def __init__(self):
        pass

    def render(
        self,
        title: str,
        sections: list[SectionOutput],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """渲染为 Markdown 字符串"""
        lines = []

        # 标题
        lines.append(f"# {title}")
        lines.append("")

        # 元数据
        if metadata:
            lines.append("---")
            for key, value in metadata.items():
                lines.append(f"{key}: {value}")
            lines.append("---")
            lines.append("")

        # 生成时间
        lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")

        # 段落内容
        for section in sections:
            lines.append(f"## {section.key.replace('_', ' ').title()}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

            # 证据引用
            if section.evidence_refs:
                lines.append("**参考文献:**")
                for ref in section.evidence_refs:
                    lines.append(f"- [{ref}] 来源待补充")
                lines.append("")

            # 警告
            if section.warnings:
                lines.append("⚠️ **警告:**")
                for warning in section.warnings:
                    lines.append(f"- {warning}")
                lines.append("")

        return "\n".join(lines)

    def save(
        self,
        output_path: Path | str,
        title: str,
        sections: list[SectionOutput],
        metadata: dict[str, Any] | None = None,
    ):
        """保存为 Markdown 文件"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.render(title, sections, metadata)
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Saved Markdown report to: {output_path}")
