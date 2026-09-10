"""Read-only MCP Registry backend and API security contract."""

from __future__ import annotations

import asyncio
import json

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
from app.research_web.mcp_registry.catalog import OFFICIAL_REGISTRY_ID
from app.research_web.mcp_registry.credentials import KEYRING_SERVICE
from app.research_web.mcp_registry.publisher import PublisherMetadata
from app.research_web.mcp_registry.sync import MAX_REGISTRY_RESPONSE_BYTES
from app.research_web.service import ResearchService
from app.research_web.store import Store


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
    assert first["items"][0]["title"] == "&lt;Weather &amp; Research&gt;"
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
