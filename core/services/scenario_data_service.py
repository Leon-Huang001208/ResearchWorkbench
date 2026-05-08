"""ScenarioDataService — 用真实事件/Outcome/记忆数据丰富场景分析。

当数据不可用时，所有方法都有 graceful fallback：返回空列表而非报错。
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from core.observability import get_logger
from memory_learning.journal import LearningJournal

logger = get_logger(__name__)

EvidenceStrength = Literal["high", "medium", "low", "none"]


def _compute_evidence_strength(count: int) -> EvidenceStrength:
    """根据证据数量计算证据强度。"""
    if count >= 5:
        return "high"
    elif count >= 3:
        return "medium"
    elif count >= 1:
        return "low"
    return "none"


class ScenarioDataService:
    """从真实存储获取事件历史、Outcome 记录和传播模式，丰富场景输出。"""

    def __init__(
        self,
        event_repository: Optional[Any] = None,
        outcome_repository: Optional[Any] = None,
        journal: Optional[LearningJournal] = None,
    ):
        self._event_repo = event_repository
        self._outcome_repo = outcome_repository
        self._journal = journal

    # ── 事件证据 ──────────────────────────────────────────

    def get_event_evidence(
        self,
        event_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """从数据库获取相关事件历史。

        Args:
            event_type: 事件类型过滤
            subject_id: 主体ID过滤
            limit: 返回数量限制

        Returns:
            事件证据列表，每条包含 event_id, event_type, summary, confidence, impact_direction
        """
        if self._event_repo is None:
            logger.debug("no event repository configured, returning empty evidence")
            return []

        try:
            if subject_id:
                events = self._event_repo.get_by_entity(subject_id)
            else:
                events = self._event_repo.list(limit=limit)

            if event_type:
                events = [e for e in events if e.event_type == event_type]

            return [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "confidence": e.confidence,
                    "impact_direction": e.impact_direction,
                    "event_time": str(e.event_time) if e.event_time else None,
                }
                for e in events[:limit]
            ]
        except Exception as exc:
            logger.warning("failed to get event evidence, returning empty", error=str(exc))
            return []

    # ── Outcome 证据 ─────────────────────────────────────

    def get_outcome_evidence(
        self,
        subject_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """从数据库获取相关 Outcome 记录。

        Args:
            subject_id: 主体ID过滤
            event_type: 事件类型过滤
            limit: 返回数量限制

        Returns:
            Outcome 证据列表，每条包含 outcome_id, event_id, outcome_return, lesson 等
        """
        if self._outcome_repo is None:
            logger.debug("no outcome repository configured, returning empty evidence")
            return []

        try:
            outcomes = self._outcome_repo.list(
                event_type=event_type,
                limit=limit,
            )

            if subject_id:
                outcomes = [o for o in outcomes if o.subject_id == subject_id]

            return [
                {
                    "outcome_id": o.outcome_id,
                    "event_id": o.event_id,
                    "signal_id": o.signal_id,
                    "subject_id": o.subject_id,
                    "outcome_return": o.outcome_return,
                    "outcome_excess_return": o.outcome_excess_return,
                    "max_drawdown": o.max_drawdown,
                    "decay": o.decay,
                    "timing_action": o.timing_action,
                    "lesson": o.lesson,
                    "failure_reason": o.failure_reason,
                }
                for o in outcomes[:limit]
            ]
        except Exception as exc:
            logger.warning("failed to get outcome evidence, returning empty", error=str(exc))
            return []

    # ── 传播模式 ──────────────────────────────────────────

    def get_propagation_patterns(
        self,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """从记忆学习模块获取传播模式。

        Args:
            event_type: 事件类型过滤

        Returns:
            传播模式列表，包含 event_type, sample_size, win_rate, avg_excess_return 等
        """
        if self._journal is None:
            logger.debug("no learning journal configured, returning empty patterns")
            return []

        try:
            if event_type:
                summary = self._journal.summarize_event_type(event_type)
                if summary.get("sample_size", 0) > 0:
                    return [
                        {
                            "event_type": event_type,
                            "sample_size": summary["sample_size"],
                            "win_rate": summary["win_rate"],
                            "average_excess_return": summary["average_excess_return"],
                        }
                    ]
                return []

            # 如果没有指定 event_type，从 journal 中获取所有 episode 类型
            episodes = self._journal.list_episodes()
            if not episodes:
                return []

            # 按 event_type 分组
            by_type: Dict[str, List[Any]] = {}
            for ep in episodes:
                by_type.setdefault(ep.event_type, []).append(ep)

            patterns = []
            for etype, eps in by_type.items():
                wins = sum(1 for e in eps if e.outcome_excess_return > 0)
                avg_excess = sum(e.outcome_excess_return for e in eps) / len(eps)
                patterns.append(
                    {
                        "event_type": etype,
                        "sample_size": len(eps),
                        "win_rate": wins / len(eps),
                        "average_excess_return": avg_excess,
                    }
                )
            return patterns
        except Exception as exc:
            logger.warning("failed to get propagation patterns, returning empty", error=str(exc))
            return []

    # ── Regime 摘要 ───────────────────────────────────────

    def get_regime_summaries(
        self,
        regime: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取特定市场环境的摘要。

        Args:
            regime: 市场环境过滤

        Returns:
            Regime 摘要列表
        """
        if self._journal is None:
            logger.debug("no learning journal configured, returning empty regime summaries")
            return []

        try:
            # 从策略记忆中获取 regime 信息
            strategies = self._journal.list_strategies(market_regime=regime)
            return [
                {
                    "strategy_id": s.strategy_id,
                    "signal_family": s.signal_family,
                    "market_regime": s.market_regime,
                    "sample_size": s.sample_size,
                    "win_rate": s.win_rate,
                    "average_excess_return": s.average_excess_return,
                    "sharpe_ratio": s.sharpe_ratio,
                }
                for s in strategies
            ]
        except Exception as exc:
            logger.warning("failed to get regime summaries, returning empty", error=str(exc))
            return []

    # ── 场景丰富 ──────────────────────────────────────────

    def enrich_scenario(
        self,
        scenario_id: str,
        event_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        """用真实数据丰富场景输出。

        Args:
            scenario_id: 场景ID
            event_type: 事件类型
            subject_id: 主体ID
            regime: 市场环境

        Returns:
            包含 evidence, evidence_strength, propagation_patterns, regime_summaries 的字典
        """
        events = self.get_event_evidence(event_type=event_type, subject_id=subject_id)
        outcomes = self.get_outcome_evidence(subject_id=subject_id, event_type=event_type)
        patterns = self.get_propagation_patterns(event_type=event_type)
        regimes = self.get_regime_summaries(regime=regime)

        total_evidence_count = len(events) + len(outcomes)
        strength = _compute_evidence_strength(total_evidence_count)

        enriched = {
            "scenario_id": scenario_id,
            "evidence": {
                "events": events,
                "outcomes": outcomes,
            },
            "evidence_strength": strength,
            "evidence_count": total_evidence_count,
            "propagation_patterns": patterns,
            "regime_summaries": regimes,
        }

        logger.info(
            "scenario enriched",
            scenario_id=scenario_id,
            evidence_count=total_evidence_count,
            evidence_strength=strength,
        )

        return enriched
