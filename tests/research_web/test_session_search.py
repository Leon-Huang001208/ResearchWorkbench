"""Read-only native full-text search: ownership, bounded schema and wire route."""

import copy
import json
from types import MethodType, SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.research_web.client import DSHClient, RuntimeFailure
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


def search_fixture(tmp_path, *, response=None, owned=True):
    store = Store(tmp_path)
    claw = store.create("claw", "本地 Claw 标题")
    fingpt = store.create("fingpt", "本地 FinGPT 标题")
    deleted = store.create("claw", "已删除")
    for row in (claw, fingpt, deleted):
        row["created"] = True
    deleted["deleted_at"] = 1
    calls = []
    value = (
        response
        if response is not None
        else {
            "items": [
                {"sessionId": claw["id"], "snippet": "正文匹配，不是标题"},
                {"sessionId": fingpt["id"], "snippet": "FinGPT 匹配"},
                {"sessionId": deleted["id"], "snippet": "禁止泄露已删除正文"},
                {"sessionId": "unknown-child", "snippet": "禁止泄露子会话正文"},
            ],
            "hasMore": True,
        }
    )

    async def rpc(method, payload):
        calls.append((method, payload))
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    owner = SimpleNamespace(
        store=store, client=SimpleNamespace(rpc=rpc), owned=owned, expected_cwd=None
    )
    owner.ensure_owned = MethodType(ResearchService.ensure_owned, owner)
    owner.search_sessions = MethodType(ResearchService.search_sessions, owner)
    return owner, calls, claw, fingpt


@pytest.mark.asyncio
async def test_search_filters_owned_active_modes_without_creating_or_sending(tmp_path):
    owner, calls, claw, _fingpt = search_fixture(tmp_path)
    before = copy.deepcopy(owner.store.data)
    result = await owner.search_sessions("  正文关键词  ", mode="claw")
    assert result == {
        "items": [
            {
                "id": claw["id"],
                "title": claw["title"],
                "mode": "claw",
                "snippet": "正文匹配，不是标题",
            }
        ],
        "has_more": True,
        "source": "native_dsh",
    }
    assert calls == [("session.search", {"query": "正文关键词"})]
    assert owner.store.data == before
    result = await owner.search_sessions("内容")
    assert [item["mode"] for item in result["items"]] == ["claw", "fingpt"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", ["", " \n\t ", "a\x00b", "a" * 501, "😀" * 251, "\ud800", None, 1]
)
async def test_search_invalid_query_never_reaches_native(tmp_path, query):
    owner, calls, *_ = search_fixture(tmp_path)
    with pytest.raises(StoreError) as failure:
        await owner.search_sessions(query)
    assert failure.value.code == "invalid_request" and failure.value.status == 422
    assert calls == []


@pytest.mark.asyncio
async def test_search_query_utf16_boundary_and_snippet_codepoints(tmp_path):
    owner, calls, claw, _ = search_fixture(tmp_path)

    async def rpc(method, payload):
        calls.append((method, payload))
        return {"items": [{"sessionId": claw["id"], "snippet": "😀" * 240}], "hasMore": False}

    owner.client.rpc = rpc
    assert len((await owner.search_sessions("😀" * 250))["items"][0]["snippet"]) == 240
    assert calls[0][1]["query"] == "😀" * 250


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        {},
        {"items": [], "hasMore": 1},
        {"items": "bad", "hasMore": False},
        {"items": [None], "hasMore": False},
        {"items": [{"sessionId": 5, "snippet": "bad"}], "hasMore": False},
        {"items": [{"sessionId": "bad/id", "snippet": "bad"}], "hasMore": False},
        {"items": [{"sessionId": "a", "snippet": []}], "hasMore": False},
        {"items": [{"sessionId": "a", "snippet": "x" * 241}], "hasMore": False},
        {"items": [{"sessionId": "a", "snippet": "\x00"}], "hasMore": False},
        {"items": [{"sessionId": "a", "snippet": "x"}] * 21, "hasMore": False},
    ],
)
async def test_search_malformed_native_schema_fails_closed(tmp_path, response):
    owner, calls, *_ = search_fixture(tmp_path)

    async def rpc(method, payload):
        calls.append((method, payload))
        return response

    owner.client.rpc = rpc
    with pytest.raises(RuntimeFailure) as failure:
        await owner.search_sessions("内容")
    assert failure.value.code == "session_search_invalid_response"
    assert calls == [("session.search", {"query": "内容"})]


@pytest.mark.asyncio
async def test_search_unowned_and_unavailable_are_explicit_failures(tmp_path):
    owner, calls, *_ = search_fixture(tmp_path, owned=False)
    with pytest.raises(RuntimeFailure) as failure:
        await owner.search_sessions("secret-query")
    assert failure.value.code == "read_only_runtime" and calls == []
    owner.owned = True

    async def unavailable(*_args):
        raise RuntimeFailure("upstream secret-query secret-snippet", "upstream")

    owner.client.rpc = unavailable
    with pytest.raises(RuntimeFailure) as failure:
        await owner.search_sessions("secret-query")
    assert failure.value.code == "session_search_unavailable"
    assert "secret" not in str(failure.value)


