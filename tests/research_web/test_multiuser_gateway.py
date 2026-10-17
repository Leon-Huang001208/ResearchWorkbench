"""Real HTTP contracts for authenticated per-user request routing."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.research_web.multiuser.accounts import AccountStore
from app.research_web.multiuser.gateway import create_gateway


class Pool:
    def __init__(self):
        self.users = []
        self.stopped = []

    async def backend_for(self, user_id):
        from types import SimpleNamespace

        self.users.append(user_id)
        return SimpleNamespace(url="http://127.0.0.1:19999", key=user_id)

    async def stop(self, user_id):
        self.stopped.append(user_id)

    async def close(self):
        pass


@pytest.fixture
def server(tmp_path):
    store = AccountStore(tmp_path / "server")
    admin = store.create_user("admin", "a safe admin password", role="admin")
    alice = store.create_user("alice", "a safe alice password")
    bob = store.create_user("bobby", "a safe bobby password")
    pool = Pool()
    forwarded = []

    async def upstream(request):
        forwarded.append(request)
        if request.url.path.endswith("/preview"):
            return httpx.Response(
                200,
                text="<p>untrusted</p>",
                headers={"Content-Security-Policy": "sandbox; default-src 'none'"},
            )
        if request.url.path.startswith("/frameworks-embed/"):
            return httpx.Response(
                200,
                text="framework",
                headers={
                    "Content-Security-Policy": "script-src 'self' 'unsafe-inline'; frame-ancestors 'self'"
                },
            )
        if request.url.path.endswith("/events"):

            class Events(httpx.AsyncByteStream):
                async def __aiter__(self):
                    yield b"data: first\n\n"
                    store.set_enabled(alice.id, False)
                    yield b"data: forbidden\n\n"

            return httpx.Response(
                200, stream=Events(), headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(
            200,
            json={"owner": request.headers["x-rwb-tenant-gateway-key"]},
            headers={
                "set-cookie": "native-secret=never-forward",
                "content-type": "application/json",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_gateway(store, pool, origin="http://localhost", upstream=client)
    with TestClient(app, base_url="http://localhost") as browser:
        yield browser, store, pool, (admin, alice, bob), forwarded


def login(browser, username="alice", password="a safe alice password"):
    response = browser.post(
        "/api/server/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://localhost"},
    )
    if response.status_code == 200:
        browser.headers["X-RWB-Page-User"] = response.json()["user"]["id"]
    return response


def test_anonymous_cannot_read_user_data_or_start_runtime(server):
    browser, _, pool, _, _ = server
    assert browser.get("/api/research/sessions").status_code == 401
    assert browser.get("/", follow_redirects=False).headers["location"] == "/auth"
    assert pool.users == []


def test_two_users_route_from_cookie_not_owner_or_headers(server):
    browser, _, pool, (_, alice, bob), forwarded = server
    assert login(browser).status_code == 200
    response = browser.get(
        f"/api/research/sessions?owner={bob.id}",
        headers={"X-RWB-Tenant-Gateway-Key": bob.id, "Authorization": "Bearer fake"},
    )
    assert response.json()["owner"] == alice.id
    assert "set-cookie" not in response.headers
    assert "cookie" not in forwarded[-1].headers
    assert "authorization" not in forwarded[-1].headers
    assert pool.users == [alice.id]
    assert login(browser, "bobby", "a safe bobby password").status_code == 200
    assert browser.get("/api/research/sessions").json()["owner"] == bob.id
    assert "cookie" not in forwarded[-1].headers


def test_private_callbacks_and_proxy_targets_are_not_browser_routes(server):
    browser, _, pool, _, _ = server
    login(browser)
    for path in [
        "/api/research/internal/data/query",
        "/rpc",
        "/api/research/internal/../internal/data/query",
    ]:
        assert browser.post(path, json={}, headers={"Origin": "http://localhost"}).status_code in {
            403,
            404,
        }
    assert pool.users == []


def test_csrf_host_and_origin_checked_before_login_or_runtime(server):
    browser, _, pool, _, _ = server
    assert (
        browser.post(
            "/api/server/login", json={"username": "alice", "password": "a safe alice password"}
        ).status_code
        == 403
    )
    assert (
        browser.post(
            "/api/server/login", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert browser.get("/api/server/me", headers={"Host": "evil.test"}).status_code == 403
    assert pool.users == []


def test_cookie_and_errors_do_not_expose_password_or_session_token(server):
    browser, _, _, _, _ = server
    response = login(browser)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "password" not in response.json()["user"]
    bad = browser.post(
        "/api/server/login",
        json={"username": "alice", "password": "secret", "unknown": "never echo"},
        headers={"Origin": "http://localhost"},
    )
    assert bad.status_code == 422
    assert "secret" not in bad.text and "never echo" not in bad.text


def test_administration_and_revocation(server):
    browser, store, pool, (admin, alice, _), _ = server
    login(browser)
    assert browser.get("/api/server/users").status_code == 403
    old_token = browser.cookies.get("rwb_session")
    login(browser, "admin", "a safe admin password")
    assert browser.get("/api/server/users").status_code == 200
    created = browser.post(
        "/api/server/users",
        json={"username": "carol", "password": "a safe carol password"},
        headers={"Origin": "http://localhost"},
    )
    assert created.status_code == 201
    response = browser.patch(
        f"/api/server/users/{alice.id}",
        json={"enabled": False},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    assert store.authenticate(old_token) is None
    assert pool.stopped == [alice.id]
    assert store.get_user(admin.id).enabled


def test_password_reset_and_logout_revoke_tokens(server):
    browser, store, _, (_, alice, _), _ = server
    login(browser)
    token = browser.cookies.get("rwb_session")
    login(browser, "admin", "a safe admin password")
    response = browser.post(
        f"/api/server/users/{alice.id}/password",
        json={"password": "replacement alice password"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200 and store.authenticate(token) is None
    login(browser, "alice", "replacement alice password")
    token = browser.cookies.get("rwb_session")
    assert (
        browser.post("/api/server/logout", headers={"Origin": "http://localhost"}).status_code
        == 200
    )
    assert store.authenticate(token) is None


def test_login_does_not_boot_runtime_and_server_ui_is_separate(server):
    browser, _, pool, _, _ = server
    assert browser.get("/auth").status_code == 200
    login(browser)
    assert browser.get("/account").status_code == 200
    root = browser.get("/")
    assert "/server-static/session.mjs" in root.text
    assert pool.users == []
    assert browser.get("/static/index.html").status_code == 403


def test_invalid_server_origin_rejected_without_network(tmp_path):
    store = AccountStore(tmp_path / "state")
    for origin in [
        "http://example.com",
        "https://evil.test",
        "https://user:pw@unit.tailabc.ts.net",
        "https://unit.tailabc.ts.net/path",
    ]:
        with pytest.raises(ValueError):
            create_gateway(store, Pool(), origin=origin)


def test_revoked_while_starting_backend_cannot_submit_request(server):
    browser, store, pool, _, forwarded = server
    login(browser)
    token = browser.cookies.get("rwb_session")
    original = pool.backend_for

    async def delayed(user_id):
        result = await original(user_id)
        store.logout(token)
        return result

    pool.backend_for = delayed
    response = browser.post(
        "/api/research/sessions", json={"mode": "claw"}, headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 401
    assert forwarded == []


def test_old_browser_tab_cannot_send_under_new_account(server):
    browser, _, pool, (_, alice, _), _ = server
    login(browser, "bobby", "a safe bobby password")
    assert (
        browser.get("/api/research/sessions", headers={"X-RWB-Page-User": alice.id}).status_code
        == 401
    )
    assert browser.get(f"/api/research/events?rwb_user={alice.id}").status_code == 401
    assert pool.users == []


def test_upstream_preview_sandbox_and_framework_frame_policy_survive(server):
    browser, _, _, _, _ = server
    login(browser)
    preview = browser.get("/api/research/sessions/example/files/example/preview")
    assert preview.headers["Content-Security-Policy"] == "sandbox; default-src 'none'"
    framework = browser.get("/frameworks-embed/example/index.html")
    assert "frame-ancestors 'self'" in framework.headers["Content-Security-Policy"]


def test_stream_revocation_drops_late_chunks(server):
    browser, _, _, _, _ = server
    login(browser)
    response = browser.get("/api/research/sessions/example/events")
    assert "first" in response.text and "forbidden" not in response.text


def test_chunked_account_body_is_bounded_before_json_parsing(server):
    browser, _, pool, _, _ = server

    def chunks():
        yield b'{"username":"alice","password":"'
        yield b"x" * 20000
        yield b'"}'

    response = browser.post(
        "/api/server/login",
        content=chunks(),
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert pool.users == []


def test_admin_revoked_during_slow_body_cannot_create_an_account(server):
    browser, store, _, (admin, _, _), _ = server
    login(browser, "admin", "a safe admin password")

    def body():
        yield b'{"username":"intruder","password":"'
        store.reset_password(admin.id, "replacement admin password")
        yield b'a safe intruder password"}'

    response = browser.post(
        "/api/server/users",
        content=body(),
        headers={"Origin": "http://localhost", "Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert all(user.username != "intruder" for user in store.list_users())
