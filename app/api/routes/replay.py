"""回放 API 路由 — 历史事件批量回放 & 信号校准"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.models import ErrorResponse
from core.contracts.replay import ReplayAggregate, ReplayJob, ReplayJobCreateRequest, ReplayResult
from core.services.replay_service import ReplayService

router = APIRouter(prefix="/api/replay", tags=["replay"])


def get_replay_service() -> ReplayService:
    """获取 ReplayService 实例（内存版）"""
    if not hasattr(get_replay_service, "_instance"):
        get_replay_service._instance = ReplayService()
    return get_replay_service._instance


# ─── 创建回放任务 ────────────────────────────────────────


@router.post(
    "/jobs",
    response_model=ReplayJob,
    responses={500: {"model": ErrorResponse}},
)
async def create_replay_job(
    request: ReplayJobCreateRequest,
    service: ReplayService = Depends(get_replay_service),
):
    """创建回放任务"""
    try:
        return service.create_job(
            name=request.name,
            description=request.description,
            event_filter=request.event_filter,
            max_events=request.max_events,
        )
    except Exception as e:
        from core.observability import get_logger

        logger = get_logger(__name__)
        logger.error("Failed to create replay job", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─── 执行回放 ────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/run",
    response_model=ReplayAggregate,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def run_replay_job(
    job_id: str,
    service: ReplayService = Depends(get_replay_service),
):
    """执行回放"""
    try:
        aggregate = await service.run_job(job_id)
        return aggregate
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        from core.observability import get_logger

        logger = get_logger(__name__)
        logger.error("Failed to run replay job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ─── 查询状态 ────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/status",
    response_model=ReplayJob,
    responses={404: {"model": ErrorResponse}},
)
async def get_replay_job_status(
    job_id: str,
    service: ReplayService = Depends(get_replay_service),
):
    """查询回放任务状态"""
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Replay job {job_id} not found")
    return job


# ─── 获取结果 ────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/results",
    response_model=list[ReplayResult],
    responses={404: {"model": ErrorResponse}},
)
async def get_replay_results(
    job_id: str,
    service: ReplayService = Depends(get_replay_service),
):
    """获取回放结果"""
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Replay job {job_id} not found")
    return service._get_all_results(job_id)


# ─── 获取聚合分析 ────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/aggregate",
    response_model=ReplayAggregate,
    responses={404: {"model": ErrorResponse}},
)
async def get_replay_aggregate(
    job_id: str,
    service: ReplayService = Depends(get_replay_service),
):
    """获取聚合分析"""
    aggregate = service.get_aggregate(job_id)
    if aggregate is None:
        raise HTTPException(
            status_code=404,
            detail=f"No aggregate data for replay job {job_id}",
        )
    return aggregate


# ─── 获取校准报告 ────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/calibration",
    responses={404: {"model": ErrorResponse}},
)
async def get_replay_calibration(
    job_id: str,
    service: ReplayService = Depends(get_replay_service),
):
    """获取校准报告"""
    calibration = service.calibrate(job_id)
    if calibration is None:
        raise HTTPException(
            status_code=404,
            detail=f"No calibration data for replay job {job_id}",
        )
    return calibration
