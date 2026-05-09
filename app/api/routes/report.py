"""
研报生成API路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from core.services.report_generator import ReportGenerator

router = APIRouter(prefix="/api/report", tags=["report"])

report_generator = ReportGenerator()

class ReportGenerateRequest(BaseModel):
    """研报生成请求"""
    canonical_id: str
    report_type: str = "full"  # full/summary/valuation
    as_of: datetime = None

class ReportGenerateResponse(BaseModel):
    """研报生成响应"""
    report_id: str
    canonical_id: str
    report_type: str
    generated_at: datetime
    download_url: str
    content: str

@router.post("/generate", response_model=ReportGenerateResponse, summary="生成资产研报")
async def generate_report(request: ReportGenerateRequest):
    """
    生成指定资产的研究报告，支持PDF和Markdown格式
    """
    try:
        as_of = request.as_of or datetime.now()
        report = await report_generator.generate(
            canonical_id=request.canonical_id,
            report_type=request.report_type,
            as_of=as_of
        )
        return ReportGenerateResponse(
            report_id=report["report_id"],
            canonical_id=request.canonical_id,
            report_type=request.report_type,
            generated_at=as_of,
            download_url=f"/api/report/download/{report['report_id']}",
            content=report["content"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"研报生成失败：{str(e)}")

@router.get("/download/{report_id}", summary="下载研报")
async def download_report(report_id: str):
    """
    下载生成的研报PDF文件
    """
    try:
        content = await report_generator.get_report_content(report_id)
        from fastapi.responses import FileResponse
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
            f.write(content)
            temp_path = f.name
        return FileResponse(temp_path, filename=f"report_{report_id}.pdf", media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"研报不存在：{str(e)}")
