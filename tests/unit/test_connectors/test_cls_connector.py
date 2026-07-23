"""CLS DocumentConnector 集成测试 — 使用 mock 验证完整生命周期."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.document.cls import CLSDocumentConnector
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
def sample_telegram_envelopes():
    """构造两条模拟电报 DocumentEnvelope."""
    return [
        {
            "doc_id": "cls-001",
            "source_type": "news",
            "title": "央行降准0.5个百分点",
            "published_at": "2026-06-01T10:30:00",
            "source_name": "财联社",
            "language": "zh",
            "metadata": {"telegram_id": "001"},
            "raw_text": "央行决定自2026年6月15日起下调存款准备金率0.5个百分点。",
            "canonical_text": "央行决定自2026年6月15日起下调存款准备金率0.5个百分点。",
        },
        {
            "doc_id": "cls-002",
            "source_type": "news",
            "title": "沪指突破3500点",
            "published_at": "2026-06-01T14:00:00",
            "source_name": "财联社",
            "language": "zh",
            "metadata": {"telegram_id": "002"},
            "raw_text": "沪指午后持续走强，突破3500点整数关口。",
            "canonical_text": "沪指午后持续走强，突破3500点整数关口。",
        },
    ]


@pytest.fixture
def cls_connector():
    """创建 CLS connector（无需 mock — 构造方法仅设置配置）."""
    return CLSDocumentConnector()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestCLSHealthCheck:
    def test_healthy(self, cls_connector):
        result = cls_connector.health_check()
        assert result in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE)
        # 如果没有 requests 库，可能 DEGRADED
        assert cls_connector._health != HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestCLSDiscover:
    def test_telegram_with_date_range(self, cls_connector):
        items = cls_connector.discover(
            dataset="telegram",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        assert len(items) == 1
        assert items[0].item_type == "telegram"
        assert items[0].params["start_date"] == "2026-01-01"
        assert items[0].params["end_date"] == "2026-01-31"
        assert "2026-01-01" in items[0].description

    def test_telegram_with_days(self, cls_connector):
        items = cls_connector.discover(dataset="telegram", days=7)
        assert len(items) == 1
        assert items[0].params["days"] == 7

    def test_telegram_incremental(self, cls_connector):
        items = cls_connector.discover(dataset="telegram")
        assert len(items) == 1
        assert "incremental" in items[0].item_id.lower()

    def test_unknown_dataset(self, cls_connector):
        items = cls_connector.discover(dataset="unknown")
        assert items == []


# ---------------------------------------------------------------------------
# fetch (with mock)
# ---------------------------------------------------------------------------


class TestCLSFetch:
    def test_fetch_telegram(self, cls_connector, sample_telegram_envelopes):
        """使用 mock CLSAdapter 验证 fetch."""
        with patch("data_layer.adapters.cls_adapter.CLSAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_telegram_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="telegram_2026-01-01_2026-01-31",
                item_type="telegram",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
            )
            raw = cls_connector.fetch(dataset="telegram", item=item)
            assert isinstance(raw, RawObject)
            assert raw.content_type == "application/json"
            assert "cls://telegram/" in raw.source_uri
            assert raw.metadata["item_count"] == 2

    def test_fetch_unknown_dataset_raises(self, cls_connector):
        item = DiscoveryItem(item_id="bad", item_type="bad", params={})
        with pytest.raises(ValueError, match="Unknown dataset"):
            cls_connector.fetch(dataset="unknown", item=item)


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------


class TestCLSParseDocument:
    def test_parse_telegrams(self, cls_connector, sample_telegram_envelopes):
        raw = RawObject(
            data=json.dumps(sample_telegram_envelopes, ensure_ascii=False),
            content_type="application/json",
            source_uri="cls://telegram/2026-01-01",
            metadata={
                "item_type": "telegram",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "item_count": 2,
            },
        )
        doc = cls_connector.parse_document(raw)
        assert isinstance(doc, ParsedDocument)
        assert "财联社电报" in doc.title
        assert "2026-01-01" in doc.title
        assert "2 条" in doc.title
        assert "央行降准" in doc.text or "央行" in doc.text
        assert "沪指" in doc.text
        assert doc.pages == 2
        assert doc.file_type == "json"
        assert doc.metadata["telegram_count"] == 2
        assert len(doc.metadata["individual_titles"]) == 2

    def test_parse_empty(self, cls_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="cls://telegram/empty",
            metadata={"start_date": "2026-01-01"},
        )
        doc = cls_connector.parse_document(raw)
        assert doc.text == ""
        assert doc.pages is None


# ---------------------------------------------------------------------------
# normalize_metadata
# ---------------------------------------------------------------------------


class TestCLSNormalizeMetadata:
    def test_normalize(self, cls_connector):
        parsed = ParsedDocument(
            title="财联社电报 2026-01-01 (2 条)",
            text="央行降准\n\n---\n\n沪指突破3500点",
            pages=2,
            file_type="json",
            metadata={
                "individual_titles": ["央行降准0.5个百分点", "沪指突破3500点"],
                "telegram_count": 2,
            },
        )
        record = cls_connector.normalize_metadata(
            dataset="telegram",
            parsed=parsed,
            raw_uri="cls://telegram/test",
            content_hash="abc123",
        )
        assert isinstance(record, IngestionRecord)
        assert record.source == "cls"
        assert record.dataset == "telegram"
        assert record.asset_type == AssetType.NEWS
        assert record.entity_type == EntityType.UNKNOWN
        assert record.content_hash == "abc123"
        assert record.raw_uri == "cls://telegram/test"
        assert record.payload["source_name"] == "财联社"
        assert "telegram" in record.payload["tags"]


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


class TestCLSPersist:
    def test_persist_empty(self, cls_connector):
        result = cls_connector.persist([])
        assert result == 0

    def test_persist_enqueues(self, cls_connector):
        """验证 persist 将 IngestionRecord 转换后入队."""
        record = IngestionRecord(
            source="cls",
            dataset="telegram",
            asset_type=AssetType.NEWS,
            entity_type=EntityType.UNKNOWN,
            published_at=datetime(2026, 6, 1, 10, 30),
            raw_uri="cls://telegram/test",
            content_hash="abc123",
            payload=NewsPayload(
                title="央行降准",
                content="央行决定下调存款准备金率。",
                source_name="财联社",
            ).model_dump(),
        )

        with (
            patch("data_layer.repositories.base.db_session") as mock_db_session_class,
            patch(
                "data_layer.repositories.ingestion_repository.IngestionQueueRepository"
            ) as mock_repo_class,
            patch("services.ingestion_queue_service.IngestionQueueService") as mock_service_class,
        ):
            # Mock context manager for db_session
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

            result = cls_connector.persist([record])
            assert result == 1
            mock_service.enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestCLSRun:
    def test_run_telegram_full_lifecycle(self, cls_connector, sample_telegram_envelopes):
        """验证 run() 模版方法完整生命周期 (with mocked adapter + persist)."""
        with (
            patch("data_layer.adapters.cls_adapter.CLSAdapter") as mock_adapter_class,
            patch.object(cls_connector, "persist", return_value=1),
        ):
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_telegram_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            result = cls_connector.run(
                dataset="telegram",
                days=2,
                use_incremental=True,
                max_pages=10,
            )
            assert result.source == "cls"
            assert result.dataset == "telegram"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1
            # run_id is generated
            assert result.run_id is not None

    def test_run_unknown_dataset(self, cls_connector):
        result = cls_connector.run(dataset="unknown")
        assert result.status == IngestionStatus.COMPLETED
        # discover returns empty → no items → nothing to do
        assert result.stats.discovered == 0
