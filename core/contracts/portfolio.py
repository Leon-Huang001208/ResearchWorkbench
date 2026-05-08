"""组合构建与风险预算契约。

将多个并发信号转为一致的投资组合，在显式约束下将评分信号转为排名配置。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioCandidate(BaseModel):
    """组合候选 — 来自单个信号的配置建议"""

    signal_id: str
    subject_id: str
    event_type: str
    signal_score: float
    signal_confidence: float
    readiness: Optional[str] = None  # from timing
    timing_action: Optional[str] = None
    suggested_weight: float = 0.0  # 初始权重
    historical_hit_rate: Optional[float] = None  # 从 Outcome 统计
    historical_avg_excess_return: Optional[float] = None
    sector: Optional[str] = None  # 行业标签，用于集中度约束
    theme: Optional[str] = None  # 主题标签，用于集中度约束


class PortfolioConstraints(BaseModel):
    """组合约束"""

    max_position_size: float = 0.15  # 单个持仓最大权重
    max_sector_concentration: float = 0.40  # 行业集中度上限
    max_theme_concentration: float = 0.30  # 主题集中度上限
    min_candidates: int = 3  # 最少候选数
    max_candidates: int = 20  # 最多候选数
    correlation_threshold: float = 0.7  # 相关性去重阈值
    min_signal_score: float = 0.3  # 最低信号分数
    min_confidence: float = 0.3  # 最低置信度
    regime_exposure_limit: Optional[Dict[str, float]] = None  # 市场环境暴露限制


class PortfolioProposal(BaseModel):
    """组合提案 — 多信号约束后的最终配置"""

    proposal_id: str
    name: str
    created_at: datetime
    candidates: List[PortfolioCandidate]
    allocations: Dict[str, float]  # subject_id -> weight
    constraints_applied: List[str]  # 应用过的约束列表
    excluded_signals: List[Dict[str, Any]]  # 被排除的信号及原因
    rationale: Dict[str, Any]  # 决策理由
