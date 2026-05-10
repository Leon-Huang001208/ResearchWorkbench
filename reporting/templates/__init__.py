"""报告模板"""
from pathlib import Path

from reporting.templates.template_manager import TemplateManager

TEMPLATES_DIR = Path(__file__).parent
AVAILABLE_TEMPLATES = [
    "asset_analysis",
    "thesis_research",
    "market_report",
    "weekly_report",
]

__all__ = [
    "TEMPLATES_DIR",
    "AVAILABLE_TEMPLATES",
    "TemplateManager",
]
