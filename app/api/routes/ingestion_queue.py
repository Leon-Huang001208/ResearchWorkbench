"""统一摄取队列 API"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.contracts.ingestion import (
    EnqueueRequest,
    EnqueueResponse,
    IngestionQueueItem,
    IngestionQueueStats,
    ProcessResponse,
    RetryResponse,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.ingestion_repository import IngestionQueueRepository
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl as TimingRepository
from services.ingestion_queue_service import IngestionQueueService
from services.signal_service import SignalService

if TYPE_CHECKING:
    from services.pipeline_service import ResearchPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ingestion-queue", tags=["ingestion-queue"])

# 模块级缓存：避免每次请求都重建 pipeline
_pipeline: ResearchPipeline | None = None


def _build_pipeline(db: Session) -> ResearchPipeline:
    """构建/更新 ResearchPipeline（带信号/择时持久化，模块级缓存）"""
    from services.pipeline_service import ResearchPipeline

    global _pipeline
    if _pipeline is None:
        signal_repo = SignalRepositoryImpl(db)
        signal_service = SignalService(repository=signal_repo)
        timing_repo = TimingRepository(db)
        _pipeline = ResearchPipeline(
            signal_service=signal_service,
            timing_repository=timing_repo,
        )
    else:
        # 每次请求更新 db session（防止使用已关闭的旧 session）
        if _pipeline.signal_service and _pipeline.signal_service.repository:
            _pipeline.signal_service.repository.db = db
        if _pipeline.timing_repository:
            _pipeline.timing_repository.db = db
    return _pipeline


def get_ingestion_queue_service(db: Session = Depends(get_db)) -> IngestionQueueService:
    """获取摄取队列服务实例（已注入 Golden Path pipeline）"""
    repo = IngestionQueueRepository(db)
    pipeline = _build_pipeline(db)
    return IngestionQueueService(repository=repo, pipeline=pipeline)


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue(
    request: EnqueueRequest,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> EnqueueResponse:
    """入队"""
    try:
        result = service.enqueue(request)
        return EnqueueResponse(**result)
    except Exception as e:
        logger.error("Enqueue failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process", response_model=ProcessResponse)
async def process(
    limit: int = 10,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> ProcessResponse:
    """处理下一批队列项"""
    try:
        result = await service.process_batch(limit=limit)
        return ProcessResponse(**result)
    except Exception as e:
        logger.error("Process failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=IngestionQueueStats)
async def stats(
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> IngestionQueueStats:
    """队列统计"""
    try:
        return service.get_stats()
    except Exception as e:
        logger.error("Stats failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent", response_model=List[IngestionQueueItem])
async def recent(
    limit: int = 20,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> List[IngestionQueueItem]:
    """最近处理记录"""
    try:
        return cast(List[IngestionQueueItem], service.get_recent(limit=limit))
    except Exception as e:
        logger.error("Recent query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry", response_model=RetryResponse)
async def retry(
    limit: int = 100,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
) -> RetryResponse:
    """重试失败项"""
    try:
        result = service.retry_failed(limit=limit)
        return RetryResponse(**result)
    except Exception as e:
        logger.error("Retry failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
