"""AlphaFoundry API"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

# 把项目根目录加入path（必须在其他本地导入之前）
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent.parent  # app/api/main.py → project root
sys.path.insert(0, str(project_root))

# 日志必须在所有其他模块导入前配置，否则模块级 get_logger(__name__)
# 会在 structlog.configure() 之前创建 PrintLogger 实例，导致 Windows
# 上 print() 抛 OSError: [Errno 22] Invalid argument。
from core.observability import setup_logging

setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.types import Scope

from app.api.configuration_security import (
    APPLICATION_CORS_ORIGINS,
    CONFIGURATION_CSRF_META_PLACEHOLDER,
    CONFIGURATION_CSRF_TOKEN,
    CONFIGURATION_TRUSTED_HOSTS,
    parse_cors_origins,
    parse_trusted_hosts,
    validate_cors_trusted_host_consistency,
)
from core.observability import get_logger
from core.settings.config import RUNTIME_CONTEXT, settings
from data_layer.repositories.base import ensure_schema
from services.database_readiness import DatabaseReadiness, DatabaseReadinessCode, probe_postgresql

__all__ = [
    "app",
    "parse_cors_origins",
    "parse_trusted_hosts",
    "validate_cors_trusted_host_consistency",
]

logger = get_logger(__name__)

_DATABASE_READINESS_STARTUP_ERROR = "无法连接 PostgreSQL；请检查数据库配置后重试。"

# 后端启动时间戳，供前端轮询检测后端重启后自动刷新页面
_STARTUP_TIMESTAMP: str = str(time.time())
_resource_monitor_runtime: Any | None = None


app = FastAPI(
    title="AlphaFoundry API",
    description="本地优先、可企业化的买方投研情报系统",
)


@app.on_event("startup")
async def startup() -> None:
    """Preflight persistence before initializing database-dependent services."""
    logger.info("AlphaFoundry API starting up...")
    readiness = probe_postgresql(settings.DATABASE_URL)
    app.state.database_readiness = readiness
    if not readiness.ready:
        if RUNTIME_CONTEXT.mode == "desktop":
            logger.warning(
                "Desktop started in setup-required mode",
                extra={"code": readiness.code.value},
            )
            return
        logger.error(
            "Database readiness failed during startup",
            extra={"code": readiness.code.value},
        )
        raise RuntimeError(_DATABASE_READINESS_STARTUP_ERROR)

    if os.environ.get("ALPHAFOUNDRY_PREVIEW") == "1":
        logger.info("Skipped database initialization and background services for branch preview")
        return

    ensure_schema()
    _start_resource_monitor_runtime()
    _start_wind_workbook_background()
    # 自动启动数据获取调度器（在 async 上下文中，AsyncIOScheduler 可正常拿到事件循环）
    _start_data_acquisition_schedulers()


def _start_wind_workbook_background() -> None:
    """Start the optional Wind workbook task only after persistence is ready."""
    try:
        from services.wind_workbook_manager import get_wind_workbook_manager

        get_wind_workbook_manager().start_background_ensure(reason="api_startup")
    except Exception as exc:
        logger.warning(
            "Wind realtime workbook background startup skipped",
            extra={"error_type": type(exc).__name__},
        )


def _start_resource_monitor_runtime() -> None:
    """在数据库已就绪后启动单一资源监控运行时。"""
    global _resource_monitor_runtime
    try:
        if _resource_monitor_runtime is None:
            from services.resource_monitor_runtime import ResourceMonitorRuntime

            _resource_monitor_runtime = ResourceMonitorRuntime()
        _resource_monitor_runtime.start()
    except Exception as exc:
        logger.warning(
            "Resource monitor runtime startup skipped",
            error_type=type(exc).__name__,
        )


def _start_data_acquisition_schedulers() -> None:
    """自动启动数据获取调度器"""
    logger = get_logger(__name__)

    # 尝试启动市场数据调度器
    try:
        from services.market_data_scheduler import get_market_data_scheduler

        scheduler = get_market_data_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("市场数据调度器已启动")
        else:
            logger.info("市场数据调度器已在运行中")
    except ImportError as e:
        logger.warning("无法导入市场数据调度器: %s", e)
    except Exception as e:
        logger.error("启动市场数据调度器失败: %s", e, exc_info=True)

    # 尝试启动爬虫调度器
    try:
        from services.crawl_scheduler import get_crawl_scheduler

        scheduler = get_crawl_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("爬虫调度器已启动")
        else:
            logger.info("爬虫调度器已在运行中")
    except ImportError as e:
        logger.warning("无法导入爬虫调度器: %s", e)
    except Exception as e:
        logger.error("启动爬虫调度器失败: %s", e, exc_info=True)

    try:
        from services.daily_market_commentary_scheduler import get_daily_market_commentary_scheduler

        get_daily_market_commentary_scheduler().start()
    except Exception as exc:
        logger.warning("每日市场点评调度器未启动", error_type=type(exc).__name__)

    # 检查 APScheduler 可用性
    try:
        import apscheduler  # noqa: F401

        logger.info("APScheduler 可用，数据获取调度器已配置")
    except ImportError:
        logger.warning("APScheduler 不可用，数据获取调度器将不会运行")


@app.on_event("shutdown")
def shutdown() -> None:
    """Shutdown hook"""
    logger.info("AlphaFoundry API shutting down...")
    _stop_resource_monitor_runtime()
    # 停止数据获取调度器
    _stop_data_acquisition_schedulers()


def _stop_resource_monitor_runtime() -> None:
    """停止已缓存的资源监控线程，不阻断 API 关闭。"""
    if _resource_monitor_runtime is None:
        return
    try:
        _resource_monitor_runtime.stop()
    except Exception as exc:
        logger.warning(
            "Resource monitor runtime shutdown failed",
            error_type=type(exc).__name__,
        )


def _stop_data_acquisition_schedulers() -> None:
    """停止数据获取调度器"""
    logger = get_logger(__name__)

    # 尝试停止市场数据调度器
    try:
        from services.market_data_scheduler import get_market_data_scheduler

        scheduler = get_market_data_scheduler()
        if scheduler.running:
            scheduler.stop()
            logger.info("市场数据调度器已停止")
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        logger.error("停止市场数据调度器失败: %s", e, exc_info=True)

    # 尝试停止爬虫调度器
    try:
        from services.crawl_scheduler import get_crawl_scheduler

        scheduler = get_crawl_scheduler()
        if scheduler.running:
            scheduler.stop()
            logger.info("爬虫调度器已停止")
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        logger.error("停止爬虫调度器失败: %s", e, exc_info=True)

    try:
        from services.daily_market_commentary_scheduler import get_daily_market_commentary_scheduler

        get_daily_market_commentary_scheduler().stop()
    except Exception as exc:
        logger.warning("每日市场点评调度器停止失败", error_type=type(exc).__name__)


# ─── CORS（收紧为配置驱动的域名白名单）──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=APPLICATION_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-AlphaFoundry-Config-Token"],
)

# ─── TrustedHost（防止 Host header 注入）────────────────
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=CONFIGURATION_TRUSTED_HOSTS,
    www_redirect=False,
)

# ─── 注册路由 ───────────────────────────────────────────
from app.api.routes import (  # noqa: E402
    assets,
    audit,
    commentary,
    configuration,
    dashboard,
    decision_console,
    event_ingestion,
    fingpt,
    factors,
    funds,
    governance,
    graph,
    ingest,
    ingest_admin,
    ingestion_queue,
    knowledge,
    llm,
    market_data,
    memory,
    monitoring,
    outcome_journal,
    outcomes,
    paper_trading,
    pdf_admin,
    pipeline,
    portfolio,
    realtime,
    replay,
    report,
    report_projects,
    research_runs,
    runtime_workflows,
    review,
    scenarios,
    scheduler,
    search,
    setup,
    signal_lab,
    signals,
    system,
    thesis_generator,
    thesis_review,
    timing,
    timing_engine,
    wind,
    workbench,
)

app.include_router(assets.router)
app.include_router(commentary.router)
app.include_router(configuration.router)
app.include_router(setup.router)
app.include_router(scenarios.router)
app.include_router(review.router)
app.include_router(signals.router)
app.include_router(ingest.router)
app.include_router(ingest_admin.router)
app.include_router(pipeline.router)
app.include_router(workbench.router)
app.include_router(graph.router)
app.include_router(timing.router)
app.include_router(memory.router)
app.include_router(outcomes.router)
app.include_router(outcome_journal.router, prefix="/api/outcome-journal")
app.include_router(ingestion_queue.router)
app.include_router(audit.router)
app.include_router(search.router)
app.include_router(replay.router)
app.include_router(research_runs.router)
app.include_router(research_runs.template_router)
app.include_router(runtime_workflows.router)
app.include_router(fingpt.router)
app.include_router(portfolio.router)
app.include_router(paper_trading.router)
app.include_router(governance.router)
app.include_router(monitoring.router)
app.include_router(decision_console.router)
app.include_router(event_ingestion.router)
app.include_router(funds.router)
app.include_router(factors.router)
app.include_router(thesis_generator.router)
app.include_router(thesis_review.router)
app.include_router(timing_engine.router)
app.include_router(dashboard.router)
app.include_router(report.router)
app.include_router(report_projects.router)
app.include_router(signal_lab.router)
app.include_router(llm.router)
app.include_router(scheduler.router)
app.include_router(knowledge.router)
app.include_router(pdf_admin.router)
app.include_router(market_data.router)
app.include_router(wind.router)
app.include_router(system.router)
app.include_router(realtime.router)

# ─── 静态文件 ────────────────────────────────────────────
_web_dir = Path(__file__).resolve().parent.parent / "web"
_static_dir = _web_dir / "static"
_templates_dir = _web_dir / "templates"


class NoCacheStaticFiles(StaticFiles):
    """让桌面 WebView 始终重新获取前端资源，避免缓存旧代码。"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.mount("/static", NoCacheStaticFiles(directory=str(_static_dir)), name="static")


