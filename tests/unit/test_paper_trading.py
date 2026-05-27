"""Paper Trading 和 Portfolio Simulation 测试。

测试覆盖：
- 创建模拟组合
- 调仓逻辑（权重变化、换手率、交易成本）
- 成本建模（佣金、滑点、印花税）
- 每日增量更新
- 绩效指标计算（总收益、最大回撤、夏普比率、胜率）
- 基准比较（等权基准、Top-K 信号基准）
- 回放驱动模拟完整流程
"""
from datetime import datetime, timedelta, timezone

from core.contracts.paper_trading import (
    PaperPortfolio,
    PortfolioSnapshot,
    RebalanceEvent,
    RebalanceTrigger,
    SimulationAssumptions,
    SimulationMode,
    TransactionCost,
)
from core.contracts.portfolio import PortfolioCandidate, PortfolioProposal
from services.paper_trading_service import PaperTradingService

# ─── 辅助函数 ────────────────────────────────────────────


def _make_proposal(
    allocations: dict[str, float] | None = None,
    name: str = "test_proposal",
) -> PortfolioProposal:
    """创建测试用组合提案"""
    if allocations is None:
        allocations = {"A": 0.4, "B": 0.35, "C": 0.25}

    candidates = [
        PortfolioCandidate(
            signal_id=f"sig-{sid}",
            subject_id=sid,
            event_type="earnings",
            signal_score=0.7,
            signal_confidence=0.8,
            suggested_weight=w,
        )
        for sid, w in allocations.items()
    ]

    return PortfolioProposal(
        proposal_id="prop-001",
        name=name,
        created_at=datetime.now(timezone.utc),
        candidates=candidates,
        allocations=allocations,
        constraints_applied=["position_sizing"],
        excluded_signals=[],
        rationale={"method": "test"},
    )


def _make_portfolio_with_snapshots(
    nav_series: list[float],
    start_date: datetime | None = None,
) -> PaperPortfolio:
    """创建带有 NAV 序列的模拟组合"""
    if start_date is None:
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

    assumptions = SimulationAssumptions(initial_capital=1_000_000.0)
    snapshots = []
    for i, nav in enumerate(nav_series):
        snapshots.append(
            PortfolioSnapshot(
                timestamp=start_date + timedelta(days=i),
                nav=nav,
                total_value=nav * assumptions.initial_capital,
                cash=0.0,
                positions=[],
                gross_exposure=1.0,
                net_exposure=1.0,
            )
        )

    return PaperPortfolio(
        portfolio_id="port-001",
        proposal_id="prop-001",
        name="test_paper",
        created_at=start_date,
        assumptions=assumptions,
        status="active",
        current_snapshot=snapshots[-1] if snapshots else None,
        snapshots=snapshots,
        rebalance_events=[],
    )


# ─── 创建模拟组合测试 ───────────────────────────────────


