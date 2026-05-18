"""测试 PDF Conversion Admin API"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestPdfAdminAPI:
    """测试 PDF 转换管理 API"""

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_convert_pdf_success(self, mock_service_class):
        """POST /api/admin/pdf/convert 成功"""
        mock_service = MagicMock()
        mock_service.convert_pdf.return_value = MagicMock(
            success=True,
            strategy_used="mineru",
            error_message="",
            page_count=5,
            token_count=1000,
            quality_score=0.85,
            has_tables=True,
            has_images=False,
            has_code_blocks=True,
        )
        mock_service_class.return_value = mock_service

        resp = client.post(
            "/api/admin/pdf/convert",
            json={"pdf_id": "pdf_001", "strategy": "auto"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["strategy_used"] == "mineru"
        assert data["page_count"] == 5
        assert data["has_tables"] is True

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_convert_pdf_failure(self, mock_service_class):
        """POST /api/admin/pdf/convert 失败"""
        mock_service = MagicMock()
        mock_service.convert_pdf.return_value = MagicMock(
            success=False,
            strategy_used="",
            error_message="PDF artifact 不存在: bad_id",
            page_count=0,
            token_count=0,
            quality_score=None,
            has_tables=False,
            has_images=False,
            has_code_blocks=False,
        )
        mock_service_class.return_value = mock_service

        resp = client.post(
            "/api/admin/pdf/convert",
            json={"pdf_id": "bad_id"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "不存在" in data["error_message"]

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_get_stats(self, mock_service_class):
        """GET /api/admin/pdf/stats"""
        mock_service = MagicMock()
        mock_service.get_stats.return_value = {
            "total_pdfs": 10,
            "pending_conversion": 3,
            "converted": 5,
            "failed_conversion": 2,
            "by_status": {"success": 5, "error": 2, "pending": 3},
        }
        mock_service_class.return_value = mock_service

        resp = client.get("/api/admin/pdf/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pdfs"] == 10
        assert data["pending_conversion"] == 3
        assert data["converted"] == 5

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_get_pending(self, mock_service_class):
        """GET /api/admin/pdf/pending"""
        mock_pending = MagicMock()
        mock_pending.pdf_id = "pdf_001"
        mock_pending.file_name = "report.pdf"
        mock_pending.source_type = "zhiqiu"
        mock_pending.conversion_strategy = "mineru"
        mock_pending.status = "pending"
        mock_pending.created_at = None

        mock_service = MagicMock()
        mock_service.get_pending.return_value = [mock_pending]
        mock_service_class.return_value = mock_service

        resp = client.get("/api/admin/pdf/pending?limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["pdf_id"] == "pdf_001"

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_get_pending_empty(self, mock_service_class):
        """GET /api/admin/pdf/pending 空列表"""
        mock_service = MagicMock()
        mock_service.get_pending.return_value = []
        mock_service_class.return_value = mock_service

        resp = client.get("/api/admin/pdf/pending")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["items"] == []

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_retry_failed(self, mock_service_class):
        """POST /api/admin/pdf/retry"""
        mock_service = MagicMock()
        mock_service.retry_failed.return_value = [
            MagicMock(
                success=True,
                strategy_used="mineru",
                error_message="",
                page_count=3,
                token_count=500,
                quality_score=0.9,
                has_tables=True,
                has_images=False,
                has_code_blocks=False,
            ),
            MagicMock(
                success=False,
                strategy_used="raw_text",
                error_message="Conversion failed",
                page_count=0,
                token_count=0,
                quality_score=None,
                has_tables=False,
                has_images=False,
                has_code_blocks=False,
            ),
        ]
        mock_service_class.return_value = mock_service

        resp = client.post("/api/admin/pdf/retry", json={"limit": 5})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["success"] == 1
        assert data["failed"] == 1

    @patch("app.api.routes.pdf_admin.PDFConversionService")
    def test_retry_failed_empty(self, mock_service_class):
        """POST /api/admin/pdf/retry 无失败项"""
        mock_service = MagicMock()
        mock_service.retry_failed.return_value = []
        mock_service_class.return_value = mock_service

        resp = client.post("/api/admin/pdf/retry", json={"limit": 10})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["success"] == 0