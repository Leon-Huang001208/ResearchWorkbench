"""Opt-in public DataHub execution reuses real stores/routes, without DSH or network."""

import asyncio
import base64
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.applications import Starlette

from app.research_web.client import ExternalExecutionClient
from app.research_web.datahub.routes import router as data_router
from app.research_web.main import create_app
from app.research_web.mcp_facade.authorization_store import AuthorizationStore
from app.research_web.mcp_facade.oauth import OAuthProvider, create_oauth_routes
from app.research_web.multiuser.accounts import AccountError, AccountStore
from app.research_web.multiuser.gateway import create_gateway
from app.research_web.multiuser.runtime import RuntimeConfig, RuntimePool
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError
from app.research_web.workbench import router

SCOPES = ["rwb.read", "rwb.data.query"]
ORIGIN = "http://127.0.0.1:18443"
WK_ORIGIN = "http://127.0.0.1:18181"
PASSWORD = "correct horse battery staple"
VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)


def oauth(tmp_path):
    accounts = AccountStore(tmp_path / "accounts")
    user = accounts.create_user("alice", PASSWORD)
    store = AuthorizationStore(accounts, issuer=ORIGIN, weknora_oauth_origin=WK_ORIGIN)
    return accounts, user, store


def grant(store, user, scopes=SCOPES):
    request = store.create_request(
        user_id=user.id,
        client_id="rwb-weknora",
        scopes=scopes,
        redirect_uri=WK_ORIGIN + "/api/v1/mcp-oauth/callback",
        code_challenge=CHALLENGE,
        code_challenge_method="S256",
    )
    code = store.issue_code(request.id, user_id=user.id, material_ids=[])
    return store.exchange_code(
        code,
        client_id="rwb-weknora",
        code_verifier=VERIFIER,
        redirect_uri=WK_ORIGIN + "/api/v1/mcp-oauth/callback",
    )


def test_data_scope_is_explicit_persistent_and_revocable(tmp_path):
    accounts, user, store = oauth(tmp_path)
    readonly = grant(store, user, ["rwb.read"])
    tokens = grant(store, user, list(reversed(SCOPES)))
    reopened = AuthorizationStore(accounts, issuer=ORIGIN, weknora_oauth_origin=WK_ORIGIN)
    record = reopened.verify_access(tokens.access_token, resource=store.resource)
    assert record.scopes == tuple(SCOPES)
    assert reopened.verify_access(readonly.access_token, resource=store.resource).scopes == (
        "rwb.read",
    )
    refreshed = reopened.rotate_refresh(
        tokens.refresh_token, client_id="rwb-weknora", scopes=SCOPES
    )
    assert refreshed.scope == "rwb.read rwb.data.query"
    reopened.revoke_grant(record.grant_id, user_id=user.id)
    with pytest.raises(AccountError):
        reopened.verify_access(refreshed.access_token, resource=store.resource)


def test_refresh_cannot_upgrade_an_old_readonly_grant(tmp_path):
    _, user, store = oauth(tmp_path)
    tokens = grant(store, user, ["rwb.read"])
    with pytest.raises(AccountError, match="invalid_scope"):
        store.rotate_refresh(tokens.refresh_token, client_id="rwb-weknora", scopes=SCOPES)
    assert store.rotate_refresh(tokens.refresh_token, client_id="rwb-weknora").scope == "rwb.read"


def test_data_scope_requires_base_read_and_registered_weknora_client(tmp_path):
    _, user, store = oauth(tmp_path)
    for client_id, scopes, callback in (
        ("rwb-weknora", ["rwb.data.query"], WK_ORIGIN + "/api/v1/mcp-oauth/callback"),
        ("rwb-codex-native", SCOPES, "http://127.0.0.1/callback"),
    ):
        with pytest.raises(AccountError, match="invalid_scope"):
            store.create_request(
                user_id=user.id,
                client_id=client_id,
                scopes=scopes,
                redirect_uri=callback,
                code_challenge=CHALLENGE,
                code_challenge_method="S256",
            )


