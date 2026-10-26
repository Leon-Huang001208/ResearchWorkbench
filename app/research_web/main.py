"""Web-only startup: python -m uvicorn app.research_web.main:app --port 8088."""

import asyncio
import hashlib
import json
import mimetypes
import os
import re
import shutil
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlsplit
from uuid import uuid4

from fastapi import FastAPI, Header, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.observability import get_logger, setup_logging
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, admission

from .ai_news_routes import router as ai_news_router
from .ai_news_service import create_ai_news_service
from .aihot_routes import router as aihot_router
from .asset_routes import router as asset_router
from .asset_workspace import AssetWorkspaceError
from .automation.routes import router as automation_router
from .capabilities.models import CapabilityError
from .capabilities.routes import router as capabilities_router
from .claw_routes import router as claw_router
from .client import DSHClient, RuntimeFailure
from .credential_backend import default_credential_backend
from .datahub.routes import router as datahub_router
from .discovery.routes import router as discovery_router
from .documentation import DOCUMENT_NAMES
from .documentation import router as documentation_router
from .dossier_signal_routes import router as dossier_signal_router
from .dossiers.routes import router as dossiers_router
from .frameworks.base import FrameworkError
from .frameworks.routes import router as frameworks_router
from .hot_routes import private_router as hot_private_router
from .hot_routes import router as hot_router
from .hot_service import HotWebError, HotWebService
from .integrations.routes import router as integrations_router
from .intel_routes import router as intel_router
from .local_integrations import LocalIntegrationError
from .local_integrations.routes import router as local_integrations_router
from .market_routes import router as market_router
from .mcp_registry import RegistryError
from .mcp_registry.routes import router as mcp_registry_router
from .mcp_runtime.routes import router as mcp_runtime_router
from .operations import router as operations_router
from .plugin_routes import router as plugin_router
from .plugins.runtime_restart import router as plugin_runtime_router
from .portfolio_decisions.routes import router as portfolio_decisions_router
from .report_routes import router as report_router
from .report_studio import ReportStudioError
from .report_workflow_routes import router as report_workflow_router
from .report_workflows.models import WorkflowError
from .service import ResearchService
from .store import Store, StoreError
from .tabbit import TabbitError
from .tenant_policy import check_request as check_tenant_request
from .tenant_policy import enabled as tenant_mode_enabled
from .workbench import router as workbench_router

log = get_logger(__name__)
UI = Path(__file__).parent / "ui"
ROOT = Path(
    os.environ.get("RESEARCH_DATA_HOME", str(Path.home() / ".research-workbench" / "research-web"))
)
UPLOAD_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".md",
    ".csv",
    ".xlsx",
    ".docx",
    ".pptx",
}


class NewSession(BaseModel):
    mode: Literal["fingpt", "claw"] = "fingpt"
    research_depth: Literal["instant", "deep"] = "instant"
    research_mode: Literal["quick", "deep", "agent"] | None = None
    source_scope: list[Literal["datahub", "web", "uploads"]] = Field(
        default=["datahub", "web", "uploads"], min_length=1, max_length=3
    )
    title: str | None = Field(default=None, min_length=1, max_length=120)
    workspace_id: Literal["research"] = "research"
    project_id: str | None = Field(default=None, pattern=r"^(default|project-[a-f0-9]{32})$")


class SessionSearch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str
    mode: Literal["claw", "fingpt"] | None = None


class TabbitTabRef(BaseModel):
    tab_id: int = Field(ge=0, strict=True)
    instance_id: str = Field(pattern=r"^[A-F0-9]{16}$")


class Prompt(BaseModel):
    dossier_handoff_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    text: str = Field(min_length=1, max_length=100000)
    research_mode: Literal["quick", "deep", "agent"] | None = None
    research_requirements: list[str] | None = Field(default=None, min_length=1, max_length=30)
    research_as_of: date | None = None

    @field_validator("research_requirements")
    @classmethod
    def bounded_requirements(cls, value):
        if value is not None and any(not item.strip() or len(item) > 4000 for item in value):
            raise ValueError("研究要求须为非空且不超过4000字符")
        return value

    attachment_ids: list[str] = Field(default_factory=list, max_length=20)
    skill_id: str | None = None
    capability_id: str | None = None
    capability_version: int | None = Field(default=None, ge=1, strict=True)
    tool_ids: list[str] = Field(default_factory=list, max_length=3)
    method_ids: list[str] = Field(default_factory=list, max_length=3)
    expected_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png", "pdf"]] | None = (
        Field(default=None, max_length=5)
    )
    tabbit_tabs: list[TabbitTabRef] = Field(default_factory=list, max_length=8)
    tabbit_live_confirmed: bool = False


