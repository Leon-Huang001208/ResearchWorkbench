"""Paper Trading 和 Portfolio Simulation 服务。

模拟组合在时间序列上的运行，包括建仓/调仓/成本建模/绩效计算/基准比较。
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.contracts.paper_trading import (
    BenchmarkComparison,
    PaperPortfolio,
    PerformanceMetrics,
    PortfolioSnapshot,
    PositionSnapshot,
    RebalanceEvent,
    RebalanceTrigger,
    SimulationAssumptions,
    SimulationMode,
    SimulationResult,
)
from core.contracts.portfolio import PortfolioProposal
from core.observability import get_logger

logger = get_logger(__name__)


class PaperTradingService:
    """模拟交易核心服务"""

    def __init__(
        self,
        portfolio_repository: Optional[Any] = None,
        paper_trading_repository: Optional[Any] = None,
        outcome_repository: Optional[Any] = None,
    ):
        self._portfolio_repo = portfolio_repository
        self._paper_trading_repo = paper_trading_repository
        self._outcome_repo = outcome_repository

    # ── 创建模拟组合 ────────────────────────────────────

    def create_paper_portfolio(
        self,
        proposal: PortfolioProposal,
        name: Optional[str] = None,
        assumptions: Optional[SimulationAssumptions] = None,
    ) -> PaperPortfolio:
        """从组合提案创建模拟组合。

        Args:
            proposal: 组合提案
            name: 组合名称
            assumptions: 模拟假设

        Returns:
            PaperPortfolio 模拟组合实例
        """
        if assumptions is None:
            assumptions = SimulationAssumptions()
        if name is None:
            name = f"paper_{proposal.name}"

        portfolio_id = str(uuid.uuid4())

        # 构建初始持仓快照
        initial_capital = assumptions.initial_capital
        positions: List[PositionSnapshot] = []
        for subject_id, weight in proposal.allocations.items():
            allocated = initial_capital * weight
            positions.append(
                PositionSnapshot(
                    subject_id=subject_id,
                    weight=weight,
                    shares=allocated,  # 简化：1元1股
                    entry_price=1.0,
                    current_price=1.0,
                    market_value=allocated,
                    unrealized_pnl=0.0,
                    unrealized_pnl_pct=0.0,
                    cost_basis=allocated,
                )
            )

        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            nav=1.0,
            total_value=initial_capital,
            cash=0.0,
            positions=positions,
            gross_exposure=1.0,
            net_exposure=1.0,
        )

        paper_portfolio = PaperPortfolio(
            portfolio_id=portfolio_id,
            proposal_id=proposal.proposal_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            assumptions=assumptions,
            status="active",
            current_snapshot=snapshot,
            snapshots=[snapshot],
            rebalance_events=[],
            metadata={"proposal_allocations": proposal.allocations},
        )

        if self._paper_trading_repo:
            self._paper_trading_repo.save_paper_portfolio(paper_portfolio)
            logger.info(
                "paper portfolio created and persisted",
                portfolio_id=portfolio_id,
                proposal_id=proposal.proposal_id,
            )
        else:
            logger.info(
                "paper portfolio created (no repository)",
                portfolio_id=portfolio_id,
            )

        return paper_portfolio

    # ── 调仓 ────────────────────────────────────────────

    def rebalance(
        self,
        portfolio: PaperPortfolio,
        target_allocations: Dict[str, float],
        prices: Dict[str, float],
        trigger: RebalanceTrigger = RebalanceTrigger.SCHEDULED,
        timestamp: Optional[datetime] = None,
    ) -> Tuple[PaperPortfolio, RebalanceEvent]:
        """执行调仓操作。

        计算当前权重 vs 目标权重的差异，生成交易指令，
        应用滑点和交易成本，更新持仓和快照。

        Args:
            portfolio: 当前模拟组合
            target_allocations: 目标权重 {subject_id: weight}
            prices: 当前价格 {subject_id: price}
            trigger: 调仓触发类型
            timestamp: 调仓时间

        Returns:
            (更新后的组合, 调仓事件)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        assumptions = portfolio.assumptions
        cost_model = assumptions.transaction_cost

        # 获取当前持仓权重
        prior_allocations: Dict[str, float] = {}
        current_positions: Dict[str, PositionSnapshot] = {}

        if portfolio.current_snapshot:
            for pos in portfolio.current_snapshot.positions:
                prior_allocations[pos.subject_id] = pos.weight
                current_positions[pos.subject_id] = pos

        # 计算换手率 (half-turnover)
        all_keys = set(prior_allocations.keys()) | set(target_allocations.keys())
        total_abs_drift = 0.0
        for key in all_keys:
            old_w = prior_allocations.get(key, 0.0)
            new_w = target_allocations.get(key, 0.0)
            total_abs_drift += abs(new_w - old_w)
        turnover = total_abs_drift / 2.0

        # 计算当前 NAV
        total_value = (
            portfolio.current_snapshot.total_value
            if portfolio.current_snapshot
            else assumptions.initial_capital
        )

        # 生成交易明细和成本
        trades: List[Dict[str, Any]] = []
        total_commission = 0.0
        total_slippage = 0.0
        total_stamp_tax = 0.0

        for subject_id in all_keys:
            old_w = prior_allocations.get(subject_id, 0.0)
            new_w = target_allocations.get(subject_id, 0.0)
            weight_delta = new_w - old_w

            if abs(weight_delta) < 1e-8:
                continue

            price = prices.get(subject_id, 1.0)
            trade_value = abs(weight_delta) * total_value

            # 佣金
            commission = max(trade_value * cost_model.commission_rate, cost_model.commission_min)

            # 滑点
            slippage = trade_value * cost_model.slippage_bps / 10000.0

            # 印花税（仅卖出）
            stamp_tax = 0.0
            if weight_delta < 0:
                stamp_tax = trade_value * cost_model.stamp_tax_rate

            # 市场冲击
            impact = trade_value * cost_model.impact_rate

            action = "buy" if weight_delta > 0 else "sell"
            trades.append(
                {
                    "subject_id": subject_id,
                    "action": action,
                    "weight_delta": weight_delta,
                    "trade_value": trade_value,
                    "price": price,
                    "commission": commission,
                    "slippage": slippage,
                    "stamp_tax": stamp_tax,
                    "impact": impact,
                }
            )

            total_commission += commission
            total_slippage += slippage + impact
            total_stamp_tax += stamp_tax

        total_cost = total_commission + total_slippage + total_stamp_tax

        # 构建调仓事件
        rebalance_id = str(uuid.uuid4())
        rebalance_event = RebalanceEvent(
            rebalance_id=rebalance_id,
            portfolio_id=portfolio.portfolio_id,
            timestamp=timestamp,
            trigger=trigger,
            prior_allocations=prior_allocations,
            target_allocations=target_allocations,
            trades=trades,
            turnover=turnover,
            transaction_cost=total_commission + total_stamp_tax,
            slippage_cost=total_slippage,
            total_cost=total_cost,
        )

        # 更新持仓快照
        new_value = total_value - total_cost
        new_positions: List[PositionSnapshot] = []
        for subject_id, weight in target_allocations.items():
            if weight < 1e-8:
                continue
            price = prices.get(subject_id, 1.0)
            allocated = new_value * weight
            old_pos = current_positions.get(subject_id)
            entry_price = old_pos.entry_price if old_pos else price

            new_positions.append(
                PositionSnapshot(
                    subject_id=subject_id,
                    weight=weight,
                    shares=allocated / price if price > 0 else 0.0,
                    entry_price=entry_price,
                    current_price=price,
                    market_value=allocated,
                    unrealized_pnl=allocated - (old_pos.cost_basis if old_pos else allocated),
                    unrealized_pnl_pct=(
                        allocated
                        / (old_pos.cost_basis if old_pos and old_pos.cost_basis > 0 else allocated)
                    )
                    - 1.0
                    if old_pos
                    else 0.0,
                    cost_basis=allocated,
                )
            )

        new_nav = new_value / assumptions.initial_capital
        new_snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            nav=new_nav,
            total_value=new_value,
            cash=0.0,
            positions=new_positions,
            gross_exposure=sum(p.weight for p in new_positions),
            net_exposure=sum(p.weight for p in new_positions),
        )

        # 更新 portfolio
        portfolio.current_snapshot = new_snapshot
        portfolio.snapshots.append(new_snapshot)
        portfolio.rebalance_events.append(rebalance_event)

        if self._paper_trading_repo:
            self._paper_trading_repo.save_paper_portfolio(portfolio)

        logger.info(
            "rebalance executed",
            portfolio_id=portfolio.portfolio_id,
            rebalance_id=rebalance_id,
            turnover=turnover,
            total_cost=total_cost,
            num_trades=len(trades),
        )

        return portfolio, rebalance_event

    # ── 每日增量更新 ────────────────────────────────────

    def update_daily(
        self,
        portfolio: PaperPortfolio,
        prices: Dict[str, float],
        date: Optional[datetime] = None,
    ) -> PaperPortfolio:
        """每日增量更新：用最新价格更新持仓市值和 NAV。

        不做调仓，仅更新快照。

        Args:
            portfolio: 模拟组合
            prices: 最新价格 {subject_id: price}
            date: 日期

        Returns:
            更新后的组合
        """
        if date is None:
            date = datetime.now(timezone.utc)

        if not portfolio.current_snapshot:
            return portfolio

        total_value = 0.0
        updated_positions: List[PositionSnapshot] = []

        for pos in portfolio.current_snapshot.positions:
            price = prices.get(pos.subject_id, pos.current_price)
            market_value = pos.shares * price
            unrealized_pnl = market_value - pos.cost_basis
            unrealized_pnl_pct = (
                (market_value / pos.cost_basis - 1.0) if pos.cost_basis > 0 else 0.0
            )
            total_value += market_value

            updated_positions.append(
                PositionSnapshot(
                    subject_id=pos.subject_id,
                    weight=0.0,  # 重新计算
                    shares=pos.shares,
                    entry_price=pos.entry_price,
                    current_price=price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    cost_basis=pos.cost_basis,
                )
            )

        # Recalculate weights
        for pos in updated_positions:
            pos.weight = pos.market_value / total_value if total_value > 0 else 0.0

        nav = total_value / portfolio.assumptions.initial_capital
        snapshot = PortfolioSnapshot(
            timestamp=date,
            nav=nav,
            total_value=total_value,
            cash=0.0,
            positions=updated_positions,
            gross_exposure=sum(p.weight for p in updated_positions),
            net_exposure=sum(p.weight for p in updated_positions),
        )

        portfolio.current_snapshot = snapshot
        portfolio.snapshots.append(snapshot)

        if self._paper_trading_repo:
            self._paper_trading_repo.save_paper_portfolio(portfolio)

        logger.info(
            "daily update",
            portfolio_id=portfolio.portfolio_id,
            nav=nav,
            date=date.isoformat() if date else None,
        )

        return portfolio

    # ── 绩效计算 ────────────────────────────────────────

    def compute_performance(
        self,
        portfolio: PaperPortfolio,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> PerformanceMetrics:
        """计算绩效指标。

        Args:
            portfolio: 模拟组合
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            PerformanceMetrics 绩效指标
        """
        snapshots = portfolio.snapshots
        if not snapshots:
            return PerformanceMetrics(
                start_date=start_date or portfolio.created_at,
                end_date=end_date or datetime.now(timezone.utc),
            )

        # 过滤日期范围
        if start_date:
            snapshots = [s for s in snapshots if s.timestamp >= start_date]
        if end_date:
            snapshots = [s for s in snapshots if s.timestamp <= end_date]

        if len(snapshots) < 2:
            return PerformanceMetrics(
                start_date=snapshots[0].timestamp if snapshots else portfolio.created_at,
                end_date=snapshots[-1].timestamp if snapshots else datetime.now(timezone.utc),
            )

        start_nav = snapshots[0].nav
        end_nav = snapshots[-1].nav
        total_return = end_nav / start_nav - 1.0 if start_nav > 0 else 0.0

        # 交易日数
        num_days = len(snapshots) - 1
        if num_days < 1:
            num_days = 1

        # 年化收益 (252交易日)
        annualized_return = (
            (1.0 + total_return) ** (252.0 / num_days) - 1.0 if num_days > 0 else 0.0
        )

        # 最大回撤
        max_drawdown = self._compute_max_drawdown(snapshots)

        # 日收益率序列
        daily_returns = self._compute_daily_returns(snapshots)

        # 夏普比率 (假设无风险利率为 2%)
        sharpe_ratio = self._compute_sharpe_ratio(daily_returns, risk_free_rate=0.02)

        # 索提诺比率
        sortino_ratio = self._compute_sortino_ratio(daily_returns, risk_free_rate=0.02)

        # 胜率
        hit_rate = self._compute_hit_rate(daily_returns)

        # 平均盈亏
        avg_win, avg_loss = self._compute_avg_win_loss(daily_returns)
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else None

        # 换手率
        total_turnover = sum(r.turnover for r in portfolio.rebalance_events)

        # 平均暴露
        avg_exposure = (
            sum(s.gross_exposure for s in snapshots) / len(snapshots) if snapshots else 1.0
        )

        # 累计交易成本
        total_transaction_costs = sum(r.total_cost for r in portfolio.rebalance_events)

        metrics = PerformanceMetrics(
            start_date=snapshots[0].timestamp,
            end_date=snapshots[-1].timestamp,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            hit_rate=hit_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_loss_ratio=win_loss_ratio,
            turnover=total_turnover,
            avg_exposure=avg_exposure,
            total_transaction_costs=total_transaction_costs,
            num_rebalances=len(portfolio.rebalance_events),
            num_trading_days=num_days,
        )

        logger.info(
            "performance computed",
            portfolio_id=portfolio.portfolio_id,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
        )

        return metrics

    # ── 基准比较 ────────────────────────────────────────

    def compare_benchmarks(
        self,
        portfolio: PaperPortfolio,
        benchmark_returns: Dict[str, float],
        benchmark_nav_series: Optional[Dict[str, List[float]]] = None,
    ) -> List[BenchmarkComparison]:
        """与基准进行比较。

        Args:
            portfolio: 模拟组合
            benchmark_returns: 基准收益 {benchmark_name: return}
            benchmark_nav_series: 基准 NAV 序列 {benchmark_name: [nav1, nav2, ...]}

        Returns:
            基准比较列表
        """
        metrics = self.compute_performance(portfolio)
        portfolio_return = metrics.total_return
        daily_returns = self._compute_daily_returns(portfolio.snapshots)

        comparisons: List[BenchmarkComparison] = []

        for bench_name, bench_return in benchmark_returns.items():
            excess_return = portfolio_return - bench_return

            # Tracking error 和 Information Ratio（需要基准日收益率序列）
            tracking_error = None
            information_ratio = None
            beta = None
            alpha = None

            if benchmark_nav_series and bench_name in benchmark_nav_series:
                bench_navs = benchmark_nav_series[bench_name]
                if len(bench_navs) >= 2:
                    bench_daily_returns = [
                        bench_navs[i] / bench_navs[i - 1] - 1.0
                        for i in range(1, len(bench_navs))
                        if bench_navs[i - 1] > 0
                    ]

                    # 对齐长度
                    min_len = min(len(daily_returns), len(bench_daily_returns))
                    if min_len > 1:
                        aligned_portfolio = daily_returns[:min_len]
                        aligned_bench = bench_daily_returns[:min_len]

                        # Tracking error
                        diffs = [a - b for a, b in zip(aligned_portfolio, aligned_bench)]
                        mean_diff = sum(diffs) / len(diffs)
                        variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
                        tracking_error = (variance**0.5) * (252**0.5) if variance > 0 else 0.0

                        # Information ratio
                        if tracking_error and tracking_error > 0:
                            information_ratio = (
                                (excess_return / tracking_error) if tracking_error > 0 else None
                            )

                        # Beta
                        bench_var = sum(
                            (b - sum(aligned_bench) / len(aligned_bench)) ** 2
                            for b in aligned_bench
                        ) / len(aligned_bench)
                        if bench_var > 0:
                            bench_mean = sum(aligned_bench) / len(aligned_bench)
                            port_mean = sum(aligned_portfolio) / len(aligned_portfolio)
                            cov = sum(
                                (a - port_mean) * (b - bench_mean)
                                for a, b in zip(aligned_portfolio, aligned_bench)
                            ) / len(aligned_portfolio)
                            beta = cov / bench_var

                            # Alpha (annualized)
                            annualized_bench = (1.0 + bench_return) ** (
                                252.0 / max(metrics.num_trading_days, 1)
                            ) - 1.0
                            risk_free_daily = 0.02 / 252
                            alpha = metrics.annualized_return - (
                                risk_free_daily * 252
                                + (beta or 1.0) * (annualized_bench - risk_free_daily * 252)
                            )

            comparisons.append(
                BenchmarkComparison(
                    benchmark_name=bench_name,
                    benchmark_return=bench_return,
                    portfolio_return=portfolio_return,
                    excess_return=excess_return,
                    tracking_error=tracking_error,
                    information_ratio=information_ratio,
                    beta=beta,
                    alpha=alpha,
                )
            )

        return comparisons

    # ── 生成基准收益 ────────────────────────────────────

    def generate_equal_weight_baseline(
        self,
        subject_ids: List[str],
        price_history: Dict[str, List[float]],
    ) -> Tuple[float, List[float]]:
        """生成等权基准收益。

        Args:
            subject_ids: 主体列表
            price_history: 价格历史 {subject_id: [price1, price2, ...]}

        Returns:
            (总收益率, NAV序列)
        """
        if not subject_ids or not price_history:
            return 0.0, [1.0]

        # 找出最短价格序列长度
        min_len = min(
            len(price_history[sid])
            for sid in subject_ids
            if sid in price_history and len(price_history[sid]) > 0
        )
        if min_len < 2:
            return 0.0, [1.0]

        # 等权 NAV
        nav_series = [1.0]
        n = len(subject_ids)

        for i in range(1, min_len):
            daily_return = 0.0
            valid_count = 0
            for sid in subject_ids:
                prices = price_history.get(sid, [])
                if len(prices) > i and prices[i - 1] > 0:
                    daily_return += prices[i] / prices[i - 1] - 1.0
                    valid_count += 1

            if valid_count > 0:
                daily_return /= valid_count
            nav_series.append(nav_series[-1] * (1.0 + daily_return))

        total_return = nav_series[-1] / nav_series[0] - 1.0
        return total_return, nav_series

    def generate_top_k_signal_baseline(
        self,
        candidates: List[Dict[str, Any]],
        price_history: Dict[str, List[float]],
        k: int = 5,
    ) -> Tuple[float, List[float]]:
        """生成 Top-K 信号基准收益。

        选取评分最高的 k 个信号，等权组合。

        Args:
            candidates: 候选列表 [{subject_id, score, ...}]
            price_history: 价格历史
            k: 选取数量

        Returns:
            (总收益率, NAV序列)
        """
        sorted_candidates = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
        top_k_subjects = [c["subject_id"] for c in sorted_candidates[:k]]

        return self.generate_equal_weight_baseline(top_k_subjects, price_history)

    # ── 回放驱动模拟 ────────────────────────────────────

    def run_replay_simulation(
        self,
        proposal: PortfolioProposal,
        price_history: Dict[str, List[float]],
        dates: List[datetime],
        assumptions: Optional[SimulationAssumptions] = None,
        name: Optional[str] = None,
    ) -> SimulationResult:
        """运行回放驱动的模拟交易。

        基于历史价格序列，逐日模拟组合表现，
        按设定的调仓频率执行调仓。

        Args:
            proposal: 组合提案
            price_history: 价格历史 {subject_id: [price1, price2, ...]}
            dates: 日期序列
            assumptions: 模拟假设
            name: 模拟名称

        Returns:
            SimulationResult 模拟结果
        """
        if assumptions is None:
            assumptions = SimulationAssumptions(mode=SimulationMode.REPLAY)

        # 创建模拟组合
        portfolio = self.create_paper_portfolio(proposal, name=name, assumptions=assumptions)

        subject_ids = list(proposal.allocations.keys())
        num_days = min(
            len(dates),
            max(len(price_history.get(sid, [])) for sid in subject_ids) if subject_ids else 0,
        )

        if num_days < 2:
            logger.warning("insufficient price history for simulation", num_days=num_days)
            result_id = str(uuid.uuid4())
            return SimulationResult(
                result_id=result_id,
                portfolio_id=portfolio.portfolio_id,
                name=name or portfolio.name,
                created_at=datetime.now(timezone.utc),
                mode=SimulationMode.REPLAY,
                assumptions=assumptions,
                performance=self.compute_performance(portfolio),
                rebalance_count=0,
            )

        # 逐日模拟
        rebalance_counter = 0
        for day_idx in range(1, num_days):
            date = dates[day_idx]
            prices = {}
            for sid in subject_ids:
                history = price_history.get(sid, [])
                if day_idx < len(history):
                    prices[sid] = history[day_idx]

            # 更新每日快照
            portfolio = self.update_daily(portfolio, prices, date=date)

            # 检查是否需要调仓
            rebalance_counter += 1
            if rebalance_counter >= assumptions.rebalance_frequency_days:
                # 检查偏离阈值
                if self._check_drift_threshold(
                    portfolio, proposal.allocations, assumptions.drift_threshold
                ):
                    portfolio, _ = self.rebalance(
                        portfolio,
                        proposal.allocations,
                        prices,
                        trigger=RebalanceTrigger.SCHEDULED,
                        timestamp=date,
                    )
                    rebalance_counter = 0

        # 计算绩效
        performance = self.compute_performance(portfolio)

        # 计算基准收益
        benchmark_comparisons: List[BenchmarkComparison] = []
        benchmark_nav_series: Dict[str, List[float]] = {}

        # 等权基准
        if "equal_weight" in assumptions.benchmark_ids:
            eq_return, eq_nav = self.generate_equal_weight_baseline(subject_ids, price_history)
            benchmark_returns = {"equal_weight": eq_return}
            benchmark_nav_series["equal_weight"] = eq_nav
            comparisons = self.compare_benchmarks(
                portfolio, benchmark_returns, benchmark_nav_series
            )
            benchmark_comparisons.extend(comparisons)

        # Top-K 信号基准
        if "top_k_signal" in assumptions.benchmark_ids:
            candidates = [
                {"subject_id": sid, "score": proposal.allocations.get(sid, 0.0)}
                for sid in subject_ids
            ]
            top_k_return, top_k_nav = self.generate_top_k_signal_baseline(candidates, price_history)
            benchmark_returns = {"top_k_signal": top_k_return}
            benchmark_nav_series["top_k_signal"] = top_k_nav
            comparisons = self.compare_benchmarks(
                portfolio, benchmark_returns, benchmark_nav_series
            )
            benchmark_comparisons.extend(comparisons)

        # 生成 NAV 序列
        nav_series = [{"date": s.timestamp.isoformat(), "nav": s.nav} for s in portfolio.snapshots]

        total_turnover = sum(r.turnover for r in portfolio.rebalance_events)

        result_id = str(uuid.uuid4())
        result = SimulationResult(
            result_id=result_id,
            portfolio_id=portfolio.portfolio_id,
            name=name or portfolio.name,
            created_at=datetime.now(timezone.utc),
            mode=SimulationMode.REPLAY,
            assumptions=assumptions,
            performance=performance,
            benchmark_comparisons=benchmark_comparisons,
            nav_series=nav_series,
            rebalance_count=len(portfolio.rebalance_events),
            total_turnover=total_turnover,
        )

        # 持久化
        if self._paper_trading_repo:
            self._paper_trading_repo.save_simulation_result(result)
            logger.info(
                "simulation result persisted",
                result_id=result_id,
                portfolio_id=portfolio.portfolio_id,
            )

        logger.info(
            "replay simulation completed",
            result_id=result_id,
            total_return=performance.total_return,
            max_drawdown=performance.max_drawdown,
            num_rebalances=len(portfolio.rebalance_events),
        )

        return result

    # ── 查询方法 ────────────────────────────────────────

    def get_paper_portfolio(self, portfolio_id: str) -> Optional[PaperPortfolio]:
        """获取模拟组合"""
        if self._paper_trading_repo:
            return self._paper_trading_repo.get_paper_portfolio(portfolio_id)
        return None

    def list_paper_portfolios(self, limit: int = 100) -> List[PaperPortfolio]:
        """列出模拟组合"""
        if self._paper_trading_repo:
            return self._paper_trading_repo.list_paper_portfolios(limit=limit)
        return []

    def get_simulation_result(self, result_id: str) -> Optional[SimulationResult]:
        """获取模拟结果"""
        if self._paper_trading_repo:
            return self._paper_trading_repo.get_simulation_result(result_id)
        return None

    def list_simulation_results(
        self, portfolio_id: Optional[str] = None, limit: int = 100
    ) -> List[SimulationResult]:
        """列出模拟结果"""
        if self._paper_trading_repo:
            return self._paper_trading_repo.list_simulation_results(
                portfolio_id=portfolio_id, limit=limit
            )
        return []

    # ── 内部计算方法 ────────────────────────────────────

    def _compute_max_drawdown(self, snapshots: List[PortfolioSnapshot]) -> float:
        """计算最大回撤"""
        if not snapshots:
            return 0.0

        peak = snapshots[0].nav
        max_dd = 0.0

        for snapshot in snapshots:
            if snapshot.nav > peak:
                peak = snapshot.nav
            dd = (peak - snapshot.nav) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _compute_daily_returns(self, snapshots: List[PortfolioSnapshot]) -> List[float]:
        """计算日收益率序列"""
        returns = []
        for i in range(1, len(snapshots)):
            prev_nav = snapshots[i - 1].nav
            curr_nav = snapshots[i].nav
            if prev_nav > 0:
                returns.append(curr_nav / prev_nav - 1.0)
            else:
                returns.append(0.0)
        return returns

    def _compute_sharpe_ratio(
        self, daily_returns: List[float], risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """计算夏普比率"""
        if len(daily_returns) < 2:
            return None

        avg_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance**0.5

        if std_dev < 1e-10:
            return None

        # 年化
        daily_rf = risk_free_rate / 252
        excess_return = (avg_return - daily_rf) * 252
        annualized_std = std_dev * (252**0.5)

        return excess_return / annualized_std if annualized_std > 0 else None

    def _compute_sortino_ratio(
        self, daily_returns: List[float], risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """计算索提诺比率"""
        if len(daily_returns) < 2:
            return None

        daily_rf = risk_free_rate / 252
        downside_returns = [r for r in daily_returns if r < daily_rf]

        if not downside_returns:
            return None

        downside_std = (
            sum((r - daily_rf) ** 2 for r in downside_returns) / len(daily_returns)
        ) ** 0.5
        annualized_downside_std = downside_std * (252**0.5)

        avg_return = sum(daily_returns) / len(daily_returns)
        annualized_excess = (avg_return - daily_rf) * 252

        return annualized_excess / annualized_downside_std if annualized_downside_std > 0 else None

    def _compute_hit_rate(self, daily_returns: List[float]) -> float:
        """计算胜率"""
        if not daily_returns:
            return 0.0
        wins = sum(1 for r in daily_returns if r > 0)
        return wins / len(daily_returns)

    def _compute_avg_win_loss(self, daily_returns: List[float]) -> Tuple[float, float]:
        """计算平均盈利和平均亏损"""
        wins = [r for r in daily_returns if r > 0]
        losses = [r for r in daily_returns if r < 0]

        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        return avg_win, avg_loss

    def _check_drift_threshold(
        self,
        portfolio: PaperPortfolio,
        target_allocations: Dict[str, float],
        threshold: float,
    ) -> bool:
        """检查偏离是否超过阈值，决定是否触发调仓"""
        if not portfolio.current_snapshot:
            return True

        current_weights = {
            pos.subject_id: pos.weight for pos in portfolio.current_snapshot.positions
        }

        all_keys = set(current_weights.keys()) | set(target_allocations.keys())
        for key in all_keys:
            current = current_weights.get(key, 0.0)
            target = target_allocations.get(key, 0.0)
            if abs(current - target) > threshold:
                return True

        return False
