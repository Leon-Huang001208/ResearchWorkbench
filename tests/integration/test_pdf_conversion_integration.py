"""PDF 转换集成测试 —— 使用真实 sample PDF"""

import os

import pytest

from ingestion.converters.raw_text import RawTextStrategy


@pytest.mark.integration
class TestPdfIntegration:
    """使用真实 PDF 文件的集成测试"""

    @pytest.fixture
    def sample_pdf_path(self):
        """sample PDF 文件路径"""
        return os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample.pdf")

    def test_raw_text_conversion_with_real_pdf(self, sample_pdf_path):
        """RawTextStrategy 能成功转换真实 PDF"""
        assert os.path.exists(sample_pdf_path), f"Sample PDF not found: {sample_pdf_path}"

        strategy = RawTextStrategy()
        result = strategy.convert(sample_pdf_path)

        assert result.success is True
        assert result.strategy_used == "raw_text"
        assert result.page_count >= 1
        assert len(result.raw_text) > 0
        assert "Research Workbench" in result.raw_text
        assert "<!-- page: 1 -->" in result.raw_text
        assert result.token_count > 0
        assert result.quality_score is not None
        assert 0.0 <= result.quality_score <= 1.0

    def test_real_pdf_has_expected_content(self, sample_pdf_path):
        """真实 PDF 包含预期内容"""
        strategy = RawTextStrategy()
        result = strategy.convert(sample_pdf_path)

        assert result.success is True
        # 验证关键内容存在
        assert "Chapter 1" in result.raw_text or "Market Overview" in result.raw_text
        assert "Chapter 2" in result.raw_text or "Sector Analysis" in result.raw_text

    def test_real_pdf_quality_score_reasonable(self, sample_pdf_path):
        """真实 PDF 的质量评分应在合理范围内"""
        strategy = RawTextStrategy()
        result = strategy.convert(sample_pdf_path)

        assert result.success is True
        # 合理内容应有 > 0.2 的质量评分
        assert result.quality_score > 0.2


@pytest.mark.integration
class TestPdfToMarkdownIntegration:
    """MarkItDown 集成测试（如果已安装）"""

    def test_markitdown_conversion_if_available(self):
        """如果 markitdown 可用，测试真实 PDF 转换"""
        from ingestion.converters.markitdown import HAS_MARKITDOWN, MarkItDownStrategy

        if not HAS_MARKITDOWN:
            pytest.skip("markitdown 未安装")

        sample_pdf = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample.pdf")
        assert os.path.exists(sample_pdf)

        strategy = MarkItDownStrategy()
        result = strategy.convert(sample_pdf)

        assert result.success is True
        assert result.strategy_used == "markitdown"
        assert len(result.markdown) > 0
        assert result.token_count > 0
        assert result.quality_score is not None
