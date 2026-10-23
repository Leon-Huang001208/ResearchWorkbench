"""Offline candidate, credentials, exact budgets and session raw-result protection."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.research_web.mcp_runtime.authorization import AuthorizationError, AuthorizationManager
from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
from app.research_web.mcp_runtime.evidence import MCPResultEvidence
from app.research_web.mcp_runtime.seek_alpha import (
    CREDENTIAL_SLOT,
    ENDPOINT,
    QUERIES,
    TOOL_NAMES,
    candidate,
    evaluation_preview,
)
from app.research_web.mcp_runtime.service import MCPRuntimeError, MCPRuntimeService
from app.research_web.mcp_runtime.transport import RemoteTarget
from app.research_web.store import Store, StoreError

INSTALLATION = "mcp-installation-" + "a" * 32
VERSION = "1.0.0"


@contextmanager
def assert_code(expected):
    with pytest.raises(MCPRuntimeError) as failure:
        yield
    assert expected in failure.value.code


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


@pytest.fixture(autouse=True)
def forbid_real_credentials(monkeypatch):
    import keyring

    def fail(*_args, **_kwargs):
        raise AssertionError("real credentials forbidden")

    for name in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, name, fail)
    monkeypatch.setattr("app.research_web.mcp_runtime.credentials.default_credential_backend", fail)


def register(root, sid):
    authorization = AuthorizationManager(root)
    for query in QUERIES:
        tool = authorization.register_tool(
            installation_id=INSTALLATION,
            version=VERSION,
            tool_name=TOOL_NAMES[query],
            input_schema={"type": "object"},
            output_schema=None,
            risk_tier="read_only",
        )
        authorization.authorize_session(
            session_id=sid,
            installation_id=INSTALLATION,
            version=VERSION,
            tool_name=tool["tool_name"],
            schema_sha256=tool["schema_sha256"],
        )
    return authorization


def approved(authorization, sid, *, maximum=54):
    preview = evaluation_preview(authorization.list_tools(), "2026-10-23")
    budget = authorization.authorize_budget(
        session_id=sid,
        installation_id=INSTALLATION,
        version=VERSION,
        entries=preview["entries"],
        catalog_sha256=preview["catalog_sha256"],
        max_credits=maximum,
        confirmed=True,
    )
    return preview, budget


def call_for(sid, entry, budget, call_id="sample-1"):
    return {
        "call_id": call_id,
        "session_id": sid,
        "installation_id": INSTALLATION,
        "version": VERSION,
        "tool_name": entry["tool_name"],
        "schema_sha256": entry["schema_sha256"],
        "arguments": entry["arguments"],
        "budget_id": budget["id"],
    }


def test_candidate_is_fixed_and_never_report_admitted():
    value = candidate()
    assert value["enabled"] is False and value["report_admitted"] is False
    assert value["calls"] == 18 and value["max_credits"] == 54
    assert ENDPOINT == "https://seek-alpha.cn/mcp/rpc"


def test_fixed_preview_validates_current_schema_and_public_parameters(tmp_path):
    auth = register(tmp_path, "owned")
    preview = evaluation_preview(auth.list_tools(), "2026-10-23")
    assert len(preview["entries"]) == 18
    chain = next(item for item in preview["entries"] if item["query"] == "supply_chain")
    assert chain["arguments"] == {"code": "600519"}
    assert preview["current_only"] == ["supply_chain"]
    incompatible = auth.list_tools()
    incompatible[0]["input_schema"] = {"type": "object", "required": ["unexpected"]}
    with pytest.raises(AuthorizationError, match="schema_incompatible"):
        evaluation_preview(incompatible, "2026-10-23")
    external = auth.list_tools()
    external[0]["input_schema"] = {"$ref": "https://example.invalid/schema"}
    with pytest.raises(AuthorizationError):
        evaluation_preview(external, "2026-10-23")
    for item in preview["entries"]:
        item["arguments"]["private_document"] = "not allowed"
    with pytest.raises(AuthorizationError, match="private_arguments"):
        auth.authorize_budget(
            session_id="owned",
            installation_id=INSTALLATION,
            version=VERSION,
            entries=preview["entries"],
            catalog_sha256=preview["catalog_sha256"],
            max_credits=54,
            confirmed=True,
        )


def test_budget_missing_confirmation_insufficient_credit_unknown_and_restart(tmp_path):
    auth = register(tmp_path, "owned")
    preview = evaluation_preview(auth.list_tools(), "2026-10-23")
    with pytest.raises(AuthorizationError, match="confirmation_required"):
        auth.authorize_budget(
            session_id="owned",
            installation_id=INSTALLATION,
            version=VERSION,
            entries=preview["entries"],
            catalog_sha256=preview["catalog_sha256"],
            max_credits=54,
        )
    preview, budget = approved(auth, "owned", maximum=3)
    first = call_for("owned", preview["entries"][0], budget)
    assert auth.reserve_paid_call(**first)["dispatch"] is True
    assert AuthorizationManager(tmp_path).reserve_paid_call(**first)["dispatch"] is False
    auth.transition_paid_call(first["call_id"], session_id="owned", status="dispatched")
    auth.transition_paid_call(first["call_id"], session_id="owned", status="unknown")
    other = call_for("owned", preview["entries"][1], budget, "sample-2")
    with pytest.raises(AuthorizationError, match="exhausted"):
        AuthorizationManager(tmp_path).reserve_paid_call(**other)
    with pytest.raises(AuthorizationError, match="evidence_reference_required"):
        auth.transition_paid_call(first["call_id"], session_id="owned", status="completed")
    with pytest.raises(AuthorizationError, match="transition_invalid"):
        auth.transition_paid_call(first["call_id"], session_id="owned", status="known_unsent")
    changed = {**first, "arguments": {"code": "688981"}}
    with pytest.raises(AuthorizationError, match="identity_conflict"):
        auth.reserve_paid_call(**changed)
    # Lock-internal reload retains updates from an independently constructed manager.
    peer = AuthorizationManager(tmp_path)
    peer.authorize_session(
        session_id="another",
        installation_id=INSTALLATION,
        version=VERSION,
        tool_name=first["tool_name"],
        schema_sha256=first["schema_sha256"],
    )
    assert auth.has_session_authorization(session_id="another", installation_id=INSTALLATION)


def _reserve_in_process(root, payload, start, output):
    try:
        auth = AuthorizationManager(root)
        start.wait(5)
        output.put(auth.reserve_paid_call(**payload)["dispatch"])
    except AuthorizationError as exc:
        output.put(exc.code)


def test_two_processes_cannot_reserve_same_reviewed_cell_twice(tmp_path):
    auth = register(tmp_path, "owned")
    preview, budget = approved(auth, "owned")
    context = multiprocessing.get_context("spawn")
    start, output = context.Event(), context.Queue()
    workers = [
        context.Process(
            target=_reserve_in_process,
            args=(
                tmp_path,
                call_for("owned", preview["entries"][0], budget, f"parallel-{index}"),
                start,
                output,
            ),
        )
        for index in range(2)
    ]
    for worker in workers:
        worker.start()
    start.set()
    results = [output.get(timeout=10) for _ in workers]
    for worker in workers:
        worker.join(10)
        assert worker.exitcode == 0
    assert results.count(True) == 1
    assert set(results) <= {True, "mcp_budget_call_reserved", "mcp_authorization_storage_busy"}


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    store = Store(tmp_path)
    sid = store.create("claw", "Owned")["id"]
    authorization = register(tmp_path, sid)
    backend = MemoryCredentials()
    credentials = RuntimeCredentialStore(backend)
    state = {"revoked": False, "calls": 0, "fail": False, "oversize": False}

    def managed(*_args, **_kwargs):
        if state["revoked"]:
            raise ValueError("revoked")
        return "approved", "candidate"

    monkeypatch.setattr("app.research_web.plugins.mcp_policy.managed_binding", managed)
    monkeypatch.setattr("app.research_web.plugins.mcp_policy.requires_managed", lambda *_args: True)
    native = {"id": INSTALLATION, "plan": {"endpoint": ENDPOINT, "server_version": VERSION}}

    async def capabilities(_target):
        return {"tools": []}

    async def invoke(_target, _name, _arguments):
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("unknown submission")
        if state["oversize"]:
            return {"content": [{"text": "x" * (3 * 1024 * 1024)}]}
        return {"content": [{"type": "text", "text": "source result"}]}

    host = SimpleNamespace(credentials=credentials, capabilities=capabilities, call_tool=invoke)
    service = MCPRuntimeService(
        tmp_path,
        enabled=True,
        managed_only=True,
        evidence_store=store,
        store=SimpleNamespace(get=lambda _iid: native),
        host=host,
        authorization=authorization,
        installer=SimpleNamespace(
            target=lambda _manifest: RemoteTarget(ENDPOINT, INSTALLATION, ENDPOINT)
        ),
    )
    service._active.add(INSTALLATION)
    return service, store, sid, state, backend


def test_static_bearer_fixed_binding_no_secret_projection_or_file(runtime):
    service, store, _sid, state, backend = runtime
    for resource, slot in ((ENDPOINT + "/wrong", CREDENTIAL_SLOT), (ENDPOINT, "oauth")):
        with assert_code("binding_invalid"):
            service.static_credential(
                INSTALLATION, resource=resource, slot=slot, token="secret-one"
            )
    result = service.static_credential(INSTALLATION, resource=ENDPOINT, token="secret-one")
    assert result == {"configured": True, "resource": ENDPOINT, "slot": CREDENTIAL_SLOT}
    assert "secret-one" not in json.dumps(result)
    assert all("secret-one" not in path.read_text() for path in store.root.rglob("*.json"))
    assert any("secret-one" in value for value in backend.values.values())
    state["revoked"] = True
    with assert_code("approval_required"):
        service.static_credential(INSTALLATION, resource=ENDPOINT, token="secret-two")
    state["revoked"] = False
    assert (
        service.static_credential(INSTALLATION, resource=ENDPOINT, delete=True)["configured"]
        is False
    )


@pytest.mark.asyncio
async def test_paid_call_budget_before_dispatch_freezes_original_and_recovers(runtime):
    service, store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)
    with assert_code("budget_required"):
        await service.call_tool(**{**request, "budget_id": None})
    assert state["calls"] == 0
    response = await service.call_tool(**request)
    assert state["calls"] == 1 and response["cost"]["status"] == "completed"
    detail = await service.read_frozen_result(sid, response["evidence"]["dataset_id"])
    assert detail["result"] == response["result"]
    assert detail["manifest"]["provider_metadata"]["admission"]["report_admitted"] is False
    repeated = await service.call_tool(**request)
    assert repeated["recovered"] is True and state["calls"] == 1
    state["revoked"] = True
    with assert_code("approval_required"):
        service.assert_frozen_result_authorized(sid, response["evidence"]["dataset_id"])
    state["revoked"] = False
    with pytest.raises(StoreError):
        service.assert_frozen_result_authorized("not-owned", response["evidence"]["dataset_id"])
    # All receipt persistence carries only identity hashes and result handles.
    persisted = json.loads((store.root / "mcp-runtime/authorizations.json").read_text())
    assert "source result" not in json.dumps(persisted)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["fail", "oversize"])
async def test_exception_or_oversized_response_holds_budget_and_never_reissues(runtime, failure):
    service, _store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid, maximum=3)
    request = call_for(sid, preview["entries"][0], budget)
    state[failure] = True
    with pytest.raises((MCPRuntimeError, StoreError)):
        await service.call_tool(**request)
    assert (
        service.authorization.paid_call(request["call_id"], session_id=sid)["status"] == "unknown"
    )
    with pytest.raises(StoreError, match="禁止重发"):
        await service.call_tool(**request)
    assert state["calls"] == 1
    state[failure] = False
    with assert_code("exhausted"):
        await service.call_tool(**call_for(sid, preview["entries"][1], budget, "another"))
    assert state["calls"] == 1


@pytest.mark.asyncio
async def test_cancelled_provider_is_unknown_and_does_not_refund(runtime):
    service, _store, sid, _state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)

    async def cancel(*_args):
        raise asyncio.CancelledError

    service.host.call_tool = cancel
    with pytest.raises(asyncio.CancelledError):
        await service.call_tool(**request)
    assert (
        service.authorization.paid_call(request["call_id"], session_id=sid)["status"] == "unknown"
    )


def test_frozen_raw_hash_corruption_and_source_version_never_silently_refresh(runtime):
    service, store, sid, _state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)
    evidence = MCPResultEvidence(store)
    reference = evidence.freeze(request, {"content": [{"text": "original"}]}, endpoint=ENDPOINT)
    with pytest.raises(StoreError, match="身份冲突"):
        evidence.freeze(request, {"content": [{"text": "updated"}]}, endpoint=ENDPOINT)
    raw = store.root / ".control/snapshots" / sid / reference["dataset_id"] / "raw-0001.bin"
    raw.write_bytes(b"{}")
    with pytest.raises(StoreError, match="hash"):
        evidence.read(sid, reference["dataset_id"])


@pytest.mark.asyncio
async def test_snapshot_storage_failure_retains_original_and_can_complete_without_redispatch(
    runtime, monkeypatch
):
    from app.research_web.datahub import snapshots

    service, _store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)
    rename = snapshots.rename_directory
    failed = False

    def fail_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated storage interruption")
        return rename(*args)

    monkeypatch.setattr(snapshots, "rename_directory", fail_once)
    with pytest.raises((MCPRuntimeError, StoreError)):
        await service.call_tool(**request)
    assert (
        service.authorization.paid_call(request["call_id"], session_id=sid)["status"] == "unknown"
    )
    recovered = await service.call_tool(**request)
    assert recovered["recovered"] is True and state["calls"] == 1
    assert recovered["cost"]["status"] == "completed"
    assert recovered["result"]["content"][0]["text"] == "source result"


@pytest.mark.asyncio
async def test_provider_echoed_credential_never_reaches_response_or_snapshot(runtime):
    service, store, sid, _state, _backend = runtime
    service.static_credential(INSTALLATION, resource=ENDPOINT, token="do-not-echo-me")
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)

    async def echoed(*_args):
        return {"content": [{"text": "Bearer do-not-echo-me"}]}

    service.host.call_tool = echoed
    with assert_code("contains_credential"):
        await service.call_tool(**request)
    assert all("do-not-echo-me" not in path.read_text() for path in store.root.rglob("*.json"))
    assert (
        service.authorization.paid_call(request["call_id"], session_id=sid)["status"] == "unknown"
    )


def test_known_unsent_is_only_safe_release_and_cross_session_or_drift_cannot_spend(tmp_path):
    auth = register(tmp_path, "owned")
    preview, budget = approved(auth, "owned", maximum=3)
    first = call_for("owned", preview["entries"][0], budget)
    auth.reserve_paid_call(**first)
    auth.transition_paid_call(first["call_id"], session_id="owned", status="known_unsent")
    assert (
        auth.reserve_paid_call(**{**first, "call_id": "explicit-new-attempt"})["dispatch"] is True
    )
    with pytest.raises(AuthorizationError, match="budget_required"):
        auth.reserve_paid_call(**{**first, "session_id": "other-account-session"})
    auth.register_tool(
        installation_id=INSTALLATION,
        version=VERSION,
        tool_name=first["tool_name"],
        input_schema={"type": "object", "required": ["changed"]},
        output_schema=None,
        risk_tier="read_only",
    )
    with pytest.raises(AuthorizationError, match="authorization_required|schema_drift"):
        auth.reserve_paid_call(**first)


@pytest.mark.asyncio
async def test_explicit_evaluation_action_uses_fixed_call_identity_and_recovers(runtime):
    service, _store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    entry = preview["entries"][0]
    arguments = {
        "session_id": sid,
        "budget_id": budget["id"],
        "entry_id": entry["subject"] + ":" + entry["query"],
    }
    first = await service.evaluation_call(INSTALLATION, **arguments)
    second = await service.evaluation_call(INSTALLATION, **arguments)
    assert first["evidence"] == second["evidence"]
    assert second["recovered"] is True and state["calls"] == 1
    with assert_code("not_reviewed"):
        await service.evaluation_call(INSTALLATION, **{**arguments, "entry_id": "unapproved"})


def test_plugin_credential_routes_expose_status_only_and_refuse_wrong_resource(
    runtime, monkeypatch
):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.research_web import plugin_routes
    from app.research_web.mcp_registry.service import RegistryError

    service, _store, _sid, _state, _backend = runtime
    app = FastAPI()
    app.include_router(plugin_routes.router)
    app.state.research = SimpleNamespace(
        mcp_runtime=service,
        plugins=SimpleNamespace(_reviewed=lambda _digest: {"mcp_bindings": {"seek": INSTALLATION}}),
    )
    monkeypatch.setattr(plugin_routes, "tenant_enabled", lambda: False)

    @app.exception_handler(RegistryError)
    async def error(_request: Request, exception: RegistryError):
        return JSONResponse({"error": {"code": exception.code}}, status_code=exception.status)

    prefix = "/api/research/plugins/" + "a" * 64 + "/mcp/seek/"
    with TestClient(app) as client:
        saved = client.post(
            prefix + "credential-save", json={"resource": ENDPOINT, "token": "safe-fixture"}
        )
        assert saved.status_code == 200 and saved.json()["configured"] is True
        assert "safe-fixture" not in saved.text
        status = client.post(prefix + "credential-status", json={"resource": ENDPOINT})
        assert status.json() == {"configured": True, "resource": ENDPOINT, "slot": CREDENTIAL_SLOT}
        denied = client.post(
            prefix + "credential-save",
            json={"resource": "https://wrong.invalid/mcp", "token": "safe-fixture"},
        )
        assert denied.status_code == 403 and "safe-fixture" not in denied.text
        deleted = client.post(prefix + "credential-delete", json={"resource": ENDPOINT})
        assert deleted.json()["configured"] is False


def test_tenant_gateway_credential_route_is_bound_to_authenticated_user(tmp_path):
    import httpx
    from fastapi.testclient import TestClient
    from test_multiuser_gateway import Pool

    from app.research_web.multiuser.accounts import AccountStore
    from app.research_web.multiuser.gateway import create_gateway

    accounts = AccountStore(tmp_path / "server")
    consumer = accounts.create_user("consumer", "safe fixture password")
    seen = []

    def upstream(request):
        seen.append(request)
        return httpx.Response(
            200, json={"configured": True, "resource": ENDPOINT, "slot": CREDENTIAL_SLOT}
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_gateway(accounts, Pool(), origin="http://localhost", upstream=transport)
    with TestClient(app, base_url="http://localhost") as client:
        client.post(
            "/api/server/login",
            json={"username": "consumer", "password": "safe fixture password"},
            headers={"Origin": "http://localhost"},
        )
        path = "/api/server/plugins/mcp/" + "a" * 64 + "/seek/credential-save"
        for header in (None, "different-user"):
            headers = {"Origin": "http://localhost"}
            if header:
                headers["X-RWB-Page-User"] = header
            denied = client.post(
                path, json={"resource": ENDPOINT, "token": "fixture-secret"}, headers=headers
            )
            assert denied.status_code == 401
        assert seen == []
        response = client.post(
            path,
            json={"resource": ENDPOINT, "token": "fixture-secret"},
            headers={"Origin": "http://localhost", "X-RWB-Page-User": consumer.id},
        )
        assert response.status_code == 200
        assert seen[0].url.path.endswith("/mcp/seek/credential-save")
        assert seen[0].headers["X-RWB-Plugin-Actor"] == consumer.id
        assert "fixture-secret" not in response.text


@pytest.mark.asyncio
async def test_first_party_candidate_imports_without_claiming_registry_or_tools(tmp_path):
    from app.research_web.plugins.packages import PluginError, parse_archive
    from app.research_web.plugins.seek_alpha_candidate import candidate_archive
    from app.research_web.plugins.service import PluginService

    raw = candidate_archive()
    assert raw == candidate_archive(), "candidate bytes must be reproducible"
    parsed = parse_archive(raw)
    assert parsed["name"] == "seek-alpha-candidate"
    assert list(parsed["files"]) == ["plugin.json", ".mcp.json", "README.md"]
    assert ENDPOINT.encode() in parsed["files"][".mcp.json"]
    assert b"access_token" not in raw
    service = PluginService(tmp_path, idle_gate=lambda: True)
    item = service.preview(raw)
    assert item["components"][0]["support"] == "unsupported"
    assert item["components"][0]["reason"] == "native_registry_selection_required"
    service.review(item["digest"], item["permissions"], "administrator")
    await service.enable(item["digest"])
    status = service.detail(item["digest"])
    assert all(part["ready"] is False for part in status["components"])
    with pytest.raises(PluginError, match="loader_unavailable"):
        await service.mcp_preview(item["digest"], "host-mcp")


@pytest.mark.asyncio
async def test_soft_deleted_source_retains_read_only_evidence_and_still_checks_revocation(runtime):
    service, store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)
    result = await service.call_tool(**request)
    store.soft_delete(sid)
    retained = await service.read_frozen_result(sid, result["evidence"]["dataset_id"])
    assert retained["result"] == result["result"]
    state["revoked"] = True
    with assert_code("approval_required"):
        await service.read_frozen_result(sid, result["evidence"]["dataset_id"])
    with pytest.raises(StoreError):
        await service.evaluation_call(
            INSTALLATION,
            session_id=sid,
            budget_id=budget["id"],
            entry_id=preview["entries"][0]["subject"] + ":" + preview["entries"][0]["query"],
        )


@pytest.mark.asyncio
async def test_revocation_during_provider_response_denies_exposure_but_retains_original(runtime):
    service, store, sid, state, _backend = runtime
    preview, budget = approved(service.authorization, sid)
    request = call_for(sid, preview["entries"][0], budget)

    async def revoke(*_args):
        state["calls"] += 1
        state["revoked"] = True
        return {"content": [{"text": "retained after revocation"}]}

    service.host.call_tool = revoke
    with assert_code("approval_required"):
        await service.call_tool(**request)
    did = MCPResultEvidence.dataset_id(sid, request["call_id"])
    assert (
        MCPResultEvidence(store).read(sid, did)["result"]["content"][0]["text"]
        == "retained after revocation"
    )
    with assert_code("approval_required"):
        await service.read_frozen_result(sid, did)
    state["revoked"] = False
    recovered = await service.call_tool(**request)
    assert recovered["recovered"] is True and state["calls"] == 1
