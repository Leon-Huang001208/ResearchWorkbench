"""组合构建与风险预算服务。

将多个并发信号转为一致的投资组合，在显式约束下将评分信号转为排名配置。
"""
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.contracts.portfolio import PortfolioCandidate, PortfolioConstraints, PortfolioProposal
from core.observability import get_logger

logger = get_logger(__name__)


class PortfolioService:
    """组合构建与风险预算服务"""

    def __init__(
        self,
        outcome_repository: Optional[Any] = None,
        portfolio_repository: Optional[Any] = None,
    ):
        """
        初始化组合服务。

        Args:
            outcome_repository: Outcome 仓储（用于获取历史质量指标）
            portfolio_repository: Portfolio 仓储（用于持久化提案）
        """
        self._outcome_repo = outcome_repository
        self._portfolio_repo = portfolio_repository

    def build_proposal(
        self,
        active_signals: List[Any],
        constraints: Optional[PortfolioConstraints] = None,
        name: Optional[str] = None,
    ) -> PortfolioProposal:
        """核心方法：从活跃信号构建组合提案。

        流程：
        1. 过滤：移除低于 min_signal_score / min_confidence 的信号
        2. 转换：将信号转为 PortfolioCandidate，补充历史质量数据
        3. 排名：按综合评分排序
        4. 冲突解决：同事件链/高相关主体只保留最高分
        5. 仓位定权：根据综合评分分配权重（归一化）
        6. 约束检查：max_position_size, sector/theme concentration
        7. 记录排除理由和约束应用日志

        Args:
            active_signals: 活跃信号列表（AlphaSignal 或 EventAlphaSignal）
            constraints: 组合约束，默认使用 PortfolioConstraints()
            name: 提案名称

        Returns:
            PortfolioProposal 组合提案
        """
        if constraints is None:
            constraints = PortfolioConstraints()
        if name is None:
            name = f"portfolio_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        excluded_signals: List[Dict[str, Any]] = []
        constraints_applied: List[str] = []
        rationale_steps: Dict[str, Any] = {}

        # Step 1: 过滤
        candidates, filtered_out = self._filter_signals(active_signals, constraints)
        excluded_signals.extend(filtered_out)
        constraints_applied.append("min_signal_score/min_confidence_filter")
        rationale_steps["filter"] = {
            "input_count": len(active_signals),
            "passed_count": len(candidates),
            "filtered_count": len(filtered_out),
        }
        logger.info(
            "portfolio filter completed",
            input_count=len(active_signals),
            passed_count=len(candidates),
        )

        # Step 2: 补充历史质量数据
        candidates = self._enrich_candidates(candidates)
        rationale_steps["enrichment"] = {
            "candidates_enriched": len(candidates),
        }

        # Step 3: 排名
        ranked_candidates = self._rank_candidates(candidates)
        rationale_steps["ranking"] = {
            "ranking_method": "score * confidence * historical_hit_rate",
            "top_3_scores": [c.suggested_weight for c in ranked_candidates[:3]],
        }
        logger.info("portfolio ranking completed", ranked_count=len(ranked_candidates))

        # Step 4: 冲突解决
        resolved_candidates, conflict_excluded = self.resolve_conflicts(
            ranked_candidates, constraints
        )
        excluded_signals.extend(conflict_excluded)
        constraints_applied.append("conflict_resolution")
        rationale_steps["conflict_resolution"] = {
            "before_count": len(ranked_candidates),
            "after_count": len(resolved_candidates),
            "conflicts_resolved": len(conflict_excluded),
        }
        logger.info(
            "conflict resolution completed",
            before=len(ranked_candidates),
            after=len(resolved_candidates),
        )

        # Step 5: 仓位定权
        sized_candidates = self.size_positions(resolved_candidates, constraints)
        constraints_applied.append("position_sizing")
        rationale_steps["position_sizing"] = {
            "method": "score_weighted_normalization",
            "candidate_count": len(sized_candidates),
        }

        # Step 6: 约束检查
        final_candidates, constraint_excluded = self.apply_constraints(
            sized_candidates, constraints
        )
        excluded_signals.extend(constraint_excluded)
        for c_applied in constraint_excluded:
            reason = c_applied.get("reason", "unknown")
            if reason not in constraints_applied:
                constraints_applied.append(reason)
        rationale_steps["constraint_check"] = {
            "final_candidate_count": len(final_candidates),
            "excluded_by_constraints": len(constraint_excluded),
        }

        # Build allocations map
        allocations: Dict[str, float] = {}
        for candidate in final_candidates:
            allocations[candidate.subject_id] = round(candidate.suggested_weight, 6)

        # Build proposal
        proposal_id = str(uuid.uuid4())
        proposal = PortfolioProposal(
            proposal_id=proposal_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            candidates=final_candidates,
            allocations=allocations,
            constraints_applied=constraints_applied,
            excluded_signals=excluded_signals,
            rationale=rationale_steps,
        )

        # Persist
        if self._portfolio_repo:
            self._portfolio_repo.save_proposal(proposal)
            logger.info("proposal persisted", proposal_id=proposal_id)

        logger.info(
            "portfolio proposal built",
            proposal_id=proposal_id,
            candidate_count=len(final_candidates),
            allocation_count=len(allocations),
            excluded_count=len(excluded_signals),
        )

        return proposal

    def get_historical_quality(
        self, subject_id: str, event_type: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """从 Outcome 历史获取 hit_rate 和 avg_excess_return。

        Args:
            subject_id: 主体ID
            event_type: 事件类型

        Returns:
            (hit_rate, avg_excess_return) 元组，数据不足时返回 (None, None)
        """
        if self._outcome_repo is None:
            return None, None

        try:
            outcomes = self._outcome_repo.list(event_type=event_type, limit=200)
            # 过滤匹配 subject_id
            matching = [o for o in outcomes if o.subject_id == subject_id]
            if not matching:
                return None, None

            wins = sum(1 for o in matching if o.outcome_excess_return > 0)
            hit_rate = wins / len(matching)
            avg_excess = sum(o.outcome_excess_return for o in matching) / len(matching)

            logger.debug(
                "historical quality computed",
                subject_id=subject_id,
                event_type=event_type,
                sample_size=len(matching),
                hit_rate=hit_rate,
                avg_excess_return=avg_excess,
            )
            return hit_rate, avg_excess

        except Exception as exc:
            logger.warning(
                "failed to compute historical quality",
                subject_id=subject_id,
                event_type=event_type,
                error=str(exc),
            )
            return None, None

    def resolve_conflicts(
        self,
        candidates: List[PortfolioCandidate],
        constraints: Optional[PortfolioConstraints] = None,
    ) -> Tuple[List[PortfolioCandidate], List[Dict[str, Any]]]:
        """冲突解决：同事件链/同主体只保留最高分。

        Args:
            candidates: 已排序的候选列表
            constraints: 组合约束

        Returns:
            (resolved_candidates, excluded_signals) 元组
        """
        excluded: List[Dict[str, Any]] = []

        # 按 subject_id 去重 — 同主体只保留最高分
        seen_subjects: Dict[str, PortfolioCandidate] = {}
        for candidate in candidates:
            if candidate.subject_id in seen_subjects:
                existing = seen_subjects[candidate.subject_id]
                # candidate 已经按综合评分排序，第一个就是最高分
                excluded.append(
                    {
                        "signal_id": candidate.signal_id,
                        "subject_id": candidate.subject_id,
                        "event_type": candidate.event_type,
                        "reason": "duplicate_subject",
                        "detail": f"Subject {candidate.subject_id} already represented by signal {existing.signal_id}",
                    }
                )
            else:
                seen_subjects[candidate.subject_id] = candidate

        # 按 event_type 去重 — 同事件类型只保留前 N 个（避免集中度过高）
        if constraints:
            resolved = list(seen_subjects.values())
            return resolved, excluded

        return list(seen_subjects.values()), excluded

    def apply_constraints(
        self,
        candidates: List[PortfolioCandidate],
        constraints: PortfolioConstraints,
    ) -> Tuple[List[PortfolioCandidate], List[Dict[str, Any]]]:
        """约束检查和调整。

        检查 max_position_size, sector/theme concentration，
        对超限的权重进行裁剪并重新归一化。

        Args:
            candidates: 已定权的候选列表
            constraints: 组合约束

        Returns:
            (final_candidates, excluded_signals) 元组
        """
        excluded: List[Dict[str, Any]] = []

        # Check max_position_size
        for candidate in candidates:
            if candidate.suggested_weight > constraints.max_position_size:
                logger.info(
                    "position size capped",
                    subject_id=candidate.subject_id,
                    original_weight=candidate.suggested_weight,
                    cap=constraints.max_position_size,
                )
                candidate.suggested_weight = constraints.max_position_size

        # Check sector concentration
        sector_weights: Dict[str, float] = defaultdict(float)
        sector_candidates: Dict[str, List[PortfolioCandidate]] = defaultdict(list)
        for candidate in candidates:
            if candidate.sector:
                sector_weights[candidate.sector] += candidate.suggested_weight
                sector_candidates[candidate.sector].append(candidate)

        for sector, total_weight in sector_weights.items():
            if total_weight > constraints.max_sector_concentration:
                # 按权重从低到高排除，直到满足约束
                sector_cands = sorted(sector_candidates[sector], key=lambda c: c.suggested_weight)
                for cand in sector_cands:
                    if sector_weights[sector] <= constraints.max_sector_concentration:
                        break
                    sector_weights[sector] -= cand.suggested_weight
                    excluded.append(
                        {
                            "signal_id": cand.signal_id,
                            "subject_id": cand.subject_id,
                            "event_type": cand.event_type,
                            "reason": "max_sector_concentration",
                            "detail": f"Sector {sector} weight {total_weight:.2%} exceeds limit {constraints.max_sector_concentration:.2%}",
                        }
                    )
                    cand.suggested_weight = 0.0  # mark for removal

        # Check theme concentration
        theme_weights: Dict[str, float] = defaultdict(float)
        theme_candidates: Dict[str, List[PortfolioCandidate]] = defaultdict(list)
        for candidate in candidates:
            if candidate.theme:
                theme_weights[candidate.theme] += candidate.suggested_weight
                theme_candidates[candidate.theme].append(candidate)

        for theme, total_weight in theme_weights.items():
            if total_weight > constraints.max_theme_concentration:
                theme_cands = sorted(theme_candidates[theme], key=lambda c: c.suggested_weight)
                for cand in theme_cands:
                    if theme_weights[theme] <= constraints.max_theme_concentration:
                        break
                    theme_weights[theme] -= cand.suggested_weight
                    excluded.append(
                        {
                            "signal_id": cand.signal_id,
                            "subject_id": cand.subject_id,
                            "event_type": cand.event_type,
                            "reason": "max_theme_concentration",
                            "detail": f"Theme {theme} weight {total_weight:.2%} exceeds limit {constraints.max_theme_concentration:.2%}",
                        }
                    )
                    cand.suggested_weight = 0.0

        # Remove zero-weight candidates
        final_candidates = [c for c in candidates if c.suggested_weight > 0]

        # Re-normalize after all constraint adjustments
        if final_candidates:
            total = sum(c.suggested_weight for c in final_candidates)
            if total > 0:
                for c in final_candidates:
                    c.suggested_weight = c.suggested_weight / total

        return final_candidates, excluded

    def size_positions(
        self,
        ranked_candidates: List[PortfolioCandidate],
        constraints: PortfolioConstraints,
    ) -> List[PortfolioCandidate]:
        """仓位定权：根据综合评分分配权重（归一化）。

        使用 suggested_weight 字段存储综合评分，然后归一化。

        Args:
            ranked_candidates: 已排序的候选列表（suggested_weight 已设为综合评分）
            constraints: 组合约束

        Returns:
            定权后的候选列表
        """
        if not ranked_candidates:
            return ranked_candidates

        # Cap at max_candidates
        if len(ranked_candidates) > constraints.max_candidates:
            logger.info(
                "candidates capped at max_candidates",
                original_count=len(ranked_candidates),
                max_candidates=constraints.max_candidates,
            )
            ranked_candidates = ranked_candidates[: constraints.max_candidates]

        # Normalize weights
        total_score = sum(c.suggested_weight for c in ranked_candidates)
        if total_score > 0:
            for c in ranked_candidates:
                c.suggested_weight = c.suggested_weight / total_score

        return ranked_candidates

    # ── 内部方法 ──────────────────────────────────────────

    def _filter_signals(
        self,
        signals: List[Any],
        constraints: PortfolioConstraints,
    ) -> Tuple[List[PortfolioCandidate], List[Dict[str, Any]]]:
        """过滤低于阈值的信号，转换为 PortfolioCandidate。"""
        candidates: List[PortfolioCandidate] = []
        excluded: List[Dict[str, Any]] = []

        for signal in signals:
            score = signal.score
            confidence = signal.confidence
            signal_id = signal.signal_id
            subject_id = signal.subject_id

            # Get event_type
            event_type = getattr(signal, "event_type", "generic")
            readiness = None
            timing_action = None
            sector = None
            theme = None

            # For EventAlphaSignal, extract additional fields
            if hasattr(signal, "timing_decision") and signal.timing_decision:
                readiness = getattr(signal.timing_decision, "action", None)
                timing_action = getattr(signal.timing_decision, "action", None)

            if hasattr(signal, "industry_impacts") and signal.industry_impacts:
                sector = signal.industry_impacts[0] if signal.industry_impacts else None

            if hasattr(signal, "impact_path") and signal.impact_path:
                theme = signal.impact_path[0] if signal.impact_path else None

            # Filter logic
            if score < constraints.min_signal_score:
                excluded.append(
                    {
                        "signal_id": signal_id,
                        "subject_id": subject_id,
                        "event_type": event_type,
                        "reason": "below_min_signal_score",
                        "detail": f"Score {score:.3f} < threshold {constraints.min_signal_score:.3f}",
                    }
                )
                continue

            if confidence < constraints.min_confidence:
                excluded.append(
                    {
                        "signal_id": signal_id,
                        "subject_id": subject_id,
                        "event_type": event_type,
                        "reason": "below_min_confidence",
                        "detail": f"Confidence {confidence:.3f} < threshold {constraints.min_confidence:.3f}",
                    }
                )
                continue

            candidate = PortfolioCandidate(
                signal_id=signal_id,
                subject_id=subject_id,
                event_type=event_type,
                signal_score=score,
                signal_confidence=confidence,
                readiness=readiness,
                timing_action=timing_action,
                suggested_weight=0.0,  # will be set during ranking
                historical_hit_rate=None,
                historical_avg_excess_return=None,
                sector=sector,
                theme=theme,
            )
            candidates.append(candidate)

        return candidates, excluded

    def _enrich_candidates(self, candidates: List[PortfolioCandidate]) -> List[PortfolioCandidate]:
        """补充历史质量数据。"""
        for candidate in candidates:
            hit_rate, avg_excess = self.get_historical_quality(
                candidate.subject_id, candidate.event_type
            )
            candidate.historical_hit_rate = hit_rate
            candidate.historical_avg_excess_return = avg_excess

        return candidates

    def _rank_candidates(self, candidates: List[PortfolioCandidate]) -> List[PortfolioCandidate]:
        """按综合评分排序：score * confidence * historical_hit_rate。

        如果 historical_hit_rate 不可用，使用 0.5 作为中性默认值。
        综合评分存储在 suggested_weight 中，后续用于仓位定权。
        """
        for candidate in candidates:
            hit_rate = (
                candidate.historical_hit_rate if candidate.historical_hit_rate is not None else 0.5
            )
            composite = candidate.signal_score * candidate.signal_confidence * hit_rate
            candidate.suggested_weight = composite

        candidates.sort(key=lambda c: c.suggested_weight, reverse=True)
        return candidates

    # ── 查询方法 ──────────────────────────────────────────

    def get_proposal(self, proposal_id: str) -> Optional[PortfolioProposal]:
        """获取组合提案。"""
        if self._portfolio_repo:
            return self._portfolio_repo.get_proposal(proposal_id)
        return None

    def list_proposals(self, limit: int = 100) -> List[PortfolioProposal]:
        """列出历史提案。"""
        if self._portfolio_repo:
            return self._portfolio_repo.list_proposals(limit=limit)
        return []