def test_oauth_http_consent_names_public_provider_execution(tmp_path):
    accounts, user, store = oauth(tmp_path)
    session, _ = accounts.login(user.username, PASSWORD)
    with TestClient(
        Starlette(routes=create_oauth_routes(OAuthProvider(store))), base_url=ORIGIN
    ) as client:
        metadata = client.get("/.well-known/oauth-authorization-server").json()
        assert metadata["scopes_supported"] == [*SCOPES, "rwb.data.configured"]
        response = client.get(
            "/authorize",
            params={
                "client_id": "rwb-weknora",
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "redirect_uri": WK_ORIGIN + "/api/v1/mcp-oauth/callback",
                "code_challenge": CHALLENGE,
                "code_challenge_method": "S256",
            },
            headers={"Cookie": "rwb_session=" + session},
            follow_redirects=False,
        )
        assert response.status_code == 302
        page = client.get(
            response.headers["location"], headers={"Cookie": "rwb_session=" + session}
        )
        assert page.status_code == 200
        assert "FRED" in page.text and "BLS" in page.text and "快照" in page.text
        request_id = parse_qs(urlsplit(response.headers["location"]).query)["request_id"][0]
        denied = client.post(
            "/mcp/consent",
            data={"request_id": request_id, "decision": "deny"},
            headers={"Cookie": "rwb_session=" + session, "Origin": ORIGIN},
            follow_redirects=False,
        )
        assert "error=access_denied" in denied.headers["location"]
        assert store.list_grants(user.id) == []
        # A fresh explicit consent must survive the actual SDK code/token and
        # refresh routes, not only AuthorizationStore's direct Python methods.
        fresh = client.get(
            "/authorize",
            params={
                "client_id": "rwb-weknora",
                "response_type": "code",
                "scope": " ".join(reversed(SCOPES)),
                "redirect_uri": WK_ORIGIN + "/api/v1/mcp-oauth/callback",
                "code_challenge": CHALLENGE,
                "code_challenge_method": "S256",
            },
            headers={"Cookie": "rwb_session=" + session},
            follow_redirects=False,
        )
        request_id = parse_qs(urlsplit(fresh.headers["location"]).query)["request_id"][0]
        allowed = client.post(
            "/mcp/consent",
            data={"request_id": request_id, "decision": "allow"},
            headers={"Cookie": "rwb_session=" + session, "Origin": ORIGIN},
            follow_redirects=False,
        )
        code = parse_qs(urlsplit(allowed.headers["location"]).query)["code"][0]
        exchanged = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "rwb-weknora",
                "code": code,
                "code_verifier": VERIFIER,
                "redirect_uri": WK_ORIGIN + "/api/v1/mcp-oauth/callback",
            },
        )
        assert exchanged.status_code == 200, exchanged.text
        assert exchanged.json()["scope"] == " ".join(SCOPES)
        refreshed = client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": "rwb-weknora",
                "refresh_token": exchanged.json()["refresh_token"],
                "scope": " ".join(SCOPES),
            },
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["scope"] == " ".join(SCOPES)


def host(tmp_path):
    service = ResearchService(ExternalExecutionClient(), Store(tmp_path / "host"))
    app = FastAPI()
    app.state.research = service
    app.include_router(router)
    app.include_router(data_router)

    @app.exception_handler(StoreError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)

    return service, app


def fred_query(series="DFF"):
    return {
        "capability": "external_data",
        "source": "ext_fred",
        "allow_fallback": False,
        "purpose": "research",
        "quality": "strict",
        "refresh": True,
        "parameters": {
            "dataset": "series",
            "arguments_json": '{"params":{"series":"'
            + series
            + '"},"query":{"cosd":"2024-01-02","coed":"2024-01-08"}}',
        },
    }


def test_data_context_creation_uses_store_only_and_is_grant_bound(tmp_path):
    service, app = host(tmp_path)
    with TestClient(app) as client:
        payload = {"grant_id": "00000000-0000-0000-0000-000000000001"}
        one = client.post("/api/research/data/contexts", json=payload)
        two = client.post("/api/research/data/contexts", json=payload)
        assert one.status_code == 201, one.text
        assert two.status_code == 200
        assert one.json()["session_id"] == two.json()["session_id"]
        sid = one.json()["session_id"]
        row = service.store.session(sid)
        assert row["created"] is False and row["source_scope"] == ["datahub"]
        assert row["mcp_data_grant_id"] == payload["grant_id"]
        other = client.post(
            "/api/research/data/contexts", json={"grant_id": "00000000-0000-0000-0000-000000000002"}
        )
        assert other.json()["session_id"] != sid


