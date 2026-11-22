"""Owned loopback data UI acceptance only; no models, schedulers or host secrets.

Credentials are temporary in-memory values and never written to evidence files.
The real Host/DataHub/providers and warehouse driver run normally. Native DSH
transport is deliberately unavailable for model generation in this fixture.
"""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18993)
    options = parser.parse_args()
    root = options.root.absolute()
    if root.exists():
        raise RuntimeError("fixture_requires_new_owned_root")
    root.mkdir(mode=0o700)
    os.environ.update(
        RESEARCH_PROJECT_ROOT=str(root),
        RESEARCH_RUN_MODE="web-prod",
        RESEARCH_AUTOMATIONS_ENABLED="0",
    )
    project = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project / "tests" / "research_web"))
    import keyring
    import uvicorn
    from starlette.responses import HTMLResponse
    from test_api import NativeFixture

    from app.research_web.client import RuntimeFailure
    from app.research_web.main import create_app
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    values = {}
    keyring.get_password = lambda service, account: values.get((service, account))
    keyring.set_password = lambda service, account, value: values.__setitem__(
        (service, account), value
    )
    keyring.delete_password = lambda service, account: values.pop((service, account), None)

    class NoModels(NativeFixture):
        async def rpc(self, method, payload):
            if method == "session.prompt":
                raise RuntimeFailure("隔离数据验证实例禁止模型生成", "fixture_models_disabled")
            return await super().rpc(method, payload)

    async def offline():
        return None

    service = ResearchService(NoModels(), Store(root / "host"), auto_probe_on_start=False)
    service.frameworks.start = offline
    service.mcp_registry.start = offline
    service.report_workflows.start = offline
    app = create_app(service)

    @app.middleware("http")
    async def isolated_banner(request, call_next):
        if request.url.path == "/":
            html = (project / "app" / "research_web" / "ui" / "index.html").read_text()
            banner = '<aside class="notice warning" role="status">隔离数据验证页：不连接现有服务；禁止模型生成。凭据仅保存在本进程临时内存，关闭即清除；请勿把凭据发到聊天中。</aside>'
            return HTMLResponse(html.replace("<body>", "<body>" + banner))
        return await call_next(request)

    uvicorn.run(app, host="127.0.0.1", port=options.port, log_level="warning")


if __name__ == "__main__":
    main()
