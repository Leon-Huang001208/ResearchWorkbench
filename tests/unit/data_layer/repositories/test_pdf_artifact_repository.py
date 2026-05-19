"""
测试 PDF Artifact Repository
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from data_layer.repositories.models import PDFArtifactV1DB, PDFConversionV1DB


@pytest.fixture
def sample_pdf_artifact():
    """样例 PDF 制品"""
    return PDFArtifactV1DB(
        pdf_id="pdf_123",
        doc_id="doc_123",
        source_obj_id="report_456",
        file_path="/data/pdfs/report_456.pdf",
        file_name="2026Q1_某某证券_某某公司_深度报告.pdf",
        file_size_bytes=1234567,
        file_hash_sha256="abc123def456789abc",
        file_hash_md5="def456abc",
        source_type="zq",
        source_name="知丘",
        source_url="https://example.com/report/456",
        source_broker="某某证券",
        source_author="某某分析师",
        source_publish_date=datetime.utcnow() - timedelta(days=7),
        fetch_timestamp=datetime.utcnow() - timedelta(hours=1),
        fetch_config={"retry": 3},
        fetch_strategy="pdf_first",
        fetch_duration_ms=2500,
        parse_version="1.0",
        parse_config={"enable_ocr": False},
        parse_status="success",
        parse_error=None,
        parsed_at=datetime.utcnow() - timedelta(minutes=55),
        pdf_metadata={"pages": 25, "title": "深度报告"},
        extra={},
        created_at=datetime.utcnow() - timedelta(hours=1),
        updated_at=datetime.utcnow() - timedelta(minutes=55),
    )


@pytest.fixture
def sample_pdf_conversion():
    """样例 PDF 转换"""
    return PDFConversionV1DB(
        conversion_id="conv_123",
        pdf_id="pdf_123",
        conversion_strategy="markitdown",
        strategy_version="0.1.0",
        strategy_config={"markdown": True},
        markdown_path="/data/markdown/report_456.md",
        markdown_content=None,
        raw_text_path="/data/raw/report_456.txt",
        raw_text_content=None,
        page_count=25,
        token_count=5200,
        conversion_duration_ms=3200,
        quality_score=0.92,
        has_tables=True,
        has_images=False,
        has_code_blocks=False,
        status="success",
        error_log=None,
        created_at=datetime.utcnow() - timedelta(minutes=55),
        completed_at=datetime.utcnow() - timedelta(minutes=55),
    )


class TestPDFArtifactRepository:
    """测试 PDF 制品仓储"""

    @patch("data_layer.repositories.pdf_artifact_repository.add_pdf_artifact")
    def test_add_pdf_artifact(self, mock_add, db_session, sample_pdf_artifact):
        """测试添加 PDF 制品"""
        # Arrange
        mock_add.return_value = sample_pdf_artifact

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.add_pdf_artifact(db_session, sample_pdf_artifact)

        # Assert
        assert result is not None
        assert result.pdf_id == "pdf_123"
        assert result.source_type == "zq"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdf_by_id")
    def test_get_pdf_by_id(self, mock_get, db_session, sample_pdf_artifact):
        """测试通过 ID 获取"""
        # Arrange
        mock_get.return_value = sample_pdf_artifact

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.get_pdf_by_id(db_session, "pdf_123")

        # Assert
        assert result is not None
        assert result.pdf_id == "pdf_123"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdf_by_doc_id")
    def test_get_pdf_by_doc_id(self, mock_get_doc, db_session, sample_pdf_artifact):
        """测试通过文档 ID 获取"""
        # Arrange
        mock_get_doc.return_value = sample_pdf_artifact

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.get_pdf_by_doc_id(db_session, "doc_123")

        # Assert
        assert result is not None
        assert result.doc_id == "doc_123"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdf_by_hash")
    def test_get_pdf_by_hash(self, mock_get_hash, db_session, sample_pdf_artifact):
        """测试通过哈希获取"""
        # Arrange
        mock_get_hash.return_value = sample_pdf_artifact

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.get_pdf_by_hash(db_session, "abc123def456789abc")

        # Assert
        assert result is not None
        assert result.file_hash_sha256 == "abc123def456789abc"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdfs_by_source")
    def test_get_pdfs_by_source(self, mock_get_source, db_session, sample_pdf_artifact):
        """测试按来源获取"""
        # Arrange
        mock_get_source.return_value = [sample_pdf_artifact]

        # Act
        from data_layer.repositories import pdf_artifact_repository

        results = pdf_artifact_repository.get_pdfs_by_source(db_session, "zq", limit=10)

        # Assert
        assert len(results) == 1
        assert results[0].source_type == "zq"

    @patch("data_layer.repositories.pdf_artifact_repository.add_conversion")
    def test_add_conversion(self, mock_add_conv, db_session, sample_pdf_conversion):
        """测试添加转换记录"""
        # Arrange
        mock_add_conv.return_value = sample_pdf_conversion

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.add_conversion(db_session, sample_pdf_conversion)

        # Assert
        assert result is not None
        assert result.conversion_id == "conv_123"
        assert result.status == "success"

    @patch("data_layer.repositories.pdf_artifact_repository.update_conversion_status")
    def test_update_conversion_status(self, mock_update, db_session, sample_pdf_conversion):
        """测试更新转换状态"""
        # Arrange
        sample_pdf_conversion.status = "error"
        sample_pdf_conversion.error_log = "Failed to parse"
        mock_update.return_value = sample_pdf_conversion

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.update_conversion_status(
            db_session, "conv_123", "error", error_log="Failed to parse"
        )

        # Assert
        assert result is not None
        assert result.status == "error"
        assert result.error_log == "Failed to parse"

    @patch("data_layer.repositories.pdf_artifact_repository.get_conversion_stats")
    def test_get_conversion_stats(self, mock_get_stats, db_session):
        """测试获取转换统计"""
        # Arrange
        mock_get_stats.return_value = {
            "total_pdfs": 256,
            "pending_conversion": 12,
            "converted": 244,
            "failed_conversion": 0,
            "by_status": {"success": 244, "pending": 12},
        }

        # Act
        from data_layer.repositories import pdf_artifact_repository

        result = pdf_artifact_repository.get_conversion_stats(db_session)

        # Assert
        assert result["total_pdfs"] == 256
        assert result["converted"] == 244

    @patch("data_layer.repositories.pdf_artifact_repository.get_pending_conversions")
    def test_get_pending_conversions(self, mock_get_pending, db_session, sample_pdf_conversion):
        """测试获取待处理的转换"""
        # Arrange
        sample_pdf_conversion.status = "pending"
        mock_get_pending.return_value = [sample_pdf_conversion]

        # Act
        from data_layer.repositories import pdf_artifact_repository

        results = pdf_artifact_repository.get_pending_conversions(db_session, limit=10)

        # Assert
        assert len(results) == 1
        assert results[0].status == "pending"
