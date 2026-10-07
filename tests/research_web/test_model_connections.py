"""One declared compatible connection; no ambient key or fake key requirement."""

import pytest
from pydantic import ValidationError

from app.research_web.main import ModelConfig


def compatible(**changes):
    value = {
        "provider": "openai-compatible",
        "model": "qwen3:0.6b",
        "base_url": "http://127.0.0.1:11434/v1",
        "protocol": "openai-completions",
        "credential_mode": "none",
    }
    value.update(changes)
    return value


def test_keyless_local_connection_does_not_require_a_fake_key():
    value = ModelConfig.model_validate(compatible())
    assert value.api_key is None
    assert value.credential_mode == "none"
    assert value.base_url == "http://127.0.0.1:11434/v1"


def test_keyless_connection_rejects_secret_input():
    with pytest.raises(ValidationError):
        ModelConfig.model_validate(compatible(api_key="synthetic-contract-value"))


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/model",
        "http://user:password@127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1?token=synthetic",
        "http://127.0.0.1:11434/v1#fragment",
        "http://127.0.0.1:11434/v1\x7f",
        "http://127.0.0.1:11434/v1\x85",
    ],
)
def test_connection_rejects_secret_or_non_network_endpoint(url):
    with pytest.raises(ValidationError):
        ModelConfig.model_validate(compatible(base_url=url))


def test_authenticated_compatible_connection_keeps_blank_key_for_preservation():
    value = ModelConfig.model_validate(
        compatible(base_url="https://model.example/v1", credential_mode="api_key")
    )
    assert value.api_key is None
    assert value.credential_mode == "api_key"


def test_original_deepseek_configuration_keeps_its_contract():
    value = ModelConfig.model_validate({"model": "deepseek-flash"})
    assert value.provider == "deepseek-official"
    assert value.api_key is None


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from test_api import NativeFixture

    from app.research_web.main import create_app
    from app.research_web.service import ResearchService
    from app.research_web.store import Store

    service = ResearchService(NativeFixture(), Store(tmp_path))
    with TestClient(create_app(service)) as client:
        service.connected = {"mux", "host"}
        yield client, service


def test_native_connection_channel_is_private_and_never_returns_secret_fields(api):
    client, service = api
    path = "/api/research/internal/data/model-connection"
    assert client.get(path).status_code == 403
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    assert client.get(path, headers=headers).json() == {"connection": None}
    service.store.data["compatible_model_connection"] = compatible()
    assert client.get(path, headers=headers).json() == {"connection": compatible()}
    service.store.data["compatible_model_connection"]["api_key"] = "synthetic-secret"
    response = client.get(path, headers=headers)
    assert response.status_code != 200
    assert "synthetic-secret" not in response.text


@pytest.mark.parametrize(
    "url", ["https://user:synthetic@example.test/v1", "https://example.test/v1?token=synthetic"]
)
def test_private_connection_projection_rejects_secret_url_content(api, url):
    client, service = api
    service.store.data["compatible_model_connection"] = compatible(
        base_url=url, credential_mode="api_key"
    )
    response = client.get(
        "/api/research/internal/data/model-connection",
        headers={"X-Research-Data-Key": service.datahub.control["token"]},
    )
    assert response.status_code != 200
    assert "synthetic" not in response.text


def compatible_native(service):
    native = service.client
    original = native.rpc
    values = {"RESEARCH_DSH_API_KEY": "synthetic-original"}

    async def rpc(method, payload):
        if method == "llm.models":
            result = await original(method, payload)
            result["groups"].append({"id": "openai-compatible", "models": []})
            return result
        if method.startswith("credentials."):
            native.calls.append((method, payload))
            if method == "credentials.describe":
                return {
                    "credentials": {
                        ref: {
                            "configured": bool(values.get(ref)),
                            "source": "system-keychain",
                            "writable": True,
                        }
                        for ref in payload["refs"]
                    }
                }
            if method == "credentials.set":
                values[payload["ref"]] = payload["value"]
            if method == "credentials.unset":
                values.pop(payload["ref"], None)
            return {}
        return await original(method, payload)

    native.rpc = rpc
    return values


def test_page_keyless_save_and_restore_do_not_consult_original_credentials(api):
    client, service = api
    values = compatible_native(service)
    response = client.put("/api/research/runtime/model", json=compatible())
    assert response.status_code == 200
    assert values == {"RESEARCH_DSH_API_KEY": "synthetic-original"}
    assert not any(m.startswith("credentials.") for m, _ in service.client.calls)
    runtime = client.get("/api/research/runtime").json()
    assert runtime["credential_required"] is False
    assert runtime["credential_configured"] is None
    assert runtime["credential_storage"] == "not_required"
    assert runtime["inference_verified"] is False
    assert len(service.store.data["compatible_model_connection_revision"]) == 32
    from app.research_web.store import Store

    restored = Store(service.store.root)
    assert restored.data["model"]["provider"] == "openai-compatible"
    assert restored.data["compatible_model_connection"] == compatible()


