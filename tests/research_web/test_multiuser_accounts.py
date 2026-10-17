"""Private account identities, durable login limits and credential revocation."""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from app.research_web.multiuser.accounts import (
    SESSION_TTL_SECONDS,
    AccountError,
    AccountStore,
)

PASSWORD = "correct horse battery staple"
OTHER_PASSWORD = "a different long password"


def error_code(code, status):
    return pytest.raises(AccountError, match=f"^{code}$", check=lambda exc: exc.status == status)


def test_accounts_persist_normalized_public_identities_without_secrets(tmp_path):
    root = tmp_path / "accounts"
    store = AccountStore(root)
    alice = store.create_user("Alice", PASSWORD, "admin")
    bob = store.create_user("bob", OTHER_PASSWORD)
    token, account = store.login("ALICE", PASSWORD)
    assert account == alice
    assert alice.public() == {
        "id": alice.id,
        "username": "alice",
        "role": "admin",
        "enabled": True,
    }
    assert bob.role == "user" and bob.id != alice.id
    with pytest.raises(FrozenInstanceError):
        alice.username = "bob"
    restored = AccountStore(root)
    assert restored.authenticate(token) == alice
    assert {user.id for user in restored.list_users()} == {alice.id, bob.id}
    assert restored.get_user(bob.id) == bob
    data = (root / "accounts.sqlite3").read_bytes()
    assert PASSWORD.encode() not in data
    assert OTHER_PASSWORD.encode() not in data
    assert token.encode() not in data
    assert os.stat(root).st_mode & 0o777 == 0o700
    assert os.stat(root / "accounts.sqlite3").st_mode & 0o777 == 0o600