def test_query_idempotency_rejects_changed_payload_without_second_fetch(tmp_path):
    service, app = host(tmp_path)
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, text="observation_date,DFF\n2024-01-02,5.33\n2024-01-03,.\n")

    service.datahub.transport = httpx.MockTransport(provider)
    with TestClient(app) as client:
        sid = service.store.create("fingpt", "DataHub only")["id"]
        body = {"session_id": sid, "section": "market", "query": fred_query()}
        headers = {"Idempotency-Key": "mcp-public-query-0001"}
        first = client.post("/api/research/data/queries", json=body, headers=headers)
        second = client.post("/api/research/data/queries", json=body, headers=headers)
        assert first.status_code == second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        altered = {**body, "query": fred_query("SOFR")}
        conflict = client.post("/api/research/data/queries", json=altered, headers=headers)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "data_query_idempotency_conflict"
        assert len(calls) <= 1


def test_cancel_queued_query_is_terminal_without_replaying_provider(tmp_path):
    service, app = host(tmp_path)
    started = asyncio.Event()

    async def provider(_request):
        started.set()
        await asyncio.Event().wait()

    service.datahub.transport = httpx.MockTransport(provider)
    with TestClient(app) as client:
        sid = service.store.create("fingpt", "DataHub cancel")["id"]
        body = {"session_id": sid, "section": "market", "query": fred_query()}
        first = client.post(
            "/api/research/data/queries", json=body, headers={"Idempotency-Key": "mcp-cancel-0001"}
        )
        query_id = first.json()["id"]
        cancelled = client.post(f"/api/research/data/queries/{query_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert client.get(f"/api/research/data/queries/{query_id}").json()["status"] == "cancelled"
        replay = client.post(
            "/api/research/data/queries", json=body, headers={"Idempotency-Key": "mcp-cancel-0001"}
        )
        assert replay.json()["id"] == query_id and replay.json()["status"] == "cancelled"


def test_public_query_builder_uses_fixed_provider_contracts_and_rejects_injection():
    from app.research_web.mcp_facade.backend import public_data_query

    fred = public_data_query("ext_fred", "DFF", "2024-01-02", "2024-01-08")
    bls = public_data_query("ext_bls", "CUUR0000SA0", "2024-01-01", "2024-12-31")
    assert fred.source == "ext_fred" and bls.source == "ext_bls"
    assert fred.allow_fallback is False and fred.refresh is True
    assert "registrationkey" not in bls.parameters["arguments_json"]
    for args in (
        ("wind", "DFF", "2024-01-01", "2024-01-08"),
        ("ext_fred", "https://evil.invalid", "2024-01-01", "2024-01-08"),
        ("ext_fred", "DFF", "2024-02-01", "2024-01-08"),
    ):
        with pytest.raises(ValueError):
            public_data_query(*args)


@pytest.fixture
def gateway(tmp_path):
    accounts, user, auth = oauth(tmp_path)
    service, backend_app = host(tmp_path)
    state = SimpleNamespace(calls=[], lookups=[], fail_bls=False)

    def provider(request):
        state.calls.append(request)
        if request.url.host == "api.bls.gov":
            return httpx.Response(403, text="public endpoint refused this request")
        return httpx.Response(200, text="observation_date,DFF\n2024-01-02,5.33\n2024-01-03,.\n")

    service.datahub.transport = httpx.MockTransport(provider)

    class Pool:
        async def backend_for_readonly(self, uid):
            assert uid == user.id
            state.lookups.append(uid)
            return SimpleNamespace(url="http://account.invalid", key="")

        async def backend_for(self, _uid):
            raise AssertionError("MCP must not cold-start DSH or schedulers")

        async def close(self):
            await service.datahub.close()

    app = create_gateway(
        accounts, Pool(), origin=ORIGIN, mcp_enabled=True, weknora_oauth_origin=WK_ORIGIN
    )
    facade = app.state.mcp_facade
    asyncio.run(facade.client.aclose())
    facade.client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=backend_app), trust_env=False
    )
    facade.backend.client = facade.datahub.client = facade.client
    with TestClient(app, base_url=ORIGIN) as client:
        yield SimpleNamespace(
            client=client,
            store=facade.store,
            user=user,
            service=service,
            datahub=facade.datahub,
            state=state,
            auth=auth,
        )


