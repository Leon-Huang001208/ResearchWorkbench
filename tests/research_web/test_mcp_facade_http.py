"""Real loopback Gateway + SDK bearer dispatch with isolated synthetic accounts."""

import asyncio
import concurrent.futures
import hashlib
import json
import socket
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import uvicorn
from test_mcp_facade_oauth import PASSWORD, authorize, exchange, params

from app.research_web.multiuser.accounts import AccountError, AccountStore
from app.research_web.multiuser.gateway import create_gateway
from app.research_web.multiuser.runtime import RuntimeErrorSafe


@pytest.fixture
def environment(tmp_path):
    accounts = AccountStore(tmp_path / "accounts")
    users = [accounts.create_user(f"user{i:02d}", PASSWORD) for i in range(10)]
    sessions = [accounts.login(u.username, PASSWORD)[0] for u in users]
    state = SimpleNamespace(
        calls=[], busy=False, ack=True, mutation=None, assets={}, allocations=[]
    )

    class Pool:
        async def backend_for(self, user_id):
            state.allocations.append(user_id)
            if state.busy:
                raise RuntimeErrorSafe("capacity_exceeded")
            return SimpleNamespace(
                url="http://" + user_id + ".invalid", key="" if user_id == users[0].id else user_id
            )

        async def close(self):
            pass

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    app = create_gateway(accounts, Pool(), origin=origin, mcp_enabled=True)
    facade = app.state.mcp_facade

    async def respond(request):
        state.calls.append(request)
        assert request.method == "GET"
        assert "cookie" not in request.headers and "authorization" not in request.headers
        assert "x-client-default" not in request.headers
        assert request.headers["origin"] == f"http://{request.url.host}"
        if request.url.path == "/api/research/data/catalog":
            return httpx.Response(
                200,
                json={"frozen_read_protocol": "v1"} if state.ack else {"old": True},
                headers={"X-RWB-Frozen-Read": "v1"} if state.ack else {},
            )
        if state.mutation:
            state.mutation()
        raw = state.assets.get((request.url.host, request.url.path))
        return httpx.Response(
            200 if raw is not None else 404,
            content=raw or b"",
            headers={"X-RWB-Frozen-Read": "v1", "Set-Cookie": "injected=forbidden"},
        )

    # Only the backend transport is synthetic. Gateway, sockets, AS, SDK auth,
    # ContextVars, manager, typed tools and final serialization are production.
    asyncio.run(facade.client.aclose())
    facade.client = httpx.AsyncClient(
        transport=httpx.MockTransport(respond),
        trust_env=False,
        headers={"X-Client-Default": "must-not-forward"},
        cookies={"automatic": "must-not-forward"},
        auth=("synthetic", "must-not-forward"),
    )
    # Registered closures reference the original adapter; change its client via
    # the owned server assembly seam, before any application request.
    facade.backend.client = facade.client
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 8
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("gateway_start_failed")
            time.sleep(0.01)
        with httpx.Client(base_url=origin, trust_env=False, timeout=10) as client:
            state.env = (client, facade.store, users, sessions, [time.time()])
            state.app = app
            yield state
    finally:
        server.should_exit = True
        thread.join(8)
        sock.close()
        assert not thread.is_alive()


def approved(state, index=0, kind="source", raw=None):
    client, store, users, *_ = state.env
    sid, oid = str(uuid4()), ("a" * 24 if kind == "source" else str(uuid4()))
    raw = raw if raw is not None else f"synthetic user {index}".encode()
    host = users[index].id + ".invalid"
    if kind == "source":
        path = f"/api/research/sessions/{sid}/files/{oid}/download"
        state.assets[(host, path)] = raw
    else:
        rows = raw
        raw = json.dumps(
            {
                "dataset_id": oid,
                "files": [{"name": "rows.json", "sha256": hashlib.sha256(rows).hexdigest()}],
                "as_of": None,
                "missing": ["source date unknown"],
            }
        ).encode()
        base = f"/api/research/sessions/{sid}/datasets/{oid}/files"
        state.assets[(host, base + "/rows.json")] = rows
        state.assets[(host, base + "/manifest.json")] = raw
    material = store.approve_material(
        user_id=users[index].id,
        context_id=sid,
        kind=kind,
        object_id=oid,
        sha256=hashlib.sha256(raw).hexdigest(),
        classification="synthetic",
    )
    token = exchange(client, authorize(state.env, index=index, material_ids=[material.id])).json()[
        "access_token"
    ]
    return token, material


