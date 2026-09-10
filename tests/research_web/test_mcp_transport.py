"""MCP Host transport, OAuth and credential isolation contracts."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.research_web.mcp_runtime import credentials as credential_module
from app.research_web.mcp_runtime.credentials import (
    KEYRING_SERVICE,
    RuntimeCredentialError,
    RuntimeCredentialStore,
)
from app.research_web.mcp_runtime.oauth import (
    OAuthCoordinator,
    OAuthDiscovery,
    OAuthError,
)
from app.research_web.mcp_runtime.sdk_host import MCPHostError, SDKHost
from app.research_web.mcp_runtime.transport import (
    RemoteTarget,
    StdioTarget,
    build_stdio_target,
    minimal_stdio_environment,
    validate_redirect,
    validate_remote_endpoint,
)

INSTALLATION_ID = "mcp-installation-0123456789abcdef0123456789abcdef"


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value

    def delete_password(self, service: str, account: str) -> None:
        self.values.pop((service, account), None)


def test_runtime_credentials_are_keyring_only_and_resource_bound(tmp_path):
    keyring = FakeKeyring()
    store = RuntimeCredentialStore(keyring)
    token = {
        "access_token": "super-secret",
        "token_type": "Bearer",
        "resource": "https://mcp.example.test/mcp",
    }

    store.write(INSTALLATION_ID, "oauth", token)

    assert (
        store.read(
            INSTALLATION_ID,
            "oauth",
            expected_resource="https://mcp.example.test/mcp",
        )
        == token
    )
    assert list(keyring.values) == [(KEYRING_SERVICE, f"{INSTALLATION_ID}:oauth")]
    assert "super-secret" not in json.dumps(
        {"credential_ref": store.reference(INSTALLATION_ID, "oauth")}
    )
    with pytest.raises(OAuthError, match="audience"):
        store.read(
            INSTALLATION_ID,
            "oauth",
            expected_resource="https://other.example.test/mcp",
        )


def test_runtime_credential_failure_log_uses_only_id_digest_and_error_type(monkeypatch):
    records = []

    class FailingKeyring(FakeKeyring):
        def set_password(self, service: str, account: str, value: str) -> None:
            raise RuntimeError("backend included a secret")

    class CapturingLog:
        def warning(self, event: str, **fields) -> None:
            records.append((event, fields))

    monkeypatch.setattr(credential_module, "log", CapturingLog())
    with pytest.raises(RuntimeCredentialError, match="unavailable"):
        RuntimeCredentialStore(FailingKeyring()).write(
            INSTALLATION_ID,
            "oauth",
            {"access_token": "do-not-log"},
        )

    assert records == [
        (
            "mcp_runtime_credential_write_failed",
            {
                "installation_id_digest": credential_module._id_digest(INSTALLATION_ID),
                "error_type": "RuntimeError",
            },
        )
    ]
    assert INSTALLATION_ID not in json.dumps(records)
    assert "do-not-log" not in json.dumps(records)


@pytest.mark.parametrize(
    "url",
    [
        "https://mcp.example.test/mcp",
        "http://127.0.0.1:8765/mcp",
        "http://[::1]:8765/mcp",
    ],
)
def test_remote_endpoint_accepts_https_or_explicit_loopback(url):
    assert validate_remote_endpoint(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.example.test/mcp",
        "http://localhost:8765/mcp",
        "https://user:secret@mcp.example.test/mcp",
        "https://mcp.example.test/mcp?token=secret",
        "file:///tmp/server",
    ],
)
def test_remote_endpoint_rejects_insecure_or_credential_bearing_urls(url):
    with pytest.raises(ValueError):
        validate_remote_endpoint(url)


def test_redirect_allows_same_origin_or_same_host_https_upgrade_only():
    assert (
        validate_redirect("https://mcp.example.test/mcp", "https://mcp.example.test/mcp/")
        == "https://mcp.example.test/mcp/"
    )
    assert (
        validate_redirect("http://127.0.0.1:8765/mcp", "https://127.0.0.1/mcp")
        == "https://127.0.0.1/mcp"
    )
    with pytest.raises(ValueError):
        validate_redirect("https://mcp.example.test/mcp", "https://evil.example.test/mcp")
    with pytest.raises(ValueError):
        validate_redirect("https://mcp.example.test/mcp", "http://mcp.example.test/mcp")


def test_stdio_uses_direct_argv_isolated_cwd_and_no_ambient_secret(tmp_path, monkeypatch):
    installation = tmp_path / "installation"
    installation.mkdir()
    executable = installation / "server"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ambient-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-secret")

    target = build_stdio_target(
        [str(executable), "--mode", "stdio"],
        installation,
        {"MCP_SERVER_TOKEN": "configured-secret"},
        platform_name="posix",
    )
    environment = dict(target.env)

    assert target == StdioTarget(
        argv=(str(executable), "--mode", "stdio"),
        cwd=installation.resolve(),
        env=environment,
        environment_names=("MCP_SERVER_TOKEN",),
    )
    assert environment["HOME"] == str(installation.resolve())
    assert environment["MCP_SERVER_TOKEN"] == "configured-secret"
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    with pytest.raises(TypeError, match="argv"):
        build_stdio_target(f"{executable} --mode stdio", installation, {})


def test_stdio_rejects_shell_ambient_environment_and_tmp_symlink(tmp_path):
    installation = tmp_path / "installation"
    installation.mkdir()
    executable = installation / "server"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    with pytest.raises(ValueError, match="shell"):
        build_stdio_target(["/bin/sh", "-c", "echo owned"], installation, {})
    with pytest.raises(ValueError, match="environment"):
        build_stdio_target([str(executable), "ok"], installation, os.environ)
    with pytest.raises(ValueError, match="environment"):
        build_stdio_target([str(executable)], installation, {"HOME": "/tmp"})

    outside = tmp_path / "outside"
    outside.mkdir()
    (installation / "tmp").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="temporary"):
        minimal_stdio_environment(installation)


def test_stdio_executable_must_be_contained_and_inline_runtime_is_forbidden(tmp_path):
    installation = tmp_path / "installation"
    installation.mkdir()
    outside = tmp_path / "outside-server"
    outside.write_text("#!/bin/sh\n", encoding="utf-8")
    outside.chmod(0o700)
    with pytest.raises(ValueError, match="escapes"):
        build_stdio_target([str(outside), "server.py"], installation, {})

    python = installation / "python3"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o700)
    with pytest.raises(ValueError, match="inline"):
        build_stdio_target([str(python), "-c", "print('owned')"], installation, {})


@pytest.mark.asyncio
async def test_oauth_discovery_requires_resource_and_issuer_binding():
    requested: list[str] = []

    async def fetch_json(url: str):
        requested.append(url)
        if "oauth-protected-resource" in url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://identity.example.test",
            "authorization_endpoint": "https://identity.example.test/authorize",
            "token_endpoint": "https://identity.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    metadata = await OAuthDiscovery(fetch_json).discover("https://mcp.example.test/mcp")

    assert metadata.resource == "https://mcp.example.test/mcp"
    assert metadata.issuer == "https://identity.example.test"
    assert requested == [
        "https://mcp.example.test/.well-known/oauth-protected-resource/mcp",
        "https://identity.example.test/.well-known/oauth-authorization-server",
    ]

    async def wrong_issuer(_url: str):
        if "oauth-protected-resource" in _url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://evil.example.test",
            "authorization_endpoint": "https://evil.example.test/authorize",
            "token_endpoint": "https://evil.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    with pytest.raises(OAuthError, match="issuer"):
        await OAuthDiscovery(wrong_issuer).discover("https://mcp.example.test/mcp")


@pytest.mark.asyncio
async def test_oauth_uses_pkce_state_resource_and_rejects_passthrough():
    keyring = FakeKeyring()
    store = RuntimeCredentialStore(keyring)

    async def fetch_json(url: str):
        if "oauth-protected-resource" in url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://identity.example.test",
            "authorization_endpoint": "https://identity.example.test/authorize",
            "token_endpoint": "https://identity.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    async def token_exchange(request: httpx.Request) -> httpx.Response:
        form = parse_qs((await request.aread()).decode())
        assert request.url == httpx.URL("https://identity.example.test/token")
        assert form["resource"] == ["https://mcp.example.test/mcp"]
        assert form["code_verifier"][0]
        assert "subject_token" not in form
        return httpx.Response(
            200,
            json={
                "access_token": "server-token",
                "token_type": "Bearer",
                "resource": "https://mcp.example.test/mcp",
            },
        )

    coordinator = OAuthCoordinator(
        OAuthDiscovery(fetch_json),
        store,
        redirect_uri="http://127.0.0.1:8088/api/research/mcp/oauth/callback",
        client_id="research-workbench",
        token_transport=httpx.MockTransport(token_exchange),
    )
    attempt = await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")
    query = parse_qs(urlsplit(attempt.authorization_url).query)

    assert query["code_challenge_method"] == ["S256"]
    state = query["state"][0]
    assert attempt.attempt_id == state
    assert query["resource"] == ["https://mcp.example.test/mcp"]
    assert "code_verifier" not in query
    assert not hasattr(attempt, "state")
    assert not hasattr(attempt, "code_verifier")

    with pytest.raises(OAuthError, match="state"):
        await coordinator.complete(state, "wrong", "code")
    result = await coordinator.complete(state, state, "code")
    assert result.resource == "https://mcp.example.test/mcp"
    assert result.credential_ref["account"] == f"{INSTALLATION_ID}:oauth"
    assert not hasattr(result, "access_token")
    assert (
        store.read(
            INSTALLATION_ID,
            "oauth",
            expected_resource="https://mcp.example.test/mcp",
        )["access_token"]
        == "server-token"
    )
    with pytest.raises(OAuthError, match="state"):
        await coordinator.complete(state, state, "code")


@pytest.mark.asyncio
async def test_oauth_token_exchange_rejects_redirect_and_oversized_response():
    async def fetch_json(url: str):
        if "oauth-protected-resource" in url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://identity.example.test",
            "authorization_endpoint": "https://identity.example.test/authorize",
            "token_endpoint": "https://identity.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    for response in (
        httpx.Response(302, headers={"location": "https://identity.example.test/other"}),
        httpx.Response(200, content=b"x" * 129),
    ):
        coordinator = OAuthCoordinator(
            OAuthDiscovery(fetch_json),
            RuntimeCredentialStore(FakeKeyring()),
            redirect_uri="http://127.0.0.1:8088/api/research/mcp/oauth/callback",
            client_id="research-workbench",
            token_transport=httpx.MockTransport(lambda _request, value=response: value),
            max_token_response_bytes=128,
        )
        attempt = await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")
        state = parse_qs(urlsplit(attempt.authorization_url).query)["state"][0]
        with pytest.raises(OAuthError, match="token"):
            await coordinator.complete(attempt.attempt_id, state, "code")


@pytest.mark.asyncio
async def test_oauth_opaque_token_requires_explicit_resource_assertion():
    async def fetch_json(url: str):
        if "oauth-protected-resource" in url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://identity.example.test",
            "authorization_endpoint": "https://identity.example.test/authorize",
            "token_endpoint": "https://identity.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    coordinator = OAuthCoordinator(
        OAuthDiscovery(fetch_json),
        RuntimeCredentialStore(FakeKeyring()),
        redirect_uri="http://127.0.0.1:8088/api/research/mcp/oauth/callback",
        client_id="research-workbench",
    )
    attempt = await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")
    state = parse_qs(urlsplit(attempt.authorization_url).query)["state"][0]

    async def exchange(_endpoint: str, _body: dict[str, str]):
        return {"access_token": "opaque", "token_type": "Bearer"}

    with pytest.raises(OAuthError, match="audience"):
        await coordinator.complete(state, state, "code", exchange)


@pytest.mark.asyncio
async def test_oauth_attempts_are_bounded_and_expired_attempts_are_pruned():
    now = [1000.0]

    async def fetch_json(url: str):
        if "oauth-protected-resource" in url:
            return {
                "resource": "https://mcp.example.test/mcp",
                "authorization_servers": ["https://identity.example.test"],
            }
        return {
            "issuer": "https://identity.example.test",
            "authorization_endpoint": "https://identity.example.test/authorize",
            "token_endpoint": "https://identity.example.test/token",
            "code_challenge_methods_supported": ["S256"],
        }

    coordinator = OAuthCoordinator(
        OAuthDiscovery(fetch_json),
        RuntimeCredentialStore(FakeKeyring()),
        redirect_uri="http://127.0.0.1:8088/api/research/mcp/oauth/callback",
        client_id="research-workbench",
        clock=lambda: now[0],
        max_attempts=1,
    )
    await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")
    with pytest.raises(OAuthError, match="capacity"):
        await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")
    now[0] += 601
    await coordinator.start(INSTALLATION_ID, "https://mcp.example.test/mcp")


class FakeResult:
    def __init__(self, **value) -> None:
        self.value = value

    def model_dump(self, *, mode: str):
        assert mode == "json"
        return self.value


class FakeClient:
    protocol_version = "negotiated-by-server"
    server_info = SimpleNamespace(name="fixture", version="1.2.3")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def list_tools(self):
        return FakeResult(
            tools=[
                {
                    "name": "search",
                    "description": "Search safely",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ],
            nextCursor=None,
        )

    async def list_resources(self):
        return FakeResult(resources=[{"uri": "fixture://resource", "name": "Facts"}])

    async def list_prompts(self):
        return FakeResult(prompts=[{"name": "brief"}])

    async def call_tool(self, name, arguments):
        assert name == "search"
        assert arguments == {"query": "rates"}
        return FakeResult(content=[{"type": "text", "text": "result"}], isError=False)

    async def read_resource(self, uri):
        return FakeResult(contents=[{"uri": uri, "text": "facts"}])

    async def get_prompt(self, name, arguments):
        return FakeResult(description=name, messages=[{"role": "user", "content": arguments}])


def safe_stdio_target(tmp_path: Path) -> StdioTarget:
    installation = tmp_path / "installation"
    installation.mkdir()
    executable = installation / "server"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o700)
    return build_stdio_target([str(executable)], installation, {}, platform_name="posix")


@pytest.mark.asyncio
async def test_sdk_host_negotiates_auto_and_exposes_only_supported_client_verbs(tmp_path):
    calls = []

    def client_factory(target, **kwargs):
        calls.append((target, kwargs))
        return FakeClient()

    host = SDKHost(client_factory=client_factory, target_factory=lambda target: target)
    target = safe_stdio_target(tmp_path)

    capabilities = await host.capabilities(target)
    tool = await host.call_tool(target, "search", {"query": "rates"})
    resource = await host.read_resource(target, "fixture://resource")
    prompt = await host.get_prompt(target, "brief", {"topic": "rates"})

    assert capabilities["protocol_version"] == "negotiated-by-server"
    assert capabilities["tools"][0]["name"] == "search"
    assert len(capabilities["tools"][0]["schema_sha256"]) == 64
    assert tool["content"][0]["text"] == "result"
    assert resource["contents"][0]["text"] == "facts"
    assert prompt["description"] == "brief"
    assert all(
        kwargs
        == {
            "mode": "auto",
            "sampling_callback": None,
            "elicitation_callback": None,
            "extensions": (),
            "cache": None,
            "read_timeout_seconds": 30.0,
        }
        for _, kwargs in calls
    )
    assert not hasattr(host, "sample")
    assert not hasattr(host, "elicit")
    assert not hasattr(host, "tasks")


@pytest.mark.asyncio
async def test_sdk_host_rejects_oversized_third_party_results_without_logging_body(tmp_path):
    class Oversized(FakeClient):
        async def call_tool(self, name, arguments):
            return FakeResult(content=[{"type": "text", "text": "x" * 1024}])

    host = SDKHost(
        client_factory=lambda target, **kwargs: Oversized(),
        target_factory=lambda target: target,
        max_result_bytes=128,
    )
    with pytest.raises(MCPHostError, match="too_large"):
        await host.call_tool(
            safe_stdio_target(tmp_path),
            "search",
            {"query": "secret query"},
        )


@pytest.mark.asyncio
async def test_sdk_host_rejects_oversized_tool_arguments_before_opening_client(tmp_path):
    opened = False

    def client_factory(_target, **_kwargs):
        nonlocal opened
        opened = True
        return FakeClient()

    host = SDKHost(
        client_factory=client_factory,
        target_factory=lambda target: target,
        max_request_bytes=128,
    )

    with pytest.raises(MCPHostError, match="too_large"):
        await host.call_tool(
            safe_stdio_target(tmp_path),
            "search",
            {"query": "secret query" * 128},
        )

    assert opened is False


@pytest.mark.asyncio
async def test_sdk_host_revalidates_remote_target_before_client_factory():
    opened = False

    def client_factory(_target, **_kwargs):
        nonlocal opened
        opened = True
        return FakeClient()

    host = SDKHost(
        client_factory=client_factory,
        target_factory=lambda target: target,
    )

    with pytest.raises(MCPHostError, match="target_invalid"):
        await host.capabilities(
            RemoteTarget(
                "http://mcp.example.test/mcp",
                INSTALLATION_ID,
                "http://mcp.example.test/mcp",
            )
        )

    assert opened is False


@pytest.mark.asyncio
async def test_sdk_host_revalidates_stdio_target_before_client_factory(tmp_path):
    opened = False

    def client_factory(_target, **_kwargs):
        nonlocal opened
        opened = True
        return FakeClient()

    host = SDKHost(client_factory=client_factory, target_factory=lambda target: target)
    hostile = StdioTarget(
        argv=("/bin/sh", "-c", "echo owned"),
        cwd=tmp_path,
        env=dict(os.environ),
        environment_names=tuple(os.environ),
    )

    with pytest.raises(MCPHostError, match="target_invalid"):
        await host.capabilities(hostile)
    assert opened is False


@pytest.mark.asyncio
async def test_sdk_host_loads_resource_bound_token_from_credential_store():
    keyring = FakeKeyring()
    credentials = RuntimeCredentialStore(keyring)
    credentials.write(
        INSTALLATION_ID,
        "oauth",
        {
            "access_token": "server-token",
            "token_type": "Bearer",
            "resource": "https://mcp.example.test/mcp",
        },
    )
    resolved = []
    host = SDKHost(
        credentials=credentials,
        client_factory=lambda target, **_kwargs: FakeClient(),
        remote_target_factory=lambda endpoint, token: resolved.append((endpoint, token))
        or "safe-transport",
    )
    target = RemoteTarget(
        "https://mcp.example.test/mcp",
        INSTALLATION_ID,
        "https://mcp.example.test/mcp",
    )

    await host.capabilities(target)

    assert resolved == [("https://mcp.example.test/mcp", "server-token")]
    with pytest.raises(TypeError):
        RemoteTarget(
            endpoint="https://mcp.example.test/mcp",
            bearer_token="raw-user-token",
        )


@pytest.mark.asyncio
async def test_sdk_host_allows_public_remote_without_synthesizing_authorization_header():
    resolved = []
    host = SDKHost(
        credentials=RuntimeCredentialStore(FakeKeyring()),
        client_factory=lambda target, **_kwargs: FakeClient(),
        remote_target_factory=lambda endpoint, token: resolved.append((endpoint, token))
        or "safe-transport",
    )

    await host.capabilities(
        RemoteTarget(
            "https://mcp.example.test/mcp",
            INSTALLATION_ID,
            "https://mcp.example.test/mcp",
        )
    )

    assert resolved == [("https://mcp.example.test/mcp", None)]


@pytest.mark.asyncio
async def test_remote_transport_disables_proxies_redirects_and_caps_before_buffer(monkeypatch):
    import httpx2
    from mcp.client import streamable_http

    captured = {}

    class FakeHTTPClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    @asynccontextmanager
    async def fake_streamable_http_client(url: str, *, http_client):
        assert url == "https://mcp.example.test/mcp"
        assert isinstance(http_client, FakeHTTPClient)
        yield "safe-transport"

    monkeypatch.setattr(httpx2, "AsyncClient", FakeHTTPClient)
    monkeypatch.setattr(
        streamable_http,
        "streamable_http_client",
        fake_streamable_http_client,
    )
    host = SDKHost(max_remote_response_bytes=128)

    async with host._remote_transport(
        "https://mcp.example.test/mcp",
        "server-token",
    ) as transport:
        assert transport == "safe-transport"
        assert captured["trust_env"] is False
        assert captured["follow_redirects"] is False
        hook = captured["event_hooks"]["response"][0]
        with pytest.raises(MCPHostError, match="too_large"):
            await hook(SimpleNamespace(headers={"content-length": "129"}))
