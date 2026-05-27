"""CrawlerIngestionBridge 单元测试"""
from unittest.mock import MagicMock

from core.contracts.ingestion import EnqueueRequest


class TestCrawlerIngestionBridge:
    """测试 CrawlerIngestionBridge"""

    def test_submit_crawled_item_enqueues_correctly(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = {
            "item_id": "test-item-001",
            "dedup_hash": "abc123",
            "was_duplicate": False,
            "message": "enqueued",
        }

        bridge = CrawlerIngestionBridge(queue_service=mock_queue)
        item = {
            "id": "doc-1",
            "title": "Test Title",
            "content": "Test content body",
            "url": "https://example.com",
        }
        result = bridge.submit_crawled_item("cls", item)

        assert result["item_id"] == "test-item-001"
        assert result["was_duplicate"] is False
        mock_queue.enqueue.assert_called_once()
        call_args = mock_queue.enqueue.call_args[0][0]
        assert isinstance(call_args, EnqueueRequest)
        assert call_args.source_type == "cls"
        assert call_args.source_id == "doc-1"
        assert call_args.title == "Test Title"
        assert call_args.raw_content == "Test content body"

    def test_submit_crawled_item_generates_id_from_hash(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = {
            "item_id": "test-item-002",
            "dedup_hash": "def456",
            "was_duplicate": False,
            "message": "enqueued",
        }

        bridge = CrawlerIngestionBridge(queue_service=mock_queue)
        item = {"title": "No ID item", "content": "Some content here"}
        result = bridge.submit_crawled_item("manual", item)

        assert result["item_id"] == "test-item-002"
        call_args = mock_queue.enqueue.call_args[0][0]
        assert call_args.source_id is not None
        assert len(call_args.source_id) == 16  # SHA256[:16]

    def test_submit_batch_enqueues_all_items(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = {
            "item_id": "batch-item",
            "dedup_hash": "xyz",
            "was_duplicate": False,
            "message": "enqueued",
        }

        bridge = CrawlerIngestionBridge(queue_service=mock_queue)
        items = [
            {"title": "Item 1", "content": "Content 1"},
            {"title": "Item 2", "content": "Content 2"},
            {"title": "Item 3", "content": "Content 3"},
        ]
        results = bridge.submit_batch("cnstock", items)

        assert len(results) == 3
        assert mock_queue.enqueue.call_count == 3

    def test_infer_priority_zq_is_high(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = {
            "item_id": "p-item",
            "dedup_hash": "p-hash",
            "was_duplicate": False,
            "message": "enqueued",
        }

        bridge = CrawlerIngestionBridge(queue_service=mock_queue)
        bridge.submit_crawled_item("zq", {"title": "Report", "content": "Deep analysis"})
        call_args = mock_queue.enqueue.call_args[0][0]
        assert call_args.priority == 1  # high priority for ZQ reports

    def test_infer_priority_default_is_normal(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        mock_queue = MagicMock()
        mock_queue.enqueue.return_value = {
            "item_id": "p-item",
            "dedup_hash": "p-hash",
            "was_duplicate": False,
            "message": "enqueued",
        }

        bridge = CrawlerIngestionBridge(queue_service=mock_queue)
        bridge.submit_crawled_item("unknown_source", {"title": "X", "content": "Y"})
        call_args = mock_queue.enqueue.call_args[0][0]
        assert call_args.priority == 0  # default/normal priority

    def test_to_document_envelope_maps_source_types(self):
        from services.crawler_ingestion_bridge import CrawlerIngestionBridge

        bridge = CrawlerIngestionBridge(queue_service=MagicMock())
        envelope = bridge._to_document_envelope(
            "zq", {"id": "r1", "title": "研报", "content": "深度分析", "published_at": "2026-05-19"}
        )
        assert envelope.source_type == "report"
        assert envelope.doc_id == "r1"
        assert envelope.title == "研报"
        assert envelope.canonical_text == "深度分析"
