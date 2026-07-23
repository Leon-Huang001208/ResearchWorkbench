"""PDF Conversion Admin API — PDF 转换管理路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.contracts.pdf_conversion import StrategyType
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.pdf_conversion_service import PDFConversionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/pdf", tags=["pdf-conversion-admin"])


# ── 请求/响应模型 ──────────────────────────────────────


class ConvertPdfRequest(BaseModel):
    """PDF 转换请求"""

    pdf_id: str = Field(..., description="PDF artifact ID")
    strategy: StrategyType = Field(
        default=StrategyType.AUTO, description="首选策略 (auto/mineru/markitdown/raw_text)"
    )


class ConvertPdfResponse(BaseModel):
    """PDF 转换响应"""

    pdf_id: str
    success: bool
    strategy_used: str
    error_message: str = ""
    page_count: int = 0
    token_count: int = 0
    quality_score: Optional[float] = None
    duration_ms: Optional[int] = None
    has_tables: bool = False
    has_images: bool = False
    has_code_blocks: bool = False


class PdfStatsResponse(BaseModel):
    """PDF 统计响应"""

    total_pdfs: int = 0
    pending_conversion: int = 0
    converted: int = 0
    failed_conversion: int = 0
    by_status: dict = Field(default_factory=dict)


class PdfPendingResponse(BaseModel):
    """待转换 PDF 列表"""

    items: list[dict] = Field(default_factory=list)
    count: int = 0


class RetryRequest(BaseModel):
    """重试请求"""

    limit: int = Field(default=10, ge=1, le=100, description="每次重试的最大数量")


class RetryResponse(BaseModel):
    """重试响应"""

    total: int = 0
    success: int = 0
    failed: int = 0
    results: list[ConvertPdfResponse] = Field(default_factory=list)


# ── 路由 ──────────────────────────────────────────────


def _get_service(db: Session) -> PDFConversionService:
    """获取 PDF 转换服务实例"""
    return PDFConversionService(db)


@router.post("/convert", response_model=ConvertPdfResponse)
async def convert_pdf(body: ConvertPdfRequest, db: Session = Depends(get_db)):
    """触发 PDF 转换

    对指定 pdf_id 执行转换，可通过 strategy 参数指定首选策略。
    """
    service = _get_service(db)
    result = service.convert_pdf(body.pdf_id, preferred_strategy=body.strategy)

    return ConvertPdfResponse(
        pdf_id=body.pdf_id,
        success=result.success,
        strategy_used=result.strategy_used,
        error_message=result.error_message,
        page_count=result.page_count,
        token_count=result.token_count,
        quality_score=result.quality_score,
        has_tables=result.has_tables,
        has_images=result.has_images,
        has_code_blocks=result.has_code_blocks,
    )


@router.get("/stats", response_model=PdfStatsResponse)
async def get_pdf_stats(db: Session = Depends(get_db)):
    """获取 PDF 转换统计"""
    service = _get_service(db)
    stats = service.get_stats()

    return PdfStatsResponse(
        total_pdfs=stats.get("total_pdfs", 0),
        pending_conversion=stats.get("pending_conversion", 0),
        converted=stats.get("converted", 0),
        failed_conversion=stats.get("failed_conversion", 0),
        by_status=stats.get("by_status", {}),
    )


@router.get("/pending", response_model=PdfPendingResponse)
async def get_pending(
    limit: int = Query(default=50, ge=1, le=200, description="返回数量上限"),
    db: Session = Depends(get_db),
):
    """获取待转换的 PDF 列表"""
    service = _get_service(db)
    pending = service.get_pending(limit=limit)

    items = [
        {
            "pdf_id": p.pdf_id,
            "file_name": getattr(p, "file_name", ""),
            "source_type": getattr(p, "source_type", ""),
            "conversion_strategy": getattr(p, "parse_version", ""),
            "status": p.parse_status,
            "created_at": str(p.created_at) if p.created_at else None,
        }
        for p in pending
    ]

    return PdfPendingResponse(items=items, count=len(items))


@router.post("/retry", response_model=RetryResponse)
async def retry_failed(body: RetryRequest, db: Session = Depends(get_db)):
    """重试失败的 PDF 转换"""
    service = _get_service(db)
    results = service.retry_failed(limit=body.limit)

    items = [
        ConvertPdfResponse(
            pdf_id="",
            success=r.success,
            strategy_used=r.strategy_used,
            error_message=r.error_message,
            page_count=r.page_count,
            token_count=r.token_count,
            quality_score=r.quality_score,
            has_tables=r.has_tables,
            has_images=r.has_images,
            has_code_blocks=r.has_code_blocks,
        )
        for r in results
    ]

    success_count = sum(1 for r in results if r.success)

    return RetryResponse(
        total=len(results),
        success=success_count,
        failed=len(results) - success_count,
        results=items,
    )
