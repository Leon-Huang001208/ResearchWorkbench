"""来源分级器 - 报告编译器第二阶段.

为 DocumentV1 计算 source_tier / trust_score / freshness_score，回填到
DocumentQuality。这些字段供报告编译器做证据优先级排序（tier A 官方源 > B 准一级
> C 二级 > D 商业社媒），使正文引用优先锚定高可信来源。

设计依据：deep-research-report.md 第二阶段"来源分级落地"。

与既有 RecencyDecayScorer（services/rag_retrieval.py）复用时效衰减逻辑，
不重复实现半衰期公式。
"""

from datetime import datetime

from core.contracts import DocumentV1, SourceReliabilityLevel
from core.contracts.documents_v1 import DocumentQuality
from core.observability import get_logger
from core.source_registry import get as get_source_spec
from core.source_registry import reliability_to_tier

logger = get_logger(__name__)

# tier → 基础可信分（与 SourceTier 分层对齐）
_TIER_BASE_TRUST = {
    "tier_a": 0.95,
    "tier_b": 0.80,
    "tier_c": 0.60,
    "tier_d": 0.35,
}


class SourceGrader:
    """来源分级器.

    计算并回填 DocumentQuality 的 source_tier / trust_score / freshness_score。
    幂等：重复调用不会叠加，每次基于当前 reliability 重新计算。
    """

    def __init__(self, half_life_days: float = 7.0, min_freshness: float = 0.1):
        self._half_life_days = half_life_days
        self._min_freshness = min_freshness

    def grade(self, doc: DocumentV1) -> DocumentQuality:
        """计算并返回填充了分级字段的 DocumentQuality（不修改原 doc）.

        Args:
            doc: 待分级文档

        Returns:
            带有 source_tier / trust_score / freshness_score 的 DocumentQuality
        """
        quality = doc.quality.model_copy()
        reliability = self._resolve_reliability(doc)
        tier = reliability_to_tier(reliability)
        quality.source_tier = tier
        quality.trust_score = self._compute_trust(doc, reliability, tier)
        quality.freshness_score = self._compute_freshness(doc)
        logger.debug(
            "Document graded",
            doc_id=doc.doc_id,
            source_tier=tier,
            trust_score=quality.trust_score,
            freshness_score=quality.freshness_score,
        )
        return quality

    def grade_inplace(self, doc: DocumentV1) -> DocumentV1:
        """分级并就地回填 doc.quality（知识加工阶段调用）."""
        doc.quality = self.grade(doc)
        return doc

    def _resolve_reliability(self, doc: DocumentV1) -> SourceReliabilityLevel:
        """优先用文档自身 reliability；未显式设置时从 source_registry 推导."""
        reliability = doc.quality.source_reliability_level
        if reliability and reliability != SourceReliabilityLevel.UNKNOWN:
            return reliability
        spec = get_source_spec(doc.source_type)
        if spec is not None:
            return spec.reliability
        return SourceReliabilityLevel.UNKNOWN

    def _compute_trust(
        self,
        doc: DocumentV1,
        reliability: SourceReliabilityLevel,
        tier: str,
    ) -> float:
        """可信度评分 = tier 基础分 ± reliability/is_fact_source 微调，截断到 [0,1]."""
        base = _TIER_BASE_TRUST.get(tier, 0.35)
        # is_fact_source 为 False 的来源降权（观点/社媒类）
        if not doc.quality.is_fact_source:
            base -= 0.10
        # UNKNOWN reliability 再降一档
        if reliability == SourceReliabilityLevel.UNKNOWN:
            base -= 0.05
        return max(0.0, min(1.0, base))

    def _compute_freshness(self, doc: DocumentV1) -> float:
        """时效性评分 - 复用半衰期衰减公式，无发布时间给中性分 0.5."""
        import math
        from datetime import timezone

        publish_time = doc.timeliness.publish_time if doc.timeliness else None
        if publish_time is None:
            return 0.5
        reference = datetime.now(timezone.utc)
        # publish_time 无 tzinfo 时按 naive UTC 处理；有 tzinfo 时统一 aware 比较
        if publish_time.tzinfo is None:
            reference = reference.replace(tzinfo=None)
        days_ago = (reference - publish_time).total_seconds() / (24 * 60 * 60)
        if days_ago < 0:
            return 1.0
        decay = math.pow(0.5, days_ago / self._half_life_days)
        return max(self._min_freshness, min(1.0, decay))