def rpc(state, token=None, method="tools/list", arguments=None, version="2025-11-25", headers=None):
    client = state.env[0]
    h = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": version}
    if token:
        h["Authorization"] = "Bearer " + token
    h.update(headers or {})
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if arguments is not None:
        payload["params"] = arguments
    return client.post("/mcp", json=payload, headers=h)


def call(state, token, name, **args):
    return rpc(state, token, "tools/call", {"name": name, "arguments": args})


def value(response):
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def test_gateway_sdk_bearer_and_discovery(environment):
    s = environment
    token, _ = approved(s)
    metadata = s.env[0].get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["resource"] == s.env[1].resource
    assert metadata["authorization_servers"] == [s.env[1].issuer]
    for headers in ({}, {"Cookie": "rwb_session=" + s.env[3][0]}):
        response = rpc(s, headers=headers)
        assert response.status_code == 401
        assert "resource_metadata=" in response.headers["www-authenticate"]
    result = rpc(s, token).json()["result"]["tools"]
    assert {t["name"] for t in result} == {
        "rwb_capabilities_list",
        "rwb_datasets_list",
        "rwb_dataset_read",
        "rwb_source_read",
    }
    assert all(
        t["annotations"]["readOnlyHint"]
        and not t["annotations"]["openWorldHint"]
        and not t["annotations"]["destructiveHint"]
        for t in result
    )
    assert all(t["inputSchema"]["additionalProperties"] is False for t in result)
    assert value(call(s, token, "rwb_capabilities_list"))["execution"] is False
    assert len(value(call(s, token, "rwb_datasets_list"))["items"]) == 1
    assert s.allocations == [] and s.calls == []


def test_initialize_newer_offer_and_version_gate(environment):
    s = environment
    token, _ = approved(s)
    for offered in ("2025-11-25", "2026-07-28", "2027-01-01"):
        response = rpc(
            s,
            token,
            "initialize",
            {
                "protocolVersion": offered,
                "capabilities": {},
                "clientInfo": {"name": "isolated", "version": "1"},
            },
            version=offered,
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["protocolVersion"] == "2025-11-25"
        assert set(response.json()["result"]["capabilities"]) == {"tools"}
    assert rpc(s, token, version="2026-07-28").status_code == 400
    invalid = rpc(
        s,
        token,
        "initialize",
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {},
            "clientInfo": {"name": "isolated", "version": "1"},
        },
        version="untrusted-header",
    )
    assert invalid.status_code == 400 and invalid.json()["id"] == 1
    notification = s.env[0].post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={
            "Authorization": "Bearer " + token,
            "MCP-Protocol-Version": "2025-11-25",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert notification.status_code == 202
    for method in ("prompts/list", "resources/list", "resources/read", "tasks/list", "skills/list"):
        response = rpc(s, token, method, {})
        assert response.status_code == 200
        assert response.json()["error"]["code"] == -32601


def test_four_sequential_accounts_and_ten_concurrent_same_client(environment):
    s = environment
    owned = [approved(s, i) for i in range(10)]

    def read(index):
        token, m = owned[index]
        result = value(
            call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
        )
        assert result["text"] == f"synthetic user {index}"
        assert result["provenance"]["status"] == "missing"
        assert result["original_sha256"] == m.sha256
        foreign = owned[(index + 1) % 10][1]
        denied = call(
            s, token, "rwb_source_read", context_id=foreign.context_id, file_id=foreign.object_id
        ).json()["result"]
        assert denied["isError"] and "synthetic user" not in json.dumps(denied)

    for i in range(4):
        read(i)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(read, range(10)))
    assert set(s.allocations) == {u.id for u in s.env[2]}
    for request in s.calls:
        expected = request.url.host.removesuffix(".invalid")
        assert request.headers.get("x-rwb-tenant-gateway-key", "") == (
            "" if expected == s.env[2][0].id else expected
        )


