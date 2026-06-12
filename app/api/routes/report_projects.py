"""Report project API routes."""
import base64
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.observability import get_logger
from reporting.projects.chart_generation import ReportProjectChartService
from reporting.projects.generation import ReportProjectGenerationService, compute_report_period
from reporting.projects.keyword_profiles import keyword_profiles_for_api
from reporting.projects.project_manager import ReportProject, ReportProjectManager
from reporting.projects.table_generation import build_project_tables

logger = get_logger(__name__)
router = APIRouter(prefix="/api/report-projects", tags=["report-projects"])

report_project_manager = ReportProjectManager()
report_generation_service = ReportProjectGenerationService()
report_chart_service = ReportProjectChartService()


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
    project_dir: str
    word_template_path: str
    word_template_filename: str
    excel_workbook_path: str
    excel_workbook_filename: str
    section_config_path: str
    section_config_filename: str
    prompt_templates_path: str | None = None
    prompt_templates_filename: str | None = None
    data_source_files: List[str] = Field(default_factory=list)
    data_assets: List[DataAssetInfo] = Field(default_factory=list)
    word_placeholders: List[str] = Field(default_factory=list)
    section_config: Dict[str, Any] = Field(default_factory=dict)
    section_config_source: str = ""
    prompt_templates_source: str = ""
    keyword_profiles: Dict[str, Any] = Field(default_factory=dict)
    excel_sheets: List[ExcelSheetInfo] = Field(default_factory=list)
    output_dir: str
    run_log_dir: str
    generated_reports: List[GeneratedReportInfo] = Field(default_factory=list)


class ReportProjectsListResponse(BaseModel):
    """Report projects list response."""

    projects: List[ReportProjectInfo]
    total: int


class RenderReportProjectRequest(BaseModel):
    """Project report render request."""

    placeholders: Dict[str, str] = Field(default_factory=dict)
    generate_from_config: bool = True
    lookback_days: int = Field(default=7, ge=1, le=90)
    report_date: str | None = None


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


@router.get("/", response_model=ReportProjectsListResponse, summary="列出报告项目")
async def list_report_projects():
    """List report projects stored as project folders."""
    try:
        projects = [_to_project_info(project) for project in report_project_manager.list_projects()]
        return ReportProjectsListResponse(projects=projects, total=len(projects))
    except Exception as exc:
        logger.exception("Failed to list report projects")
        raise HTTPException(status_code=500, detail=f"Failed to list report projects: {exc}")


@router.post("/upload", response_model=ReportProjectInfo, summary="上传报告项目包")
async def upload_report_project(
    project_name: str = Form(..., description="报告项目名称"),
    word_template: UploadFile = File(..., description="Word 模板 .docx"),
    excel_workbook: UploadFile = File(..., description="Excel 数据底稿 .xlsx"),
    section_config: UploadFile = File(..., description="Section 配置 .yaml/.yml"),
    prompt_templates: UploadFile | None = File(None, description="Prompt 模板 .md"),
    data_files: List[UploadFile] = File(default_factory=list, description="配套数据文件"),
):
    """Create a report project folder from uploaded project package assets."""
    slug = _safe_project_slug(project_name)
    project_dir = report_project_manager.projects_root / slug
    if project_dir.exists():
        raise HTTPException(status_code=409, detail=f"Report project already exists: {slug}")

    try:
        templates_dir = project_dir / "templates"
        data_dir = project_dir / "data"
        config_dir = project_dir / "config"
        generated_dir = project_dir / "generated"
        runs_dir = project_dir / "runs"
        for directory in [templates_dir, data_dir, config_dir, generated_dir, runs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        _require_suffix(word_template.filename or "", [".docx"], "Word 模板")
        _require_suffix(excel_workbook.filename or "", [".xlsx"], "Excel 数据底稿")
        _require_suffix(section_config.filename or "", [".yaml", ".yml"], "Section 配置")
        if prompt_templates:
            _require_suffix(prompt_templates.filename or "", [".md"], "Prompt 模板")

        word_path = templates_dir / "report_template.docx"
        excel_filename = _safe_filename(excel_workbook.filename or "workbook.xlsx")
        excel_path = data_dir / excel_filename
        section_path = config_dir / "section_config.yaml"

        word_path.write_bytes(await word_template.read())
        excel_path.write_bytes(await excel_workbook.read())
        section_path.write_bytes(await section_config.read())

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
            "active_word_template": "templates/report_template.docx",
            "active_excel_workbook": f"data/{excel_filename}",
            "section_config": "config/section_config.yaml",
            "output_dir": "generated",
            "run_log_dir": "runs",
        }
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
        elif request.source_kind == "section_config":
            target_path = project.section_config_path
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