class TestCreatePaperPortfolio:
    """创建模拟组合测试"""

    def test_create_from_proposal(self):
        """从组合提案创建模拟组合"""
        service = PaperTradingService()
        proposal = _make_proposal()

        portfolio = service.create_paper_portfolio(proposal)

        assert portfolio.portfolio_id
        assert portfolio.proposal_id == "prop-001"
        assert portfolio.status == "active"
        assert portfolio.current_snapshot is not None
        assert portfolio.current_snapshot.nav == 1.0
        assert portfolio.current_snapshot.total_value == 1_000_000.0

    def test_create_positions_match_allocations(self):
        """初始持仓与提案分配一致"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.3, "C": 0.2})

        portfolio = service.create_paper_portfolio(proposal)

        positions = {p.subject_id: p for p in portfolio.current_snapshot.positions}
        assert abs(positions["A"].weight - 0.5) < 1e-6
        assert abs(positions["B"].weight - 0.3) < 1e-6
        assert abs(positions["C"].weight - 0.2) < 1e-6

    def test_create_with_custom_assumptions(self):
        """自定义模拟假设"""
        service = PaperTradingService()
        proposal = _make_proposal()
        assumptions = SimulationAssumptions(
            initial_capital=500_000.0,
            rebalance_frequency_days=10,
        )

        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)

        assert portfolio.assumptions.initial_capital == 500_000.0
        assert portfolio.assumptions.rebalance_frequency_days == 10
        assert portfolio.current_snapshot.total_value == 500_000.0

    def test_create_with_name(self):
        """指定名称"""
        service = PaperTradingService()
        proposal = _make_proposal()

        portfolio = service.create_paper_portfolio(proposal, name="my_paper")

        assert portfolio.name == "my_paper"


# ─── 调仓逻辑测试 ───────────────────────────────────────


class TestRebalance:
    """调仓逻辑测试"""

    def test_rebalance_changes_weights(self):
        """调仓改变持仓权重"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)
        prices = {"A": 1.0, "B": 1.0}

        new_allocations = {"A": 0.6, "B": 0.4}
        portfolio, event = service.rebalance(portfolio, new_allocations, prices)

        positions = {p.subject_id: p for p in portfolio.current_snapshot.positions}
        assert abs(positions["A"].weight - 0.6) < 0.01
        assert abs(positions["B"].weight - 0.4) < 0.01

    def test_rebalance_computes_turnover(self):
        """调仓计算换手率"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)
        prices = {"A": 1.0, "B": 1.0}

        # A: 0.5 → 0.6, B: 0.5 → 0.4
        # half-turnover = (|0.1| + |0.1|) / 2 = 0.1
        portfolio, event = service.rebalance(portfolio, {"A": 0.6, "B": 0.4}, prices)

        assert abs(event.turnover - 0.1) < 1e-6

    def test_rebalance_adds_new_position(self):
        """调仓新增持仓"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        portfolio = service.create_paper_portfolio(proposal)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 0.5, "B": 0.5}, prices)

        positions = {p.subject_id: p for p in portfolio.current_snapshot.positions}
        assert "B" in positions
        assert abs(positions["B"].weight - 0.5) < 0.01

    def test_rebalance_removes_position(self):
        """调仓移除持仓"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 1.0}, prices)

        positions = {p.subject_id: p for p in portfolio.current_snapshot.positions}
        assert "B" not in positions
        assert len(portfolio.current_snapshot.positions) == 1

    def test_rebalance_records_event(self):
        """调仓事件被记录"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        portfolio = service.create_paper_portfolio(proposal)
        prices = {"A": 1.0}

        portfolio, event = service.rebalance(
            portfolio,
            {"A": 0.7, "B": 0.3},
            prices,
            trigger=RebalanceTrigger.SIGNAL_DRIVEN,
        )

        assert len(portfolio.rebalance_events) == 1
        assert portfolio.rebalance_events[0].rebalance_id == event.rebalance_id
        assert event.trigger == RebalanceTrigger.SIGNAL_DRIVEN
        assert len(event.trades) > 0


# ─── 成本建模测试 ───────────────────────────────────────


