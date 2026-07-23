"""
样式映射器 — DesignTokens → 格式特定样式配置.

将文档级 DesignTokens 转换为各目标格式（Word/PPT）所需的
具体样式参数，确保不同格式之间视觉一致性。

设计原则：
- 每个格式有独立的映射方法，返回该格式直接可用的配置
- 映射器不持有状态，所有方法为纯函数
- callout 颜色映射到格式友好的格式
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from core.contracts.document import DesignTokens
from core.observability import get_logger

if TYPE_CHECKING:
    from core.contracts.content_element import CalloutType

logger = get_logger(__name__)


class StyleMapper:
    """DesignTokens → 格式特定样式映射器."""

    def __init__(self, tokens: DesignTokens) -> None:
        self.tokens = tokens

    # ========================================================================
    # Word 样式映射
    # ========================================================================

    def word_heading_style(self, level: int) -> Dict[str, Any]:
        """返回 Word 标题样式参数.

        Args:
            level: 标题级别 (1-6).

        Returns:
            包含 font_name, font_size_pt, bold, color_hex 的字典.
        """
        sizes = self.tokens.heading_sizes
        return {
            "font_name": self.tokens.heading_font,
            "font_size_pt": sizes.get(level, self.tokens.body_size + 4),
            "bold": level <= 3,
            "color_hex": self.tokens.primary_color if level <= 2 else self.tokens.text_color,
        }

    def word_body_style(self) -> Dict[str, Any]:
        """返回 Word 正文样式参数."""
        return {
            "font_name": self.tokens.body_font,
            "font_size_pt": self.tokens.body_size,
            "line_spacing": self.tokens.body_line_spacing,
            "color_hex": self.tokens.text_color,
            "space_after_pt": self.tokens.paragraph_spacing_after,
        }

    def word_table_style(self) -> Dict[str, Any]:
        """返回 Word 表格样式参数."""
        return {
            "header_bg_hex": self.tokens.primary_color,
            "header_fg_hex": "#FFFFFF",
            "header_font": self.tokens.heading_font,
            "header_size_pt": self.tokens.body_size,
            "body_font": self.tokens.body_font,
            "body_size_pt": self.tokens.body_size,
            "border_color_hex": self.tokens.border_color,
            "alt_row_bg_hex": self.tokens.background_color,
        }

    def word_callout_style(self, callout_type: "CalloutType") -> Dict[str, Any]:
        """返回 Word 提示框样式参数.

        Args:
            callout_type: 提示框类型.

        Returns:
            包含 bg_hex, border_hex, font_name, font_size_pt 的字典.
        """
        bg_map = self.tokens.callout_colors
        ct_val = callout_type.value if hasattr(callout_type, "value") else str(callout_type)
        return {
            "bg_hex": bg_map.get(ct_val, "#F7FAFC"),
            "border_hex": self.tokens.primary_color,
            "font_name": self.tokens.body_font,
            "font_size_pt": self.tokens.body_size - 1,
        }

    # ========================================================================
    # PPT 样式映射
    # ========================================================================

    def ppt_title_style(self) -> Dict[str, Any]:
        """返回 PPT 标题样式参数."""
        return {
            "font_name": self.tokens.heading_font,
            "font_size_pt": self.tokens.heading_sizes.get(1, 36),
            "color_hex": self.tokens.primary_color,
            "bold": True,
        }

    def ppt_subtitle_style(self) -> Dict[str, Any]:
        """返回 PPT 副标题样式参数."""
        return {
            "font_name": self.tokens.body_font,
            "font_size_pt": self.tokens.heading_sizes.get(3, 18),
            "color_hex": self.tokens.muted_text_color,
        }

    def ppt_body_style(self) -> Dict[str, Any]:
        """返回 PPT 正文样式参数."""
        return {
            "font_name": self.tokens.body_font,
            "font_size_pt": self.tokens.body_size,
            "line_spacing": self.tokens.body_line_spacing,
            "color_hex": self.tokens.text_color,
        }

    def ppt_heading_style(self, level: int) -> Dict[str, Any]:
        """返回 PPT 标题样式参数（每级）.

        All heading levels on PPT are scaled up by ~40% from Word.
        """
        word_sizes = self.tokens.heading_sizes
        scale = 1.4  # PPT slides need bigger fonts
        return {
            "font_name": self.tokens.heading_font,
            "font_size_pt": int(word_sizes.get(level, self.tokens.body_size + 4) * scale),
            "bold": level <= 3,
            "color_hex": self.tokens.primary_color if level <= 2 else self.tokens.text_color,
        }

    def ppt_table_style(self) -> Dict[str, Any]:
        """返回 PPT 表格样式参数."""
        return {
            "header_bg_hex": self.tokens.primary_color,
            "header_fg_hex": "#FFFFFF",
            "header_size_pt": self.tokens.body_size,
            "body_size_pt": self.tokens.body_size - 1,
            "border_color_hex": self.tokens.border_color,
        }

    def ppt_slide_dimensions_inches(self) -> Tuple[float, float]:
        """返回 PPT 幻灯片尺寸（英寸）."""
        return (self.tokens.ppt_slide_width, self.tokens.ppt_slide_height)

    # ========================================================================
    # 通用工具
    # ========================================================================

    def to_emu(self, inches: float) -> int:
        """英寸 → EMU (English Metric Units).

        1 inch = 914400 EMU. 用于 python-pptx 的尺寸参数.
        """
        return int(inches * 914400)

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Hex 颜色 → (R, G, B) 元组.

        Args:
            hex_color: 如 "#1A365D".

        Returns:
            (R, G, B) 0-255.
        """
        hex_color = hex_color.lstrip("#")
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    def chart_colors(self) -> List[str]:
        """返回图表颜色序列."""
        return list(self.tokens.chart_palette)

    def chart_color_at(self, index: int) -> str:
        """返回第 index 个图表颜色（循环）."""
        palette = self.tokens.chart_palette
        return palette[index % len(palette)]
