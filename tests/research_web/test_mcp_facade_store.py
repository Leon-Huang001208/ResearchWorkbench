"""Durable independent application grants, exact material approval, and replay fences."""

import base64
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.research_web.multiuser.accounts import AccountError, AccountStore

PASSWORD = "correct horse battery staple"
ORIGIN = "https://research.tail123.ts.net"
CLIENT = "rwb-codex-native"
CALLBACK = "http://127.0.0.1:43210/callback"
VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
DIGEST = hashlib.sha256(b"public fixture").hexdigest()


@pytest.fixture
def env(tmp_path):
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    now = [1000.0]
    accounts = AccountStore(tmp_path / "accounts", clock=lambda: now[0])
    alice = accounts.create_user("alice", PASSWORD)
    bob = accounts.create_user("bob", PASSWORD)
    store = AuthorizationStore(accounts, issuer=ORIGIN)
    return accounts, store, alice, bob, now


def request(store, user, **changes):
    args = {
        "user_id": user.id,
        "client_id": CLIENT,
        "redirect_uri": CALLBACK,
        "scopes": ["rwb.read"],
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "resource": ORIGIN + "/mcp",
        "state": "opaque-state",
    }
    args.update(changes)
    return store.create_request(**args)


def approval(store, user, **changes):
    args = {
        "user_id": user.id,
        "context_id": "context-a",
        "kind": "report",
        "object_id": "report-a",
        "sha256": DIGEST,
        "classification": "public",
    }
    args.update(changes)
    return store.approve_material(**args)


def exchange(store, code, **changes):
    args = {
        "client_id": CLIENT,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
        "resource": ORIGIN + "/mcp",
    }
    args.update(changes)
    return store.exchange_code(code, **args)


def grant(env):
    _, store, alice, _, _ = env
    material = approval(store, alice)
    req = request(store, alice)
    code = store.issue_code(req.id, user_id=alice.id, material_ids=[material.id])
    return material, code, exchange(store, code)


def test_store_contract_exists():
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    assert callable(AuthorizationStore)


def test_restart_digest_storage_and_binding(env):
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    accounts, _store, alice, _, _ = env
    material, code, tokens = grant(env)
    reopened = AuthorizationStore(AccountStore(accounts.root, clock=accounts.clock), issuer=ORIGIN)
    access = reopened.verify_access(tokens.access_token, resource=ORIGIN + "/mcp")
    assert access.user_id == alice.id and access.scopes == ("rwb.read",)
    assert (
        reopened.authorize_material(
            access.grant_id,
            user_id=alice.id,
            context_id="context-a",
            kind="report",
            object_id="report-a",
            sha256=DIGEST,
        )
        == material
    )
    assert reopened.load_client(CLIENT).token_endpoint_auth_method == "none"
    assert reopened.list_grants(alice.id)[0].id == access.grant_id
    assert reopened.list_materials(alice.id) == [material]
    for token in (code, tokens.access_token, tokens.refresh_token):
        assert token.encode() not in accounts.path.read_bytes()


def test_invalid_request_boundaries(env):
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    accounts, store, alice, _, _ = env
    with pytest.raises(AccountError, match="invalid_issuer"):
        AuthorizationStore(accounts, issuer="https://public.example.com")
    for changes in (
        {"client_id": "foreign"},
        {"redirect_uri": "http://localhost/callback"},
        {"redirect_uri": "http://127.0.0.1/callback?x=1"},
        {"redirect_uri": "http://127.0.0.1:0/callback"},
        {"scopes": ["write"]},
        {"scopes": []},
        {"resource": ORIGIN + "/other"},
        {"code_challenge_method": "plain"},
        {"code_challenge": "bad"},
    ):
        with pytest.raises(AccountError):
            request(store, alice, **changes)


def test_wrong_exchange_context_does_not_consume_code(env):
    _, store, alice, _, _ = env
    req = request(store, alice)
    code = store.issue_code(req.id, user_id=alice.id, material_ids=[])
    assert store.load_code(code, client_id=CLIENT).code_challenge == CHALLENGE
    for changes in (
        {"client_id": "foreign"},
        {"redirect_uri": "http://127.0.0.1:42/callback"},
        {"resource": ORIGIN + "/other"},
        {"code_verifier": "x" * 43},
    ):
        with pytest.raises(AccountError):
            exchange(store, code, **changes)
    assert exchange(store, code, resource=None).resource == ORIGIN + "/mcp"
    with pytest.raises(AccountError):
        exchange(store, code)
    with pytest.raises(AccountError):
        store.issue_code(req.id, user_id=alice.id, material_ids=[])


