"""
Core contracts for paper trading and portfolio simulation.

This module defines Pydantic models for simulating trading and portfolio
performance, including PaperPortfolio, RebalanceEvent, SimulationResult,
PerformanceMetrics, and more, for tracking simulated portfolio performance
over time in Research Workbench.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SimulationMode(str, Enum):
    """模拟模式"""

    REPLAY = "replay"  # 回放驱动：基于历史事件逐日回放
    INCREMENTAL = "incremental"  # 增量模式：每日增量更新


class RebalanceTrigger(str, Enum):
    """调仓触发类型"""

    SCHEDULED = "scheduled"  # 定期调仓
    SIGNAL_DRIVEN = "signal_driven"  # 信号驱动调仓
    THRESHOLD = "threshold"  # 偏离阈值触发
    MANUAL = "manual"  # 手动触发


class PositionSnapshot(BaseModel):
    """持仓快照 — 某一时点的单个持仓状态"""

    subject_id: str
    weight: float = 0.0
    shares: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    cost_basis: float = 0.0


class PortfolioSnapshot(BaseModel):
    """组合快照 — 某一时点的整体组合状态"""

    timestamp: datetime
    nav: float = 1.0  # 净值
    total_value: float = 1.0  # 总市值
    cash: float = 0.0  # 现金
    positions: List[PositionSnapshot] = Field(default_factory=list)
    gross_exposure: float = 1.0  # 总暴露
    net_exposure: float = 1.0  # 净暴露


class TransactionCost(BaseModel):
    """交易成本模型"""

    commission_rate: float = 0.0003  # 佣金率 (万三)
    commission_min: float = 5.0  # 最低佣金 (元)
    slippage_bps: float = 5.0  # 滑点 (基点)
    stamp_tax_rate: float = 0.001  # 印花税 (千一，仅卖出)
    impact_rate: float = 0.0001  # 市场冲击率


class RebalanceEvent(BaseModel):
    """调仓事件 — 记录一次调仓的完整信息"""

    rebalance_id: str
    portfolio_id: str
    timestamp: datetime
    trigger: RebalanceTrigger = RebalanceTrigger.SCHEDULED
    prior_allocations: Dict[str, float] = Field(default_factory=dict)  # subject_id -> weight
    target_allocations: Dict[str, float] = Field(default_factory=dict)  # subject_id -> weight
    trades: List[Dict[str, Any]] = Field(default_factory=list)  # 交易明细
    turnover: float = 0.0  # 换手率
    transaction_cost: float = 0.0  # 交易成本
    slippage_cost: float = 0.0  # 滑点成本
    total_cost: float = 0.0  # 总成本


class PerformanceMetrics(BaseModel):
    """绩效指标 — 某一时段内的组合表现"""

    start_date: datetime
    end_date: datetime
    total_return: float = 0.0  # 总收益
    annualized_return: float = 0.0  # 年化收益
    max_drawdown: float = 0.0  # 最大回撤
    sharpe_ratio: Optional[float] = None  # 夏普比率
    sortino_ratio: Optional[float] = None  # 索提诺比率
    hit_rate: float = 0.0  # 胜率
    avg_win: float = 0.0  # 平均盈利
    avg_loss: float = 0.0  # 平均亏损
    win_loss_ratio: Optional[float] = None  # 盈亏比
    turnover: float = 0.0  # 换手率
    avg_exposure: float = 1.0  # 平均暴露
    total_transaction_costs: float = 0.0  # 累计交易成本
    num_rebalances: int = 0  # 调仓次数
    num_trading_days: int = 0  # 交易日数


class BenchmarkComparison(BaseModel):
    """基准比较 — 模拟组合 vs 基准"""

    benchmark_name: str
    benchmark_return: float = 0.0
    portfolio_return: float = 0.0
    excess_return: float = 0.0
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    beta: Optional[float] = None
    alpha: Optional[float] = None


class SimulationAssumptions(BaseModel):
    """模拟假设 — 显式记录所有模拟假设，确保可复现"""

    initial_capital: float = 1_000_000.0  # 初始资金
    transaction_cost: TransactionCost = Field(default_factory=TransactionCost)
    rebalance_frequency_days: int = 5  # 调仓频率（天）
    max_position_size: float = 0.15  # 单持仓上限
    drift_threshold: float = 0.05  # 偏离阈值（触发调仓）
    price_source: str = "close"  # 价格源
    settlement_delay_days: int = 1  # 结算延迟
    fractional_shares: bool = True  # 允许碎股
    benchmark_ids: List[str] = Field(default_factory=lambda: ["equal_weight", "top_k_signal"])
    mode: SimulationMode = SimulationMode.REPLAY


class PaperPortfolio(BaseModel):
    """模拟组合 — 跟踪一个组合提案在模拟环境中的运行"""

    portfolio_id: str
    proposal_id: str  # 关联的 PortfolioProposal
    name: str
    created_at: datetime
    assumptions: SimulationAssumptions = Field(default_factory=SimulationAssumptions)
    status: str = "active"  # active / paused / closed
    current_snapshot: Optional[PortfolioSnapshot] = None
    snapshots: List[PortfolioSnapshot] = Field(default_factory=list)
    rebalance_events: List[RebalanceEvent] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    """模拟结果 — 一次完整模拟的输出"""

    result_id: str
    portfolio_id: str
    name: str
    created_at: datetime
    mode: SimulationMode
    assumptions: SimulationAssumptions
    performance: PerformanceMetrics
    benchmark_comparisons: List[BenchmarkComparison] = Field(default_factory=list)
    nav_series: List[Dict[str, Any]] = Field(default_factory=list)  # [{date, nav, benchmark_nav}]
    rebalance_count: int = 0
    total_turnover: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
