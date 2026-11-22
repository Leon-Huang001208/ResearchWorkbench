"""Fixture isolation owns synthetic credentials; no OS credential operation is used."""

import os
from contextlib import contextmanager

import keyring
import keyring.core
import pytest
import test_api as api_fixtures
from _pytest.outcomes import Failed

from app.research_web import credential_backend
from app.research_web.frameworks.scheduler import collectors_enabled
from app.research_web.service import _persistent_mcp_key


@contextmanager
def memory_scope():
    """Exercise the real shared fixture with normal setup/teardown and undo."""
    with pytest.MonkeyPatch.context() as patch:
        scope = api_fixtures.isolated_keyring.__wrapped__(patch)
        values = next(scope)
        try:
            yield values
        finally:
            with pytest.raises(StopIteration):
                next(scope)


def test_memory_backend_and_public_facade_share_one_scope(monkeypatch, tmp_path):
    protected = tmp_path / "must-not-be-used"
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", str(protected))
    monkeypatch.setenv("HTTPS_PROXY", "http://fixture.invalid:9")
    monkeypatch.setenv("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED", "1")
    old_get = keyring.get_password
    old_factory = credential_backend.default_credential_backend
    with memory_scope() as values:
        assert "RESEARCH_CREDENTIAL_HOME" not in os.environ
        assert "HTTPS_PROXY" not in os.environ
        assert not collectors_enabled()
        first = credential_backend.default_credential_backend()
        second = credential_backend.default_credential_backend()
        first.set_password("fixture", "account", "synthetic")
        second.set_password(service="fixture", account="keyword", password="synthetic")
        assert first.get_password("fixture", "keyword") == "synthetic"
        assert second.get_password("fixture", "account") == "synthetic"
        assert keyring.get_password("fixture", "account") == "synthetic"
        keyring.set_password("fixture", "other", "also-synthetic")
        assert first.get_password("fixture", "other") == "also-synthetic"
        one = _persistent_mcp_key("fixture-confirmation", first)
        assert len(one) == 32 and _persistent_mcp_key("fixture-confirmation", second) == one
        assert values and not protected.exists()
    assert not values
    assert keyring.get_password is old_get
    assert credential_backend.default_credential_backend is old_factory
    assert os.environ["RESEARCH_CREDENTIAL_HOME"] == str(protected)
    assert os.environ["HTTPS_PROXY"] == "http://fixture.invalid:9"
    assert os.environ["RESEARCH_FRAMEWORK_COLLECTORS_ENABLED"] == "1"


def test_next_scope_cannot_reuse_the_previous_scope_vault():
    with memory_scope():
        credential_backend.default_credential_backend().set_password(
            "fixture", "case-owned", "synthetic"
        )
    with memory_scope() as values:
        assert not values
        assert (
            credential_backend.default_credential_backend().get_password("fixture", "case-owned")
            is None
        )


@pytest.mark.parametrize(
    "entry", ["system-init", "system-get", "private-init", "private-get", "public", "core"]
)
def test_real_backend_attempt_is_rejected_and_cannot_be_swallowed(entry):
    # This standalone scope deliberately catches the immediate rejection. The
    # fixture teardown must still reject the recorded escape, without OS calls.
    with (
        pytest.raises(AssertionError, match="real credential fallback"),
        memory_scope(),
        pytest.raises(Failed, match="must not access a real credential backend"),
    ):
        if entry == "system-init":
            credential_backend.SystemKeyringBackend()
        elif entry == "private-init":
            credential_backend.PrivateFileCredentialBackend("not-a-real-home")
        elif entry in {"system-get", "private-get"}:
            cls = (
                credential_backend.SystemKeyringBackend
                if entry == "system-get"
                else credential_backend.PrivateFileCredentialBackend
            )
            object.__new__(cls).get_password("fixture", "account")
        elif entry == "public":
            keyring.get_keyring()
        else:
            keyring.core.get_keyring()
