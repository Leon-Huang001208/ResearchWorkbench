"""Profile routing must preserve old accounts and never share new credentials."""

import json

import pytest

from app.research_web.model_credentials import execute
from app.research_web.model_profile_registry import (
    LEGACY_IDS,
    PROFILE_PREFIX,
    bootstrap_profiles,
    credential_account,
)


class MemoryCredentials:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


def persist(root, state):
    (root / "index.json").write_text(json.dumps(state))


def test_legacy_profiles_keep_exact_original_accounts(tmp_path):
    data = {"sessions": {}, "model": {"provider": "deepseek-official", "model": "deepseek-flash"}}
    registry = bootstrap_profiles(data)
    assert "model_profiles" not in data
    assert (
        registry["items"][LEGACY_IDS["deepseek-official"]]["credential_ref"]
        == "RESEARCH_DSH_API_KEY"
    )
    assert credential_account(tmp_path, "RESEARCH_DSH_API_KEY") == "RESEARCH_DSH_API_KEY"


def test_new_profiles_are_isolated_and_fixed_runtime_ref_follows_selected_route(tmp_path):
    data = {"sessions": {}}
    registry = bootstrap_profiles(data)
    first, second = "a" * 32, "b" * 32
    for identity in (first, second):
        registry["items"][identity] = {
            "id": identity,
            "name": "Synthetic",
            "provider": "deepseek-official",
            "model": "deepseek-flash",
            "credential_ref": PROFILE_PREFIX + identity,
            "credential_mode": "api_key",
            "archived": False,
        }
    registry["routes"]["deepseek-official"] = first
    registry["active_id"] = first
    data["model_profiles"] = registry
    persist(tmp_path, data)
    backend = MemoryCredentials()
    for identity, value in ((first, "synthetic-first"), (second, "synthetic-second")):
        execute(tmp_path, {"op": "set", "ref": PROFILE_PREFIX + identity, "value": value}, backend)
    assert (
        execute(tmp_path, {"op": "resolve", "ref": "RESEARCH_DSH_API_KEY"}, backend)["value"]
        == "synthetic-first"
    )
    registry["routes"]["deepseek-official"] = second
    registry["active_id"] = second
    persist(tmp_path, data)
    assert (
        execute(tmp_path, {"op": "resolve", "ref": "RESEARCH_DSH_API_KEY"}, backend)["value"]
        == "synthetic-second"
    )
    assert (
        execute(tmp_path, {"op": "resolve", "ref": PROFILE_PREFIX + first}, backend)["value"]
        == "synthetic-first"
    )


def test_unknown_profile_ref_and_corrupt_registry_fail_closed(tmp_path):
    with pytest.raises(ValueError):
        credential_account(tmp_path, PROFILE_PREFIX + "a" * 32)
    persist(tmp_path, {"model_profiles": {"version": 99}})
    with pytest.raises(ValueError):
        credential_account(tmp_path, "RESEARCH_DSH_API_KEY")


