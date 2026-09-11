import json

import pytest
from pydantic import ValidationError

from app.research_web.automation.channels import DeliveryChannelStore
from app.research_web.automation.models import DeliveryChannelPut
from app.research_web.store import Store


class MemoryKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[(service, account)] = value

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


def test_delivery_channel_keeps_endpoint_and_secret_out_of_json(tmp_path):
    keyring = MemoryKeyring()
    store = Store(tmp_path)
    channels = DeliveryChannelStore(store, keyring_backend=keyring)

    public = channels.put(
        DeliveryChannelPut(
            name="研究通知",
            kind="webhook",
            endpoint="https://notify.example.test/research",
            secret="signing-secret",
        )
    )

    persisted = json.loads(store.index.read_text(encoding="utf-8"))
    raw = store.index.read_text(encoding="utf-8")
    assert public["configured"] is True
    assert "endpoint" not in public
    assert "notify.example.test" not in raw
    assert "signing-secret" not in raw
    assert persisted["delivery_channels"][public["id"]]["credential_ref"]["service"] == (
        "ResearchWorkbench.Delivery"
    )
    assert channels.configuration(public["id"])["secret"] == "signing-secret"


def test_delivery_channel_rejects_header_injection_and_insecure_endpoint():
    with pytest.raises(ValidationError):
        DeliveryChannelPut(
            name="SMTP",
            kind="smtp",
            smtp_host="smtp.example.test",
            smtp_port=587,
            sender="robot@example.test\nBcc: leak@example.test",
            recipients=["private@example.test"],
        )
    with pytest.raises(Exception, match="HTTPS"):
        DeliveryChannelStore._validated_endpoint("http://example.test/hook")


def test_new_signed_webhook_requires_a_secret(tmp_path):
    channels = DeliveryChannelStore(Store(tmp_path), keyring_backend=MemoryKeyring())

    with pytest.raises(Exception, match="签名秘密"):
        channels.put(
            DeliveryChannelPut(
                name="研究通知",
                kind="webhook",
                endpoint="https://notify.example.test/research",
            )
        )


def test_channel_write_failure_restores_index_and_keyring(tmp_path):
    keyring = MemoryKeyring()
    store = Store(tmp_path)
    channels = DeliveryChannelStore(store, keyring_backend=keyring)
    created = channels.put(
        DeliveryChannelPut(
            name="研究通知",
            kind="webhook",
            endpoint="https://notify.example.test/research",
            secret="old-secret",
        )
    )
    original = channels.get(created["id"])

    def fail_save():
        raise OSError("disk unavailable")

    store.save = fail_save
    with pytest.raises(OSError, match="disk unavailable"):
        channels.put(
            DeliveryChannelPut(
                id=created["id"],
                name="新名称",
                kind="webhook",
                endpoint="https://notify.example.test/new",
                secret="new-secret",
            )
        )

    assert channels.get(created["id"]) == original
    assert channels.configuration(created["id"])["secret"] == "old-secret"


def test_new_channel_and_delete_roll_back_when_index_save_fails(tmp_path):
    keyring = MemoryKeyring()
    store = Store(tmp_path)
    channels = DeliveryChannelStore(store, keyring_backend=keyring)
    created = channels.put(
        DeliveryChannelPut(
            name="保留渠道",
            kind="webhook",
            endpoint="https://notify.example.test/research",
            secret="keep-secret",
        )
    )

    def fail_save():
        raise OSError("disk unavailable")

    store.save = fail_save
    with pytest.raises(OSError, match="disk unavailable"):
        channels.put(
            DeliveryChannelPut(
                name="新渠道",
                kind="webhook",
                endpoint="https://notify.example.test/new",
                secret="new-secret",
            )
        )
    assert list(store.data["delivery_channels"]) == [created["id"]]
    assert all("new-secret" not in value for value in keyring.values.values())

    with pytest.raises(OSError, match="disk unavailable"):
        channels.delete(created["id"])
    assert channels.get(created["id"])["name"] == "保留渠道"
    assert channels.configuration(created["id"])["secret"] == "keep-secret"
