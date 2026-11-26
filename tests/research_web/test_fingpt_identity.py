"""Real gateway requests for the native WeKnora identity handoff."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.research_web.knowledge_backend.storage import KnowledgeStore
from app.research_web.multiuser.accounts import AccountStore
from app.research_web.multiuser.fingpt import CLIENT, PREFIX, FinGPTConfig
from app.research_web.multiuser.gateway import create_gateway


@pytest.fixture
def bridge(tmp_path):
    accounts = AccountStore(tmp_path / "server")
    user = accounts.create_user("admin", "a safe admin password", "admin")
    other = accounts.create_user("alice", "a safe alice password")
    root = tmp_path / "primary"
    root.mkdir(mode=0o700)
    knowledge = KnowledgeStore(root)
    knowledge.save_binding(
        {
            "origin": "http://127.0.0.1:18181",
            "user_id": "weknora-original",
            "workspace_id": "2",
            "sso_email": "original@example.com",
        }
    )

    class Pool:
        primary_user_id = user.id
        binding = SimpleNamespace(data_root=root)
        config = SimpleNamespace(root=tmp_path / "server")

        async def close(self):
            pass

    cfg = FinGPTConfig("http://127.0.0.1:18181", "s" * 48)
    app = create_gateway(accounts, Pool(), origin="http://localhost", fingpt_config=cfg)
    with TestClient(app, base_url="http://localhost") as browser:
        browser.post(
            "/api/server/login",
            json={"username": "admin", "password": "a safe admin password"},
            headers={"Origin": "http://localhost"},
        )
        yield browser, cfg, knowledge, accounts, other


def authorize(browser, cfg, **changes):
    args = {
        "response_type": "code",
        "client_id": CLIENT,
        "redirect_uri": cfg.callback,
        "scope": "openid email profile",
        "state": "native-signed-state",
        **changes,
    }
    return browser.get(PREFIX + "/authorize?" + urlencode(args), follow_redirects=False)


def exchange(browser, cfg, code):
    return browser.post(
        PREFIX + "/token",
        data={
            "client_id": CLIENT,
            "client_secret": cfg.client_secret,
            "redirect_uri": cfg.callback,
            "code": code,
            "grant_type": "authorization_code",
        },
    )


def test_native_code_exchange_uses_bound_identity_not_admin(bridge):
    browser, cfg, *_ = bridge
    response = authorize(browser, cfg)
    assert response.status_code == 302
    q = parse_qs(urlsplit(response.headers["location"]).query)
    assert q["state"] == ["native-signed-state"]
    token = exchange(browser, cfg, q["code"][0])
    assert token.status_code == 200
    result = browser.get(
        PREFIX + "/userinfo", headers={"Authorization": "Bearer " + token.json()["access_token"]}
    )
    assert result.json()["email"] == "original@example.com"
    assert result.json()["name"] != "admin"
    assert exchange(browser, cfg, q["code"][0]).status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"redirect_uri": "http://attacker/callback"},
        {"client_id": "other"},
        {"scope": "rwb.data.query"},
        {"state": ""},
    ],
)
def test_callback_and_client_are_fixed(bridge, changes):
    browser, cfg, *_ = bridge
    assert authorize(browser, cfg, **changes).status_code == 400


def test_logout_and_rebind_revoke_bridge_tokens(bridge):
    browser, cfg, knowledge, *_ = bridge
    code = parse_qs(urlsplit(authorize(browser, cfg).headers["location"]).query)["code"][0]
    token = exchange(browser, cfg, code).json()["access_token"]
    knowledge.save_binding({**knowledge.binding(), "sso_email": "different@example.com"})
    assert (
        browser.get(PREFIX + "/userinfo", headers={"Authorization": "Bearer " + token}).status_code
        == 401
    )
    browser.post("/api/server/logout", headers={"Origin": "http://localhost"})
    assert authorize(browser, cfg).status_code == 401


def test_workspace_exposes_entry_without_credentials(bridge):
    browser, cfg, *_ = bridge
    assert browser.get("/api/server/me").json()["fingpt_workspace"] is True
    r = browser.get(PREFIX + "/workspace")
    assert r.json() == {"enabled": True, "entry": cfg.origin + "/rwb-fingpt.html"}
    assert cfg.origin in r.headers["content-security-policy"]
