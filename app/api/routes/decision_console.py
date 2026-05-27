"""Decision Console API — 分析师循环决策控制台路由"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.decision_console import (
    AnalystDecision,
    DecisionAction,
    DecisionAudit,
    DecisionWorkspace,
    PostMortemRecord,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.decision_console_repository import DecisionConsoleRepository
from services.decision_console_service import DecisionConsoleService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/decision-console", tags=["decision-console"])

# 模块级单例
_decision_console_service: DecisionConsoleService | None = None


# Request/impl get it


class CreateWorkspaceRequest(BaseModel):
    """创建工作区请求"""

    created_by: str = Field(..., description="创建人ID/名称")
    workspace_date: Optional[str] = Field(None, description="工作区日期（ISO格式，默认今天）")
    team_id: Optional[str] = Field(None, description="团队ID")
    candidate_ids: Optional[List[str]] = Field(None, description="初始候选列表")


class CloseWorkspaceRequest(BaseModel):
    """关闭工作区请求"""

    notes: Optional[str] = Field(None, description="关闭备注")


class AddCandidatesRequest(BaseModel):
    """添加候选请求"""

    candidate_ids: List[str] = Field(..., description="候选ID列表")


class RecordDecisionRequest(BaseModel):
    """记录决策请求"""

    workspace_id: str = Field(..., description="工作区ID")
    candidate_id: str = Field(..., description="候选ID")
    candidate_type: str = Field(..., description="候选类型: signal/portfolio_candidate/proposal")
    previous_status: str = Field(..., description="之前状态")
    action_type: str = Field(
        ..., description="决策动作类型: approve/watch/reject/defer/revise_thesis/add_to_paper_portfolio"
    )
    action_by: str = Field(..., description="决策人ID/名称")
    rationale: str = Field(..., description="决策理由")
    changes: Optional[Dict[str, str]] = Field(None, description="修改内容")


class CreatePostMortemRequest(BaseModel):
    """创建复盘请求"""

    decision_id: str = Field(..., description="关联决策ID")
    original_decision: str = Field(..., description="原始决策内容")
    realized_outcome: str = Field(..., description="实际结果: win/loss/draw/pending")
    learning_points: str = Field(..., description="学习要点")
    outcome_metrics: Optional[Dict[str, float]] = Field(None, description="结果指标")
    linked_signal_accuracy: Optional[float] = Field(None, description="关联信号准确率")


class UpdatePostMortemRequest(BaseModel):
    """更新复盘请求"""

    realized_outcome: Optional[str] = Field(None, description="实际结果")
    learning_points: Optional[str] = Field(None, description="学习要点")
    outcome_metrics: Optional[Dict[str, float]] = Field(None, description="结果指标")
    linked_signal_accuracy: Optional[float] = Field(None, description="关联信号准确率")


class WorkspaceResponse(BaseModel):
    """工作区响应"""

    workspace_id: str
    workspace_date: str
    status: str
    candidate_ids: List[str]
    team_id: Optional[str]
    created_at: str
    created_by: str
    closed_at: Optional[str]
    notes: Optional[str]


class DecisionActionResponse(BaseModel):
    """决策动作响应"""

    action_type: str
    action_by: str
    action_at: str
    rationale: str
    changes: Optional[Dict[str, str]]


class DecisionResponse(BaseModel):
    """决策响应"""

    decision_id: str
    workspace_id: str
    candidate_id: str
    candidate_type: str
    previous_status: str
    final_action: DecisionActionResponse
    revision_history: List[DecisionActionResponse]
    is_closed: bool


class AuditResponse(BaseModel):
    """审计响应"""

    audit_id: str
    decision_id: str
    action: str
    actor: str
    timestamp: str
    before_state: Dict[str, Any]
    after_state: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]


class PostMortemResponse(BaseModel):
    """复盘响应"""

    post_mortem_id: str
    decision_id: str
    original_decision: str
    realized_outcome: str
    outcome_metrics: Dict[str, float]
    learning_points: str
    created_at: str
    updated_at: str
    linked_signal_accuracy: Optional[float]


def get_decision_console_service(db: Session = Depends(get_db)) -> DecisionConsoleService:
    """获取决策控制台服务实例（单例 + 请求级 DB session）"""
    global _decision_console_service
    if _decision_console_service is None:
        repo = DecisionConsoleRepository(db)
        _decision_console_service = DecisionConsoleService(repository=repo)
    else:
        _decision_console_service.repo.db = db
    return _decision_console_service


def _reset_service():
    """重置模块级单例（仅用于测试）"""
    global _decision_console_service
    _decision_console_service = None


def _workspace_to_response(workspace: DecisionWorkspace) -> WorkspaceResponse:
    """转换工作区到响应"""
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        workspace_date=workspace.workspace_date.isoformat(),
        status=workspace.status,
        candidate_ids=workspace.candidate_ids,
        team_id=workspace.team_id,
        created_at=workspace.created_at.isoformat(),
        created_by=workspace.created_by,
        closed_at=workspace.closed_at.isoformat() if workspace.closed_at else None,
        notes=workspace.notes,
    )


def _action_to_response(action: DecisionAction) -> DecisionActionResponse:
    """转换动作到响应"""
    return DecisionActionResponse(
        action_type=action.action_type,
        action_by=action.action_by,
        action_at=action.action_at.isoformat(),
        rationale=action.rationale,
        changes=action.changes,
    )


def _decision_to_response(decision: AnalystDecision) -> DecisionResponse:
    """转换决策到响应"""
    return DecisionResponse(
        decision_id=decision.decision_id,
        workspace_id=decision.workspace_id,
        candidate_id=decision.candidate_id,
        candidate_type=decision.candidate_type,
        previous_status=decision.previous_status,
        final_action=_action_to_response(decision.final_action),
        revision_history=[_action_to_response(a) for a in decision.revision_history],
        is_closed=decision.is_closed,
    )


def _audit_to_response(audit: DecisionAudit) -> AuditResponse:
    """转换审计到响应"""
    return AuditResponse(
        audit_id=audit.audit_id,
        decision_id=audit.decision_id,
        action=audit.action,
        actor=audit.actor,
        timestamp=audit.timestamp.isoformat(),
        before_state=audit.before_state,
        after_state=audit.after_state,
        ip_address=audit.ip_address,
        user_agent=audit.user_agent,
    )


def _post_mortem_to_response(post_mortem: PostMortemRecord) -> PostMortemResponse:
    """转换复盘到响应"""
    return PostMortemResponse(
        post_mortem_id=post_mortem.post_mortem_id,
        decision_id=post_mortem.decision_id,
        original_decision=post_mortem.original_decision,
        realized_outcome=post_mortem.realized_outcome,
        outcome_metrics=post_mortem.outcome_metrics,
        learning_points=post_mortem.learning_points,
        created_at=post_mortem.created_at.isoformat(),
        updated_at=post_mortem.updated_at.isoformat(),
        linked_signal_accuracy=post_mortem.linked_signal_accuracy,
    )


@router.post(
    "/workspace",
    response_model=WorkspaceResponse,
)
async def create_workspace(
    request: CreateWorkspaceRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """创建新的决策工作区"""
    try:
        workspace_date = None
        if request.workspace_date:
            from datetime import datetime

            workspace_date = datetime.fromisoformat(request.workspace_date)

        workspace = service.create_workspace(
            created_by=request.created_by,
            workspace_date=workspace_date,
            team_id=request.team_id,
            candidate_ids=request.candidate_ids,
        )
        return _workspace_to_response(workspace)
    except Exception as e:
        logger.error(f"Create workspace failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/workspace/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: str,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """获取工作区详情"""
    try:
        workspace = service.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
        return _workspace_to_response(workspace)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get workspace failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/workspaces/open",
    response_model=List[WorkspaceResponse],
)
async def list_open_workspaces(
    limit: int = Query(20, ge=1, le=100),
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """列出所有打开的工作区"""
    try:
        workspaces = service.list_open_workspaces(limit=limit)
        return [_workspace_to_response(w) for w in workspaces]
    except Exception as e:
        logger.error(f"List open workspaces failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/workspace/{workspace_id}/close",
    response_model=WorkspaceResponse,
)
async def close_workspace(
    workspace_id: str,
    request: CloseWorkspaceRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """关闭工作区"""
    try:
        workspace = service.close_workspace(workspace_id=workspace_id, notes=request.notes)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
        return _workspace_to_response(workspace)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close workspace failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/workspace/{workspace_id}/candidates",
    response_model=WorkspaceResponse,
)
async def add_candidates(
    workspace_id: str,
    request: AddCandidatesRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """添加候选到工作区"""
    try:
        workspace = service.add_candidates_to_workspace(
            workspace_id=workspace_id, candidate_ids=request.candidate_ids
        )
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
        return _workspace_to_response(workspace)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add candidates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/decision",
    response_model=DecisionResponse,
)
async def record_decision(
    request: RecordDecisionRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """记录分析师决策"""
    try:
        action = DecisionAction(
            action_type=request.action_type,
            action_by=request.action_by,
            rationale=request.rationale,
            changes=request.changes,
        )

        decision, audit = service.record_decision(
            workspace_id=request.workspace_id,
            candidate_id=request.candidate_id,
            candidate_type=request.candidate_type,
            previous_status=request.previous_status,
            action=action,
        )
        return _decision_to_response(decision)
    except Exception as e:
        logger.error(f"Record decision failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/decision/{decision_id}",
    response_model=DecisionResponse,
)
async def get_decision(
    decision_id: str,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """获取决策详情"""
    try:
        decision = service.get_decision(decision_id)
        if not decision:
            raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
        return _decision_to_response(decision)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get decision failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/workspace/{workspace_id}/decisions",
    response_model=List[DecisionResponse],
)
async def get_workspace_decisions(
    workspace_id: str,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """获取工作区所有决策"""
    try:
        decisions = service.get_workspace_decisions(workspace_id)
        return [_decision_to_response(d) for d in decisions]
    except Exception as e:
        logger.error(f"Get workspace decisions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/decision/{decision_id}/audit",
    response_model=List[AuditResponse],
)
async def get_decision_audit(
    decision_id: str,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """获取决策审计历史"""
    try:
        audits = service.get_audit_history(decision_id)
        return [_audit_to_response(a) for a in audits]
    except Exception as e:
        logger.error(f"Get decision audit failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/post-mortem",
    response_model=PostMortemResponse,
)
async def create_post_mortem(
    request: CreatePostMortemRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """创建复盘记录"""
    try:
        post_mortem = service.create_post_mortem(
            decision_id=request.decision_id,
            original_decision=request.original_decision,
            realized_outcome=request.realized_outcome,
            learning_points=request.learning_points,
            outcome_metrics=request.outcome_metrics,
            linked_signal_accuracy=request.linked_signal_accuracy,
        )
        return _post_mortem_to_response(post_mortem)
    except Exception as e:
        logger.error(f"Create post-mortem failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/post-mortem/{post_mortem_id}",
    response_model=PostMortemResponse,
)
async def update_post_mortem(
    post_mortem_id: str,
    request: UpdatePostMortemRequest,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """更新复盘记录"""
    try:
        post_mortem = service.update_post_mortem(
            post_mortem_id=post_mortem_id,
            realized_outcome=request.realized_outcome,
            learning_points=request.learning_points,
            outcome_metrics=request.outcome_metrics,
            linked_signal_accuracy=request.linked_signal_accuracy,
        )
        if not post_mortem:
            raise HTTPException(status_code=404, detail=f"Post-mortem {post_mortem_id} not found")
        return _post_mortem_to_response(post_mortem)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update post-mortem failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/post-mortem/{post_mortem_id}",
    response_model=PostMortemResponse,
)
async def get_post_mortem(
    post_mortem_id: str,
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """获取复盘详情"""
    try:
        post_mortem = service.get_post_mortem(post_mortem_id)
        if not post_mortem:
            raise HTTPException(status_code=404, detail=f"Post-mortem {post_mortem_id} not found")
        return _post_mortem_to_response(post_mortem)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get post-mortem failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/post-mortems",
    response_model=List[PostMortemResponse],
)
async def list_post_mortems(
    limit: int = Query(100, ge=1, le=1000),
    service: DecisionConsoleService = Depends(get_decision_console_service),
):
    """列出所有复盘记录"""
    try:
        post_mortems = service.list_post_mortems(limit=limit)
        return [_post_mortem_to_response(pm) for pm in post_mortems]
    except Exception as e:
        logger.error(f"List post-mortems failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