@pytest.fixture
def profile_api(tmp_path):
    from fastapi.testclient import TestClient
    from test_api import NativeFixture

    from app.research_web.main import create_app
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    backend = MemoryCredentials()
    execute(
        tmp_path, {"op": "set", "ref": "RESEARCH_DSH_API_KEY", "value": "synthetic-legacy"}, backend
    )

    class ProfileRuntime(NativeFixture):
        unknown = False
        reject_after_set = False

        async def rpc(self, method, payload):
            if method == "credentials.describe":
                return {
                    "credentials": {
                        ref: execute(tmp_path, {"op": "describe", "ref": ref}, backend)
                        for ref in payload["refs"]
                    }
                }
            if method in {"credentials.set", "credentials.unset"}:
                execute(tmp_path, {"op": method.split(".")[1], **payload}, backend)
                if self.reject_after_set:
                    from app.research_web.client import RuntimeFailure

                    raise RuntimeFailure("synthetic rejection", "credential/rejected")
                return {}
            if method == "session.list" and self.unknown:
                return {"items": [{"sessionId": "synthetic"}]}
            return await super().rpc(method, payload)

    runtime = ProfileRuntime()
    service = ResearchService(runtime, Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service, runtime, backend


def profile_body(**changes):
    return {
        "name": "Synthetic account",
        "provider": "deepseek-official",
        "model": "deepseek-flash",
        **changes,
    }


def test_profile_api_retains_legacy_and_switches_only_default_route(profile_api):
    client, service, _, backend = profile_api
    listing = client.get("/api/research/model-profiles").json()
    assert listing["items"][0]["credential_configured"] is True
    assert "model_profiles" not in service.store.data
    response = client.post(
        "/api/research/model-profiles", json=profile_body(api_key="synthetic-new")
    )
    assert response.status_code == 200, response.text
    identity = response.json()["id"]
    assert client.post(f"/api/research/model-profiles/{identity}/activate").status_code == 200
    registry = service.model_profile_registry()
    assert registry["active_id"] == identity
    assert "synthetic" not in client.get("/api/research/model-profiles").text.lower().replace(
        "synthetic account", ""
    )
    original_account = next(
        value
        for (_namespace, account), value in backend.values.items()
        if account == "RESEARCH_DSH_API_KEY"
    )
    assert original_account == "synthetic-legacy"
    with pytest.raises(Exception, match="切回原连接"):
        service.assert_session_model_profile({"model_provider": "deepseek-official"})
    service.assert_session_model_profile(
        {"model_provider": "deepseek-official", "model_profile_id": identity}
    )
    assert (
        client.post(
            f"/api/research/model-profiles/{LEGACY_IDS['deepseek-official']}/activate"
        ).status_code
        == 200
    )
    service.assert_session_model_profile({"model_provider": "deepseek-official"})


def test_profile_cannot_activate_missing_key_and_unknown_activity_blocks_save(profile_api):
    client, service, runtime, _ = profile_api
    identity = client.post("/api/research/model-profiles", json=profile_body()).json()["id"]
    assert client.post(f"/api/research/model-profiles/{identity}/activate").status_code == 503
    assert service.model_profile_registry()["active_id"] == LEGACY_IDS["deepseek-official"]
    runtime.unknown = True
    response = client.post("/api/research/model-profiles", json=profile_body())
    assert response.status_code != 200
    assert response.json()["error"]["code"] == "model_activity_unknown"


def test_profile_unknown_credential_receipt_is_durable_and_repairable(profile_api):
    client, service, runtime, _ = profile_api
    runtime.reject_after_set = True
    response = client.post(
        "/api/research/model-profiles", json=profile_body(api_key="synthetic-canary")
    )
    assert response.status_code != 200
    registry = service.model_profile_registry()
    identity = next(
        identity for identity in registry["items"] if identity not in LEGACY_IDS.values()
    )
    assert registry["items"][identity]["uncertain"] is True
    assert (
        json.loads(service.store.index.read_text())["model_profiles"]["items"][identity][
            "uncertain"
        ]
        is True
    )
    assert client.post(f"/api/research/model-profiles/{identity}/activate").status_code != 200
    runtime.reject_after_set = False
    assert (
        client.put(
            f"/api/research/model-profiles/{identity}",
            json=profile_body(api_key="synthetic-repair"),
        ).status_code
        == 200
    )
    assert service.model_profile_registry()["items"][identity]["uncertain"] is False


def test_archive_keeps_profile_and_credential_binding(profile_api):
    client, service, _, backend = profile_api
    identity = client.post(
        "/api/research/model-profiles", json=profile_body(api_key="synthetic-retained")
    ).json()["id"]
    before = dict(backend.values)
    assert client.delete(f"/api/research/model-profiles/{identity}").status_code == 200
    assert backend.values == before
    assert service.model_profile_registry()["items"][identity]["archived"] is True
    assert identity not in [
        item["id"] for item in client.get("/api/research/model-profiles").json()["items"]
    ]


def test_encrypted_profiles_reopen_and_reject_foreign_binding(tmp_path):
    from test_encrypted_model_credentials import store

    from app.research_web.credential_backend import (
        CredentialBackendError,
        EncryptedModelCredentialBackend,
    )

    backend = store(tmp_path / "encrypted", "e" * 32)
    namespace = "org.research-workbench.model." + backend.instance
    ref = PROFILE_PREFIX + "d" * 32
    backend.set_password(namespace, ref, "synthetic-profile")
    reopened = EncryptedModelCredentialBackend(backend.root, backend.key_root, backend.instance)
    assert reopened.get_password(namespace, ref) == "synthetic-profile"
    record = next(backend.root.glob("*.json"))
    assert "synthetic-profile" not in record.read_text()
    envelope = json.loads(record.read_text())
    secret = json.loads(envelope["password"])
    secret["account"] = PROFILE_PREFIX + "f" * 32
    envelope["password"] = json.dumps(secret)
    record.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")))
    record.chmod(0o600)
    with pytest.raises(CredentialBackendError):
        EncryptedModelCredentialBackend(backend.root, backend.key_root, backend.instance)


def test_unknown_receipt_and_disconnected_event_state_block_changes(profile_api):
    client, service, _, _ = profile_api
    service.store.data["receipts"]["synthetic"] = {"status": "unknown"}
    assert client.post("/api/research/model-profiles", json=profile_body()).status_code != 200
    service.store.data["receipts"].clear()
    service.connected.clear()
    assert (
        client.post("/api/research/model-profiles", json=profile_body()).json()["error"]["code"]
        == "model_activity_unknown"
    )


def test_inactive_native_children_are_accepted_by_original_idle_gate(profile_api, monkeypatch):
    client, service, runtime, _ = profile_api
    parent = service.store.create("claw", "Synthetic history")
    parent.update(created=True, status="idle")
    original = runtime.rpc

    async def rpc(method, payload):
        if method == "subagent.list":
            return {"entries": [{"kind": "child", "activity": "inactive"}]}
        return await original(method, payload)

    monkeypatch.setattr(runtime, "rpc", rpc)
    assert client.post("/api/research/model-profiles", json=profile_body()).status_code == 200


def test_referenced_connection_cannot_be_removed_from_recovery_list(profile_api):
    client, service, _, _ = profile_api
    identity = client.post("/api/research/model-profiles", json=profile_body()).json()["id"]
    service.store.data["sessions"]["preserved"] = {
        "id": "preserved",
        "created": False,
        "model_provider": "deepseek-official",
        "model_profile_id": identity,
    }
    response = client.delete(f"/api/research/model-profiles/{identity}")
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "model_profile_referenced"
    assert any(
        row["id"] == identity for row in client.get("/api/research/model-profiles").json()["items"]
    )


def test_schedule_profile_race_fails_before_native_session_create(profile_api, monkeypatch):
    import asyncio

    from app.research_web.client import RuntimeFailure

    client, service, runtime, _ = profile_api
    identity = client.post(
        "/api/research/model-profiles", json=profile_body(api_key="synthetic-race")
    ).json()["id"]
    definition = {
        "description": "Synthetic research",
        "model_provider": "deepseek-official",
        "model_id": "deepseek-flash",
        "output_requirements": "Text",
        "approved_data_sources": ["web"],
        "approved_tools": [],
    }

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        original = service._require_model_credentials

        async def barrier(provider):
            entered.set()
            await release.wait()
            await original(provider)

        monkeypatch.setattr(service, "_require_model_credentials", barrier)
        task = asyncio.create_task(
            service.create_automation_research_session("Synthetic", definition)
        )
        await entered.wait()
        await service.activate_model_profile(identity)
        release.set()
        with pytest.raises(RuntimeFailure) as failure:
            await task
        assert failure.value.code == "model_profile_changed"

    asyncio.run(run())
    assert not any(method == "session.create" for method, _payload in runtime.calls)


def test_active_credential_change_invalidates_old_inference_evidence(profile_api):
    client, service, _, _ = profile_api
    # Materialize the non-secret registry without switching the legacy connection.
    client.post("/api/research/model-profiles", json=profile_body())
    service.store.data["model_test"] = {
        "status": "passed",
        "selection": dict(service.default_model),
    }
    service.store.data["model_application"] = {"selection": dict(service.default_model)}
    response = client.put(
        f"/api/research/model-profiles/{LEGACY_IDS['deepseek-official']}",
        json=profile_body(api_key="synthetic-replacement"),
    )
    assert response.status_code == 200, response.text
    assert "model_test" not in service.store.data
    assert "model_application" not in service.store.data
    service.store.data["model_test"] = {"status": "passed"}
    client.post("/api/research/model-profiles", json=profile_body(api_key="synthetic-inactive"))
    assert service.store.data["model_test"] == {"status": "passed"}


def test_old_api_first_compatible_write_failure_retains_unknown_profile(profile_api):
    client, service, runtime, _ = profile_api
    client.post("/api/research/model-profiles", json=profile_body())
    runtime.reject_after_set = True
    original = runtime.rpc

    async def rpc(method, payload):
        if method == "llm.models":
            return {"groups": [{"id": "openai-compatible", "models": []}], "failures": []}
        return await original(method, payload)

    runtime.rpc = rpc
    response = client.put(
        "/api/research/runtime/model",
        json={
            "provider": "openai-compatible",
            "model": "fixture",
            "base_url": "https://model.example/v1",
            "api_key": "synthetic-new-endpoint",
        },
    )
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "model_configuration_uncertain"
    registry = service.model_profile_registry()
    assert registry["items"][LEGACY_IDS["openai-compatible"]]["uncertain"] is True
    assert service.default_model["provider"] == "deepseek-official"


def test_first_keyless_compatible_profile_can_be_saved_without_prior_route(profile_api):
    client, service, _, _ = profile_api
    response = client.post(
        "/api/research/model-profiles",
        json={
            "name": "Local fixture",
            "provider": "openai-compatible",
            "model": "local-demo",
            "base_url": "http://127.0.0.1:9000/v1",
            "credential_mode": "none",
        },
    )
    assert response.status_code == 200, response.text
    row = next(
        item
        for item in client.get("/api/research/model-profiles").json()["items"]
        if item["id"] == response.json()["id"]
    )
    assert row["credential_required"] is False
    assert row["active"] is False
    assert service.default_model["provider"] == "deepseek-official"


def test_current_compatible_route_key_change_invalidates_prepared_generation(profile_api):
    client, service, runtime, _ = profile_api
    original = runtime.rpc

    async def rpc(method, payload):
        if method == "llm.models":
            return {
                "groups": [
                    {"id": "deepseek-official", "models": [{"id": "deepseek-flash"}]},
                    {"id": "openai-compatible", "models": [{"id": "fixture"}]},
                ],
                "failures": [],
            }
        return await original(method, payload)

    runtime.rpc = rpc
    body = {
        "name": "Compatible synthetic",
        "provider": "openai-compatible",
        "model": "fixture",
        "base_url": "https://model.example/v1",
        "api_key": "synthetic-first",
    }
    result = client.post("/api/research/model-profiles", json=body)
    assert result.status_code == 200, result.text
    identity = result.json()["id"]
    assert client.post(f"/api/research/model-profiles/{identity}/activate").status_code == 200
    assert (
        client.post(
            f"/api/research/model-profiles/{LEGACY_IDS['deepseek-official']}/activate"
        ).status_code
        == 200
    )
    before = service.compatible_connection()["revision"]
    service.store.data["model_test"] = {
        "status": "passed",
        "selection": dict(service.default_model),
    }
    response = client.put(
        f"/api/research/model-profiles/{identity}",
        json={**body, "api_key": "synthetic-replacement"},
    )
    assert response.status_code == 200, response.text
    assert service.compatible_connection()["revision"] != before
    assert service.store.data["model_test"]["status"] == "passed"
