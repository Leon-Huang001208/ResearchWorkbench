"""
测试审核服务
"""
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts import Assertion, CanonicalEvent
from core.services.review_service import ReviewService
from data_layer.repositories.base import Base
from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
from data_layer.repositories.event_repository import EventRepositoryImpl


def _make_mock_assertion_repo(pending_return=None):
    """创建 mock 断言仓储"""
    mock = Mock()
    mock.get_pending_review.return_value = pending_return or []
    return mock


def _make_mock_event_repo(pending_return=None):
    """创建 mock 事件仓储"""
    mock = Mock()
    mock.get_pending_review.return_value = pending_return or []
    return mock


class TestReviewServiceBasic:
    """测试审核服务基本功能（mock 仓储）"""

    def test_list_pending_assertions_empty(self):
        """测试无待审核断言的情况"""
        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=_make_mock_event_repo(),
        )
        assertions = service.list_pending_assertions(limit=20)
        assert assertions == []

    def test_list_pending_assertions_with_repo(self):
        """测试带仓储的待审核列表"""
        mock_assertion1 = Mock(spec=Assertion)
        mock_assertion1.assertion_id = "test-1"
        mock_assertion2 = Mock(spec=Assertion)
        mock_assertion2.assertion_id = "test-2"

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo([mock_assertion1, mock_assertion2]),
            event_repo=_make_mock_event_repo(),
        )
        assertions = service.list_pending_assertions(limit=10)

        assert len(assertions) == 2

    def test_approve_assertion(self):
        """测试批准断言"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "test-1"
        mock_repo.get.return_value = mock_assertion
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=mock_repo,
            event_repo=_make_mock_event_repo(),
        )
        success = service.approve_assertion("test-1", reviewer="tester")

        assert success is True
        assert mock_assertion.reviewer_status == "approved"
        assert mock_assertion.reviewer == "tester"
        assert mock_assertion.reviewed_at is not None
        mock_repo.save.assert_called_once_with(mock_assertion)

    def test_approve_assertion_not_found(self):
        """测试批准不存在的断言"""
        mock_repo = Mock()
        mock_repo.get.return_value = None
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=mock_repo,
            event_repo=_make_mock_event_repo(),
        )
        success = service.approve_assertion("nonexistent", reviewer="tester")

        assert success is False

    def test_approve_assertion_no_repo(self):
        """测试无断言仓储时的批准"""
        service = ReviewService(
            assertion_repo=None,
            event_repo=_make_mock_event_repo(),
        )
        service._assertion_repo = None
        success = service.approve_assertion("test-1", reviewer="tester")
        assert success is False

    def test_reject_assertion(self):
        """测试拒绝断言"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "test-1"
        mock_repo.get.return_value = mock_assertion
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=mock_repo,
            event_repo=_make_mock_event_repo(),
        )
        success = service.reject_assertion("test-1", reviewer="tester")

        assert success is True
        assert mock_assertion.reviewer_status == "rejected"
        assert mock_assertion.reviewer == "tester"
        assert mock_assertion.reviewed_at is not None
        mock_repo.save.assert_called_once_with(mock_assertion)

    def test_reject_assertion_not_found(self):
        """测试拒绝不存在的断言"""
        mock_repo = Mock()
        mock_repo.get.return_value = None
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=mock_repo,
            event_repo=_make_mock_event_repo(),
        )
        success = service.reject_assertion("nonexistent", reviewer="tester")

        assert success is False

    def test_get_statistics_empty(self):
        """测试无数据时的统计"""
        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=_make_mock_event_repo(),
        )
        stats = service.get_statistics()

        assert stats["pending_assertions"] == 0
        assert stats["approved_assertions"] == 0
        assert stats["rejected_assertions"] == 0
        assert stats["pending_events"] == 0
        assert stats["approved_events"] == 0
        assert stats["rejected_events"] == 0

    def test_get_statistics_with_repo(self):
        """测试带仓储的统计"""
        mock_assertion1 = Mock(spec=Assertion)
        mock_assertion2 = Mock(spec=Assertion)
        mock_event = Mock(spec=CanonicalEvent)

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo([mock_assertion1, mock_assertion2]),
            event_repo=_make_mock_event_repo([mock_event]),
        )
        stats = service.get_statistics()

        assert stats["pending_assertions"] == 2
        assert stats["pending_events"] == 1

    def test_full_assertion_workflow(self):
        """测试完整的断言审核工作流"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "workflow-test-1"
        mock_repo.get.return_value = mock_assertion
        mock_repo.get_pending_review.return_value = [mock_assertion]

        service = ReviewService(
            assertion_repo=mock_repo,
            event_repo=_make_mock_event_repo(),
        )

        # 1. 列出待审核
        pending = service.list_pending_assertions()
        assert len(pending) == 1

        # 2. 批准
        success = service.approve_assertion("workflow-test-1", reviewer="tester")
        assert success is True

        # 3. 获取统计
        stats = service.get_statistics()
        assert stats is not None


class TestReviewServiceEvents:
    """测试审核服务事件功能"""

    def test_list_pending_events(self):
        """测试列出待审核事件"""
        mock_event = Mock(spec=CanonicalEvent)
        mock_event.event_id = "evt-1"

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=_make_mock_event_repo([mock_event]),
        )
        events = service.list_pending_events()

        assert len(events) == 1

    def test_list_pending_events_empty(self):
        """测试无待审核事件"""
        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=_make_mock_event_repo(),
        )
        events = service.list_pending_events()
        assert events == []

    def test_list_pending_events_no_repo(self):
        """测试无事件仓储时返回空列表"""
        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=None,
        )
        service._event_repo = None
        events = service.list_pending_events()
        assert events == []

    def test_approve_event(self):
        """测试批准事件"""
        mock_repo = Mock()
        mock_event = Mock(spec=CanonicalEvent)
        mock_event.event_id = "evt-1"
        mock_repo.get.return_value = mock_event
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=mock_repo,
        )
        success = service.approve_event("evt-1", reviewer="tester")

        assert success is True
        assert mock_event.reviewer_status == "approved"
        assert mock_event.reviewer == "tester"
        assert mock_event.reviewed_at is not None
        assert mock_event.needs_review is False
        mock_repo.save.assert_called_once_with(mock_event)

    def test_approve_event_not_found(self):
        """测试批准不存在的事件"""
        mock_repo = Mock()
        mock_repo.get.return_value = None
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=mock_repo,
        )
        success = service.approve_event("nonexistent", reviewer="tester")
        assert success is False

    def test_reject_event(self):
        """测试拒绝事件"""
        mock_repo = Mock()
        mock_event = Mock(spec=CanonicalEvent)
        mock_event.event_id = "evt-1"
        mock_repo.get.return_value = mock_event
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=mock_repo,
        )
        success = service.reject_event("evt-1", reviewer="tester")

        assert success is True
        assert mock_event.reviewer_status == "rejected"
        assert mock_event.reviewer == "tester"
        assert mock_event.reviewed_at is not None
        assert mock_event.needs_review is False
        mock_repo.save.assert_called_once_with(mock_event)

    def test_reject_event_not_found(self):
        """测试拒绝不存在的事件"""
        mock_repo = Mock()
        mock_repo.get.return_value = None
        mock_repo.get_pending_review.return_value = []

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=mock_repo,
        )
        success = service.reject_event("nonexistent", reviewer="tester")
        assert success is False

    def test_full_event_workflow(self):
        """测试完整的事件审核工作流"""
        mock_repo = Mock()
        mock_event = Mock(spec=CanonicalEvent)
        mock_event.event_id = "evt-workflow-1"
        mock_repo.get.return_value = mock_event
        mock_repo.get_pending_review.return_value = [mock_event]

        service = ReviewService(
            assertion_repo=_make_mock_assertion_repo(),
            event_repo=mock_repo,
        )

        # 1. 列出待审核
        pending = service.list_pending_events()
        assert len(pending) == 1

        # 2. 拒绝
        success = service.reject_event("evt-workflow-1", reviewer="tester")
        assert success is True

        # 3. 统计
        stats = service.get_statistics()
        assert stats is not None
        assert "pending_events" in stats


class TestReviewServiceWithSQLite:
    """使用真实 SQLite 仓储测试审核服务"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """设置内存数据库"""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.session = SessionLocal()
        self.assertion_repo = AssertionRepositoryImpl(db=self.session)
        self.event_repo = EventRepositoryImpl(db=self.session)
        yield
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_auto_connect_repos(self):
        """测试自动连接 SQLite 仓储"""
        service = ReviewService(
            assertion_repo=self.assertion_repo,
            event_repo=self.event_repo,
        )
        assert service._assertion_repo is not None
        assert service._event_repo is not None

    def test_event_lifecycle_with_sqlite(self):
        """测试使用 SQLite 的事件完整生命周期"""
        service = ReviewService(
            assertion_repo=self.assertion_repo,
            event_repo=self.event_repo,
        )

        # 创建并保存待审核事件
        event = CanonicalEvent(
            event_id="evt-sqlite-001",
            event_type="earnings",
            summary="贵州茅台净利润增长28%",
            impact_direction="positive",
            confidence=0.75,
            needs_review=True,
            entities=[{"text": "贵州茅台"}],
            evidence_spans=[{"text": "净利润增长28%"}],
            source_doc_id="doc-001",
            reviewer_status="pending",
        )
        self.event_repo.save(event)
        self.session.flush()

        # 查看待审核事件
        pending = service.list_pending_events()
        assert len(pending) == 1
        assert pending[0].event_id == "evt-sqlite-001"

        # 批准
        success = service.approve_event("evt-sqlite-001", reviewer="admin")
        assert success is True

        # 验证状态已变更
        updated = self.event_repo.get("evt-sqlite-001")
        assert updated.reviewer_status == "approved"
        assert updated.reviewer == "admin"
        assert updated.needs_review is False

        # 待审核列表应不再包含该事件
        pending_after = service.list_pending_events()
        assert len(pending_after) == 0

    def test_assertion_lifecycle_with_sqlite(self):
        """测试使用 SQLite 的断言完整生命周期"""
        service = ReviewService(
            assertion_repo=self.assertion_repo,
            event_repo=self.event_repo,
        )

        # 创建并保存待审核断言
        assertion = Assertion(
            assertion_id="asrt-sqlite-001",
            predicate="reported_revenue",
            object_value={"amount": 350e9},
            confidence=0.8,
            source_doc_id="doc-001",
            source_span={},
            extractor_version="rule_v1",
            reviewer_status="pending",
        )
        self.assertion_repo.save(assertion)
        self.session.flush()

        # 查看待审核断言
        pending = service.list_pending_assertions()
        assert len(pending) == 1

        # 拒绝
        success = service.reject_assertion("asrt-sqlite-001", reviewer="admin")
        assert success is True

        # 验证状态
        updated = self.assertion_repo.get("asrt-sqlite-001")
        assert updated.reviewer_status == "rejected"
        assert updated.reviewer == "admin"

        # 统计
        stats = service.get_statistics()
        assert stats["pending_assertions"] == 0
