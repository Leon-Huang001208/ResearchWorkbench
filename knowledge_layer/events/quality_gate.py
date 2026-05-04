"""
事件质量门
"""
from datetime import datetime
from typing import List, Tuple

from core.contracts import CanonicalEvent
from core.observability import get_logger

logger = get_logger(__name__)


class EventQualityGate:
    """事件质量门"""

    def __init__(
        self,
        min_confidence: float = 0.4,
        auto_approve_threshold: float = 0.85,
    ):
        self._min_confidence = min_confidence
        self._auto_approve_threshold = auto_approve_threshold

    def validate(self, event: CanonicalEvent) -> Tuple[bool, List[str]]:
        """
        验证单个事件

        Returns:
            (是否自动通过, 问题列表)
        """
        issues: List[str] = []

        # 1. 检查置信度
        if event.confidence < self._min_confidence:
            issues.append(f"置信度过低: {event.confidence:.2f} (最小: {self._min_confidence})")

        # 2. 检查必需字段
        if not event.summary:
            issues.append("摘要为空")

        # 3. 检查时间
        if event.event_time and event.event_time > datetime.utcnow():
            issues.append("事件时间在未来")

        # 4. 判断是否需要审核
        needs_review = (
            len(issues) > 0 or event.confidence < self._auto_approve_threshold or event.needs_review
        )

        return not needs_review, issues

    def process_batch(
        self,
        events: List[CanonicalEvent],
    ) -> Tuple[List[CanonicalEvent], List[CanonicalEvent]]:
        """
        处理一批事件

        Returns:
            (通过列表, 待审核列表)
        """
        passed: List[CanonicalEvent] = []
        needs_review: List[CanonicalEvent] = []

        for event in events:
            if hasattr(event, "model_copy"):
                validated = event.model_copy(deep=True)
            elif hasattr(event, "copy"):
                validated = event.copy(deep=True)
            else:
                validated = event
            is_passed, issues = self.validate(validated)

            if is_passed:
                validated.needs_review = False
                passed.append(validated)
            else:
                validated.needs_review = True
                needs_review.append(validated)

        logger.info(
            f"Quality gate processed {len(events)} events: "
            f"{len(passed)} passed, {len(needs_review)} need review"
        )

        return passed, needs_review
