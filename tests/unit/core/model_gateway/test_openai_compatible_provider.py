"""OpenAI-compatible provider fallback behavior."""

from __future__ import annotations

import json

import httpx
import pytest

from core.model_gateway.providers import openai_compatible as provider_module
from core.model_gateway.providers.openai_compatible import OpenAICompatibleProvider
from core.settings.config import ProviderProfile


def _profile(api_key: str = "test-secret") -> ProviderProfile:
    return ProviderProfile(
        name="configured-provider",
        protocol="openai_compatible",
        base_url="https://models.example.test/v1",
        api_key=api_key,
    )


def _fallback_provider(
    monkeypatch: pytest.MonkeyPatch,
    handler: httpx.MockTransport,
    *,
    api_key: str = "test-secret",
) -> OpenAICompatibleProvider:
    monkeypatch.setattr(provider_module, "OpenAIClient", None)
    provider = OpenAICompatibleProvider(_profile(api_key))
    provider._http_client.close()
    provider._http_client = httpx.Client(
        transport=handler,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )
    return provider


def test_chat_uses_httpx_fallback_when_openai_sdk_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "reasoning-model",
                "choices": [{"message": {"content": '{"conclusion":"ok"}'}}],
                "usage": {"total_tokens": 42},
            },
        )

    provider = _fallback_provider(monkeypatch, httpx.MockTransport(handle))

    response = provider.chat(
        messages=[{"role": "user", "content": "synthetic"}],
        model="reasoning-model",
        temperature=0.0,
        max_tokens=4096,
        response_format={"type": "json_object"},
        timeout=7.0,
    )

    assert response.content == '{"conclusion":"ok"}'
    assert response.provider == "configured-provider"
    assert response.model_name == "reasoning-model"
    assert response.tokens_used == 42
    assert len(requests) == 1
    request = requests[0]
    assert request.url == "https://models.example.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-secret"
    sent = json.loads(request.content)
    assert sent == {
        "model": "reasoning-model",
        "messages": [{"role": "user", "content": "synthetic"}],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    assert request.extensions["timeout"]["read"] == 7.0


def test_chat_keeps_client_timeout_when_no_request_override_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeouts: list[dict[str, float | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(
            200,
            json={
                "model": "reasoning-model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1},
            },
        )

    provider = _fallback_provider(monkeypatch, httpx.MockTransport(handle))

    provider.chat(
        messages=[{"role": "user", "content": "synthetic"}],
        model="reasoning-model",
    )

    assert timeouts == [{"connect": 30.0, "read": 120.0, "write": 120.0, "pool": 120.0}]


def test_chat_never_substitutes_reasoning_content_for_final_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hidden_reasoning = "private-reasoning-must-not-leak"

    def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "reasoning-model",
                "choices": [{"message": {"content": "", "reasoning_content": hidden_reasoning}}],
                "usage": {"total_tokens": 99},
            },
        )

    provider = _fallback_provider(monkeypatch, httpx.MockTransport(handle))

    response = provider.chat(
        messages=[{"role": "user", "content": "synthetic"}],
        model="reasoning-model",
    )

    assert response.content == ""
    assert hidden_reasoning not in response.model_dump_json()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": {"message": "secret-in-body"}}),
        httpx.Response(200, content=b"not-json"),
    ],
)
def test_httpx_fallback_errors_are_generic_and_do_not_leak_credentials(
    monkeypatch: pytest.MonkeyPatch,
    response: httpx.Response,
) -> None:
    api_key = "credential-must-not-leak"

    def handle(_request: httpx.Request) -> httpx.Response:
        return response

    provider = _fallback_provider(
        monkeypatch,
        httpx.MockTransport(handle),
        api_key=api_key,
    )

    result = provider.chat(
        messages=[{"role": "user", "content": "synthetic"}],
        model="reasoning-model",
    )

    assert result.content == "Error: configured provider request failed"
    assert api_key not in result.model_dump_json()
    assert "secret-in-body" not in result.model_dump_json()