def mcp(env, token, name=None, **arguments):
    params = {"name": name, "arguments": arguments} if name else None
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call" if name else "tools/list"}
    if params is not None:
        body["params"] = params
    response = env.client.post(
        "/mcp",
        json=body,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def content(result):
    assert not result.get("isError"), result
    return result.get("structuredContent") or json.loads(result["content"][0]["text"])


def query_args(request_id="fred-example-1", source="ext_fred", series_id="DFF"):
    return {
        "request_id": request_id,
        "source": source,
        "series_id": series_id,
        "start_date": "2024-01-02",
        "end_date": "2024-01-08",
    }


def completed(env, token, query_id):
    for _ in range(30):
        value = content(mcp(env, token, "rwb_datahub_status", query_id=query_id))
        if value["status"] != "running":
            return value
    raise AssertionError("query did not finish")


def test_mcp_public_query_reuses_datahub_and_preserves_frozen_evidence(gateway):
    env = gateway
    token = grant(env.store, env.user).access_token
    tools = mcp(env, token)["tools"]
    assert len(tools) == 7
    assert not next(t for t in tools if t["name"] == "rwb_datahub_query")["annotations"][
        "readOnlyHint"
    ]
    one = content(mcp(env, token, "rwb_datahub_query", **query_args()))
    two = content(mcp(env, token, "rwb_datahub_query", **query_args()))
    assert one["id"] == two["id"]
    conflict = mcp(env, token, "rwb_datahub_query", **query_args(series_id="SOFR"))
    assert conflict["isError"] and "idempotency_conflict" in conflict["content"][0]["text"]
    result = completed(env, token, one["id"])
    assert result["status"] == "completed"
    assert result["data_success"] is True
    assert result["result"]["items"] == [
        {"observation_date": "2024-01-02", "DFF": "5.33"},
        {"observation_date": "2024-01-03", "DFF": "."},
    ]
    manifest = result["result"]["manifest"]
    assert manifest["provider"] == "ext_fred"
    assert manifest["limitations"] and manifest["files"]
    assert result["result"]["rows_sha256"]
    assert len(env.state.calls) == 1
    assert env.service.store.session(one["session_id"])["created"] is False


def test_old_readonly_token_cannot_discover_or_execute_query_tools(gateway):
    env = gateway
    token = grant(env.store, env.user, ["rwb.read"]).access_token
    assert {t["name"] for t in mcp(env, token)["tools"]} == {
        "rwb_capabilities_list",
        "rwb_datasets_list",
        "rwb_dataset_read",
        "rwb_source_read",
    }
    denied = mcp(env, token, "rwb_datahub_query", **query_args())
    assert denied["isError"] and "access_denied" in denied["content"][0]["text"]
    assert env.state.lookups == [] and env.state.calls == []


def test_resource_metadata_advertises_optional_scope_without_requiring_it(gateway):
    env = gateway
    metadata = env.client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["scopes_supported"] == [*SCOPES, "rwb.data.configured"]
    readonly = grant(env.store, env.user, ["rwb.read"]).access_token
    assert len(mcp(env, readonly)["tools"]) == 4


def test_query_results_are_grant_bound_and_revocation_withholds_bytes(gateway, monkeypatch):
    env = gateway
    pair = grant(env.store, env.user)
    token = pair.access_token
    other = grant(env.store, env.user).access_token
    first = content(mcp(env, token, "rwb_datahub_query", **query_args()))
    completed(env, token, first["id"])
    other_query = content(mcp(env, other, "rwb_datahub_query", **query_args("other-1")))
    assert other_query["session_id"] != first["session_id"]
    denied = mcp(env, other, "rwb_datahub_status", query_id=first["id"])
    assert denied["isError"] and "access_denied" in denied["content"][0]["text"]
    grant_id = env.store.verify_access(token, resource=env.store.resource).grant_id
    original = env.datahub._get

    async def read_then_revoke(*args, **kwargs):
        raw = await original(*args, **kwargs)
        env.store.revoke_grant(grant_id, user_id=env.user.id)
        return raw

    monkeypatch.setattr(env.datahub, "_get", read_then_revoke)
    denied = mcp(env, token, "rwb_datahub_status", query_id=first["id"])
    assert denied["isError"] and "access_denied" in denied["content"][0]["text"]
    assert "structuredContent" not in denied


def test_provider_403_is_reported_without_successful_snapshot(gateway):
    env = gateway
    token = grant(env.store, env.user).access_token
    query = content(
        mcp(env, token, "rwb_datahub_query", **query_args("bls-1", "ext_bls", "CUUR0000SA0"))
    )
    result = completed(env, token, query["id"])
    assert result["status"] == "failed" or result.get("dataset", {}).get("status") == "failed"
    assert result["data_success"] is False
    assert len(env.state.calls) == 1
    assert env.state.calls[0].url.host == "api.bls.gov"


def test_actual_service_only_app_allows_datahub_but_not_embedded_execution(tmp_path, monkeypatch):
    """Exercise create_app's real middleware/lifespan, not a bare router fixture."""
    monkeypatch.delenv("RWB_TENANT_MODE", raising=False)
    service = ResearchService(ExternalExecutionClient(), Store(tmp_path / "actual-host"))
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, text="observation_date,DFF\n2024-01-02,5.33\n")

    service.datahub.transport = httpx.MockTransport(provider)
    with TestClient(create_app(service)) as client:
        context = client.post("/api/research/data/contexts", json={"grant_id": str(uuid4())})
        assert context.status_code == 201, context.text
        sid = context.json()["session_id"]
        body = {"session_id": sid, "section": "market", "query": fred_query()}
        submitted = client.post(
            "/api/research/data/queries",
            json=body,
            headers={"Idempotency-Key": "actual-app-datahub-0001"},
        )
        assert submitted.status_code == 202, submitted.text
        query_id = submitted.json()["id"]
        for _ in range(30):
            response = client.get(f"/api/research/data/queries/{query_id}")
            assert response.status_code == 200, response.text
            status = response.json()
            if status["status"] != "running":
                break
        assert status["status"] == "completed" and status["dataset"]["row_count"] == 1
        assert (
            client.post(f"/api/research/data/queries/{query_id}/cancel").json()["status"]
            == "completed"
        )
        assert len(calls) == 1
        assert service.store.session(sid)["created"] is False
        for method, path in (
            ("POST", "/api/research/sessions"),
            ("PUT", "/api/research/runtime/model"),
            ("PUT", "/api/research/data/sources/ext_fred/configuration"),
        ):
            denied = client.request(method, path, json={})
            assert (
                denied.status_code == 403
                and denied.json()["error"]["code"] == "embedded_research_disabled"
            )


