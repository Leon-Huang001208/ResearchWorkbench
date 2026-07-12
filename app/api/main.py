"""AlphaFoundry API"""
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.types import Scope

# 把项目根目录加入path
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent.parent  # app/api/main.py → project root
sys.path.insert(0, str(project_root))

from app.api.configuration_security import (
    APPLICATION_CORS_ORIGINS,
    CONFIGURATION_CSRF_META_PLACEHOLDER,
    CONFIGURATION_CSRF_TOKEN,
    CONFIGURATION_TRUSTED_HOSTS,
    parse_cors_origins,
    parse_trusted_hosts,
    validate_cors_trusted_host_consistency,
)
from core.observability import configure_logging, get_logger

__all__ = [
    "app",
    "parse_cors_origins",
    "parse_trusted_hosts",
    "validate_cors_trusted_host_consistency",
]

logger = get_logger(__name__)


app = FastAPI(
    title="AlphaFoundry API",
    description="本地优先、可企业化的买方投研情报系统",
)


@app.on_event("startup")
def startup() -> None:
    """Startup hook: configure logging and check database connection"""
    configure_logging()
    logger.info("AlphaFoundry API starting up...")
    # Explicit database connection check on API startup + schema ensure
    from data_layer.repositories.base import check_database_connection, ensure_schema

    check_database_connection()
    ensure_schema()

    try:
        from services.wind_workbook_manager import get_wind_workbook_manager

        get_wind_workbook_manager().start_background_ensure(reason="api_startup")
    except Exception as exc:
        logger.warning("Wind realtime workbook background startup skipped: %s", exc)


@app.on_event("shutdown")
def shutdown() -> None:
    """Shutdown hook"""
    logger.info("AlphaFoundry API shutting down...")


app.add_middleware(
    CORSMiddleware,
    allow_origins=APPLICATION_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-AlphaFoundry-Config-Token"],
)
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
    review,
    scenarios,
    scheduler,
    search,
    signal_lab,
    signals,
    system,
    templates,
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
app.include_router(portfolio.router)
app.include_router(paper_trading.router)
app.include_router(governance.router)
app.include_router(monitoring.router)
app.include_router(decision_console.router)
app.include_router(event_ingestion.router)
app.include_router(funds.router)
app.include_router(thesis_generator.router)
app.include_router(thesis_review.router)
app.include_router(timing_engine.router)
app.include_router(dashboard.router)
app.include_router(report.router)
app.include_router(report_projects.router)
app.include_router(templates.router)
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


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查 - includes persistence status"""
    from sqlalchemy import text

    from core.settings.config import settings
    from data_layer.repositories.base import SessionLocal

    persistence_status = "unknown"
    db_connected = False
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            session.commit()
            db_connected = True
            persistence_status = "ready"
    except Exception as e:
        persistence_status = f"unavailable: {str(e)}"

    return {
        "status": "ok",
        "app_env": settings.APP_ENV,
        "persistence": {"database_connected": db_connected, "status": persistence_status},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000)
