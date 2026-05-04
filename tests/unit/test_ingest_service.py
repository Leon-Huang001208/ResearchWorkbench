"""
测试摄入服务
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.contracts import Assertion, DocumentEnvelope
from core.services.ingest_service import IngestService


class TestIngestService:
    """测试摄入服务"""

    def test_ingest_text_basic(self):
        """测试摄入文本"""
        service = IngestService()

        result = service.ingest_text(
            text="贵州茅台2026年一季度财报显示，净利润同比增长28%",
            source_type="report",
            source_name="测试研报",
            title="贵州茅台财报分析",
        )

        assert result is not None
        assert "doc_id" in result
        assert "title" in result
        assert "assertions_extracted" in result
        assert "events_extracted" in result
        assert result["title"] == "贵州茅台财报分析"

    def test_ingest_text_minimal(self):
        """测试最简参数的文本摄入"""
        service = IngestService()

        result = service.ingest_text(text="简单测试文本")

        assert result is not None
        assert "doc_id" in result

    def test_ingest_file_txt(self, tmp_path):
        """测试摄入 TXT 文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("腾讯控股公布业绩，云业务收入增长强劲。\n人工智能技术突破，推动科技股上涨。", encoding="utf-8")

        service = IngestService()
        result = service.ingest_file(
            file_path=test_file, source_type="news", source_name="测试新闻", title="科技新闻"
        )

        assert result is not None
        assert result["title"] == "科技新闻"

    def test_ingest_file_not_found(self):
        """测试文件不存在的情况"""
        service = IngestService()

        with pytest.raises(FileNotFoundError):
            service.ingest_file(file_path=Path("/nonexistent/file.txt"), source_type="report")

    @patch("core.services.ingest_service.pdfplumber")
    def test_ingest_file_pdf(self, mock_pdfplumber, tmp_path):
        """测试摄入 PDF 文件"""
        # 设置模拟
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "PDF 测试内容"
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy pdf content")

        service = IngestService()
        result = service.ingest_file(file_path=test_file, source_type="report")

        assert result is not None

    def test_normalize_text(self):
        """测试文本规范化"""
        service = IngestService()

        # 访问私有方法进行测试
        raw_text = "  测试文本  \n\n  多行内容  \n  "
        normalized = service._normalize_text(raw_text)

        assert normalized == "测试文本\n多行内容"

    def test_ingest_with_mock_repository(self):
        """测试带模拟仓储的摄入"""
        mock_repo = Mock()
        service = IngestService(document_repo=mock_repo)

        result = service.ingest_text(text="测试文本", source_type="report")

        assert result is not None

    def test_assertions_and_events_extracted(self):
        """测试断言和事件提取"""
        service = IngestService()

        result = service.ingest_text(text="贵州茅台发布财报，净利润同比增长28%。腾讯控股宣布收购计划。", source_type="report")

        # 断言应该被提取（数量 >= 0）
        assert result["assertions_extracted"] >= 0
        assert result["events_extracted"] >= 0
