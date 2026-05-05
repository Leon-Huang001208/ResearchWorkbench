
"""AlphaFoundry API"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
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


@app.get("/", response_class=HTMLResponse)
async def index():
    """首页 - 简单HTML"""
    return """
&lt;!DOCTYPE html&gt;
&lt;html&gt;
&lt;head&gt;
    &lt;meta charset="UTF-8"&gt;
    &lt;title&gt;AlphaFoundry&lt;/title&gt;
    &lt;style&gt;
        body { font-family: Arial, sans-serif; padding: 2rem; background: #f5f7fa; }
        h1 { color: #1a365d; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    &lt;/style&gt;
&lt;/head&gt;
&lt;body&gt;
    &lt;div class="container"&gt;
        &lt;h1&gt;🐉 AlphaFoundry&lt;/h1&gt;
        &lt;p&gt;本地优先、可企业化的买方投研情报系统&lt;/p&gt;
        &lt;h2&gt;快速开始&lt;/h2&gt;
        &lt;ul&gt;
            &lt;li&gt;运行基础测试: &lt;code&gt;python examples/test_simple.py&lt;/code&gt;&lt;/li&gt;
            &lt;li&gt;运行信号测试: &lt;code&gt;python examples/test_signal_lab_simple.py&lt;/code&gt;&lt;/li&gt;
            &lt;li&gt;CLI帮助: &lt;code&gt;af --help&lt;/code&gt;&lt;/li&gt;
        &lt;/ul&gt;
        &lt;h2&gt;文档&lt;/h2&gt;
        &lt;ul&gt;
            &lt;li&gt;&lt;a href="https://github.com/your-repo" target="_blank"&gt;README.md&lt;/a&gt;&lt;/li&gt;
            &lt;li&gt;&lt;a href="https://github.com/your-repo" target="_blank"&gt;docs/REFERENCE.md&lt;/a&gt;&lt;/li&gt;
        &lt;/ul&gt;
    &lt;/div&gt;
&lt;/body&gt;
&lt;/html&gt;
    """


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000)
