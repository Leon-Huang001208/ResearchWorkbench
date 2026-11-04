"""OAuth over a real isolated loopback socket with actual account sessions."""

import base64
import hashlib
import socket
import threading
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette

from app.research_web.mcp_facade.authorization_store import AuthorizationStore
from app.research_web.multiuser.accounts import AccountStore

CLIENT = "rwb-codex-native"
CALLBACK = "http://127.0.0.1:43210/callback"
PASSWORD = "correct horse battery staple"
VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)


@pytest.fixture
def http_env(tmp_path):
    from app.research_web.mcp_facade.oauth import OAuthProvider, create_oauth_routes

    now = [time.time()]
    accounts = AccountStore(tmp_path / "accounts", clock=lambda: now[0])
    users = [accounts.create_user(name, PASSWORD) for name in ("alice", "bobby")]
    sessions = [accounts.login(user.username, PASSWORD)[0] for user in users]
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    store = AuthorizationStore(accounts, issuer=origin)
    provider = OAuthProvider(store)
    app = Starlette(routes=create_oauth_routes(provider))
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("isolated_server_start_failed")
            time.sleep(0.01)
        with httpx.Client(
            base_url=origin, follow_redirects=False, timeout=5, trust_env=False
        ) as client:
            yield client, store, users, sessions, now
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


def params(**changes):
    values = {
        "client_id": CLIENT,
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "scope": "rwb.read",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "opaque-state",
    }
    values.update(changes)
    return values


