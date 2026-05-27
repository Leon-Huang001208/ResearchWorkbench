"""MarkItDown 转换策略 —— 基于 microsoft/markitdown 的 PDF 转 Markdown

作为首选转换器，当 markitdown 可用时优先使用。不可用时优雅降级。
"""
import logging
from typing import Any, Dict

from core.contracts.pdf_conversion import ConversionResult, StrategyType
from ingestion.converters.base import PDFConversionStrategy

logger = logging.getLogger(__name__)

try:
    from markitdown import MarkItDown

    HAS_MARKITDOWN = True
except ImportError:
    HAS_MARKITDOWN = False


class MarkItDownStrategy(PDFConversionStrategy):
    """基于 microsoft/markitdown 的 Markdown 转换策略"""

    def is_available(self) -> bool:
        return HAS_MARKITDOWN

    def convert(self, pdf_path: str) -> ConversionResult:
        if not HAS_MARKITDOWN:
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message="markitdown 未安装，请执行: pip install markitdown[pdf]",
            )

        try:
            md = MarkItDown()
            result = md.convert(pdf_path)
            markdown = result.text_content if hasattr(result, "text_content") else str(result)

            # 添加页面锚点（如果 markitdown 没有自带）
            marked_markdown = self._add_page_anchors(markdown)

            token_count = self.estimate_tokens(marked_markdown)

            # 检测内容特征
            feature_metadata = self._detect_features(marked_markdown)

            quality_score = self._compute_quality_score(marked_markdown, feature_metadata)

            return ConversionResult(
                success=True,
                strategy_used=self.name,
                markdown=marked_markdown,
                token_count=token_count,
                quality_score=quality_score,
                has_tables=feature_metadata.get("has_tables", False),
                has_images=feature_metadata.get("has_images", False),
                has_code_blocks=feature_metadata.get("has_code_blocks", False),
                metadata=feature_metadata,
            )
        except Exception as e:
            logger.warning(f"MarkItDown 转换失败: {e}")
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message=str(e),
            )

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MARKITDOWN

    @property
    def name(self) -> str:
        return "markitdown"

    @staticmethod
    def _add_page_anchors(markdown: str) -> str:
        """如果 markitdown 输出中没有页面标记，在分页符处添加标记"""
        # markitdown 通常在转换时保留分页符 (\f 或多个换行)
        import re

        # 检测是否已有页面锚点
        if "<!-- page:" in markdown:
            return markdown

        # 按换页符分割并添加标记
        parts = re.split(r"\f", markdown)
        if len(parts) <= 1:
            return markdown

        anchored_parts = []
        for i, part in enumerate(parts, 1):
            anchored_parts.append(f"<!-- page: {i} -->\n{part.strip()}")

        return "\n\n".join(anchored_parts)

    @staticmethod
    def _detect_features(markdown: str) -> Dict[str, Any]:
        """检测 Markdown 内容中的表格、图片和代码块"""
        metadata: Dict[str, Any] = {}

        has_tables = "| " in markdown and " |" in markdown
        has_images = "![" in markdown
        has_code_blocks = "```" in markdown

        metadata["has_tables"] = has_tables
        metadata["has_images"] = has_images
        metadata["has_code_blocks"] = has_code_blocks

        if has_tables:
            # 估算表格行数
            table_lines = [line for line in markdown.split("\n") if line.strip().startswith("|")]
            metadata["table_rows"] = len(table_lines)

        return metadata

    @staticmethod
    def _compute_quality_score(markdown: str, features: Dict[str, Any]) -> float:
        """基于 Markdown 特征计算质量评分"""
        if not markdown.strip():
            return 0.0

        score = 0.6  # markitdown 基准质量较高

        # 有表格是加分项
        if features.get("has_tables"):
            score += 0.15

        # Markdown 标题层级丰富度
        heading_levels = set()
        for line in markdown.split("\n"):
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                heading_levels.add(min(level, 4))

        if len(heading_levels) >= 3:
            score += 0.1
        elif len(heading_levels) >= 1:
            score += 0.05

        # 内容长度合理
        if len(markdown) > 1000:
            score += 0.1

        return min(score, 1.0)