@pytest.mark.asyncio
async def test_real_service_only_launcher_reaches_datahub_without_dsh(tmp_path):
    """Real RuntimePool → process spec → uvicorn → create_app, with no provider network."""
    project = Path(__file__).resolve().parents[2]
    root = tmp_path / "launcher"
    user = str(uuid4())
    pool = RuntimePool(
        RuntimeConfig(
            root=root,
            project=project,
            source=None,
            python=sys.executable,
            node=None,
            max_instances=1,
            service_only=True,
        )
    )
    try:
        backend = await pool.backend_for(user)
        assert backend.service_only and backend.runtime_pid is None
        owner = json.loads((root / "users" / user / "state" / "owner.json").read_text())
        assert owner["execution_mode"] == "external" and len(owner["pids"]) == 1
        headers = {"X-RWB-Tenant-Gateway-Key": backend.key, "Origin": backend.url}
        async with httpx.AsyncClient(
            base_url=backend.url, headers=headers, trust_env=False, timeout=15
        ) as client:
            context = await client.post(
                "/api/research/data/contexts", json={"grant_id": str(uuid4())}
            )
            assert context.status_code == 201, context.text
            sid = context.json()["session_id"]
            # Unsupported catalog source fails inside DataHub before any HTTP
            # Provider request; this is a launcher/route test, not live data proof.
            query = fred_query()
            query["source"] = "not_registered"
            body = {"session_id": sid, "section": "market", "query": query}
            submitted = await client.post(
                "/api/research/data/queries",
                json=body,
                headers={"Idempotency-Key": "real-launcher-query-0001"},
            )
            assert submitted.status_code == 202, submitted.text
            query_id = submitted.json()["id"]
            for _ in range(30):
                response = await client.get(f"/api/research/data/queries/{query_id}")
                assert response.status_code == 200, response.text
                status = response.json()
                if status["status"] != "running":
                    break
                await asyncio.sleep(0.01)
            assert status["status"] == "failed" and status["failure_code"] == "query_failed"
            cancelled = await client.post(f"/api/research/data/queries/{query_id}/cancel")
            assert cancelled.status_code == 200 and cancelled.json()["id"] == query_id
            denied = await client.post("/api/research/sessions", json={})
            assert denied.status_code == 403
    finally:
        await pool.close()


def test_configured_scope_needs_fresh_explicit_authorization(gateway):
    env = gateway
    pair = grant(env.store, env.user)
    assert len(mcp(env, pair.access_token)["tools"]) == 7
    denied = mcp(env, pair.access_token, "rwb_datahub_catalog")
    assert denied.get("isError") is True
    with pytest.raises(AccountError, match="invalid_scope"):
        env.store.rotate_refresh(
            pair.refresh_token, client_id="rwb-weknora", scopes=[*SCOPES, "rwb.data.configured"]
        )


