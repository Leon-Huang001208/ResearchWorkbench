"""Research Web MCP Host orchestration and route contracts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.research_web.mcp_runtime.routes import InstallPreviewRequest, router
from app.research_web.mcp_runtime.service import MCPRuntimeError, MCPRuntimeService


@dataclass
class FakePlan:
    target_kind: str = "local"
    registry_id: str = "official"
    server_name: str = "io.example/weather"
    server_version: str = "1.2.3"
    environment_names: tuple[str, ...] = ("WEATHER_TOKEN",)
    summary_sha256: str = "a" * 64

    def model_dump(self, **_kwargs):
        return {
            "target_kind": self.target_kind,
            "registry_id": self.registry_id,
            "server_name": self.server_name,
            "server_version": self.server_version,
            "environment_names": list(self.environment_names),
            "summary_sha256": self.summary_sha256,
            "argv": ["/verified/server", "--stdio"],
            "artifacts": [{"filename": "server.whl", "sha256": "b" * 64}],
        }


@dataclass
class FakeManifest:
    id: str
    plan: FakePlan
    manifest_sha256: str = "c" * 64

    def model_dump(self, **_kwargs):
        return {
            "id": self.id,
            "status": "installed",
            "plan": self.plan.model_dump(),
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass
class FakeRemotePlan:
    target_kind: str = "remote"
    registry_id: str = "official"
    server_name: str = "io.example/weather"
    server_version: str = "1.2.3"
    endpoint: str = "https://mcp.example.test"

    def model_dump(self, **_kwargs):
        return vars(self).copy()


class FakeOAuth:
    def __init__(self):
        self.calls = []

    async def start(self, installation_id, resource):
        self.calls.append((installation_id, resource))
        return SimpleNamespace(authorization_url="https://auth.example.test/authorize")


class FakeRegistry:
    def __init__(self):
        self.calls = []

    async def version_detail(self, registry_id, server_name, version, *, refresh=True):
        self.calls.append((registry_id, server_name, version, refresh))
        return {
            "registry_id": registry_id,
            "name": server_name,
            "version": version,
            "packages": [{"registry_type": "pypi", "identifier": "weather"}],
            "remotes": [{"type": "streamable-http", "url": "https://mcp.example.test"}],
        }


class FakeResolver:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    async def resolve(self, selection, detail):
        self.calls.append((selection, detail))
        return {"trusted": True, "plan": self.plan}


class FakePlanner:
    def plan(self, resolution):
        assert resolution["trusted"] is True
        return resolution["plan"]


class FakeTokens:
    def issue(self, plan):
        assert plan.summary_sha256 == "a" * 64
        return "confirmation-token"


class FakeStore:
    def __init__(self, plan):
        self.plan = plan
        self.items = {}

    def create(self, plan, token, tokens):
        assert plan is self.plan
        assert token == "confirmation-token"
        manifest = FakeManifest("mcp-installation-" + "1" * 32, plan)
        self.items[manifest.id] = manifest
        return manifest

    def list(self):
        return list(self.items.values())

    def get(self, installation_id):
        try:
            return self.items[installation_id]
        except KeyError as exc:
            raise RuntimeError("installation_not_found") from exc

    def delete(self, installation_id):
        self.items.pop(installation_id)


class FakeInstaller:
    def __init__(self):
        self.installed = []

    async def install(self, plan, environment):
        self.installed.append((plan, environment))
        return {"transport": "stdio", "installation": "candidate"}

    def target(self, manifest):
        return {"installation_id": manifest.id}

    async def remove(self, _manifest):
        return None


class FakeHost:
    async def capabilities(self, target):
        assert target["installation_id"].startswith("mcp-installation-")
        return {
            "protocol_version": "negotiated",
            "tools": [
                {
                    "name": "read_weather",
                    "description": "Read weather",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {"type": "object"},
                }
            ],
            "resources": [{"uri": "weather://today"}],
            "prompts": [{"name": "brief"}],
            "sampling": False,
            "elicitation": False,
            "tasks": False,
        }

    async def call_tool(self, target, name, arguments):
        assert target["installation_id"].startswith("mcp-installation-")
        assert name == "read_weather"
        assert arguments == {"city": "Shanghai"}
        return {"content": [{"type": "text", "text": "sunny"}]}

    async def read_resource(self, _target, uri):
        return {"contents": [{"uri": uri, "text": "facts"}]}

    async def get_prompt(self, _target, name, arguments):
        return {"description": name, "messages": [arguments]}


class FakeAuthorization:
    def __init__(self):
        self.tools = []
        self.grants = []
        self.approvals = []
        self.require_approval = False
        self.admissions = []

    def register_tool(self, **tool):
        previous = next(
            (
                item
                for item in self.tools
                if item["installation_id"] == tool["installation_id"]
                and item["tool_name"] == tool["tool_name"]
                and item["version"] == tool["version"]
            ),
            None,
        )
        snapshot = {
            **tool,
            "schema_sha256": "d" * 64,
            "risk_tier": previous["risk_tier"] if previous else "read_only",
            "allow_unattended": previous["allow_unattended"] if previous else False,
            "status": "active",
        }
        self.tools = [snapshot]
        return snapshot

    def active_bindings(self, installation_ids=None):
        return [
            {
                "name": f"mcp__{tool['installation_id']}__{tool['tool_name']}",
                "installation_id": tool["installation_id"],
                "version": tool["version"],
                "tool_name": tool["tool_name"],
                "schema_sha256": tool["schema_sha256"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in self.tools
            if installation_ids is None or tool["installation_id"] in installation_ids
        ]

    def list_tools(self):
        return list(self.tools)

    def classify_tool(self, installation_id, tool_name, *, risk_tier, allow_unattended):
        snapshot = next(
            tool
            for tool in self.tools
            if tool["installation_id"] == installation_id and tool["tool_name"] == tool_name
        )
        snapshot.update(risk_tier=risk_tier, allow_unattended=allow_unattended)
        return snapshot

    def authorize_session(self, **grant):
        result = {"id": "mcp-grant-" + "2" * 32, **grant, "status": "active"}
        self.grants.append(result)
        return result

    def admit_call(self, **request):
        self.admissions.append(request)
        assert request["allowlist"].allows(
            f"mcp__{request['installation_id']}__{request['tool_name']}",
            request["installation_id"],
            request["version"],
            "d" * 64,
        )
        if self.require_approval and request.get("approval_id") is None:
            approval = {
                "id": "mcp-approval-" + "3" * 32,
                "session_id": request["session_id"],
                "status": "pending",
            }
            self.approvals = [approval]
            return {"allowed": False, "approval_id": approval["id"]}
        return {"allowed": True}

    def list_approvals(self, *, session_id=None):
        return [
            item
            for item in self.approvals
            if session_id is None or item["session_id"] == session_id
        ]

    def approve(self, approval_id, *, session_id):
        result = {"id": approval_id, "session_id": session_id, "status": "approved"}
        self.approvals = [result]
        return result

    def deny(self, approval_id, *, session_id):
        return {"id": approval_id, "session_id": session_id, "status": "denied"}


def make_service(*, restart=None, data_root=None):
    plan = FakePlan()
    registry = FakeRegistry()
    resolver = FakeResolver(plan)
    store = FakeStore(plan)
    installer = FakeInstaller()
    authorization = FakeAuthorization()
    restarts = []

    async def restart_callback(bindings):
        restarts.append(bindings)
        if restart is not None:
            return await restart(bindings)

    service = MCPRuntimeService(
        data_root=data_root,
        enabled=True,
        registry=registry,
        resolver=resolver,
        planner=FakePlanner(),
        tokens=FakeTokens(),
        store=store,
        installer=installer,
        host=FakeHost(),
        authorization=authorization,
        idle_gate=lambda: True,
        restart_callback=restart_callback,
    )
    return service, registry, resolver, store, installer, authorization, restarts


def preview_request():
    return InstallPreviewRequest.model_validate(
        {
            "registry_id": "official",
            "server_name": "io.example/weather",
            "server_version": "1.2.3",
            "package_index": 0,
            "environment_names": ["WEATHER_TOKEN"],
        }
    )


def test_preview_contract_rejects_client_supplied_execution_or_hash_fields():
    with pytest.raises(ValidationError):
        InstallPreviewRequest.model_validate(
            {
                **preview_request().model_dump(),
                "argv": ["sh", "-c", "evil"],
                "artifacts": [],
                "schema_sha256": "a" * 64,
            }
        )


@pytest.mark.asyncio
async def test_disabled_runtime_lifecycle_is_a_safe_noop_but_api_is_hidden():
    service = MCPRuntimeService(enabled=False)

    await service.start()
    await service.close()

    with pytest.raises(MCPRuntimeError) as error:
        service.list_installations()
    assert (error.value.code, error.value.status) == ("mcp_runtime_disabled", 404)


@pytest.mark.asyncio
async def test_disabled_runtime_does_not_load_corrupt_persisted_state(tmp_path):
    runtime_root = tmp_path / "mcp-runtime"
    runtime_root.mkdir()
    (runtime_root / "active.json").write_text("not-json", encoding="utf-8")

    service = MCPRuntimeService(data_root=tmp_path, enabled=False)

    await service.start()
    await service.close()


@pytest.mark.asyncio
async def test_preview_uses_registry_detail_and_trusted_resolver_only():
    service, registry, resolver, *_ = make_service()

    result = await service.preview(preview_request())

    assert result["confirmation_token"] == "confirmation-token"
    assert result["plan"]["argv"] == ["/verified/server", "--stdio"]
    assert registry.calls == [("official", "io.example/weather", "1.2.3", True)]
    selection, detail = resolver.calls[0]
    assert selection.package_index == 0
    assert selection.remote_index is None
    assert selection.environment_names == ["WEATHER_TOKEN"]
    assert detail["name"] == "io.example/weather"

    unavailable = MCPRuntimeService(enabled=True, registry=registry)
    with pytest.raises(MCPRuntimeError) as error:
        await unavailable.preview(preview_request())
    assert (error.value.code, error.value.status) == ("mcp_resolver_unavailable", 503)


@pytest.mark.asyncio
async def test_update_requires_a_new_preview_instead_of_mutating_an_immutable_installation():
    service, *_ = make_service()
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )

    with pytest.raises(MCPRuntimeError) as error:
        await service.update(installed["installation"]["id"])

    assert (error.value.code, error.value.status) == (
        "mcp_update_requires_preview",
        409,
    )


@pytest.mark.asyncio
async def test_oauth_start_is_bound_to_the_installed_remote_endpoint():
    service, _, _, store, *_ = make_service()
    oauth = FakeOAuth()
    service.oauth = oauth
    installation_id = "mcp-installation-" + "9" * 32
    store.items[installation_id] = FakeManifest(installation_id, FakeRemotePlan())

    result = await service.oauth_start(installation_id, "https://mcp.example.test")
    assert result == {"authorization_url": "https://auth.example.test/authorize"}
    assert oauth.calls == [(installation_id, "https://mcp.example.test")]

    with pytest.raises(MCPRuntimeError) as mismatch:
        await service.oauth_start(installation_id, "https://other.example.test")
    assert (mismatch.value.code, mismatch.value.status) == (
        "mcp_oauth_resource_mismatch",
        422,
    )
    assert len(oauth.calls) == 1

    local_id = "mcp-installation-" + "8" * 32
    store.items[local_id] = FakeManifest(local_id, FakePlan())
    with pytest.raises(MCPRuntimeError) as local:
        await service.oauth_start(local_id, "https://mcp.example.test")
    assert local.value.code == "mcp_oauth_resource_mismatch"


@pytest.mark.asyncio
async def test_install_probe_enable_and_internal_call_recheck_exact_snapshot():
    service, _, _, store, installer, authorization, restarts = make_service()
    preview = await service.preview(preview_request())

    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    assert installer.installed[0][1] == {"WEATHER_TOKEN": "runtime-secret"}
    assert "runtime-secret" not in str(installed)

    capabilities = await service.probe(installation_id)
    assert capabilities["tools"][0]["name"] == "read_weather"
    assert capabilities["tools"][0]["schema_sha256"] == "d" * 64
    assert capabilities["tools"][0]["risk_tier"] == "read_only"
    assert capabilities["tools"][0]["allow_unattended"] is False
    assert service.capabilities(installation_id) == capabilities
    assert authorization.tools[0]["version"] == "1.2.3"
    enabled = await service.enable(installation_id)
    assert enabled["status"] == "enabled"
    assert restarts[-1][0]["name"] == f"mcp__{installation_id}__read_weather"

    grant = service.authorize_session(
        "native-session-1",
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_weather",
        schema_sha256="d" * 64,
    )
    assert grant["status"] == "active"

    result = await service.call_tool(
        call_id="call-1",
        session_id="native-session-1",
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_weather",
        schema_sha256="d" * 64,
        arguments={"city": "Shanghai"},
    )
    assert result == {
        "status": "complete",
        "result": {"content": [{"type": "text", "text": "sunny"}]},
    }

    with pytest.raises(MCPRuntimeError) as drift:
        await service.call_tool(
            call_id="call-2",
            session_id="native-session-1",
            installation_id=installation_id,
            version="1.2.3",
            tool_name="read_weather",
            schema_sha256="e" * 64,
            arguments={"city": "Shanghai"},
        )
    assert drift.value.code == "mcp_schema_drift"
    assert store.get(installation_id).manifest_sha256 == "c" * 64


@pytest.mark.asyncio
async def test_trusted_automation_session_injects_exact_unattended_lock():
    service, *_rest, authorization, _restarts = make_service()
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    await service.probe(installation_id)
    service.classify_tool(
        installation_id,
        "read_weather",
        risk_tier="read_only",
        allow_unattended=True,
    )
    await service.enable(installation_id)
    lock = {
        "installation_id": installation_id,
        "version": "1.2.3",
        "tool_name": "read_weather",
        "schema_sha256": "d" * 64,
    }
    service.authorize_session("native-session-automation", **lock)
    service.register_automation_session("native-session-automation", [lock])

    await service.call_tool(
        call_id="call-automation",
        session_id="native-session-automation",
        **lock,
        arguments={"city": "Shanghai"},
    )

    admission = authorization.admissions[-1]
    assert admission["unattended"] is True
    assert admission["automation_lock"] == lock


@pytest.mark.asyncio
async def test_enable_restart_failure_rolls_back_active_snapshot():
    attempts = 0

    async def restart(_bindings):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("candidate failed with secret body")

    service, *_ = make_service(restart=restart)
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    await service.probe(installation_id)

    with pytest.raises(MCPRuntimeError) as error:
        await service.enable(installation_id)

    assert error.value.code == "mcp_runtime_restart_failed"
    assert attempts == 2
    assert service.status(installation_id)["status"] == "health_failed"


def test_router_uses_exact_public_session_and_internal_prefixes():
    app = FastAPI()
    app.include_router(router)
    paths = set(app.openapi()["paths"])

    assert "/api/research/mcp/installations/preview" in paths
    assert "/api/research/sessions/{session_id}/mcp-authorizations" in paths
    assert "/api/research/sessions/{session_id}/mcp/resources/read" in paths
    assert "/api/research/internal/mcp/tools/call" in paths
    assert "/api/research/mcp/sessions/{session_id}/mcp-authorizations" not in paths
    assert "/api/research/mcp/internal/mcp/tools/call" not in paths

    class Runtime:
        def authorize_session(self, session_id, **binding):
            return {"session_id": session_id, **binding}

        def authenticate_internal(self, presented):
            assert presented == "runtime-key"

        async def call_tool(self, **_body):
            return {"status": "complete", "result": {"content": []}}

    app.state.research = SimpleNamespace(mcp_runtime=Runtime())
    authorization = {
        "installation_id": "mcp-installation-" + "1" * 32,
        "version": "1.2.3",
        "tool_name": "read_weather",
        "schema_sha256": "d" * 64,
    }
    internal = {
        "call_id": "call-1",
        "session_id": "native-session-1",
        **authorization,
        "arguments": {"city": "Shanghai"},
    }
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/research/sessions/native-session-1/mcp-authorizations",
                json=authorization,
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/research/internal/mcp/tools/call",
                headers={"X-Research-MCP-Key": "runtime-key"},
                json=internal,
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/research/mcp/internal/mcp/tools/call",
                headers={"X-Research-MCP-Key": "runtime-key"},
                json=internal,
            ).status_code
            == 404
        )


@pytest.mark.asyncio
async def test_resource_and_prompt_require_session_installation_authorization():
    service, *_ = make_service()
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    await service.probe(installation_id)
    await service.enable(installation_id)

    with pytest.raises(MCPRuntimeError) as denied:
        await service.read_resource("native-session-1", installation_id, "weather://today")
    assert denied.value.code == "mcp_authorization_required"

    service.authorize_session(
        "native-session-1",
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_weather",
        schema_sha256="d" * 64,
    )
    resource = await service.read_resource("native-session-1", installation_id, "weather://today")
    prompt = await service.get_prompt(
        "native-session-1", installation_id, "brief", {"city": "Shanghai"}
    )
    assert resource["contents"][0]["text"] == "facts"
    assert prompt["description"] == "brief"


@pytest.mark.asyncio
async def test_tool_call_waits_for_approval_and_rechecks_same_request():
    service, _, _, _, _, authorization, _ = make_service()
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    await service.probe(installation_id)
    await service.enable(installation_id)
    service.authorize_session(
        "native-session-1",
        installation_id=installation_id,
        version="1.2.3",
        tool_name="read_weather",
        schema_sha256="d" * 64,
    )
    authorization.require_approval = True

    pending = asyncio.create_task(
        service.call_tool(
            call_id="call-approval",
            session_id="native-session-1",
            installation_id=installation_id,
            version="1.2.3",
            tool_name="read_weather",
            schema_sha256="d" * 64,
            arguments={"city": "Shanghai"},
        )
    )
    for _ in range(20):
        if authorization.approvals:
            break
        await asyncio.sleep(0)
    approval_id = authorization.approvals[0]["id"]
    await service.decide_approval(approval_id, session_id="native-session-1", approve=True)

    result = await pending
    assert result["status"] == "complete"
    assert service._approval_waiters == {}


@pytest.mark.asyncio
async def test_candidate_active_is_persisted_before_restart_and_rollback(tmp_path):
    snapshots = []

    async def restart(_bindings):
        path = tmp_path / "mcp-runtime" / "active.json"
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        if len(snapshots) == 1:
            raise RuntimeError("candidate failed")

    service, *_ = make_service(restart=restart, data_root=tmp_path)
    preview = await service.preview(preview_request())
    installed = await service.install(
        preview["confirmation_token"], {"WEATHER_TOKEN": "runtime-secret"}
    )
    installation_id = installed["installation"]["id"]
    await service.probe(installation_id)

    with pytest.raises(MCPRuntimeError):
        await service.enable(installation_id)

    assert snapshots == [
        {"schema_version": 1, "installation_ids": [installation_id]},
        {"schema_version": 1, "installation_ids": []},
    ]
