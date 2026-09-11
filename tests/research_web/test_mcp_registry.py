"""Read-only MCP Registry backend and API security contract."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.research_web.main import create_app
from app.research_web.mcp_registry import (
    MCPRegistryService,
    RegistryCreate,
    RegistryError,
    RegistryUpdate,
)
from app.research_web.mcp_registry.catalog import OFFICIAL_REGISTRY_ID, CatalogError
from app.research_web.mcp_registry.credentials import KEYRING_SERVICE
from app.research_web.mcp_registry.models import safe_http_url, safe_text
from app.research_web.mcp_registry.publisher import PublisherMetadata
from app.research_web.mcp_registry.service import registry_feature_enabled
from app.research_web.mcp_registry.sync import (
    MAX_REGISTRY_RESPONSE_BYTES,
    RegistryHTTPClient,
    SyncError,
)
from app.research_web.service import ResearchService
from app.research_web.store import Store


def test_registry_feature_is_enabled_by_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("RESEARCH_MCP_REGISTRY_ENABLED", raising=False)
    assert registry_feature_enabled() is True
    monkeypatch.setenv("RESEARCH_MCP_REGISTRY_ENABLED", "0")
    assert registry_feature_enabled() is False


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        self.values[(service, account)] = password

    def delete_password(self, service: str, account: str) -> None:
        key = (service, account)
        if key not in self.values:
            raise RuntimeError("missing")
        del self.values[key]


class NativeFixture:
    async def rpc(self, method, payload):
        if method == "subagent.list":
            return {"entries": []}
        if method == "session.list":
            return {"items": []}
        if method == "host.describe":
            return {"version": "fixture", "provider": "fixture", "cwd": None}
        return {"accepted": True}

    async def history(self, sid):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


def registry_payload(**overrides):
    value = {
        "name": "Private Registry",
        "base_url": "https://registry.example.test",
        "auth": {"type": "none"},
    }
    value.update(overrides)
    return value


def remote_page(name="io.example/weather", version="1.2.3", *, cursor="opaque:/next?x=1"):
    return {
        "servers": [
            {
                "server": {
                    "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
                    "name": name,
                    "title": "<Weather & Research>",
                    "description": "Safe <b>facts</b> & signals",
                    "version": version,
                    "repository": {
                        "url": "https://github.com/example/weather",
                        "source": "github",
                    },
                    "packages": [
                        {
                            "registryType": "npm",
                            "identifier": "@example/weather",
                            "version": version,
                            "transport": {"type": "stdio"},
                        }
                    ],
                    "remotes": [{"type": "streamable-http", "url": "https://mcp.example.test"}],
                    "icons": [{"src": "https://evil.example/icon.svg"}],
                },
                "_meta": {
                    "io.modelcontextprotocol.registry/official": {
                        "status": "active",
                        "publishedAt": "2026-09-01T00:00:00Z",
                        "isLatest": True,
                    }
                },
            }
        ],
        "metadata": {"nextCursor": cursor, "count": 1},
    }


def test_registry_requests_are_strict_and_reject_credential_urls():
    with pytest.raises(ValidationError):
        RegistryCreate.model_validate({**registry_payload(), "unexpected": True})
    with pytest.raises(ValidationError):
        RegistryCreate.model_validate(
            registry_payload(base_url="https://token@example.test/registry")
        )
    with pytest.raises(ValidationError):
        RegistryUpdate.model_validate({"base_url": "file:///tmp/registry"})


@pytest.mark.parametrize("control", ["\x7f", "\x85", "\ud800"])
def test_plain_text_rejects_unicode_controls_and_surrogates(control):
    with pytest.raises(ValueError):
        safe_text(f"safe{control}text")


@pytest.mark.parametrize(
    "payload",
    [
        registry_payload(base_url="http://registry.example.test"),
        registry_payload(
            base_url="http://127.0.0.1:8080",
            auth={"type": "bearer", "token": "secret"},
        ),
        registry_payload(
            base_url="http://localhost:8080",
            auth={
                "type": "oauth2",
                "authorization_url": "https://id.example.test/authorize",
                "token_url": "https://id.example.test/token",
                "client_id": "workbench",
                "access_token": "secret",
            },
        ),
    ],
    ids=["remote-http-none", "loopback-http-bearer", "loopback-http-oauth"],
)
def test_registry_transport_requires_https_except_unauthenticated_loopback(payload):
    with pytest.raises(ValidationError):
        RegistryCreate.model_validate(payload)

    local = RegistryCreate.model_validate(
        registry_payload(base_url="http://127.0.0.1:8080", auth={"type": "none"})
    )
    assert local.base_url == "http://127.0.0.1:8080"


@pytest.mark.parametrize("field", ["authorization_url", "token_url"])
def test_oauth_endpoints_require_https(field):
    auth = {
        "type": "oauth2",
        "authorization_url": "https://id.example.test/authorize",
        "token_url": "https://id.example.test/token",
        "client_id": "workbench",
    }
    auth[field] = f"http://127.0.0.1/{field}"
    with pytest.raises(ValidationError):
        RegistryCreate.model_validate(registry_payload(auth=auth))


def test_registry_update_validates_effective_url_and_auth_before_mutation(tmp_path):
    keyring = FakeKeyring()
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=keyring)
    local = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(base_url="http://localhost:8080", auth={"type": "none"})
        )
    )
    with pytest.raises(RegistryError) as local_error:
        service.update_registry(
            local["id"],
            RegistryUpdate.model_validate({"auth": {"type": "bearer", "token": "must-not-store"}}),
        )
    assert local_error.value.code == "registry_transport_insecure"
    assert all("must-not-store" not in value for value in keyring.values.values())
    assert service.registry(local["id"])["auth"]["type"] == "none"

    remote = service.create_registry(
        RegistryCreate.model_validate(registry_payload(auth={"type": "bearer", "token": "stored"}))
    )
    with pytest.raises(RegistryError) as remote_error:
        service.update_registry(
            remote["id"], RegistryUpdate.model_validate({"base_url": "http://127.0.0.1:8080"})
        )
    assert remote_error.value.code == "registry_transport_insecure"
    assert service.registry(remote["id"])["base_url"] == "https://registry.example.test"


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_type", ["bearer", "oauth2"])
async def test_insecure_stored_registry_with_secret_makes_zero_network_requests(
    tmp_path, auth_type
):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=remote_page())

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    auth = {"type": auth_type}
    if auth_type == "oauth2":
        auth.update(
            {
                "authorization_url": "https://id.example.test/authorize",
                "token_url": "https://id.example.test/token",
                "client_id": "workbench",
                "scopes": [],
            }
        )
    row = service.catalog.create("Legacy insecure", "http://registry.example.test", auth)
    secret_key = "token" if auth_type == "bearer" else "access_token"
    service.credentials.write(row["id"], auth_type, {secret_key: "must-not-leak"})

    with pytest.raises(RegistryError) as error:
        await service.sync_registry(row["id"])
    assert error.value.code == "registry_transport_insecure"
    assert requests == []
    await service.close()


@pytest.mark.asyncio
async def test_insecure_stored_oauth_endpoint_makes_zero_network_requests(tmp_path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=remote_page())

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    row = service.catalog.create(
        "Legacy insecure OAuth",
        "https://registry.example.test",
        {
            "type": "oauth2",
            "authorization_url": "http://127.0.0.1/authorize",
            "token_url": "https://id.example.test/token",
            "client_id": "workbench",
            "scopes": [],
        },
    )
    service.credentials.write(row["id"], "oauth2", {"access_token": "must-not-leak"})

    with pytest.raises(RegistryError) as error:
        await service.sync_registry(row["id"])
    assert error.value.code == "registry_transport_insecure"
    assert requests == []
    await service.close()


@pytest.mark.asyncio
async def test_registry_http_client_never_follows_redirect_to_insecure_target():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                302,
                headers={"Location": "http://registry.example.test/v0.1/servers"},
            )
        return httpx.Response(200, json=remote_page())

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    registry_http = RegistryHTTPClient(client)
    with pytest.raises(SyncError) as error:
        await registry_http.page(
            "https://registry.example.test",
            cursor=None,
            search=None,
            limit=100,
            etag=None,
            authorization=None,
        )
    assert error.value.code == "registry_http_error"
    assert len(requests) == 1
    await client.aclose()


def test_catalog_seeds_immutable_official_and_keeps_stable_user_identity(tmp_path):
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    official = service.registry(OFFICIAL_REGISTRY_ID)
    assert official == {
        "id": "official",
        "name": "Official MCP Registry",
        "base_url": "https://registry.modelcontextprotocol.io",
        "official": True,
        "immutable": True,
        "auth": {"type": "none", "secret_configured": False},
        "created_at": official["created_at"],
        "updated_at": official["updated_at"],
    }
    with pytest.raises(RegistryError, match="official registry"):
        service.update_registry(OFFICIAL_REGISTRY_ID, RegistryUpdate(name="changed"))
    with pytest.raises(RegistryError, match="official registry"):
        service.delete_registry(OFFICIAL_REGISTRY_ID)

    created = service.create_registry(RegistryCreate.model_validate(registry_payload()))
    registry_id = created["id"]
    updated = service.update_registry(registry_id, RegistryUpdate(name="Renamed"))
    assert updated["id"] == registry_id
    reloaded = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    assert reloaded.registry(registry_id)["id"] == registry_id


def test_bearer_and_oauth_secrets_stay_in_keyring_and_are_redacted(tmp_path):
    keyring = FakeKeyring()
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=keyring)
    bearer = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(auth={"type": "bearer", "token": "browser-secret"})
        )
    )
    account = f"{bearer['id']}:bearer"
    assert keyring.values[(KEYRING_SERVICE, account)] == "browser-secret"
    assert bearer["auth"] == {"type": "bearer", "secret_configured": True}
    assert "browser-secret" not in (tmp_path / "mcp-registry" / "catalog.json").read_text()
    assert "browser-secret" not in json.dumps(service.list_registries())

    oauth = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(
                name="OAuth Registry",
                base_url="https://oauth.example.test",
                auth={
                    "type": "oauth2",
                    "authorization_url": "https://id.example.test/authorize",
                    "token_url": "https://id.example.test/token",
                    "client_id": "workbench",
                    "scopes": ["registry.read"],
                    "access_token": "oauth-access",
                    "client_secret": "oauth-client-secret",
                },
            )
        )
    )
    assert oauth["auth"] == {
        "type": "oauth2",
        "authorization_url": "https://id.example.test/authorize",
        "token_url": "https://id.example.test/token",
        "client_id": "workbench",
        "scopes": ["registry.read"],
        "secret_configured": True,
    }
    raw = (tmp_path / "mcp-registry" / "catalog.json").read_text()
    assert "oauth-access" not in raw and "oauth-client-secret" not in raw


@pytest.mark.asyncio
async def test_sync_preserves_registry_identity_opaque_cursor_and_etag(tmp_path):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(200, json=remote_page(), headers={"ETag": '"page-v1"'})
        return httpx.Response(304)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=client,
    )
    first = await service.sync_registry(OFFICIAL_REGISTRY_ID, limit=25)
    assert first["next_cursor"] == "opaque:/next?x=1"
    assert first["items"][0]["registry_id"] == OFFICIAL_REGISTRY_ID
    assert first["items"][0]["title"] == "<Weather & Research>"
    assert first["items"][0]["description"] == "Safe <b>facts</b> & signals"
    assert "icons" not in first["items"][0]
    assert seen[0].url.path == "/v0.1/servers"
    assert seen[0].url.params["limit"] == "25"

    second = await service.sync_registry(OFFICIAL_REGISTRY_ID, limit=25)
    assert seen[1].headers["If-None-Match"] == '"page-v1"'
    assert second["items"] == first["items"]
    assert second["not_modified"] is True
    assert second["stale"] is False
    await service.close()


@pytest.mark.asyncio
async def test_registry_normalization_round_trips_bounded_unicode_plain_text(tmp_path):
    payload = remote_page()
    server = payload["servers"][0]["server"]
    server["title"] = "研报 & 风险 <script>不是节点</script>"
    server["description"] = "保留 Unicode、& 与 <tag>，只在最终 HTML sink 转义。"
    server["repository"].update(
        {"source": "代码 & 审查", "id": "组/<仓库>", "subfolder": "资料 & 图表"}
    )
    payload["servers"][0]["_meta"]["io.modelcontextprotocol.registry/official"].update(
        {"status": "active & reviewed", "updatedAt": "2026-09-01T00:00:00Z & source"}
    )

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
    )
    result = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    item = result["items"][0]
    assert item["title"] == server["title"]
    assert item["description"] == server["description"]
    assert item["repository"] == {
        "url": "https://github.com/example/weather",
        "source": "代码 & 审查",
        "id": "组/<仓库>",
        "subfolder": "资料 & 图表",
    }
    assert item["status"] == "active & reviewed"
    assert item["updated_at"] == "2026-09-01T00:00:00Z & source"
    assert "&amp;" not in json.dumps(item, ensure_ascii=False)
    cached = service.list_servers(OFFICIAL_REGISTRY_ID)["items"][0]
    assert cached["title"] == server["title"]
    assert cached["description"] == server["description"]
    await service.close()

    reloaded = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    persisted = reloaded.list_servers(OFFICIAL_REGISTRY_ID)["items"][0]
    assert persisted["title"] == server["title"]
    assert persisted["description"] == server["description"]
    await reloaded.close()


@pytest.mark.asyncio
async def test_registry_package_projection_separates_type_support_from_fixed_reference(tmp_path):
    payload = remote_page()
    payload["servers"][0]["server"]["packages"] = [
        {
            "registryType": "npm",
            "identifier": "@example/fixed",
            "version": "1.2.3",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "npm",
            "identifier": "@example/dynamic",
            "version": "latest",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "mcpb",
            "identifier": "https://downloads.example.test/server.mcpb",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "unknown",
            "identifier": "example/server",
            "version": "1.2.3",
            "transport": {"type": "stdio"},
        },
    ]
    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
    )

    packages = (await service.sync_registry(OFFICIAL_REGISTRY_ID))["items"][0]["packages"]
    assert packages[0]["package_type_supported"] is True
    assert packages[0]["immutable_reference"] is True
    assert packages[1]["package_type_supported"] is True
    assert packages[1]["immutable_reference"] is False
    assert packages[2]["package_type_supported"] is True
    assert packages[2]["immutable_reference"] is False
    assert packages[3]["package_type_supported"] is False
    assert packages[3]["immutable_reference"] is False
    assert all("supported" not in package for package in packages)
    await service.close()


@pytest.mark.asyncio
async def test_registry_package_projection_keeps_bounded_execution_descriptors_without_values(
    tmp_path,
):
    payload = remote_page()
    payload["servers"][0]["server"]["packages"] = [
        {
            "registryType": "npm",
            "identifier": "@example/fixed",
            "version": "1.2.3",
            "runtimeHint": "npx",
            "runtimeArguments": [
                {"type": "named", "name": "--yes", "value": "true"},
            ],
            "packageArguments": [
                {"type": "positional", "value": "--stdio"},
            ],
            "environmentVariables": [
                {
                    "name": "EXAMPLE_API_KEY",
                    "description": "API credential",
                    "isRequired": True,
                    "isSecret": True,
                    "format": "string",
                    "value": "must-not-persist",
                }
            ],
            "transport": {"type": "stdio"},
        }
    ]
    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ),
    )

    package = (await service.sync_registry(OFFICIAL_REGISTRY_ID))["items"][0]["packages"][0]

    assert package["runtime_hint"] == "npx"
    assert package["runtime_arguments"] == [
        {"type": "named", "name": "--yes", "value": "true", "is_repeated": False}
    ]
    assert package["package_arguments"] == [
        {"type": "positional", "value": "--stdio", "is_repeated": False}
    ]
    assert package["environment_variables"] == [
        {
            "name": "EXAMPLE_API_KEY",
            "description": "API credential",
            "is_required": True,
            "is_secret": True,
            "format": "string",
        }
    ]
    assert "must-not-persist" not in json.dumps(package)
    await service.close()


@pytest.mark.asyncio
async def test_same_server_name_from_two_registries_never_merges_identity(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        version = "1.0.0" if request.url.host == "one.example.test" else "2.0.0"
        return httpx.Response(200, json=remote_page(version=version))

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    first = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(name="One", base_url="https://one.example.test")
        )
    )
    second = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(name="Two", base_url="https://two.example.test")
        )
    )
    one = await service.sync_registry(first["id"])
    two = await service.sync_registry(second["id"])
    assert one["items"][0]["identity"] == [first["id"], "io.example/weather", "1.0.0"]
    assert two["items"][0]["identity"] == [second["id"], "io.example/weather", "2.0.0"]
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["timeout", "malformed", "empty", "oversized", "count_mismatch", "malicious_cursor"],
)
async def test_failed_invalid_or_empty_sync_returns_stale_without_replacing_cache(
    tmp_path, failure
):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=remote_page())
        if failure == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if failure == "malformed":
            return httpx.Response(200, content=b"{not-json")
        if failure == "empty":
            return httpx.Response(200, json={"servers": [], "metadata": {"count": 0}})
        if failure == "count_mismatch":
            invalid = remote_page()
            invalid["metadata"]["count"] = 99
            return httpx.Response(200, json=invalid)
        if failure == "malicious_cursor":
            return httpx.Response(200, json=remote_page(cursor="next\nInjected: value"))
        return httpx.Response(200, content=b"x" * (MAX_REGISTRY_RESPONSE_BYTES + 1))

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    fresh = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    cache_path = tmp_path / "mcp-registry" / "cache" / "official.json"
    original = cache_path.read_bytes()

    stale = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    assert stale["stale"] is True
    assert stale["items"] == fresh["items"]
    assert stale["failure_code"].startswith("registry_")
    assert cache_path.read_bytes() == original
    await service.close()


@pytest.mark.asyncio
async def test_timeout_without_cache_is_a_stable_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RegistryError) as error:
        await service.sync_registry(OFFICIAL_REGISTRY_ID)
    assert error.value.code == "registry_timeout"
    assert error.value.status == 504
    await service.close()


@pytest.mark.asyncio
async def test_version_detail_uses_encoded_external_path_and_stale_detail(tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=remote_page()["servers"][0])
        raise httpx.ConnectError("offline", request=request)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    fresh = await service.version_detail(
        OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3", refresh=True
    )
    assert fresh["identity"] == [OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3"]
    stale = await service.version_detail(
        OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3", refresh=True
    )
    assert stale["stale"] is True
    assert stale["failure_code"] == "registry_network_error"
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("server_name", "version"),
    [("../escape", "1.0.0"), ("io.example/weather", "latest")],
)
async def test_version_detail_rejects_noncanonical_identity(tmp_path, server_name, version):
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    with pytest.raises(RegistryError) as error:
        await service.version_detail(OFFICIAL_REGISTRY_ID, server_name, version)
    assert error.value.code == "registry_identity_invalid"
    await service.close()


def valid_server_json():
    return {
        "name": "io.example/weather",
        "title": "Weather",
        "description": "Weather research server",
        "version": "1.2.3",
        "repository": {"url": "https://github.com/example/weather", "source": "github"},
        "packages": [
            {
                "registryType": "npm",
                "identifier": "@example/weather",
                "version": "1.2.3",
                "transport": {"type": "stdio"},
            }
        ],
    }


def test_publisher_preview_is_canonical_strict_and_never_executes_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("publisher subprocess must never execute")

    monkeypatch.setattr("subprocess.run", forbidden)
    metadata = PublisherMetadata()
    result = metadata.preview(valid_server_json())
    assert result["valid"] is True
    assert result["server_json"]["$schema"].startswith("https://static.modelcontextprotocol.io/")
    assert result["sha256"] == metadata.digest(result["server_json"])
    assert result["argv"] == {
        "validate": ["mcp-publisher", "validate", "server.json"],
        "publish": ["mcp-publisher", "publish", "server.json"],
    }
    assert metadata.validate({**valid_server_json(), "name": "../escape"})["valid"] is False
    assert metadata.validate({**valid_server_json(), "extra": "forbidden"})["valid"] is False


def test_publisher_preview_round_trips_through_validation_with_same_digest():
    metadata = PublisherMetadata()
    preview = metadata.preview(valid_server_json())
    validated = metadata.validate(preview["server_json"])
    assert validated["valid"] is True
    assert validated["server_json"] == preview["server_json"]
    assert validated["sha256"] == preview["sha256"]


def test_disabled_registry_does_not_initialize_damaged_catalog(tmp_path, monkeypatch):
    root = tmp_path / "disabled-damaged"
    damaged = root / "mcp-registry"
    damaged.mkdir(parents=True)
    (damaged / "catalog.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("RESEARCH_MCP_REGISTRY_ENABLED", "0")

    service = ResearchService(NativeFixture(), Store(root))
    with TestClient(create_app(service)) as client:
        assert client.get("/").status_code == 200
        disabled = client.get("/api/research/mcp/registries")
        assert disabled.status_code == 404
        assert disabled.json()["error"]["code"] == "mcp_registry_disabled"


@pytest.mark.asyncio
async def test_failed_auth_switch_keeps_old_catalog_secret_and_authorization(tmp_path):
    class FailingOAuthKeyring(FakeKeyring):
        def set_password(self, service: str, account: str, password: str) -> None:
            if account.endswith(":oauth2"):
                raise RuntimeError("oauth write failed")
            super().set_password(service, account, password)

    seen_authorization = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_authorization
        seen_authorization = request.headers.get("Authorization")
        return httpx.Response(200, json=remote_page())

    keyring = FailingOAuthKeyring()
    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=keyring,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    created = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(auth={"type": "bearer", "token": "still-valid"})
        )
    )
    with pytest.raises(RegistryError) as error:
        service.update_registry(
            created["id"],
            RegistryUpdate.model_validate(
                {
                    "auth": {
                        "type": "oauth2",
                        "authorization_url": "https://id.example.test/authorize",
                        "token_url": "https://id.example.test/token",
                        "client_id": "workbench",
                        "access_token": "new-token",
                    }
                }
            ),
        )
    assert error.value.code == "credential_store_unavailable"
    assert service.registry(created["id"])["auth"] == {
        "type": "bearer",
        "secret_configured": True,
    }
    await service.sync_registry(created["id"])
    assert seen_authorization == "Bearer still-valid"
    await service.close()


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_catalog_io_errors_are_stable_and_keep_memory_disk_consistent(
    tmp_path, monkeypatch, operation
):
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    existing = service.create_registry(RegistryCreate.model_validate(registry_payload()))
    before = service.list_registries()

    with monkeypatch.context() as patch:
        patch.setattr(tempfile, "mkstemp", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
        with pytest.raises(RegistryError) as error:
            if operation == "create":
                service.create_registry(
                    RegistryCreate.model_validate(
                        registry_payload(
                            name="Never persisted", base_url="https://new.example.test"
                        )
                    )
                )
            elif operation == "update":
                service.update_registry(existing["id"], RegistryUpdate(name="Never persisted"))
            else:
                service.delete_registry(existing["id"])
    assert error.value.code == "registry_storage_unavailable"
    assert service.list_registries() == before
    reloaded = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    assert reloaded.list_registries() == before


def test_catalog_failure_during_auth_switch_restores_old_keyring_record(tmp_path, monkeypatch):
    keyring = FakeKeyring()
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=keyring)
    created = service.create_registry(
        RegistryCreate.model_validate(
            registry_payload(auth={"type": "bearer", "token": "old-token"})
        )
    )

    monkeypatch.setattr(
        service.catalog,
        "update",
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_storage_unavailable")),
    )
    with pytest.raises(RegistryError) as error:
        service.update_registry(
            created["id"],
            RegistryUpdate.model_validate(
                {
                    "auth": {
                        "type": "oauth2",
                        "authorization_url": "https://id.example.test/authorize",
                        "token_url": "https://id.example.test/token",
                        "client_id": "workbench",
                        "access_token": "new-token",
                    }
                }
            ),
        )
    assert error.value.code == "registry_storage_unavailable"
    assert keyring.values[(KEYRING_SERVICE, f"{created['id']}:bearer")] == "old-token"
    assert (KEYRING_SERVICE, f"{created['id']}:oauth2") not in keyring.values


def test_post_replace_directory_fsync_failure_keeps_committed_catalog_consistent(
    tmp_path, monkeypatch
):
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    real_fsync = os.fsync
    calls = 0

    def fail_directory_fsync(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory fsync unavailable")
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory_fsync)
    created = service.create_registry(RegistryCreate.model_validate(registry_payload()))
    assert service.registry(created["id"])["id"] == created["id"]
    reloaded = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    assert reloaded.registry(created["id"])["id"] == created["id"]


@pytest.mark.asyncio
async def test_base_url_change_does_not_reuse_old_cache_etag_or_stale_data(tmp_path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "old.example.test":
            return httpx.Response(
                200,
                json=remote_page(name="io.example/old"),
                headers={"ETag": '"old-etag"'},
            )
        raise httpx.ConnectError("new source offline", request=request)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    created = service.create_registry(
        RegistryCreate.model_validate(registry_payload(base_url="https://old.example.test"))
    )
    await service.sync_registry(created["id"])
    service.update_registry(created["id"], RegistryUpdate(base_url="https://new.example.test"))
    assert service.list_servers(created["id"])["items"] == []
    with pytest.raises(RegistryError) as error:
        await service.sync_registry(created["id"])
    assert error.value.code == "registry_network_error"
    assert "If-None-Match" not in requests[-1].headers
    await service.close()


@pytest.mark.asyncio
async def test_inflight_sync_cannot_commit_after_registry_source_changes(tmp_path):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        return httpx.Response(200, json=remote_page(name="io.example/old"))

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    created = service.create_registry(
        RegistryCreate.model_validate(registry_payload(base_url="https://old.example.test"))
    )
    task = asyncio.create_task(service.sync_registry(created["id"]))
    await entered.wait()
    service.update_registry(created["id"], RegistryUpdate(base_url="https://new.example.test"))
    release.set()
    with pytest.raises(RegistryError) as error:
        await task
    assert error.value.code == "registry_source_changed"
    assert service.list_servers(created["id"])["items"] == []
    await service.close()


def test_publisher_requires_fixed_npm_version_but_accepts_digest_pinned_file():
    metadata = PublisherMetadata()
    missing = valid_server_json()
    del missing["packages"][0]["version"]
    assert metadata.validate(missing)["valid"] is False

    dynamic = valid_server_json()
    dynamic["packages"][0]["version"] = "latest"
    assert metadata.validate(dynamic)["valid"] is False

    digest_pinned = valid_server_json()
    digest_pinned["packages"] = [
        {
            "registryType": "mcpb",
            "identifier": "https://downloads.example.test/weather.mcpb",
            "fileSha256": "a" * 64,
            "transport": {"type": "stdio"},
        }
    ]
    assert metadata.validate(digest_pinned)["valid"] is True


@pytest.mark.parametrize(
    "dynamic_version", ["beta", "next", "stable", "1", "1.2", "1.0.0 || 2.0.0"]
)
def test_publisher_rejects_every_noncanonical_npm_version(dynamic_version):
    value = valid_server_json()
    value["packages"][0]["version"] = dynamic_version
    assert PublisherMetadata().validate(value)["valid"] is False


@pytest.mark.parametrize(
    "package",
    [
        {"registryType": "pypi", "identifier": "weather", "transport": {"type": "stdio"}},
        {
            "registryType": "oci",
            "identifier": "ghcr.io/example/weather:latest",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "mcpb",
            "identifier": "https://downloads.example.test/weather.mcpb",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "nuget",
            "identifier": "Example.Weather",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "unknown",
            "identifier": "example/weather",
            "version": "1.2.3",
            "transport": {"type": "stdio"},
        },
    ],
)
def test_publisher_rejects_package_references_that_are_not_provably_fixed(package):
    value = valid_server_json()
    value["packages"] = [package]
    assert PublisherMetadata().validate(value)["valid"] is False


@pytest.mark.parametrize(
    ("registry_type", "identifier"),
    [
        ("oci", "ghcr.io/example/weather:latest"),
        ("oci", "ghcr.io/example/weather"),
        ("mcpb", "https://downloads.example.test/latest/weather.mcpb"),
    ],
    ids=["oci-latest", "oci-untagged", "mcpb-without-file-digest"],
)
def test_publisher_fixed_version_cannot_pin_mutable_download_reference(registry_type, identifier):
    value = valid_server_json()
    value["packages"] = [
        {
            "registryType": registry_type,
            "identifier": identifier,
            "version": "1.2.3",
            "transport": {"type": "stdio"},
        }
    ]
    result = PublisherMetadata().validate(value)
    assert result["valid"] is False
    assert result["executed"] is False
    assert result["issues"][0]["path"] == "packages.0"


@pytest.mark.parametrize("registry_type", ["pypi", "oci", "nuget", "mcpb"])
def test_publisher_accepts_supported_non_npm_package_pinned_by_digest(registry_type):
    value = valid_server_json()
    value["packages"] = [
        {
            "registryType": registry_type,
            "identifier": "example/weather",
            "fileSha256": "b" * 64,
            "transport": {"type": "stdio"},
        }
    ]
    assert PublisherMetadata().validate(value)["valid"] is True


@pytest.mark.parametrize(
    "package",
    [
        {
            "registryType": "npm",
            "identifier": "@example/weather",
            "version": "1.2.3-beta.1+build.5",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "pypi",
            "identifier": "weather",
            "version": "1.2.3rc1",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "oci",
            "identifier": f"ghcr.io/example/weather@sha256:{'a' * 64}",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "nuget",
            "identifier": "Example.Weather",
            "version": "1.2.3",
            "transport": {"type": "stdio"},
        },
        {
            "registryType": "mcpb",
            "identifier": "https://downloads.example.test/weather.mcpb",
            "fileSha256": "a" * 64,
            "transport": {"type": "stdio"},
        },
    ],
)
def test_publisher_accepts_supported_provably_fixed_package_references(package):
    value = valid_server_json()
    value["packages"] = [package]
    assert PublisherMetadata().validate(value)["valid"] is True


@pytest.mark.parametrize("initial_token", [None, "old-access-token"])
def test_same_oauth_catalog_failure_restores_exact_secret_snapshot(
    tmp_path, monkeypatch, initial_token
):
    keyring = FakeKeyring()
    auth = {
        "type": "oauth2",
        "authorization_url": "https://id.example.test/authorize",
        "token_url": "https://id.example.test/token",
        "client_id": "old-client",
    }
    if initial_token is not None:
        auth["access_token"] = initial_token
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=keyring)
    created = service.create_registry(RegistryCreate.model_validate(registry_payload(auth=auth)))
    account = (KEYRING_SERVICE, f"{created['id']}:oauth2")
    before = keyring.values.get(account)
    monkeypatch.setattr(
        service.catalog,
        "update",
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_storage_unavailable")),
    )

    with pytest.raises(RegistryError) as error:
        service.update_registry(
            created["id"],
            RegistryUpdate.model_validate(
                {
                    "auth": {
                        **auth,
                        "client_id": "new-client",
                        "access_token": "new-access-token",
                    }
                }
            ),
        )
    assert error.value.code == "registry_storage_unavailable"
    assert keyring.values.get(account) == before
    assert service.registry(created["id"])["auth"]["client_id"] == "old-client"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["page", "detail"])
async def test_cache_read_failure_returns_stable_registry_error(tmp_path, monkeypatch, kind):
    service = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    target = "cached_page" if kind == "page" else "cached_detail"
    monkeypatch.setattr(
        service.catalog,
        target,
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_cache_unavailable")),
    )
    with pytest.raises(RegistryError) as error:
        if kind == "page":
            await service.sync_registry(OFFICIAL_REGISTRY_ID)
        else:
            await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
    assert error.value.code == "registry_cache_unavailable"
    assert error.value.status == 503
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["page", "detail"])
async def test_deep_json_returns_stale_invalid_response_without_replacing_cache(tmp_path, kind):
    calls = 0
    deep_json = b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            payload = remote_page() if kind == "page" else remote_page()["servers"][0]
            return httpx.Response(200, json=payload)
        return httpx.Response(200, content=deep_json)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    if kind == "page":
        fresh = await service.sync_registry(OFFICIAL_REGISTRY_ID)
        cache_path = tmp_path / "mcp-registry" / "cache" / "official.json"
        before = cache_path.read_bytes()
        stale = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    else:
        fresh = await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
        cache_path = tmp_path / "mcp-registry" / "cache" / "official.json"
        before = cache_path.read_bytes()
        stale = await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
    assert (
        stale["identity"] == fresh["identity"]
        if kind == "detail"
        else stale["items"] == fresh["items"]
    )
    assert stale["stale"] is True
    assert stale["failure_code"] == "registry_invalid_response"
    assert cache_path.read_bytes() == before
    await service.close()


@pytest.mark.asyncio
async def test_deep_json_without_cache_is_stable_invalid_response(tmp_path):
    deep_json = b'{"x":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}"
    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=deep_json))
        ),
    )
    with pytest.raises(RegistryError) as error:
        await service.sync_registry(OFFICIAL_REGISTRY_ID)
    assert error.value.code == "registry_invalid_response"
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["page", "detail"])
async def test_status_write_failure_returns_stale_cache_and_keeps_memory_status(
    tmp_path, monkeypatch, kind
):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            payload = remote_page() if kind == "page" else remote_page()["servers"][0]
            return httpx.Response(200, json=payload)
        raise httpx.ConnectError("offline", request=request)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    if kind == "page":
        await service.sync_registry(OFFICIAL_REGISTRY_ID)
    else:
        await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
    monkeypatch.setattr(
        service.catalog,
        "set_sync_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_storage_unavailable")),
    )
    if kind == "page":
        stale = await service.sync_registry(OFFICIAL_REGISTRY_ID)
        later = service.list_servers(OFFICIAL_REGISTRY_ID)
    else:
        stale = await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
        later = await service.version_detail(
            OFFICIAL_REGISTRY_ID,
            "io.example/weather",
            "1.2.3",
            refresh=False,
        )
    assert stale["stale"] is True
    assert stale["failure_code"] == "registry_network_error"
    assert later["stale"] is True
    assert later["failure_code"] == "registry_network_error"
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["page", "detail"])
async def test_status_write_failure_does_not_block_fresh_cache(tmp_path, monkeypatch, kind):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = remote_page() if kind == "page" else remote_page()["servers"][0]
        return httpx.Response(200, json=payload)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        service.catalog,
        "set_sync_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_storage_unavailable")),
    )
    if kind == "page":
        fresh = await service.sync_registry(OFFICIAL_REGISTRY_ID)
        later = service.list_servers(OFFICIAL_REGISTRY_ID)
    else:
        fresh = await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
        later = await service.version_detail(
            OFFICIAL_REGISTRY_ID,
            "io.example/weather",
            "1.2.3",
            refresh=False,
        )
    assert fresh["stale"] is False
    assert fresh["failure_code"] is None
    assert later["stale"] is False
    assert later["failure_code"] is None
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["page", "detail"])
async def test_status_read_failure_projects_conservative_stale_state(tmp_path, monkeypatch, kind):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = remote_page() if kind == "page" else remote_page()["servers"][0]
        return httpx.Response(200, json=payload)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    if kind == "page":
        await service.sync_registry(OFFICIAL_REGISTRY_ID)
    else:
        await service.version_detail(OFFICIAL_REGISTRY_ID, "io.example/weather", "1.2.3")
    monkeypatch.setattr(
        service.catalog,
        "sync_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(CatalogError("registry_status_unavailable")),
    )
    if kind == "page":
        result = service.list_servers(OFFICIAL_REGISTRY_ID)
    else:
        result = await service.version_detail(
            OFFICIAL_REGISTRY_ID,
            "io.example/weather",
            "1.2.3",
            refresh=False,
        )
    assert result["stale"] is True
    assert result["failure_code"] == "registry_status_unavailable"
    await service.close()


@pytest.mark.asyncio
async def test_total_sync_deadline_returns_stale_registry_timeout(tmp_path):
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(0.02)
                yield b" "

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=remote_page())
        return httpx.Response(200, stream=SlowStream())

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await service.sync_registry(OFFICIAL_REGISTRY_ID)
    service.http.total_timeout = 0.05
    stale = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    assert stale["stale"] is True
    assert stale["failure_code"] == "registry_timeout"
    await service.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://[::1]", "https://[::1]"),
        ("https://[2001:db8::1]:8443/registry/", "https://[2001:db8::1]:8443/registry"),
    ],
)
def test_safe_http_url_preserves_ipv6_brackets(value, expected):
    assert safe_http_url(value) == expected


@pytest.mark.asyncio
async def test_stale_failure_status_persists_for_later_server_list(tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=remote_page())
        raise httpx.ConnectError("offline", request=request)

    service = MCPRegistryService(
        tmp_path,
        enabled=True,
        keyring_backend=FakeKeyring(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await service.sync_registry(OFFICIAL_REGISTRY_ID)
    stale = await service.sync_registry(OFFICIAL_REGISTRY_ID)
    listed = service.list_servers(OFFICIAL_REGISTRY_ID)
    assert listed["items"] == stale["items"]
    assert listed["stale"] is True
    assert listed["failure_code"] == "registry_network_error"
    await service.close()

    reloaded = MCPRegistryService(tmp_path, enabled=True, keyring_backend=FakeKeyring())
    persisted = reloaded.list_servers(OFFICIAL_REGISTRY_ID)
    assert persisted["items"] == stale["items"]
    assert persisted["stale"] is True
    assert persisted["failure_code"] == "registry_network_error"
    await reloaded.close()


def test_registry_api_flag_crud_server_list_detail_and_publisher(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_MCP_REGISTRY_ENABLED", "0")
    disabled_service = ResearchService(NativeFixture(), Store(tmp_path / "disabled"))
    with TestClient(create_app(disabled_service)) as client:
        response = client.get("/api/research/mcp/registries")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "mcp_registry_disabled"

    monkeypatch.setenv("RESEARCH_MCP_REGISTRY_ENABLED", "1")
    service = ResearchService(NativeFixture(), Store(tmp_path / "enabled"))
    service.mcp_registry.credentials.keyring = FakeKeyring()
    with TestClient(create_app(service)) as client:
        registries = client.get("/api/research/mcp/registries")
        assert registries.status_code == 200
        assert registries.json()["items"][0]["id"] == OFFICIAL_REGISTRY_ID
        created = client.post(
            "/api/research/mcp/registries", json=registry_payload(name="API Registry")
        )
        assert created.status_code == 201
        registry_id = created.json()["id"]
        assert client.get(f"/api/research/mcp/registries/{registry_id}").status_code == 200
        assert (
            client.patch(
                f"/api/research/mcp/registries/{registry_id}", json={"name": "API Renamed"}
            ).json()["id"]
            == registry_id
        )
        servers = client.get(
            "/api/research/mcp/servers",
            params={"registry_id": OFFICIAL_REGISTRY_ID, "cursor": "opaque", "limit": 20},
        )
        assert servers.status_code == 200
        assert servers.json()["registry_id"] == OFFICIAL_REGISTRY_ID
        assert servers.json()["items"] == []
        preview = client.post(
            "/api/research/mcp/publisher/preview", json={"server_json": valid_server_json()}
        )
        assert preview.status_code == 200
        assert preview.json()["valid"] is True
        validated = client.post("/api/research/mcp/publisher/validate", json=valid_server_json())
        assert validated.status_code == 200
        assert validated.json()["valid"] is True
        removed = client.delete(f"/api/research/mcp/registries/{registry_id}")
        assert removed.json() == {"id": registry_id, "deleted": True}
