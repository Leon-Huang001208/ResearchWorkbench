"""
事件质量门
"""

from datetime import datetime
from typing import List, Tuple

from core.contracts import CanonicalEvent
from core.observability import get_logger

logger = get_logger(__name__)

# 摘要最小长度
MIN_SUMMARY_LENGTH = 5


class EventQualityGate:
    """事件质量门"""

    def __init__(
        self,
        min_confidence: float = 0.4,
        auto_approve_threshold: float = 0.85,
        min_summary_length: int = MIN_SUMMARY_LENGTH,
        impact_direction_unknown_penalty: float = 0.15,
    ):
        self._min_confidence = min_confidence
        self._auto_approve_threshold = auto_approve_threshold
        self._min_summary_length = min_summary_length
        self._impact_direction_unknown_penalty = impact_direction_unknown_penalty

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

        # 2. 检查摘要
        if not event.summary:
            issues.append("摘要为空")
        elif len(event.summary.strip()) < self._min_summary_length:
            issues.append(f"摘要过短: {len(event.summary.strip())} 字符 (最小: {self._min_summary_length})")

        # 3. 检查时间
        if event.event_time and event.event_time > datetime.utcnow():
            issues.append("事件时间在未来")

        # 4. 检查实体非空
        if not event.entities:
            issues.append("实体列表为空")

        # 5. 检查 evidence_spans 非空
        if not event.evidence_spans:
            issues.append("evidence_spans 为空")

        # 6. impact_direction 未知时降级置信度
        effective_confidence = event.confidence
        if event.impact_direction == "unknown":
            effective_confidence -= self._impact_direction_unknown_penalty
            if effective_confidence < self._min_confidence:
                issues.append(
                    f"impact_direction 未知，降级后置信度 {effective_confidence:.2f} "
                    f"低于最小 {self._min_confidence}"
                )

        # 7. 判断是否需要审核
        needs_review = len(issues) > 0 or effective_confidence < self._auto_approve_threshold

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
                validated.reviewer_status = "approved"
                validated.reviewer = "auto_quality_gate"
                validated.reviewed_at = datetime.utcnow()
                passed.append(validated)
            else:
                validated.needs_review = True
                validated.reviewer_status = "pending"
                needs_review.append(validated)

        logger.info(
            f"Quality gate processed {len(events)} events: "
            f"{len(passed)} passed, {len(needs_review)} need review"
        )

        return passed, needs_review