class TestCostModeling:
    """成本建模测试"""

    def test_commission_applied(self):
        """佣金被应用"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            transaction_cost=TransactionCost(commission_rate=0.001),  # 千一
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        # Trade value: 0.3 * 1_000_000 = 300,000 (buy B), 300,000 (sell A)
        portfolio, event = service.rebalance(portfolio, {"A": 0.7, "B": 0.3}, prices)

        # Commission should be > 0
        assert event.transaction_cost > 0

    def test_slippage_applied(self):
        """滑点成本被应用"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            transaction_cost=TransactionCost(slippage_bps=10.0),
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 0.7, "B": 0.3}, prices)

        assert event.slippage_cost > 0

    def test_stamp_tax_on_sell_only(self):
        """印花税仅对卖出收取"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            transaction_cost=TransactionCost(
                commission_rate=0.0,  # 零佣金便于观察
                commission_min=0.0,
                slippage_bps=0.0,
                stamp_tax_rate=0.001,
                impact_rate=0.0,
            ),
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 0.7, "B": 0.3}, prices)

        # A: sell 0.3 → stamp tax; B: buy 0.3 → no stamp tax
        sell_trades = [t for t in event.trades if t["action"] == "sell"]
        buy_trades = [t for t in event.trades if t["action"] == "buy"]

        assert any(t.get("stamp_tax", 0) > 0 for t in sell_trades)
        assert all(t.get("stamp_tax", 0) == 0 for t in buy_trades)

    def test_total_cost_reduces_nav(self):
        """交易成本减少 NAV"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            transaction_cost=TransactionCost(
                commission_rate=0.001,
                slippage_bps=10.0,
                stamp_tax_rate=0.001,
            ),
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        nav_before = portfolio.current_snapshot.nav
        portfolio, event = service.rebalance(portfolio, {"A": 0.7, "B": 0.3}, prices)
        nav_after = portfolio.current_snapshot.nav

        assert event.total_cost > 0
        assert nav_after < nav_before

    def test_zero_cost_model(self):
        """零成本模型：无佣金、无滑点、无印花税"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            transaction_cost=TransactionCost(
                commission_rate=0.0,
                commission_min=0.0,
                slippage_bps=0.0,
                stamp_tax_rate=0.0,
                impact_rate=0.0,
            ),
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 0.5, "B": 0.5}, prices)

        assert event.total_cost == 0.0
        assert abs(portfolio.current_snapshot.nav - 1.0) < 1e-6


# ─── 每日增量更新测试 ───────────────────────────────────


class TestDailyUpdate:
    """每日增量更新测试"""

    def test_daily_update_with_prices(self):
        """价格更新后市值和 NAV 变化"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)

        # A 涨 10%, B 跌 5%
        prices = {"A": 1.1, "B": 0.95}
        portfolio = service.update_daily(portfolio, prices)

        # Portfolio should have 2 snapshots now (initial + daily)
        assert len(portfolio.snapshots) == 2
        # NAV should be different from 1.0
        assert portfolio.current_snapshot.nav != 1.0

    def test_daily_update_preserves_shares(self):
        """每日更新不改变股数"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        portfolio = service.create_paper_portfolio(proposal)
        initial_shares = portfolio.current_snapshot.positions[0].shares

        prices = {"A": 1.5}
        portfolio = service.update_daily(portfolio, prices)

        assert portfolio.current_snapshot.positions[0].shares == initial_shares

    def test_daily_update_adds_snapshot(self):
        """每日更新增加快照"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        portfolio = service.create_paper_portfolio(proposal)
        assert len(portfolio.snapshots) == 1

        for _ in range(5):
            portfolio = service.update_daily(portfolio, {"A": 1.0})

        assert len(portfolio.snapshots) == 6


# ─── 绩效指标计算测试 ───────────────────────────────────


