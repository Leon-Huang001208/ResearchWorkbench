"""Research Web lifecycle and ownership integration for the MCP Host."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.research_web.main import create_app
from app.research_web.mcp_runtime.authorization import AuthorizationManager
from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
from app.research_web.mcp_runtime.installation_store import (
    INTEGRITY_KEY_ACCOUNT,
    INTEGRITY_KEY_SERVICE,
    InstallationStore,
)
from app.research_web.mcp_runtime.oauth import OAuthCoordinator
from app.research_web.mcp_runtime.package_installer import PackageInstaller
from app.research_web.mcp_runtime.package_resolver import PackageResolver
from app.research_web.mcp_runtime.sdk_host import SDKHost
from app.research_web.mcp_runtime.service import (
    MCPRuntimeService,
    runtime_feature_enabled,
)
from app.research_web.service import MCP_CONFIRMATION_KEY_ACCOUNT, ResearchService
from app.research_web.store import Store, StoreError


def test_runtime_feature_is_enabled_by_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("RESEARCH_MCP_RUNTIME_ENABLED", raising=False)
    assert runtime_feature_enabled() is True
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    assert runtime_feature_enabled() is False


class NativeFixture:
    async def rpc(self, method, _payload):
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        return {"accepted": True}

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()

    async def close(self):
        return None


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[(service, account)] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


class FakeRuntime:
    def __init__(self):
        self.started = 0
        self.closed = 0
        self.calls = []

    async def start(self):
        self.started += 1

    async def close(self):
        self.closed += 1

    def authorize_session(self, session_id, **binding):
        self.calls.append(("authorize", session_id, binding))
        return {"session_id": session_id, **binding}

    async def read_resource(self, session_id, installation_id, uri):
        self.calls.append(("resource", session_id, installation_id, uri))
        return {"contents": []}

    async def get_prompt(self, session_id, installation_id, name, arguments):
        self.calls.append(("prompt", session_id, installation_id, name, arguments))
        return {"messages": []}

    async def call_tool(self, **request):
        self.calls.append(("tool", request))
        return {"status": "complete", "result": {}}

    def authenticate_internal(self, presented):
        if presented != "runtime-key":
            raise AssertionError("unexpected control token")

    async def oauth_callback(self, **request):
        self.calls.append(("oauth", request))
        return {"status": "connected"}

    def list_installations(self):
        self.calls.append(("list",))
        return {"items": []}


class FakeRuntimeManager:
    def __init__(self):
        self.restarts = 0

    def restart_runtime(self):
        self.restarts += 1
        return {"healthy": True}


@pytest.mark.asyncio
async def test_injected_runtime_is_lifecycle_managed_and_session_scoped(tmp_path):
    runtime = FakeRuntime()
    service = ResearchService(NativeFixture(), Store(tmp_path), mcp_runtime=runtime)

    await service.start()
    try:
        assert runtime.started == 1
        with pytest.raises(StoreError):
            service.mcp_runtime.authorize_session(
                "not-owned",
                installation_id="mcp-installation-" + "1" * 32,
                version="1.2.3",
                tool_name="read",
                schema_sha256="a" * 64,
            )
        with pytest.raises(StoreError):
            await service.mcp_runtime.call_tool(session_id="not-owned")

        session_id = service.store.create("claw", "owned")["id"]
        service.mcp_runtime.authorize_session(session_id, installation_id="owned-installation")
        await service.mcp_runtime.call_tool(session_id=session_id, arguments={"private": True})
        assert runtime.calls[-1][0] == "tool"
    finally:
        await service.close()
    assert runtime.closed == 1


@pytest.mark.asyncio
async def test_disabled_runtime_constructs_no_private_runtime_state(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    service = ResearchService(NativeFixture(), Store(tmp_path))

    assert isinstance(service.mcp_runtime.runtime, MCPRuntimeService)
    assert service.mcp_runtime.runtime.enabled is False
    assert not (tmp_path / "mcp-runtime").exists()

    await service.mcp_runtime.start()
    await service.mcp_runtime.close()
    assert not (tmp_path / "mcp-runtime").exists()


def test_enabled_runtime_builds_persistent_private_host_dependencies(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "1")
    monkeypatch.setenv("RESEARCH_MCP_REGISTRY_ENABLED", "1")
    monkeypatch.setenv("RESEARCH_WEB_INTERNAL_URL", "http://127.0.0.1:18088")
    keyring = FakeKeyring()
    manager = FakeRuntimeManager()

    service = ResearchService(
        NativeFixture(),
        Store(tmp_path),
        mcp_keyring_backend=keyring,
        runtime_manager=manager,
    )
    runtime = service.mcp_runtime.runtime

    assert runtime.enabled is True
    assert isinstance(runtime.resolver, PackageResolver)
    assert isinstance(runtime.store, InstallationStore)
    assert isinstance(runtime.installer, PackageInstaller)
    assert isinstance(runtime.authorization, AuthorizationManager)
    assert isinstance(runtime.host, SDKHost)
    assert isinstance(runtime.host.credentials, RuntimeCredentialStore)
    assert isinstance(runtime.oauth, OAuthCoordinator)
    assert runtime.oauth.redirect_uri == ("http://127.0.0.1:18088/api/research/mcp/oauth/callback")
    assert runtime.control["url"] == "http://127.0.0.1:18088"
    assert runtime.registry is service.mcp_registry
    assert keyring.values[(INTEGRITY_KEY_SERVICE, INTEGRITY_KEY_ACCOUNT)]
    assert keyring.values[(INTEGRITY_KEY_SERVICE, MCP_CONFIRMATION_KEY_ACCOUNT)]
    assert (tmp_path / ".control" / "mcp-runtime.json").is_file()


@pytest.mark.asyncio
async def test_mcp_idle_gate_returns_true_and_restart_only_targets_dsh(tmp_path):
    manager = FakeRuntimeManager()
    service = ResearchService(
        NativeFixture(),
        Store(tmp_path),
        mcp_runtime=FakeRuntime(),
        runtime_manager=manager,
    )
    service.connected = {"mux", "host"}

    assert await service._mcp_idle_gate() is True
    await service._restart_mcp_runtime([])
    assert manager.restarts == 1


def test_oauth_callback_has_only_narrow_cross_site_navigation_exception(tmp_path):
    runtime = FakeRuntime()
    service = ResearchService(NativeFixture(), Store(tmp_path), mcp_runtime=runtime)
    with TestClient(create_app(service)) as client:
        callback = client.get(
            "/api/research/mcp/oauth/callback",
            params={"state": "s" * 16, "code": "code"},
            headers={
                "Origin": "https://authorization.example",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
        )
        rejected = client.get(
            "/api/research/mcp/installations",
            headers={
                "Origin": "https://authorization.example",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            },
        )

    assert callback.status_code == 200
    assert callback.json() == {"status": "connected"}
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "origin_denied"


def test_session_and_internal_routes_reject_unowned_session_ids(tmp_path):
    runtime = FakeRuntime()
    service = ResearchService(NativeFixture(), Store(tmp_path), mcp_runtime=runtime)
    installation_id = "mcp-installation-" + "1" * 32
    authorization = {
        "installation_id": installation_id,
        "version": "1.2.3",
        "tool_name": "read",
        "schema_sha256": "a" * 64,
    }
    with TestClient(create_app(service)) as client:
        session_response = client.post(
            "/api/research/sessions/not-owned/mcp-authorizations",
            json=authorization,
        )
        internal_response = client.post(
            "/api/research/internal/mcp/tools/call",
            headers={"X-Research-MCP-Key": "runtime-key"},
            json={
                "call_id": "call-1",
                "session_id": "not-owned",
                **authorization,
                "arguments": {},
            },
        )

    assert session_response.status_code == 400
    assert internal_response.status_code == 400
    assert not any(call[0] in {"authorize", "tool"} for call in runtime.calls)
