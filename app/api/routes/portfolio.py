"""Portfolio API — 组合构建与风险预算路由"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.portfolio import PortfolioConstraints, PortfolioProposal
from core.observability import get_logger
from core.services.portfolio_service import PortfolioService
from data_layer.repositories.base import get_db
from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl
from data_layer.repositories.portfolio_repository import PortfolioRepositoryImpl
from data_layer.repositories.signal_repository import SignalRepositoryImpl

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# 模块级单例
_portfolio_service: PortfolioService | None = None


class BuildRequest(BaseModel):
    """组合构建请求"""
    name: Optional[str] = Field(None, description="提案名称")
    constraints: Optional[Dict[str, Any]] = Field(None, description="自定义约束")
    signal_ids: Optional[List[str]] = Field(None, description="指定信号ID列表（为空则取所有活跃信号）")


class BuildWithConstraintsRequest(BaseModel):
    """自定义约束构建请求"""
    name: Optional[str] = Field(None, description="提案名称")
    max_position_size: float = Field(0.15, ge=0.01, le=1.0, description="单个持仓最大权重")
    max_sector_concentration: float = Field(0.40, ge=0.01, le=1.0, description="行业集中度上限")
    max_theme_concentration: float = Field(0.30, ge=0.01, le=1.0, description="主题集中度上限")
    min_candidates: int = Field(3, ge=1, le=50, description="最少候选数")
    max_candidates: int = Field(20, ge=1, le=100, description="最多候选数")
    min_signal_score: float = Field(0.3, ge=0.0, le=1.0, description="最低信号分数")
    min_confidence: float = Field(0.3, ge=0.0, le=1.0, description="最低置信度")
    signal_ids: Optional[List[str]] = Field(None, description="指定信号ID列表")


class CandidateResponse(BaseModel):
    """候选响应"""
    signal_id: str
    subject_id: str
    event_type: str
    signal_score: float
    signal_confidence: float
    readiness: Optional[str] = None
    timing_action: Optional[str] = None
    suggested_weight: float
    historical_hit_rate: Optional[float] = None
    historical_avg_excess_return: Optional[float] = None
    sector: Optional[str] = None
    theme: Optional[str] = None


class ProposalResponse(BaseModel):
    """提案响应"""
    proposal_id: str
    name: str
    created_at: str
    candidates: List[CandidateResponse]
    allocations: Dict[str, float]
    constraints_applied: List[str]
    excluded_signals: List[Dict[str, Any]]
    rationale: Dict[str, Any]


class ProposalSummaryResponse(BaseModel):
    """提案摘要响应"""
    proposal_id: str
    name: str
    created_at: str
    candidate_count: int
    allocation_count: int
    excluded_count: int


def get_portfolio_service(db: Session = Depends(get_db)) -> PortfolioService:
    """获取组合服务实例（单例 + 请求级 DB session）"""
    global _portfolio_service
    if _portfolio_service is None:
        outcome_repo = OutcomeRepositoryImpl(db)
        portfolio_repo = PortfolioRepositoryImpl(db)
        _portfolio_service = PortfolioService(
            outcome_repository=outcome_repo,
            portfolio_repository=portfolio_repo,
        )
    else:
        if _portfolio_service._outcome_repo:
            _portfolio_service._outcome_repo.db = db
        if _portfolio_service._portfolio_repo:
            _portfolio_service._portfolio_repo.db = db
    return _portfolio_service


def _reset_portfolio_service():
    """重置模块级单例（仅用于测试）"""
    global _portfolio_service
    _portfolio_service = None


def _get_active_signals(
    db: Session, signal_ids: Optional[List[str]] = None
) -> List[Any]:
    """获取活跃信号列表"""
    signal_repo = SignalRepositoryImpl(db)
    if signal_ids:
        signals = []
        for sid in signal_ids:
            signal = signal_repo.get(sid)
            if signal:
                signals.append(signal)
        return signals
    else:
        # 获取所有 candidate 和 paper_trade 状态的信号
        candidates = signal_repo.list(status="candidate", limit=200)
        paper_trades = signal_repo.list(status="paper_trade", limit=200)
        return candidates + paper_trades


def _proposal_to_response(proposal: PortfolioProposal) -> ProposalResponse:
    """将 PortfolioProposal 转为 API 响应"""
    return ProposalResponse(
        proposal_id=proposal.proposal_id,
        name=proposal.name,
        created_at=proposal.created_at.isoformat(),
        candidates=[
            CandidateResponse(
                signal_id=c.signal_id,
                subject_id=c.subject_id,
                event_type=c.event_type,
                signal_score=c.signal_score,
                signal_confidence=c.signal_confidence,
                readiness=c.readiness,
                timing_action=c.timing_action,
                suggested_weight=c.suggested_weight,
                historical_hit_rate=c.historical_hit_rate,
                historical_avg_excess_return=c.historical_avg_excess_return,
                sector=c.sector,
                theme=c.theme,
            )
            for c in proposal.candidates
        ],
        allocations=proposal.allocations,
        constraints_applied=proposal.constraints_applied,
        excluded_signals=proposal.excluded_signals,
        rationale=proposal.rationale,
    )


@router.post(
    "/build",
    response_model=ProposalResponse,
)
async def build_portfolio(
    request: BuildRequest,
    service: PortfolioService = Depends(get_portfolio_service),
    db: Session = Depends(get_db),
):
    """从当前活跃信号构建组合提案"""
    try:
        active_signals = _get_active_signals(db, request.signal_ids)

        if not active_signals:
            raise HTTPException(
                status_code=400,
                detail="No active signals found to build portfolio",
            )

        constraints = None
        if request.constraints:
            constraints = PortfolioConstraints(**request.constraints)

        proposal = service.build_proposal(
            active_signals=active_signals,
            constraints=constraints,
            name=request.name,
        )

        return _proposal_to_response(proposal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio build failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/build-with-constraints",
    response_model=ProposalResponse,
)
async def build_portfolio_with_constraints(
    request: BuildWithConstraintsRequest,
    service: PortfolioService = Depends(get_portfolio_service),
    db: Session = Depends(get_db),
):
    """自定义约束构建组合提案"""
    try:
        active_signals = _get_active_signals(db, request.signal_ids)

        if not active_signals:
            raise HTTPException(
                status_code=400,
                detail="No active signals found to build portfolio",
            )

        constraints = PortfolioConstraints(
            max_position_size=request.max_position_size,
            max_sector_concentration=request.max_sector_concentration,
            max_theme_concentration=request.max_theme_concentration,
            min_candidates=request.min_candidates,
            max_candidates=request.max_candidates,
            min_signal_score=request.min_signal_score,
            min_confidence=request.min_confidence,
        )

        proposal = service.build_proposal(
            active_signals=active_signals,
            constraints=constraints,
            name=request.name,
        )

        return _proposal_to_response(proposal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio build with constraints failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/proposals",
    response_model=List[ProposalSummaryResponse],
)
async def list_proposals(
    limit: int = Query(100, ge=1, le=1000),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """列出历史提案"""
    try:
        proposals = service.list_proposals(limit=limit)
        return [
            ProposalSummaryResponse(
                proposal_id=p.proposal_id,
                name=p.name,
                created_at=p.created_at.isoformat(),
                candidate_count=len(p.candidates),
                allocation_count=len(p.allocations),
                excluded_count=len(p.excluded_signals),
            )
            for p in proposals
        ]
    except Exception as e:
        logger.error(f"List proposals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/proposals/{proposal_id}",
    response_model=ProposalResponse,
)
async def get_proposal(
    proposal_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
):
    """获取提案详情（含排除理由）"""
    try:
        proposal = service.get_proposal(proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
        return _proposal_to_response(proposal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get proposal failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