class TestPerformanceMetrics:
    """绩效指标计算测试"""

    def test_total_return(self):
        """总收益计算"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 1.05, 1.10, 1.15])

        metrics = service.compute_performance(portfolio)

        assert abs(metrics.total_return - 0.15) < 1e-4

    def test_negative_return(self):
        """负收益计算"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 0.95, 0.90, 0.85])

        metrics = service.compute_performance(portfolio)

        assert abs(metrics.total_return - (-0.15)) < 1e-4

    def test_max_drawdown(self):
        """最大回撤计算"""
        service = PaperTradingService()
        # Peak at 1.10, trough at 0.90 → max drawdown = (1.10 - 0.90) / 1.10 = 18.18%
        portfolio = _make_portfolio_with_snapshots([1.0, 1.05, 1.10, 1.00, 0.90, 0.95])

        metrics = service.compute_performance(portfolio)

        expected_dd = (1.10 - 0.90) / 1.10
        assert abs(metrics.max_drawdown - expected_dd) < 1e-4

    def test_max_drawdown_no_drawdown(self):
        """无回撤时最大回撤为 0"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 1.01, 1.02, 1.03])

        metrics = service.compute_performance(portfolio)

        assert abs(metrics.max_drawdown) < 1e-6

    def test_sharpe_ratio(self):
        """夏普比率计算"""
        service = PaperTradingService()
        # Returns with some variance (mostly positive) → positive Sharpe
        import random

        random.seed(42)
        navs = [1.0]
        for _ in range(30):
            daily = random.gauss(0.005, 0.01)  # mean 0.5%, std 1%
            navs.append(navs[-1] * (1.0 + daily))

        portfolio = _make_portfolio_with_snapshots(navs)
        metrics = service.compute_performance(portfolio)

        assert metrics.sharpe_ratio is not None
        assert metrics.sharpe_ratio > 0

    def test_hit_rate(self):
        """胜率计算"""
        service = PaperTradingService()
        # 5 up days, 3 down days → hit_rate = 5/8
        navs = [1.0, 1.01, 1.02, 0.99, 1.00, 1.01, 0.98, 0.99, 1.00]
        portfolio = _make_portfolio_with_snapshots(navs)

        metrics = service.compute_performance(portfolio)

        # Count positive daily returns
        positive_days = sum(1 for i in range(1, len(navs)) if navs[i] > navs[i - 1])
        expected_hit_rate = positive_days / (len(navs) - 1)
        assert abs(metrics.hit_rate - expected_hit_rate) < 1e-4

    def test_turnover_aggregation(self):
        """换手率从调仓事件聚合"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 1.01])

        # 手动添加调仓事件
        portfolio.rebalance_events = [
            RebalanceEvent(
                rebalance_id="rb-1",
                portfolio_id="port-001",
                timestamp=datetime.now(timezone.utc),
                turnover=0.15,
                total_cost=100,
            ),
            RebalanceEvent(
                rebalance_id="rb-2",
                portfolio_id="port-001",
                timestamp=datetime.now(timezone.utc),
                turnover=0.10,
                total_cost=80,
            ),
        ]

        metrics = service.compute_performance(portfolio)

        assert abs(metrics.turnover - 0.25) < 1e-6
        assert abs(metrics.total_transaction_costs - 180) < 1e-6
        assert metrics.num_rebalances == 2

    def test_empty_snapshots(self):
        """无快照时返回默认指标"""
        service = PaperTradingService()
        portfolio = PaperPortfolio(
            portfolio_id="port-001",
            proposal_id="prop-001",
            name="empty",
            created_at=datetime.now(timezone.utc),
        )

        metrics = service.compute_performance(portfolio)

        assert metrics.total_return == 0.0
        assert metrics.max_drawdown == 0.0

    def test_single_snapshot(self):
        """仅一个快照时返回默认指标"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0])

        metrics = service.compute_performance(portfolio)

        assert metrics.total_return == 0.0


# ─── 基准比较测试 ───────────────────────────────────────


class TestBenchmarkComparison:
    """基准比较测试"""

    def test_equal_weight_baseline(self):
        """等权基准计算"""
        service = PaperTradingService()
        price_history = {
            "A": [1.0, 1.05, 1.10, 1.15],
            "B": [1.0, 0.98, 1.02, 1.05],
        }

        total_return, nav_series = service.generate_equal_weight_baseline(["A", "B"], price_history)

        assert len(nav_series) == 4
        assert nav_series[0] == 1.0
        # A: +5%, +4.76%, +4.55% → avg ~4.77%
        # B: -2%, +4.08%, +2.94% → avg ~1.67%
        # avg daily return ~3.22% → total return should be positive
        assert total_return > 0

    def test_equal_weight_baseline_empty(self):
        """空输入返回零收益"""
        service = PaperTradingService()

        total_return, nav_series = service.generate_equal_weight_baseline([], {})

        assert total_return == 0.0
        assert nav_series == [1.0]

    def test_top_k_signal_baseline(self):
        """Top-K 信号基准计算"""
        service = PaperTradingService()
        candidates = [
            {"subject_id": "A", "score": 0.9},
            {"subject_id": "B", "score": 0.7},
            {"subject_id": "C", "score": 0.5},
        ]
        price_history = {
            "A": [1.0, 1.05, 1.10],
            "B": [1.0, 0.98, 1.02],
            "C": [1.0, 1.01, 1.03],
        }

        total_return, nav_series = service.generate_top_k_signal_baseline(
            candidates, price_history, k=2
        )

        # Should pick A and B (top 2 by score)
        assert len(nav_series) == 3
        assert total_return != 0.0

    def test_compare_benchmarks_basic(self):
        """基本基准比较"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 1.05, 1.10, 1.15])

        benchmark_returns = {"equal_weight": 0.10}

        comparisons = service.compare_benchmarks(portfolio, benchmark_returns)

        assert len(comparisons) == 1
        assert comparisons[0].benchmark_name == "equal_weight"
        assert abs(comparisons[0].portfolio_return - 0.15) < 1e-4
        assert abs(comparisons[0].benchmark_return - 0.10) < 1e-4
        assert abs(comparisons[0].excess_return - 0.05) < 1e-4

    def test_compare_benchmarks_multiple(self):
        """多基准比较"""
        service = PaperTradingService()
        portfolio = _make_portfolio_with_snapshots([1.0, 1.05, 1.10])

        benchmark_returns = {
            "equal_weight": 0.08,
            "top_k_signal": 0.12,
        }

        comparisons = service.compare_benchmarks(portfolio, benchmark_returns)

        assert len(comparisons) == 2
        names = {c.benchmark_name for c in comparisons}
        assert names == {"equal_weight", "top_k_signal"}


