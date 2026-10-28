"""Loopback-only real Host fixture. Synthetic catalog; external work fails closed."""

import argparse
import json
import socket
from pathlib import Path

import pytest
import uvicorn

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from tests.research_web.test_asset_workspace import NativeFixture, isolated_host_credentials
from tests.research_web.test_watchlist_import import install_catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    args = parser.parse_args()
    patch = pytest.MonkeyPatch()
    isolated_host_credentials.__wrapped__(patch)
    service = ResearchService(NativeFixture(), Store(args.root))
    calls = []

    def deny(*_args, **_kwargs):
        calls.append("forbidden_external_call")
        raise RuntimeError("offline_fixture_external_call_denied")

    for obj, names in [
        (service.datahub, ["asset_directory", "query"]),
        (service.datahub.connections, ["read_source_secret"]),
    ]:
        for name in names:
            patch.setattr(obj, name, deny)
    patch.setattr(service.asset_workspace.directory, "loader", deny)
    rpc = service.client.rpc

    async def guarded(method, payload):
        if method in {"session.send", "session.create", "tool.call", "model.generate"}:
            deny()
        return await rpc(method, payload)

    patch.setattr(service.client, "rpc", guarded)
    install_catalog(service.asset_workspace)
    target = service.asset_workspace.create_watchlist("离线验收自选😀", 15)
    old = service.asset_workspace.add_watchlist_item(
        target["id"], {"asset": "999999.SH", "asset_type": "stock", "name": "保留旧项"}
    )
    app = create_app(service)

    @app.get("/_fixture/state")
    async def state():
        return {
            "watchlists": service.store.data["watchlists"],
            "external_calls": len(calls),
            "target": target["id"],
            "old": old,
            "observations": len(service.store.data["asset_observations"]),
            "sessions": len(service.store.data["sessions"]),
        }

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    args.ready.write_text(json.dumps({"origin": origin, "target": target["id"]}))
    try:
        uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
    finally:
        sock.close()
        patch.undo()


if __name__ == "__main__":
    main()