def test_compatible_replace_preserve_clear_and_endpoint_change_do_not_touch_original(api):
    client, service = api
    values = compatible_native(service)
    body = compatible(credential_mode="api_key", api_key="synthetic-compatible-a")
    path = "/api/research/runtime/model"
    assert client.put(path, json=body).status_code == 200
    first_revision = service.store.data["compatible_model_connection_revision"]
    body.pop("api_key")
    assert client.put(path, json=body).status_code == 200
    assert values["RESEARCH_COMPAT_API_KEY"] == "synthetic-compatible-a"
    assert service.store.data["compatible_model_connection_revision"] != first_revision
    denied = client.put(path, json={**body, "base_url": "https://other.example/v1"})
    assert denied.status_code >= 400
    assert values["RESEARCH_COMPAT_API_KEY"] == "synthetic-compatible-a"
    assert client.put(path, json={**body, "api_key": "synthetic-compatible-b"}).status_code == 200
    assert client.put(path, json={**body, "clear_api_key": True}).status_code == 200
    assert "RESEARCH_COMPAT_API_KEY" not in values
    assert values["RESEARCH_DSH_API_KEY"] == "synthetic-original"


def test_compatible_write_failure_does_not_block_original_provider(api):
    from app.research_web.client import RuntimeFailure

    client, service = api
    values = compatible_native(service)
    old_sid = client.post("/api/research/sessions", json={}).json()["id"]
    original = service.client.rpc

    async def fail_after_write(method, payload):
        result = await original(method, payload)
        if method == "credentials.set" and payload["ref"] == "RESEARCH_COMPAT_API_KEY":
            raise RuntimeFailure("synthetic unconfirmed write")
        return result

    service.client.rpc = fail_after_write
    response = client.put(
        "/api/research/runtime/model",
        json=compatible(credential_mode="api_key", api_key="synthetic-compatible"),
    )
    assert response.status_code >= 400
    assert service.store.data["compatible_model_configuration_uncertain"] is True
    assert not service.store.data.get("model_configuration_uncertain")
    assert service.default_model["provider"] == "deepseek-official"
    assert values["RESEARCH_DSH_API_KEY"] == "synthetic-original"
    assert (
        client.post(
            f"/api/research/sessions/{old_sid}/messages",
            json={"text": "原服务保持可用"},
            headers={"Idempotency-Key": "original-after-compatible-failure"},
        ).status_code
        == 202
    )


def test_new_endpoint_cannot_silently_receive_an_existing_session_history(api):
    client, service = api
    compatible_native(service)
    path = "/api/research/runtime/model"
    assert client.put(path, json=compatible()).status_code == 200
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    assert (
        client.put(path, json=compatible(base_url="http://127.0.0.1:11435/v1")).status_code == 200
    )
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "不改投新地址"},
        headers={"Idempotency-Key": "old-connection-blocked"},
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "model_connection_changed"


def test_clear_blocks_next_submission_for_existing_and_new_compatible_sessions(api):
    client, service = api
    compatible_native(service)
    body = compatible(credential_mode="api_key", api_key="synthetic-compatible")
    path = "/api/research/runtime/model"
    assert client.put(path, json=body).status_code == 200
    old = client.post("/api/research/sessions", json={}).json()["id"]
    body.pop("api_key")
    assert client.put(path, json={**body, "clear_api_key": True}).status_code == 200
    new = client.post("/api/research/sessions", json={}).json()["id"]
    for sid in [old, new]:
        response = client.post(
            f"/api/research/sessions/{sid}/messages",
            json={"text": "清除后不请求模型"},
            headers={"Idempotency-Key": "cleared-compatible-" + sid},
        )
        assert response.status_code >= 400
        assert response.json()["error"]["code"] == "model_credentials_missing"


def test_active_original_task_blocks_compatible_configuration_mutation(api):
    client, service = api
    values = compatible_native(service)
    sid = client.post("/api/research/sessions", json={}).json()["id"]
    service.client.running.add(sid)
    response = client.put("/api/research/runtime/model", json=compatible())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "model_change_busy"
    assert "compatible_model_connection" not in service.store.data
    assert values == {"RESEARCH_DSH_API_KEY": "synthetic-original"}
