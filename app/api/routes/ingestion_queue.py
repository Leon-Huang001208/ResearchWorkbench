"""统一摄取队列 API"""
from typing import List

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
from core.services.ingestion_queue_service import IngestionQueueService
from data_layer.repositories.base import get_db
from data_layer.repositories.ingestion_repository import IngestionQueueRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ingestion-queue", tags=["ingestion-queue"])


def get_ingestion_queue_service(db: Session = Depends(get_db)) -> IngestionQueueService:
    """获取摄取队列服务实例"""
    repo = IngestionQueueRepository(db)
    return IngestionQueueService(repository=repo)


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue(
    request: EnqueueRequest,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
):
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
):
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
):
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
):
    """最近处理记录"""
    try:
        return service.get_recent(limit=limit)
    except Exception as e:
        logger.error("Recent query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry", response_model=RetryResponse)
async def retry(
    limit: int = 100,
    service: IngestionQueueService = Depends(get_ingestion_queue_service),
):
    """重试失败项"""
    try:
        result = service.retry_failed(limit=limit)
        return RetryResponse(**result)
    except Exception as e:
        logger.error("Retry failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
