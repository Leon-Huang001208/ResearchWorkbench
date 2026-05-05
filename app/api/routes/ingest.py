"""摄入路由"""
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.models import ErrorResponse, IngestResponse, IngestTextRequest
from core.services.ingest_service import IngestService

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
