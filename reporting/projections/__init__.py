"""报告投影层"""
from reporting.projections.excel import ExcelProjection
from reporting.projections.markdown import MarkdownProjection
from reporting.projections.powerpoint import PowerPointProjection
from reporting.projections.word import WordProjection

__all__ = [
    "MarkdownProjection",
    "WordProjection",
    "ExcelProjection",
    "PowerPointProjection",
]
