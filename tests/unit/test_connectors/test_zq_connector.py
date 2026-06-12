"""ZQ DocumentConnector 集成测试 — 使用 mock 验证完整生命周期."""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.document.zq import ZQDocumentConnector
from core.connectors.base import DiscoveryItem, ParsedDocument, RawObject
from core.contracts.ingestion_record import (
    AssetType,
    EntityType,
    HealthStatus,
    IngestionRecord,
    IngestionStatus,
    NewsPayload,
)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_report_envelopes():
    """构造两条模拟知丘研报 DocumentEnvelope."""
    return [
        {
            "doc_id": "zq-rpt-001",
            "source_type": "report",
            "title": "新能源行业2026年度策略",
            "published_at": "2026-06-01T08:00:00",
            "source_name": "中信证券",
            "language": "zh",
            "metadata": {"obj_id": "rpt001", "doc_type": "report"},
            "raw_text": '{"OBJID": "rpt001", "title": "新能源行业2026年度策略"}',
            "canonical_text": "新能源行业2026年展望：光伏装机超预期，储能需求爆发。",
        },
        {
            "doc_id": "zq-rpt-002",
            "source_type": "report",
            "title": "半导体设备国产化专题",
            "published_at": "2026-06-01T09:00:00",
            "source_name": "华泰证券",
            "language": "zh",
            "metadata": {"obj_id": "rpt002", "doc_type": "report"},
            "raw_text": '{"OBJID": "rpt002", "title": "半导体设备国产化专题"}',
            "canonical_text": "半导体设备国产化加速，刻蚀、薄膜沉积设备率先突破。",
        },
    ]


@pytest.fixture
def zq_connector():
    return ZQDocumentConnector()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestZQHealthCheck:
    def test_healthy(self, zq_connector):
        result = zq_connector.health_check()
        assert result in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE)
        assert zq_connector._health != HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestZQDiscover:
    def test_report_with_date_range(self, zq_connector):
        items = zq_connector.discover(
            dataset="report",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert len(items) == 1
        assert items[0].item_type == "report"
        assert "知丘研报" in items[0].description

    def test_news_with_search(self, zq_connector):
        items = zq_connector.discover(
            dataset="news",
            start_date="2026-01-01",
            end_date="2026-01-31",
            search="新能源",
        )
        assert len(items) == 1
        assert items[0].item_type == "news"
        assert items[0].params["search"] == "新能源"

    def test_meeting_with_days(self, zq_connector):
        items = zq_connector.discover(dataset="meeting", days=7)
        assert len(items) == 1
        assert items[0].item_type == "meeting"

    def test_report_incremental(self, zq_connector):
        items = zq_connector.discover(dataset="report")
        assert len(items) == 1
        assert "incremental" in items[0].item_id.lower()

    def test_unknown_dataset(self, zq_connector):
        items = zq_connector.discover(dataset="unknown")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestZQFetch:
    def test_fetch_respects_connector_config(self, sample_report_envelopes):
        zq_connector = ZQDocumentConnector(
            {"use_homepage_search": False, "enable_pdf": True, "max_pages": 7}
        )

        with patch("data_layer.adapters.zq_adapter.ZQAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_report_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="zq_report_2026-06-07_2026-06-09",
                item_type="report",
                params={
                    "start_date": "2026-06-07",
                    "end_date": "2026-06-09",
                    "doc_type": "REPORT",
                },
            )

            zq_connector.fetch(dataset="report", item=item)

            _, kwargs = mock_adapter.fetch.call_args
            assert kwargs["use_homepage_search"] is False
            assert kwargs["enable_pdf"] is True
            assert kwargs["max_pages"] == 7

    def test_fetch_report(self, zq_connector, sample_report_envelopes):
        with patch("data_layer.adapters.zq_adapter.ZQAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_report_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="zq_report_2026-01-01_2026-01-31",
                item_type="report",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "doc_type": "REPORT",
                },
            )
            raw = zq_connector.fetch(dataset="report", item=item)
            assert isinstance(raw, RawObject)
            assert raw.content_type == "application/json"
            assert "zq://report/" in raw.source_uri
            assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_dataset_raises(self, zq_connector):
        item = DiscoveryItem(item_id="bad", item_type="bad", params={})
        with pytest.raises(ValueError, match="Unknown dataset"):
            zq_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------


