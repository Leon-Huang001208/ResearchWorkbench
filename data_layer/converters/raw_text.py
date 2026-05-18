"""Raw Text 回退策略 —— 基于 pdfplumber 的纯文本提取

作为基线策略，始终可用（只要 pdfplumber 已安装），无需外部依赖。
"""
import logging
from typing import Any, Dict

from core.contracts.pdf_conversion import ConversionResult, StrategyType
from data_layer.converters.base import PDFConversionStrategy

logger = logging.getLogger(__name__)


class RawTextStrategy(PDFConversionStrategy):
    """基于 pdfplumber 的原始文本提取策略"""

    def is_available(self) -> bool:
        try:
            import pdfplumber  # noqa: F401

            return True
        except ImportError:
            return False

    def convert(self, pdf_path: str) -> ConversionResult:
        try:
            import pdfplumber
        except ImportError:
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message="pdfplumber 未安装",
            )

        try:
            raw_text_parts: list[str] = []
            metadata: Dict[str, Any] = {"pages": 0}

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                metadata["pages"] = page_count

                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    # 添加页面标记，便于后续分块时定位
                    raw_text_parts.append(f"<!-- page: {page_num} -->\n{page_text}")
                    if page_num == 1:
                        metadata["first_page_chars"] = len(page_text)

            raw_text = "\n\n".join(raw_text_parts)
            token_count = self.estimate_tokens(raw_text)

            quality_score = self._compute_quality_score(raw_text, page_count)

            return ConversionResult(
                success=True,
                strategy_used=self.name,
                raw_text=raw_text,
                page_count=page_count,
                token_count=token_count,
                quality_score=quality_score,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"原始文本提取失败: {e}")
            return ConversionResult(
                success=False,
                strategy_used=self.name,
                error_message=str(e),
            )

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.RAW_TEXT

    @property
    def name(self) -> str:
        return "raw_text"

    @staticmethod
    def _compute_quality_score(text: str, page_count: int) -> float:
        """基于启发式方法计算质量评分

        评分因素：
        - 是否有足够内容（非空文本）
        - 每页平均字符数
        - 中文内容占比（期望以中文为主）
        """
        if not text.strip() or page_count == 0:
            return 0.0

        score = 0.5  # 基准分（pdfplumber 提取质量通常中等）

        # 每页平均字符数（合理范围 200-2000）
        avg_chars_per_page = len(text) / max(page_count, 1)
        if avg_chars_per_page >= 500:
            score += 0.2
        elif avg_chars_per_page >= 200:
            score += 0.1

        # 文本中有结构化内容（数字/表格痕迹）
        if "\t" in text or "  " in text:
            score += 0.1

        # 有多页内容
        if page_count > 1:
            score += 0.1

        return min(score, 1.0)