# ─── 回放驱动模拟测试 ───────────────────────────────────


class TestReplaySimulation:
    """回放驱动模拟测试"""

    def test_replay_simulation_basic(self):
        """基本回放模拟"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        # 价格历史：A 上涨，B 下跌
        price_history = {
            "A": [1.0, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12, 1.14, 1.16, 1.18, 1.20],
            "B": [1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.90],
        }

        dates = [datetime(2024, 1, i, tzinfo=timezone.utc) for i in range(1, 12)]

        result = service.run_replay_simulation(
            proposal=proposal,
            price_history=price_history,
            dates=dates,
        )

        assert result.result_id
        assert result.mode == SimulationMode.REPLAY
        assert result.performance is not None
        assert result.performance.total_return != 0.0
        assert result.performance.num_trading_days > 0

    def test_replay_simulation_with_rebalancing(self):
        """回放模拟执行调仓"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        # 价格历史：长序列，确保触发调仓
        n_days = 30
        price_history = {
            "A": [1.0 + i * 0.01 for i in range(n_days)],
            "B": [1.0 - i * 0.005 for i in range(n_days)],
        }

        dates = [
            datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(n_days)
        ]

        assumptions = SimulationAssumptions(
            initial_capital=1_000_000.0,
            rebalance_frequency_days=5,
            drift_threshold=0.01,  # 低阈值，容易触发
        )

        result = service.run_replay_simulation(
            proposal=proposal,
            price_history=price_history,
            dates=dates,
            assumptions=assumptions,
        )

        assert result.rebalance_count > 0

    def test_replay_simulation_benchmarks(self):
        """回放模拟包含基准比较"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.6, "B": 0.4})

        n_days = 10
        price_history = {
            "A": [1.0 + i * 0.01 for i in range(n_days)],
            "B": [1.0 + i * 0.005 for i in range(n_days)],
        }

        dates = [
            datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(n_days)
        ]

        result = service.run_replay_simulation(
            proposal=proposal,
            price_history=price_history,
            dates=dates,
        )

        # Should have benchmark comparisons
        assert len(result.benchmark_comparisons) > 0
        bench_names = [b.benchmark_name for b in result.benchmark_comparisons]
        assert "equal_weight" in bench_names

    def test_replay_simulation_nav_series(self):
        """回放模拟生成 NAV 序列"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        price_history = {"A": [1.0, 1.01, 1.02, 1.03, 1.04]}
        dates = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i) for i in range(5)]

        result = service.run_replay_simulation(
            proposal=proposal,
            price_history=price_history,
            dates=dates,
        )

        assert len(result.nav_series) > 0
        # NAV should be increasing
        assert result.nav_series[-1]["nav"] > result.nav_series[0]["nav"]


# ─── 偏离阈值测试 ───────────────────────────────────────