def test_each_token_has_its_owner_and_logout_is_idempotent(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    alice = store.create_user("alice", PASSWORD)
    bob = store.create_user("bob", PASSWORD)
    alice_token, _ = store.login("alice", PASSWORD)
    bob_token, _ = store.login("bob", PASSWORD)
    assert store.authenticate(alice_token).id == alice.id
    assert store.authenticate(bob_token).id == bob.id
    store.logout(alice_token)
    store.logout(alice_token)
    assert store.authenticate(alice_token) is None
    assert store.authenticate(bob_token).id == bob.id
    assert store.authenticate("fabricated") is None


def test_password_reset_and_disabling_revoke_existing_sessions(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    alice = store.create_user("alice", PASSWORD)
    first, _ = store.login("alice", PASSWORD)
    store.reset_password(alice.id, OTHER_PASSWORD)
    assert store.authenticate(first) is None
    with error_code("invalid_credentials", 401):
        store.login("alice", PASSWORD)
    second, _ = store.login("alice", OTHER_PASSWORD)
    assert not store.set_enabled(alice.id, False).enabled
    assert store.authenticate(second) is None
    with error_code("invalid_credentials", 401):
        store.login("alice", OTHER_PASSWORD)
    store.set_enabled(alice.id, True)
    assert store.authenticate(second) is None
    assert store.login("alice", OTHER_PASSWORD)[1].enabled


def test_expiry_is_fixed_and_oldest_session_is_bounded(tmp_path):
    now = [1000.0]
    store = AccountStore(tmp_path / "accounts", clock=lambda: now[0])
    store.create_user("alice", PASSWORD)
    token, _ = store.login("alice", PASSWORD)
    now[0] += SESSION_TTL_SECONDS - 1
    assert store.authenticate(token) is not None
    now[0] += 1
    assert store.authenticate(token) is None
    tokens = []
    for _ in range(17):
        tokens.append(store.login("alice", PASSWORD)[0])
        now[0] += 1
    assert store.authenticate(tokens[0]) is None
    assert all(store.authenticate(token) for token in tokens[1:])


def test_last_enabled_admin_cannot_be_disabled_but_reset_is_allowed(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    first = store.create_user("admin", PASSWORD, "admin")
    token, _ = store.login("admin", PASSWORD)
    with error_code("last_active_admin", 409):
        store.set_enabled(first.id, False)
    store.reset_password(first.id, OTHER_PASSWORD)
    assert store.authenticate(token) is None
    second = store.create_user("admin2", PASSWORD, "admin")
    store.set_enabled(first.id, False)
    with error_code("last_active_admin", 409):
        store.set_enabled(second.id, False)


def test_duplicate_and_invalid_input_errors_are_safe(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    store.create_user("alice", PASSWORD)
    with error_code("username_exists", 409):
        store.create_user("ALICE", OTHER_PASSWORD)
    for username in ("ab", "1alice", " alice", "中文用户", "a" * 65, "a/b"):
        with error_code("invalid_username", 400):
            store.create_user(username, PASSWORD)
    for password in ("short", "x" * 1025, "密" * 400, "broken\ud800password"):
        with error_code("invalid_password", 400):
            store.create_user("valid", password)
    with error_code("invalid_role", 400):
        store.create_user("valid", PASSWORD, "owner")
    with error_code("account_not_found", 404):
        store.get_user("../elsewhere")
    with error_code("invalid_credentials", 401):
        store.login("missing", PASSWORD)
    with error_code("invalid_credentials", 401):
        store.login("alice", "wrong password")


def test_username_throttle_is_persistent_and_applies_to_unknown_names(tmp_path):
    now = [1000.0]
    root = tmp_path / "accounts"
    store = AccountStore(root, clock=lambda: now[0])
    store.create_user("alice", PASSWORD)
    for username in ("ALICE", "missing"):
        for _ in range(5):
            with error_code("invalid_credentials", 401):
                AccountStore(root, clock=lambda: now[0]).login(username, "wrong password")
        with error_code("login_rate_limited", 429):
            AccountStore(root, clock=lambda: now[0]).login(username.lower(), PASSWORD)
    now[0] += 901
    assert AccountStore(root, clock=lambda: now[0]).login("alice", PASSWORD)[1].username == "alice"


def test_global_throttle_limits_varying_unknown_names(tmp_path):
    now = [1000.0]
    root = tmp_path / "accounts"
    store = AccountStore(root, clock=lambda: now[0])
    for index in range(100):
        with error_code("invalid_credentials", 401):
            store.login(f"unknown{index}", "bad")
    with error_code("login_rate_limited", 429):
        AccountStore(root, clock=lambda: now[0]).login("another", PASSWORD)


def test_account_limit_is_transactional(tmp_path, monkeypatch):
    import app.research_web.multiuser.accounts as module

    monkeypatch.setattr(module, "MAX_ACCOUNTS", 2)
    store = AccountStore(tmp_path / "accounts")
    store.create_user("alice", PASSWORD)
    store.create_user("bob", PASSWORD)
    with error_code("account_limit_reached", 409):
        store.create_user("third", PASSWORD)
    assert len(store.list_users()) == 2


def test_refuses_symlinks_insecure_permissions_and_replacement(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    for root in (alias, alias / "nested"):
        with error_code("account_store_unsafe", 503):
            AccountStore(root)
    assert not (outside / "nested").exists()
    insecure = tmp_path / "insecure"
    insecure.mkdir(mode=0o755)
    with error_code("account_store_unsafe", 503):
        AccountStore(insecure)
    store = AccountStore(tmp_path / "private")
    store.path.unlink()
    store.path.symlink_to(outside / "db")
    with error_code("account_store_unsafe", 503):
        store.list_users()
    assert not (outside / "db").exists()


def test_refuses_insecure_or_corrupt_existing_database(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    store.path.chmod(0o644)
    with error_code("account_store_unsafe", 503):
        store.list_users()
    store.path.chmod(0o600)
    store.path.write_bytes(b"not a sqlite database")
    with error_code("account_store_failed", 503):
        AccountStore(store.root)


def test_invalid_stored_password_parameters_fail_closed(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    store.create_user("alice", PASSWORD)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE accounts SET scrypt_n = ?", (2**30,))
    with error_code("account_store_failed", 503):
        store.login("alice", PASSWORD)


def test_permission_error_is_reported_without_path_or_secret(tmp_path, monkeypatch):
    store = AccountStore(tmp_path / "accounts")

    def denied(*args, **kwargs):
        raise PermissionError("secret path must not escape")

    monkeypatch.setattr(sqlite3, "connect", denied)
    with error_code("account_store_failed", 503):
        store.list_users()


def test_concurrent_writers_cannot_duplicate_names_or_disable_all_admins(tmp_path):
    root = tmp_path / "accounts"
    store = AccountStore(root)
    first = store.create_user("admin", PASSWORD, "admin")
    second = store.create_user("admin2", PASSWORD, "admin")

    def disable(user_id):
        try:
            AccountStore(root).set_enabled(user_id, False)
            return "disabled"
        except AccountError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(disable, (first.id, second.id))) == [
            "disabled",
            "last_active_admin",
        ]

    def create(_):
        try:
            AccountStore(root).create_user("alice", PASSWORD)
            return "created"
        except AccountError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(create, range(2))) == ["created", "username_exists"]


def test_salts_and_token_digests_are_distinct_and_database_links_are_rejected(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    store.create_user("alice", PASSWORD)
    store.create_user("bob", PASSWORD)
    first, _ = store.login("alice", PASSWORD)
    second, _ = store.login("alice", PASSWORD)
    assert first != second
    with sqlite3.connect(store.path) as db:
        salts = db.execute("SELECT salt, password_hash FROM accounts").fetchall()
        tokens = db.execute("SELECT token_hash FROM sessions").fetchall()
    assert len({row[0] for row in salts}) == 2
    assert len({row[1] for row in salts}) == 2
    assert len({row[0] for row in tokens}) == 2
    assert all(len(row[0]) == 64 for row in tokens)
    os.link(store.path, tmp_path / "linked.sqlite3")
    with error_code("account_store_unsafe", 503):
        store.list_users()


def test_store_detects_replaced_root_and_rejects_journal_symlink(tmp_path):
    store = AccountStore(tmp_path / "accounts")
    original = tmp_path / "original"
    store.root.rename(original)
    store.root.mkdir(mode=0o700)
    with error_code("account_store_unsafe", 503):
        store.list_users()
    journal_store = AccountStore(tmp_path / "other")
    (journal_store.root / "accounts.sqlite3-journal").symlink_to(tmp_path / "outside-journal")
    with error_code("account_store_unsafe", 503):
        journal_store.create_user("alice", PASSWORD)
    assert not (tmp_path / "outside-journal").exists()


def test_corrupt_foreign_keys_and_clock_fail_closed(tmp_path):
    now = [1000.0]
    store = AccountStore(tmp_path / "accounts", clock=lambda: now[0])
    store.create_user("alice", PASSWORD)
    token, _ = store.login("alice", PASSWORD)
    now[0] = float("nan")
    with error_code("account_store_failed", 503):
        store.authenticate(token)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE sessions SET user_id='missing-account'")
    with error_code("account_store_failed", 503):
        AccountStore(store.root)
