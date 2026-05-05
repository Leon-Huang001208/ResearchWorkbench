"""
审核服务 - 审核队列管理
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.contracts import Assertion, CanonicalEvent
from core.interfaces import AssertionRepository, EventRepository
from core.observability import get_logger
from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
from data_layer.repositories.event_repository import EventRepositoryImpl

logger = get_logger(__name__)


class ReviewService:
    """审核服务"""

    def __init__(
        self,
        assertion_repo: Optional[AssertionRepository] = None,
        event_repo: Optional[EventRepository] = None,
    ):
        # 自动连接 SQLite 实现当未显式传入时
        self._assertion_repo = assertion_repo
        self._event_repo = event_repo
        self._owns_session = False  # 标记是否需要自行管理会话

        if self._assertion_repo is None or self._event_repo is None:
            try:
                from data_layer.repositories.base import SessionLocal

                self._db_session = SessionLocal()
                if self._assertion_repo is None:
                    self._assertion_repo = AssertionRepositoryImpl(db=self._db_session)
                    logger.info("Auto-connected AssertionRepository to SQLite")
                if self._event_repo is None:
                    self._event_repo = EventRepositoryImpl(db=self._db_session)
                    logger.info("Auto-connected EventRepository to SQLite")
            except Exception as e:
                logger.warning(f"Failed to auto-connect repositories: {e}")

    # ---- 断言审核 ----

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

        try:
            return self._assertion_repo.get_pending_review()[:limit]
        except Exception as e:
            logger.error(f"Failed to list pending assertions: {e}")
            return []

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

        assertion = self._assertion_repo.get(assertion_id)
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

        assertion = self._assertion_repo.get(assertion_id)
        if not assertion:
            logger.warning(f"Assertion not found: {assertion_id}")
            return False

        assertion.reviewer_status = "rejected"
        assertion.reviewer = reviewer
        assertion.reviewed_at = datetime.utcnow()

        self._assertion_repo.save(assertion)
        logger.info(f"Assertion rejected: {assertion_id}")
        return True

    # ---- 事件审核 ----

    def list_pending_events(self, limit: int = 100) -> List[CanonicalEvent]:
        """
        列出待审核的事件

        Args:
            limit: 最大数量

        Returns:
            事件列表
        """
        if not self._event_repo:
            logger.warning("Event repository not configured")
            return []

        try:
            return self._event_repo.get_pending_review()[:limit]
        except Exception as e:
            logger.error(f"Failed to list pending events: {e}")
            return []

    def approve_event(self, event_id: str, reviewer: str = "cli") -> bool:
        """
        批准事件

        Args:
            event_id: 事件 ID
            reviewer: 审核人

        Returns:
            是否成功
        """
        if not self._event_repo:
            logger.warning("Event repository not configured")
            return False

        event = self._event_repo.get(event_id)
        if not event:
            logger.warning(f"Event not found: {event_id}")
            return False

        event.reviewer_status = "approved"
        event.reviewer = reviewer
        event.reviewed_at = datetime.utcnow()
        event.needs_review = False

        self._event_repo.save(event)
        logger.info(f"Event approved: {event_id}")
        return True

    def reject_event(self, event_id: str, reviewer: str = "cli") -> bool:
        """
        拒绝事件

        Args:
            event_id: 事件 ID
            reviewer: 审核人

        Returns:
            是否成功
        """
        if not self._event_repo:
            logger.warning("Event repository not configured")
            return False

        event = self._event_repo.get(event_id)
        if not event:
            logger.warning(f"Event not found: {event_id}")
            return False

        event.reviewer_status = "rejected"
        event.reviewer = reviewer
        event.reviewed_at = datetime.utcnow()
        event.needs_review = False

        self._event_repo.save(event)
        logger.info(f"Event rejected: {event_id}")
        return True

    # ---- 统计 ----

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取审核统计

        Returns:
            统计信息
        """
        stats: Dict[str, Any] = {
            "pending_assertions": 0,
            "approved_assertions": 0,
            "rejected_assertions": 0,
            "pending_events": 0,
            "approved_events": 0,
            "rejected_events": 0,
        }

        if self._assertion_repo:
            try:
                pending = self._assertion_repo.get_pending_review()
                stats["pending_assertions"] = len(pending)
            except Exception as e:
                logger.error(f"Failed to get pending assertions stats: {e}")

        if self._event_repo:
            try:
                pending_events = self._event_repo.get_pending_review()
                stats["pending_events"] = len(pending_events)
            except Exception as e:
                logger.error(f"Failed to get pending events stats: {e}")

        return stats
