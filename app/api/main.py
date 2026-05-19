"""AlphaFoundry API"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# 把项目根目录加入path
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent.parent  # app/api/main.py → project root
sys.path.insert(0, str(project_root))

from core.observability import configure_logging, get_logger

logger = get_logger(__name__)


app = FastAPI(
    title="AlphaFoundry API",
    description="本地优先、可企业化的买方投研情报系统",
)


@app.on_event("startup")
def startup():
    """Startup hook: configure logging and check database connection"""
    configure_logging()
    logger.info("AlphaFoundry API starting up...")
    # Explicit database connection check on API startup + schema ensure
    from data_layer.repositories.base import check_database_connection, ensure_schema

    check_database_connection()
    ensure_schema()


@app.on_event("shutdown")
def shutdown():
    """Shutdown hook"""
    logger.info("AlphaFoundry API shutting down...")


# ─── CORS（开发模式允许所有来源）─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 注册路由 ───────────────────────────────────────────
from app.api.routes import (  # noqa: E402
    assets,
    audit,
    dashboard,
    decision_console,
    event_ingestion,
    governance,
    graph,
    ingest,
    ingest_admin,
    ingestion_queue,
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
    replay,
    report,
    review,
    scenarios,
    scheduler,
    search,
    signal_lab,
    signals,
    templates,
    thesis_generator,
    thesis_review,
    timing,
    timing_engine,
    workbench,
)

app.include_router(assets.router)
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
app.include_router(thesis_generator.router)
app.include_router(thesis_review.router)
app.include_router(timing_engine.router)
app.include_router(dashboard.router)
app.include_router(report.router)
app.include_router(templates.router)
app.include_router(signal_lab.router)
app.include_router(llm.router)
app.include_router(scheduler.router)
app.include_router(pdf_admin.router)
app.include_router(market_data.router)

# ─── 静态文件 ────────────────────────────────────────────
_web_dir = Path(__file__).resolve().parent.parent / "web"
_static_dir = _web_dir / "static"
_templates_dir = _web_dir / "templates"

app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ─── 首页 & 健康检查 ───────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页 - 交互式 Web 前端"""
    index_path = _templates_dir / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/health")
async def health_check():
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
