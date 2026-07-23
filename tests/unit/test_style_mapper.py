"""Phase 2 单元测试 - StyleMapper 样式映射器."""

from core.contracts.content_element import CalloutType
from core.contracts.document import (
    DesignTokens,
    brief_tokens,
    presentation_tokens,
    report_tokens,
)
from reporting.rendering.style_mapper import StyleMapper


class TestStyleMapper:
    def test_init_with_default_tokens(self):
        """默认令牌初始化."""
        mapper = StyleMapper(DesignTokens())
        assert mapper.tokens.primary_color == "#1A365D"

    def test_init_with_custom_tokens(self):
        """自定义令牌初始化."""
        tokens = DesignTokens(primary_color="#FF0000")
        mapper = StyleMapper(tokens)
        assert mapper.tokens.primary_color == "#FF0000"

    # ── Word 样式 ──

    def test_word_heading_style(self):
        """Word 标题样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.word_heading_style(1)
        assert style["font_name"] == "Microsoft YaHei"
        assert style["font_size_pt"] == 28
        assert style["bold"] is True
        assert style["color_hex"] == "#1A365D"

    def test_word_heading_style_deep_level(self):
        """深层标题样式（level 5+ 不加粗）."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.word_heading_style(5)
        assert style["bold"] is False
        assert style["color_hex"] == "#1A202C"  # text_color for deep levels

    def test_word_body_style(self):
        """Word 正文样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.word_body_style()
        assert style["font_name"] == "Microsoft YaHei"
        assert style["font_size_pt"] == 11
        assert style["line_spacing"] == 1.5
        assert style["color_hex"] == "#1A202C"

    def test_word_table_style(self):
        """Word 表格样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.word_table_style()
        assert style["header_bg_hex"] == "#1A365D"
        assert style["header_fg_hex"] == "#FFFFFF"
        assert "border_color_hex" in style
        assert "alt_row_bg_hex" in style

    def test_word_callout_style(self):
        """Word 提示框样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.word_callout_style(CalloutType.WARNING)
        assert "bg_hex" in style
        assert "border_hex" in style
        assert style["border_hex"] == "#1A365D"

    def test_word_callout_style_different_types(self):
        """不同类型提示框背景色不同."""
        mapper = StyleMapper(DesignTokens())
        info_style = mapper.word_callout_style(CalloutType.INFO)
        warn_style = mapper.word_callout_style(CalloutType.WARNING)
        assert info_style["bg_hex"] != warn_style["bg_hex"]

    # ── PPT 样式 ──

    def test_ppt_title_style(self):
        """PPT 标题样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.ppt_title_style()
        assert style["font_size_pt"] == 28
        assert style["color_hex"] == "#1A365D"
        assert style["bold"] is True

    def test_ppt_heading_style_scaling(self):
        """PPT 标题样式自动放大."""
        mapper = StyleMapper(DesignTokens())
        word_style = mapper.word_heading_style(2)
        ppt_style = mapper.ppt_heading_style(2)
        # PPT 字号应该比 Word 大约 40%
        assert ppt_style["font_size_pt"] > word_style["font_size_pt"]

    def test_ppt_body_style(self):
        """PPT 正文样式映射."""
        mapper = StyleMapper(DesignTokens())
        style = mapper.ppt_body_style()
        assert style["font_name"] == "Microsoft YaHei"
        assert style["font_size_pt"] == 11

    def test_ppt_slide_dimensions(self):
        """PPT 幻灯片尺寸."""
        mapper = StyleMapper(DesignTokens())
        w, h = mapper.ppt_slide_dimensions_inches()
        assert w == 13.333
        assert h == 7.5

    # ── 预设令牌样式测试 ──

    def test_report_tokens_mapper(self):
        """研报预设令牌的映射."""
        mapper = StyleMapper(report_tokens())
        assert mapper.tokens.body_font == "SimSun"
        assert mapper.tokens.heading_font == "SimHei"
        body = mapper.word_body_style()
        assert body["font_name"] == "SimSun"
        assert body["font_size_pt"] == 12

    def test_presentation_tokens_mapper(self):
        """PPT 预设令牌的映射."""
        mapper = StyleMapper(presentation_tokens())
        # PPT 预设字号应大于 Word
        assert mapper.tokens.heading_sizes[1] == 36

    def test_brief_tokens_mapper(self):
        """简报预设令牌的映射."""
        mapper = StyleMapper(brief_tokens())
        assert mapper.tokens.body_size == 10

    # ── 通用工具 ──

    def test_to_emu(self):
        """英寸 → EMU 转换."""
        mapper = StyleMapper(DesignTokens())
        assert mapper.to_emu(1.0) == 914400
        assert mapper.to_emu(0.5) == 457200

    def test_hex_to_rgb(self):
        """Hex → RGB 转换."""
        mapper = StyleMapper(DesignTokens())
        assert mapper.hex_to_rgb("#FF0000") == (255, 0, 0)
        assert mapper.hex_to_rgb("#00FF00") == (0, 255, 0)
        assert mapper.hex_to_rgb("#0000FF") == (0, 0, 255)
        assert mapper.hex_to_rgb("1A365D") == (26, 54, 93)

    def test_chart_colors(self):
        """图表颜色序列."""
        mapper = StyleMapper(DesignTokens())
        colors = mapper.chart_colors()
        assert len(colors) == 8
        assert colors[0] == "#1A365D"

    def test_chart_color_at(self):
        """图表颜色索引（循环）."""
        mapper = StyleMapper(DesignTokens())
        assert mapper.chart_color_at(0) == "#1A365D"
        assert mapper.chart_color_at(8) == "#1A365D"  # 循环
        assert mapper.chart_color_at(9) == "#2B6CB0"
