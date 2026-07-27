"""报告项目资产根目录。"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent
AVAILABLE_TEMPLATES: list[str] = []

__all__ = [
    "TEMPLATES_DIR",
    "AVAILABLE_TEMPLATES",
]
