"""Cninfo DocumentConnector 集成测试 — 使用 mock 验证完整生命周期."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.document.cninfo import CninfoDocumentConnector
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
def sample_envelopes():
    """构造两条模拟 cninfo DocumentEnvelope."""
    return [
        {
            "doc_id": "cninfo-hash-001",
            "source_type": "filing",
            "title": "2025年年度报告",
            "published_at": "2026-06-01T10:00:00",
            "source_name": "巨潮资讯网",
            "language": "zh",
            "metadata": {
                "sec_code": "600519",
                "sec_name": "贵州茅台",
                "adjunct_url": "https://static.cninfo.com.cn/finalpage/2026-06-01/12345.PDF",
                "announcement_type": "",
                "announcement_id": "12345",
            },
            "raw_text": "【600519 贵州茅台】2025年年度报告 (2026-06-01 10:00:00)",
            "canonical_text": "【600519 贵州茅台】2025年年度报告 (2026-06-01 10:00:00)",
        },
        {
            "doc_id": "cninfo-hash-002",
            "source_type": "filing",
            "title": "2025年半年度报告",
            "published_at": "2026-06-01T08:00:00",
            "source_name": "巨潮资讯网",
            "language": "zh",
            "metadata": {
                "sec_code": "000858",
                "sec_name": "五粮液",
                "adjunct_url": "https://static.cninfo.com.cn/finalpage/2026-06-01/12346.PDF",
                "announcement_type": "",
                "announcement_id": "12346",
            },
            "raw_text": "【000858 五粮液】2025年半年度报告 (2026-06-01 08:00:00)",
            "canonical_text": "【000858 五粮液】2025年半年度报告 (2026-06-01 08:00:00)",
        },
    ]


@pytest.fixture
def cninfo_connector():
    return CninfoDocumentConnector()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestCninfoHealthCheck:
    def test_healthy(self, cninfo_connector):
        result = cninfo_connector.health_check()
        assert result in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE)
        assert cninfo_connector._health != HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestCninfoDiscover:
    def test_announcements_with_date_range(self, cninfo_connector):
        items = cninfo_connector.discover(
            dataset="announcements",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert len(items) == 1
        assert items[0].item_type == "announcements"
        assert "2026-01-01" in items[0].description
        assert "2026-01-31" in items[0].description

    def test_announcements_with_plate(self, cninfo_connector):
        items = cninfo_connector.discover(
            dataset="announcements",
            start_date="2026-01-01",
            end_date="2026-01-31",
            plate="szse",
        )
        assert len(items) == 1
        assert items[0].params["plate"] == "szse"
        assert items[0].params["column"] == "szse"
        assert "szse" in items[0].description

    def test_unknown_dataset(self, cninfo_connector):
        items = cninfo_connector.discover(dataset="unknown")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestCninfoFetch:
    def test_fetch_announcements(self, cninfo_connector, sample_envelopes):
        with patch("data_layer.adapters.cninfo_adapter.CninfoAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="cninfo_szse_all_2026-01-01_2026-01-31",
                item_type="announcements",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "plate": "szse",
                    "column": "szse",
                    "category": "",
                    "stock": "",
                },
            )
            raw = cninfo_connector.fetch(dataset="announcements", item=item)
            assert isinstance(raw, RawObject)
            assert raw.content_type == "application/json"
            assert "cninfo://announcements/" in raw.source_uri
            assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_dataset_raises(self, cninfo_connector):
        item = DiscoveryItem(
            item_id="cninfo_test",
            item_type="unknown",
            params={},
        )
        with pytest.raises(ValueError, match="Unknown dataset"):
            cninfo_connector.fetch(dataset="unknown", item=item)

    def test_fetch_passes_attachment_text_options(
        self, cninfo_connector, sample_envelopes, tmp_path
    ):
        with patch("data_layer.adapters.cninfo_adapter.CninfoAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_envelopes[:1]
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="cninfo_szse_all_2026-01-01_2026-01-31",
                item_type="announcements",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "plate": "szse",
                    "column": "szse",
                    "category": "",
                    "stock": "",
                },
            )

            cninfo_connector.fetch(
                dataset="announcements",
                item=item,
                fetch_attachment_text=True,
                attachment_output_dir=str(tmp_path),
                max_attachment_bytes=2048,
                trust_env=True,
            )

            call_kwargs = mock_adapter.fetch.call_args.kwargs
            assert call_kwargs["fetch_attachment_text"] is True
            assert call_kwargs["attachment_output_dir"] == str(tmp_path)
            assert call_kwargs["max_attachment_bytes"] == 2048
            assert call_kwargs["trust_env"] is True


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------


class TestCninfoParseDocument:
    def test_parse(self, cninfo_connector, sample_envelopes):
        raw = RawObject(
            data=json.dumps(sample_envelopes, ensure_ascii=False),
            content_type="application/json",
            source_uri="cninfo://announcements/szse/2026-01-01_to_2026-01-31",
            metadata={
                "item_type": "announcements",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "plate": "szse",
            },
        )
        doc = cninfo_connector.parse_document(raw)
        assert isinstance(doc, ParsedDocument)
        assert "巨潮资讯网" in doc.title
        assert "szse" in doc.title
        assert "2 条" in doc.title
        assert "贵州茅台" in doc.text or "五粮液" in doc.text
        assert doc.pages == 2

    def test_parse_empty(self, cninfo_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="cninfo://announcements/empty",
            metadata={"start_date": "2026-01-01"},
        )
        doc = cninfo_connector.parse_document(raw)
        assert doc.text == ""
        assert doc.pages is None


# ---------------------------------------------------------------------------
# normalize_metadata
# ---------------------------------------------------------------------------


class TestCninfoNormalizeMetadata:
    def test_normalize(self, cninfo_connector):
        parsed = ParsedDocument(
            title="巨潮资讯网 [szse] 公告 2026-01-01 → 2026-01-31 (2 条)",
            text="【600519 贵州茅台】2025年年度报告\n\n【000858 五粮液】2025年半年度报告",
            pages=2,
            file_type="json",
            metadata={
                "individual_titles": ["2025年年度报告", "2025年半年度报告"],
                "announcement_count": 2,
                "plate": "szse",
            },
        )
        record = cninfo_connector.normalize_metadata(
            dataset="announcements",
            parsed=parsed,
            raw_uri="cninfo://announcements/test",
            content_hash="abc123",
        )
        assert isinstance(record, IngestionRecord)
        assert record.source == "cninfo"
        assert record.dataset == "announcements"
        assert record.asset_type == AssetType.DOCUMENT
        assert record.entity_type == EntityType.STOCK
        assert record.payload["source_name"] == "巨潮资讯网 - szse"
        assert "cninfo" in record.payload["tags"]
        assert "filing" in record.payload["tags"]


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


class TestCninfoPersist:
    def test_persist_empty(self, cninfo_connector):
        result = cninfo_connector.persist([])
        assert result == 0

    def test_persist_enqueues(self, cninfo_connector):
        record = IngestionRecord(
            source="cninfo",
            dataset="announcements",
            asset_type=AssetType.DOCUMENT,
            entity_type=EntityType.STOCK,
            published_at=datetime(2026, 6, 1, 10, 30),
            raw_uri="cninfo://announcements/test",
            content_hash="abc123",
            payload=NewsPayload(
                title="巨潮资讯网公告",
                content="公告正文内容。",
                source_name="巨潮资讯网",
                tags=["cninfo", "filing", "公告"],
            ).model_dump(),
        )

        with (
            patch("data_layer.repositories.base.db_session") as mock_db_session_class,
            patch(
                "data_layer.repositories.ingestion_repository.IngestionQueueRepository"
            ) as mock_repo_class,
            patch("services.ingestion_queue_service.IngestionQueueService") as mock_service_class,
        ):
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

            result = cninfo_connector.persist([record])
            assert result == 1
            mock_service.enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestCninfoRun:
    def test_run_announcements_full_lifecycle(self, cninfo_connector, sample_envelopes):
        with (
            patch("data_layer.adapters.cninfo_adapter.CninfoAdapter") as mock_adapter_class,
            patch.object(cninfo_connector, "persist", return_value=1),
        ):
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            result = cninfo_connector.run(
                dataset="announcements",
                start_date="2026-01-01",
                end_date="2026-01-31",
                plate="szse",
            )
            assert result.source == "cninfo"
            assert result.dataset == "announcements"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1

    def test_run_unknown_dataset(self, cninfo_connector):
        result = cninfo_connector.run(dataset="unknown")
        assert result.status == IngestionStatus.COMPLETED
        assert result.stats.discovered == 0
