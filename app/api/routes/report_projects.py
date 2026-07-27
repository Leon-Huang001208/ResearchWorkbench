"""Report project API routes."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import xml.etree.ElementTree as ET
import zipfile
from copy import deepcopy
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.observability import get_logger
from reporting.projects.project_manager import ReportProject, ReportProjectManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/report-projects", tags=["report-projects"])

# ── Reporting 服务（模块加载时初始化）─────────────────
# PEP 562 __getattr__ 懒加载在 Python 3.13+ uvicorn 下对模块内部
# LOAD_GLOBAL 访问失效，改用显式初始化。

report_project_manager = ReportProjectManager()

_report_generation_service = None
_report_chart_service = None

# ── 异步报告生成 Job Store ─────────────────────────────
_report_job_store: dict[str, dict] = {}
_report_job_store_lock = threading.Lock()
_REPORT_JOB_TTL = timedelta(hours=1)


def _get_report_generation_service():
    """Lazily initialize the report generation service."""
    global _report_generation_service
    if _report_generation_service is None:
        from data_layer.web_search import build_web_search_provider
        from reporting.projects.generation import ReportProjectGenerationService
        from services.web_search_service import WebSearchService

        provider = build_web_search_provider()
        web_search = WebSearchService(provider=provider) if provider else None
        _report_generation_service = ReportProjectGenerationService(
            web_search_service=web_search,
        )
    return _report_generation_service


def _get_report_chart_service():
    """Lazily initialize the report chart service."""
    global _report_chart_service
    if _report_chart_service is None:
        from reporting.projects.chart_generation import ReportProjectChartService

        _report_chart_service = ReportProjectChartService()
    return _report_chart_service


WORD_PREVIEW_LAYOUT_VERSION = "word-v1"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


class GeneratedReportInfo(BaseModel):
    """Generated report metadata."""

    file_name: str
    file_path: str
    generated_at: datetime


class ExcelSheetInfo(BaseModel):
    """Excel worksheet summary."""

    name: str
    dimension: str
    nonempty_count: int
    sample_cells: List[str] = Field(default_factory=list)


class DataAssetInfo(BaseModel):
    """Project data-folder asset summary."""

    file_name: str
    relative_path: str
    kind: str
    usage: str
    is_primary: bool = False


class ReportProjectInfo(BaseModel):
    """Report project summary for the frontend."""

    name: str
    slug: str
    project_type: str = "word"
    project_dir: str
    template_path: str = ""
    template_filename: str = ""
    word_template_path: str
    word_template_filename: str
    ppt_template_path: str = ""
    ppt_template_filename: str = ""
    excel_workbook_path: str
    excel_workbook_filename: str
    report_config_path: str
    report_config_filename: str
    prompt_templates_path: str | None = None
    prompt_templates_filename: str | None = None
    data_source_files: List[str] = Field(default_factory=list)
    data_assets: List[DataAssetInfo] = Field(default_factory=list)
    word_placeholders: List[str] = Field(default_factory=list)
    ppt_placeholders: List[str] = Field(default_factory=list)
    report_config: Dict[str, Any] = Field(default_factory=dict)
    report_config_source: str = ""
    prompt_templates_source: str = ""
    compiled_plan: Dict[str, Any] = Field(default_factory=dict)
    keyword_profiles: Dict[str, Any] = Field(default_factory=dict)
    excel_sheets: List[ExcelSheetInfo] = Field(default_factory=list)
    output_dir: str
    run_log_dir: str
    generated_reports: List[GeneratedReportInfo] = Field(default_factory=list)


class ReportProjectScanIssueInfo(BaseModel):
    """Non-fatal report project scan diagnostic for the frontend."""

    code: str
    project_slug: str
    relative_path: str


class ReportProjectsListResponse(BaseModel):
    """Report projects list response."""

    projects: List[ReportProjectInfo]
    total: int
    issues: List[ReportProjectScanIssueInfo] = Field(default_factory=list)


class RenderReportProjectRequest(BaseModel):
    """Project report render request."""

    placeholders: Dict[str, str] = Field(default_factory=dict)
    generate_from_config: bool = True
    lookback_days: int | None = Field(default=None, ge=1, le=90)
    report_date: str | None = None
    data_scope: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class UpdateReportProjectRequest(BaseModel):
    """Report project update request."""

    project_name: str


class UpdateReportProjectSourceRequest(BaseModel):
    """Report project source update request."""

    source_kind: str
    content: str


class RenderReportProjectResponse(BaseModel):
    """Project report render response."""

    success: bool
    project_name: str
    slug: str
    file_name: str
    file_path: str
    download_url: str
    preview_url: str
    run_log_url: str
    generated_at: datetime
    generated_placeholder_count: int = 0
    evidence_count: int = 0
    warnings: List[str] = Field(default_factory=list)


class RenderJobCreatedResponse(BaseModel):
    """Response returned when a render job is submitted."""

    job_id: str
    status_url: str


class RenderJobStatusResponse(BaseModel):
    """Response returned when polling a render job's status."""

    status: str
    phase: str
    message: str
    completed_sections: int = 0
    total_sections: int = 0
    result: dict | None = None
    error: str | None = None


class OpenReportProjectFolderResponse(BaseModel):
    """Result for opening a local report project folder."""

    success: bool
    folder_path: str


@router.get("/", response_model=ReportProjectsListResponse, summary="列出报告项目")
async def list_report_projects():
    """List report projects stored as project folders."""
    try:
        scan = report_project_manager.scan_projects()
        projects = []
        for project in scan.projects:
            try:
                projects.append(_to_project_info(project))
            except Exception as exc:
                logger.error(
                    "Failed to serialize report project info",
                    slug=project.slug,
                    error=str(exc),
                    exc_info=True,
                )
        issues = [
            ReportProjectScanIssueInfo(
                code=issue.code,
                project_slug=issue.project_slug,
                relative_path=issue.relative_path,
            )
            for issue in scan.issues
        ]
        return ReportProjectsListResponse(
            projects=projects,
            total=len(projects),
            issues=issues,
        )
    except Exception as exc:
        logger.exception("Failed to list report projects")
        raise HTTPException(status_code=500, detail=f"Failed to list report projects: {exc}")