def test_dataset_digest_pagination_and_source_fragment(environment):
    s = environment
    token, m = approved(s, kind="dataset", raw=json.dumps([{"n": i} for i in range(105)]).encode())
    result = value(
        call(s, token, "rwb_dataset_read", context_id=m.context_id, dataset_id=m.object_id)
    )
    assert len(result["items"]) == 100 and result["partial"] and result["total"] == 105
    assert result["manifest_sha256"] == m.sha256 != result["rows_sha256"]
    token, m = approved(s, raw=("汉" * 12001).encode())
    result = value(call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id))
    assert len(result["text"]) == 12000 and result["partial"]
    assert result["original_sha256"] != result["fragment_sha256"]


def test_legacy_protocol_and_busy_fail_before_material_get(environment):
    s = environment
    token, m = approved(s)
    s.ack = False
    response = call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
    assert response.json()["result"]["isError"]
    assert len(s.calls) == 1 and s.calls[0].url.path.endswith("/catalog")
    s.busy = True
    response = call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
    assert "capacity_exceeded" in response.text and len(s.calls) == 1


def test_material_changes_revocation_midread_and_hash_failure(environment):
    s = environment
    token, m = approved(s)
    s.mutation = lambda: s.env[1].revoke_material(m.id)
    response = call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
    assert response.json()["result"]["isError"] and "synthetic user" not in response.text
    s.mutation = None
    token, m = approved(s)
    for key in list(s.assets):
        if m.context_id in key[1]:
            s.assets[key] = b"changed secret text"
    response = call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
    assert "frozen_material_changed" in response.text and "changed secret text" not in response.text


