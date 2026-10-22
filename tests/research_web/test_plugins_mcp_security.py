"""Managed MCP startup/call policy and one-use gateway proofs; all Hosts mocked."""

import json
from types import SimpleNamespace

import pytest
from test_plugins import Catalog, bundle

from app.research_web.mcp_runtime.service import MCPRuntimeError, MCPRuntimeService
from app.research_web.plugins.mcp_policy import managed_binding, native_fingerprint
from app.research_web.plugins.packages import PluginError
from app.research_web.plugins.proof import sign, verify
from app.research_web.plugins.service import PluginService

ACTOR = "01234567-0123-4123-8123-0123456789ab"
PATH = "/api/research/plugins/" + "a" * 64 + "/mcp/weather/install"


def test_proof_is_one_use_body_method_route_actor_and_expiry_bound():
    headers = sign("k" * 48, "POST", PATH, b"{}", ACTOR, "user", now=100)
    assert verify("k" * 48, "POST", PATH, b"{}", headers, {}, now=101) == (ACTOR, "user")
    consumed = {}
    verify("k" * 48, "POST", PATH, b"{}", headers, consumed, now=101)
    with pytest.raises(PluginError):
        verify("k" * 48, "POST", PATH, b"{}", headers, consumed, now=101)
    for key, method, path, body, proof, clock in [
        ("x" * 48, "POST", PATH, b"{}", headers, 101),
        ("k" * 48, "GET", PATH, b"{}", headers, 101),
        ("k" * 48, "POST", PATH.replace("install", "enable"), b"{}", headers, 101),
        ("k" * 48, "POST", PATH, b'{"changed":true}', headers, 101),
        ("k" * 48, "POST", PATH, b"{}", {**headers, "X-RWB-Plugin-Role": "admin"}, 101),
        ("k" * 48, "POST", PATH, b"{}", headers, 131),
    ]:
        with pytest.raises(PluginError):
            verify(key, method, path, body, proof, {}, now=clock)


@pytest.mark.asyncio
async def test_managed_native_artifacts_schemas_and_approvals_are_rechecked(tmp_path):
    service = PluginService(tmp_path, Catalog(), idle_gate=lambda: True)
    declaration = {
        "registry_id": "official",
        "server_name": "io.example/weather",
        "server_version": "1.2.3",
        "remote_index": 0,
    }
    manifest = {
        "name": "fixture",
        "version": "1.0.0",
        "extensions": {"research_workbench": {"mcp": {"weather": declaration}}},
    }
    item = service.preview(bundle("plugin.json", extra={"plugin.json": json.dumps(manifest)}))
    service.review(item["digest"], item["permissions"], "admin")
    await service.enable(item["digest"])
    native = {
        "id": "mcp-installation-" + "b" * 32,
        "plan": {**declaration, "endpoint": "https://example.invalid/mcp"},
    }
    schemas = {
        "tools": [
            {"name": "read", "inputSchema": {"type": "object"}, "description": "Read fixture"}
        ]
    }
    row = service._row(item["digest"])
    row["mcp_bindings"]["weather"] = native["id"]
    row["mcp_reviews"] = {"weather": native_fingerprint(tmp_path, native, schemas)}
    service.save()
    assert managed_binding(tmp_path, native, schemas) == (item["digest"], "weather")
    with pytest.raises(PluginError, match="schema_review_required"):
        managed_binding(tmp_path, native, {"tools": []})
    changed = {**native, "plan": {**native["plan"], "endpoint": "https://other.invalid/mcp"}}
    with pytest.raises(PluginError, match="native_review_required"):
        managed_binding(tmp_path, changed, schemas)
    service.mcp = SimpleNamespace(status=lambda _id: {"active": False})
    await service.disable(item["digest"])
    with pytest.raises(PluginError, match="approval_inactive"):
        managed_binding(tmp_path, native, schemas)


@pytest.mark.asyncio
async def test_tenant_legacy_active_never_resolves_process_but_native_default_stays_compatible(
    tmp_path,
):
    calls = []
    iid = "mcp-installation-" + "c" * 32
    manifest = {"id": iid, "plan": {"endpoint": "https://example.invalid/mcp"}}
    store = SimpleNamespace(get=lambda _id: manifest)
    installer = SimpleNamespace(target=lambda value: calls.append(value) or "target")
    tenant = MCPRuntimeService(
        tmp_path, enabled=True, store=store, installer=installer, managed_only=True
    )
    tenant._active = {iid}
    with pytest.raises(MCPRuntimeError) as denied:
        await tenant.start()
    assert denied.value.code == "mcp_managed_approval_required"
    assert calls == []
    native = MCPRuntimeService(
        tmp_path, enabled=True, store=store, installer=installer, managed_only=False
    )
    native._active = {iid}
    await native.start()
    assert calls == [manifest]


def test_installed_file_mutation_invalidates_fingerprint(tmp_path):
    iid = "mcp-installation-" + "d" * 32
    package = tmp_path / "mcp-runtime/packages" / iid
    package.mkdir(parents=True)
    script = package / "fixture.py"
    script.write_text("print('one')")
    manifest = {"id": iid, "plan": {"server_version": "1.0.0"}}
    first = native_fingerprint(tmp_path, manifest)
    script.write_text("print('two')")
    assert native_fingerprint(tmp_path, manifest)["artifacts"] != first["artifacts"]


@pytest.mark.asyncio
async def test_native_managed_activation_is_staged_until_manager_commit_and_rollback_is_idempotent(
    tmp_path,
):
    from test_mcp_runtime_routes import FakeManifest, FakeRemotePlan, make_service

    native, _, _, store, _, _, restarts = make_service(data_root=tmp_path)
    iid = "mcp-installation-" + "e" * 32
    manifest = FakeManifest(iid, FakeRemotePlan())
    store.items[iid] = manifest
    native.managed_only = True
    declaration = {
        "registry_id": "official",
        "server_name": "io.example/weather",
        "server_version": "1.2.3",
        "remote_index": 0,
    }
    package = {
        "name": "fixture",
        "version": "1.0.0",
        "extensions": {"research_workbench": {"mcp": {"weather": declaration}}},
    }
    plugins = PluginService(tmp_path, Catalog(), native, idle_gate=lambda: True)
    item = plugins.preview(bundle("plugin.json", extra={"plugin.json": json.dumps(package)}))
    plugins.review(item["digest"], item["permissions"], "admin")
    await plugins.enable(item["digest"])
    row = plugins._row(item["digest"])
    row["mcp_bindings"]["weather"] = iid
    schemas = await native.host.capabilities({"installation_id": iid})
    row["mcp_reviews"] = {"weather": native_fingerprint(tmp_path, manifest, schemas)}
    plugins.save()
    staged = await native.stage_managed_enable(iid)
    assert staged["status"] == "restart_required" and iid not in native._active
    assert restarts == []
    assert await native.stage_managed_enable(iid) == staged
    committed = await native.commit_managed_activation(staged["transaction_id"])
    assert committed["status"] == "ready" and iid in native._active
    assert await native.commit_managed_activation(staged["transaction_id"]) == committed
    disabling = await native.stage_managed_enable(iid, disable=True)
    assert iid in native._active  # Candidate file is not a current Host grant.
    rolled_back = native.rollback_managed_activation(disabling["transaction_id"])
    assert native.rollback_managed_activation(disabling["transaction_id"]) == rolled_back
    assert iid in native._active and restarts == []