@router.post("/upload", response_model=ReportProjectInfo, summary="上传报告项目包")
async def upload_report_project(
    project_name: str = Form(..., description="报告项目名称"),
    project_type: str = Form("word", description="项目类型：word 或 ppt"),
    word_template: UploadFile | None = File(None, description="Word 模板 .docx"),
    ppt_template: UploadFile | None = File(None, description="PPT 模板 .pptx"),
    excel_workbook: UploadFile | None = File(None, description="Excel 数据底稿 .xlsx"),
    report_config: UploadFile | None = File(None, description="报告配置 .yaml/.yml"),
    prompt_templates: UploadFile | None = File(None, description="Prompt 模板 .md"),
    data_files: List[UploadFile] = File(default_factory=list, description="配套数据文件"),
):
    """Create a report project folder from uploaded project package assets."""
    slug = _safe_project_slug(project_name)
    project_dir = report_project_manager.projects_root / slug
    if project_dir.exists():
        raise HTTPException(status_code=409, detail=f"Report project already exists: {slug}")

    try:
        normalized_project_type = project_type.strip().lower()
        if normalized_project_type not in {"word", "ppt"}:
            raise HTTPException(status_code=400, detail="Unsupported report project type")
        if normalized_project_type == "word" and not word_template:
            raise HTTPException(status_code=422, detail="Word project requires a .docx template")
        if normalized_project_type == "ppt" and not ppt_template:
            raise HTTPException(status_code=422, detail="PPT project requires a .pptx template")

        templates_dir = project_dir / "templates"
        data_dir = project_dir / "data"
        config_dir = project_dir / "config"
        generated_dir = project_dir / "generated"
        runs_dir = project_dir / "runs"
        for directory in [templates_dir, data_dir, config_dir, generated_dir, runs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        if word_template and word_template.filename:
            _require_suffix(word_template.filename, [".docx"], "Word 模板")
        if ppt_template and ppt_template.filename:
            _require_suffix(ppt_template.filename, [".pptx"], "PPT 模板")
        if excel_workbook and excel_workbook.filename:
            _require_suffix(excel_workbook.filename, [".xlsx"], "Excel 数据底稿")
        if report_config and report_config.filename:
            _require_suffix(report_config.filename, [".yaml", ".yml"], "报告配置")
        if prompt_templates:
            _require_suffix(prompt_templates.filename or "", [".md"], "Prompt 模板")

        word_path = templates_dir / "report_template.docx"
        ppt_path = templates_dir / "report_template.pptx"
        report_config_path = config_dir / "report_config.yaml"

        if normalized_project_type == "ppt" and ppt_template:
            ppt_path.write_bytes(await ppt_template.read())
        elif word_template:
            word_path.write_bytes(await word_template.read())

        excel_filename = ""
        if excel_workbook and excel_workbook.filename:
            excel_filename = _safe_filename(excel_workbook.filename)
            excel_path = data_dir / excel_filename
            excel_path.write_bytes(await excel_workbook.read())
        if report_config and report_config.filename:
            report_config_path.write_bytes(await report_config.read())
        else:
            default_source = (
                _build_default_ppt_report_config_source(ppt_path)
                if normalized_project_type == "ppt"
                else _build_default_report_config_source(word_path)
            )
            report_config_path.write_text(default_source, encoding="utf-8")

        prompt_path = None
        if prompt_templates:
            prompt_path = config_dir / "prompt_templates.md"
            prompt_path.write_bytes(await prompt_templates.read())

        data_source_paths: List[Path] = []
        for upload in data_files or []:
            filename = _safe_filename(upload.filename or "")
            if not filename:
                continue
            _require_suffix(filename, [".json", ".xlsx", ".png"], "数据文件")
            target_path = data_dir / filename
            target_path.write_bytes(await upload.read())
            data_source_paths.append(target_path)

        project_data = {
            "name": project_name,
            "project_type": normalized_project_type,
            "report_config": "config/report_config.yaml",
            "output_dir": "generated",
            "run_log_dir": "runs",
        }
        if normalized_project_type == "ppt":
            project_data["active_ppt_template"] = "templates/report_template.pptx"
        else:
            project_data["active_word_template"] = "templates/report_template.docx"
        if excel_filename:
            project_data["active_excel_workbook"] = f"data/{excel_filename}"
        if prompt_path:
            project_data["prompt_templates"] = "config/prompt_templates.md"
        if data_source_paths:
            project_data["data_sources"] = [f"data/{path.name}" for path in data_source_paths]

        import yaml

        (project_dir / "project.yaml").write_text(
            yaml.safe_dump(project_data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        project = report_project_manager.get_project(slug)
        logger.info("Uploaded report project package", slug=slug, project_dir=str(project_dir))
        return _to_project_info(project)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to upload report project", project_name=project_name)
        raise HTTPException(status_code=500, detail=f"Failed to upload report project: {exc}")


@router.get("/{slug}", response_model=ReportProjectInfo, summary="获取报告项目详情")
async def get_report_project(slug: str):
    """Get one report project by folder slug."""
    try:
        return _to_project_info(report_project_manager.get_project(slug))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to get report project", slug=slug)
        raise HTTPException(status_code=500, detail=f"Failed to get report project: {exc}")


@router.patch("/{slug}", response_model=ReportProjectInfo, summary="更新报告项目")
async def update_report_project(slug: str, request: UpdateReportProjectRequest):
    """Rename a report project and update its project.yaml."""
    try:
        project = report_project_manager.rename_project(slug, request.project_name)
        return _to_project_info(project)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except FileExistsError:
        raise HTTPException(
            status_code=409, detail=f"Report project already exists: {request.project_name}"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to update report project", slug=slug)
        raise HTTPException(status_code=500, detail=f"Failed to update report project: {exc}")


@router.put("/{slug}/source", response_model=ReportProjectInfo, summary="保存报告项目源码")
async def update_report_project_source(slug: str, request: UpdateReportProjectSourceRequest):
    """Persist editable report project source files."""
    try:
        project = report_project_manager.get_project(slug)
        if request.source_kind == "prompt_templates":
            target_path = project.prompt_templates_path
            if not target_path:
                target_path = project.project_dir / "config" / "prompt_templates.md"
                _attach_prompt_templates(project.project_dir, target_path)
        elif request.source_kind == "report_config":
            target_path = project.report_config_path
        else:
            raise HTTPException(status_code=400, detail="Unsupported source kind")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(request.content, encoding="utf-8")
        logger.info(
            "Updated report project source",
            slug=slug,
            source_kind=request.source_kind,
            path=str(target_path),
        )
        return _to_project_info(report_project_manager.get_project(slug))
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to update report project source", slug=slug)
        raise HTTPException(
            status_code=500, detail=f"Failed to update report project source: {exc}"
        )


def _run_refresh_in_com_thread(project: Any) -> Any:
    """在 COM-initialized 线程中执行 Excel/Wind 刷新。

    Windows COM 要求调用线程初始化 COM STA。xlwings 内部也会初始化，
    但在 uvicorn asyncio 线程池中显式初始化更安全。
    """
    try:
        import pythoncom

        pythoncom.CoInitialize()
    except ImportError:
        pass

    try:
        from services.report_workbook_refresh import ReportWorkbookRefreshService

        return ReportWorkbookRefreshService().refresh(project=project)
    finally:
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except (ImportError, Exception):
            pass


async def _refresh_report_workbook(project: Any, slug: str) -> None:
    """Refresh the report project's Excel workbook via Wind/xlwings before generation.

    在独立线程中运行 COM 刷新，避免阻塞 event loop 和 COM apartment 问题。
    Failure is non-blocking: if the refresh fails (xlwings unavailable, Wind not
    logged in, timeout, etc.), generation proceeds with the cached formula values.
    """
    excel_refresh_config = project.config.get("excel_refresh") or {}
    if not excel_refresh_config.get("enabled"):
        return
    if project.excel_workbook_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return

    try:
        import asyncio

        logger.info("Refreshing report workbook before generation", slug=slug)
        refresh_result = await asyncio.to_thread(_run_refresh_in_com_thread, project)
        logger.info(
            "Report workbook refreshed",
            slug=slug,
            refreshed=refresh_result.refreshed,
        )
    except Exception as exc:
        logger.warning(
            "Report workbook refresh failed, continuing with cached data",
            slug=slug,
            error=str(exc),
        )


@router.post("/{slug}/render", response_model=RenderReportProjectResponse, summary="生成报告项目文档")
async def render_report_project(slug: str, request: RenderReportProjectRequest):
    """Render a report project into its own generated directory."""
    from reporting.projects.run import ReportProjectRunRequest, ReportProjectRunService

    try:
        project = report_project_manager.get_project(slug)
        await _refresh_report_workbook(project, slug)
        report_config, _ = _read_report_config(project.report_config_path)
        prompt_templates_source = _read_prompt_templates(project.prompt_templates_path)
        run_result = ReportProjectRunService(
            generation_service=_get_report_generation_service(),
            chart_service=_get_report_chart_service(),
        ).execute(
            project=project,
            report_config=report_config,
            prompt_templates_source=prompt_templates_source,
            request=ReportProjectRunRequest(
                placeholders=request.placeholders,
                generate_from_config=request.generate_from_config,
                lookback_days=request.lookback_days,
                report_date=request.report_date,
                data_scope=request.data_scope,
                start_date=request.start_date,
                end_date=request.end_date,
            ),
        )

        return RenderReportProjectResponse(
            success=True,
            project_name=run_result.project_name,
            slug=run_result.slug,
            file_name=run_result.file_name,
            file_path=str(run_result.output_path),
            download_url=f"/api/report-projects/{run_result.slug}/download/{run_result.file_name}",
            preview_url=f"/api/report-projects/{run_result.slug}/preview/{run_result.file_name}",
            run_log_url=f"/api/report-projects/{run_result.slug}/runs/{run_result.run_log_path.name}",
            generated_at=run_result.generated_at,
            generated_placeholder_count=run_result.generated_placeholder_count,
            evidence_count=run_result.evidence_count,
            warnings=run_result.warnings,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to render report project", slug=slug)
        raise HTTPException(status_code=500, detail=f"Failed to render report project: {exc}")


# ── 异步报告生成端点 ────────────────────────────────────


# Job 文件持久化目录（服务重启后可从磁盘恢复 job 状态）
def _job_files_dir(slug: str) -> Path:
    """Return the directory where job state files are persisted."""
    return report_project_manager.get_project(slug).project_dir / "jobs"


def _job_file_path(job_id: str, slug: str | None = None) -> Path | None:
    """Find a job file on disk by scanning all known project job dirs.

    If *slug* is provided, looks only in that project's jobs dir;
    otherwise scans all report projects.
    """
    if slug:
        return _job_files_dir(slug) / f"{job_id}.json"
    for proj in report_project_manager.list_projects():
        candidate = _job_files_dir(proj.slug) / f"{job_id}.json"
        if candidate.exists():
            return candidate
    return None


def _serialize_job(job: dict) -> dict:
    """Convert datetime values to ISO strings for JSON serialization."""
    out = dict(job)
    for key in ("created_at", "updated_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    return out


def _deserialize_job(data: dict) -> dict:
    """Convert ISO datetime strings back to datetime objects."""
    out = dict(data)
    for key in ("created_at", "updated_at"):
        val = out.get(key)
        if isinstance(val, str):
            try:
                out[key] = datetime.fromisoformat(val)
            except ValueError:
                pass
    return out


def _save_job_to_disk(job: dict) -> None:
    """Persist a job record to disk so it survives server restarts."""
    slug = job.get("slug")
    if not slug:
        return
    try:
        jobs_dir = _job_files_dir(slug)
        jobs_dir.mkdir(parents=True, exist_ok=True)
        path = jobs_dir / f"{job['job_id']}.json"
        path.write_text(
            json.dumps(_serialize_job(job), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # 文件写入失败不应阻塞主流程


def _load_job_from_disk(job_id: str) -> dict | None:
    """Try to load a job record from disk."""
    path = _job_file_path(job_id)
    if path is None or not path.exists():
        return None
    try:
        return _deserialize_job(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _delete_job_from_disk(job_id: str, slug: str | None = None) -> None:
    """Remove a job file from disk."""
    path = _job_file_path(job_id, slug=slug)
    if path and path.exists():
        try:
            path.unlink()
        except Exception:
            pass


def _update_job(job_id: str, **kwargs: Any) -> None:
    """Thread-safe partial update to a job record (memory + disk)."""
    with _report_job_store_lock:
        if job_id in _report_job_store:
            _report_job_store[job_id].update(kwargs)
            _report_job_store[job_id]["updated_at"] = datetime.now()
            _save_job_to_disk(_report_job_store[job_id])


def _cleanup_expired_jobs() -> None:
    """Remove completed or failed jobs older than the TTL (memory + disk)."""
    cutoff = datetime.now() - _REPORT_JOB_TTL
    with _report_job_store_lock:
        expired = [
            jid
            for jid, job in _report_job_store.items()
            if job["status"] in ("completed", "failed") and job["updated_at"] < cutoff
        ]
        for jid in expired:
            _delete_job_from_disk(jid, slug=_report_job_store[jid].get("slug"))
            del _report_job_store[jid]


def _run_report_render_job(
    job_id: str, slug: str, project: Any, request: RenderReportProjectRequest
) -> None:
    """Background thread target: execute report generation and update job store."""
    try:
        # Phase: prepare
        _update_job(
            job_id,
            status="running",
            phase="prepare",
            message="正在准备生成配置...",
        )

        # 在后台线程中直接调用 COM 刷新（线程已有独立上下文）
        try:
            _run_refresh_in_com_thread(project)
        except Exception as exc:
            logger.warning(
                "Report workbook refresh failed in background job, continuing with cached data",
                slug=slug,
                error=str(exc),
            )
        report_config, _ = _read_report_config(project.report_config_path)
        prompt_templates_source = _read_prompt_templates(project.prompt_templates_path)

        total_placeholders = len(
            [
                k
                for k, v in report_config.get("placeholders", {}).items()
                if isinstance(v, dict) and v.get("prompt_template")
            ]
        )
        _update_job(job_id, total_sections=max(total_placeholders, 1))

        # Phase: generate
        _update_job(
            job_id,
            phase="generate",
            message=f"正在生成报告内容（共 {total_placeholders} 个段落）...",
        )

        from reporting.projects.run import ReportProjectRunRequest, ReportProjectRunService

        run_result = ReportProjectRunService(
            generation_service=_get_report_generation_service(),
            chart_service=_get_report_chart_service(),
        ).execute(
            project=project,
            report_config=report_config,
            prompt_templates_source=prompt_templates_source,
            request=ReportProjectRunRequest(
                placeholders=request.placeholders,
                generate_from_config=request.generate_from_config,
                lookback_days=request.lookback_days,
                report_date=request.report_date,
                data_scope=request.data_scope,
                start_date=request.start_date,
                end_date=request.end_date,
            ),
        )

        # Phase: render
        _update_job(job_id, phase="render", message="正在渲染报告文档...")

        # Phase: save
        _update_job(job_id, phase="save", message="正在保存运行日志...")

        # Completed
        _update_job(
            job_id,
            status="completed",
            phase="save",
            message="报告生成完成",
            completed_sections=total_placeholders,
            result={
                "success": True,
                "project_name": run_result.project_name,
                "slug": run_result.slug,
                "file_name": run_result.file_name,
                "file_path": str(run_result.output_path),
                "download_url": (
                    f"/api/report-projects/{run_result.slug}/download/{run_result.file_name}"
                ),
                "preview_url": (
                    f"/api/report-projects/{run_result.slug}/preview/{run_result.file_name}"
                ),
                "run_log_url": (
                    f"/api/report-projects/{run_result.slug}/runs/"
                    f"{run_result.run_log_path.name}"
                ),
                "generated_at": run_result.generated_at.isoformat(),
                "generated_placeholder_count": run_result.generated_placeholder_count,
                "evidence_count": run_result.evidence_count,
                "warnings": run_result.warnings,
            },
        )

    except Exception as exc:
        logger.exception("Report render job failed", job_id=job_id, slug=slug)
        _update_job(
            job_id,
            status="failed",
            phase="save",
            message=f"生成失败: {exc}",
            error=str(exc),
        )


@router.post(
    "/{slug}/render-jobs",
    response_model=RenderJobCreatedResponse,
    summary="提交异步报告生成任务",
)
async def submit_report_render_job(slug: str, request: RenderReportProjectRequest):
    """Submit a background report render job and return a polling URL."""
    try:
        project = report_project_manager.get_project(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")

    job_id = uuid.uuid4().hex
    now = datetime.now()
    job: dict[str, Any] = {
        "job_id": job_id,
        "slug": slug,
        "status": "queued",
        "phase": "queued",
        "message": "任务已提交，等待执行",
        "completed_sections": 0,
        "total_sections": 0,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with _report_job_store_lock:
        _report_job_store[job_id] = job
        _save_job_to_disk(job)

    thread = threading.Thread(
        target=_run_report_render_job,
        args=(job_id, slug, project, request),
        daemon=True,
    )
    thread.start()

    status_url = f"/api/report-projects/{quote(slug, safe='')}/render-jobs/{job_id}"
    logger.info("Submitted report render job", job_id=job_id, slug=slug)
    return RenderJobCreatedResponse(job_id=job_id, status_url=status_url)


@router.get(
    "/{slug}/render-jobs/{job_id}",
    response_model=RenderJobStatusResponse,
    summary="查询异步报告生成任务状态",
)
async def get_report_render_job_status(slug: str, job_id: str):
    """Poll the status of a background report render job.

    Job state is stored in-memory for speed and mirrored to disk so it survives
    server restarts.  On a cache miss the endpoint transparently recovers from disk.
    """
    _cleanup_expired_jobs()

    with _report_job_store_lock:
        job = _report_job_store.get(job_id)

    # ── 磁盘回退：服务重启后内存为空，从磁盘恢复 ──
    if job is None:
        job = _load_job_from_disk(job_id)
        if job is not None and job.get("slug") == slug:
            # 恢复到内存供后续快速访问
            with _report_job_store_lock:
                _report_job_store[job_id] = job
            # 已完成的任务仍返回结果；进行中的任务恢复为 queued（线程已丢失）
            if job["status"] not in ("completed", "failed"):
                _update_job(
                    job_id,
                    status="failed",
                    phase="save",
                    message="服务端重启导致任务丢失，请重新提交生成。",
                    error="Server restarted — background thread was lost.",
                )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Render job not found: {job_id}. It may have expired or never existed.",
        )

    if job["slug"] != slug:
        raise HTTPException(
            status_code=404,
            detail=f"Render job not found for project: {slug}",
        )

    return RenderJobStatusResponse(
        status=job["status"],
        phase=job["phase"],
        message=job["message"],
        completed_sections=job["completed_sections"],
        total_sections=job["total_sections"],
        result=job["result"],
        error=job["error"],
    )


@router.get("/{slug}/preview/{file_name}", response_class=HTMLResponse, summary="预览报告项目生成文档")
async def preview_report_project_file(slug: str, file_name: str):
    """Render one generated docx as an inline HTML preview."""
    try:
        project = report_project_manager.get_project(slug)
        output_path = project.output_dir / file_name
        if output_path.parent.resolve() != project.output_dir.resolve():
            raise HTTPException(status_code=400, detail="Invalid generated report file name")
        if not output_path.exists():
            raise HTTPException(status_code=404, detail=f"Generated report not found: {file_name}")
        if project.project_type == "ppt" or output_path.suffix.lower() == ".pptx":
            return HTMLResponse(
                _pptx_preview_placeholder_html(output_path),
                media_type="text/html; charset=utf-8",
                headers={
                    "Cache-Control": "no-store, max-age=0",
                    "Pragma": "no-cache",
                },
            )
        asset_base_url = f"/api/report-projects/{project.slug}/preview-assets/{file_name}"
        return HTMLResponse(
            _docx_to_preview_html(output_path, asset_base_url=asset_base_url),
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
            },
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to preview report project file", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to preview report: {exc}")


@router.get("/{slug}/preview-assets/{file_name}/{asset_name}", summary="获取报告预览页图片")
async def get_report_project_preview_asset(slug: str, file_name: str, asset_name: str):
    """Serve one cached rendered page image for the generated Word preview."""
    try:
        if not re.fullmatch(r"page-\d{3}\.png", asset_name):
            raise HTTPException(status_code=400, detail="Invalid preview asset name")
        project = report_project_manager.get_project(slug)
        output_path = project.output_dir / file_name
        if output_path.parent.resolve() != project.output_dir.resolve():
            raise HTTPException(status_code=400, detail="Invalid generated report file name")
        if not output_path.exists():
            raise HTTPException(status_code=404, detail=f"Generated report not found: {file_name}")
        asset_path = _word_preview_page_asset_dir(output_path) / asset_name
        if asset_path.parent.resolve() != _word_preview_page_asset_dir(output_path).resolve():
            raise HTTPException(status_code=400, detail="Invalid preview asset path")
        if not asset_path.exists():
            raise HTTPException(status_code=404, detail=f"Preview asset not found: {asset_name}")
        return FileResponse(
            asset_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception(
            "Failed to read report project preview asset", slug=slug, file_name=file_name
        )
        raise HTTPException(status_code=500, detail=f"Failed to read preview asset: {exc}")


@router.get("/{slug}/preview-manifest/{file_name}", summary="获取报告预览分页清单")
async def get_report_project_preview_manifest(slug: str, file_name: str):
    """Return page manifest (src URLs, dimensions, labels) for the page-image preview viewer."""
    try:
        project = report_project_manager.get_project(slug)
        output_path = project.output_dir / file_name
        if output_path.parent.resolve() != project.output_dir.resolve():
            raise HTTPException(status_code=400, detail="Invalid generated report file name")
        if not output_path.exists():
            raise HTTPException(status_code=404, detail=f"Generated report not found: {file_name}")

        if output_path.suffix.lower() != ".docx":
            return {"fileName": file_name, "title": "预览", "pages": []}

        asset_base_url = f"/api/report-projects/{project.slug}/preview-assets/{file_name}"
        word_pdf = _build_word_pdf_preview(output_path)
        pages: List[Dict[str, Any]] = []
        if word_pdf:
            pages = _render_pdf_preview_page_assets(word_pdf, output_path, asset_base_url)
            if not pages:
                pages = _render_pdf_preview_pages(word_pdf)

        return {
            "fileName": file_name,
            "title": "Word 预览",
            "pages": pages,
        }
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to build preview manifest", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to build preview manifest: {exc}")


@router.get("/{slug}/download/{file_name}", summary="下载报告项目生成文档")
async def download_report_project_file(slug: str, file_name: str):
    """Download one generated project report."""
    try:
        project = report_project_manager.get_project(slug)
        output_path = project.output_dir / file_name
        if output_path.parent.resolve() != project.output_dir.resolve():
            raise HTTPException(status_code=400, detail="Invalid generated report file name")
        if not output_path.exists():
            raise HTTPException(status_code=404, detail=f"Generated report not found: {file_name}")

        media_type = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            if output_path.suffix.lower() == ".pptx" or project.project_type == "ppt"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return FileResponse(
            output_path,
            filename=file_name,
            media_type=media_type,
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to download report project file", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to download report: {exc}")


@router.post(
    "/{slug}/open-folder",
    response_model=OpenReportProjectFolderResponse,
    summary="打开报告项目生成目录",
)
async def open_report_project_generated_folder(slug: str, file_name: str | None = None):
    """Open the report project's generated folder, revealing a selected report when possible."""
    try:
        project = report_project_manager.get_project(slug)
        folder_path = project.output_dir
        folder_path.mkdir(parents=True, exist_ok=True)
        target_path = _resolve_generated_report_open_target(project, file_name)
        command = _open_folder_command(target_path, folder_path=folder_path)
        logger.info(
            "Opening report project generated folder",
            slug=slug,
            folder=str(folder_path),
            target=str(target_path),
        )
        subprocess.Popen(command)
        return OpenReportProjectFolderResponse(success=True, folder_path=str(folder_path))
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to open report project generated folder", slug=slug)
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {exc}")


@router.get("/{slug}/runs/{file_name}", summary="获取报告项目生成日志")
async def get_report_project_run_log(slug: str, file_name: str) -> Dict[str, Any]:
    """Return one report project run log JSON."""
    try:
        project = report_project_manager.get_project(slug)
        run_path = project.run_log_dir / file_name
        if run_path.parent.resolve() != project.run_log_dir.resolve():
            raise HTTPException(status_code=400, detail="Invalid run log file name")
        if not run_path.exists():
            raise HTTPException(status_code=404, detail=f"Run log not found: {file_name}")
        return json.loads(run_path.read_text(encoding="utf-8"))
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to read report project run log", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to read run log: {exc}")


def _resolve_generated_report_open_target(project: ReportProject, file_name: str | None) -> Path:
    """Return the generated report to reveal, or the output directory when no file is selected."""
    folder_path = project.output_dir
    if not file_name:
        return folder_path

    target_path = folder_path / file_name
    if target_path.parent.resolve() != folder_path.resolve():
        raise HTTPException(status_code=400, detail="Invalid generated report file name")
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Generated report not found: {file_name}")
    return target_path


def _open_folder_command(target_path: Path, *, folder_path: Path | None = None) -> List[str]:
    folder = folder_path or (target_path if target_path.is_dir() else target_path.parent)
    if sys.platform == "darwin":
        if target_path.is_file():
            return ["open", "-R", str(target_path)]
        return ["open", str(folder)]
    if sys.platform.startswith("win"):
        if target_path.is_file():
            return ["explorer", f"/select,{target_path}"]
        return ["explorer", str(folder)]
    return ["xdg-open", str(folder)]


def _to_project_info(project: ReportProject) -> ReportProjectInfo:
    from reporting.projections.ppt import extract_pptx_placeholders
    from reporting.projects.keyword_profiles import keyword_profiles_for_api
    from reporting.projects.plan import compile_report_plan

    report_config, report_config_source = _read_report_config(project.report_config_path)
    prompt_templates_source = _read_prompt_templates(project.prompt_templates_path)
    compiled_plan = compile_report_plan(report_config, prompt_templates_source).to_dict()
    excel_exists = project.excel_workbook_path.is_file()
    template_path = project.template_path or project.word_template_path
    ppt_template_path = project.ppt_template_path if project.project_type == "ppt" else None
    word_template_exists = project.project_type == "word" and project.word_template_path.is_file()
    ppt_template_exists = bool(ppt_template_path and ppt_template_path.is_file())
    return ReportProjectInfo(
        name=project.name,
        slug=project.slug,
        project_type=project.project_type,
        project_dir=str(project.project_dir),
        template_path=str(template_path) if template_path and template_path.is_file() else "",
        template_filename=template_path.name if template_path and template_path.is_file() else "",
        word_template_path=str(project.word_template_path) if word_template_exists else "",
        word_template_filename=project.word_template_path.name if word_template_exists else "",
        ppt_template_path=str(ppt_template_path) if ppt_template_exists else "",
        ppt_template_filename=(
            ppt_template_path.name if ppt_template_path and ppt_template_exists else ""
        ),
        excel_workbook_path=str(project.excel_workbook_path) if excel_exists else "",
        excel_workbook_filename=project.excel_workbook_path.name if excel_exists else "",
        report_config_path=str(project.report_config_path),
        report_config_filename=project.report_config_path.name,
        prompt_templates_path=(
            str(project.prompt_templates_path) if project.prompt_templates_path else None
        ),
        prompt_templates_filename=(
            project.prompt_templates_path.name if project.prompt_templates_path else None
        ),
        data_source_files=[path.name for path in project.data_source_paths],
        data_assets=_list_project_data_assets(project, report_config),
        word_placeholders=(
            _extract_docx_placeholders(project.word_template_path) if word_template_exists else []
        ),
        ppt_placeholders=(
            extract_pptx_placeholders(ppt_template_path)
            if ppt_template_exists and ppt_template_path
            else []
        ),
        report_config=report_config,
        report_config_source=report_config_source,
        prompt_templates_source=prompt_templates_source,
        compiled_plan=compiled_plan,
        keyword_profiles=keyword_profiles_for_api(),
        excel_sheets=_summarize_excel_workbook(project.excel_workbook_path) if excel_exists else [],
        output_dir=str(project.output_dir),
        run_log_dir=str(project.run_log_dir),
        generated_reports=[_to_generated_report_info(path) for path in project.generated_reports],
    )


def _list_project_data_assets(
    project: ReportProject, report_config: Dict[str, Any]
) -> List[DataAssetInfo]:
    """Return every file in the project data directory with a user-facing role."""
    data_dir = project.project_dir / "data"
    if not data_dir.exists():
        return []

    config_assets = report_config.get("assets") or {}
    chart_workbooks = {
        str(chart.get("workbook") or "")
        for chart in (report_config.get("charts") or {}).values()
        if isinstance(chart, dict)
    }
    table_workbooks = {
        str(table.get("workbook") or "")
        for table in (report_config.get("tables") or {}).values()
        if isinstance(table, dict)
    }
    configured_chart_workbook = str(config_assets.get("chart_workbook") or "")
    if configured_chart_workbook:
        chart_workbooks.add(configured_chart_workbook)

    assets: List[DataAssetInfo] = []
    for path in sorted(data_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name.startswith("~$") or path.name.startswith("."):
            continue
        kind, usage = _classify_data_asset(
            path=path,
            project=project,
            chart_workbooks=chart_workbooks,
            table_workbooks=table_workbooks,
        )
        assets.append(
            DataAssetInfo(
                file_name=path.name,
                relative_path=str(path.relative_to(project.project_dir)),
                kind=kind,
                usage=usage,
                is_primary=path.resolve() == project.excel_workbook_path.resolve(),
            )
        )
    return sorted(assets, key=lambda item: (_data_asset_sort_key(item), item.file_name))


def _classify_data_asset(
    path: Path,
    project: ReportProject,
    chart_workbooks: set[str],
    table_workbooks: set[str],
) -> tuple[str, str]:
    """Classify a data-folder file for the template workbench."""
    suffix = path.suffix.lower()
    if path.resolve() == project.excel_workbook_path.resolve():
        return "primary_excel", "主 Excel 底稿"
    if path.name in chart_workbooks:
        return "chart_workbook", "图表底稿"
    if path.name in table_workbooks:
        return "table_workbook", "表格底稿"
    if suffix == ".json":
        return "query_json", "检索 Query / 旧数据源"
    if suffix in {".xlsx", ".xlsm"}:
        return "workbook", "配套 Excel"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "image", "配套图片"
    return "file", "配套文件"


def _data_asset_sort_key(asset: DataAssetInfo) -> int:
    order = {
        "primary_excel": 0,
        "chart_workbook": 1,
        "table_workbook": 2,
        "workbook": 3,
        "query_json": 4,
        "image": 5,
        "file": 6,
    }
    return order.get(asset.kind, 99)


def _build_default_report_config_source(word_path: Path) -> str:
    """Build a minimal report config when only a Word template is uploaded."""
    placeholders = {placeholder: "" for placeholder in _extract_docx_placeholders(word_path)}
    return yaml.safe_dump(
        {"placeholders": placeholders, "sections": []},
        allow_unicode=True,
        sort_keys=False,
    )


def _build_default_ppt_report_config_source(ppt_path: Path) -> str:
    """Build a minimal report config when only a PPT template is uploaded."""
    from reporting.projections.ppt import extract_pptx_placeholders

    placeholders = {
        placeholder: {"type": "static", "value": ""}
        for placeholder in extract_pptx_placeholders(ppt_path)
    }
    return yaml.safe_dump(
        {"placeholders": placeholders, "sections": []},
        allow_unicode=True,
        sort_keys=False,
    )


def _attach_prompt_templates(project_dir: Path, prompt_path: Path) -> None:
    """Attach a newly created prompt template file to project.yaml."""
    project_yaml = project_dir / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    data["prompt_templates"] = str(prompt_path.relative_to(project_dir))
    project_yaml.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _read_report_config(path: Path) -> tuple[Dict[str, Any], str]:
    """Read raw and parsed report YAML for frontend inspection."""
    try:
        source = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(source) or {}
        if not isinstance(parsed, dict):
            parsed = {}
        return parsed, source
    except Exception as exc:
        logger.warning("Failed to read report config summary", path=str(path), error=str(exc))
        return {}, ""


def _read_prompt_templates(path: Path | None) -> str:
    """Read raw Markdown prompt templates when bound to the project."""
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to read prompt templates", path=str(path), error=str(exc))
        return ""



def _extract_docx_placeholders(path: Path) -> List[str]:
    """Extract {{placeholder}} tokens from Word text, including tokens split across runs."""
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    placeholders: List[str] = []
    seen: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            for name in _ordered_docx_xml_names(archive.namelist()):
                if not (name.startswith("word/") and name.endswith(".xml")):
                    continue
                if any(
                    skipped in name
                    for skipped in [
                        "styles",
                        "settings",
                        "numbering",
                        "fontTable",
                        "theme",
                        "webSettings",
                    ]
                ):
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError:
                    continue
                for paragraph in root.iter(f"{word_ns}p"):
                    text = "".join(node.text or "" for node in paragraph.iter(f"{word_ns}t"))
                    for match in re.findall(r"\{\{\s*([^{}]+?)\s*\}\}", text):
                        normalized = match.strip()
                        if normalized and normalized not in seen:
                            placeholders.append(normalized)
                            seen.add(normalized)
        return placeholders
    except Exception as exc:
        logger.warning("Failed to extract docx placeholders", path=str(path), error=str(exc))
        return []


def _ordered_docx_xml_names(names: List[str]) -> List[str]:
    """Return Word XML files in a user-facing reading order."""
    return sorted(names, key=_docx_xml_sort_key)


def _docx_xml_sort_key(name: str) -> tuple[int, str]:
    if name == "word/document.xml":
        return (0, name)
    if name.startswith("word/header"):
        return (1, name)
    if name.startswith("word/footer"):
        return (2, name)
    return (3, name)


def _summarize_excel_workbook(path: Path) -> List[ExcelSheetInfo]:
    """Summarize worksheet names, dimensions, and sample cells from an xlsx package."""
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
            sheets: List[ExcelSheetInfo] = []
            for sheet in workbook.findall(
                ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"
            ):
                sheet_name = sheet.attrib.get("name", "Sheet")
                rel_id = sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                target = rel_map.get(rel_id or "")
                if not target:
                    continue
                sheet_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
                sheet_root = ET.fromstring(archive.read(sheet_path))
                dimension_el = sheet_root.find(
                    ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}dimension"
                )
                dimension = dimension_el.attrib.get("ref", "") if dimension_el is not None else ""
                cells = _read_xlsx_nonempty_cells(sheet_root, shared_strings)
                sample = [f"{address}={str(value)[:60]}" for address, value in cells[:12]]
                sheets.append(
                    ExcelSheetInfo(
                        name=sheet_name,
                        dimension=dimension,
                        nonempty_count=len(cells),
                        sample_cells=sample,
                    )
                )
            return sheets
    except Exception as exc:
        logger.warning("Failed to summarize excel workbook", path=str(path), error=str(exc))
        return []


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    text_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
    return ["".join(node.text or "" for node in item.iter(text_tag)) for item in root]


def _read_xlsx_nonempty_cells(
    sheet_root: ET.Element, shared_strings: List[str]
) -> List[tuple[str, str]]:
    cell_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"
    value_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"
    text_tag = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
    cells: List[tuple[str, str]] = []
    for cell in sheet_root.iter(cell_tag):
        address = cell.attrib.get("r", "")
        value = ""
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            value = "".join(node.text or "" for node in cell.iter(text_tag))
        else:
            value_el = cell.find(value_tag)
            if value_el is not None and value_el.text is not None:
                value = value_el.text
                if cell_type == "s":
                    try:
                        value = shared_strings[int(value)]
                    except (ValueError, IndexError):
                        pass
        if value:
            cells.append((address, value))
    return sorted(cells, key=lambda item: _xlsx_cell_sort_key(item[0]))


def _xlsx_cell_sort_key(address: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", address)
    if not match:
        return (10**9, 10**9)
    col = 0
    for char in match.group(1):
        col = col * 26 + ord(char) - 64
    return (int(match.group(2)), col)


def _to_generated_report_info(path: Path) -> GeneratedReportInfo:
    stat = path.stat()
    return GeneratedReportInfo(
        file_name=path.name,
        file_path=str(path),
        generated_at=datetime.fromtimestamp(stat.st_mtime),
    )


def _docx_to_preview_html(path: Path, asset_base_url: str | None = None) -> str:
    """Convert a generated docx into an inline preview page."""
    word_pdf = _build_word_pdf_preview(path)
    if word_pdf:
        return _word_pdf_preview_html(
            path.name,
            word_pdf,
            source_path=path,
            asset_base_url=asset_base_url,
        )
    quicklook_image = _build_quicklook_preview_image(path)
    if quicklook_image:
        return _quicklook_preview_html(path.name, quicklook_image)
    return _docx_to_fallback_preview_html(path)


def _pptx_preview_placeholder_html(path: Path) -> str:
    """Return a lightweight placeholder preview for generated PPTX files."""
    file_name = escape(path.name)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f7;
      color: #1d1d1f;
    }}
    .ppt-preview-placeholder {{
      min-height: 320px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      text-align: center;
      padding: 48px;
    }}
    .ppt-preview-placeholder strong {{ font-size: 18px; }}
    .ppt-preview-placeholder span {{ color: #6e6e73; }}
  </style>
</head>
<body>
  <main class="ppt-preview-placeholder">
    <strong>{file_name}</strong>
    <span>PPT 已生成，可下载后在 PowerPoint 中查看。页面缩略图预览将在后续版本支持。</span>
  </main>
</body>
</html>"""


def _read_cached_word_pdf_preview(path: Path) -> bytes | None:
    try:
        cache_path = _word_pdf_preview_cache_path(path.resolve(strict=True), engine="word")
        if cache_path.exists():
            return cache_path.read_bytes()
    except Exception as exc:
        logger.warning("Failed to read cached Word PDF preview", path=str(path), error=str(exc))
    return None


def _build_word_pdf_preview(path: Path) -> bytes | None:
    """Build or read a local PDF preview, preferring Microsoft Word fidelity on macOS."""
    try:
        source_path = path.resolve(strict=True)
        word_cache_path = _word_pdf_preview_cache_path(source_path, engine="word")
        if word_cache_path.exists():
            return word_cache_path.read_bytes()

        if _find_microsoft_word_app():
            word_pdf = _export_docx_pdf_with_microsoft_word(source_path, word_cache_path)
            if word_pdf:
                return word_pdf

        soffice = _find_soffice_command()
        if not soffice:
            return None
        soffice_cache_path = _word_pdf_preview_cache_path(source_path, engine="soffice")
        if soffice_cache_path.exists():
            return soffice_cache_path.read_bytes()
        return _export_docx_pdf_with_soffice(source_path, soffice_cache_path, soffice)
    except Exception as exc:
        logger.warning("Local PDF preview unavailable", path=str(path), error=str(exc))
        return None


def _find_microsoft_word_app() -> Path | None:
    if sys.platform != "darwin" or os.environ.get("ALPHAFOUNDRY_DISABLE_WORD_PREVIEW") == "1":
        return None
    app_path = Path("/Applications/Microsoft Word.app")
    return app_path if app_path.exists() else None


def _export_docx_pdf_with_microsoft_word(source_path: Path, cache_path: Path) -> bytes | None:
    """Export a DOCX to PDF with Microsoft Word for faithful preview pagination."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists():
            cache_path.unlink()

        script = f"""
set inputPath to {_applescript_string(str(source_path))}
set outputPath to {_applescript_string(str(cache_path))}
set openedDoc to missing value
set openedByPreview to false
tell application id "com.microsoft.Word"
    set oldAlerts to display alerts
    try
        set display alerts to alerts none
        repeat with documentIndex from 1 to (count of documents)
            try
                set existingDoc to document documentIndex
                if (full name of existingDoc as text) is inputPath then
                    set openedDoc to existingDoc
                    exit repeat
                end if
            end try
        end repeat
        if openedDoc is missing value then
            open file name inputPath
            set openedDoc to active document
            set openedByPreview to true
        end if
        save as openedDoc file name outputPath file format format PDF
        if openedByPreview then close openedDoc saving no
        set display alerts to oldAlerts
    on error errMsg number errNum
        if openedByPreview and openedDoc is not missing value then
            try
                close openedDoc saving no
            end try
        end if
        set display alerts to oldAlerts
        error errMsg number errNum
    end try
end tell
"""
        result = subprocess.run(
            ["osascript"],
            input=script,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            logger.warning(
                "Microsoft Word PDF preview failed",
                path=str(source_path),
                returncode=result.returncode,
                stderr=result.stderr[-1000:],
            )
            return None
        if not cache_path.exists():
            logger.warning("Microsoft Word PDF preview produced no file", path=str(source_path))
            return None
        return cache_path.read_bytes()
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "Microsoft Word PDF preview timed out", path=str(source_path), timeout=exc.timeout
        )
    except Exception as exc:
        logger.warning(
            "Microsoft Word PDF preview unavailable", path=str(source_path), error=str(exc)
        )
    return None


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _find_soffice_command() -> str | None:
    env_path = os.environ.get("ALPHAFOUNDRY_SOFFICE")
    candidates = [
        env_path,
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _export_docx_pdf_with_soffice(
    source_path: Path, cache_path: Path, soffice: str
) -> bytes | None:
    try:
        with tempfile.TemporaryDirectory(prefix="alphafoundry-soffice-preview-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            profile_dir = tmp_path / "profile"
            output_dir = tmp_path / "output"
            profile_dir.mkdir()
            output_dir.mkdir()
            preview_source_path = _prepare_docx_for_soffice_preview(source_path, tmp_path)
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--invisible",
                    "--nodefault",
                    "--nolockcheck",
                    "--nologo",
                    "--nofirststartwizard",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    str(output_dir),
                    str(preview_source_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.warning(
                    "LibreOffice PDF preview failed",
                    path=str(source_path),
                    returncode=result.returncode,
                    stderr=result.stderr[-1000:],
                )
                return None
            pdf_path = output_dir / f"{preview_source_path.stem}.pdf"
            if not pdf_path.exists():
                previews = sorted(output_dir.glob("*.pdf"))
                if not previews:
                    logger.warning(
                        "LibreOffice PDF preview produced no file", path=str(source_path)
                    )
                    return None
                pdf_path = previews[0]
            pdf_bytes = pdf_path.read_bytes()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(pdf_bytes)
            return pdf_bytes
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "LibreOffice PDF preview timed out", path=str(source_path), timeout=exc.timeout
        )
    except Exception as exc:
        logger.warning("LibreOffice PDF preview unavailable", path=str(source_path), error=str(exc))
    return None


def _prepare_docx_for_soffice_preview(source_path: Path, tmp_path: Path) -> Path:
    """Return a DOCX copy whose floating charts are stable for LibreOffice preview export."""
    normalized_path = tmp_path / source_path.name
    try:
        changed = _write_docx_with_inline_preview_charts(source_path, normalized_path)
        return normalized_path if changed else source_path
    except Exception as exc:
        logger.warning(
            "Failed to normalize Word preview chart layout",
            path=str(source_path),
            error=str(exc),
        )
        return source_path


def _write_docx_with_inline_preview_charts(source_path: Path, normalized_path: Path) -> bool:
    """Write a preview-only docx copy with anchored chart drawings moved below captions."""
    with zipfile.ZipFile(source_path, "r") as source:
        entries = {name: source.read(name) for name in source.namelist()}

    document_xml = entries.get("word/document.xml")
    if not document_xml:
        return False

    root = ET.fromstring(document_xml)
    if not _normalize_anchored_charts_for_preview(root):
        return False

    entries["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(normalized_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, content in entries.items():
            target.writestr(name, content)
    return True


def _normalize_anchored_charts_for_preview(root: ET.Element) -> bool:
    """Move Word floating charts after nearby figure captions for LibreOffice preview fidelity."""
    ns = {
        "w": WORD_NS,
        "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    }
    body = root.find("w:body", ns)
    if body is None:
        return False

    children = list(body)
    moved = False
    for paragraph in list(children):
        if not paragraph.tag.endswith("}p"):
            continue
        anchors = [
            anchor
            for anchor in paragraph.findall(".//wp:anchor", ns)
            if anchor.find(".//c:chart", ns) is not None
        ]
        if not anchors:
            continue
        paragraph_index = children.index(paragraph)
        paragraph_text = _word_paragraph_text(paragraph).replace(" ", "")
        if re.match(r"^图[一二三四五六七八九十0-9]+[:：]", paragraph_text):
            caption_index = paragraph_index
        else:
            caption_index = _find_next_figure_caption_index(children, paragraph_index + 1)
        if caption_index is None:
            continue
        insert_at = caption_index + 1
        for anchor in anchors:
            chart_paragraph = _build_inline_chart_preview_paragraph(anchor)
            if _remove_element(paragraph, anchor):
                body.insert(insert_at, chart_paragraph)
                children.insert(insert_at, chart_paragraph)
                insert_at += 1
                moved = True
    return moved


def _find_next_figure_caption_index(children: List[ET.Element], start: int) -> int | None:
    for index in range(start, min(len(children), start + 8)):
        child = children[index]
        if not child.tag.endswith("}p"):
            continue
        text = _word_paragraph_text(child).replace(" ", "")
        if re.match(r"^图[一二三四五六七八九十0-9]+[:：]", text):
            return index
    return None


def _word_paragraph_text(paragraph: ET.Element) -> str:
    text_tag = f"{{{WORD_NS}}}t"
    return "".join(node.text or "" for node in paragraph.iter(text_tag)).strip()


def _build_inline_chart_preview_paragraph(anchor: ET.Element) -> ET.Element:
    inline = ET.Element(f"{{{WP_NS}}}inline")
    for attr in ("distT", "distB", "distL", "distR"):
        if attr in anchor.attrib:
            inline.set(attr, anchor.attrib[attr])
    for local_name in ("extent", "effectExtent", "docPr", "cNvGraphicFramePr"):
        child = anchor.find(f"{{{WP_NS}}}{local_name}")
        if child is not None:
            inline.append(deepcopy(child))
    graphic = anchor.find(f"{{{DRAWING_NS}}}graphic")
    if graphic is not None:
        inline.append(deepcopy(graphic))

    paragraph = ET.Element(f"{{{WORD_NS}}}p")
    paragraph_properties = ET.SubElement(paragraph, f"{{{WORD_NS}}}pPr")
    ET.SubElement(
        paragraph_properties,
        f"{{{WORD_NS}}}jc",
        {f"{{{WORD_NS}}}val": "center"},
    )
    run = ET.SubElement(paragraph, f"{{{WORD_NS}}}r")
    drawing = ET.SubElement(run, f"{{{WORD_NS}}}drawing")
    drawing.append(inline)
    return paragraph


def _remove_element(root: ET.Element, target: ET.Element) -> bool:
    for parent in root.iter():
        for child in list(parent):
            if child is target:
                parent.remove(child)
                return True
    return False


def _word_pdf_preview_cache_path(path: Path, engine: str = "word") -> Path:
    stat = path.stat()
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "report"
    cache_dir = path.parent / ".preview-cache"
    safe_engine = re.sub(r"[^A-Za-z0-9_.-]+", "_", engine).strip("._") or "preview"
    return (
        cache_dir
        / f"{safe_stem}-{WORD_PREVIEW_LAYOUT_VERSION}-{safe_engine}-{stat.st_mtime_ns}-{stat.st_size}.pdf"
    )


def _word_preview_page_asset_dir(path: Path) -> Path:
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "report"
    return path.parent / ".preview-cache" / f"{safe_stem}-{WORD_PREVIEW_LAYOUT_VERSION}-pages"


def _word_pdf_preview_html(
    file_name: str,
    pdf_bytes: bytes,
    source_path: Path | None = None,
    asset_base_url: str | None = None,
) -> str:
    if source_path is not None and asset_base_url:
        pages = _render_pdf_preview_page_assets(pdf_bytes, source_path, asset_base_url)
        if pages:
            return _word_page_preview_html(file_name, pages)

    pages = _render_pdf_preview_pages(pdf_bytes)
    if pages:
        return _word_page_preview_html(file_name, pages)

    escaped_name = escape(file_name)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1224" height="1584" viewBox="0 0 1224 1584">'
        '<rect width="1224" height="1584" fill="#fff"/>'
        '<text x="612" y="742" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Arial" '
        'font-size="38" font-weight="700" fill="#1d1d1f">PDF 预览暂不可用</text>'
        '<text x="612" y="804" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Arial" '
        f'font-size="24" fill="#6e6e73">{escaped_name}</text>'
        "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return _word_page_preview_html(
        file_name,
        [
            {
                "src": f"data:image/svg+xml;base64,{encoded}",
                "width": 1224,
                "height": 1584,
                "label": "PDF 预览暂不可用",
            }
        ],
        source_label="PDF 渲染暂不可用",
    )


def _render_pdf_preview_page_assets(
    pdf_bytes: bytes,
    source_path: Path,
    asset_base_url: str,
) -> List[Dict[str, Any]]:
    """Render PDF pages into cached PNG files and return lazy-loadable page URLs."""
    try:
        stat = source_path.stat()
        asset_dir = _word_preview_page_asset_dir(source_path)
        manifest_path = asset_dir / "manifest.json"
        cache_signature = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "version": WORD_PREVIEW_LAYOUT_VERSION,
            "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        }
        asset_version = str(cache_signature["pdf_sha256"])[:16]
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cached_pages = (
                manifest.get("pages") if manifest.get("source") == cache_signature else None
            )
            if isinstance(cached_pages, list) and all(
                (asset_dir / str(page.get("asset", ""))).exists() for page in cached_pages
            ):
                return [
                    {
                        "src": f"{asset_base_url}/{page['asset']}?v={asset_version}",
                        "width": int(page["width"]),
                        "height": int(page["height"]),
                        "label": str(page.get("label") or f"第 {index + 1} 页"),
                    }
                    for index, page in enumerate(cached_pages)
                ]

        import pypdfium2 as pdfium

        asset_dir.mkdir(parents=True, exist_ok=True)
        for stale_page in asset_dir.glob("page-*.png"):
            stale_page.unlink()

        document = pdfium.PdfDocument(pdf_bytes)
        pages: List[Dict[str, Any]] = []
        manifest_pages: List[Dict[str, Any]] = []
        try:
            for index in range(len(document)):
                page = document[index]
                try:
                    image = page.render(scale=2.0).to_pil()
                    asset_name = f"page-{index + 1:03d}.png"
                    image.save(asset_dir / asset_name, format="PNG", optimize=True)
                    label = f"第 {index + 1} 页"
                    page_info = {
                        "src": f"{asset_base_url}/{asset_name}?v={asset_version}",
                        "width": image.width,
                        "height": image.height,
                        "label": label,
                    }
                    pages.append(page_info)
                    manifest_pages.append(
                        {
                            "asset": asset_name,
                            "width": image.width,
                            "height": image.height,
                            "label": label,
                        }
                    )
                finally:
                    close_page = getattr(page, "close", None)
                    if callable(close_page):
                        close_page()
        finally:
            close_document = getattr(document, "close", None)
            if callable(close_document):
                close_document()

        manifest_path.write_text(
            json.dumps({"source": cache_signature, "pages": manifest_pages}, ensure_ascii=False),
            encoding="utf-8",
        )
        return pages
    except Exception as exc:
        logger.warning("Failed to render Word PDF preview page assets", error=str(exc))
        return []


def _render_pdf_preview_pages(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(pdf_bytes)
        pages: List[Dict[str, Any]] = []
        try:
            for index in range(len(document)):
                page = document[index]
                try:
                    image = page.render(scale=2.0).to_pil()
                    output = io.BytesIO()
                    image.save(output, format="PNG", optimize=True)
                    encoded = base64.b64encode(output.getvalue()).decode("ascii")
                    pages.append(
                        {
                            "src": f"data:image/png;base64,{encoded}",
                            "width": image.width,
                            "height": image.height,
                            "label": f"第 {index + 1} 页",
                        }
                    )
                finally:
                    close_page = getattr(page, "close", None)
                    if callable(close_page):
                        close_page()
        finally:
            close_document = getattr(document, "close", None)
            if callable(close_document):
                close_document()
        return pages
    except Exception as exc:
        logger.warning("Failed to render Word PDF preview pages", error=str(exc))
        return []


def _word_page_preview_html(
    file_name: str,
    pages: List[Dict[str, Any]],
    source_label: str = "",
) -> str:
    escaped_name = escape(file_name)
    page_items = []
    thumbnail_items = []
    placeholder_svg = "data:image/svg+xml;base64," + base64.b64encode(
        b"<svg xmlns='http://www.w3.org/2000/svg' width='24' height='32'></svg>"
    ).decode("ascii")
    for index, page in enumerate(pages, start=1):
        src = escape(str(page.get("src", "")), quote=True)
        width = int(page.get("width") or 1)
        height = int(page.get("height") or 1)
        label = escape(str(page.get("label") or f"第 {index} 页"))
        image_class = escape(str(page.get("image_class") or "docx-preview-page-image"))
        lazy_attrs = (
            f'src="{placeholder_svg}" data-src="{src}"'
            if not src.startswith("data:")
            else f'src="{src}"'
        )
        page_items.append(
            '<figure class="docx-preview-page" '
            f'data-page-index="{index}" data-page-width="{width}" data-page-height="{height}" aria-label="{label}">'
            f'<img class="{image_class}" {lazy_attrs} width="{width}" height="{height}" '
            f'alt="{label}" loading="lazy" decoding="async">'
            "</figure>"
        )
        thumb_attrs = (
            f'src="{placeholder_svg}" data-src="{src}"'
            if not src.startswith("data:")
            else f'src="{src}"'
        )
        thumbnail_items.append(
            '<button class="docx-preview-thumbnail" type="button" '
            f'data-preview-thumbnail="{index}" aria-label="跳转到第 {index} 页">'
            f'<img {thumb_attrs} width="{width}" height="{height}" alt="第 {index} 页缩略图" '
            'loading="lazy" decoding="async">'
            f"<span>{index}</span>"
            "</button>"
        )
    page_count = len(pages)
    double_button_disabled = page_count < 2
    double_button_state = ' aria-disabled="true" disabled' if double_button_disabled else ""
    double_button_title = "双页（需要至少两页）" if double_button_disabled else "双页"
    default_layout = "single" if double_button_disabled else "double"
    storage_key = json.dumps(f"alphafoundry.wordPreview.{file_name}", ensure_ascii=False)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{escaped_name}</title>"
        "<script>(function(){"
        "function apply(theme,scheme){document.documentElement.setAttribute('data-theme',theme||'dark');"
        "document.documentElement.setAttribute('data-color-scheme',scheme||'claude');}"
        "function localTheme(){try{return{theme:localStorage.getItem('af-theme'),scheme:localStorage.getItem('af-color-scheme')}}"
        "catch(error){return{theme:null,scheme:null}}}"
        "function parentTheme(){try{if(window.parent&&window.parent!==window&&window.parent.document){"
        "var parentRoot=parent.document.documentElement;"
        "return{theme:parentRoot.getAttribute('data-theme'),scheme:parentRoot.getAttribute('data-color-scheme')}}}"
        "catch(error){}return{theme:null,scheme:null}}"
        "function syncTheme(){var fallback=localTheme();var upstream=parentTheme();"
        "apply(upstream.theme||fallback.theme,upstream.scheme||fallback.scheme);}"
        "syncTheme();"
        "try{if(window.parent&&window.parent!==window&&window.parent.document){"
        "new MutationObserver(syncTheme).observe(parent.document.documentElement,"
        "{attributes:true,attributeFilter:['data-theme','data-color-scheme']});}}catch(error){}"
        "window.addEventListener('storage',function(event){if(event.key==='af-theme'||event.key==='af-color-scheme')syncTheme();});"
        "window.addEventListener('message',function(event){var data=event.data||{};"
        "if(data.type==='alphafoundry-theme')apply(data.theme,data.scheme);});"
        "})();</script>"
        "<style>"
        ":root{color-scheme:light dark;--accent:#d97706;--accent-hover:#b45309;--accent-light:#fff8e1;"
        "--preview-accent:var(--accent);--preview-accent-fg:#fff;"
        "--preview-page-bg:#e9e9ee;--preview-text:#1d1d1f;--preview-muted:#6e6e73;"
        "--preview-toolbar-bg:rgba(255,255,255,.94);--preview-toolbar-border:rgba(0,0,0,.08);"
        "--preview-control-bg:#f5f5f7;--preview-control-hover:#fff;--preview-control-fg:#1d1d1f;"
        "--preview-control-muted:#6e6e73;--preview-control-border:rgba(0,0,0,.12);"
        "--preview-control-active-bg:#1d1d1f;--preview-control-active-fg:#fff;"
        "--preview-focus:color-mix(in srgb,var(--preview-accent) 32%,transparent);"
        "--preview-stage-bg:#e2e2e8;--preview-sidebar-bg:rgba(246,246,248,.96);"
        "--preview-status-bg:rgba(255,255,255,.92);--preview-layout-bg:rgba(0,0,0,.055);"
        "--preview-layout-hover:rgba(255,255,255,.55);--preview-layout-active-bg:#fff;"
        "--preview-layout-active-fg:#1d1d1f;}"
        '[data-color-scheme="vscode"]{--accent:#007acc;--accent-hover:#0098ff;--accent-light:#ddf4ff;}'
        '[data-color-scheme="github"]{--accent:#1a7f37;--accent-hover:#2ea043;--accent-light:#dafbe1;}'
        '[data-color-scheme="openclaw"]{--accent:#cf222e;--accent-hover:#a40e26;--accent-light:#ffebe9;}'
        '[data-color-scheme="claude"]{--accent:#d97706;--accent-hover:#b45309;--accent-light:#fff8e1;}'
        '[data-color-scheme="obsidian"]{--accent:#7c3aed;--accent-hover:#6d28d9;--accent-light:#ede9fe;}'
        '[data-theme="dark"][data-color-scheme="vscode"]{--accent:#007acc;--accent-hover:#0098ff;--accent-light:#1e3a5f;}'
        '[data-theme="dark"][data-color-scheme="github"]{--accent:#3fb950;--accent-hover:#2ea043;--accent-light:#1a2e1a;}'
        '[data-theme="dark"][data-color-scheme="openclaw"]{--accent:#f85149;--accent-hover:#ff6b6b;--accent-light:#2e1a1a;}'
        '[data-theme="dark"][data-color-scheme="claude"]{--accent:#f59e0b;--accent-hover:#fbbf24;--accent-light:#2e2a1a;}'
        '[data-theme="dark"][data-color-scheme="obsidian"]{--accent:#a78bfa;--accent-hover:#c4b5fd;--accent-light:#2e2a3a;}'
        "html,body{margin:0;width:100%;height:100%;overflow:hidden;background:var(--preview-page-bg);color:var(--preview-text);"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;}"
        ".docx-word-page-preview{height:100vh;display:grid;grid-template-columns:0 minmax(0,1fr);"
        "grid-template-rows:46px minmax(0,1fr);--preview-zoom:.48;}"
        ".docx-word-page-preview[data-thumbnails='open']{grid-template-columns:152px minmax(0,1fr);}"
        ".docx-preview-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;"
        "grid-column:1/-1;height:46px;padding:0 14px;background:var(--preview-toolbar-bg);"
        "border-bottom:1px solid var(--preview-toolbar-border);"
        "position:sticky;top:0;z-index:5;box-sizing:border-box;}"
        ".docx-preview-toolbar-left,.docx-preview-toolbar-center,.docx-preview-toolbar-right{display:flex;align-items:center;gap:6px;}"
        ".docx-preview-button{appearance:none;border:1px solid var(--preview-control-border);"
        "background:var(--preview-control-bg);color:var(--preview-control-fg);"
        "height:28px;min-width:30px;border-radius:8px;font:600 13px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "display:inline-flex;align-items:center;justify-content:center;cursor:pointer;}"
        ".docx-preview-button:hover{background:var(--preview-control-hover);}"
        ".docx-preview-button[aria-pressed='true']{background:var(--preview-control-active-bg);"
        "color:var(--preview-control-active-fg);border-color:var(--preview-control-active-bg);}"
        ".docx-preview-button[data-preview-thumbnails-toggle][aria-pressed='true']{"
        "background:var(--preview-accent);color:var(--preview-accent-fg);border-color:var(--preview-accent);}"
        ".docx-preview-button:disabled{opacity:.45;cursor:default;}"
        ".docx-preview-tool-button{width:32px;min-width:32px;height:30px;border-radius:9px;padding:0;}"
        ".docx-preview-tool-icon{position:relative;display:inline-block;width:17px;height:17px;color:currentColor;}"
        ".docx-preview-tool-icon::before,.docx-preview-tool-icon::after{content:'';position:absolute;box-sizing:border-box;}"
        ".docx-preview-icon-sidebar{width:18px;height:16px;border:1.7px solid currentColor;border-radius:3px;}"
        ".docx-preview-icon-sidebar::before{left:4px;top:1px;width:1.7px;height:12px;background:currentColor;border-radius:1px;}"
        ".docx-preview-icon-sidebar::after{left:8px;top:4px;width:6px;height:1.7px;background:currentColor;border-radius:1px;"
        "box-shadow:0 3.5px 0 currentColor,0 7px 0 currentColor;}"
        ".docx-preview-icon-minus::before{left:3px;right:3px;top:8px;height:1.8px;background:currentColor;border-radius:2px;}"
        ".docx-preview-icon-plus::before{left:3px;right:3px;top:8px;height:1.8px;background:currentColor;border-radius:2px;}"
        ".docx-preview-icon-plus::after{top:3px;bottom:3px;left:8px;width:1.8px;background:currentColor;border-radius:2px;}"
        ".docx-preview-icon-fit-width::before{left:2px;top:4px;width:13px;height:9px;border:1.6px solid currentColor;border-radius:2px;}"
        ".docx-preview-icon-fit-width::after{left:0;top:7px;width:17px;height:3px;border-left:1.8px solid currentColor;"
        "border-right:1.8px solid currentColor;box-shadow:4px 1px 0 -0.2px currentColor,-4px 1px 0 -0.2px currentColor;}"
        ".docx-preview-icon-fit-page::before{left:4px;top:2px;width:9px;height:13px;border:1.6px solid currentColor;border-radius:2px;}"
        ".docx-preview-icon-fit-page::after{left:1px;top:1px;width:15px;height:15px;border-radius:3px;"
        "border:1.7px solid currentColor;clip-path:polygon(0 0,32% 0,32% 12%,12% 12%,12% 32%,0 32%,0 0,68% 0,100% 0,100% 32%,88% 32%,88% 12%,68% 12%,68% 0,100% 68%,100% 100%,68% 100%,68% 88%,88% 88%,88% 68%,100% 68%,32% 100%,0 100%,0 68%,12% 68%,12% 88%,32% 88%,32% 100%);}"
        ".docx-preview-zoom-input{box-sizing:border-box;width:56px;height:28px;text-align:center;border-radius:8px;"
        "border:1px solid var(--preview-control-border);background:var(--preview-control-bg);color:var(--preview-control-muted);"
        "font:600 12px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-variant-numeric:tabular-nums;}"
        ".docx-preview-zoom-input:focus{outline:2px solid var(--preview-focus);outline-offset:1px;"
        "background:var(--preview-control-hover);color:var(--preview-control-fg);}"
        ".docx-preview-page-nav{display:flex;align-items:center;gap:5px;color:var(--preview-muted);font-size:12px;font-weight:600;}"
        ".docx-preview-page-input{box-sizing:border-box;width:42px;height:28px;text-align:center;border-radius:8px;"
        "border:1px solid var(--preview-control-border);background:var(--preview-control-bg);"
        "color:var(--preview-control-fg);font:600 12px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}"
        ".docx-preview-page-range{min-width:48px;text-align:center;color:var(--preview-muted);font-variant-numeric:tabular-nums;}"
        ".docx-preview-layout-switch{height:32px;padding:3px;display:flex;align-items:center;gap:2px;border-radius:10px;"
        "background:var(--preview-layout-bg);border:1px solid var(--preview-toolbar-border);box-sizing:border-box;}"
        ".docx-preview-layout-button{width:34px;height:26px;min-width:34px;border:0;background:transparent;border-radius:8px;}"
        ".docx-preview-layout-button:hover{background:var(--preview-layout-hover);}"
        ".docx-preview-layout-button[aria-pressed='true']{background:var(--preview-layout-active-bg);"
        "color:var(--preview-layout-active-fg);box-shadow:0 1px 3px rgba(0,0,0,.18);}"
        ".docx-preview-layout-icon{position:relative;display:inline-flex;align-items:center;justify-content:center;width:18px;height:16px;}"
        ".docx-preview-layout-icon::before,.docx-preview-layout-icon::after{content:'';display:block;box-sizing:border-box;"
        "width:8px;height:12px;border:1.8px solid currentColor;border-radius:2px;background:transparent;}"
        ".docx-preview-layout-single::after{display:none;}"
        ".docx-preview-layout-double{gap:3px;}"
        ".docx-preview-thumbnails{grid-row:2;grid-column:1;overflow:auto;background:var(--preview-sidebar-bg);"
        "border-right:1px solid var(--preview-toolbar-border);padding:12px 10px;box-sizing:border-box;}"
        ".docx-word-page-preview:not([data-thumbnails='open']) .docx-preview-thumbnails{display:none;}"
        ".docx-preview-thumbnail{appearance:none;width:100%;border:1px solid transparent;background:transparent;color:var(--preview-muted);"
        "border-radius:8px;padding:6px 4px;margin:0 0 10px;display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;"
        "font:600 11px/1 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}"
        ".docx-preview-thumbnail img{display:block;width:88px;height:auto;background:#fff;box-shadow:0 5px 16px rgba(0,0,0,.16);}"
        ".docx-preview-thumbnail[aria-current='page']{"
        "background:color-mix(in srgb,var(--preview-accent) 12%,transparent);"
        "border-color:color-mix(in srgb,var(--preview-accent) 32%,transparent);color:var(--preview-accent);}"
        ".docx-preview-stage{grid-row:2;grid-column:2;overflow:auto;background:var(--preview-stage-bg);height:100%;}"
        ".docx-preview-status{position:fixed;right:16px;bottom:16px;z-index:8;padding:7px 12px;border-radius:999px;"
        "background:var(--preview-status-bg);box-shadow:0 10px 28px rgba(0,0,0,.16);"
        "font-size:12px;font-weight:600;color:var(--preview-muted);}"
        ".docx-preview-status[hidden]{display:none;}"
        ".docx-preview-pages{box-sizing:border-box;min-height:100%;display:grid;grid-template-columns:max-content;"
        "gap:22px;align-content:start;justify-content:center;padding:24px;}"
        ".docx-word-page-preview[data-layout='double'] .docx-preview-pages{grid-template-columns:repeat(2,max-content);}"
        ".docx-preview-page{margin:0;background:#fff;box-shadow:0 18px 46px rgba(0,0,0,.18);}"
        ".docx-preview-page img{display:block;width:100%;height:auto;}"
        ".docx-native-preview-fit-page{display:block;max-width:100%;max-height:calc(100vh - 76px);"
        "width:auto;height:auto;object-fit:contain;object-position:center center;}"
        "@media(max-width:1100px){.docx-preview-toolbar{gap:8px;}}"
        "@media(max-width:900px){.docx-word-page-preview,.docx-word-page-preview[data-thumbnails='open']{grid-template-columns:0 minmax(0,1fr);}"
        ".docx-preview-thumbnails{display:none!important;}.docx-preview-pages{padding:14px;gap:14px;}"
        ".docx-word-page-preview[data-layout='double'] .docx-preview-pages{grid-template-columns:max-content;}}"
        "@media(prefers-color-scheme:dark){:root{--preview-page-bg:#1f1f23;--preview-text:#f5f5f7;"
        "--preview-muted:#a1a1aa;--preview-toolbar-bg:rgba(42,42,46,.96);"
        "--preview-toolbar-border:rgba(255,255,255,.1);--preview-control-bg:#34343a;"
        "--preview-control-hover:#3f3f46;--preview-control-fg:#f5f5f7;--preview-control-muted:#a1a1aa;"
        "--preview-control-border:rgba(255,255,255,.14);--preview-control-active-bg:#f5f5f7;"
        "--preview-control-active-fg:#1d1d1f;--preview-focus:color-mix(in srgb,var(--preview-accent) 42%,transparent);"
        "--preview-stage-bg:#202024;--preview-sidebar-bg:rgba(32,32,36,.96);"
        "--preview-status-bg:rgba(42,42,46,.94);--preview-layout-bg:rgba(255,255,255,.07);"
        "--preview-layout-hover:rgba(255,255,255,.08);--preview-layout-active-bg:#f5f5f7;"
        "--preview-layout-active-fg:#1d1d1f;}}"
        "</style></head><body>"
        f'<main class="docx-word-page-preview" data-layout="{default_layout}" data-thumbnails="open" '
        f"data-preview-page-count=\"{page_count}\" data-preview-storage-key='{storage_key}'>"
        '<div class="docx-preview-toolbar">'
        '<div class="docx-preview-toolbar-left">'
        '<button class="docx-preview-button docx-preview-tool-button" type="button" title="缩略图" aria-label="缩略图" '
        'aria-pressed="true" data-preview-thumbnails-toggle>'
        '<span class="docx-preview-tool-icon docx-preview-icon-sidebar" aria-hidden="true"></span>'
        "</button>"
        '<button class="docx-preview-button docx-preview-tool-button" type="button" title="缩小" aria-label="缩小" data-preview-zoom-out>'
        '<span class="docx-preview-tool-icon docx-preview-icon-minus" aria-hidden="true"></span>'
        "</button>"
        '<input class="docx-preview-zoom-input" type="text" inputmode="numeric" pattern="[0-9]*" '
        'value="48%" title="缩放百分比" aria-label="缩放百分比" data-preview-zoom-input>'
        '<button class="docx-preview-button docx-preview-tool-button" type="button" title="放大" aria-label="放大" data-preview-zoom-in>'
        '<span class="docx-preview-tool-icon docx-preview-icon-plus" aria-hidden="true"></span>'
        "</button>"
        '<button class="docx-preview-button docx-preview-tool-button" type="button" title="适合宽度" aria-label="适合宽度" data-preview-fit-width>'
        '<span class="docx-preview-tool-icon docx-preview-icon-fit-width" aria-hidden="true"></span>'
        "</button>"
        '<button class="docx-preview-button docx-preview-tool-button" type="button" title="适合整页" aria-label="适合整页" data-preview-fit-page>'
        '<span class="docx-preview-tool-icon docx-preview-icon-fit-page" aria-hidden="true"></span>'
        "</button>"
        "</div>"
        '<div class="docx-preview-toolbar-center">'
        '<div class="docx-preview-page-nav">'
        '<input class="docx-preview-page-input" type="text" inputmode="numeric" aria-label="页码" '
        'value="1" data-preview-page-input>'
        "<span>/</span>"
        f"<span data-preview-page-total>{page_count}</span>"
        '<span class="docx-preview-page-range" data-preview-page-range>1</span>'
        "</div>"
        "</div>"
        '<div class="docx-preview-toolbar-right">'
        '<div class="docx-preview-layout-switch" role="group" aria-label="页面布局">'
        '<button class="docx-preview-button docx-preview-layout-button" type="button" title="单页" aria-label="单页" '
        f"aria-pressed=\"{str(default_layout == 'single').lower()}\" data-preview-layout=\"single\">"
        '<span class="docx-preview-layout-icon docx-preview-layout-single" aria-hidden="true"></span>'
        "</button>"
        f'<button class="docx-preview-button docx-preview-layout-button" type="button" title="{double_button_title}" '
        f"aria-label=\"双页\" aria-pressed=\"{str(default_layout == 'double').lower()}\"{double_button_state} data-preview-layout=\"double\">"
        '<span class="docx-preview-layout-icon docx-preview-layout-double" aria-hidden="true"></span>'
        "</button>"
        "</div>"
        "</div>"
        "</div>"
        '<aside class="docx-preview-thumbnails" data-preview-thumbnails>'
        f"{''.join(thumbnail_items)}"
        "</aside>"
        '<section class="docx-preview-stage" data-preview-stage>'
        '<div class="docx-preview-status" data-preview-loading>正在载入预览</div>'
        '<div class="docx-preview-status" data-preview-error hidden>部分页面载入失败</div>'
        '<div class="docx-preview-pages" data-preview-pages>'
        f"{''.join(page_items)}"
        "</div>"
        "</section>"
        "</main>"
        "<script>"
        "(()=>{"
        "const root=document.querySelector('.docx-word-page-preview');"
        "const stage=document.querySelector('[data-preview-stage]');"
        "const pages=[...document.querySelectorAll('.docx-preview-page')];"
        "const images=[...document.querySelectorAll('img')];"
        "const zoomInput=document.querySelector('[data-preview-zoom-input]');"
        "const pageInput=document.querySelector('[data-preview-page-input]');"
        "const pageRange=document.querySelector('[data-preview-page-range]');"
        "const loading=document.querySelector('[data-preview-loading]');"
        "const error=document.querySelector('[data-preview-error]');"
        "const storageKey=root?.dataset.previewStorageKey||'alphafoundry.wordPreview';"
        "let currentPage=1;"
        "let zoom=.48;"
        "const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));"
        "function saveState(){try{localStorage.setItem(storageKey,JSON.stringify({zoom,layout:root.dataset.layout,thumbnails:root.dataset.thumbnails}));}catch(_){}}"
        "function restoreState(){try{const saved=JSON.parse(localStorage.getItem(storageKey)||'{}');"
        "if(Number.isFinite(saved.zoom))zoom=clamp(saved.zoom,.18,2.4);"
        "}catch(_){}}"
        "function applyZoom(){"
        "pages.forEach(page=>{const width=Number(page.dataset.pageWidth||1);page.style.width=Math.round(width*zoom)+'px';});"
        "if(zoomInput)zoomInput.value=Math.round(zoom*100)+'%';"
        "saveState();updatePageDisplay();"
        "}"
        "function parseZoomInput(){"
        "if(!zoomInput)return;"
        "const raw=zoomInput.value.trim().replace('%','');"
        "const next=Number(raw);"
        "if(!Number.isFinite(next)||next<=0){applyZoom();return;}"
        "zoom=clamp(next/100,.18,2.4);"
        "applyZoom();"
        "}"
        "function fitWidth(){"
        "const first=pages[0];if(!first||!stage)return;"
        "const width=Number(first.dataset.pageWidth||1);"
        "const doubleMode=root.dataset.layout==='double'&&stage.clientWidth>900;"
        "const availableWidth=stage.clientWidth-(doubleMode?92:48);"
        "const pageWidth=doubleMode?(width*2+22):width;"
        "zoom=clamp(availableWidth/pageWidth,.18,2.4);applyZoom();"
        "}"
        "function fitPage(){"
        "const first=pages[0];if(!first||!stage)return;"
        "const width=Number(first.dataset.pageWidth||1);const height=Number(first.dataset.pageHeight||1);"
        "const doubleMode=root.dataset.layout==='double'&&stage.clientWidth>900;"
        "const availableWidth=stage.clientWidth-(doubleMode?92:48);"
        "const availableHeight=stage.clientHeight-48;"
        "const pageWidth=doubleMode?(width*2+22):width;"
        "zoom=clamp(Math.min(availableWidth/pageWidth,availableHeight/height),.18,1.6);"
        "applyZoom();"
        "}"
        "function pageFromScroll(){if(!stage||!pages.length)return 1;"
        "const stageBox=stage.getBoundingClientRect();const anchor=stageBox.top+Math.min(stageBox.height*.18,90);"
        "let best=pages[0];let bestDistance=Infinity;"
        "pages.forEach(page=>{const box=page.getBoundingClientRect();const distance=Math.abs(box.top-anchor);if(distance<bestDistance){bestDistance=distance;best=page;}});"
        "return Number(best.dataset.pageIndex||1);}"
        "function updatePageDisplay(){currentPage=pageFromScroll();"
        "const doubleMode=root.dataset.layout==='double'&&stage.clientWidth>900;"
        "const end=doubleMode?Math.min(currentPage+1,pages.length):currentPage;"
        "if(pageInput)pageInput.value=String(currentPage);"
        "if(pageRange)pageRange.textContent=doubleMode&&end!==currentPage?currentPage+'-'+end:String(currentPage);"
        "document.querySelectorAll('[data-preview-thumbnail]').forEach(item=>item.setAttribute('aria-current',item.dataset.previewThumbnail==String(currentPage)?'page':'false'));"
        "}"
        "function goToPage(value){const page=pages[clamp(Math.round(Number(value)||1),1,pages.length)-1];if(page&&stage){page.scrollIntoView({block:'start',inline:'center'});setTimeout(updatePageDisplay,80);}}"
        "function parsePageInput(){if(pageInput)goToPage(pageInput.value);}"
        "function loadImage(image){if(image.dataset.src){image.src=image.dataset.src;delete image.dataset.src;}}"
        "function loadThumbnails(){document.querySelectorAll('[data-preview-thumbnails] img').forEach(loadImage);}"
        "if('IntersectionObserver'in window){const imageObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){loadImage(entry.target);imageObserver.unobserve(entry.target);}}),{root:stage,rootMargin:'900px'});images.forEach(image=>imageObserver.observe(image));}else{images.forEach(loadImage);}"
        "let loadedCount=0;images.forEach(image=>{if(image.complete)loadedCount+=1;image.addEventListener('load',()=>{loadedCount+=1;if(loading&&loadedCount>0)loading.hidden=true;});image.addEventListener('error',()=>{if(loading)loading.hidden=true;if(error)error.hidden=false;});});"
        "if(loading&&images.length===0)loading.hidden=true;"
        "if(loading&&loadedCount>0)loading.hidden=true;"
        "restoreState();"
        "document.querySelector('[data-preview-zoom-out]')?.addEventListener('click',()=>{zoom=clamp(zoom-.08,.18,2.4);applyZoom();});"
        "document.querySelector('[data-preview-zoom-in]')?.addEventListener('click',()=>{zoom=clamp(zoom+.08,.18,2.4);applyZoom();});"
        "document.querySelector('[data-preview-fit-width]')?.addEventListener('click',fitWidth);"
        "document.querySelector('[data-preview-fit-page]')?.addEventListener('click',fitPage);"
        "zoomInput?.addEventListener('change',parseZoomInput);"
        "zoomInput?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();parseZoomInput();zoomInput.blur();}});"
        "pageInput?.addEventListener('change',parsePageInput);"
        "pageInput?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();parsePageInput();pageInput.blur();}});"
        "stage?.addEventListener('scroll',()=>requestAnimationFrame(updatePageDisplay),{passive:true});"
        "stage?.addEventListener('wheel',event=>{if(event.metaKey||event.ctrlKey){event.preventDefault();zoom=clamp(zoom+(event.deltaY<0 ? .08 : -.08),.18,2.4);applyZoom();}},{passive:false});"
        "document.querySelector('[data-preview-thumbnails-toggle]')?.addEventListener('click',event=>{const open=root.dataset.thumbnails!=='open';root.dataset.thumbnails=open?'open':'closed';event.currentTarget.setAttribute('aria-pressed',String(open));if(open)loadThumbnails();saveState();setTimeout(updatePageDisplay,50);});"
        "document.querySelectorAll('[data-preview-thumbnail]').forEach(button=>button.addEventListener('click',()=>goToPage(button.dataset.previewThumbnail)));"
        "document.querySelectorAll('[data-preview-layout]').forEach(button=>button.addEventListener('click',()=>{"
        "if(button.disabled)return;"
        "const targetPage=currentPage||pageFromScroll();"
        "root.dataset.layout=button.dataset.previewLayout;"
        "document.querySelectorAll('[data-preview-layout]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));"
        "saveState();fitWidth();setTimeout(()=>goToPage(targetPage),80);"
        "}));"
        "document.querySelectorAll('[data-preview-layout]').forEach(item=>item.setAttribute('aria-pressed',String(item.dataset.previewLayout===root.dataset.layout)));"
        "document.querySelector('[data-preview-thumbnails-toggle]')?.setAttribute('aria-pressed',String(root.dataset.thumbnails==='open'));"
        "if(root.dataset.thumbnails==='open')loadThumbnails();"
        "window.addEventListener('resize',fitWidth);"
        "requestAnimationFrame(()=>{applyZoom();fitWidth();updatePageDisplay();});"
        "})();"
        "</script>"
        "</body></html>"
    )


def _build_quicklook_preview_image(path: Path) -> bytes | None:
    """Render the first Word preview page with macOS Quick Look when available."""
    if sys.platform != "darwin":
        return None
    qlmanage = shutil.which("qlmanage")
    if not qlmanage:
        return None

    try:
        with tempfile.TemporaryDirectory(prefix="alphafoundry-docx-preview-") as tmp_dir:
            result = subprocess.run(
                [qlmanage, "-t", "-s", "2200", "-o", tmp_dir, str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode != 0:
                logger.warning(
                    "Quick Look docx preview failed",
                    path=str(path),
                    returncode=result.returncode,
                    stderr=result.stderr[-1000:],
                )
                return None
            previews = sorted(Path(tmp_dir).glob("*.png"))
            if not previews:
                logger.warning("Quick Look docx preview produced no image", path=str(path))
                return None
            return previews[0].read_bytes()
    except Exception as exc:
        logger.warning("Quick Look docx preview unavailable", path=str(path), error=str(exc))
        return None


def _quicklook_preview_html(file_name: str, image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    width, height = _preview_image_dimensions(image_bytes)
    return _word_page_preview_html(
        file_name,
        [
            {
                "src": f"data:image/png;base64,{encoded}",
                "width": width,
                "height": height,
                "label": "系统缩略预览",
                "image_class": "docx-preview-page-image docx-native-preview-fit-page",
            }
        ],
        source_label="系统缩略预览",
    )


def _preview_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.width, image.height
    except Exception as exc:
        logger.warning("Failed to read preview image dimensions", error=str(exc))
        return 1100, 1556


def _docx_to_fallback_preview_html(path: Path) -> str:
    """Convert a generated docx package into a lightweight HTML preview."""
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    drawing_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as archive:
            document_root = ET.fromstring(archive.read("word/document.xml"))
            try:
                rels_root = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
                rel_map = {
                    str(rel.attrib["Id"]): str(rel.attrib.get("Target", ""))
                    for rel in rels_root.iter(f"{rel_ns}Relationship")
                    if rel.attrib.get("Id")
                }
            except KeyError:
                rel_map = {}
            body = document_root.find(f"{word_ns}body")
            if body is None:
                return '<div class="docx-preview-empty">无法读取 Word 正文</div>'
            parts = [
                '<!doctype html><html><head><meta charset="utf-8">'
                "<title>Word 预览</title>"
                "<style>"
                "html,body{margin:0;min-height:100%;background:#e9e9ee;color:#1d1d1f;"
                "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
                "'Microsoft YaHei',Arial,sans-serif;}"
                ".docx-preview-workspace{box-sizing:border-box;min-height:100vh;padding:32px;"
                "display:flex;justify-content:center;align-items:flex-start;}"
                ".docx-preview-page{box-sizing:border-box;width: 210mm;min-height: 297mm;"
                "padding:23mm 24mm;background:#fff;box-shadow: 0 18px 52px rgba(0,0,0,.18);"
                "font-size:11pt;line-height:1.68;}"
                ".docx-preview-page p{margin:0 0 10pt;}"
                ".docx-preview-page p.caption{margin-top:4pt;color:#6e6e73;font-size:9.5pt;text-align:center;}"
                ".docx-preview-table{width:100%;border-collapse:collapse;margin:12pt 0;font-size:10pt;}"
                ".docx-preview-table td{border:1px solid #d2d2d7;padding:5pt 6pt;vertical-align:top;}"
                ".docx-preview-figure{margin:14pt 0;text-align:center;}"
                ".docx-preview-figure img{max-width:100%;height:auto;}"
                ".docx-preview-figure figcaption{margin-top:6pt;color:#6e6e73;font-size:9.5pt;}"
                ".docx-preview-empty{margin:48px auto;padding:24px;max-width:720px;background:#fff;"
                "border-radius:14px;color:#6e6e73;}"
                "@media(max-width:900px){.docx-preview-workspace{padding:16px;}"
                ".docx-preview-page{width:100%;min-height:calc(100vh - 32px);padding:18mm 14mm;}}"
                '</style></head><body><main class="docx-preview-workspace"><article class="docx-preview-page">'
            ]
            for child in list(body):
                tag = child.tag
                if tag == f"{word_ns}p":
                    parts.append(
                        _preview_paragraph_html(
                            child, archive, rel_map, rel_attr, drawing_ns, word_ns
                        )
                    )
                elif tag == f"{word_ns}tbl":
                    parts.append(_preview_table_html(child, word_ns))
            parts.append("</article></main></body></html>")
            return "".join(part for part in parts if part)
    except Exception as exc:
        logger.warning("Failed to convert docx preview", path=str(path), error=str(exc))
        return f'<div class="docx-preview-empty">预览生成失败：{escape(str(exc))}</div>'


def _preview_paragraph_html(
    paragraph: ET.Element,
    archive: zipfile.ZipFile,
    rel_map: Dict[str, str],
    rel_attr: str,
    drawing_ns: str,
    word_ns: str,
) -> str:
    text = "".join(node.text or "" for node in paragraph.iter(f"{word_ns}t")).strip()
    images = []
    for blip in paragraph.iter(f"{drawing_ns}blip"):
        rel_id = blip.attrib.get(rel_attr)
        target = rel_map.get(rel_id or "")
        if not target:
            continue
        image_path = target if target.startswith("word/") else f"word/{target.lstrip('/')}"
        try:
            image_bytes = archive.read(image_path)
        except KeyError:
            continue
        ext = Path(image_path).suffix.lower().lstrip(".") or "png"
        mime = "jpeg" if ext in {"jpg", "jpeg"} else ext
        encoded = base64.b64encode(image_bytes).decode("ascii")
        images.append(
            f'<img src="data:image/{mime};base64,{encoded}" alt="{escape(text or image_path)}">'
        )
    if images:
        caption = f"<figcaption>{escape(text)}</figcaption>" if text else ""
        return f'<figure class="docx-preview-figure">{"".join(images)}{caption}</figure>'
    if not text:
        return ""
    class_name = "caption" if text.startswith(("图", "数据来源")) else ""
    return f'<p class="{class_name}">{escape(text)}</p>'


def _preview_table_html(table: ET.Element, word_ns: str) -> str:
    rows = []
    for row in table.iter(f"{word_ns}tr"):
        cells = []
        for cell in row.iter(f"{word_ns}tc"):
            text = "".join(node.text or "" for node in cell.iter(f"{word_ns}t")).strip()
            cells.append(f"<td>{escape(text)}</td>")
        if cells:
            rows.append(f"<tr>{''.join(cells)}</tr>")
    if not rows:
        return ""
    return f'<table class="docx-preview-table">{"".join(rows)}</table>'


def _safe_project_slug(project_name: str) -> str:
    slug = project_name.strip()
    if not slug:
        raise HTTPException(status_code=400, detail="Report project name is required")
    if any(part in slug for part in ["/", "\\", ".."]):
        raise HTTPException(status_code=400, detail="Invalid report project name")
    return slug


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid upload file name")
    return name


def _require_suffix(filename: str, allowed_suffixes: List[str], label: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = "、".join(allowed_suffixes)
        raise HTTPException(status_code=400, detail=f"{label} 仅支持 {allowed}")