# ─── 首页 & 健康检查 ───────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """首页 - 交互式 Web 前端"""
    index_path = _templates_dir / "index.html"
    html = index_path.read_text(encoding="utf-8").replace(
        CONFIGURATION_CSRF_META_PLACEHOLDER,
        CONFIGURATION_CSRF_TOKEN,
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/_version")
async def backend_version() -> Dict[str, Any]:
    """后端版本/启动时间戳。

    前端可定期轮询此端点，当 startup_ts 变化时自动刷新页面，
    从而在后端重启（如 uvicorn --reload）后无需手动 Ctrl+R。
    """
    return {
        "startup_ts": _STARTUP_TIMESTAMP,
        "version": app.version,
    }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查 - report the startup persistence state without retrying the database."""
    from core.settings.config import settings

    readiness = getattr(app.state, "database_readiness", None)
    if not isinstance(readiness, DatabaseReadiness):
        readiness = DatabaseReadiness(
            ready=False,
            code=DatabaseReadinessCode.UNEXPECTED_ERROR,
            message="数据库状态尚未完成初始化。",
            remediation=("请重启应用后重试。",),
        )
    persistence_status = "ready" if readiness.ready else "setup_required"

    return {
        "status": "ok",
        "app_env": settings.APP_ENV,
        "persistence": {
            "database_connected": readiness.ready,
            "status": persistence_status,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000)