def test_code_and_consent_expiry(env):
    _, store, alice, _, now = env
    req = request(store, alice)
    pending = request(store, alice)
    code = store.issue_code(req.id, user_id=alice.id, material_ids=[])
    now[0] += 60
    with pytest.raises(AccountError):
        exchange(store, code)
    now[0] += 600
    with pytest.raises(AccountError):
        store.load_request(req.id, user_id=alice.id)
    with pytest.raises(AccountError):
        store.load_request(pending.id, user_id=alice.id)


def test_concurrent_code_exchange_has_one_winner(env):
    _, store, alice, _, _ = env
    code = store.issue_code(request(store, alice).id, user_id=alice.id, material_ids=[])

    def attempt(_):
        try:
            return exchange(store, code)
        except AccountError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(value is not None for value in pool.map(attempt, range(4))) == 1


def test_refresh_rotation_binding_and_concurrency(env):
    _, store, _, _, _ = env
    _, _, tokens = grant(env)
    for changes in ({"client_id": "other"}, {"resource": ORIGIN + "/other"}, {"scopes": ["write"]}):
        args = {"client_id": CLIENT, "resource": None, "scopes": None}
        args.update(changes)
        with pytest.raises(AccountError):
            store.rotate_refresh(tokens.refresh_token, **args)
    assert store.load_refresh(tokens.refresh_token, client_id=CLIENT).resource == ORIGIN + "/mcp"

    def attempt(_):
        try:
            return store.rotate_refresh(tokens.refresh_token, client_id=CLIENT)
        except AccountError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [value for value in pool.map(attempt, range(4)) if value]
    assert len(results) == 1
    # A concurrent second use is indistinguishable from theft: revoke the family.
    with pytest.raises(AccountError):
        store.verify_access(results[0].access_token, resource=ORIGIN + "/mcp")
    with pytest.raises(AccountError):
        store.rotate_refresh(tokens.refresh_token, client_id=CLIENT)


def test_expired_access_refresh_and_issuer(env):
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    accounts, store, _, _, now = env
    _, _, tokens = grant(env)
    other = AuthorizationStore(accounts, issuer="https://other.tail123.ts.net")
    with pytest.raises(AccountError):
        other.verify_access(tokens.access_token, resource=other.resource)
    now[0] += 600
    with pytest.raises(AccountError):
        store.verify_access(tokens.access_token, resource=store.resource)
    now[0] += 604800
    with pytest.raises(AccountError):
        store.rotate_refresh(tokens.refresh_token, client_id=CLIENT)


def test_material_owner_context_hash_and_revocation(env):
    _, store, alice, bob, _ = env
    material, _, tokens = grant(env)
    access = store.verify_access(tokens.access_token, resource=store.resource)
    args = {
        "user_id": alice.id,
        "context_id": "context-a",
        "kind": "report",
        "object_id": "report-a",
        "sha256": DIGEST,
    }
    for changes in (
        {"user_id": bob.id},
        {"context_id": "context-b"},
        {"object_id": "other"},
        {"sha256": "0" * 64},
    ):
        with pytest.raises(AccountError):
            store.authorize_material(access.grant_id, **(args | changes))
    store.revoke_material(material.id)
    with pytest.raises(AccountError):
        store.authorize_material(access.grant_id, **args)
    approval(store, alice)
    with pytest.raises(AccountError):
        store.authorize_material(access.grant_id, **args)


def test_approval_is_exact_and_consent_never_crosses_owner(env):
    _, store, alice, bob, _ = env
    for changes in ({"classification": "private"}, {"sha256": "unknown"}):
        with pytest.raises(AccountError):
            approval(store, alice, **changes)
    material = approval(store, bob)
    req = request(store, alice)
    with pytest.raises(AccountError):
        store.issue_code(req.id, user_id=bob.id, material_ids=[])
    with pytest.raises(AccountError):
        store.issue_code(req.id, user_id=alice.id, material_ids=[material.id])
    code = store.issue_code(req.id, user_id=alice.id, material_ids=[])
    tokens = exchange(store, code)
    access = store.verify_access(tokens.access_token, resource=store.resource)
    assert store.list_grant_materials(access.grant_id, user_id=alice.id) == []


