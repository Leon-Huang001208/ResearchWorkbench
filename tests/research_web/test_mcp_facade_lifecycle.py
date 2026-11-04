"""Offline upgrade/rollback preserves account records and independent grant semantics."""

import sqlite3

import pytest
from test_mcp_facade_store import CLIENT, ORIGIN, PASSWORD, exchange, request

from app.research_web.mcp_facade.authorization_store import AuthorizationStore
from app.research_web.multiuser.accounts import AccountError, AccountStore
from app.research_web.multiuser.gateway import create_gateway


def account_rows(accounts):
    with sqlite3.connect(accounts.path) as db:
        return {
            name: db.execute(f"SELECT * FROM {name} ORDER BY rowid").fetchall()
            for name in ("accounts", "sessions")
        }


class NoResearchPool:
    async def close(self):
        pass

    async def backend_for(self, *args):
        pytest.fail("lifecycle must not start a research runtime")


@pytest.mark.asyncio
async def test_additive_upgrade_restart_and_explicit_revoke_rollback(tmp_path):
    root = tmp_path / "server"
    accounts = AccountStore(root)
    user = accounts.create_user("alice", PASSWORD)
    cookie, _ = accounts.login(user.username, PASSWORD)
    history = root / "history.json"
    history.write_bytes(b'{"synthetic":"original-history"}')
    original_rows = account_rows(accounts)
    original_history = history.read_bytes(), history.stat().st_mtime_ns
    pool = NoResearchPool()
    app = create_gateway(accounts, pool, origin=ORIGIN, mcp_enabled=True)
    async with app.router.lifespan_context(app):
        store = app.state.mcp_facade.store
        req = request(store, user)
        tokens = exchange(store, store.issue_code(req.id, user_id=user.id, material_ids=[]))
        record = store.verify_access(tokens.access_token, resource=store.resource)
        assert account_rows(accounts) == original_rows
    reopened_accounts = AccountStore(root)
    reopened = AuthorizationStore(reopened_accounts, issuer=ORIGIN)
    assert reopened.verify_access(tokens.access_token, resource=reopened.resource) == record
    assert reopened_accounts.authenticate(cookie).id == user.id
    # Explicit application revocation is durable; merely disabling the switch
    # does not pretend to revoke stored grants or erase recovery evidence.
    reopened.revoke_grant(record.grant_id, user_id=user.id)
    before_disabled = accounts.path.read_bytes()
    disabled = create_gateway(reopened_accounts, pool, origin=ORIGIN, mcp_enabled=False)
    async with disabled.router.lifespan_context(disabled):
        assert not hasattr(disabled.state, "mcp_facade")
        assert accounts.path.read_bytes() == before_disabled
    enabled = create_gateway(reopened_accounts, pool, origin=ORIGIN, mcp_enabled=True)
    async with enabled.router.lifespan_context(enabled):
        restored = enabled.state.mcp_facade.store
        with pytest.raises(AccountError):
            restored.verify_access(tokens.access_token, resource=restored.resource)
        with pytest.raises(AccountError):
            restored.rotate_refresh(tokens.refresh_token, client_id=CLIENT)
    assert account_rows(accounts) == original_rows
    assert (history.read_bytes(), history.stat().st_mtime_ns) == original_history


@pytest.mark.parametrize("action", ["logout", "reset", "disable"])
def test_account_actions_keep_logout_independent_and_revoke_security_changes(tmp_path, action):
    accounts = AccountStore(tmp_path / "server")
    user = accounts.create_user("alice", PASSWORD)
    cookie, _ = accounts.login(user.username, PASSWORD)
    store = AuthorizationStore(accounts, issuer=ORIGIN)
    req = request(store, user)
    tokens = exchange(store, store.issue_code(req.id, user_id=user.id, material_ids=[]))
    if action == "logout":
        accounts.logout(cookie)
    elif action == "reset":
        accounts.reset_password(user.id, PASSWORD + " changed")
    else:
        accounts.set_enabled(user.id, False)
        accounts.set_enabled(user.id, True)
    restored = AuthorizationStore(AccountStore(accounts.root), issuer=ORIGIN)
    if action == "logout":
        assert (
            restored.verify_access(tokens.access_token, resource=restored.resource).user_id
            == user.id
        )
    else:
        with pytest.raises(AccountError):
            restored.verify_access(tokens.access_token, resource=restored.resource)
        with pytest.raises(AccountError):
            restored.rotate_refresh(tokens.refresh_token, client_id=CLIENT)
