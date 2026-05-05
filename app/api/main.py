"""AlphaFoundry API"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

# ─── CORS（开发模式允许所有来源）─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 注册路由 ───────────────────────────────────────────
from app.api.routes import assets, scenarios, review, signals, ingest  # noqa: E402

app.include_router(assets.router)
app.include_router(scenarios.router)
app.include_router(review.router)
app.include_router(signals.router)
app.include_router(ingest.router)


# ─── 首页 & 健康检查 ───────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """首页 - 简单HTML"""
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>AlphaFoundry</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 2rem; background: #f5f7fa; }
        h1 { color: #1a365d; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐉 AlphaFoundry</h1>
        <p>本地优先、可企业化的买方投研情报系统</p>
        <h2>API 端点</h2>
        <ul>
            <li><code>POST /api/assets/analyze</code> — 生成资产分析快照</li>
            <li><code>GET /api/assets/{canonical_id}</code> — 查询资产快照</li>
            <li><code>POST /api/scenarios/generate</code> — 生成多情景分析</li>
            <li><code>GET /api/scenarios/{set_id}</code> — 查询情景集</li>
            <li><code>GET /api/review/pending</code> — 列出待审核项</li>
            <li><code>POST /api/review/approve/{item_id}</code> — 批准</li>
            <li><code>POST /api/review/reject/{item_id}</code> — 拒绝</li>
            <li><code>GET /api/review/stats</code> — 审核统计</li>
            <li><code>POST /api/signals/create</code> — 创建信号</li>
            <li><code>GET /api/signals/list</code> — 列出信号</li>
            <li><code>POST /api/signals/validate/{signal_id}</code> — 验证信号</li>
            <li><code>POST /api/signals/promote/{signal_id}</code> — 升级信号状态</li>
            <li><code>POST /api/ingest/text</code> — 摄入文本</li>
            <li><code>POST /api/ingest/file</code> — 上传文件摄入</li>
        </ul>
        <h2>文档</h2>
        <ul>
            <li><a href="/docs" target="_blank">Swagger UI</a></li>
            <li><a href="/redoc" target="_blank">ReDoc</a></li>
            <li><a href="/health">健康检查</a></li>
        </ul>
    </div>
</body>
</html>
    """


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000)
