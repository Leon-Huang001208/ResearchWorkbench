"""数据解析器"""
from data_layer.parsers.html_parser import HTMLParser, HTMLParseResult
from data_layer.parsers.pdf_parser import PDFParser, PDFParseResult

__all__ = [
    "PDFParser",
    "PDFParseResult",
    "HTMLParser",
    "HTMLParseResult",
]