def test_configured_catalog_reuses_account_readiness_without_fetch(gateway):
    env = gateway
    token = grant(env.store, env.user, [*SCOPES, "rwb.data.configured"]).access_token
    assert len(mcp(env, token)["tools"]) == 18
    catalog = content(mcp(env, token, "rwb_datahub_catalog"))
    sources = {item["id"] for item in catalog["sources"]}
    assert "ext_worldbank" in sources
    assert "ext_finance_mcp" not in sources
    assert all(
        item["readiness"]["callable"] and item["readiness"]["allowed"]
        for item in catalog["sources"]
    )
    assert env.state.calls == []


def test_configured_query_accepts_existing_non_fred_binding(gateway):
    env = gateway
    token = grant(env.store, env.user, [*SCOPES, "rwb.data.configured"]).access_token
    value = content(
        mcp(
            env,
            token,
            "rwb_datahub_business_query",
            request_id="worldbank-catalog",
            query={
                "capability": "external_data",
                "source": "ext_worldbank",
                "parameters": {"dataset": "catalog", "limit": 5},
            },
        )
    )
    result = completed(env, token, value["id"])
    assert result["source"] == "ext_worldbank"
    assert result["data_success"] is True
    assert result["result"]["items"]
    assert env.state.calls == []


def test_configured_query_rejects_missing_credential_and_auto_source(gateway):
    env = gateway
    token = grant(env.store, env.user, [*SCOPES, "rwb.data.configured"]).access_token
    for source in ["ext_finance_mcp", "auto"]:
        denied = mcp(
            env,
            token,
            "rwb_datahub_business_query",
            request_id="blocked-source",
            query={
                "capability": "external_data",
                "source": source,
                "parameters": {"dataset": "catalog"},
            },
        )
        assert denied.get("isError") is True
        assert "configured_source_unavailable" in denied["content"][0]["text"]
    assert env.state.calls == []


def test_business_kline_uses_original_query_status_and_gangtise_binding(gateway, monkeypatch):
    env = gateway
    token = grant(env.store, env.user, [*SCOPES, "rwb.data.configured"]).access_token
    from app.research_web.datahub import catalog

    monkeypatch.setattr(catalog, "_dependency_status", lambda *_: (False, "fixture_unavailable"))
    monkeypatch.setattr(
        env.service.datahub.connections,
        "statuses",
        lambda: {"ext_finance_mcp": {"secret_configured": True}},
    )
    monkeypatch.setattr(
        env.service.datahub.connections,
        "read_source_secret",
        lambda source: "fixture-finance-token",
    )
    calls = []

    def provider(request):
        if request.method == "GET":
            return httpx.Response(405)
        body = json.loads(request.content)
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        result = {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "serverInfo": {"name": "fixture", "version": "1"},
        }
        if body["method"] == "tools/list":
            result = {
                "tools": [
                    {"name": "gangtise_query", "inputSchema": {"type": "object", "properties": {}}}
                ]
            }
        if body["method"] == "tools/call":
            calls.append(body["params"])
            result = {
                "isError": False,
                "content": [],
                "structuredContent": {
                    "ok": True,
                    "data": {
                        "code": "000000",
                        "status": True,
                        "data": {
                            "total": 1,
                            "fieldList": [
                                "securityCode",
                                "tradeDate",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "amount",
                            ],
                            "list": [["600519.SH", "2026-01-05", 10, 12, 9, 11, 100, 1100]],
                        },
                    },
                },
            }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    env.service.datahub.transport = httpx.MockTransport(provider)
    value = content(
        mcp(
            env,
            token,
            "get_stock_kline",
            request_id="business-kline-1",
            asset="600519.SH",
            start_date="2026-01-05",
            end_date="2026-01-05",
        )
    )
    result = completed(env, token, value["id"])
    assert result["status"] == "completed"
    assert result["result"]["manifest"]["provider"] == "ext_finance_mcp"
    assert result["data_success"] is True
    assert result["result"]["items"][0]["turnover"] == 1100
    assert calls[0]["name"] == "gangtise_query"
    assert calls[0]["arguments"]["operation"] == "查询A股日K线"
    again = content(
        mcp(
            env,
            token,
            "get_stock_kline",
            request_id="business-kline-1",
            asset="600519.SH",
            start_date="2026-01-05",
            end_date="2026-01-05",
        )
    )
    assert again["id"] == value["id"]
    assert len(calls) == 1
