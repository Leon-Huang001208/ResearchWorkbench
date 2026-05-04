"""
测试审核服务
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock

import pytest

from core.contracts import Assertion
from core.services.review_service import ReviewService


class TestReviewService:
    """测试审核服务"""

    def test_list_pending_assertions_empty(self):
        """测试无待审核断言的情况"""
        service = ReviewService()
        assertions = service.list_pending_assertions(limit=20)

        # 没有配置仓储时应该返回空列表
        assert assertions == []

    def test_list_pending_assertions_with_repo(self):
        """测试带仓储的待审核列表"""
        mock_repo = Mock()
        mock_assertion1 = Mock(spec=Assertion)
        mock_assertion1.assertion_id = "test-1"
        mock_assertion2 = Mock(spec=Assertion)
        mock_assertion2.assertion_id = "test-2"
        mock_repo.list_by_status.return_value = [mock_assertion1, mock_assertion2]

        service = ReviewService(assertion_repo=mock_repo)
        assertions = service.list_pending_assertions(limit=10)

        assert len(assertions) == 2
        mock_repo.list_by_status.assert_called_with("pending", limit=10)

    def test_approve_assertion(self):
        """测试批准断言"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "test-1"
        mock_repo.get_by_id.return_value = mock_assertion

        service = ReviewService(assertion_repo=mock_repo)
        success = service.approve_assertion("test-1", reviewer="tester")

        assert success is True
        assert mock_assertion.reviewer_status == "approved"
        assert mock_assertion.reviewer == "tester"
        assert mock_assertion.reviewed_at is not None
        mock_repo.save.assert_called_once_with(mock_assertion)

    def test_approve_assertion_not_found(self):
        """测试批准不存在的断言"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None

        service = ReviewService(assertion_repo=mock_repo)
        success = service.approve_assertion("nonexistent", reviewer="tester")

        assert success is False

    def test_approve_assertion_no_repo(self):
        """测试无仓储时的批准"""
        service = ReviewService()
        success = service.approve_assertion("test-1", reviewer="tester")

        assert success is False

    def test_reject_assertion(self):
        """测试拒绝断言"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "test-1"
        mock_repo.get_by_id.return_value = mock_assertion

        service = ReviewService(assertion_repo=mock_repo)
        success = service.reject_assertion("test-1", reviewer="tester")

        assert success is True
        assert mock_assertion.reviewer_status == "rejected"
        assert mock_assertion.reviewer == "tester"
        assert mock_assertion.reviewed_at is not None
        mock_repo.save.assert_called_once_with(mock_assertion)

    def test_reject_assertion_not_found(self):
        """测试拒绝不存在的断言"""
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None

        service = ReviewService(assertion_repo=mock_repo)
        success = service.reject_assertion("nonexistent", reviewer="tester")

        assert success is False

    def test_get_statistics_empty(self):
        """测试无仓储时的统计"""
        service = ReviewService()
        stats = service.get_statistics()

        assert stats["pending_assertions"] == 0
        assert stats["approved_assertions"] == 0
        assert stats["rejected_assertions"] == 0

    def test_get_statistics_with_repo(self):
        """测试带仓储的统计"""
        mock_repo = Mock()
        mock_assertion1 = Mock(spec=Assertion)
        mock_assertion2 = Mock(spec=Assertion)
        mock_repo.list_by_status.return_value = [mock_assertion1, mock_assertion2]

        service = ReviewService(assertion_repo=mock_repo)
        stats = service.get_statistics()

        assert stats["pending_assertions"] == 2
        mock_repo.list_by_status.assert_called_with("pending", limit=1000)

    def test_full_workflow(self):
        """测试完整的审核工作流"""
        mock_repo = Mock()
        mock_assertion = Mock(spec=Assertion)
        mock_assertion.assertion_id = "workflow-test-1"
        mock_repo.get_by_id.return_value = mock_assertion
        mock_repo.list_by_status.return_value = [mock_assertion]

        service = ReviewService(assertion_repo=mock_repo)

        # 1. 列出待审核
        pending = service.list_pending_assertions()
        assert len(pending) == 1

        # 2. 批准
        success = service.approve_assertion("workflow-test-1", reviewer="tester")
        assert success is True

        # 3. 获取统计
        stats = service.get_statistics()
        assert stats is not None
