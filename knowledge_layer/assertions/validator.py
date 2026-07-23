"""
断言验证器 - 质量门机制
"""

from datetime import datetime
from typing import List, Tuple

from core.contracts import Assertion
from core.observability import get_logger

logger = get_logger(__name__)


class AssertionValidator:
    """断言验证器"""

    def __init__(
        self,
        min_confidence: float = 0.5,
        auto_approve_threshold: float = 0.9,
    ):
        self._min_confidence = min_confidence
        self._auto_approve_threshold = auto_approve_threshold

    def validate(self, assertion: Assertion) -> Tuple[bool, List[str]]:
        """
        验证单个断言

        Args:
            assertion: 待验证断言

        Returns:
            (是否通过, 问题列表)
        """
        issues: List[str] = []

        # 1. 检查置信度
        if assertion.confidence < self._min_confidence:
            issues.append(f"置信度过低: {assertion.confidence:.2f} (最小: {self._min_confidence})")

        # 2. 检查必需字段
        if not assertion.predicate:
            issues.append("谓语为空")

        # 3. 检查时间有效性
        if assertion.observed_at:
            if assertion.observed_at > datetime.utcnow():
                issues.append("观察时间在未来")

        # 4. 判断是否需要审核
        needs_review = len(issues) > 0 or assertion.confidence < self._auto_approve_threshold

        return not needs_review, issues

    def validate_batch(
        self, assertions: List[Assertion]
    ) -> List[Tuple[Assertion, bool, List[str]]]:
        """
        批量验证

        Returns:
            [(断言, 是否通过, 问题列表)]
        """
        results = []
        for assertion in assertions:
            passed, issues = self.validate(assertion)
            results.append((assertion, passed, issues))
        return results

    def update_review_status(
        self,
        assertion: Assertion,
    ) -> Assertion:
        """
        更新断言的审核状态

        Args:
            assertion: 断言

        Returns:
            更新后的断言
        """
        passed, issues = self.validate(assertion)

        if passed:
            assertion.reviewer_status = "approved"
            assertion.reviewer = "auto_validator"
            assertion.reviewed_at = datetime.utcnow()
        else:
            assertion.reviewer_status = "pending"

        return assertion


class QualityGate:
    """质量门 - 用于断言的整体质量检查"""

    def __init__(self, validator: AssertionValidator):
        self._validator = validator

    def process_batch(
        self,
        assertions: List[Assertion],
    ) -> Tuple[List[Assertion], List[Assertion]]:
        """
        处理一批断言

        Args:
            assertions: 输入断言列表

        Returns:
            (通过列表, 待审核列表)
        """
        passed: List[Assertion] = []
        needs_review: List[Assertion] = []

        for assertion in assertions:
            validated = self._validator.update_review_status(assertion)
            if validated.reviewer_status == "approved":
                passed.append(validated)
            else:
                needs_review.append(validated)

        logger.info(
            f"Quality gate processed {len(assertions)} assertions: "
            f"{len(passed)} passed, {len(needs_review)} need review"
        )

        return passed, needs_review
