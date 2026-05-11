#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 转换工具模块

提供可插拔的 PDF 转换策略：
- 原始文本提取（pdfplumber，总是可用）
- Markdown 转换（可选策略）
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PDFConversionResult:
    """PDF 转换结果"""

    success: bool
    raw_text: str = ""
    markdown: str = ""
    strategy_used: str = ""
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class PDFConversionStrategy(ABC):
    """PDF 转换策略基类"""

    @abstractmethod
    def is_available(self) -> bool:
        """检查策略是否可用"""
        pass

    @abstractmethod
    def convert(self, pdf_path: str) -> PDFConversionResult:
        """转换 PDF 到目标格式"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取策略名称"""
        pass


class RawTextStrategy(PDFConversionStrategy):
    """原始文本提取策略（基于 pdfplumber）"""

    def is_available(self) -> bool:
        try:
            import pdfplumber

            return True
        except ImportError:
            return False

    def convert(self, pdf_path: str) -> PDFConversionResult:
        try:
            import pdfplumber

            raw_text = ""
            metadata: Dict[str, Any] = {"pages": 0}

            with pdfplumber.open(pdf_path) as pdf:
                metadata["pages"] = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    raw_text += page_text + "\n\n"
                    if page_num == 1:
                        # 从第一页尝试提取元数据
                        metadata["first_page_chars"] = len(page_text)

            return PDFConversionResult(
                success=True,
                raw_text=raw_text.strip(),
                strategy_used="raw_text",
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"原始文本提取失败: {e}")
            return PDFConversionResult(
                success=False,
                raw_text="",
                strategy_used="raw_text",
                error_message=str(e),
            )

    def get_name(self) -> str:
        return "raw_text"


class MarkItDownStrategy(PDFConversionStrategy):
    """MarkItDown 转换策略（如果可用）"""

    def is_available(self) -> bool:
        try:
            import markitdown

            return True
        except ImportError:
            return False

    def convert(self, pdf_path: str) -> PDFConversionResult:
        try:
            import markitdown

            md_converter = markitdown.MarkItDown()
            markdown = md_converter.convert(pdf_path)

            # 同时提取原始文本作为备份
            raw_result = RawTextStrategy().convert(pdf_path)

            return PDFConversionResult(
                success=True,
                raw_text=raw_result.raw_text,
                markdown=markdown,
                strategy_used="markitdown",
                metadata=raw_result.metadata,
            )
        except Exception as e:
            logger.warning(f"MarkItDown 转换失败: {e}")
            # 回退到原始文本
            raw_result = RawTextStrategy().convert(pdf_path)
            raw_result.error_message = str(e)
            raw_result.strategy_used = "markitdown_fallback_to_raw"
            return raw_result

    def get_name(self) -> str:
        return "markitdown"


class PDFConverter:
    """PDF 转换器 - 可插拔策略"""

    def __init__(self):
        self.strategies: Dict[str, PDFConversionStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """注册默认策略"""
        self.register_strategy(RawTextStrategy())
        self.register_strategy(MarkItDownStrategy())

    def register_strategy(self, strategy: PDFConversionStrategy):
        """注册转换策略"""
        name = strategy.get_name()
        self.strategies[name] = strategy
        logger.debug(f"注册 PDF 转换策略: {name} (可用: {strategy.is_available()})")

    def get_available_strategies(self) -> list[str]:
        """获取可用策略列表"""
        return [name for name, s in self.strategies.items() if s.is_available()]

    def convert(
        self,
        pdf_path: str,
        preferred_strategy: Optional[str] = None,
    ) -> PDFConversionResult:
        """
        转换 PDF 文件

        Args:
            pdf_path: PDF 文件路径
            preferred_strategy: 首选策略名称（可选）

        Returns:
            PDFConversionResult
        """
        if not os.path.exists(pdf_path):
            return PDFConversionResult(
                success=False,
                strategy_used="none",
                error_message=f"文件不存在: {pdf_path}",
            )

        # 确定使用哪个策略
        strategy: Optional[PDFConversionStrategy] = None

        if preferred_strategy and preferred_strategy in self.strategies:
            candidate = self.strategies[preferred_strategy]
            if candidate.is_available():
                strategy = candidate
            else:
                logger.warning(f"首选策略不可用: {preferred_strategy}，将回退")

        # 如果没有首选策略或首选不可用，按优先级选择
        if not strategy:
            priority = ["markitdown", "raw_text"]
            for name in priority:
                candidate = self.strategies.get(name)
                if candidate and candidate.is_available():
                    strategy = candidate
                    break

        if not strategy:
            return PDFConversionResult(
                success=False,
                strategy_used="none",
                error_message="没有可用的转换策略",
            )

        logger.debug(f"使用策略 {strategy.get_name()} 转换: {pdf_path}")
        return strategy.convert(pdf_path)

    def convert_and_save(
        self,
        pdf_path: str,
        output_dir: str,
        preferred_strategy: Optional[str] = None,
        save_raw: bool = True,
        save_markdown: bool = True,
    ) -> Tuple[PDFConversionResult, Dict[str, str]]:
        """
        转换 PDF 并保存结果

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录
            preferred_strategy: 首选策略
            save_raw: 是否保存原始文本
            save_markdown: 是否保存 Markdown

        Returns:
            (PDFConversionResult, {file_type: saved_path})
        """
        result = self.convert(pdf_path, preferred_strategy)
        saved_paths: Dict[str, str] = {}

        if not result.success:
            return result, saved_paths

        os.makedirs(output_dir, exist_ok=True)

        pdf_name = Path(pdf_path).stem

        # 保存原始文本
        if save_raw and result.raw_text:
            raw_path = os.path.join(output_dir, f"{pdf_name}_raw.txt")
            try:
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(result.raw_text)
                saved_paths["raw_text"] = raw_path
            except Exception as e:
                logger.warning(f"保存原始文本失败: {e}")

        # 保存 Markdown
        if save_markdown and result.markdown:
            md_path = os.path.join(output_dir, f"{pdf_name}.md")
            try:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(result.markdown)
                saved_paths["markdown"] = md_path
            except Exception as e:
                logger.warning(f"保存 Markdown 失败: {e}")

        return result, saved_paths


# 全局转换器实例
_default_converter: Optional[PDFConverter] = None


def get_converter() -> PDFConverter:
    """获取全局 PDF 转换器实例"""
    global _default_converter
    if _default_converter is None:
        _default_converter = PDFConverter()
    return _default_converter


def convert_pdf(
    pdf_path: str,
    preferred_strategy: Optional[str] = None,
) -> PDFConversionResult:
    """便捷函数：转换 PDF"""
    return get_converter().convert(pdf_path, preferred_strategy)


def convert_and_save(
    pdf_path: str,
    output_dir: str,
    preferred_strategy: Optional[str] = None,
    save_raw: bool = True,
    save_markdown: bool = True,
) -> Tuple[PDFConversionResult, Dict[str, str]]:
    """便捷函数：转换 PDF 并保存"""
    return get_converter().convert_and_save(
        pdf_path, output_dir, preferred_strategy, save_raw, save_markdown
    )
