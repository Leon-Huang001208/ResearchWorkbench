"""测试 RawTextStrategy"""
import os
from unittest.mock import MagicMock, patch

import pytest

from ingestion.converters.raw_text import RawTextStrategy


class TestRawTextStrategy:
    """RawTextStrategy 测试"""

    def test_strategy_type(self):
        strategy = RawTextStrategy()
        assert strategy.name == "raw_text"
        assert strategy.strategy_type.value == "raw_text"

    def test_is_available(self):
        strategy = RawTextStrategy()
        # pdfplumber 应该在开发环境中可用
        assert strategy.is_available() is True

    @patch("pdfplumber.open")
    def test_convert_success(self, mock_pdfplumber_open):
        """测试成功提取文本（mock pdfplumber）"""
        # 设置 mock
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "第一页内容 测试文本"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "第二页内容 更多测试"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = False
        mock_pdfplumber_open.return_value = mock_pdf

        strategy = RawTextStrategy()
        result = strategy.convert("test.pdf")

        assert result.success is True
        assert result.strategy_used == "raw_text"
        assert "<!-- page: 1 -->" in result.raw_text
        assert "<!-- page: 2 -->" in result.raw_text
        assert "第一页内容 测试文本" in result.raw_text
        assert "第二页内容 更多测试" in result.raw_text
        assert result.page_count == 2
        assert result.token_count > 0
        assert result.quality_score is not None
        assert 0.0 <= result.quality_score <= 1.0

    @patch("pdfplumber.open")
    def test_convert_empty_page(self, mock_pdfplumber_open):
        """测试空页面处理"""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None  # 模拟空页面

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = False
        mock_pdfplumber_open.return_value = mock_pdf

        strategy = RawTextStrategy()
        result = strategy.convert("test.pdf")

        assert result.success is True
        assert result.page_count == 1
        assert "<!-- page: 1 -->" in result.raw_text

    @patch("pdfplumber.open")
    def test_convert_error(self, mock_pdfplumber_open):
        """测试 pdfplumber 错误时的降级处理"""
        mock_pdfplumber_open.side_effect = Exception("PDF 已损坏")

        strategy = RawTextStrategy()
        result = strategy.convert("damaged.pdf")

        assert result.success is False
        assert "PDF 已损坏" in result.error_message
        assert result.strategy_used == "raw_text"

    def test_convert_nonexistent_file(self):
        """测试不存在的文件"""
        strategy = RawTextStrategy()
        result = strategy.convert("/nonexistent/path/file.pdf")

        assert result.success is False
        assert result.strategy_used == "raw_text"

    def test_compute_quality_score_empty(self):
        score = RawTextStrategy._compute_quality_score("", 0)
        assert score == 0.0

    def test_compute_quality_score_rich(self):
        """富文本应得到较高评分"""
        # 构造较长、多页、含制表符的内容
        text = "这是测试内容" * 100 + "\t表格列1\t表格列2\n" + "数据" * 50
        score = RawTextStrategy._compute_quality_score(text, page_count=5)
        assert score > 0.5
        assert score <= 1.0

    def test_compute_quality_score_sparse(self):
        """稀疏文本评分较低"""
        text = "短文本"
        score = RawTextStrategy._compute_quality_score(text, page_count=10)
        assert score <= 0.6


class TestRawTextStrategyIntegration:
    """使用真实 PDF 的集成测试（标记为 integration）"""

    @pytest.mark.integration
    def test_with_real_pdf(self):
        """如果有样本 PDF，测试真实提取"""
        sample_pdf = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "fixtures", "sample.pdf"
        )
        if not os.path.exists(sample_pdf):
            pytest.skip("样本 PDF 不存在")

        strategy = RawTextStrategy()
        result = strategy.convert(sample_pdf)

        assert result.success is True
        assert result.page_count > 0
        assert len(result.raw_text) > 0
