"""User-owned MySQL configuration and credential-store boundaries."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api import NativeFixture

from app.research_web.datahub.connections import (
    MYSQL_ACCOUNT,
    MYSQL_SERVICE,
    CredentialStoreError,
    MySQLConfiguration,
    MySQLConnectionStore,
)
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


class FakeKeyring:
    def __init__(self):
        self.value = None
        self.fail_get = False
        self.fail_set = False
        self.fail_delete = False

    def get_password(self, service, account):
        assert (service, account) == (MYSQL_SERVICE, MYSQL_ACCOUNT)
        if self.fail_get:
            raise RuntimeError("locked")
        return self.value

    def set_password(self, service, account, value):
        assert (service, account) == (MYSQL_SERVICE, MYSQL_ACCOUNT)
        if self.fail_set:
            raise RuntimeError("denied")
        self.value = value

    def delete_password(self, service, account):
        assert (service, account) == (MYSQL_SERVICE, MYSQL_ACCOUNT)
        if self.fail_delete:
            raise RuntimeError("denied")
        self.value = None


def config(**overrides):
    values = {
        "label": "阿里云因子库",
        "host": "db.example.test",
        "port": 3306,
        "user": "research_reader",
        "charset": "gbk",
        "tls_mode": "required_no_verify",
    }
    values.update(overrides)
    return MySQLConfiguration(**values)


def test_mysql_configuration_is_strict_and_never_accepts_secret_fields():
    with pytest.raises(ValidationError):
        MySQLConfiguration.model_validate({**config().model_dump(), "password": "secret"})
    with pytest.raises(ValidationError):
        MySQLConfiguration.model_validate({**config().model_dump(), "host": "47.0.0.1/path"})
    with pytest.raises(ValidationError):
        MySQLConfiguration.model_validate({**config().model_dump(), "tls_mode": "disabled"})


def test_save_keeps_secret_out_of_json_and_status_never_returns_it(tmp_path):
    keyring = FakeKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    status = store.save(config(), password="new-secret")

    raw = (tmp_path / "connections/mysql.json").read_text()
    assert "new-secret" not in raw
    assert json.loads(raw)["label"] == "阿里云因子库"
    assert keyring.value == "new-secret"
    assert status["configured"] is True
    assert status["secret_configured"] is True
    assert status["restart_required"] is True
    assert "password" not in status


def test_blank_password_retains_old_secret_and_config_failure_compensates(tmp_path, monkeypatch):
    keyring = FakeKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    store.save(config(), password="old-secret")
    store.save(config(label="更新名称"), password="")
    assert keyring.value == "old-secret"

    old = (tmp_path / "connections/mysql.json").read_bytes()
    monkeypatch.setattr(
        store, "_write_configuration", lambda _value: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(CredentialStoreError, match="configuration_write_failed"):
        store.save(config(label="失败更新"), password="new-secret")
    assert keyring.value == "old-secret"
    assert (tmp_path / "connections/mysql.json").read_bytes() == old


def test_nonempty_password_is_preserved_exactly(tmp_path):
    keyring = FakeKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    store.save(config(), password=" spaces-are-secret ")
    assert keyring.value == " spaces-are-secret "


def test_keyring_failures_are_closed_and_delete_is_compensated(tmp_path, monkeypatch):
    keyring = FakeKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    store.save(config(), password="old-secret")

    keyring.fail_get = True
    status = store.status()
    assert status["credential_store_available"] is False
    assert status["secret_configured"] is False
    assert status["failure_code"] == "credential_store_unavailable"
    with pytest.raises(CredentialStoreError, match="credential_store_unavailable"):
        store.credentials()
    keyring.fail_get = False

    original = (tmp_path / "connections/mysql.json").read_bytes()
    monkeypatch.setattr(
        store, "_delete_configuration", lambda: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(CredentialStoreError, match="configuration_delete_failed"):
        store.delete()
    assert keyring.value == "old-secret"
    assert (tmp_path / "connections/mysql.json").read_bytes() == original


def test_delete_failure_does_not_report_completion(tmp_path):
    keyring = FakeKeyring()
    store = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    store.save(config(), password="secret")
    keyring.fail_delete = True
    with pytest.raises(CredentialStoreError, match="credential_store_unavailable"):
        store.delete()
    assert (tmp_path / "connections/mysql.json").exists()


def test_mysql_configuration_api_never_refills_password(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    service.datahub.connections = MySQLConnectionStore(tmp_path, keyring_backend=FakeKeyring())
    with TestClient(create_app(service)) as client:
        initial = client.get("/api/research/data/sources/mysql/configuration")
        assert initial.status_code == 200
        assert initial.json()["configured"] is False
        payload = {**config().model_dump(), "password": "browser-secret"}
        saved = client.put("/api/research/data/sources/mysql/configuration", json=payload)
        assert saved.status_code == 200
        assert saved.json()["secret_configured"] is True
        assert "password" not in saved.text
        assert "browser-secret" not in saved.text
        loaded = client.get("/api/research/data/sources/mysql/configuration")
        assert "password" not in loaded.text
        removed = client.delete("/api/research/data/sources/mysql/configuration")
        assert removed.json() == {"deleted": True}


def test_mysql_configuration_api_rejects_extra_fields_and_closed_keyring(tmp_path):
    native = NativeFixture()
    service = ResearchService(native, Store(tmp_path))
    keyring = FakeKeyring()
    keyring.fail_get = True
    service.datahub.connections = MySQLConnectionStore(tmp_path, keyring_backend=keyring)
    with TestClient(create_app(service)) as client:
        invalid = client.put(
            "/api/research/data/sources/mysql/configuration",
            json={**config().model_dump(), "database": "must-not-be-saved"},
        )
        assert invalid.status_code == 422
        unavailable = client.put(
            "/api/research/data/sources/mysql/configuration",
            json={**config().model_dump(), "password": "secret"},
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "credential_store_unavailable"
