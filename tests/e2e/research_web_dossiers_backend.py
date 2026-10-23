"""Temporary real Host for dossier browser tests; never starts a real runtime.

Lifespan and collectors are disabled. The login cookie is an explicit test gate,
not a claim about production gateway authentication. Every credential adapter is
ephemeral, outbound sockets are blocked, and all files belong to TemporaryDirectory.
"""

import argparse
import asyncio
import ipaddress
import json
import logging
import os
import socket
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

PROJECT = Path(__file__).resolve().parents[2]
ACCOUNT = "d6b5bef3-23fb-44a4-9dc7-44f45162df41"
COOKIE = "rwb_dossier_http_fixture"
log = logging.getLogger("dossier_http_fixture")


class MemoryCredentials:
    """No secret value is ever supplied or accepted by this fixture."""

    def get_password(self, *_args):
        return None

    def set_password(self, *_args):
        raise RuntimeError("fixture_credential_write_forbidden")

    def delete_password(self, *_args):
        raise RuntimeError("fixture_credential_write_forbidden")


def isolate(root: Path, output: Path):
    """Fail closed on credentials or non-loopback network before Host imports."""
    os.environ.clear()
    os.environ.update(
        PATH=os.defpath,
        PYTHONIOENCODING="utf-8",
        RESEARCH_DATA_HOME=str(root),
        LOG_DIR=str(output / "backend-logs"),
        RESEARCH_AUTOMATIONS_ENABLED="0",
        RESEARCH_MCP_RUNTIME_ENABLED="0",
    )
    (output / "backend-logs").mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(output / "backend-logs" / "fixture.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    original_connect, original_dns = socket.socket.connect, socket.getaddrinfo
    blocked = []

    def loopback(host):
        if host in {None, "localhost"}:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if not isinstance(address, tuple) or not loopback(address[0]):
            blocked.append("non_loopback_connect")
            log.error("fixture_outbound_socket_denied")
            raise RuntimeError("fixture_outbound_socket_denied")
        return original_connect(sock, address)

    def dns(host, *args, **kwargs):
        if not loopback(host):
            blocked.append("non_loopback_dns")
            log.error("fixture_outbound_dns_denied")
            raise RuntimeError("fixture_outbound_dns_denied")
        return original_dns(host, *args, **kwargs)

    socket.socket.connect, socket.getaddrinfo = connect, dns
    import keyring

    memory = MemoryCredentials()
    keyring.get_password = memory.get_password
    keyring.set_password = memory.set_password
    keyring.delete_password = memory.delete_password
    return memory, blocked


def build_fixture(root: Path, output: Path):
    """Return the real app with only transport/credential test doubles."""
    memory, blocked = isolate(root, output)
    sys.path.insert(0, str(PROJECT))
    sys.path.insert(0, str(PROJECT / "tests" / "research_web"))
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from test_api import NativeFixture

    from app.research_web import main as web_main
    from app.research_web.datahub import connections
    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.snapshots import Snapshots
    from app.research_web.mcp_runtime.service import MCPRuntimeService
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    connections.default_credential_backend = lambda: memory
    web_main.default_credential_backend = lambda: memory
    native = NativeFixture()
    research = ResearchService(
        native,
        Store(root / ACCOUNT),
        mcp_runtime=MCPRuntimeService(enabled=False),
        mcp_keyring_backend=memory,
        delivery_keyring_backend=memory,
        auto_probe_on_start=False,
    )
    research.connected = {"mux", "host"}
    research._model_tools_verified = lambda _sid=None: True
    app = web_main.create_app(research)
    app.state.research = research
    source = research.store.create("claw", "离线 HTTP 原始材料")
    source["source_scope"] = ["uploads", "datahub", "web"]
    source_path = research.store.directory(source["id"]) / "inputs" / "source.txt"
    source_path.write_text("FROZEN_BACKEND_HTTP_SOURCE\n" + "真实 Host 只读证据。" * 4000)
    research.store.files(source["id"])
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600519.SH"}
    )
    observed = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    def publish(rows):
        return Snapshots(research.store).publish(
            source["id"],
            query,
            Result(
                rows=rows,
                raw=[b"offline original disclosure"],
                status="snapshot" if rows else "empty",
                as_of=observed,
                pagination_complete=True,
                metadata={"schema_version": "akshare-sina-financial-disclosure-v1"},
            ),
            request_query=query,
            authorization_fingerprint=research.datahub.source_configuration_digest("akshare"),
        )

    snapshots = {
        "empty": publish([]),
        "signal": publish(
            [
                {
                    "asset": "600519.SH",
                    "report_period": "2026-06-30",
                    "publication_date": observed,
                    "publication_precision": "date",
                    "net_profit_yoy": -2.0,
                }
            ]
        ),
    }

    @app.middleware("http")
    async def fixture_login(request, call_next):
        if request.url.path in {"/__fixture/login", "/__fixture/ready"}:
            if request.url.path == "/__fixture/login":
                log.info(
                    "fixture_login_request method=%s origin=%s fetch_site=%s",
                    request.method,
                    request.headers.get("origin"),
                    request.headers.get("sec-fetch-site"),
                )
            response = await call_next(request)
            if request.url.path == "/__fixture/login":
                # Native form navigation with no-referrer serializes Origin as
                # null in Chrome; this test-only login retains same-origin proof.
                response.headers["Referrer-Policy"] = "same-origin"
            return response
        if request.cookies.get(COOKIE) != ACCOUNT:
            return JSONResponse(
                {"error": {"code": "fixture_login_required", "message": "请登录离线验收账号"}},
                status_code=401,
            )
        if request.url.path == "/api/research/claw/projects" and request.method == "GET":
            await asyncio.sleep(0.2)  # Deterministically exercise the draft opening lock.
        return await call_next(request)

    @app.get("/__fixture/ready")
    def ready():
        return {"fixture": True, "lifespan": "off", "account": ACCOUNT}

    @app.get("/__fixture/login")
    def login():
        return HTMLResponse(
            '<!doctype html><html lang="zh-CN"><title>离线验收登录</title>'
            '<h1>仅本地临时研究账号</h1><form method="post">'
            '<label>验收账号<input name="username" value="fixture-researcher"></label>'
            '<button type="submit">进入离线验收</button></form></html>'
        )

    @app.post("/__fixture/login")
    async def authenticate(request: Request):
        fields = parse_qs((await request.body()).decode("utf-8"))
        if fields.get("username") != ["fixture-researcher"]:
            return JSONResponse({"error": "fixture_identity_invalid"}, status_code=401)
        response = RedirectResponse("/#/assets?view=dossiers", status_code=303)
        response.set_cookie(COOKIE, ACCOUNT, httponly=True, samesite="strict")
        log.info("fixture_account_entered")
        return response

    @app.get("/__fixture/bootstrap")
    def bootstrap():
        return {
            "fixture": True,
            "account": ACCOUNT,
            "source_session_id": source["id"],
            "source_path": "inputs/source.txt",
            "datasets": {key: value["dataset_id"] for key, value in snapshots.items()},
        }

    @app.get("/__fixture/state")
    def state():
        with research.dossiers.metadata.connection() as connection:
            table = (
                connection
                and connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='handoffs'"
                ).fetchone()
            )
            bindings = (
                connection.execute(
                    "SELECT count(*) FROM handoffs WHERE session_id IS NOT NULL"
                ).fetchone()[0]
                if table
                else 0
            )
        return {
            "fixture": True,
            "native_prompt_calls": sum(method == "session.prompt" for method, _ in native.calls),
            "bound_receipts": bindings,
            "blocked_outbound": blocked,
            "automations": len(research.store.data.get("automations", {})),
            "sessions": [
                {"id": row["id"], "mode": row["mode"]}
                for row in research.store.data["sessions"].values()
            ],
        }

    @app.post("/__fixture/revoke")
    def revoke():
        research.store.session(source["id"])["source_scope"] = []
        research.store.save()
        log.info("fixture_source_scope_revoked")
        return {"revoked": True}

    @app.post("/__fixture/restore")
    def restore():
        research.store.session(source["id"])["source_scope"] = ["uploads", "datahub", "web"]
        research.store.save()
        log.info("fixture_source_scope_restored")
        return {"restored": True}

    @app.post("/__fixture/read-bound")
    async def read_bound(request: Request):
        body = await request.json()
        result = research.dossiers.read_handle(body["session_id"], body["handle"])
        return {
            "state": result.get("state"),
            "contains_fixture_source": "FROZEN_BACKEND_HTTP_SOURCE" in result.get("content", ""),
        }

    log.info("fixture_ready lifespan=off collectors=off mcp=disabled")
    return app, research, native


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="rwb-dossier-http-") as directory:
            app, _research, _native = build_fixture(Path(directory), args.output)
            if args.self_check:
                from fastapi.testclient import TestClient

                client = TestClient(app, cookies={COOKIE: ACCOUNT})
                try:
                    response = client.get("/__fixture/bootstrap")
                    response.raise_for_status()
                    state = client.get("/__fixture/state").json()
                    assert state["native_prompt_calls"] == state["bound_receipts"] == 0
                    assert state["blocked_outbound"] == []
                    assert not hasattr(app.state, "hot")
                    print(
                        json.dumps({"fixture": True, "self_check": "passed", "state": state}),
                        flush=True,
                    )
                finally:
                    client.close()
                return
            import uvicorn

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                print("RWB_DOSSIER_HTTP_READY " + json.dumps({"port": port}), flush=True)
                uvicorn.Server(
                    uvicorn.Config(app, lifespan="off", access_log=False, log_level="warning")
                ).run(sockets=[listener])
    except Exception as exc:
        log.exception("fixture_failed error_type=%s", type(exc).__name__)
        raise


if __name__ == "__main__":
    main()
