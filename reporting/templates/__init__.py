"""报告模板"""
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent
AVAILABLE_TEMPLATES = [
    "asset_analysis",
    "thesis_research",
    "market_report",
]

__all__ = [
    "TEMPLATES_DIR",
    "AVAILABLE_TEMPLATES",
]
