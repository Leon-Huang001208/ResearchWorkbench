"""Knowledge Worker 单元测试"""
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


class TestProcessOne:
    """测试 process_one"""

    @pytest.mark.asyncio
    @patch("ingestion.knowledge_pipeline.KnowledgePipeline")
    @patch("workers.knowledge_worker.event_bus", new_callable=AsyncMock)
    async def test_process_one_publishes_events(self, mock_bus, mock_pipeline_cls):
        from workers.knowledge_worker import process_one

        mock_result = MagicMock()
        mock_result.events = []
        mock_result.entities = []
        mock_pipeline_cls_instance = MagicMock()
        mock_pipeline_cls_instance.process = AsyncMock(return_value=mock_result)
        mock_pipeline_cls.return_value = mock_pipeline_cls_instance

        mock_item = MagicMock()
        mock_item.item_id = "i1"
        mock_item.source_id = None
        mock_item.source_type = "cls"
        mock_item.title = "T"
        mock_item.raw_content = "C"
        mock_item.url = None

        result = await process_one(mock_item)
        assert result["item_id"] == "i1"
        assert result["events"] == 0
        assert result["entities"] == 0
