"""统一摄取队列单元测试"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts import CanonicalEvent
from core.contracts.ingestion import EnqueueRequest, IngestionQueueItem
from data_layer.repositories.base import Base
from data_layer.repositories.ingestion_repository import IngestionQueueRepository
from services.ingestion_queue_service import IngestionQueueService

# ─── 测试数据库设置 ──────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试创建全新表"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """创建数据库会话"""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def repo(db_session):
    """创建仓储实例"""
    return IngestionQueueRepository(db_session)


@pytest.fixture
def service(repo):
    """创建服务实例（无 pipeline）"""
    return IngestionQueueService(repository=repo)


def _make_item(
    source_type: str = "cls",
    source_id: str | None = None,
    raw_content: str = "测试内容",
    title: str | None = None,
    priority: int = 0,
    max_retries: int = 3,
    created_at: datetime | None = None,
    item_id: str | None = None,
) -> IngestionQueueItem:
    """创建测试队列项"""
    return IngestionQueueItem(
        item_id=item_id or f"item-{source_type}-{raw_content[:8]}",
        source_type=source_type,
        source_id=source_id,
        raw_content=raw_content,
        title=title,
        priority=priority,
        max_retries=max_retries,
        created_at=created_at or datetime.now(timezone.utc),
    )


# ─── 仓储测试 ───────────────────────────────────────────


class TestIngestionQueueRepository:
    def test_enqueue(self, repo):
        """入队"""
        item = _make_item(source_type="cls", raw_content="财联社电报内容")
        result = repo.enqueue(item)
        assert result.item_id == item.item_id
        assert result.dedup_hash is not None
        assert result.status == "pending"

    def test_enqueue_dedup_by_source_id(self, repo):
        """去重：相同 source_type + source_id"""
        item1 = _make_item(source_type="cls", source_id="cls-001", raw_content="内容A")
        item2 = _make_item(source_type="cls", source_id="cls-001", raw_content="内容B")

        result1 = repo.enqueue(item1)
        result2 = repo.enqueue(item2)

        # 去重：第二次入队返回的是第一次的 item
        assert result2.item_id == result1.item_id

    def test_enqueue_dedup_by_content_hash(self, repo):
        """去重：无 source_id 时按内容 hash"""
        item1 = _make_item(source_type="manual", raw_content="相同内容")
        item2 = _make_item(source_type="manual", raw_content="相同内容")

        result1 = repo.enqueue(item1)
        result2 = repo.enqueue(item2)

        assert result2.item_id == result1.item_id

    def test_enqueue_different_content_not_deduped(self, repo):
        """不同内容不去重"""
        item1 = _make_item(source_type="manual", raw_content="内容A")
        item2 = _make_item(source_type="manual", raw_content="内容B")

        result1 = repo.enqueue(item1)
        result2 = repo.enqueue(item2)

        assert result2.item_id != result1.item_id

    def test_dequeue_order_by_priority_then_time(self, repo):
        """出队顺序：priority 降序 + created_at 升序"""
        # 入队 3 个不同优先级
        repo.enqueue(_make_item(source_type="cls", raw_content="普通", priority=0))
        repo.enqueue(_make_item(source_type="cls", raw_content="紧急", priority=2))
        repo.enqueue(_make_item(source_type="cls", raw_content="高优", priority=1))

        items = repo.dequeue(limit=10)
        assert len(items) == 3
        # priority 降序
        assert items[0].priority == 2
        assert items[1].priority == 1
        assert items[2].priority == 0

    def test_dequeue_spreads_batch_across_sources_with_same_priority(self, repo):
        """同优先级积压时，一个来源不能占满整个批次"""
        from datetime import timedelta

        base = datetime(2026, 6, 10, tzinfo=timezone.utc)
        for i in range(5):
            repo.enqueue(
                _make_item(
                    source_type="zhiqiu_reports",
                    raw_content=f"old-report-{i}",
                    item_id=f"old-report-{i}",
                    created_at=base + timedelta(seconds=i),
                )
            )
        for i in range(2):
            repo.enqueue(
                _make_item(
                    source_type="cls",
                    raw_content=f"new-cls-{i}",
                    item_id=f"new-cls-{i}",
                    created_at=base + timedelta(minutes=10, seconds=i),
                )
            )

        items = repo.dequeue(limit=4)

        assert len(items) == 4
        assert {item.source_type for item in items} == {"zhiqiu_reports", "cls"}

    def test_dequeue_marks_processing(self, repo):
        """出队后状态变为 processing"""
        repo.enqueue(_make_item(raw_content="待处理"))
        items = repo.dequeue(limit=1)
        assert items[0].status == "processing"
        assert items[0].processed_at is not None

    def test_dequeue_empty(self, repo):
        """空队列出队返回空列表"""
        items = repo.dequeue(limit=10)
        assert items == []

    def test_mark_completed(self, repo):
        """标记完成"""
        repo.enqueue(_make_item(raw_content="完成测试"))
        items = repo.dequeue(limit=1)
        result = repo.mark_completed(items[0].item_id)
        assert result.status == "completed"
        assert result.processed_at is not None

    def test_mark_failed_with_retry(self, repo):
        """标记失败后可重试"""
        repo.enqueue(_make_item(raw_content="失败测试", max_retries=3))
        items = repo.dequeue(limit=1)

        # 第一次失败
        result = repo.mark_failed(items[0].item_id, "timeout")
        assert result.retry_count == 1
        assert result.status == "pending"  # 应该重置为 pending 以便重试
        assert result.processed_at is None

    def test_mark_failed_permanent(self, repo):
        """超过最大重试次数后永久失败"""
        repo.enqueue(_make_item(raw_content="永久失败", max_retries=2))
        items = repo.dequeue(limit=1)

        # 失败 1 次 -> status=pending (可重试)
        result1 = repo.mark_failed(items[0].item_id, "error 1")
        assert result1.retry_count == 1
        assert result1.status == "pending"

        # 重新 dequeue（状态已回到 pending）
        items2 = repo.dequeue(limit=1)
        assert len(items2) == 1

        # 失败 2 次 -> retry_count == max_retries(2) -> status=failed
        result2 = repo.mark_failed(items2[0].item_id, "error 2")
        assert result2.retry_count == 2
        assert result2.status == "failed"  # 永久失败

    def test_get_stats(self, repo):
        """队列统计"""
        repo.enqueue(_make_item(source_type="cls", raw_content="stat1"))
        repo.enqueue(_make_item(source_type="zq", raw_content="stat2"))

        stats = repo.get_stats()
        assert stats.depth == 2  # pending
        assert stats.pending == 2
        assert stats.processing == 0
        assert stats.completed == 0
        assert stats.failed == 0

    def test_find_by_dedup_hash(self, repo):
        """根据去重哈希查找"""
        item = repo.enqueue(
            _make_item(source_type="cls", source_id="find-test", raw_content="查找测试")
        )
        found = repo.find_by_dedup_hash(item.dedup_hash)
        assert found is not None
        assert found.item_id == item.item_id

    def test_get_recent(self, repo):
        """获取最近处理记录"""
        repo.enqueue(_make_item(raw_content="recent-test"))
        items = repo.dequeue(limit=1)
        repo.mark_completed(items[0].item_id)

        recent = repo.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].status == "completed"

    def test_reset_failed_for_retry(self, repo):
        """重置失败项以重试"""
        repo.enqueue(_make_item(raw_content="retry-reset", max_retries=1))
        items = repo.dequeue(limit=1)
        repo.mark_failed(items[0].item_id, "permanent failure")

        # 确认已失败
        stats = repo.get_stats()
        assert stats.failed == 1

        # 重置
        count = repo.reset_failed_for_retry()
        assert count == 1

        # 确认回到 pending
        stats = repo.get_stats()
        assert stats.pending == 1
        assert stats.failed == 0


# ─── 服务测试 ───────────────────────────────────────────


class TestIngestionQueueService:
    def test_enqueue(self, service):
        """入队"""
        request = EnqueueRequest(
            source_type="cls",
            source_id="test-001",
            raw_content="财联社测试内容",
            title="测试标题",
        )
        result = service.enqueue(request)
        assert result["was_duplicate"] is False
        assert result["message"] == "enqueued"
        assert result["item_id"] is not None

    def test_enqueue_duplicate(self, service):
        """入队去重"""
        request = EnqueueRequest(
            source_type="cls",
            source_id="dup-001",
            raw_content="重复内容",
        )
        result1 = service.enqueue(request)
        result2 = service.enqueue(request)
        assert result2["was_duplicate"] is True
        assert result1["item_id"] == result2["item_id"]

    def test_dequeue(self, service):
        """出队"""
        request = EnqueueRequest(source_type="cls", raw_content="出队测试")
        service.enqueue(request)
        items = service.dequeue(limit=10)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_process_item(self, service, repo):
        """处理单个项（无 pipeline）"""
        request = EnqueueRequest(
            source_type="cls",
            raw_content="处理测试内容",
            title="测试事件标题",
        )
        service.enqueue(request)
        result = await service.process_batch(limit=1)
        assert result["processed_count"] == 1
        assert result["results"][0]["status"] == "completed_no_pipeline"

    @pytest.mark.asyncio
    async def test_process_item_with_pipeline(self, repo):
        """处理单个项（有 pipeline）"""
        mock_pipeline = MagicMock()
        from core.contracts import EventAlphaSignal

        mock_signal = EventAlphaSignal(
            signal_id="sig-001",
            subject_id="600000.SH",
            horizon="20d",
            thesis="测试论点",
            score=0.8,
            confidence=0.7,
            event_id="evt-001",
            event_type="regulation",
        )
        mock_pipeline.run_event_signal = AsyncMock(return_value=mock_signal)

        svc = IngestionQueueService(repository=repo, pipeline=mock_pipeline)
        request = EnqueueRequest(
            source_type="cls",
            raw_content="Pipeline 测试",
            title="Pipeline 标题",
        )
        svc.enqueue(request)
        result = await svc.process_batch(limit=1)
        assert result["processed_count"] == 1
        assert result["results"][0]["status"] == "completed"
        assert result["results"][0]["signal_id"] == "sig-001"

    def test_get_stats(self, service):
        """队列统计"""
        request = EnqueueRequest(source_type="cls", raw_content="统计测试")
        service.enqueue(request)
        stats = service.get_stats()
        assert stats.pending == 1

    def test_retry_failed(self, service, repo):
        """重试失败项"""
        # 创建一个永久失败项 (max_retries=1, fail once → permanent)
        repo.enqueue(_make_item(raw_content="重试服务测试", max_retries=1))
        items = repo.dequeue(limit=1)
        repo.mark_failed(items[0].item_id, "error")

        # 确认已永久失败
        stats = repo.get_stats()
        assert stats.failed == 1

        result = service.retry_failed()
        assert result["retried_count"] == 1

    @pytest.mark.asyncio
    async def test_full_flow(self, repo):
        """完整流程：入队 -> 去重 -> 出队 -> 处理 -> 持久化"""
        svc = IngestionQueueService(repository=repo)

        # 1. 入队
        req1 = EnqueueRequest(source_type="cls", source_id="flow-001", raw_content="流程测试1")
        req2 = EnqueueRequest(source_type="zq", raw_content="流程测试2")
        req3 = EnqueueRequest(
            source_type="cls", source_id="flow-001", raw_content="流程测试1重复"
        )  # 重复

        r1 = svc.enqueue(req1)
        r2 = svc.enqueue(req2)
        r3 = svc.enqueue(req3)

        assert r1["was_duplicate"] is False
        assert r2["was_duplicate"] is False
        assert r3["was_duplicate"] is True  # 去重

        # 2. 队列统计
        stats = svc.get_stats()
        assert stats.depth == 2  # 只有2个非重复项

        # 3. 出队 + 处理
        result = await svc.process_batch(limit=10)
        assert result["processed_count"] == 2

        # 4. 处理后统计
        stats = svc.get_stats()
        assert stats.completed == 2
        assert stats.pending == 0


# ─── 归一化测试 ─────────────────────────────────────────


class TestNormalization:
    def test_normalize_to_event(self, service):
        """归一化为 CanonicalEvent"""
        item = _make_item(
            source_type="cls",
            raw_content="央行降息50个基点",
            title="央行降息",
        )
        event = service._normalize_to_event(item)
        assert isinstance(event, CanonicalEvent)
        assert event.event_type == "regulation"  # cls -> regulation
        assert event.summary == "央行降息"
        assert event.source_doc_id == item.item_id

    def test_normalize_no_title(self, service):
        """无标题时截取 raw_content"""
        item = _make_item(
            source_type="manual",
            raw_content="这是一段很长的手动输入内容" * 20,
        )
        event = service._normalize_to_event(item)
        assert isinstance(event, CanonicalEvent)
        assert len(event.summary) <= 200

    def test_normalize_source_type_mapping(self, service):
        """不同 source_type 映射到不同 event_type"""
        test_cases = {
            "cls": "regulation",
            "cnstock": "regulation",
            "zq": "earnings",
            "report": "earnings",
            "manual": "other",
            "unknown_type": "other",
        }
        for source_type, expected_event_type in test_cases.items():
            item = _make_item(source_type=source_type, raw_content=f"{source_type}内容")
            event = service._normalize_to_event(item)
            assert event.event_type == expected_event_type, f"Failed for {source_type}"
