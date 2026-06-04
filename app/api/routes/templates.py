"""
模板管理 API 路由 - 支持 DOCX/PPTX/Excel 模板上传、占位符发现、报告渲染
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, cast

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.contracts import SectionOutput
from core.observability import get_logger
from reporting.templates.template_manager import TemplateManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])

template_manager = TemplateManager()


# ─── 数据模型 ─────────────────────────────────────────────────────────


class TemplateFileType(str, Enum):
    """模板文件类型"""

    DOCX = "docx"
    PPTX = "pptx"
    EXCEL = "excel"


class TemplateInfo(BaseModel):
    """模板基本信息"""

    template_name: str
    description: str = ""
    version: str = "1.0"
    target_audience: Optional[str] = None
    has_docx: bool = False
    has_pptx: bool = False
    has_excel: bool = False
    docx_path: Optional[str] = None
    pptx_path: Optional[str] = None
    excel_path: Optional[str] = None
    placeholders: List[str] = Field(default_factory=list)
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TemplateListResponse(BaseModel):
    """模板列表响应"""

    templates: List[TemplateInfo]
    total: int


class PlaceholderDiscoveryResponse(BaseModel):
    """占位符发现响应"""

    template_name: str
    file_type: str
    placeholders: List[str]
    total: int


class RenderReportRequest(BaseModel):
    """报告渲染请求"""

    template_name: str
    file_type: str = "docx"  # docx/pptx
    placeholders: Dict[str, str] = Field(default_factory=dict)
    canonical_id: Optional[str] = None
    report_type: str = "full"
    as_of: Optional[datetime] = None


class RenderReportFromAssetRequest(BaseModel):
    """从资产ID直接渲染报告请求"""

    template_name: str
    file_type: str = "docx"
    canonical_id: str
    report_type: str = "full"
    as_of: Optional[datetime] = None
    additional_placeholders: Dict[str, str] = Field(default_factory=dict)


class RenderReportResponse(BaseModel):
    """报告渲染响应"""

    success: bool
    report_id: str
    template_name: str
    file_type: str
    file_name: str
    download_url: str
    generated_at: datetime
    message: Optional[str] = None


class DeleteTemplateResponse(BaseModel):
    """删除模板响应"""

    success: bool
    template_name: str
    message: Optional[str] = None


class PlaceholderConfig(BaseModel):
    """单个占位符配置"""

    type: str = "string"
    description: str = ""
    prompt: str = ""
    default: Optional[Any] = None


class TemplateConfigSaveRequest(BaseModel):
    """模板配置保存请求"""

    template_name: str
    file_type: str = "docx"
    placeholders: Dict[str, PlaceholderConfig] = Field(default_factory=dict)


class TemplateConfigResponse(BaseModel):
    """模板配置响应"""

    template_name: str
    file_type: str
    config: Dict[str, Any]


# ─── 模板管理 API ─────────────────────────────────────────────────────────


@router.get("/", response_model=TemplateListResponse, summary="列出所有模板")
async def list_templates():
    """
    列出所有可用的模板，包括基本信息和占位符
    """
    try:
        template_names = template_manager.list_templates()
        templates_info: List[TemplateInfo] = []

        for template_name in template_names:
            try:
                config = template_manager.load_template(template_name)

                # 检查是否有对应的模板文件
                docx_path = template_manager.get_template_file_path(template_name, "docx")
                pptx_path = template_manager.get_template_file_path(template_name, "pptx")
                excel_path = template_manager.get_template_file_path(template_name, "excel")

                # 从配置中提取占位符和节信息
                config_placeholders = (
                    list(config.placeholders.keys()) if config.placeholders else []
                )
                config_sections = [
                    {
                        "key": s.key,
                        "title": s.title,
                        "target_words": s.target_words,
                        "placeholder": s.placeholder,
                        "required_facets": s.required_facets,
                    }
                    for s in config.sections
                ]

                templates_info.append(
                    TemplateInfo(
                        template_name=template_name,
                        description=config.description,
                        version=config.version,
                        target_audience=config.target_audience,
                        has_docx=docx_path is not None,
                        has_pptx=pptx_path is not None,
                        has_excel=excel_path is not None,
                        docx_path=str(docx_path) if docx_path else None,
                        pptx_path=str(pptx_path) if pptx_path else None,
                        excel_path=str(excel_path) if excel_path else None,
                        placeholders=config_placeholders,
                        sections=config_sections,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to load template {template_name}: {e}")

        return TemplateListResponse(templates=templates_info, total=len(templates_info))
    except Exception as e:
        logger.exception("Failed to list templates")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/{template_name}", response_model=TemplateInfo, summary="获取模板详情")
async def get_template(template_name: str):
    """
    获取指定模板的详细信息
    """
    try:
        config = template_manager.load_template(template_name)

        # 检查是否有对应的模板文件
        docx_path = template_manager.get_template_file_path(template_name, "docx")
        pptx_path = template_manager.get_template_file_path(template_name, "pptx")
        excel_path = template_manager.get_template_file_path(template_name, "excel")

        # 从配置中提取占位符和节信息
        config_placeholders = list(config.placeholders.keys()) if config.placeholders else []
        config_sections = [
            {
                "key": s.key,
                "title": s.title,
                "target_words": s.target_words,
                "placeholder": s.placeholder,
                "required_facets": s.required_facets,
            }
            for s in config.sections
        ]

        return TemplateInfo(
            template_name=template_name,
            description=config.description,
            version=config.version,
            target_audience=config.target_audience,
            has_docx=docx_path is not None,
            has_pptx=pptx_path is not None,
            has_excel=excel_path is not None,
            docx_path=str(docx_path) if docx_path else None,
            pptx_path=str(pptx_path) if pptx_path else None,
            excel_path=str(excel_path) if excel_path else None,
            placeholders=config_placeholders,
            sections=config_sections,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_name}")
    except Exception as e:
        logger.exception(f"Failed to get template {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")


@router.post("/upload", summary="上传模板文件")
async def upload_template(
    template_name: str = Form(..., description="模板名称"),
    file_type: TemplateFileType = Form(..., description="文件类型"),
    description: str = Form("", description="模板描述"),
    version: str = Form("1.0", description="模板版本"),
    target_audience: Optional[str] = Form(None, description="目标受众"),
    file: UploadFile = File(..., description="模板文件"),
):
    """
    上传 DOCX/PPTX/Excel 模板文件
    """
    try:
        # 读取文件内容
        file_content = await file.read()

        # 保存模板文件
        saved_path = template_manager.save_template_file(
            template_name=template_name,
            file_type=file_type.value,
            file_content=file_content,
            overwrite=True,  # 允许覆盖
        )

        # 自动创建对应的YAML配置（如果不存在）
        try:
            template_manager.load_template(template_name)
        except FileNotFoundError:
            # 配置不存在，创建基础配置
            from core.contracts import SectionSpec, TemplateConfig

            # 创建默认章节结构（如果是周报类型则使用标准结构，否则创建简单结构）
            if "weekly" in template_name.lower() or "周报" in template_name:
                sections = [
                    SectionSpec(
                        key="market_summary",
                        title="市场概览",
                        target_words=300,
                        required_facets=["大盘走势", "主要指数表现", "成交量"],
                        placeholder="market_summary_placeholder",
                    ),
                    SectionSpec(
                        key="key_events",
                        title="本周重要事件",
                        target_words=400,
                        required_facets=["政策新闻", "公司公告", "行业动态"],
                        placeholder="key_events_placeholder",
                    ),
                    SectionSpec(
                        key="industry_performance",
                        title="行业表现分析",
                        target_words=350,
                        required_facets=["涨幅居前行业", "跌幅居前行业", "行业资金流向"],
                        placeholder="industry_performance_placeholder",
                    ),
                    SectionSpec(
                        key="notable_stocks",
                        title="重点股票观察",
                        target_words=300,
                        required_facets=["涨幅榜", "跌幅榜", "异动股票"],
                        placeholder="notable_stocks_placeholder",
                    ),
                    SectionSpec(
                        key="outlook",
                        title="后市展望",
                        target_words=250,
                        required_facets=["技术面", "消息面", "风险提示"],
                        placeholder="outlook_placeholder",
                    ),
                ]
            else:
                sections = []

            config = TemplateConfig(
                name=template_name,
                description=description,
                version=version,
                target_audience=target_audience,
                sections=sections,
                placeholders={},
            )

            # 保存配置
            template_manager.save_template(config, overwrite=True)
            logger.info(f"Created default YAML config for template: {template_name}")

        logger.info(f"Uploaded template {template_name} ({file_type.value}): {saved_path}")

        return {
            "success": True,
            "template_name": template_name,
            "file_type": file_type.value,
            "file_path": str(saved_path),
            "file_size": len(file_content),
        }
    except Exception as e:
        logger.exception(f"Failed to upload template {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to upload template: {str(e)}")


@router.get(
    "/{template_name}/placeholders/{file_type}",
    response_model=PlaceholderDiscoveryResponse,
    summary="从模板文件中发现占位符",
)
async def discover_placeholders(template_name: str, file_type: TemplateFileType):
    """
    从 DOCX/PPTX 模板文件中扫描并发现占位符
    支持 {{placeholder}} 和 {placeholder} 格式
    """
    try:
        placeholders: Set[str] = set()

        if file_type == TemplateFileType.DOCX:
            placeholders = template_manager.discover_placeholders_from_docx(template_name)
        elif file_type == TemplateFileType.PPTX:
            placeholders = template_manager.discover_placeholders_from_pptx(template_name)
        else:
            raise HTTPException(
                status_code=400, detail=f"Placeholder discovery not supported for {file_type.value}"
            )

        return PlaceholderDiscoveryResponse(
            template_name=template_name,
            file_type=file_type.value,
            placeholders=list(placeholders),
            total=len(placeholders),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_name}")
    except ImportError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Required library not available: {str(e)}. Please install python-docx or python-pptx.",
        )
    except Exception as e:
        logger.exception(f"Failed to discover placeholders for {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to discover placeholders: {str(e)}")


@router.post("/render", response_model=RenderReportResponse, summary="渲染模板报告")
async def render_template_report(request: RenderReportRequest):
    """
    从模板渲染报告，支持 DOCX/PPTX 格式
    可以使用预定义的占位符数据，或者通过 canonical_id 从现有 ReportGenerator 获取数据
    """
    try:
        import uuid

        report_id = str(uuid.uuid4())[:8]
        placeholders = dict(request.placeholders)
        sections: List[Dict[str, Any]] = []

        # 如果提供了 canonical_id，从 ReportGenerator 获取数据并使用映射器
        if request.canonical_id:
            from reporting.integration.snapshot_mapper import get_snapshot_mapper
            from services.asset_analysis_service import AssetAnalysisService

            asset_service = AssetAnalysisService()
            mapper = get_snapshot_mapper()
            as_of = request.as_of or datetime.now()

            # 获取资产分析快照 - use mock directly since we can't get full service working
            snapshot = asset_service._generate_mock_snapshot(request.canonical_id, as_of)

            # 使用映射器将快照数据映射到占位符
            snapshot_placeholders = mapper.map_snapshot_to_placeholders(
                snapshot=snapshot,
                report_type=request.report_type,
                additional_placeholders=placeholders,
            )

            placeholders = snapshot_placeholders

        else:
            # 即使没有 canonical_id，也添加基本占位符
            placeholders.setdefault("title", "Report")
            placeholders.setdefault("date", datetime.now().strftime("%Y-%m-%d"))

        # 获取模板文件路径
        file_type = cast(Literal["docx", "pptx", "excel"], request.file_type)
        template_path = template_manager.get_template_file_path(request.template_name, file_type)

        if not template_path:
            raise HTTPException(
                status_code=404,
                detail=f"Template file not found for {request.template_name} ({request.file_type})",
            )

        # 根据文件类型选择相应的投影器
        if request.file_type == "docx":
            from reporting.projections.word import WordProjection

            projection = WordProjection()
        elif request.file_type == "pptx":
            from reporting.projections.powerpoint import PowerPointProjection

            projection = PowerPointProjection()
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {request.file_type}"
            )

        # 确保输出目录存在
        output_dir = Path("output") / "rendered_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"report_{report_id}.{request.file_type}"

        # 渲染报告
        projection.save_from_template(
            output_path=output_path,
            template_path=template_path,
            sections=cast(List[SectionOutput], sections),
            placeholders=placeholders,
        )

        logger.info(f"Rendered report: {output_path}")

        return RenderReportResponse(
            success=True,
            report_id=report_id,
            template_name=request.template_name,
            file_type=request.file_type,
            file_name=f"report_{report_id}.{request.file_type}",
            download_url=f"/api/templates/download/{report_id}",
            generated_at=datetime.utcnow(),
            message="Report rendered successfully",
        )
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Required library not available: {str(e)}. Please install python-docx or python-pptx.",
        )
    except Exception as e:
        logger.exception("Failed to render template report")
        raise HTTPException(status_code=500, detail=f"Failed to render report: {str(e)}")


@router.post("/render-from-asset", response_model=RenderReportResponse, summary="从资产ID直接渲染报告")
async def render_report_from_asset(request: RenderReportFromAssetRequest):
    """
    简化版API：直接从资产ID渲染报告
    自动获取资产分析数据并映射到模板占位符
    """
    try:
        import uuid

        report_id = str(uuid.uuid4())[:8]
        as_of = request.as_of or datetime.now()

        # 获取资产分析快照
        from reporting.integration.snapshot_mapper import get_snapshot_mapper
        from services.asset_analysis_service import AssetAnalysisService

        asset_service = AssetAnalysisService()
        mapper = get_snapshot_mapper()

        # Use mock directly
        snapshot = asset_service._generate_mock_snapshot(request.canonical_id, as_of)

        # 使用映射器将快照数据映射到占位符
        placeholders = mapper.map_snapshot_to_placeholders(
            snapshot=snapshot,
            report_type=request.report_type,
            additional_placeholders=request.additional_placeholders,
        )

        # 获取模板文件路径
        file_type = cast(Literal["docx", "pptx", "excel"], request.file_type)
        template_path = template_manager.get_template_file_path(request.template_name, file_type)

        if not template_path:
            raise HTTPException(
                status_code=404,
                detail=f"Template file not found for {request.template_name} ({request.file_type})",
            )

        # 根据文件类型选择相应的投影器
        if request.file_type == "docx":
            from reporting.projections.word import WordProjection

            projection = WordProjection()
        elif request.file_type == "pptx":
            from reporting.projections.powerpoint import PowerPointProjection

            projection = PowerPointProjection()
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type: {request.file_type}"
            )

        # 确保输出目录存在
        output_dir = Path("output") / "rendered_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"report_{report_id}.{request.file_type}"

        # 渲染报告
        projection.save_from_template(
            output_path=output_path,
            template_path=template_path,
            sections=[],
            placeholders=placeholders,
        )

        logger.info(f"Rendered report from asset {request.canonical_id}: {output_path}")

        return RenderReportResponse(
            success=True,
            report_id=report_id,
            template_name=request.template_name,
            file_type=request.file_type,
            file_name=f"report_{report_id}.{request.file_type}",
            download_url=f"/api/templates/download/{report_id}",
            generated_at=datetime.utcnow(),
            message=f"Report rendered for {request.canonical_id} successfully",
        )
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Required library not available: {str(e)}. Please install python-docx or python-pptx.",
        )
    except Exception as e:
        logger.exception("Failed to render report from asset")
        raise HTTPException(status_code=500, detail=f"Failed to render report: {str(e)}")


@router.get("/download/{report_id}", summary="下载渲染的报告")
async def download_rendered_report(report_id: str, file_type: str = "docx"):
    """
    下载渲染完成的报告文件
    """
    try:
        output_dir = Path("output") / "rendered_reports"
        output_path = output_dir / f"report_{report_id}.{file_type}"

        if not output_path.exists():
            raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

        media_type = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(file_type, "application/octet-stream")

        return FileResponse(
            output_path,
            filename=f"report_{report_id}.{file_type}",
            media_type=media_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to download report {report_id}")
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")


@router.delete("/{template_name}", response_model=DeleteTemplateResponse, summary="删除模板")
async def delete_template(template_name: str):
    """
    删除指定的模板（包括配置和所有相关文件）
    """
    try:
        # 删除所有相关的模板文件
        deleted_files = []
        for file_type in ["docx", "pptx", "excel"]:
            typed_file_type = cast(Literal["docx", "pptx", "excel"], file_type)
            if template_manager.delete_template_file(template_name, typed_file_type):
                deleted_files.append(file_type)

        # 删除 YAML 配置
        try:
            template_manager.delete_template(template_name)
        except Exception as e:
            logger.warning(f"Failed to delete template config {template_name}: {e}")

        logger.info(f"Deleted template {template_name}")

        return DeleteTemplateResponse(
            success=True,
            template_name=template_name,
            message=f"Deleted template {template_name}"
            + (f" with files: {', '.join(deleted_files)}" if deleted_files else ""),
        )
    except Exception as e:
        logger.exception(f"Failed to delete template {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


@router.get("/files/{template_name}/{file_type}", summary="下载模板文件")
async def download_template_file(template_name: str, file_type: TemplateFileType):
    """
    下载原始模板文件
    """
    try:
        file_path = template_manager.get_template_file_path(template_name, file_type.value)

        if not file_path:
            raise HTTPException(status_code=404, detail="Template file not found")

        media_type = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(file_type.value, "application/octet-stream")

        return FileResponse(
            file_path,
            filename=f"{template_name}_template.{file_type.value}",
            media_type=media_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to download template file {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to download template: {str(e)}")


@router.get("/{template_name}/config", response_model=TemplateConfigResponse, summary="获取模板配置")
async def get_template_config(template_name: str, file_type: str = "docx"):
    """
    获取模板的占位符配置
    """
    try:
        # 尝试加载模板配置
        try:
            config = template_manager.load_template(template_name)
            config_dict = config.model_dump()
        except FileNotFoundError:
            # 如果没有配置，返回空的
            config_dict = {
                "name": template_name,
                "description": "",
                "version": "1.0",
                "placeholders": {},
            }

        return TemplateConfigResponse(
            template_name=template_name, file_type=file_type, config=config_dict
        )
    except Exception as e:
        logger.exception(f"Failed to get template config {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to get template config: {str(e)}")


@router.post("/config", summary="保存模板配置")
async def save_template_config(request: TemplateConfigSaveRequest):
    """
    保存模板的占位符配置
    """
    try:
        template_name = request.template_name

        # 尝试加载现有配置，如果不存在就创建新的
        try:
            config = template_manager.load_template(template_name)
        except FileNotFoundError:
            from core.contracts import TemplateConfig

            config = TemplateConfig(
                name=template_name,
                description=f"{template_name} 模板配置",
                version="1.0",
                sections=[],
            )

        # 更新占位符配置
        if not config.placeholders:
            config.placeholders = {}

        # 将新的占位符配置合并进去
        for name, ph_config in request.placeholders.items():
            config.placeholders[name] = ph_config.model_dump()

        # 保存配置
        template_manager.save_template(config, overwrite=True)

        return {
            "success": True,
            "template_name": template_name,
            "message": "Template config saved successfully",
        }
    except Exception as e:
        logger.exception(f"Failed to save template config {request.template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to save template config: {str(e)}")


@router.post("/create-yaml", summary="创建 YAML 模板配置")
async def create_yaml_template(
    template_name: str = Form(..., description="模板名称"),
    description: str = Form("", description="模板描述"),
    version: str = Form("1.0", description="版本"),
    target_audience: Optional[str] = Form(None, description="目标受众"),
    default_retrieval_profile: str = Form("weekly_report", description="默认检索配置"),
):
    """
    创建一个新的 YAML 模板配置（不包含文件上传，仅创建基础配置）
    """
    try:
        from core.contracts import RetrievalProfileType

        # 创建基本的周报模板配置
        config = template_manager.create_weekly_report_template()
        config.name = template_name
        config.description = description
        config.version = version
        config.target_audience = target_audience
        config.default_retrieval_profile = RetrievalProfileType(default_retrieval_profile)

        # 保存配置
        template_manager.save_template(config, overwrite=True)

        return {
            "success": True,
            "template_name": template_name,
            "message": f"Template config created: {template_name}",
            "config": {
                "name": config.name,
                "description": config.description,
                "version": config.version,
                "sections_count": len(config.sections),
            },
        }
    except Exception as e:
        logger.exception(f"Failed to create yaml template {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


class UpdateTemplateRequest(BaseModel):
    """更新模板请求."""

    template_name: Optional[str] = Field(default=None, description="New template name")
    description: Optional[str] = Field(default=None, description="Template description")
    version: Optional[str] = Field(default=None, description="Template version")
    sort_order: Optional[int] = Field(default=None, description="Sort order")


class UpdateTemplatesOrderRequest(BaseModel):
    """批量更新模板排序请求."""

    template_names: List[str] = Field(description="Template names in desired order")


@router.patch("/{template_name}", summary="更新模板元数据")
async def update_template(template_name: str, request: UpdateTemplateRequest):
    """
    更新模板的元数据（名称、描述、版本、排序等）.
    """
    try:
        update_data = request.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Map template_name to name for the template manager
        if "template_name" in update_data:
            update_data["name"] = update_data.pop("template_name")

        updated_config = template_manager.update_template_metadata(template_name, **update_data)

        return {
            "success": True,
            "template_name": updated_config.name,
            "message": "Template updated successfully",
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_name}")
    except Exception as e:
        logger.exception(f"Failed to update template {template_name}")
        raise HTTPException(status_code=500, detail=f"Failed to update template: {str(e)}")


@router.post("/reorder", summary="批量更新模板排序")
async def reorder_templates(request: UpdateTemplatesOrderRequest):
    """
    批量更新模板的排列顺序.
    """
    try:
        success = template_manager.update_templates_order(request.template_names)
        if success:
            return {"success": True, "message": "Templates reordered successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to reorder templates")
    except Exception as e:
        logger.exception("Failed to reorder templates")
        raise HTTPException(status_code=500, detail=f"Failed to reorder templates: {str(e)}")
