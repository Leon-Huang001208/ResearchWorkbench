"""Ingest Admin API — 摄入管理路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.models import (
    IngestConfigResponse,
    IngestConfigUpdate,
    IngestPauseRequest,
    IngestPauseResponse,
    IngestResetResponse,
    IngestResumeResponse,
    IngestTriggerRequest,
    IngestTriggerResponse,
)
from core.observability import get_logger
from data_layer.repositories import crawl_state_repository
from data_layer.repositories.base import get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ingest/admin", tags=["ingest-admin"])


@router.post(
    "/{source_type}/trigger",
    response_model=IngestTriggerResponse,
)
async def trigger_ingest(
    source_type: str,
    body: IngestTriggerRequest,
    db: Session = Depends(get_db),
):
    """手动触发摄入；dry-run 不访问数据库。"""
    try:
        if body.dry_run:
            logger.info(
                "Manual ingest dry run completed",
                extra={"source_type": source_type},
            )
            return IngestTriggerResponse(
                source_type=source_type,
                triggered=False,
                dry_run=True,
                message="Dry run complete",
            )

        # 检查是否暂停
        state = crawl_state_repository.get_crawl_state(db, source_type)
        if state and state.is_paused:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot trigger: source {source_type} is paused",
            )

        # TODO: 实际触发逻辑（发布到队列）
        # 这里暂时只返回成功响应

        logger.info(f"Manual ingest triggered for {source_type} (dry_run={body.dry_run})")

        return IngestTriggerResponse(
            source_type=source_type,
            triggered=not body.dry_run,
            dry_run=body.dry_run,
            message="Trigger queued successfully" if not body.dry_run else "Dry run complete",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trigger ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{source_type}/pause",
    response_model=IngestPauseResponse,
)
async def pause_ingest(
    source_type: str,
    body: IngestPauseRequest,
    db: Session = Depends(get_db),
):
    """暂停摄入"""
    try:
        # 确保状态存在
        state = crawl_state_repository.get_crawl_state(db, source_type)
        if not state:
            # 如果不存在，创建一个基础状态
            from datetime import datetime

            from data_layer.repositories.models import CrawlStateV1DB

            state = CrawlStateV1DB(
                state_id=f"state_{source_type}",
                source_type=source_type,
                source_name=None,
                watermark_id=None,
                watermark_timestamp=None,
                watermark_metadata={},
                dedupe_key=None,
                dedupe_count=0,
                total_fetched=0,
                total_skipped=0,
                total_failed=0,
                crawl_config={},
                crawl_mode="incremental",
                last_run_id=None,
                last_run_start=None,
                last_run_end=None,
                is_paused=False,
                pause_reason=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                extra={},
            )
            db.add(state)
            db.commit()

        # 暂停
        updated = crawl_state_repository.pause_crawl(db, source_type, body.reason)

        return IngestPauseResponse(
            source_type=source_type,
            paused=updated is not None,
            reason=body.reason,
        )
    except Exception as e:
        logger.error(f"Pause ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{source_type}/resume",
    response_model=IngestResumeResponse,
)
async def resume_ingest(
    source_type: str,
    db: Session = Depends(get_db),
):
    """恢复摄入"""
    try:
        updated = crawl_state_repository.resume_crawl(db, source_type)

        if updated is None:
            raise HTTPException(
                status_code=404,
                detail=f"Source {source_type} not found",
            )

        return IngestResumeResponse(
            source_type=source_type,
            resumed=not updated.is_paused,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{source_type}/reset",
    response_model=IngestResetResponse,
)
async def reset_ingest(
    source_type: str,
    db: Session = Depends(get_db),
):
    """重置摄入状态（清除水位线）"""
    try:
        updated = crawl_state_repository.reset_crawl_state(db, source_type)

        if updated is None:
            raise HTTPException(
                status_code=404,
                detail=f"Source {source_type} not found",
            )

        return IngestResetResponse(
            source_type=source_type,
            reset=True,
            message="Watermark cleared, next fetch will be full",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset ingest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{source_type}/config",
    response_model=IngestConfigResponse,
)
async def get_ingest_config(
    source_type: str,
    db: Session = Depends(get_db),
):
    """获取摄入配置"""
    try:
        state = crawl_state_repository.get_crawl_state(db, source_type)

        if state is None:
            # 返回默认配置
            return IngestConfigResponse(
                source_type=source_type,
                crawl_config={},
                crawl_mode="incremental",
                is_paused=False,
            )

        return IngestConfigResponse(
            source_type=source_type,
            crawl_config=state.crawl_config or {},
            crawl_mode=state.crawl_mode or "incremental",
            is_paused=state.is_paused,
        )
    except Exception as e:
        logger.error(f"Get ingest config failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{source_type}/config",
    response_model=IngestConfigResponse,
)
async def update_ingest_config(
    source_type: str,
    body: IngestConfigUpdate,
    db: Session = Depends(get_db),
):
    """更新摄入配置"""
    try:
        state = crawl_state_repository.get_crawl_state(db, source_type)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail=f"Source {source_type} not found",
            )

        # 更新配置
        new_crawl_config = (
            body.crawl_config if body.crawl_config is not None else state.crawl_config
        )
        new_crawl_mode = body.crawl_mode if body.crawl_mode is not None else state.crawl_mode

        # 使用 UPSERT 或者直接更新
        from datetime import datetime

        # 直接更新字段（兼容各种情况）
        state.crawl_config = new_crawl_config
        state.crawl_mode = new_crawl_mode
        state.updated_at = datetime.utcnow()

        try:
            db.commit()
            db.refresh(state)
        except Exception:
            db.rollback()
            # 如果 commit 失败，可能是对象状态问题，重新读取后再次尝试
            state = crawl_state_repository.get_crawl_state(db, source_type)
            if state:
                state.crawl_config = new_crawl_config
                state.crawl_mode = new_crawl_mode
                state.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(state)

        logger.info(f"Ingest config updated for {source_type}")

        return IngestConfigResponse(
            source_type=source_type,
            crawl_config=new_crawl_config or {},
            crawl_mode=new_crawl_mode or "incremental",
            is_paused=bool(state.is_paused) if state is not None else False,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update ingest config failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
