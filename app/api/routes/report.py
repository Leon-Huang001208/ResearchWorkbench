"""
研报生成和性能报告API路由
"""
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.observability import get_logger
from core.services.report_generator import ReportGenerator

logger = get_logger(__name__)
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
            canonical_id=request.canonical_id, report_type=request.report_type, as_of=as_of
        )
        return ReportGenerateResponse(
            report_id=report["report_id"],
            canonical_id=request.canonical_id,
            report_type=request.report_type,
            generated_at=as_of,
            download_url=f"/api/report/download/{report['report_id']}",
            content=report["content"],
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
        import tempfile

        from fastapi.responses import FileResponse

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write(content)
            temp_path = f.name
        return FileResponse(
            temp_path, filename=f"report_{report_id}.pdf", media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"研报不存在：{str(e)}")


# ─── 性能报告导出功能 ─────────────────────────────────────────────────────────


@router.get(
    "/performance",
    summary="Get performance report data (JSON)",
)
async def get_performance_report():
    """Get performance report data as JSON."""
    try:
        from sqlalchemy import text

        from data_layer.repositories.base import SessionLocal

        db = SessionLocal()
        try:
            # Get outcome stats
            outcome_result = db.execute(
                text(
                    """
                SELECT
                    COUNT(*) as total_outcomes,
                    AVG(outcome_return) as avg_return,
                    AVG(outcome_excess_return) as avg_excess_return,
                    COUNT(CASE WHEN outcome_return > 0 THEN 1 END) as win_count
                FROM signal_outcome
            """
                )
            )
            outcome_row = outcome_result.fetchone()

            # Get event type breakdown
            event_type_result = db.execute(
                text(
                    """
                SELECT
                    event_type,
                    COUNT(*) as count,
                    AVG(outcome_return) as avg_return,
                    AVG(outcome_excess_return) as avg_excess_return
                FROM signal_outcome
                WHERE event_type IS NOT NULL
                GROUP BY event_type
                ORDER BY count DESC
            """
                )
            )
            event_type_breakdown = []
            for row in event_type_result:
                event_type_breakdown.append(
                    {
                        "event_type": row[0],
                        "count": row[1],
                        "avg_return": float(row[2]) if row[2] is not None else 0.0,
                        "avg_excess_return": float(row[3]) if row[3] is not None else 0.0,
                    }
                )

            # Get recent outcomes
            recent_result = db.execute(
                text(
                    """
                SELECT
                    outcome_id,
                    subject_id,
                    event_type,
                    outcome_return,
                    outcome_excess_return,
                    max_drawdown,
                    lesson,
                    created_at
                FROM signal_outcome
                ORDER BY created_at DESC
                LIMIT 50
            """
                )
            )
            recent_outcomes = []
            for row in recent_result:
                recent_outcomes.append(
                    {
                        "outcome_id": row[0],
                        "subject_id": row[1],
                        "event_type": row[2],
                        "outcome_return": float(row[3]) if row[3] is not None else 0.0,
                        "outcome_excess_return": float(row[4]) if row[4] is not None else 0.0,
                        "max_drawdown": float(row[5]) if row[5] is not None else None,
                        "lesson": row[6],
                        "created_at": row[7].isoformat() if row[7] else None,
                    }
                )

            report = {
                "exported_at": datetime.utcnow().isoformat(),
                "summary": {
                    "total_outcomes": outcome_row[0] if outcome_row[0] is not None else 0,
                    "avg_return": float(outcome_row[1]) if outcome_row[1] is not None else 0.0,
                    "avg_excess_return": float(outcome_row[2])
                    if outcome_row[2] is not None
                    else 0.0,
                    "win_count": outcome_row[3] if outcome_row[3] is not None else 0,
                    "win_rate": (outcome_row[3] / outcome_row[0])
                    if outcome_row[0] and outcome_row[3]
                    else 0.0,
                },
                "event_type_breakdown": event_type_breakdown,
                "recent_outcomes": recent_outcomes,
            }

            return report

        finally:
            db.close()

    except Exception as e:
        logger.exception("Failed to get performance report")
        raise HTTPException(status_code=500, detail=f"Failed to get performance report: {str(e)}")


@router.get(
    "/performance/download",
    summary="Export performance report as JSON file download",
)
async def export_performance_report():
    """Export performance report as downloadable JSON file."""
    import json

    from fastapi.responses import StreamingResponse

    report = await get_performance_report()
    report_json = json.dumps(report, indent=2, ensure_ascii=False)

    buffer = BytesIO(report_json.encode("utf-8"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="alphafoundry-performance-{datetime.utcnow().strftime("%Y%m%d")}.json"'
        },
    )