class TestDriftThreshold:
    """偏离阈值测试"""

    def test_no_drift_no_rebalance(self):
        """无偏离时不触发调仓"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)

        # 价格不变 → 无偏离
        prices = {"A": 1.0, "B": 1.0}
        portfolio = service.update_daily(portfolio, prices)

        needs_rebalance = service._check_drift_threshold(
            portfolio, {"A": 0.5, "B": 0.5}, threshold=0.05
        )

        assert needs_rebalance is False

    def test_drift_exceeds_threshold(self):
        """偏离超过阈值时触发调仓"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 0.5, "B": 0.5})

        portfolio = service.create_paper_portfolio(proposal)

        # A 大涨 → 权重偏离
        prices = {"A": 1.5, "B": 0.5}
        portfolio = service.update_daily(portfolio, prices)

        needs_rebalance = service._check_drift_threshold(
            portfolio, {"A": 0.5, "B": 0.5}, threshold=0.05
        )

        assert needs_rebalance is True


# ─── 交易成本模型测试 ───────────────────────────────────


class TestTransactionCostModel:
    """交易成本模型测试"""

    def test_default_cost_model(self):
        """默认成本模型"""
        cost = TransactionCost()

        assert cost.commission_rate == 0.0003
        assert cost.commission_min == 5.0
        assert cost.slippage_bps == 5.0
        assert cost.stamp_tax_rate == 0.001
        assert cost.impact_rate == 0.0001

    def test_custom_cost_model(self):
        """自定义成本模型"""
        cost = TransactionCost(
            commission_rate=0.0005,
            commission_min=3.0,
            slippage_bps=10.0,
            stamp_tax_rate=0.002,
        )

        assert cost.commission_rate == 0.0005
        assert cost.commission_min == 3.0
        assert cost.slippage_bps == 10.0
        assert cost.stamp_tax_rate == 0.002

    def test_commission_min_applied(self):
        """最低佣金生效"""
        service = PaperTradingService()
        proposal = _make_proposal({"A": 1.0})

        # Very small capital → commission below min
        assumptions = SimulationAssumptions(
            initial_capital=1000.0,  # Very small
            transaction_cost=TransactionCost(
                commission_rate=0.0003,
                commission_min=5.0,
                slippage_bps=0.0,
                stamp_tax_rate=0.0,
                impact_rate=0.0,
            ),
        )
        portfolio = service.create_paper_portfolio(proposal, assumptions=assumptions)
        prices = {"A": 1.0, "B": 1.0}

        portfolio, event = service.rebalance(portfolio, {"A": 0.9, "B": 0.1}, prices)

        # Commission should be at least commission_min for each trade
        for trade in event.trades:
            assert trade["commission"] >= 5.0


# ─── 模拟假设可复现测试 ────────────────────────────────


class TestAssumptionsReproducibility:
    """模拟假设可复现测试"""

    def test_assumptions_serializable(self):
        """模拟假设可序列化"""
        assumptions = SimulationAssumptions(
            initial_capital=2_000_000.0,
            transaction_cost=TransactionCost(commission_rate=0.0005),
            rebalance_frequency_days=10,
            drift_threshold=0.03,
        )

        data = assumptions.model_dump(mode="json")
        restored = SimulationAssumptions(**data)

        assert restored.initial_capital == 2_000_000.0
        assert restored.transaction_cost.commission_rate == 0.0005
        assert restored.rebalance_frequency_days == 10
        assert restored.drift_threshold == 0.03

    def test_simulation_mode_values(self):
        """模拟模式枚举"""
        assert SimulationMode.REPLAY.value == "replay"
        assert SimulationMode.INCREMENTAL.value == "incremental"

    def test_rebalance_trigger_values(self):
        """调仓触发类型枚举"""
        assert RebalanceTrigger.SCHEDULED.value == "scheduled"
        assert RebalanceTrigger.SIGNAL_DRIVEN.value == "signal_driven"
        assert RebalanceTrigger.THRESHOLD.value == "threshold"
        assert RebalanceTrigger.MANUAL.value == "manual"