@router.post("/{slug}/render", response_model=RenderReportProjectResponse, summary="生成报告项目文档")
async def render_report_project(slug: str, request: RenderReportProjectRequest):
    """Render a report project into its own generated directory."""
    try:
        from reporting.projections.word import WordProjection

        project = report_project_manager.get_project(slug)
        section_config, _ = _read_section_config(project.section_config_path)
        prompt_templates_source = _read_prompt_templates(project.prompt_templates_path)
        report_period = compute_report_period(request.report_date)

        if request.generate_from_config:
            generation_result = report_generation_service.generate_placeholders(
                project=project,
                section_config=section_config,
                prompt_templates_source=prompt_templates_source,
                manual_placeholders=request.placeholders,
                lookback_days=request.lookback_days,
                report_date=request.report_date,
            )
            placeholder_map = generation_result.placeholders
            generated_sections = generation_result.sections
            generation_warnings = generation_result.warnings
        else:
            placeholder_map = request.placeholders
            generated_sections = []
            generation_warnings = []

        generated_at = datetime.now()
        timestamp = generated_at.strftime("%Y-%m-%d_%H%M%S")
        safe_project_name = project.name.replace("/", "_").replace(":", "_")
        file_name = f"{timestamp}_{safe_project_name}.docx"
        output_path = project.output_dir / file_name

        tables, table_infos = build_project_tables(
            project=project,
            section_config=section_config,
        )

        projection = WordProjection()
        projection.save_from_template(
            output_path=output_path,
            template_path=project.word_template_path,
            sections=[],
            placeholders=placeholder_map,
            tables=tables,
        )
        chart_infos = report_chart_service.generate_and_embed(
            project=project,
            section_config=section_config,
            docx_path=output_path,
        )

        run_record = {
            "project_name": project.name,
            "slug": project.slug,
            "word_template_path": str(project.word_template_path),
            "excel_workbook_path": str(project.excel_workbook_path),
            "section_config_path": str(project.section_config_path),
            "prompt_templates_path": str(project.prompt_templates_path)
            if project.prompt_templates_path
            else None,
            "data_source_paths": [str(path) for path in project.data_source_paths],
            "output_path": str(output_path),
            "generated_at": generated_at.isoformat(),
            "placeholder_count": len(placeholder_map),
            "manual_placeholder_count": len(request.placeholders),
            "generate_from_config": request.generate_from_config,
            "lookback_days": request.lookback_days,
            "report_period": {
                "start_date": report_period.start_date,
                "end_date": report_period.end_date,
            },
            "generation": {
                "sections": [
                    {
                        "placeholder": section.placeholder,
                        "title": section.title,
                        "prompt_template": section.prompt_template,
                        "retrieval_query": section.retrieval_query,
                        "evidence_count": section.evidence_count,
                        "model_name": section.model_name,
                        "provider": section.provider,
                        "tokens_used": section.tokens_used,
                        "warnings": section.warnings,
                        "retrieval_config": _serialize_retrieval_config(
                            section.retrieval_config
                        ),
                        "evidence": [_serialize_evidence(item) for item in section.evidence],
                    }
                    for section in generated_sections
                ],
                "warnings": generation_warnings,
            },
            "charts": [
                {
                    "chart_id": chart.chart_id,
                    "title": chart.title,
                    "workbook": chart.workbook,
                    "source_chart": chart.source_chart,
                    "replace_kind": chart.replace_kind,
                    "point_count": chart.point_count,
                    "warnings": chart.warnings,
                }
                for chart in chart_infos
            ],
            "tables": table_infos,
        }
        run_path = project.run_log_dir / f"{timestamp}.json"
        run_path.write_text(
            json.dumps(run_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Rendered report project",
            slug=slug,
            output_path=str(output_path),
            run_path=str(run_path),
        )

        chart_warnings = [warning for chart in chart_infos for warning in chart.warnings]
        table_warnings = [warning for table in table_infos for warning in table["warnings"]]

        return RenderReportProjectResponse(
            success=True,
            project_name=project.name,
            slug=project.slug,
            file_name=file_name,
            file_path=str(output_path),
            download_url=f"/api/report-projects/{project.slug}/download/{file_name}",
            preview_url=f"/api/report-projects/{project.slug}/preview/{file_name}",
            run_log_url=f"/api/report-projects/{project.slug}/runs/{run_path.name}",
            generated_at=generated_at,
            generated_placeholder_count=len(placeholder_map),
            evidence_count=sum(section.evidence_count for section in generated_sections),
            warnings=generation_warnings
            + [warning for section in generated_sections for warning in section.warnings]
            + chart_warnings
            + table_warnings,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to render report project", slug=slug)
        raise HTTPException(status_code=500, detail=f"Failed to render report project: {exc}")


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
        return HTMLResponse(
            _docx_to_preview_html(output_path),
            media_type="text/html; charset=utf-8",
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to preview report project file", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to preview report: {exc}")


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

        return FileResponse(
            output_path,
            filename=file_name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Report project not found: {slug}")
    except Exception as exc:
        logger.exception("Failed to download report project file", slug=slug, file_name=file_name)
        raise HTTPException(status_code=500, detail=f"Failed to download report: {exc}")


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


def _to_project_info(project: ReportProject) -> ReportProjectInfo:
    section_config, section_config_source = _read_section_config(project.section_config_path)
    prompt_templates_source = _read_prompt_templates(project.prompt_templates_path)
    return ReportProjectInfo(
        name=project.name,
        slug=project.slug,
        project_dir=str(project.project_dir),
        word_template_path=str(project.word_template_path),
        word_template_filename=project.word_template_path.name,
        excel_workbook_path=str(project.excel_workbook_path),
        excel_workbook_filename=project.excel_workbook_path.name,
        section_config_path=str(project.section_config_path),
        section_config_filename=project.section_config_path.name,
        prompt_templates_path=str(project.prompt_templates_path)
        if project.prompt_templates_path
        else None,
        prompt_templates_filename=project.prompt_templates_path.name
        if project.prompt_templates_path
        else None,
        data_source_files=[path.name for path in project.data_source_paths],
        data_assets=_list_project_data_assets(project, section_config),
        word_placeholders=_extract_docx_placeholders(project.word_template_path),
        section_config=section_config,
        section_config_source=section_config_source,
        prompt_templates_source=prompt_templates_source,
        keyword_profiles=keyword_profiles_for_api(),
        excel_sheets=_summarize_excel_workbook(project.excel_workbook_path),
        output_dir=str(project.output_dir),
        run_log_dir=str(project.run_log_dir),
        generated_reports=[_to_generated_report_info(path) for path in project.generated_reports],
    )


def _list_project_data_assets(
    project: ReportProject, section_config: Dict[str, Any]
) -> List[DataAssetInfo]:
    """Return every file in the project data directory with a user-facing role."""
    data_dir = project.project_dir / "data"
    if not data_dir.exists():
        return []

    config_assets = section_config.get("assets") or {}
    chart_workbooks = {
        str(chart.get("workbook") or "")
        for chart in (section_config.get("charts") or {}).values()
        if isinstance(chart, dict)
    }
    table_workbooks = {
        str(table.get("workbook") or "")
        for table in (section_config.get("tables") or {}).values()
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


def _attach_prompt_templates(project_dir: Path, prompt_path: Path) -> None:
    """Attach a newly created prompt template file to project.yaml."""
    project_yaml = project_dir / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    data["prompt_templates"] = str(prompt_path.relative_to(project_dir))
    project_yaml.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _serialize_retrieval_config(config: Any) -> Dict[str, Any] | None:
    """Serialize retrieval controls into run logs."""
    if config is None:
        return None
    return {
        "mode": config.mode,
        "top_k": config.top_k,
        "candidate_k": config.candidate_k,
        "must_any": config.must_any,
        "exclude": config.exclude,
        "source_types": config.source_types,
        "min_keyword_score": config.min_keyword_score,
        "fusion_method": config.fusion_method,
        "keyword_weight": config.keyword_weight,
        "semantic_weight": config.semantic_weight,
        "rrf_k": config.rrf_k,
        "semantic_candidate_k": config.semantic_candidate_k,
        "rerank_enabled": config.rerank_enabled,
        "rerank_provider": config.rerank_provider,
        "rerank_top_n": config.rerank_top_n,
        "min_rerank_score": config.min_rerank_score,
    }


def _serialize_evidence(evidence: Any) -> Dict[str, Any]:
    """Serialize one evidence snippet into run logs."""
    return {
        "source": evidence.source,
        "title": evidence.title,
        "content": evidence.content,
        "published_at": evidence.published_at,
        "url": evidence.url,
        "keyword_score": evidence.keyword_score,
        "semantic_score": evidence.semantic_score,
        "retrieval_score": evidence.retrieval_score,
        "retrieval_rank": evidence.retrieval_rank,
        "retrieval_method": evidence.retrieval_method,
        "rerank_score": evidence.rerank_score,
        "rerank_rank": evidence.rerank_rank,
        "rerank_reason": evidence.rerank_reason,
        "matched_terms": evidence.matched_terms,
    }


def _read_section_config(path: Path) -> tuple[Dict[str, Any], str]:
    """Read raw and parsed section YAML for frontend inspection."""
    try:
        source = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(source) or {}
        if not isinstance(parsed, dict):
            parsed = {}
        return parsed, source
    except Exception as exc:
        logger.warning("Failed to read section config summary", path=str(path), error=str(exc))
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


def _docx_to_preview_html(path: Path) -> str:
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
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>Word 预览</title></head><body><div class=\"docx-preview-page\">"
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
            parts.append("</div></body></html>")
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
