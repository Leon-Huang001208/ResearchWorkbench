"""Paper Trading API — 模拟交易与组合仿真路由"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.paper_trading import (
    PaperPortfolio,
    RebalanceTrigger,
    SimulationAssumptions,
    SimulationMode,
    SimulationResult,
)
from core.observability import get_logger
from core.services.paper_trading_service import PaperTradingService
from data_layer.repositories.base import get_db
from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl
from data_layer.repositories.paper_trading_repository import PaperTradingRepositoryImpl
from data_layer.repositories.portfolio_repository import PortfolioRepositoryImpl

logger = get_logger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])

# 模块级单例
_paper_trading_service: PaperTradingService | None = None


# ── 请求模型 ───────────────────────────────────────────


class CreatePaperPortfolioRequest(BaseModel):
    """创建模拟组合请求"""

    proposal_id: str = Field(..., description="关联的组合提案ID")
    name: Optional[str] = Field(None, description="组合名称")
    initial_capital: float = Field(1_000_000.0, ge=1000, description="初始资金")
    commission_rate: float = Field(0.0003, ge=0, le=0.01, description="佣金率")
    slippage_bps: float = Field(5.0, ge=0, le=100, description="滑点(基点)")
    rebalance_frequency_days: int = Field(5, ge=1, le=60, description="调仓频率(天)")
    drift_threshold: float = Field(0.05, ge=0.01, le=0.5, description="偏离阈值")


class RebalanceRequest(BaseModel):
    """调仓请求"""

    target_allocations: Dict[str, float] = Field(..., description="目标权重 {subject_id: weight}")
    prices: Dict[str, float] = Field(..., description="当前价格 {subject_id: price}")
    trigger: RebalanceTrigger = Field(RebalanceTrigger.SCHEDULED, description="触发类型")


class RunSimulationRequest(BaseModel):
    """运行模拟请求"""

    proposal_id: str = Field(..., description="组合提案ID")
    name: Optional[str] = Field(None, description="模拟名称")
    price_history: Dict[str, List[float]] = Field(..., description="价格历史 {subject_id: [prices]}")
    dates: List[str] = Field(..., description="日期序列 ISO格式")
    initial_capital: float = Field(1_000_000.0, ge=1000, description="初始资金")
    commission_rate: float = Field(0.0003, ge=0, le=0.01, description="佣金率")
    slippage_bps: float = Field(5.0, ge=0, le=100, description="滑点(基点)")
    rebalance_frequency_days: int = Field(5, ge=1, le=60, description="调仓频率(天)")
    drift_threshold: float = Field(0.05, ge=0.01, le=0.5, description="偏离阈值")


class UpdateDailyRequest(BaseModel):
    """每日更新请求"""

    prices: Dict[str, float] = Field(..., description="最新价格 {subject_id: price}")


# ── 响应模型 ───────────────────────────────────────────


class PositionSnapshotResponse(BaseModel):
    """持仓快照响应"""

    subject_id: str
    weight: float
    shares: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    cost_basis: float


class PortfolioSnapshotResponse(BaseModel):
    """组合快照响应"""

    timestamp: str
    nav: float
    total_value: float
    cash: float
    positions: List[PositionSnapshotResponse]
    gross_exposure: float
    net_exposure: float


class PaperPortfolioResponse(BaseModel):
    """模拟组合响应"""

    portfolio_id: str
    proposal_id: str
    name: str
    created_at: str
    status: str
    current_snapshot: Optional[PortfolioSnapshotResponse] = None
    num_snapshots: int = 0
    num_rebalances: int = 0


class PerformanceMetricsResponse(BaseModel):
    """绩效指标响应"""

    start_date: str
    end_date: str
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    hit_rate: float
    avg_win: float
    avg_loss: float
    win_loss_ratio: Optional[float] = None
    turnover: float
    avg_exposure: float
    total_transaction_costs: float
    num_rebalances: int
    num_trading_days: int


class BenchmarkComparisonResponse(BaseModel):
    """基准比较响应"""

    benchmark_name: str
    benchmark_return: float
    portfolio_return: float
    excess_return: float
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    beta: Optional[float] = None
    alpha: Optional[float] = None


class SimulationResultResponse(BaseModel):
    """模拟结果响应"""

    result_id: str
    portfolio_id: str
    name: str
    created_at: str
    mode: str
    performance: PerformanceMetricsResponse
    benchmark_comparisons: List[BenchmarkComparisonResponse]
    nav_series: List[Dict[str, Any]]
    rebalance_count: int
    total_turnover: float


class RebalanceEventResponse(BaseModel):
    """调仓事件响应"""

    rebalance_id: str
    timestamp: str
    trigger: str
    turnover: float
    transaction_cost: float
    slippage_cost: float
    total_cost: float
    num_trades: int


# ── 依赖注入 ───────────────────────────────────────────


def get_paper_trading_service(db: Session = Depends(get_db)) -> PaperTradingService:
    """获取模拟交易服务实例（单例 + 请求级 DB session）"""
    global _paper_trading_service
    if _paper_trading_service is None:
        paper_trading_repo = PaperTradingRepositoryImpl(db)
        portfolio_repo = PortfolioRepositoryImpl(db)
        outcome_repo = OutcomeRepositoryImpl(db)
        _paper_trading_service = PaperTradingService(
            portfolio_repository=portfolio_repo,
            paper_trading_repository=paper_trading_repo,
            outcome_repository=outcome_repo,
        )
    else:
        if _paper_trading_service._paper_trading_repo:
            _paper_trading_service._paper_trading_repo.db = db
        if _paper_trading_service._portfolio_repo:
            _paper_trading_service._portfolio_repo.db = db
        if _paper_trading_service._outcome_repo:
            _paper_trading_service._outcome_repo.db = db
    return _paper_trading_service


def _reset_paper_trading_service():
    """重置模块级单例（仅用于测试）"""
    global _paper_trading_service
    _paper_trading_service = None


# ── 辅助转换 ───────────────────────────────────────────


def _portfolio_to_response(portfolio: PaperPortfolio) -> PaperPortfolioResponse:
    """PaperPortfolio → 响应"""
    snapshot_resp = None
    if portfolio.current_snapshot:
        snapshot_resp = PortfolioSnapshotResponse(
            timestamp=portfolio.current_snapshot.timestamp.isoformat(),
            nav=portfolio.current_snapshot.nav,
            total_value=portfolio.current_snapshot.total_value,
            cash=portfolio.current_snapshot.cash,
            positions=[
                PositionSnapshotResponse(
                    subject_id=p.subject_id,
                    weight=p.weight,
                    shares=p.shares,
                    entry_price=p.entry_price,
                    current_price=p.current_price,
                    market_value=p.market_value,
                    unrealized_pnl=p.unrealized_pnl,
                    unrealized_pnl_pct=p.unrealized_pnl_pct,
                    cost_basis=p.cost_basis,
                )
                for p in portfolio.current_snapshot.positions
            ],
            gross_exposure=portfolio.current_snapshot.gross_exposure,
            net_exposure=portfolio.current_snapshot.net_exposure,
        )

    return PaperPortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        proposal_id=portfolio.proposal_id,
        name=portfolio.name,
        created_at=portfolio.created_at.isoformat(),
        status=portfolio.status,
        current_snapshot=snapshot_resp,
        num_snapshots=len(portfolio.snapshots),
        num_rebalances=len(portfolio.rebalance_events),
    )


def _result_to_response(result: SimulationResult) -> SimulationResultResponse:
    """SimulationResult → 响应"""
    perf = result.performance
    return SimulationResultResponse(
        result_id=result.result_id,
        portfolio_id=result.portfolio_id,
        name=result.name,
        created_at=result.created_at.isoformat(),
        mode=result.mode.value,
        performance=PerformanceMetricsResponse(
            start_date=perf.start_date.isoformat(),
            end_date=perf.end_date.isoformat(),
            total_return=perf.total_return,
            annualized_return=perf.annualized_return,
            max_drawdown=perf.max_drawdown,
            sharpe_ratio=perf.sharpe_ratio,
            sortino_ratio=perf.sortino_ratio,
            hit_rate=perf.hit_rate,
            avg_win=perf.avg_win,
            avg_loss=perf.avg_loss,
            win_loss_ratio=perf.win_loss_ratio,
            turnover=perf.turnover,
            avg_exposure=perf.avg_exposure,
            total_transaction_costs=perf.total_transaction_costs,
            num_rebalances=perf.num_rebalances,
            num_trading_days=perf.num_trading_days,
        ),
        benchmark_comparisons=[
            BenchmarkComparisonResponse(
                benchmark_name=b.benchmark_name,
                benchmark_return=b.benchmark_return,
                portfolio_return=b.portfolio_return,
                excess_return=b.excess_return,
                tracking_error=b.tracking_error,
                information_ratio=b.information_ratio,
                beta=b.beta,
                alpha=b.alpha,
            )
            for b in result.benchmark_comparisons
        ],
        nav_series=result.nav_series,
        rebalance_count=result.rebalance_count,
        total_turnover=result.total_turnover,
    )


# ── 路由 ───────────────────────────────────────────────


@router.post(
    "/portfolios",
    response_model=PaperPortfolioResponse,
)
async def create_paper_portfolio(
    request: CreatePaperPortfolioRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
    db: Session = Depends(get_db),
):
    """从组合提案创建模拟组合"""
    try:
        # 获取提案
        proposal = (
            service._portfolio_repo.get_proposal(request.proposal_id)
            if service._portfolio_repo
            else None
        )
        if proposal is None:
            raise HTTPException(
                status_code=404,
                detail=f"Proposal {request.proposal_id} not found",
            )

        assumptions = SimulationAssumptions(
            initial_capital=request.initial_capital,
            transaction_cost__commission_rate=request.commission_rate,
            transaction_cost__slippage_bps=request.slippage_bps,
            rebalance_frequency_days=request.rebalance_frequency_days,
            drift_threshold=request.drift_threshold,
        )

        portfolio = service.create_paper_portfolio(
            proposal=proposal,
            name=request.name,
            assumptions=assumptions,
        )

        return _portfolio_to_response(portfolio)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create paper portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/portfolios",
    response_model=List[PaperPortfolioResponse],
)
async def list_paper_portfolios(
    limit: int = Query(100, ge=1, le=1000),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """列出模拟组合"""
    try:
        portfolios = service.list_paper_portfolios(limit=limit)
        return [_portfolio_to_response(p) for p in portfolios]
    except Exception as e:
        logger.error(f"List paper portfolios failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/portfolios/{portfolio_id}",
    response_model=PaperPortfolioResponse,
)
async def get_paper_portfolio(
    portfolio_id: str,
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """获取模拟组合详情"""
    try:
        portfolio = service.get_paper_portfolio(portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail=f"Paper portfolio {portfolio_id} not found")
        return _portfolio_to_response(portfolio)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get paper portfolio failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/portfolios/{portfolio_id}/rebalance",
    response_model=RebalanceEventResponse,
)
async def rebalance_portfolio(
    portfolio_id: str,
    request: RebalanceRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """执行调仓"""
    try:
        portfolio = service.get_paper_portfolio(portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail=f"Paper portfolio {portfolio_id} not found")

        # 归一化目标权重
        total_weight = sum(request.target_allocations.values())
        if total_weight <= 0:
            raise HTTPException(
                status_code=400, detail="Target allocations must sum to a positive value"
            )
        normalized = {k: v / total_weight for k, v in request.target_allocations.items()}

        portfolio, event = service.rebalance(
            portfolio=portfolio,
            target_allocations=normalized,
            prices=request.prices,
            trigger=request.trigger,
        )

        return RebalanceEventResponse(
            rebalance_id=event.rebalance_id,
            timestamp=event.timestamp.isoformat(),
            trigger=event.trigger.value,
            turnover=event.turnover,
            transaction_cost=event.transaction_cost,
            slippage_cost=event.slippage_cost,
            total_cost=event.total_cost,
            num_trades=len(event.trades),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rebalance failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/portfolios/{portfolio_id}/update",
    response_model=PaperPortfolioResponse,
)
async def update_daily(
    portfolio_id: str,
    request: UpdateDailyRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """每日增量更新"""
    try:
        portfolio = service.get_paper_portfolio(portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail=f"Paper portfolio {portfolio_id} not found")

        portfolio = service.update_daily(portfolio, request.prices)
        return _portfolio_to_response(portfolio)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Daily update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/portfolios/{portfolio_id}/performance",
    response_model=PerformanceMetricsResponse,
)
async def get_performance(
    portfolio_id: str,
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """获取绩效指标"""
    try:
        portfolio = service.get_paper_portfolio(portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail=f"Paper portfolio {portfolio_id} not found")

        metrics = service.compute_performance(portfolio)
        return PerformanceMetricsResponse(
            start_date=metrics.start_date.isoformat(),
            end_date=metrics.end_date.isoformat(),
            total_return=metrics.total_return,
            annualized_return=metrics.annualized_return,
            max_drawdown=metrics.max_drawdown,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            hit_rate=metrics.hit_rate,
            avg_win=metrics.avg_win,
            avg_loss=metrics.avg_loss,
            win_loss_ratio=metrics.win_loss_ratio,
            turnover=metrics.turnover,
            avg_exposure=metrics.avg_exposure,
            total_transaction_costs=metrics.total_transaction_costs,
            num_rebalances=metrics.num_rebalances,
            num_trading_days=metrics.num_trading_days,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get performance failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/simulate",
    response_model=SimulationResultResponse,
)
async def run_simulation(
    request: RunSimulationRequest,
    service: PaperTradingService = Depends(get_paper_trading_service),
    db: Session = Depends(get_db),
):
    """运行回放驱动模拟"""
    try:
        # 获取提案
        proposal = (
            service._portfolio_repo.get_proposal(request.proposal_id)
            if service._portfolio_repo
            else None
        )
        if proposal is None:
            raise HTTPException(
                status_code=404,
                detail=f"Proposal {request.proposal_id} not found",
            )

        # 解析日期
        from datetime import datetime as dt

        dates = [dt.fromisoformat(d) for d in request.dates]

        assumptions = SimulationAssumptions(
            initial_capital=request.initial_capital,
            transaction_cost__commission_rate=request.commission_rate,
            transaction_cost__slippage_bps=request.slippage_bps,
            rebalance_frequency_days=request.rebalance_frequency_days,
            drift_threshold=request.drift_threshold,
            mode=SimulationMode.REPLAY,
        )

        result = service.run_replay_simulation(
            proposal=proposal,
            price_history=request.price_history,
            dates=dates,
            assumptions=assumptions,
            name=request.name,
        )

        return _result_to_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Run simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/results",
    response_model=List[SimulationResultResponse],
)
async def list_simulation_results(
    portfolio_id: Optional[str] = Query(None, description="按组合ID过滤"),
    limit: int = Query(100, ge=1, le=1000),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """列出模拟结果"""
    try:
        results = service.list_simulation_results(portfolio_id=portfolio_id, limit=limit)
        return [_result_to_response(r) for r in results]
    except Exception as e:
        logger.error(f"List simulation results failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/results/{result_id}",
    response_model=SimulationResultResponse,
)
async def get_simulation_result(
    result_id: str,
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    """获取模拟结果详情"""
    try:
        result = service.get_simulation_result(result_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Simulation result {result_id} not found")
        return _result_to_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get simulation result failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
