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
        mock_result.assertions = []
        mock_result.chunks = []
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


class TestWorkerStatusSelfHealing:
    """测试 get_all_worker_statuses() 的孤儿 PID 文件自愈"""

    def test_orphaned_pid_file_is_removed_and_excluded(self, tmp_path, monkeypatch):
        """PID 文件存在但进程已死亡 → 删除文件，不返回该条目"""
        from workers import knowledge_worker

        # 准备 logs 目录，放入一个孤儿 PID 文件
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        orphan_pid = logs_dir / "knowledge_worker_1.pid"
        orphan_pid.write_text("99999")

        monkeypatch.setattr(knowledge_worker, "PROJECT_DIR", tmp_path)

        # 进程 99999 不存在 → get_process_status 返回 alive=False
        statuses = knowledge_worker.get_all_worker_statuses()

        assert statuses == []
        assert not orphan_pid.exists()

    def test_alive_worker_returned_and_file_kept(self, tmp_path, monkeypatch):
        """存活的 worker → 返回条目且保留 PID 文件"""
        import os

        from workers import knowledge_worker

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        current_pid = os.getpid()
        alive_pid_file = logs_dir / "knowledge_worker.pid"
        alive_pid_file.write_text(str(current_pid))

        monkeypatch.setattr(knowledge_worker, "PROJECT_DIR", tmp_path)

        statuses = knowledge_worker.get_all_worker_statuses()

        assert len(statuses) == 1
        assert statuses[0]["alive"] is True
        assert statuses[0]["pid"] == current_pid
        assert statuses[0]["worker_id"] is None
        assert alive_pid_file.exists()

    def test_mixed_alive_and_orphan(self, tmp_path, monkeypatch):
        """混合场景：存活 worker 保留，孤儿文件清理，只返回存活的"""
        import os

        from workers import knowledge_worker

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        current_pid = os.getpid()
        alive_file = logs_dir / "knowledge_worker_1.pid"
        alive_file.write_text(str(current_pid))
        orphan_file = logs_dir / "knowledge_worker_2.pid"
        orphan_file.write_text("99999")

        monkeypatch.setattr(knowledge_worker, "PROJECT_DIR", tmp_path)

        statuses = knowledge_worker.get_all_worker_statuses()

        assert len(statuses) == 1
        assert statuses[0]["worker_id"] == 1
        assert statuses[0]["alive"] is True
        assert alive_file.exists()
        assert not orphan_file.exists()


class TestParseArgsWorkerId:
    """测试 _parse_args 从环境变量读取 worker_id（frozen 模式下由 watchdog 注入）"""

    def test_worker_id_from_env_when_cli_absent(self, monkeypatch):
        from workers.knowledge_worker import _parse_args

        monkeypatch.setattr("sys.argv", ["knowledge_worker"])
        monkeypatch.setenv("ALPHAFOUNDRY_WORKER_ID", "4")

        args = _parse_args()

        assert args.worker_id == 4

    def test_cli_worker_id_takes_precedence(self, monkeypatch):
        from workers.knowledge_worker import _parse_args

        monkeypatch.setattr("sys.argv", ["knowledge_worker", "--worker-id", "2"])
        monkeypatch.setenv("ALPHAFOUNDRY_WORKER_ID", "9")

        args = _parse_args()

        assert args.worker_id == 2

    def test_no_worker_id_when_both_absent(self, monkeypatch):
        from workers.knowledge_worker import _parse_args

        monkeypatch.setattr("sys.argv", ["knowledge_worker"])
        monkeypatch.delenv("ALPHAFOUNDRY_WORKER_ID", raising=False)

        args = _parse_args()

        assert args.worker_id is None

    def test_invalid_env_worker_id_ignored(self, monkeypatch):
        from workers.knowledge_worker import _parse_args

        monkeypatch.setattr("sys.argv", ["knowledge_worker"])
        monkeypatch.setenv("ALPHAFOUNDRY_WORKER_ID", "not-a-number")

        args = _parse_args()

        assert args.worker_id is None


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