class TabbitConfig(BaseModel):
    browser_enabled: bool
    web_fetch_enabled: bool
    instance_id: str | None = Field(default=None, pattern=r"^[A-F0-9]{16}$")


class TabbitAccess(BaseModel):
    decision: Literal["approve", "deny"]


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class Approval(BaseModel):
    decision: Literal["approve", "deny"]


class AnswerItem(BaseModel):
    id: str
    selected: list[str] = Field(default_factory=list, max_length=20)
    custom: str = Field(max_length=10000)


class Answers(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1, max_length=20)


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["deepseek-official", "openai-compatible"] = "deepseek-official"
    model: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    api_key: str | None = Field(default=None, min_length=1, max_length=1024, repr=False)
    clear_api_key: bool = False
    base_url: str | None = Field(default=None, min_length=1, max_length=2048, repr=False)
    protocol: Literal["openai-completions"] | None = None
    credential_mode: Literal["api_key", "none"] = "api_key"

    @model_validator(mode="after")
    def declared_connection(self):
        """Validate one route contract; Runtime support is checked independently."""
        try:
            if self.provider == "deepseek-official":
                if self.base_url is not None or self.protocol is not None:
                    raise ValueError("official endpoint is fixed")
                if self.credential_mode != "api_key":
                    raise ValueError("official credentials are required")
                return self
            if self.base_url is None:
                raise ValueError("compatible endpoint is required")
            endpoint = urlsplit(self.base_url)
            if (
                self.base_url != self.base_url.strip()
                or any(ord(char) < 33 or 127 <= ord(char) <= 159 for char in self.base_url)
                or endpoint.scheme not in {"http", "https"}
                or not endpoint.hostname
                or endpoint.username is not None
                or endpoint.password is not None
                or "?" in self.base_url
                or "#" in self.base_url
                or endpoint.port == 0
            ):
                raise ValueError("endpoint is not an unauthenticated network address")
            local = endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            if endpoint.scheme == "http" and not local:
                raise ValueError("plain HTTP is only supported on local loopback")
            if self.credential_mode == "none" and (
                not local or self.api_key is not None or self.clear_api_key
            ):
                raise ValueError("keyless local route must not carry credentials")
            self.protocol = "openai-completions"
            return self
        except ValueError:
            log.warning("research_model_connection_request_rejected")
            raise ValueError("model connection contract is invalid") from None

    @field_validator("api_key")
    @classmethod
    def reject_masked_key(cls, value: str | None) -> str | None:
        if value is not None:
            stripped = value.strip()
            if (
                not stripped
                or set(stripped) <= {"*", "•", "●"}
                or stripped.casefold() in {"[redacted]", "<redacted>", "[hidden]", "<hidden>"}
            ):
                raise ValueError("credential placeholder is not a new key")
        return value


class ModelProfileConfig(ModelConfig):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def profile_name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("model_profile_name_invalid")
        return value.strip()


