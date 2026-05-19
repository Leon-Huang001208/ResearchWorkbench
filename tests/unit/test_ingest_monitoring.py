"""
测试 Ingest Monitoring API
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from data_layer.repositories.models import CrawlStateV1DB, PDFArtifactV1DB, ProcessedItemV1DB

client = TestClient(app)


class TestIngestMonitoringAPI:
    """测试摄入监控 API"""

    @patch("data_layer.repositories.crawl_state_repository.get_all_crawl_states")
    @patch("data_layer.repositories.pdf_artifact_repository.get_conversion_stats")
    def test_get_ingest_status(self, mock_get_stats, mock_get_all_states):
        """测试获取摄入状态概览"""
        # Arrange
        state_cls = CrawlStateV1DB(
            state_id="state_cls",
            source_type="cls",
            source_name="财联社",
            total_fetched=1250,
            total_skipped=42,
            total_failed=3,
            is_paused=False,
            last_run_end=datetime.utcnow() - timedelta(hours=1),
        )
        state_cnstock = CrawlStateV1DB(
            state_id="state_cnstock",
            source_type="cnstock",
            source_name="中国证券报",
            total_fetched=850,
            total_skipped=25,
            total_failed=1,
            is_paused=False,
            last_run_end=datetime.utcnow() - timedelta(hours=2),
        )
        state_zq = CrawlStateV1DB(
            state_id="state_zq",
            source_type="zq",
            source_name="知丘",
            total_fetched=180,
            total_skipped=8,
            total_failed=0,
            is_paused=False,
            last_run_end=datetime.utcnow() - timedelta(minutes=30),
        )
        mock_get_all_states.return_value = [state_cls, state_cnstock, state_zq]
        mock_get_stats.return_value = {
            "total_pdfs": 256,
            "pending_conversion": 12,
            "converted": 244,
            "failed_conversion": 0,
            "by_status": {"success": 244, "pending": 12},
        }

        # Act
        resp = client.get("/api/monitoring/ingest/status")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert "pdf_stats" in data
        assert "overall_health" in data
        assert "generated_at" in data

    @patch("data_layer.repositories.crawl_state_repository.get_crawl_state")
    def test_get_source_status(self, mock_get_state):
        """测试获取特定来源状态"""
        # Arrange
        state_cls = CrawlStateV1DB(
            state_id="state_cls",
            source_type="cls",
            source_name="财联社",
            watermark_id="news_12345",
            watermark_timestamp=datetime.utcnow() - timedelta(hours=1),
            total_fetched=1250,
            total_skipped=42,
            total_failed=3,
            is_paused=False,
        )
        mock_get_state.return_value = state_cls

        # Act
        resp = client.get("/api/monitoring/ingest/sources/cls")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "cls"
        assert data["status"] == "running"
        assert data["total_fetched"] == 1250

    @patch("data_layer.repositories.crawl_state_repository.get_crawl_state")
    def test_get_source_status_not_found(self, mock_get_state):
        """测试获取不存在的来源状态"""
        # Arrange
        mock_get_state.return_value = None

        # Act
        resp = client.get("/api/monitoring/ingest/sources/nonexistent")

        # Assert
        assert resp.status_code == 200  # 返回默认状态
        data = resp.json()
        assert data["source_type"] == "nonexistent"
        assert data["status"] == "unknown"

    @patch("data_layer.repositories.processed_item_repository.get_processed_stats")
    @patch("data_layer.repositories.processed_item_repository.get_processed_stats_by_day")
    def test_get_processed_stats(self, mock_get_daily, mock_get_stats):
        """测试获取已处理统计"""
        # Arrange
        mock_get_stats.return_value = {
            "total_items": 2280,
            "by_source_type": {"cls": 1250, "cnstock": 850, "zq": 180},
        }
        mock_get_daily.return_value = []

        # Act
        resp = client.get("/api/monitoring/ingest/processed")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 2280
        assert "by_source_type" in data

    @patch("data_layer.repositories.processed_item_repository.get_recent_processed")
    def test_get_recent_processed(self, mock_get_recent):
        """测试获取最近处理的项目"""
        # Arrange
        item1 = ProcessedItemV1DB(
            item_id="item_123",
            source_type="cls",
            item_type="news",
            title="测试新闻1",
            content_hash="abc123",
            first_seen_at=datetime.utcnow() - timedelta(minutes=30),
            process_count=1,
        )
        item2 = ProcessedItemV1DB(
            item_id="item_456",
            source_type="cls",
            item_type="news",
            title="测试新闻2",
            content_hash="def456",
            first_seen_at=datetime.utcnow() - timedelta(hours=1),
            process_count=1,
        )
        mock_get_recent.return_value = [item1, item2]

        # Act
        resp = client.get("/api/monitoring/ingest/processed/cls/recent?limit=10")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["item_id"] == "item_123"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdfs_by_source")
    def test_get_pdfs_by_source(self, mock_get_pdfs):
        """测试获取指定来源的 PDFs"""
        # Arrange
        pdf1 = PDFArtifactV1DB(
            pdf_id="pdf_123",
            source_type="zq",
            file_path="/data/pdfs/report1.pdf",
            file_name="report1.pdf",
            file_size_bytes=123456,
            file_hash_sha256="abc123",
            fetch_timestamp=datetime.utcnow() - timedelta(hours=2),
            parse_status="success",
        )
        mock_get_pdfs.return_value = [pdf1]

        # Act
        resp = client.get("/api/monitoring/ingest/pdfs?source_type=zq&limit=10")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["pdf_id"] == "pdf_123"

    @patch("data_layer.repositories.pdf_artifact_repository.get_pdfs_by_source")
    def test_get_pdfs_all_sources(self, mock_get_pdfs):
        """测试获取所有来源的 PDFs"""
        # Arrange
        pdf1 = PDFArtifactV1DB(
            pdf_id="pdf_123",
            source_type="zq",
            file_path="/data/pdfs/report1.pdf",
            file_name="report1.pdf",
            file_size_bytes=123456,
            file_hash_sha256="abc123",
            fetch_timestamp=datetime.utcnow() - timedelta(hours=2),
            parse_status="success",
        )
        mock_get_pdfs.return_value = [pdf1]

        # Act
        resp = client.get("/api/monitoring/ingest/pdfs?limit=10")

        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