class TestZQParseDocument:
    def test_parse_reports(self, zq_connector, sample_report_envelopes):
        raw = RawObject(
            data=json.dumps(sample_report_envelopes, ensure_ascii=False),
            content_type="application/json",
            source_uri="zq://report/2026-01-01",
            metadata={
                "item_type": "report",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "doc_type": "REPORT",
            },
        )
        doc = zq_connector.parse_document(raw)
        assert isinstance(doc, ParsedDocument)
        assert "知丘研报" in doc.title
        assert "2 篇" in doc.title
        assert "新能源" in doc.text or "半导体" in doc.text
        assert doc.pages == 2

    def test_parse_empty(self, zq_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="zq://report/empty",
            metadata={"start_date": "2026-01-01"},
        )
        doc = zq_connector.parse_document(raw)
        assert doc.text == ""
        assert doc.pages is None


# ---------------------------------------------------------------------------
# normalize_metadata
# ---------------------------------------------------------------------------


class TestZQNormalizeMetadata:
    def test_normalize_report(self, zq_connector):
        parsed = ParsedDocument(
            title="知丘研报 2026-01-01 (2 篇)",
            text="新能源策略\n\n---\n\n半导体专题",
            pages=2,
            file_type="json",
            metadata={
                "individual_titles": ["新能源行业2026年度策略", "半导体设备国产化专题"],
                "document_count": 2,
                "doc_type": "REPORT",
            },
        )
        record = zq_connector.normalize_metadata(
            dataset="report",
            parsed=parsed,
            raw_uri="zq://report/test",
            content_hash="abc123",
        )
        assert isinstance(record, IngestionRecord)
        assert record.source == "zq"
        assert record.dataset == "report"
        assert record.asset_type == AssetType.DOCUMENT
        assert record.payload["source_name"] == "知丘研报"
        assert "zq" in record.payload["tags"]
        assert "研报" in record.payload["tags"]


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


class TestZQPersist:
    def test_persist_empty(self, zq_connector):
        result = zq_connector.persist([])
        assert result == 0

    def test_persist_enqueues(self, zq_connector):
        record = IngestionRecord(
            source="zq",
            dataset="report",
            asset_type=AssetType.DOCUMENT,
            entity_type=EntityType.UNKNOWN,
            published_at=datetime(2026, 6, 1, 10, 30),
            raw_uri="zq://report/test",
            content_hash="abc123",
            payload=NewsPayload(
                title="测试研报",
                content="研报正文内容。",
                source_name="知丘研报",
            ).model_dump(),
        )

        with patch("data_layer.repositories.base.db_session") as mock_db_session_class, patch(
            "data_layer.repositories.ingestion_repository.IngestionQueueRepository"
        ) as mock_repo_class, patch(
            "services.ingestion_queue_service.IngestionQueueService"
        ) as mock_service_class:
            mock_db = MagicMock()
            mock_db_session_class.return_value.__enter__.return_value = mock_db

            mock_repo = MagicMock()
            mock_repo_class.return_value = mock_repo

            mock_service = MagicMock()
            mock_service.enqueue.return_value = {
                "item_id": "test-001",
                "dedup_hash": "hash123",
                "was_duplicate": False,
                "message": "enqueued",
            }
            mock_service_class.return_value = mock_service

            result = zq_connector.persist([record])
            assert result == 1
            mock_service.enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestZQRun:
    def test_run_report_full_lifecycle(self, zq_connector, sample_report_envelopes):
        with patch("data_layer.adapters.zq_adapter.ZQAdapter") as mock_adapter_class, patch.object(
            zq_connector, "persist", return_value=1
        ):
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_report_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            result = zq_connector.run(
                dataset="report",
                start_date="2026-01-01",
                end_date="2026-01-31",
            )
            assert result.source == "zq"
            assert result.dataset == "report"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1

    def test_run_unknown_dataset(self, zq_connector):
        result = zq_connector.run(dataset="unknown")
        assert result.status == IngestionStatus.COMPLETED
        assert result.stats.discovered == 0
