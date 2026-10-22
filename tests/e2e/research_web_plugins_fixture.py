"""Explicit isolated UI fixture: real Web/Plugin/Capability/MCP APIs, mocked DSH/Host.

Never connects to providers, models, the system Keychain, or resident services.
Run with PYTHONPATH=<checkout>:<checkout>/tests/research_web and an empty temp root.
"""

import argparse
import os
from pathlib import Path

import keyring
import uvicorn
from fastapi import Request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18991)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.exists():
        raise RuntimeError("fixture_requires_empty_root")
    root.mkdir(mode=0o700, parents=True)
    os.environ.update(
        RESEARCH_DATA_HOME=str(root), RESEARCH_AUTOMATIONS_ENABLED="0", LOG_DIR=str(root / "logs")
    )
    os.environ.pop("RWB_TENANT_MODE", None)
    values = {}
    keyring.get_password = lambda service, account: values.get((service, account))
    keyring.set_password = lambda service, account, value: values.__setitem__(
        (service, account), value
    )
    keyring.delete_password = lambda service, account: values.pop((service, account), None)
    from test_api import NativeFixture
    from test_mcp_runtime_integration import FakeKeyring
    from test_mcp_runtime_routes import make_service
    from test_plugins import bundle

    from app.research_web.main import create_app
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    native = NativeFixture()
    mcp, _, _, _, installer, _, restarts = make_service(data_root=root)
    original_install = installer.install

    async def install(manifest, environment):
        result = await original_install(manifest, environment)
        destination = root / "mcp-runtime/packages" / manifest.id
        destination.mkdir(mode=0o700, parents=True)
        (destination / "fixture.txt").write_text("Bounded inert package fixture; never executed.")
        return result

    installer.install = install
    research = ResearchService(
        native, Store(root), mcp_runtime=mcp, delivery_keyring_backend=FakeKeyring()
    )

    async def offline():
        return None

    research.frameworks.start = offline
    research.mcp_registry.start = offline
    research.report_workflows.start = offline
    app = create_app(research)

    @app.get("/__fixture/audit")
    def audit():
        return {
            "fixture": True,
            "native_methods": [method for method, _ in native.calls],
            "installations": len(installer.installed),
            "restarts": len(restarts),
            "root": str(root),
        }

    @app.post("/__fixture/busy")
    async def busy(request: Request):
        value = await request.json()
        native.running = {"fixture-running"} if value.get("running") else set()
        return {"running": bool(native.running)}

    (root / "fixture-plugin.zip").write_bytes(
        bundle(
            "plugin.json",
            extra={
                "plugin.json": '{"name":"fixture","version":"1.0.0","extensions":{"research_workbench":{"mcp":{"weather":{"registry_id":"official","server_name":"io.example/weather","server_version":"1.2.3","package_index":0,"environment_names":["WEATHER_TOKEN"]}}}}}'
            },
        )
    )
    (root / "fixture-plugin-v2.zip").write_bytes(bundle("plugin.json", version="2.0.0"))
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
