"""
审核服务 - 审核队列管理
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.contracts import Assertion
from core.interfaces import AssertionRepository, EventRepository
from core.observability import get_logger

logger = get_logger(__name__)


class ReviewService:
    """审核服务"""

    def __init__(
        self,
        assertion_repo: Optional[AssertionRepository] = None,
        event_repo: Optional[EventRepository] = None,
    ):
        self._assertion_repo = assertion_repo
        self._event_repo = event_repo

    def list_pending_assertions(self, limit: int = 100) -> List[Assertion]:
        """
        列出待审核的断言

        Args:
            limit: 最大数量

        Returns:
            断言列表
        """
        if not self._assertion_repo:
            logger.warning("Assertion repository not configured")
            return []

        return self._assertion_repo.list_by_status("pending", limit=limit)

    def approve_assertion(self, assertion_id: str, reviewer: str = "cli") -> bool:
        """
        批准断言

        Args:
            assertion_id: 断言 ID
            reviewer: 审核人

        Returns:
            是否成功
        """
        if not self._assertion_repo:
            logger.warning("Assertion repository not configured")
            return False

        assertion = self._assertion_repo.get_by_id(assertion_id)
        if not assertion:
            logger.warning(f"Assertion not found: {assertion_id}")
            return False

        assertion.reviewer_status = "approved"
        assertion.reviewer = reviewer
        assertion.reviewed_at = datetime.utcnow()

        self._assertion_repo.save(assertion)
        logger.info(f"Assertion approved: {assertion_id}")
        return True

    def reject_assertion(self, assertion_id: str, reviewer: str = "cli") -> bool:
        """
        拒绝断言

        Args:
            assertion_id: 断言 ID
            reviewer: 审核人

        Returns:
            是否成功
        """
        if not self._assertion_repo:
            logger.warning("Assertion repository not configured")
            return False

        assertion = self._assertion_repo.get_by_id(assertion_id)
        if not assertion:
            logger.warning(f"Assertion not found: {assertion_id}")
            return False

        assertion.reviewer_status = "rejected"
        assertion.reviewer = reviewer
        assertion.reviewed_at = datetime.utcnow()

        self._assertion_repo.save(assertion)
        logger.info(f"Assertion rejected: {assertion_id}")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取审核统计

        Returns:
            统计信息
        """
        stats = {
            "pending_assertions": 0,
            "approved_assertions": 0,
            "rejected_assertions": 0,
            "pending_events": 0,
        }

        if self._assertion_repo:
            stats["pending_assertions"] = len(self.list_pending_assertions(limit=1000))

        return stats
