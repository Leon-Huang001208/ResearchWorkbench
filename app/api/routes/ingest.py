"""摄入路由"""
import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.models import ErrorResponse, IngestResponse, IngestTextRequest
from core.observability import get_logger
from core.services.ingest_service import IngestService
from data_layer.adapters.data_source_router import DataSourceRouter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def get_ingest_service() -> IngestService:
    """获取摄入服务实例"""
    return IngestService()


@router.post(
    "/text",
    response_model=IngestResponse,
    responses={500: {"model": ErrorResponse}},
)
async def ingest_text(
    request: IngestTextRequest,
    service: IngestService = Depends(get_ingest_service),
):
    """摄入文本"""
    try:
        result = service.ingest_text(
            text=request.text,
            source_type=request.source_type,
            source_name=request.source_name,
            title=request.title,
        )
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/file",
    response_model=IngestResponse,
    responses={500: {"model": ErrorResponse}},
)
async def ingest_file(
    file: UploadFile,
    source_type: str = "report",
    source_name: str = "unknown",
    title: str = "",
    service: IngestService = Depends(get_ingest_service),
):
    """上传文件摄入"""
    # 将上传文件保存到临时路径
    suffix = Path(file.filename or "upload.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = service.ingest_file(
            file_path=tmp_path,
            source_type=source_type,
            source_name=source_name or file.filename or "unknown",
            title=title or file.filename or "Untitled",
        )
        return IngestResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        tmp_path.unlink(missing_ok=True)


@router.post("/cls", response_model=IngestResponse)
async def ingest_cls(
    days: int = 2,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """摄入财联社电报"""
    try:
        router_ = DataSourceRouter()
        envelopes = await router_.fetch_news_cls(
            days=days, start_date=start_date, end_date=end_date
        )
        return IngestResponse(
            success=True,
            message=f"Fetched {len(envelopes)} CLS telegrams",
            doc_ids=[e.id for e in envelopes],
        )
    except Exception as e:
        logger.error("cls ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cnstock", response_model=IngestResponse)
async def ingest_cnstock(
    start_date: str = "",
    end_date: str = "",
    channel: str = "证券",
):
    """摄入中国证券网新闻"""
    try:
        router_ = DataSourceRouter()
        envelopes = await router_.fetch_news_cnstock(
            start_date=start_date, end_date=end_date, channel=channel
        )
        return IngestResponse(
            success=True,
            message=f"Fetched {len(envelopes)} cnstock news",
            doc_ids=[e.id for e in envelopes],
        )
    except Exception as e:
        logger.error("cnstock ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zq", response_model=IngestResponse)
async def ingest_zq(
    search: str = "",
    doc_types: str = "REPORT",
    start_date: str | None = None,
    end_date: str | None = None,
):
    """摄入知丘内容（研报/公众号/会议纪要）"""
    try:
        router_ = DataSourceRouter()
        envelopes = await router_.fetch_reports_zq(
            search=search, doc_types=doc_types,
            start_date=start_date, end_date=end_date
        )
        return IngestResponse(
            success=True,
            message=f"Fetched {len(envelopes)} zq documents",
            doc_ids=[e.id for e in envelopes],
        )
    except Exception as e:
        logger.error("zq ingest failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
