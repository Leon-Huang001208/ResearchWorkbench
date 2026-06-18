"""Knowledge Worker 单元测试"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestKnowledgeWorker:
    """测试 workers/knowledge_worker.py"""

    def test_create_document_v1(self):
        from workers.knowledge_worker import _create_document_v1

        mock_item = MagicMock()
        mock_item.item_id = "item-001"
        mock_item.source_id = None
        mock_item.source_type = "cls"
        mock_item.title = "Test Title"
        mock_item.raw_content = "Raw content here"
        mock_item.url = "https://example.com"

        doc = _create_document_v1(mock_item)
        assert doc.doc_id == "item-001"
        assert doc.title == "Test Title"
        assert doc.content == "Raw content here"
        assert doc.source_url == "https://example.com"

    def test_create_document_v1_defaults(self):
        from workers.knowledge_worker import _create_document_v1

        mock_item = MagicMock()
        mock_item.item_id = "item-002"
        mock_item.source_id = None
        mock_item.source_type = "unknown"
        mock_item.title = ""
        mock_item.raw_content = "Content"
        mock_item.url = None

        doc = _create_document_v1(mock_item)
        assert doc.doc_id == "item-002"
        assert doc.title == ""
        assert doc.source_type.value == "other"

    def test_create_document_v1_cninfo_mapping(self):
        from workers.knowledge_worker import _create_document_v1

        mock_item = MagicMock()
        mock_item.item_id = "item-cninfo"
        mock_item.source_id = "announcement-001"
        mock_item.source_type = "cninfo"
        mock_item.title = "Announcement"
        mock_item.raw_content = "Announcement content"
        mock_item.url = "https://example.com/a"
        mock_item.published_at = "2026-06-04T10:00:00+08:00"

        doc = _create_document_v1(mock_item)

        assert doc.doc_id == "announcement-001"
        assert doc.doc_type.value == "filing"
        assert doc.source_type.value == "cninfo"

    def test_create_source_document_envelope_uses_doc_metadata_fields(self):
        from workers.knowledge_worker import _create_document_v1, _create_source_document_envelope

        mock_item = MagicMock()
        mock_item.item_id = "item-src"
        mock_item.source_id = "doc-src"
        mock_item.source_type = "cls"
        mock_item.title = "Title"
        mock_item.raw_content = "Content"
        mock_item.url = "https://example.com/src"
        mock_item.published_at = None

        doc = _create_document_v1(mock_item)
        envelope = _create_source_document_envelope(mock_item, doc)

        assert envelope.doc_id == "doc-src"
        assert envelope.metadata["content_hash"] == doc.content_hash
        assert envelope.metadata["object_uri"] == "https://example.com/src"


class TestProcessOne:
    """测试 process_one"""

    @pytest.mark.asyncio
    @patch("workers.knowledge_worker.event_bus", new_callable=AsyncMock)
    async def test_process_one_publishes_events(self, mock_bus):
        from workers.knowledge_worker import process_one

        mock_result = MagicMock()
        mock_result.events = []
        mock_result.entities = []
        mock_pipeline = MagicMock()
        mock_pipeline.process = AsyncMock(return_value=mock_result)

        mock_item = MagicMock()
        mock_item.item_id = "i1"
        mock_item.source_id = None
        mock_item.source_type = "cls"
        mock_item.title = "T"
        mock_item.raw_content = "C"
        mock_item.url = None

        result = await process_one(mock_item, mock_pipeline)
        assert result["item_id"] == "i1"
        assert result["events"] == 0
        assert result["entities"] == 0

    def test_processed_item_log_fields_excludes_raw_document_content(self):
        from workers.knowledge_worker import _create_document_v1, _processed_item_log_fields

        mock_item = MagicMock()
        mock_item.item_id = "i-log"
        mock_item.source_id = None
        mock_item.source_type = "zhiqiu_wechat"
        mock_item.title = "Important title"
        mock_item.raw_content = "Very long crawled article body that must not be logged"
        mock_item.url = None

        doc = _create_document_v1(mock_item)
        fields = _processed_item_log_fields(
            {
                "item_id": "i-log",
                "doc_id": doc.doc_id,
                "doc": doc,
                "events": 1,
                "entities": 2,
                "event_list": ["event"],
                "entity_list": ["entity"],
            }
        )

        assert "doc" not in fields
        assert "event_list" not in fields
        assert "entity_list" not in fields
        assert "content" not in fields
        assert fields["title"] == "Important title"
        assert fields["content_hash"] == doc.content_hash
        assert "Very long crawled article body" not in repr(fields)


class TestStuckRecovery:
    """测试 processing 队列项恢复"""

    def test_recover_stuck_items_with_null_processed_at(self, db_session):
        from data_layer.repositories.models import IngestionQueueItemDB
        from workers.knowledge_worker import _recover_stuck_items

        item = IngestionQueueItemDB(
            item_id="stuck-null-processed-at",
            source_type="cls",
            source_id="doc-1",
            raw_content="content",
            title="title",
            status="processing",
            retry_count=0,
            max_retries=3,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            processed_at=None,
            dedup_hash="dedup-1",
        )
        db_session.add(item)
        db_session.commit()

        recovered = _recover_stuck_items(db_session)
        db_session.commit()

        assert recovered == 1
        refreshed = db_session.get(IngestionQueueItemDB, "stuck-null-processed-at")
        assert refreshed.status == "pending"