def test_metadata_public_client(http_env):
    client, store, *_ = http_env
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["issuer"] == store.issuer
    assert metadata["token_endpoint_auth_methods_supported"] == ["none"]
    assert metadata["revocation_endpoint_auth_methods_supported"] == ["none"]
    assert metadata["authorization_response_iss_parameter_supported"] is True
    assert metadata["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert metadata["scopes_supported"] == ["rwb.read"]
    assert "registration_endpoint" not in metadata
    assert metadata.get("client_id_metadata_document_supported", False) is False
    assert client.post("/register", json={}).status_code == 404


def browser(client, session, origin=None):
    headers = {"Cookie": "rwb_session=" + session}
    if origin:
        headers["Origin"] = origin
    return headers


def authorize(http_env, *, index=0, material_ids=(), **changes):
    client, store, _, sessions, _ = http_env
    response = client.get(
        "/authorize", params=params(**changes), headers=browser(client, sessions[index])
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/mcp/consent?")
    request_id = parse_qs(urlsplit(location).query)["request_id"][0]
    page = client.get(location, headers=browser(client, sessions[index]))
    assert page.status_code == 200
    response = client.post(
        "/mcp/consent",
        data={"request_id": request_id, "decision": "allow", "material_id": list(material_ids)},
        headers=browser(client, sessions[index], store.issuer),
    )
    assert response.status_code == 302
    result = parse_qs(urlsplit(response.headers["location"]).query)
    assert result["iss"] == [store.issuer] and result["state"] == ["opaque-state"]
    return result["code"][0]


def exchange(client, code, **changes):
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT,
        "code": code,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
    }
    data.update(changes)
    return client.post("/token", data=data)


def refresh(client, token, **changes):
    data = {"grant_type": "refresh_token", "client_id": CLIENT, "refresh_token": token}
    data.update(changes)
    return client.post("/token", data=data)


def test_success_pkce_code_binding_and_replay(http_env):
    client, store, *_ = http_env
    code = authorize(http_env)
    for changes in (
        {"resource": store.issuer + "/wrong"},
        {"client_id": "foreign"},
        {"code_verifier": "x" * 43},
        {"redirect_uri": "http://127.0.0.1:43211/callback"},
    ):
        assert exchange(client, code, **changes).status_code in (400, 401)
    result = exchange(client, code)
    assert result.status_code == 200
    token = result.json()
    assert token["scope"] == "rwb.read" and token["expires_in"] == 600
    assert (
        store.verify_access(token["access_token"], resource=store.resource).issuer == store.issuer
    )
    assert exchange(client, code).json()["error"] == "invalid_grant"


def test_authorize_error_iss_and_malicious_callbacks(http_env):
    client, store, *_ = http_env
    for changes in (
        {"scope": "write"},
        {"resource": store.issuer + "/wrong"},
        {"code_challenge_method": "plain"},
        {"response_type": "token"},
    ):
        response = client.get("/authorize", params=params(**changes))
        assert response.status_code == 302
        query = parse_qs(urlsplit(response.headers["location"]).query)
        assert query["iss"] == [store.issuer] and query["state"] == ["opaque-state"]
        assert "error" in query
    for uri in (
        "https://evil.example/callback",
        "http://localhost/callback",
        "http://127.0.0.1:4/other",
        "http://127.0.0.1/callback?iss=evil",
        "http://127.0.0.1:0/callback",
        "http://127.1/callback",
    ):
        response = client.get("/authorize", params=params(redirect_uri=uri))
        assert response.status_code == 400 and "location" not in response.headers
    assert (
        client.get(
            "/authorize", params=params(client_id="https://evil.example/client.json")
        ).status_code
        == 400
    )


def test_login_return_and_no_unbound_request(http_env):
    from app.research_web.mcp_facade.oauth_views import validated_login_return

    client, store, *_ = http_env
    response = client.get("/authorize", params=params())
    login = urlsplit(response.headers["location"])
    assert login.path == "/auth"
    returned = parse_qs(login.query)["return_to"][0]
    assert validated_login_return(returned) == returned
    with store.accounts._connection() as db:
        assert db.execute("SELECT COUNT(*) FROM mcp_oauth_requests").fetchone()[0] == 0
    for bad in (
        "//evil.example/authorize?a=1",
        "https://evil.example/authorize?a=1",
        "/api/research?a=1",
        "/authorize/../api?a=1",
        "/authorize?a=1#evil",
        "/authorize?x=\nLocation:evil",
        "/\\evil?x=1",
        "//[malformed",
    ):
        assert validated_login_return(bad) is None
    # Existing login UI must navigate to this exact value after successful login.
    sessions = http_env[3]
    resumed = client.get(returned, headers=browser(client, sessions[0]))
    assert resumed.headers["location"].startswith("/mcp/consent?")


def test_refresh_resource_guard_before_replay_revocation(http_env):
    from app.research_web.multiuser.accounts import AccountError

    client, store, *_ = http_env
    original = exchange(client, authorize(http_env)).json()
    rotated = refresh(client, original["refresh_token"]).json()
    for changes in (
        {"resource": store.issuer + "/wrong"},
        {"scope": "write"},
        {"client_id": "foreign"},
    ):
        assert refresh(client, original["refresh_token"], **changes).status_code in (400, 401)
        store.verify_access(rotated["access_token"], resource=store.resource)
    assert refresh(client, original["refresh_token"]).json()["error"] == "invalid_grant"
    with pytest.raises(AccountError):
        store.verify_access(rotated["access_token"], resource=store.resource)
    assert refresh(client, rotated["refresh_token"]).status_code == 400


def test_standard_public_revoke_without_secret(http_env):
    import asyncio

    from app.research_web.mcp_facade.oauth import OAuthVerifier

    client, store, *_ = http_env
    for hint in ("access_token", "refresh_token"):
        pair = exchange(client, authorize(http_env)).json()
        assert (
            client.post(
                "/revoke", data={"client_id": CLIENT, "token": pair[hint], "token_type_hint": hint}
            ).status_code
            == 200
        )
        assert asyncio.run(OAuthVerifier(store).verify_token(pair["access_token"])) is None
    assert client.post("/revoke", data={"client_id": CLIENT, "token": "unknown"}).status_code == 200


def test_consent_csrf_isolation_and_denial(http_env):
    client, store, users, sessions, _ = http_env
    response = client.get("/authorize", params=params(), headers=browser(client, sessions[0]))
    location = response.headers["location"]
    request_id = parse_qs(urlsplit(location).query)["request_id"][0]
    data = {"request_id": request_id, "decision": "allow"}
    assert client.get(location).status_code == 401
    assert client.get(location, headers=browser(client, sessions[1])).status_code == 400
    assert (
        client.post("/mcp/consent", data=data, headers=browser(client, sessions[0])).status_code
        == 403
    )
    assert (
        client.post(
            "/mcp/consent", data=data, headers=browser(client, sessions[0], "https://evil.example")
        ).status_code
        == 403
    )
    material = store.approve_material(
        user_id=users[1].id,
        context_id="b",
        kind="source",
        object_id="secret-b",
        sha256="a" * 64,
        classification="synthetic",
    )
    page = client.get(location, headers=browser(client, sessions[0]))
    assert "secret-b" not in page.text and material.id not in page.text
    assert (
        client.post(
            "/mcp/consent",
            data={**data, "material_id": material.id},
            headers=browser(client, sessions[0], store.issuer),
        ).status_code
        == 400
    )
    denied = client.post(
        "/mcp/consent",
        data={**data, "decision": "deny"},
        headers=browser(client, sessions[0], store.issuer),
    )
    query = parse_qs(urlsplit(denied.headers["location"]).query)
    assert query["error"] == ["access_denied"] and query["iss"] == [store.issuer]


def test_application_revocation_user_isolation(http_env):
    client, store, _users, sessions, _ = http_env
    pair = exchange(client, authorize(http_env)).json()
    grant = store.verify_access(pair["access_token"], resource=store.resource).grant_id
    own = client.get("/mcp/applications", headers=browser(client, sessions[0]))
    other = client.get("/mcp/applications", headers=browser(client, sessions[1]))
    assert grant in own.text and grant not in other.text
    assert (
        client.post(
            "/mcp/applications",
            data={"grant_id": grant},
            headers=browser(client, sessions[1], store.issuer),
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/mcp/applications", data={"grant_id": grant}, headers=browser(client, sessions[0])
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/mcp/applications",
            data={"grant_id": grant},
            headers=browser(client, sessions[0], store.issuer),
        ).status_code
        == 303
    )
    assert refresh(client, pair["refresh_token"]).status_code == 400


def test_expiry_and_account_lifecycle(http_env):
    client, store, users, sessions, now = http_env
    code = authorize(http_env)
    now[0] += 61
    assert exchange(client, code).status_code == 400
    pair = exchange(client, authorize(http_env)).json()
    store.accounts.logout(sessions[0])
    assert refresh(client, pair["refresh_token"]).status_code == 200
    store.accounts.set_enabled(users[0].id, False)
    assert refresh(client, pair["refresh_token"]).status_code == 400


def test_duplicate_inputs_caps_and_secret_safe_errors(http_env):
    client, _store, *_ = http_env
    response = client.post(
        "/token",
        content="client_id=rwb-codex-native&client_id=evil&grant_type=refresh_token&refresh_token=secret",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.json() == {"error": "invalid_request"}
    assert client.post("/token", data={"client_id": CLIENT, "client_secret": "secret"}).json() == {
        "error": "invalid_client"
    }
    assert (
        "secret"
        not in client.post("/token", data={"client_id": CLIENT, "grant_type": "secret"}).text
    )
    assert (
        client.post(
            "/token",
            content=iter([b"x" * 32768, b"x" * 32769]),
            headers={"content-type": "application/x-www-form-urlencoded"},
        ).status_code
        == 413
    )


def test_material_selection_verifier_identity_and_wrong_issuer(http_env):
    import asyncio

    from app.research_web.mcp_facade.oauth import OAuthVerifier

    client, store, users, _, _ = http_env
    selected = store.approve_material(
        user_id=users[0].id,
        context_id="a",
        kind="source",
        object_id="public-a",
        sha256="b" * 64,
        classification="public",
    )
    store.approve_material(
        user_id=users[0].id,
        context_id="a",
        kind="source",
        object_id="not-selected",
        sha256="c" * 64,
        classification="synthetic",
    )
    pair = exchange(
        client, authorize(http_env, material_ids=[selected.id]), resource=store.resource
    ).json()
    access = asyncio.run(OAuthVerifier(store).verify_token(pair["access_token"]))
    assert access.subject == users[0].id and access.client_id == CLIENT
    assert access.resource == store.resource and access.claims["iss"] == store.issuer
    assert store.list_grant_materials(access.claims["grant_id"], user_id=access.subject) == [
        selected
    ]
    wrong = AuthorizationStore(store.accounts, issuer="http://127.0.0.1:23456")
    assert asyncio.run(OAuthVerifier(wrong).verify_token(pair["access_token"])) is None
    assert asyncio.run(OAuthVerifier(store).verify_token("invalid")) is None


def test_password_reset_and_token_expiry(http_env):
    import asyncio

    from app.research_web.mcp_facade.oauth import OAuthVerifier

    client, store, users, _, now = http_env
    pair = exchange(client, authorize(http_env)).json()
    now[0] += 601
    assert asyncio.run(OAuthVerifier(store).verify_token(pair["access_token"])) is None
    rotated = refresh(client, pair["refresh_token"], resource=store.resource).json()
    store.accounts.reset_password(users[0].id, "a newly reset long password")
    assert asyncio.run(OAuthVerifier(store).verify_token(rotated["access_token"])) is None
    assert refresh(client, rotated["refresh_token"]).status_code == 400


def test_concurrent_browser_contexts_and_code_redemption(http_env):
    from concurrent.futures import ThreadPoolExecutor

    client, store, users, *_ = http_env
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(lambda index: authorize(http_env, index=index), range(2)))
        pairs = list(pool.map(lambda code: exchange(client, code).json(), codes))
    for index, pair in enumerate(pairs):
        assert (
            store.verify_access(pair["access_token"], resource=store.resource).user_id
            == users[index].id
        )
    code = authorize(http_env)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: exchange(client, code), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 400]


def test_browser_authorize_post_csrf_and_host(http_env):
    client, store, _, sessions, _ = http_env
    assert (
        client.post("/authorize", data=params(), headers=browser(client, sessions[0])).status_code
        == 403
    )
    result = client.post(
        "/authorize", data=params(), headers=browser(client, sessions[0], store.issuer)
    )
    assert result.status_code == 302 and result.headers["location"].startswith("/mcp/consent?")
    assert (
        client.get(
            "/.well-known/oauth-authorization-server", headers={"Host": "attacker.example"}
        ).status_code
        == 400
    )