def test_search_static_route_precedes_session_id_and_rejects_invalid_mode(tmp_path):
    owner, calls, claw, _ = search_fixture(tmp_path)
    app = create_app()
    app.state.research = owner
    client = TestClient(app)
    try:
        result = client.post(
            "/api/research/sessions/search", json={"query": "正文", "mode": "claw"}
        )
        assert result.status_code == 200
        assert result.json()["items"][0]["id"] == claw["id"]
        assert calls == [("session.search", {"query": "正文"})]
        for body in [
            {},
            {"query": " "},
            {"query": "x", "mode": "other"},
            {"query": 1},
            {"query": True},
            {"query": "x", "cursor": "not-supported"},
        ]:
            assert client.post("/api/research/sessions/search", json=body).status_code == 422
        assert len(calls) == 1
    finally:
        client.close()


@pytest.mark.asyncio
async def test_search_client_maps_only_reviewed_private_rpc():
    calls = []

    def reply(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body["payload"]["args"]))
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": [], "hasMore": False}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        assert await client.rpc("session.search", {"query": "正文"}) == {
            "items": [],
            "hasMore": False,
        }
        with pytest.raises(RuntimeFailure) as failure:
            await client.rpc("session.arbitrarySearch", {"query": "正文"})
        assert failure.value.code == "forbidden"
    # Fixed session-controller search(request, signal) is distinct from list(_request, signal).
    assert calls == [("/api/session/search", {"request": {"query": "正文"}})]


@pytest.mark.asyncio
async def test_search_mode_filter_and_empty_native_page_do_not_forge_pagination(tmp_path):
    owner, calls, _claw, fingpt = search_fixture(tmp_path)
    result = await owner.search_sessions("内容", mode="fingpt")
    assert [item["id"] for item in result["items"]] == [fingpt["id"]]

    async def foreign_page(*_args):
        return {"items": [{"sessionId": "foreign", "snippet": "private"}], "hasMore": True}

    owner.client.rpc = foreign_page
    assert await owner.search_sessions("内容") == {
        "items": [],
        "has_more": True,
        "source": "native_dsh",
    }
    with pytest.raises(StoreError):
        await owner.search_sessions("内容", mode="unknown")
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_search_verifies_live_runtime_directory_before_search(tmp_path):
    owner, calls, *_ = search_fixture(tmp_path)
    owner.expected_cwd = tmp_path

    async def rpc(method, payload):
        calls.append((method, payload))
        return {"cwd": str(tmp_path / "foreign")}

    owner.client.rpc = rpc
    with pytest.raises(RuntimeFailure) as failure:
        await owner.search_sessions("must-not-leak")
    assert failure.value.code == "read_only_runtime"
    assert calls == [("host.describe", {})]


@pytest.mark.asyncio
async def test_search_logs_only_stable_events_and_counts(tmp_path, monkeypatch):
    from app.research_web import service as service_module

    owner, *_ = search_fixture(tmp_path)
    events = []
    logger = SimpleNamespace(
        info=lambda event, **fields: events.append((event, fields)),
        warning=lambda event, **fields: events.append((event, fields)),
    )
    monkeypatch.setattr(service_module, "log", logger)
    await owner.search_sessions("sensitive-query")
    assert events == [("research_session_search_completed", {"count": 2})]


def test_search_http_native_failure_is_sanitized(tmp_path):
    owner, calls, *_ = search_fixture(
        tmp_path, response=RuntimeFailure("sensitive upstream message", "upstream")
    )
    app = create_app()
    app.state.research = owner
    client = TestClient(app)
    try:
        response = client.post("/api/research/sessions/search", json={"query": "sensitive-query"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "session_search_unavailable"
        assert "sensitive" not in response.text
        assert calls == [("session.search", {"query": "sensitive-query"})]
    finally:
        client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("title", [None, 7, {}, ""])
async def test_search_bad_title_isolated_to_safe_fallback(tmp_path, title):
    owner, _calls, claw, _ = search_fixture(tmp_path)
    if title is None:
        claw.pop("title")
    else:
        claw["title"] = title
    result = await owner.search_sessions("正文", mode="claw")
    assert result["items"] == [
        {"id": claw["id"], "title": "未命名会话", "mode": "claw", "snippet": "正文匹配，不是标题"}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("creation_state", [False, None, 1, "true"])
async def test_search_does_not_expose_reserved_or_failed_native_creation(tmp_path, creation_state):
    owner, _calls, claw, _ = search_fixture(tmp_path)
    claw["created"] = creation_state
    claw["hot_creation_state"] = "reserved"
    claw["status"] = "failed"
    result = await owner.search_sessions("正文", mode="claw")
    assert result["items"] == []


def test_search_post_keeps_query_out_of_access_url_and_get_does_not_search(tmp_path, caplog):
    owner, calls, *_ = search_fixture(tmp_path)

    async def unknown_session(_sid):
        raise StoreError("会话不存在", "session_not_found", 404)

    owner.detail = unknown_session
    app = create_app()
    app.state.research = owner
    client = TestClient(app)
    try:
        with caplog.at_level("INFO", logger="httpx"):
            response = client.post(
                "/api/research/sessions/search", json={"query": "private-body-query"}
            )
        assert response.status_code == 200
        assert response.request.url.query == b""
        assert "private-body-query" not in str(response.request.url)
        assert "private-body-query" not in caplog.text
        assert client.get("/api/research/sessions/search").status_code == 404
        assert calls == [("session.search", {"query": "private-body-query"})]
    finally:
        client.close()
