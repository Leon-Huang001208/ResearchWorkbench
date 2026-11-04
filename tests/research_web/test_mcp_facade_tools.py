"""Transport and bounded frozen-reader edge contracts; no providers or accounts in production."""

import hashlib
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import StreamingResponse
from starlette.routing import Route

from app.research_web.mcp_facade.backend import FrozenBackend, ReadError
from app.research_web.mcp_facade.config import MATERIAL_BYTES, RESPONSE_BYTES, enabled
from app.research_web.mcp_facade.http_policy import BoundedHTTP
from app.research_web.multiuser.accounts import AccountStore
from app.research_web.multiuser.gateway import create_gateway


def test_default_off_preserves_gateway_and_does_not_create_oauth(tmp_path, monkeypatch):
    monkeypatch.delenv("RWB_MCP_READONLY_ENABLED", raising=False)
    assert enabled() is False
    monkeypatch.setenv("RWB_MCP_READONLY_ENABLED", "true")
    assert enabled() is False
    accounts = AccountStore(tmp_path / "accounts")

    class Pool:
        async def close(self):
            pass

        async def backend_for(self, user):
            raise AssertionError("must not allocate")

    def forbidden(*args):
        raise AssertionError("must not initialize SDK facade")

    monkeypatch.setattr("app.research_web.mcp_facade.server.Facade", forbidden)
    with TestClient(
        create_gateway(accounts, Pool(), origin="http://127.0.0.1"), base_url="http://127.0.0.1"
    ) as client:
        assert client.get("/mcp").status_code == 401
        assert client.get("/.well-known/oauth-authorization-server").status_code == 401
    with accounts._connection() as db:
        assert not db.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'mcp_oauth_%'"
        ).fetchall()


def test_serialized_response_cap_withholds_all_partial_bytes():
    async def chunks():
        yield b"PRIVATE_PREFIX"
        yield b"x" * RESPONSE_BYTES

    async def endpoint(request):
        return StreamingResponse(chunks(), media_type="application/json")

    with TestClient(BoundedHTTP(Starlette(routes=[Route("/mcp", endpoint)]))) as client:
        response = client.get("/mcp")
    assert response.status_code == 413
    assert response.json() == {"error": "response_too_large"}
    assert b"PRIVATE_PREFIX" not in response.content


@pytest.mark.asyncio
async def test_backend_rejects_oversize_binary_and_invalid_identifiers_before_return():
    state = SimpleNamespace(calls=0, raw=b"\xff")

    class Pool:
        async def backend_for_readonly(self, user):
            return SimpleNamespace(url="http://synthetic.invalid", key="")

    async def respond(request):
        state.calls += 1
        if request.url.path.endswith("catalog"):
            return httpx.Response(
                200, json={"frozen_read_protocol": "v1"}, headers={"X-RWB-Frozen-Read": "v1"}
            )
        return httpx.Response(200, content=state.raw, headers={"X-RWB-Frozen-Read": "v1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), trust_env=False) as client:
        backend = FrozenBackend(Pool(), client)
        material = SimpleNamespace(
            kind="source",
            context_id="00000000-0000-0000-0000-000000000000",
            object_id="a" * 24,
            sha256=hashlib.sha256(state.raw).hexdigest(),
        )
        with pytest.raises(ReadError, match="source_not_utf8"):
            await backend.read("owned", material)
        state.raw = b"x" * (MATERIAL_BYTES + 1)
        material.sha256 = hashlib.sha256(state.raw).hexdigest()
        with pytest.raises(ReadError, match="frozen_material_too_large"):
            await backend.read("owned", material)
        before = state.calls
        material.context_id = "../../etc"
        with pytest.raises(ReadError, match="invalid_material_identifier"):
            await backend.read("owned", material)
        assert state.calls == before


@pytest.mark.asyncio
async def test_backend_with_legacy_pool_cannot_fallback_to_starting_lookup():
    async def forbidden(*args):
        raise AssertionError("legacy backend_for must never be called")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(AssertionError("no HTTP before safe lookup"))
        ),
        trust_env=False,
    ) as client:
        backend = FrozenBackend(SimpleNamespace(backend_for=forbidden), client)
        material = SimpleNamespace(
            kind="source",
            context_id="00000000-0000-0000-0000-000000000000",
            object_id="a" * 24,
            sha256="a" * 64,
        )
        with pytest.raises(ReadError, match="readonly_runtime_lookup_required"):
            await backend.read("owned", material)
