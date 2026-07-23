"""CNStock DocumentConnector 集成测试 — 使用 mock 验证完整生命周期."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from connectors.document.cnstock import CNStockDocumentConnector
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
    """构造两条模拟 cnstock DocumentEnvelope."""
    return [
        {
            "doc_id": "cn-001",
            "source_type": "news",
            "title": "A股三大指数集体收涨",
            "published_at": "2026-06-01T15:00:00",
            "source_name": "中国证券网",
            "language": "zh",
            "metadata": {"article_id": "001"},
            "raw_text": "A股三大指数集体收涨，沪指涨1.2%。",
            "canonical_text": "A股三大指数集体收涨，沪指涨1.2%。",
        },
        {
            "doc_id": "cn-002",
            "source_type": "news",
            "title": "央行开展逆回购操作",
            "published_at": "2026-06-01T10:00:00",
            "source_name": "中国证券网",
            "language": "zh",
            "metadata": {"article_id": "002"},
            "raw_text": "央行开展100亿元7天期逆回购操作。",
            "canonical_text": "央行开展100亿元7天期逆回购操作。",
        },
    ]


@pytest.fixture
def cnstock_connector():
    return CNStockDocumentConnector()


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestCNStockHealthCheck:
    def test_healthy(self, cnstock_connector):
        result = cnstock_connector.health_check()
        assert result in (HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE)
        assert cnstock_connector._health != HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestCNStockDiscover:
    def test_news_with_channel(self, cnstock_connector):
        items = cnstock_connector.discover(
            dataset="news",
            start_date="2026-01-01",
            end_date="2026-01-31",
            channel="证券",
        )
        assert len(items) == 1
        assert items[0].item_type == "news"
        assert items[0].params["channel"] == "证券"
        assert "证券" in items[0].description

    def test_news_all_channels(self, cnstock_connector):
        items = cnstock_connector.discover(
            dataset="news",
            start_date="2026-01-01",
            end_date="2026-01-31",
            all_channels=True,
        )
        assert len(items) == 1
        assert items[0].params["all_channels"] is True

    def test_unknown_dataset(self, cnstock_connector):
        items = cnstock_connector.discover(dataset="unknown")
        assert items == []


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


class TestCNStockFetch:
    def test_fetch_news(self, cnstock_connector, sample_envelopes):
        with patch("data_layer.adapters.cnstock_adapter.CNStockAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="cnstock_证券_2026-01-01_2026-01-31",
                item_type="news",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "channel": "证券",
                },
            )
            raw = cnstock_connector.fetch(dataset="news", item=item)
            assert isinstance(raw, RawObject)
            assert raw.content_type == "application/json"
            assert "cnstock://news/" in raw.source_uri
            assert raw.metadata["item_count"] == 2

    def test_fetch_news_requests_article_content_by_default(self, cnstock_connector):
        with patch("data_layer.adapters.cnstock_adapter.CNStockAdapter") as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = []
            mock_adapter_class.return_value = mock_adapter

            item = DiscoveryItem(
                item_id="cnstock_证券_2026-01-01_2026-01-31",
                item_type="news",
                params={
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "channel": "证券",
                },
            )

            cnstock_connector.fetch(dataset="news", item=item)

            _, kwargs = mock_adapter.fetch.call_args
            assert kwargs["fetch_content"] is True


# ---------------------------------------------------------------------------
# parse_document
# ---------------------------------------------------------------------------


class TestCNStockParseDocument:
    def test_parse_news(self, cnstock_connector, sample_envelopes):
        raw = RawObject(
            data=json.dumps(sample_envelopes, ensure_ascii=False),
            content_type="application/json",
            source_uri="cnstock://news/2026-01-01",
            metadata={
                "item_type": "news",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "channel": "证券",
            },
        )
        doc = cnstock_connector.parse_document(raw)
        assert isinstance(doc, ParsedDocument)
        assert "中国证券网" in doc.title
        assert "证券" in doc.title
        assert "2 条" in doc.title
        assert "A股" in doc.text or "央行" in doc.text
        assert doc.pages == 2

    def test_parse_empty(self, cnstock_connector):
        raw = RawObject(
            data="[]",
            content_type="application/json",
            source_uri="cnstock://news/empty",
            metadata={"start_date": "2026-01-01"},
        )
        doc = cnstock_connector.parse_document(raw)
        assert doc.text == ""
        assert doc.pages is None


# ---------------------------------------------------------------------------
# normalize_metadata
# ---------------------------------------------------------------------------


class TestCNStockNormalizeMetadata:
    def test_normalize(self, cnstock_connector):
        parsed = ParsedDocument(
            title="中国证券网 [证券] 2026-01-01 (2 条)",
            text="A股三大指数集体收涨\n\n---\n\n央行开展逆回购操作",
            pages=2,
            file_type="json",
            metadata={
                "individual_titles": ["A股三大指数集体收涨", "央行开展逆回购操作"],
                "article_count": 2,
                "channel": "证券",
            },
        )
        record = cnstock_connector.normalize_metadata(
            dataset="news",
            parsed=parsed,
            raw_uri="cnstock://news/test",
            content_hash="abc123",
        )
        assert isinstance(record, IngestionRecord)
        assert record.source == "cnstock"
        assert record.dataset == "news"
        assert record.asset_type == AssetType.NEWS
        assert record.payload["source_name"] == "中国证券网"


# ---------------------------------------------------------------------------
# persist
# ---------------------------------------------------------------------------


class TestCNStockPersist:
    def test_persist_empty(self, cnstock_connector):
        result = cnstock_connector.persist([])
        assert result == 0

    def test_persist_enqueues(self, cnstock_connector):
        record = IngestionRecord(
            source="cnstock",
            dataset="news",
            asset_type=AssetType.NEWS,
            entity_type=EntityType.UNKNOWN,
            published_at=datetime(2026, 6, 1, 10, 30),
            raw_uri="cnstock://news/test",
            content_hash="abc123",
            payload=NewsPayload(
                title="测试新闻",
                content="新闻正文内容。",
                source_name="中国证券网",
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

            result = cnstock_connector.persist([record])
            assert result == 1
            mock_service.enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# run() template method
# ---------------------------------------------------------------------------


class TestCNStockRun:
    def test_run_news_full_lifecycle(self, cnstock_connector, sample_envelopes):
        with (
            patch("data_layer.adapters.cnstock_adapter.CNStockAdapter") as mock_adapter_class,
            patch.object(cnstock_connector, "persist", return_value=1),
        ):
            mock_adapter = MagicMock()
            mock_adapter.fetch.return_value = [
                MagicMock(model_dump=lambda e=env: e) for env in sample_envelopes
            ]
            mock_adapter_class.return_value = mock_adapter

            result = cnstock_connector.run(
                dataset="news",
                start_date="2026-01-01",
                end_date="2026-01-31",
                channel="证券",
            )
            assert result.source == "cnstock"
            assert result.dataset == "news"
            assert result.status == IngestionStatus.COMPLETED
            assert result.stats.discovered == 1

    def test_run_unknown_dataset(self, cnstock_connector):
        result = cnstock_connector.run(dataset="unknown")
        assert result.status == IngestionStatus.COMPLETED
        assert result.stats.discovered == 0
