
"""AlphaFoundry API"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 把项目根目录加入path
script_path = Path(__file__).resolve()
project_root = script_path.parent.parent.parent  # app/api/main.py → project root
sys.path.insert(0, str(project_root))

from core.observability import get_logger, configure_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理"""
    configure_logging()
    logger.info("AlphaFoundry API starting up...")
    yield
    logger.info("AlphaFoundry API shutting down...")


app = FastAPI(
    title="AlphaFoundry API",
    description="本地优先、可企业化的买方投研情报系统",
    lifespan=lifespan,
)

# 挂载静态文件和模板
static_dir = project_root / "app" / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
templates_dir = project_root / "app" / "web" / "templates"
templates_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, reload=True)
