"""Shared AI reading and admin controls never enter a user's research runtime."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.research_web import tenant_policy
from app.research_web.multiuser.accounts import AccountStore
from app.research_web.multiuser.gateway import create_gateway


class Pool:
    def __init__(self):
        self.calls = []

    async def backend_for(self, user):
        self.calls.append(user)
        pytest.fail("AI request tried to start a user Web/DSH runtime")

    async def close(self):
        pass


class News:
    def __init__(self):
        self.calls = []
        self.on_status = None
        self.reader = SimpleNamespace(read=self.read, media=SimpleNamespace(read=self.image))

    async def read(self, endpoint):
        self.calls.append(("read", endpoint))
        return {"shared": True, "endpoint": endpoint}

    async def image(self, key):
        self.calls.append(("image", key))
        return Response(b"image", media_type="image/png")

    async def status(self):
        self.calls.append(("status",))
        if self.on_status:
            self.on_status()
        return {"state": "not_configured"}

    async def control(self, action, payload):
        self.calls.append(("control", action, payload))
        return {"ok": True}

    async def feed(self, kind, origin):
        self.calls.append(("feed", kind, origin))
        return b"<rss/>"


@pytest.fixture
def server(tmp_path):
    store = AccountStore(tmp_path / "server")
    users = {
        name: store.create_user(name, "safe password for " + name, role=role)
        for name, role in (("admin", "admin"), ("alice", "user"), ("bobby", "user"))
    }
    pool, news, factories = Pool(), News(), []
    upstream_calls = []

    def factory(project, home):
        factories.append((project, home))
        return news

    def upstream(request):
        upstream_calls.append(request)
        pytest.fail("shared AI data was proxied to a user backend")

    app = create_gateway(
        store,
        pool,
        origin="http://localhost",
        upstream=httpx.AsyncClient(transport=httpx.MockTransport(upstream)),
        ai_news_factory=factory,
    )
    with TestClient(app, base_url="http://localhost") as browser:
        yield browser, store, users, pool, news, factories, upstream_calls


def login(browser, name):
    response = browser.post(
        "/api/server/login",
        json={"username": name, "password": "safe password for " + name},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    browser.headers["X-RWB-Page-User"] = response.json()["user"]["id"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/research/aihot/pages/hot",
        "/api/research/ai-news/status",
        "/api/research/ai-news/feeds/daily.xml",
    ],
)
def test_anonymous_cannot_read_any_shared_news_or_start_runtime(server, path):
    browser, _, _, pool, news, _, _ = server
    assert browser.get(path).status_code == 401
    assert not pool.calls and not news.calls


def test_members_share_one_reading_service_outside_user_data_roots(server):
    browser, store, _, pool, news, factories, upstream = server
    assert len(factories) == 1
    assert factories[0][1] == store.root / "shared"
    assert not (store.root / "shared").exists()
    for name in ("alice", "bobby"):
        login(browser, name)
        assert browser.get("/api/research/aihot/pages/hot").json()["shared"] is True
        assert (
            browser.get("/api/research/aihot/topics/openai?page=2").json()["endpoint"]
            == "/site/topics/openai?page=2"
        )
        assert browser.get("/api/research/aihot/media/" + "a" * 64).status_code == 200
        assert browser.get("/api/research/ai-news/feeds/daily.xml").content == b"<rss/>"
    assert not pool.calls and not upstream
    assert sum(call[0] == "read" for call in news.calls) == 4


def test_members_cannot_see_status_or_apply_any_control(server):
    browser, _, _, pool, news, _, _ = server
    login(browser, "alice")
    assert browser.get("/api/research/ai-news/status").status_code == 403
    response = browser.post(
        "/api/research/ai-news/control",
        json={"action": "source.list", "input": {}},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 403
    assert not news.calls and not pool.calls


def test_admin_uses_shared_status_control_without_forwarding_browser_secrets(server):
    browser, _, _, pool, news, _, upstream = server
    login(browser, "admin")
    assert browser.get("/api/research/ai-news/status").json() == {"state": "not_configured"}
    response = browser.post(
        "/api/research/ai-news/control",
        json={"action": "source.list", "input": {}},
        headers={
            "Origin": "http://localhost",
            "Authorization": "browser-private",
            "X-RWB-AI-News-Token": "forged-private",
            "X-RWB-Tenant-Gateway-Key": "forged",
        },
    )
    assert response.json() == {"ok": True}
    assert news.calls == [("status",), ("control", "source.list", {})]
    assert "set-cookie" not in response.headers
    assert not upstream and not pool.calls


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/research/ai-news/unknown", "GET"),
        ("/api/research/aihot/unknown", "GET"),
        ("/api/research/ai-news/feeds/unknown.xml", "GET"),
        ("/api/research/aihot/pages/hot", "POST"),
        ("/api/research/ai-news/status", "POST"),
    ],
)
def test_unknown_ai_paths_and_methods_never_fall_through_to_dsh(server, path, method):
    browser, _, _, pool, news, _, _ = server
    login(browser, "admin")
    assert browser.request(method, path, headers={"Origin": "http://localhost"}).status_code in {
        404,
        405,
    }
    assert not pool.calls and not news.calls


def test_ai_routes_reuse_origin_and_page_account_binding(server):
    browser, _, users, pool, news, _, _ = server
    login(browser, "admin")
    body = {"action": "source.list", "input": {}}
    assert browser.post("/api/research/ai-news/control", json=body).status_code == 403
    assert (
        browser.post(
            "/api/research/ai-news/control", json=body, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    browser.headers["X-RWB-Page-User"] = users["alice"].id
    assert browser.get("/api/research/aihot/pages/hot").status_code == 401
    assert (
        browser.post(
            "/api/research/ai-news/control", json=body, headers={"Origin": "http://localhost"}
        ).status_code
        == 401
    )
    del browser.headers["X-RWB-Page-User"]
    assert (
        browser.post(
            "/api/research/ai-news/control", json=body, headers={"Origin": "http://localhost"}
        ).status_code
        == 401
    )
    assert (
        browser.post(
            "/api/research/ai-news/control?rwb_user=" + users["admin"].id,
            json=body,
            headers={"Origin": "http://localhost"},
        ).status_code
        == 200
    )
    assert len(news.calls) == 1 and not pool.calls


def test_chunked_control_body_is_limited_before_json_or_engine(server):
    browser, _, _, pool, news, _, _ = server
    login(browser, "admin")

    def body():
        yield b'{"action":"source.create","input":{"name":"'
        yield b"x" * 65537
        yield b'"}}'

    response = browser.post(
        "/api/research/ai-news/control",
        content=body(),
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert not news.calls and not pool.calls


def test_admin_revoked_during_control_body_never_reaches_engine(server):
    browser, store, users, pool, news, _, _ = server
    login(browser, "admin")

    def body():
        yield b'{"action":"source.list",'
        store.reset_password(users["admin"].id, "a replacement safe password")
        yield b'"input":{}}'

    response = browser.post(
        "/api/research/ai-news/control",
        content=body(),
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert not news.calls and not pool.calls


def test_revocation_during_shared_read_drops_response(server):
    browser, store, users, pool, news, _, _ = server
    login(browser, "admin")
    news.on_status = lambda: store.reset_password(users["admin"].id, "a replacement safe password")
    assert browser.get("/api/research/ai-news/status").status_code == 401
    assert news.calls == [("status",)] and not pool.calls


def test_default_unconfigured_gateway_has_no_shared_home_or_process_side_effects(
    tmp_path, monkeypatch
):
    store = AccountStore(tmp_path / "server")
    store.create_user("admin", "safe password for admin", role="admin")
    pool = Pool()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: pytest.fail("process started"))
    app = create_gateway(store, pool, origin="http://localhost")
    with TestClient(app, base_url="http://localhost") as browser:
        login(browser, "admin")
        assert browser.get("/api/research/ai-news/status").json()["state"] == "not_configured"
        assert browser.get("/api/research/aihot/pages/hot").status_code == 503
    assert not (store.root / "shared").exists()
    assert not pool.calls


def test_https_rss_uses_validated_public_origin_after_loopback_proxy(tmp_path):
    store = AccountStore(tmp_path / "server")
    store.create_user("alice", "safe password for alice")
    token, _ = store.login("alice", "safe password for alice")
    news = News()
    app = create_gateway(
        store,
        Pool(),
        origin="https://unit.tailabc.ts.net",
        ai_news_factory=lambda project, home: news,
    )
    # Simulate the already-terminated HTTPS request reaching the loopback gateway.
    with TestClient(app, base_url="http://unit.tailabc.ts.net") as browser:
        response = browser.get(
            "/api/research/ai-news/feeds/daily.xml", headers={"Cookie": "rwb_session=" + token}
        )
    assert response.status_code == 200
    assert news.calls == [("feed", "daily", "https://unit.tailabc.ts.net")]


@pytest.mark.parametrize(
    "path",
    [
        "/api/research/ai-news/status",
        "/api/research/ai-news/control",
        "/api/research/aihot/pages/hot",
        "/api/research/ai-news/feeds/daily.xml",
    ],
)
def test_tenant_backends_deny_global_news_even_with_valid_instance_key(monkeypatch, path):
    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    monkeypatch.setattr(tenant_policy, "_gateway_key", lambda: "k" * 64)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"x-rwb-tenant-gateway-key", b"k" * 64)],
            "query_string": b"",
        }
    )
    response = asyncio.run(tenant_policy.check_request(request))
    assert response.status_code == 403