def test_disable_reset_revoke_but_logout_keeps_grants(env):
    accounts, store, alice, _, _ = env
    _, _, tokens = grant(env)
    browser, _ = accounts.login("alice", PASSWORD)
    accounts.logout(browser)
    assert store.verify_access(tokens.access_token, resource=store.resource)
    pending = request(store, alice)
    accounts.set_enabled(alice.id, False)
    accounts.set_enabled(alice.id, True)
    with pytest.raises(AccountError):
        store.issue_code(pending.id, user_id=alice.id, material_ids=[])
    with pytest.raises(AccountError):
        store.verify_access(tokens.access_token, resource=store.resource)
    _, _, newer = grant(env)
    code = store.issue_code(request(store, alice).id, user_id=alice.id, material_ids=[])
    accounts.reset_password(alice.id, "another long password")
    with pytest.raises(AccountError):
        exchange(store, code)
    with pytest.raises(AccountError):
        store.rotate_refresh(newer.refresh_token, client_id=CLIENT)


def test_old_database_lifecycle_and_corruption_fail_closed(tmp_path):
    accounts = AccountStore(tmp_path / "old")
    alice = accounts.create_user("alice", PASSWORD)
    accounts.set_enabled(alice.id, False)
    accounts.set_enabled(alice.id, True)
    accounts.reset_password(alice.id, PASSWORD)
    with sqlite3.connect(accounts.path) as db:
        db.execute("CREATE TABLE mcp_oauth_grants (wrong_column TEXT)")
    with pytest.raises(AccountError, match="account_store_failed"):
        accounts.set_enabled(alice.id, False)
    assert accounts.get_user(alice.id).enabled


def test_explicit_revoke_is_owner_bound(env):
    _, store, alice, bob, _ = env
    _, _, tokens = grant(env)
    access = store.verify_access(tokens.access_token, resource=store.resource)
    with pytest.raises(AccountError):
        store.revoke_grant(access.grant_id, user_id=bob.id)
    store.revoke_grant(access.grant_id, user_id=alice.id)
    with pytest.raises(AccountError):
        store.verify_access(tokens.access_token, resource=store.resource)


def test_logs_and_models_never_render_issued_secrets(env, monkeypatch):
    from app.research_web.mcp_facade import authorization_store

    events = []
    monkeypatch.setattr(authorization_store.log, "info", lambda *a, **kw: events.append((a, kw)))
    _, store, _, _, _ = env
    _, code, tokens = grant(env)
    store.rotate_refresh(tokens.refresh_token, client_id=CLIENT)
    rendered = repr(events) + repr(tokens)
    assert events
    for token in (code, tokens.access_token, tokens.refresh_token):
        assert token not in rendered


def test_password_reset_failure_rolls_back_credentials_and_grants(env):
    accounts, store, alice, _, _ = env
    _, _, tokens = grant(env)
    with sqlite3.connect(accounts.path) as db:
        db.execute(
            "CREATE TRIGGER deny_revoke BEFORE UPDATE ON mcp_oauth_grants "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )
    with pytest.raises(AccountError, match="account_store_failed"):
        accounts.reset_password(alice.id, "another long password")
    assert accounts.login("alice", PASSWORD)[1].id == alice.id
    assert store.verify_access(tokens.access_token, resource=store.resource)


def test_refresh_replay_revokes_family_even_during_sdk_load(env):
    _, store, _, _, _ = env
    _, _, tokens = grant(env)
    rotated = store.rotate_refresh(tokens.refresh_token, client_id=CLIENT)
    assert store.verify_access(rotated.access_token, resource=store.resource)
    with pytest.raises(AccountError):
        store.load_refresh(tokens.refresh_token, client_id=CLIENT)
    with pytest.raises(AccountError):
        store.verify_access(rotated.access_token, resource=store.resource)


def test_weknora_callback_cannot_rebind_existing_grants(env):
    from app.research_web.mcp_facade.authorization_store import AuthorizationStore

    accounts, default, alice, _, _ = env
    client = "rwb-weknora"
    origin = "http://127.0.0.1:18181"
    redirect = origin + "/api/v1/mcp-oauth/callback"
    enabled = AuthorizationStore(accounts, issuer=default.issuer, weknora_oauth_origin=origin)
    pending = request(enabled, alice, client_id=client, redirect_uri=redirect)
    code = enabled.issue_code(pending.id, user_id=alice.id, material_ids=[])
    pair = exchange(enabled, code, client_id=client, redirect_uri=redirect)
    assert enabled.verify_access(pair.access_token, resource=enabled.resource).client_id == client
    with pytest.raises(AccountError, match="invalid_client"):
        AuthorizationStore(
            accounts, issuer=default.issuer, weknora_oauth_origin=origin.replace("18181", "18182")
        )
    with pytest.raises(AccountError, match="invalid_grant"):
        default.verify_access(pair.access_token, resource=default.resource)
    assert enabled.verify_access(pair.access_token, resource=enabled.resource).client_id == client
