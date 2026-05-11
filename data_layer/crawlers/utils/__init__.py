"""
爬虫工具模块

提供通用的反爬虫、重试、延迟等功能
"""
from .anti_crawler_kit import (
    AntiScrapeConfig,
    AntiScrapeKit,
    RequestTiming,
    UserAgentRotator,
    SmartDelayer,
    RetryConfig,
    retry_with_backoff,
)
from .pdf_converter import (
    PDFConversionResult,
    PDFConversionStrategy,
    PDFConverter,
    RawTextStrategy,
    MarkItDownStrategy,
    get_converter,
    convert_pdf,
    convert_and_save,
)

__all__ = [
    "AntiScrapeConfig",
    "AntiScrapeKit",
    "RequestTiming",
    "UserAgentRotator",
    "SmartDelayer",
    "RetryConfig",
    "retry_with_backoff",
    "PDFConversionResult",
    "PDFConversionStrategy",
    "PDFConverter",
    "RawTextStrategy",
    "MarkItDownStrategy",
    "get_converter",
    "convert_pdf",
    "convert_and_save",
]
