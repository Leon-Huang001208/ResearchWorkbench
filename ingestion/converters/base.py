"""
PDF 转换策略基类.

提供所有 PDF 转换策略必须实现的抽象接口。
"""
import logging
from abc import ABC, abstractmethod

from core.contracts.pdf_conversion import ConversionResult, StrategyType

logger = logging.getLogger(__name__)


class PDFConversionStrategy(ABC):
    """PDF 转换策略抽象基类"""

    @abstractmethod
    def is_available(self) -> bool:
        """检查策略是否可用（依赖是否安装）"""
        pass

    @abstractmethod
    def convert(self, pdf_path: str) -> ConversionResult:
        """将 PDF 文件转换为结构化结果

        Args:
            pdf_path: PDF 文件路径

        Returns:
            ConversionResult: 统一的转换结果
        """
        pass

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """返回策略类型枚举"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """返回策略名称（小写字符串）"""
        pass

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算文本的 token 数量（粗略：中文字符 ~1.5 tokens，英文 ~0.75 tokens/词）"""
        if not text:
            return 0
        # 简单估算：按字符数 / 1.5
        return max(1, int(len(text) / 1.5))