def create_app(service: ResearchService | None = None) -> FastAPI:
    # Operator opt-in for one authenticated Tailscale Serve HTTPS origin only.
    # Never derive trust from Host, X-Forwarded-Host, or a wildcard suffix.
    private_origin = os.environ.get("RESEARCH_WEB_PRIVATE_ORIGIN", "")
    if private_origin and not re.fullmatch(
        r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tail[a-z0-9]+\.ts\.net",
        private_origin,
    ):
        log.error("research_web_private_origin_invalid")
        raise ValueError("private_origin_invalid")
    private_host = urlsplit(private_origin).hostname if private_origin else None
    access = {
        "mode": "tailscale" if private_origin else "loopback",
        "origin": private_origin or None,
    }

    @asynccontextmanager
    async def lifespan(app):
        setup_logging()
        active = service or ResearchService(
            DSHClient(os.environ.get("RESEARCH_RUNTIME_URL", "http://127.0.0.1:3081")),
            Store(ROOT),
            owned=False,
            expected_cwd=ROOT / "runtime" / "work",
            auto_probe_on_start=not tenant_mode_enabled(),
        )
        app.state.research = active
        if not tenant_mode_enabled():
            app.state.ai_news = create_ai_news_service(
                Path(__file__).resolve().parents[2],
                active.store.root,
                credentials=default_credential_backend,
            )
            app.state.aihot = app.state.ai_news.reader
        app.state.hot = HotWebService(Path(__file__).resolve().parents[2], active.store.root)
        await active.start()
        log.info(
            "research_web_started", engine="dsh", legacy_services=False, web_access=access["mode"]
        )
        try:
            yield
        finally:
            try:
                await app.state.hot.close()
            finally:
                await active.close()

    app = FastAPI(title="Research Workbench Research Web", lifespan=lifespan)
    app.include_router(aihot_router)
    app.include_router(ai_news_router)
    app.include_router(datahub_router)
    app.include_router(dossier_signal_router)
    app.include_router(dossiers_router)
    app.include_router(asset_router)
    app.include_router(market_router)
    app.include_router(intel_router)
    app.include_router(discovery_router)
    app.include_router(capabilities_router)
    app.include_router(plugin_router)
    app.include_router(plugin_runtime_router)
    app.include_router(documentation_router)
    app.include_router(frameworks_router)
    app.include_router(hot_router)
    app.include_router(hot_private_router)
    app.include_router(local_integrations_router)
    app.include_router(integrations_router)
    app.include_router(mcp_registry_router)
    app.include_router(mcp_runtime_router)
    app.include_router(automation_router)
    app.include_router(claw_router)
    app.include_router(workbench_router)
    app.include_router(operations_router)
    app.include_router(portfolio_decisions_router)
    app.include_router(report_workflow_router)
    # Legacy report-project paths remain readable, but the versioned Workflow
    # runtime owns overlapping /report-runs paths.
    app.include_router(report_router)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
        + ([private_host] if private_host else []),
    )

    @app.middleware("http")
    async def local_boundary(request, call_next):
        tenant_denial = await check_tenant_request(request)
        if tenant_denial is not None:
            return tenant_denial
        plugin_control = request.url.path.startswith("/api/research/internal/plugin-runtime/")
        if tenant_mode_enabled() and not plugin_control:
            active = request.app.state.research
            if active.plugin_runtime_frozen:
                return JSONResponse({"error": {"code": "plugin_runtime_frozen"}}, status_code=409)
        if request.url.path.startswith(
            "/api/research/internal/data/"
        ) and not request.app.state.research.datahub.authenticate(
            request.headers.get("X-Research-Data-Key")
        ):
            return JSONResponse(
                {"error": {"code": "data_auth_denied", "message": "仅可信原生插件可发起资料查询"}},
                status_code=403,
            )
        # Loopback app, no CORS. Stop drive-by requests / opaque sandbox origins.
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        remote_host = private_host and host.split(":", 1)[0].casefold() == private_host
        if remote_host and (
            host.casefold() not in {private_host, f"{private_host}:443"}
            or request.url.scheme != "https"
        ):
            log.warning("research_web_private_transport_denied")
            return JSONResponse({"error": {"code": "private_transport_denied"}}, status_code=400)
        own = private_origin if remote_host else f"{request.url.scheme}://{host}"
        # A user-activated top-level GET may load only the static app shell.
        # Fetch Metadata is browser-controlled; API/resource/iframe requests and
        # explicit foreign Origins never inherit this navigation exception.
        entry_navigation = (
            request.url.path == "/"
            and request.method == "GET"
            and request.headers.get("sec-fetch-mode") == "navigate"
            and request.headers.get("sec-fetch-dest") == "document"
            and request.headers.get("sec-fetch-user") == "?1"
            and origin in {None, own}
        )
        documentation_path = request.url.path in {
            f"/api/research/documentation/{name}" for name in DOCUMENT_NAMES
        }
        # An opaque-origin index can navigate only to these public, isolated documents.
        public_document_navigation = (
            documentation_path
            and request.method == "GET"
            and request.headers.get("sec-fetch-mode") == "navigate"
            and request.headers.get("sec-fetch-dest") == "document"
            and request.headers.get("sec-fetch-user") == "?1"
        )
        oauth_callback_navigation = (
            request.url.path == "/api/research/mcp/oauth/callback"
            and request.method == "GET"
            and request.headers.get("sec-fetch-mode") == "navigate"
            and request.headers.get("sec-fetch-dest") == "document"
        )
        if not (entry_navigation or public_document_navigation or oauth_callback_navigation) and (
            (origin and origin != own) or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse(
                {"error": {"code": "origin_denied", "message": "跨站请求被拒绝"}}, status_code=403
            )

        async def dispatch():
            ticket = (
                tenant_mode_enabled()
                and not plugin_control
                and request.method not in {"GET", "HEAD"}
            )
            if ticket:
                active = request.app.state.research
                if active.plugin_runtime_frozen:
                    return JSONResponse(
                        {"error": {"code": "plugin_runtime_frozen"}}, status_code=409
                    )
                active.plugin_inflight += 1
            try:
                return await call_next(request)
            finally:
                if ticket:
                    active.plugin_inflight -= 1

        try:
            # Internal plugin callbacks remain authenticated above and must not
            # deadlock startup while the updater holds the exclusive fence.
            if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.url.path.startswith(
                "/api/research/internal/"
            ):
                with admission():
                    response = await dispatch()
            else:
                response = await dispatch()
        except MaintenanceBusy:
            log.info("research_web_resident_maintenance")
            return JSONResponse(
                {"error": {"code": "deployment_busy", "message": "正在安全更新，请稍后重试"}},
                status_code=503,
                headers={"Retry-After": "5"},
            )
        if (
            entry_navigation
            and request.headers.get("sec-fetch-site") == "cross-site"
            and response.status_code == 200
        ):
            log.info("research_web_entry_navigation_allowed")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        documentation_response = documentation_path and response.status_code == 200
        # Vendored framework apps have a route-scoped same-origin iframe policy.
        embed_response = request.url.path.startswith("/frameworks-embed/")
        if embed_response:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'self'"
            )
        elif "/preview" not in request.url.path and not documentation_response:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'"
            )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/research/resident")
    async def resident_status(request: Request):
        setting = os.environ.get("RESEARCH_RESIDENT_HOME")
        revision = os.environ.get("RESEARCH_RESIDENT_REVISION", "")
        research = getattr(request.app.state, "research", None)
        active = None
        activity = None
        if research is not None:
            active = False

            def history_activity():
                history_jobs = research.store.data.get("asset_history_jobs", {})
                return not isinstance(history_jobs, dict) or any(
                    not isinstance(row, dict)
                    or ("state" in row and "status" in row and row["state"] != row["status"])
                    or row.get("state", row.get("status"))
                    not in {"completed", "failed", "cancelled", "interrupted"}
                    for row in history_jobs.values()
                )

            def witness_flag(value):
                if not isinstance(value, dict) or type(value.get("active")) is not bool:
                    raise ValueError("activity_witness_unknown")
                return value["active"]

            def sdk_activity():
                from .datahub.worker_activity import active_futures

                return bool(active_futures())

            def wind_api_activity():
                from .datahub.providers_wind_api import activity_witness

                return witness_flag(activity_witness())

            def report_activity():
                report_manager = getattr(research, "report_workflows", None)
                report_runtime = getattr(report_manager, "runtime", None)
                report_catalog = getattr(report_manager, "catalog", None)
                if report_runtime is None or report_catalog is None:
                    raise ValueError("report_activity_unknown")
                report_runs = report_catalog.data["runs"]
                terminal_reports = {
                    "completed",
                    "cancelled",
                    "failed",
                    "blocked_data",
                    "delivery_incomplete",
                    "quality_incomplete",
                    "skipped_overlap",
                }
                return (
                    not isinstance(report_runs, dict)
                    or any(
                        not isinstance(row, dict) or row.get("status") not in terminal_reports
                        for row in report_runs.values()
                    )
                    or bool(report_runtime.tasks)
                )

            def storage_activity():
                storage_runner = research.datahub.storage_runner
                if storage_runner is None:
                    return False
                value = storage_runner.active
                if type(value) is not bool:
                    raise ValueError("storage_activity_unknown")
                return value

            observations = {}
            for name, check in (
                ("research_tasks", lambda: any(research.running.values())),
                ("approvals", lambda: bool(research.approvals)),
                ("questions", lambda: bool(research.questions)),
                ("source_requests", lambda: bool(research.source_requests)),
                (
                    "automation_runs",
                    lambda: any(
                        row.get("research_status") in {"queued", "running"}
                        for row in research.store.data.get("automation_runs", {}).values()
                    ),
                ),
                ("history_jobs", history_activity),
                ("sdk_aggregate", sdk_activity),
                ("wind_api", wind_api_activity),
                ("market", lambda: witness_flag(research.market.activity_witness())),
                ("reports", report_activity),
                (
                    "datahub_tasks",
                    lambda: any(not task.done() for task in research.datahub.tasks.values()),
                ),
                ("storage", storage_activity),
                ("asset_directory", lambda: research.asset_workspace.directory.active),
                (
                    "asset_tasks",
                    lambda: any(
                        not task.done() for task in research.asset_workspace.tasks.values()
                    ),
                ),
                ("directory_tasks", lambda: bool(research.datahub.directory_tasks)),
            ):
                try:
                    # Evaluate every witness, including after a known busy or
                    # unknown result. Neither may erase another subsystem's fact.
                    observed = check()
                    if type(observed) is not bool:
                        raise ValueError("activity_witness_unknown")
                    observations[name] = observed
                    active = bool(active or observed)
                except Exception as exc:  # noqa: BLE001 - unknown activity must fail closed
                    log.warning("resident_data_activity_unknown", error_type=type(exc).__name__)
                    observations[name] = None
            from .datahub.worker_activity import activity_witness

            activity = {
                "schema": "resident-activity-v1",
                "checks": observations,
                "sources": activity_witness(),
            }
            active = (
                True
                if any(value is True for value in observations.values())
                else None if any(value is None for value in observations.values()) else False
            )
            # Source observations can be newer than the aggregate above. Never
            # publish aggregate idle alongside a known running or unknown source.
            # Keep the original aggregate/mock observation and its unknown result;
            # later evidence can strengthen refusal, never erase it.
            for source in activity["sources"].values():
                if source["running"] is True:
                    active = True
                elif active is not True and (
                    source["running"] is None or source["cleanup_unconfirmed"] is not False
                ):
                    active = None
        result = {
            "enabled": bool(setting),
            "revision": revision if re.fullmatch(r"[a-f0-9]{40}", revision) else None,
            "maintenance": bool(setting and (Path(setting) / "transaction.json").exists()),
            "active": active,
        }
        if activity is not None:
            result["activity_witness"] = activity
        return result

    @app.exception_handler(RuntimeFailure)
    async def runtime_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": str(exc)}}, status_code=503)

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(HotWebError)
    async def hot_error(request, exc):
        log.warning("hot_web_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(FrameworkError)
    async def framework_error(request, exc):
        log.warning("framework_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(AssetWorkspaceError)
    async def asset_workspace_error(request, exc):
        return JSONResponse(
            {"error": {"code": "asset_workspace_error", "message": str(exc)}},
            status_code=exc.status,
        )

    @app.exception_handler(ReportStudioError)
    async def report_studio_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(WorkflowError)
    async def report_workflow_error(request, exc):
        log.warning("report_workflow_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(CapabilityError)
    async def capability_error(request, exc):
        log.warning("capability_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(TabbitError)
    async def tabbit_error(request, exc):
        log.warning("tabbit_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(LocalIntegrationError)
    async def local_integration_error(request, exc):
        log.warning("local_integration_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(RegistryError)
    async def mcp_registry_error(request, exc):
        log.warning("mcp_registry_request_rejected", code=exc.code)
        return JSONResponse(
            {"error": {"code": exc.code, "message": str(exc)}}, status_code=exc.status
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default error includes rejected input, potentially an API key.
        return JSONResponse(
            {"error": {"code": "invalid_request", "message": "请求字段格式不正确"}}, status_code=422
        )

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        log.error("research_api_failed", path=request.url.path, error_type=type(exc).__name__)
        return JSONResponse(
            {"error": {"code": "internal_error", "message": "请求处理失败，请查看本地日志"}},
            status_code=500,
        )

    def svc(request):
        return request.app.state.research

    @app.get("/api/research/runtime")
    async def runtime(request: Request):
        return {**await svc(request).runtime(), "web_access": access}

    @app.get("/api/research/models")
    async def models(request: Request):
        result = await svc(request).client.rpc("llm.models", {})
        return {
            "groups": [{**group, "provider": group["id"]} for group in result["groups"]],
            "failures": result["failures"],
        }

    @app.put("/api/research/runtime/model")
    async def configure_model(body: ModelConfig, request: Request):
        if body.clear_api_key and body.api_key is not None:
            raise StoreError("替换与清除凭据不能同时提交", "invalid_request", 422)
        return await svc(request).configure_model(
            body.provider,
            body.model,
            body.api_key,
            clear_api_key=body.clear_api_key,
            base_url=body.base_url,
            protocol=body.protocol,
            credential_mode=body.credential_mode,
        )

    @app.get("/api/research/model-profiles")
    async def model_profiles(request: Request):
        return await svc(request).list_model_profiles()

    @app.post("/api/research/model-profiles")
    async def add_model_profile(body: ModelProfileConfig, request: Request):
        return await svc(request).save_model_profile(body)

    @app.put("/api/research/model-profiles/{identity}")
    async def update_model_profile(identity: str, body: ModelProfileConfig, request: Request):
        return await svc(request).save_model_profile(body, identity)

    @app.post("/api/research/model-profiles/{identity}/activate")
    async def activate_model_profile(identity: str, request: Request):
        return await svc(request).activate_model_profile(identity)

    @app.delete("/api/research/model-profiles/{identity}")
    async def archive_model_profile(identity: str, request: Request):
        return await svc(request).archive_model_profile(identity)

    @app.post("/api/research/runtime/model/test")
    async def test_model(request: Request):
        return await svc(request).test_model()

    @app.get("/api/research/runtime/tabbit")
    async def tabbit_status(request: Request):
        return await svc(request).tabbit.status()

    @app.put("/api/research/runtime/tabbit")
    async def configure_tabbit(body: TabbitConfig, request: Request):
        service = svc(request)
        await service.ensure_owned()
        status = await service.tabbit.status()
        if body.browser_enabled and status["online_instances"] > 1 and body.instance_id is None:
            raise TabbitError(
                "多个 Tabbit 实例在线时必须选择实例",
                "tabbit_instance_selection_required",
                409,
            )
        return service.tabbit.configure(**body.model_dump())

    @app.get("/api/research/workspaces")
    async def workspaces():
        return {"items": [{"id": "research", "name": "我的研究"}]}

    @app.get("/api/research/sessions")
    async def sessions(request: Request, view: Literal["active", "deleted", "all"] = "active"):
        service = svc(request)
        return {"items": await service.list_sessions(view)}

    @app.post("/api/research/sessions", status_code=201)
    async def create_session(body: NewSession, request: Request):
        return await svc(request).create(
            body.mode,
            body.title,
            project_id=body.project_id,
            research_depth=body.research_depth,
            research_mode=body.research_mode,
            source_scope=body.source_scope,
        )

    @app.post("/api/research/sessions/search")
    async def search_sessions(body: SessionSearch, request: Request):
        return await svc(request).search_sessions(body.query, mode=body.mode)

    @app.get("/api/research/sessions/{sid}")
    async def session(sid: str, request: Request):
        return await svc(request).detail(sid)

    @app.post("/api/research/sessions/{sid}/tabbit-access")
    async def tabbit_access(sid: str, body: TabbitAccess, request: Request):
        await svc(request).ensure_owned()
        return await svc(request).tabbit.access(sid, body.decision)

    @app.get("/api/research/sessions/{sid}/tabbit-tabs")
    async def tabbit_tabs(
        sid: str,
        request: Request,
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=50),
    ):
        return await svc(request).tabbit.tabs(sid, query=q, limit=limit)

    @app.patch("/api/research/sessions/{sid}")
    async def rename(sid: str, body: Rename, request: Request):
        service = svc(request)
        await service.ensure_owned()
        row = service.store.session(sid)
        await service.client.rpc("session.rename", {"sessionId": sid, "title": body.title})
        row["title"] = body.title
        service.store.save()
        return service.summary(row)

    @app.delete("/api/research/sessions/{sid}")
    async def delete_session(sid: str, request: Request):
        return await svc(request).soft_delete_session(sid)

    @app.post("/api/research/sessions/{sid}/restore")
    async def restore_session(sid: str, request: Request):
        return await svc(request).restore_session(sid)

    @app.delete("/api/research/sessions/{sid}/permanent")
    async def permanently_delete_session(sid: str, request: Request):
        return await svc(request).permanent_delete_session(sid)

    @app.post("/api/research/sessions/{sid}/messages", status_code=202)
    async def send(
        sid: str,
        body: Prompt,
        request: Request,
        idempotency_key: str = Header(min_length=8, max_length=128),
    ):
        if not body.text.strip():
            raise StoreError("问题不能为空")
        return await svc(request).send(
            sid,
            body.text,
            idempotency_key,
            body.attachment_ids,
            body.skill_id,
            body.expected_formats,
            capability_id=body.capability_id,
            capability_version=body.capability_version,
            tool_ids=body.tool_ids,
            method_ids=body.method_ids,
            tabbit_tabs=[item.model_dump() for item in body.tabbit_tabs],
            tabbit_live_confirmed=body.tabbit_live_confirmed,
            research_mode=body.research_mode,
            research_requirements=body.research_requirements,
            research_as_of=body.research_as_of.isoformat() if body.research_as_of else None,
            dossier_handoff_id=body.dossier_handoff_id,
        )

    @app.post("/api/research/sessions/{sid}/cancel")
    async def cancel(sid: str, request: Request):
        return await svc(request).cancel(sid)

    @app.post("/api/research/sessions/{sid}/approvals/{aid}")
    async def approve(sid: str, aid: str, body: Approval, request: Request):
        return await svc(request).approve(sid, aid, body.decision)

    @app.post("/api/research/sessions/{sid}/questions/{qid}")
    async def answer(sid: str, qid: str, body: Answers, request: Request):
        return await svc(request).answer(sid, qid, [item.model_dump() for item in body.answers])

    @app.post("/api/research/sessions/{sid}/upgrade")
    async def upgrade(sid: str, request: Request):
        service = svc(request)
        old = await service.detail(sid)
        new = await service.create("claw", old["title"])
        # Draft is carried into the composer, not submitted or forked across cwd boundaries.
        new["draft"] = "继续研究以下会话：\n" + "\n\n".join(
            f"{m['role']}: {m['text']}" for m in old["messages"]
        )
        for item in old["files"]:
            if item.get("kind") == "inputs":
                source = service.store.file_path(sid, item["id"])
                shutil.copyfile(source, service.store.directory(new["id"]) / "inputs" / source.name)
        new["attachments"] = service.store.files(new["id"])
        service.datahub.copy_for_upgrade(sid, new["id"])
        new["datasets"] = service.datahub.summaries(new["id"])
        mappings = []
        for item in new["datasets"]:
            dataset = service.datahub.detail(new["id"], item["dataset_id"])
            mappings.append(
                {
                    key: dataset[key]
                    for key in (
                        "origin_dataset_id",
                        "dataset_id",
                        "origin_manifest_sha256",
                        "manifest_sha256",
                        "retrieved_at",
                    )
                }
                | {
                    "files": [
                        {"path": file["path"], "sha256": file["sha256"]}
                        for file in dataset["files"]
                    ]
                }
            )
        if mappings:
            new["draft"] += (
                "\n\n数据集升级映射：上方原消息保持不变；旧数据集路径不属于当前会话。"
                "仅使用下列当前会话相对路径，先读取manifest核对状态和缺失项，不必重新取数。\n"
                + json.dumps(mappings, ensure_ascii=False, indent=2)
            )
            log.info(
                "research_upgrade_dataset_mapping_added", session_id=new["id"], count=len(mappings)
            )
        return new

    @app.get("/api/research/sessions/{sid}/events")
    async def events(sid: str, request: Request):
        service = svc(request)
        service.store.session(sid)

        async def stream():
            changed = asyncio.Event()
            service.listeners.add(changed)
            previous = None
            try:
                while not await request.is_disconnected():
                    changed.clear()
                    try:
                        detail = await service.detail(sid)
                        payload = json.dumps(detail, ensure_ascii=False)
                        if payload != previous:
                            yield f"event: snapshot\ndata: {payload}\n\n"
                            previous = payload
                    except RuntimeFailure as exc:
                        yield "event: runtime_error\ndata: " + json.dumps(
                            {"message": str(exc)}, ensure_ascii=False
                        ) + "\n\n"
                    try:
                        await asyncio.wait_for(changed.wait(), timeout=5)
                        await asyncio.sleep(0.12)
                    except TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                service.listeners.discard(changed)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    @app.post("/api/research/sessions/{sid}/uploads")
    async def upload(sid: str, request: Request, files: list[UploadFile]):
        store = svc(request).store
        if "uploads" not in store.session(sid).get("source_scope", ["datahub", "web", "uploads"]):
            log.warning("research_upload_source_excluded", session_id=sid)
            raise CapabilityError("本会话检索范围未包含上传资料", "research_source_excluded", 409)
        root = store.directory(sid) / "inputs"
        if root.is_symlink():
            raise StoreError("上传目录非法")
        if len(files) > 20:
            raise StoreError("每次最多上传 20 个文件")
        saved = set()
        for upload in files:
            name = Path(upload.filename or "").name
            extension = Path(name).suffix.lower()
            if extension not in UPLOAD_EXTENSIONS:
                raise StoreError("不支持的附件格式")
            safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", name)[:160]
            path = root / f"{uuid4().hex[:12]}-{safe_name}"
            size = 0
            try:
                with path.open("xb") as output:
                    os.chmod(path, 0o600)
                    while chunk := await upload.read(1024 * 1024):
                        size += len(chunk)
                        if size > 30 * 1024 * 1024:
                            raise StoreError("单文件超过 30 MB")
                        output.write(chunk)
                saved.add(path.name)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            finally:
                await upload.close()
        log.info("research_files_uploaded", session_id=sid, count=len(saved))
        return {"items": [file for file in store.files(sid) if file["name"] in saved]}

    @app.get("/api/research/sessions/{sid}/files")
    async def list_files(sid: str, request: Request):
        return {"items": svc(request).store.files(sid)}

    @app.get("/api/research/sessions/{sid}/files/{fid}/{action}")
    async def file(sid: str, fid: str, action: Literal["download", "preview"], request: Request):
        service = svc(request)
        relative = service.store.session(sid).get("files", {}).get(fid, "")
        receipt = service.store.data["receipts"].get(
            f"{sid}:{service.store.session(sid).get('delivery_key', '')}", {}
        )
        if relative.startswith("outputs/") and receipt.get("research_contract"):
            detail = await service.detail(sid)
            if (detail.get("research_quality") or {}).get("status") == "invalid":
                raise StoreError("报告完整性检查未通过，暂不能交付", "research_report_invalid", 409)
        stream, name = svc(request).store.open_file(sid, fid)
        if relative.startswith("outputs/report-versions/"):
            from .research_quality_service import archive_digest

            try:
                expected = archive_digest(service, sid, relative)
                raw = stream.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected:
                    raise StoreError(
                        "历史报告完整性检查未通过", "research_report_version_changed", 409
                    )
                stream.seek(0)
            except Exception:
                stream.close()
                raise
        media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if action == "preview" and media_type in {"text/markdown", "text/x-markdown"}:
            media_type = "text/plain"
        log.info(
            "research_file_response",
            session_id=sid,
            file_id=fid,
            action=action,
            media_type=media_type,
        )

        def chunks():
            try:
                while chunk := stream.read(65536):
                    yield chunk
            finally:
                stream.close()

        return StreamingResponse(
            chunks(),
            media_type=media_type,
            headers={
                "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f"{'attachment' if action == 'download' else 'inline'}; filename*=utf-8''{quote(name)}",
            },
        )

    @app.get("/api/research/skills")
    async def skills(request: Request):
        service = svc(request)
        rows = [row for row in service.store.data["sessions"].values() if row["created"]]
        if not rows:
            return {"items": []}
        result = await service.skill_catalog(rows[-1]["id"])
        return {"items": [{"id": skill["name"], **skill} for skill in result["skills"]]}

    EMBEDS = Path(__file__).resolve().parent / "frameworks" / "embeds"
    if EMBEDS.exists():
        app.mount(
            "/frameworks-embed", StaticFiles(directory=EMBEDS, html=True), name="frameworks-embed"
        )

    if UI.exists():
        app.mount("/static", StaticFiles(directory=UI), name="static")

    @app.get("/")
    async def index():
        return FileResponse(UI / "index.html")

    return app


app = create_app()
