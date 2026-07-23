"""
来源规划器 - 报告编译器第一阶段.

根据 ResearchPlan 确定来源优先级、检索域、时窗、关键词/别名，输出
RetrievalQuery 列表。对应 deep-research-report.md "来源规划器" 技能。

从 core/source_registry 读取已注册的 SourceSpec（含 reliability / retrieval_weight），
用 reliability_to_tier 映射到 SourceTier，实现来源分级优先。
"""

from typing import Optional

from core.contracts import (
    ResearchPlan,
    RetrievalFilters,
    RetrievalQuery,
    SourceReliabilityLevel,
    SourceTier,
    SourceType,
    reliability_to_tier,
)
from core.observability import get_logger
from core.source_registry import SourceSpec, get_all

logger = get_logger(__name__)


class SourcePlan:
    """来源规划结果 - 含检索查询列表与来源优先级."""

    def __init__(
        self,
        queries: list[RetrievalQuery],
        source_priorities: list[tuple[SourceType, SourceTier, float]],
    ):
        self.queries = queries
        self.source_priorities = source_priorities  # (source_type, tier, weight)

    def tier_a_b_ratio(self) -> float:
        """一级+准一级来源占比，用于评测 KPI."""
        if not self.source_priorities:
            return 0.0
        high = sum(
            1
            for _, tier, _ in self.source_priorities
            if tier in (SourceTier.TIER_A, SourceTier.TIER_B)
        )
        return high / len(self.source_priorities)


class SourcePlanner:
    """来源规划器.

    不做检索，只规划"去哪检索、按什么优先级"。
    """

    def plan(self, research_plan: ResearchPlan) -> SourcePlan:
        """规划来源与检索查询.

        Args:
            research_plan: 任务分解器产出的研究计划

        Returns:
            SourcePlan：检索查询列表 + 来源优先级
        """
        specs = get_all()
        priorities = self._rank_sources(specs)
        queries = self._build_queries(research_plan, priorities)

        logger.info(
            "Source plan ready",
            sources=len(priorities),
            queries=len(queries),
            tier_a_b_ratio=SourcePlan(queries, priorities).tier_a_b_ratio(),
        )
        return SourcePlan(queries=queries, source_priorities=priorities)

    def _rank_sources(self, specs: list[SourceSpec]) -> list[tuple[SourceType, SourceTier, float]]:
        """按 tier + retrieval_weight 排序来源."""
        ranked: list[tuple[SourceType, SourceTier, float]] = []
        for spec in specs:
            tier = reliability_to_tier(spec.reliability)
            ranked.append((spec.source_type, tier, spec.retrieval_weight))
        # tier 优先（A>B>C>D），同 tier 按 retrieval_weight 降序
        tier_order = {
            SourceTier.TIER_A: 0,
            SourceTier.TIER_B: 1,
            SourceTier.TIER_C: 2,
            SourceTier.TIER_D: 3,
        }
        ranked.sort(key=lambda x: (tier_order[x[1]], -x[2]))
        return ranked

    def _build_queries(
        self,
        research_plan: ResearchPlan,
        priorities: list[tuple[SourceType, SourceTier, float]],
    ) -> list[RetrievalQuery]:
        """为每个 research question 构建检索查询."""
        # 来源类型白名单：优先 A/B 级，不足时纳入 C
        source_types: Optional[list[SourceType]] = None
        if priorities:
            high = [
                st for st, tier, _ in priorities if tier in (SourceTier.TIER_A, SourceTier.TIER_B)
            ]
            source_types = high or [st for st, _, _ in priorities]

        queries: list[RetrievalQuery] = []
        for question in research_plan.research_questions:
            filters = RetrievalFilters(
                source_types=source_types,
                min_source_reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
            )
            queries.append(
                RetrievalQuery(
                    query_text=question,
                    filters=filters,
                    max_results=research_plan.retrieval_budget.get("max_chunks", 200),
                )
            )
        return queries
