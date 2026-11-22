"""Loopback-only real Host fixture. Synthetic catalog; external work fails closed."""

import argparse
import inspect
import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

NETWORK_ATTEMPTS = []


def offline_socket_policy(event, args):
    if event == "socket.getaddrinfo":
        host = args[0]
    elif event == "socket.connect":
        address = args[1]
        host = address[0] if isinstance(address, tuple) else None
    else:
        return
    if host not in {None, "127.0.0.1", "::1", "localhost"}:
        NETWORK_ATTEMPTS.append(event)
        raise RuntimeError("offline_fixture_external_network_denied")


# Python audit defense complements the required parent Seatbelt kernel boundary.
sys.addaudithook(offline_socket_policy)
os.environ["RESEARCH_FRAMEWORK_COLLECTORS_ENABLED"] = "0"

import pytest
import uvicorn

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from tests.research_web.test_asset_workspace import NativeFixture, isolated_host_credentials
from tests.research_web.test_watchlist_import import install_catalog


def install_client_fences(patch):
    """Count/reject nonloopback clients; Seatbelt also covers native C networking."""
    import urllib.request

    import httpx
    import requests

    counters = {}

    def wrap(target, method, label, url_index):
        original = getattr(target, method)
        counters[label] = {"nonloopback_attempts": 0, "nonloopback_successes": 0}

        def check(args, kwargs):
            value = kwargs.get("url", args[url_index] if len(args) > url_index else "")
            if hasattr(value, "get_full_url"):
                value = value.get_full_url()
            if urlsplit(str(value)).hostname not in {"127.0.0.1", "::1", "localhost"}:
                counters[label]["nonloopback_attempts"] += 1
                raise RuntimeError("offline_fixture_http_client_denied")

        if inspect.iscoroutinefunction(original):

            async def asynchronous(*args, **kwargs):
                check(args, kwargs)
                return await original(*args, **kwargs)

            patch.setattr(target, method, asynchronous)
        else:

            def synchronous(*args, **kwargs):
                check(args, kwargs)
                return original(*args, **kwargs)

            patch.setattr(target, method, synchronous)

    wrap(httpx.Client, "request", "httpx", 2)
    wrap(httpx.AsyncClient, "request", "httpx_async", 2)
    wrap(requests.Session, "request", "requests", 2)
    wrap(urllib.request.OpenerDirector, "open", "urllib", 1)
    try:
        import curl_cffi.requests as curl_requests
    except ImportError:
        counters["curl_cffi"] = {"available": False}
    else:
        wrap(curl_requests.Session, "request", "curl_cffi", 2)
        wrap(curl_requests.AsyncSession, "request", "curl_cffi_async", 2)
    return counters


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--empty-watchlists", action="store_true")
    parser.add_argument("--current-observation", action="store_true")
    args = parser.parse_args()
    if any(
        key.upper()
        in {
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "FTP_PROXY",
            "NO_PROXY",
            "RESEARCH_CREDENTIAL_HOME",
        }
        for key in os.environ
    ):
        raise RuntimeError("fixture_inherited_proxy_or_credential_home")
    if os.environ.get("RWB_WATCHLIST_SEATBELT") != "1":
        raise RuntimeError("fixture_requires_parent_seatbelt_boundary")
    patch = pytest.MonkeyPatch()
    isolated_host_credentials.__wrapped__(patch)
    counters = install_client_fences(patch)
    credential_attempts = []
    import keyring

    from app.research_web import credential_backend

    def deny_real_credentials(*_args, **_kwargs):
        credential_attempts.append("real_credential_backend")
        raise RuntimeError("offline_fixture_real_credentials_denied")

    for cls in (
        credential_backend.SystemKeyringBackend,
        credential_backend.PrivateFileCredentialBackend,
    ):
        patch.setattr(cls, "__init__", deny_real_credentials)
        for method in ("get_password", "set_password", "delete_password"):
            patch.setattr(cls, method, deny_real_credentials)
    for method in ("get_password", "set_password", "delete_password"):
        patch.setattr(keyring, method, deny_real_credentials)
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
        if method == "llm.models":
            return {"groups": [], "failures": []}
        if method in {"session.send", "session.create", "tool.call", "model.generate"}:
            deny()
        return await rpc(method, payload)

    patch.setattr(service.client, "rpc", guarded)
    install_catalog(service.asset_workspace)
    target = old = None
    if not args.empty_watchlists:
        target = service.asset_workspace.create_watchlist("离线验收自选😀", 15)
        old = service.asset_workspace.add_watchlist_item(
            target["id"], {"asset": "999999.SH", "asset_type": "stock", "name": "保留旧项"}
        )
    observation_id = None
    if args.current_observation:
        session = service.store.create("fingpt", "已存在的离线观察")
        observation_id = str(uuid4())
        now = time.time()
        service.store.data["asset_observations"][observation_id] = {
            "id": observation_id,
            "session_id": session["id"],
            "asset": "600519.SH",
            "asset_type": "stock",
            "source": "auto",
            "status": "complete",
            "created_at": now,
            "updated_at": now,
            "request": {
                "asset": "600519.SH",
                "asset_type": "stock",
                "source": "auto",
                "frequency": "daily",
                "adjustment": "none",
                "section_sources": {},
                "section_ranges": {},
            },
            "blocks": {},
        }
        row = service.store.data["asset_observations"][observation_id]
        for name in ("overview", "valuation", "financials"):
            query = BusinessQuery(
                capability="financials" if name == "financials" else "market_snapshot",
                source="akshare",
                parameters=(
                    {"asset": "600519.SH"}
                    if name == "financials"
                    else {"assets": ["600519.SH"], "asset_type": "stock"}
                ),
            )
            dataset = service.datahub.snapshots.publish(
                session["id"],
                query,
                Result(
                    status="empty",
                    provider_id="akshare",
                    pagination_complete=True,
                    source_url="fixture://local-empty",
                    limitations=["Synthetic empty fixture; no market values or provider execution"],
                ),
                request_query=query,
                authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
            )
            row["blocks"][name] = {
                "status": "empty",
                "loaded_at": now,
                "dataset": service.datahub.detail(session["id"], dataset["dataset_id"]),
                "failure_code": None,
            }
        service.store.save()
    app = create_app(service)

    @app.get("/_fixture/state")
    async def state():
        return {
            "watchlists": service.store.data["watchlists"],
            "external_calls": len(calls),
            "network_attempts": len(NETWORK_ATTEMPTS),
            "proxy_environment_keys": [
                key
                for key in os.environ
                if key.upper()
                in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY", "NO_PROXY"}
            ],
            "credential_home_present": any(
                key.upper() == "RESEARCH_CREDENTIAL_HOME" for key in os.environ
            ),
            "http_client_counters": counters,
            "real_credential_attempts": len(credential_attempts),
            "framework_collectors_enabled": False,
            "target": target["id"] if target else None,
            "current_observation": observation_id,
            "old": old,
            "observations": len(service.store.data["asset_observations"]),
            "sessions": len(service.store.data["sessions"]),
        }

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    args.ready.write_text(
        json.dumps({"origin": origin, "target": target["id"] if target else None})
    )
    try:
        uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
    finally:
        sock.close()
        patch.undo()


if __name__ == "__main__":
    main()
