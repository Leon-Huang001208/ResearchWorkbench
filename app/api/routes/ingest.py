"""摄入路由"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, cast

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.models import ErrorResponse, IngestResponse, IngestTextRequest
from core.observability import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from services.ingest_service import IngestService


router = APIRouter(prefix="/api/ingest", tags=["ingest"])


_shared_vector_store = None


def _get_vector_store():
    """懒加载共享向量库"""
    global _shared_vector_store
    if _shared_vector_store is None:
        from data_layer.repositories.base import SessionLocal
        from knowledge_layer.retrieval.vector_store import PGVectorStore

        _shared_vector_store = PGVectorStore(session_factory=SessionLocal)
    return _shared_vector_store


def get_ingest_service() -> IngestService:
    """获取摄入服务实例（每次请求使用统一 DB 会话）"""
    from data_layer.repositories.assertion_repository import AssertionRepositoryImpl
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.document_repository import DocumentRepositoryImpl
    from data_layer.repositories.event_repository import EventRepositoryImpl
    from services.ingest_service import IngestService

    session = SessionLocal()
    doc_repo = DocumentRepositoryImpl(session)
    assertion_repo = AssertionRepositoryImpl(session)
    event_repo = EventRepositoryImpl(session)

    return IngestService(
        document_repo=doc_repo,
        assertion_repo=assertion_repo,
        event_repo=event_repo,
        vector_store=_get_vector_store(),
    )


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
        shutil.copyfileobj(cast(BinaryIO, file.file), cast(Any, tmp))
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
