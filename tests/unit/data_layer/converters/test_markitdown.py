"""测试 MarkItDownStrategy"""

from unittest.mock import MagicMock, patch

import pytest

from ingestion.converters.markitdown import MarkItDownStrategy


class TestMarkItDownStrategy:
    """MarkItDownStrategy 测试"""

    def test_strategy_type(self):
        strategy = MarkItDownStrategy()
        assert strategy.name == "markitdown"
        assert strategy.strategy_type.value == "markitdown"

    def test_is_available_depends_on_import(self):
        """is_available 取决于 markitdown 是否已安装"""
        strategy = MarkItDownStrategy()
        # 在测试环境中 markitdown 可能未安装
        result = strategy.is_available()
        assert isinstance(result, bool)

    def test_convert_when_not_installed(self):
        """未安装 markitdown 时应返回错误"""
        if MarkItDownStrategy().is_available():
            pytest.skip("markitdown 已安装，跳过此测试")

        strategy = MarkItDownStrategy()
        result = strategy.convert("test.pdf")

        assert result.success is False
        assert "未安装" in result.error_message

    def test_add_page_anchors_no_formfeed(self):
        """无换页符时原样返回"""
        md = "# Title\n\nContent without page breaks"
        result = MarkItDownStrategy._add_page_anchors(md)
        assert result == md

    def test_add_page_anchors_already_has_anchors(self):
        """已有锚点时不再重复添加"""
        md = "<!-- page: 1 -->\n# Title\n\n\f<!-- page: 2 -->\nMore content"
        result = MarkItDownStrategy._add_page_anchors(md)
        assert result == md

    def test_add_page_anchors_with_formfeed(self):
        """有换页符时添加锚点"""
        md = "# Page 1 Content\n\n\f# Page 2 Content\n\n\f# Page 3 Content"
        result = MarkItDownStrategy._add_page_anchors(md)
        assert "<!-- page: 1 -->" in result
        assert "<!-- page: 2 -->" in result
        assert "<!-- page: 3 -->" in result

    def test_detect_features_tables(self):
        md = "| Column A | Column B |\n|----------|----------|\n| Data 1   | Data 2   |"
        features = MarkItDownStrategy._detect_features(md)
        assert features["has_tables"] is True
        assert features.get("table_rows", 0) > 0

    def test_detect_features_images(self):
        md = "# Report\n\n![Chart](chart.png)\n\nText"
        features = MarkItDownStrategy._detect_features(md)
        assert features["has_images"] is True

    def test_detect_features_code_blocks(self):
        md = "# Code\n\n```python\nprint('hello')\n```"
        features = MarkItDownStrategy._detect_features(md)
        assert features["has_code_blocks"] is True

    def test_detect_features_none(self):
        md = "Plain text only, no special elements"
        features = MarkItDownStrategy._detect_features(md)
        assert features["has_tables"] is False
        assert features["has_images"] is False
        assert features["has_code_blocks"] is False

    def test_compute_quality_score_empty(self):
        score = MarkItDownStrategy._compute_quality_score("", {})
        assert score == 0.0

    def test_compute_quality_score_rich(self):
        md = (
            "# Main Title\n\n"
            + "## Section 1\n\n"
            + "### Subsection 1.1\n\n"
            + "#### Detail\n\n"
            + "Rich content " * 200
            + "\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        features = {"has_tables": True}
        score = MarkItDownStrategy._compute_quality_score(md, features)
        assert score > 0.7
        assert score <= 1.0


class TestMarkItDownStrategyWithMock:
    """使用 mock MarkItDown 的测试"""

    @patch("ingestion.converters.markitdown.HAS_MARKITDOWN", True)
    def test_convert_success(self):
        """测试成功转换"""
        import ingestion.converters.markitdown as md_module

        mock_result = MagicMock()
        mock_result.text_content = "# Test Report\n\nContent of the report"
        mock_instance = MagicMock()
        mock_instance.convert.return_value = mock_result
        md_module.MarkItDown = MagicMock(return_value=mock_instance)

        strategy = MarkItDownStrategy()
        result = strategy.convert("test.pdf")

        assert result.success is True
        assert result.strategy_used == "markitdown"
        assert "# Test Report" in result.markdown
        assert result.token_count > 0
        assert result.quality_score is not None

    @patch("ingestion.converters.markitdown.HAS_MARKITDOWN", True)
    def test_convert_error(self):
        """测试 MarkItDown 抛出异常时返回错误"""
        import ingestion.converters.markitdown as md_module

        mock_instance = MagicMock()
        mock_instance.convert.side_effect = Exception("Conversion failed")
        md_module.MarkItDown = MagicMock(return_value=mock_instance)

        strategy = MarkItDownStrategy()
        result = strategy.convert("error.pdf")

        assert result.success is False
        assert "Conversion failed" in result.error_message