def test_mcp_caps_paths_and_authorization_store_503(environment, monkeypatch):
    s = environment
    token, m = approved(s)
    assert call(
        s, token, "rwb_source_read", context_id="../../private", file_id=m.object_id
    ).json()["result"]["isError"]
    assert s.allocations == []
    client = s.env[0]
    response = client.post(
        "/mcp",
        content=iter([b" " * 40000, b" " * 40000]),
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 413
    assert client.post("/mcp/elsewhere", json={}).status_code == 403

    def failed(*args, **kwargs):
        raise AccountError("account_store_failed", 503)

    monkeypatch.setattr(s.env[1], "verify_access", failed)
    response = rpc(s, token)
    assert response.status_code == 503 and "temporarily_unavailable" in response.text


def test_login_resume_and_enabled_applications(environment):
    s = environment
    client, store, *_ = s.env
    response = client.get("/authorize", params=params())
    assert response.status_code == 302 and response.headers["location"].startswith(
        "/auth?return_to="
    )
    target = "/authorize?" + str(httpx.QueryParams(params()))
    response = client.post(
        "/api/server/login",
        json={"username": "user00", "password": PASSWORD, "return_to": target},
        headers={"Origin": store.issuer},
    )
    assert response.json()["return_to"] == target
    assert client.get("/api/server/me").json()["user"]["mcp_readonly_enabled"] is True
    assert client.get("/auth", params={"return_to": target}).headers["location"] == target
    assert client.get(target).headers["location"].startswith("/mcp/consent?")
    response = client.post(
        "/api/server/login",
        json={"username": "user00", "password": PASSWORD, "return_to": "https://evil.invalid/"},
        headers={"Origin": store.issuer},
    )
    assert "return_to" not in response.json()


def test_current_token_binding_revocation_and_gateway_fences(environment, monkeypatch, tmp_path):
    s = environment
    token, m = approved(s)
    store = s.env[1]
    grant = store.verify_access(token, resource=store.resource)
    assert rpc(s, "invalid-token").status_code == 401
    for column, wrong, restore in [
        ("issuer", "https://wrong.invalid", store.issuer),
        ("resource", "https://wrong.invalid/mcp", store.resource),
        ("scope", "write", "rwb.read"),
        ("expires_at", 1, grant.expires_at),
    ]:
        with store.accounts._connection() as db:
            db.execute(
                f"UPDATE mcp_oauth_grants SET {column}=? WHERE id=?", (wrong, grant.grant_id)
            )
        assert rpc(s, token).status_code == 401
        with store.accounts._connection() as db:
            db.execute(
                f"UPDATE mcp_oauth_grants SET {column}=? WHERE id=?", (restore, grant.grant_id)
            )
    s.mutation = lambda: store.revoke_grant(grant.grant_id, user_id=grant.user_id)
    result = call(s, token, "rwb_source_read", context_id=m.context_id, file_id=m.object_id)
    assert result.json()["result"]["isError"] and "synthetic user" not in result.text
    assert rpc(s, token).status_code == 401
    s.mutation = None
    token, _ = approved(s)
    assert rpc(s, token, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert rpc(s, token, headers={"Host": "evil.invalid"}).status_code == 403
    fence = tmp_path / "maintenance"
    fence.touch()
    monkeypatch.setattr(s.app.state.pool, "maintenance_path", fence, raising=False)
    assert rpc(s, token).status_code == 503
    monkeypatch.setattr(s.app.state.pool, "deployment_path", fence, raising=False)
    assert s.env[0].get("/.well-known/oauth-protected-resource/mcp").status_code == 503


def test_sdk_output_caps_and_forbidden_arguments(environment):
    s = environment
    token, m = approved(
        s, kind="dataset", raw=json.dumps([{"text": "SENSITIVE_PREFIX" + "x" * 250000}]).encode()
    )
    response = call(s, token, "rwb_dataset_read", context_id=m.context_id, dataset_id=m.object_id)
    assert response.json()["result"]["isError"] and "response_too_large" in response.text
    assert "SENSITIVE_PREFIX" not in response.text
    count = len(s.calls)
    response = call(
        s,
        token,
        "rwb_dataset_read",
        context_id=m.context_id,
        dataset_id=m.object_id,
        url="https://evil.invalid",
        headers={"Authorization": "other"},
    )
    assert response.json()["error"]["code"] == -32602 and len(s.calls) == count
    assert call(
        s, token, "rwb_dataset_read", context_id=m.context_id, dataset_id=m.object_id, limit=501
    ).json()["result"]["isError"]


def test_browser_oauth_headers_survive_gateway(environment):
    s = environment
    client, _store, _, sessions, _ = s.env
    headers = {"Cookie": "rwb_session=" + sessions[0]}
    response = client.get("/authorize", params=params(), headers=headers)
    page = client.get(response.headers["location"], headers=headers)
    assert page.status_code == 200
    assert page.headers["Referrer-Policy"] == "same-origin"
    assert (
        "form-action 'self' http://127.0.0.1:43210/callback"
        in page.headers["Content-Security-Policy"]
    )
    page = client.get("/mcp/applications", headers=headers)
    assert page.headers["Referrer-Policy"] == "same-origin"
    assert "form-action 'self'" in page.headers["Content-Security-Policy"]
    assert client.get("/auth").headers["Referrer-Policy"] == "no-referrer"
    assert (
        client.post("/mcp/consent", data={}, headers={**headers, "Origin": "null"}).status_code
        == 403
    )
