"""Native proposals cannot arm schedules; explicit confirmation is replay-safe."""

from types import SimpleNamespace

import pytest

from app.research_web.automation.drafts import AutomationDrafts
from app.research_web.automation.models import AutomationCreate
from app.research_web.automation.service import AutomationService
from app.research_web.store import Store, StoreError


def setup(tmp_path):
    store = Store(tmp_path)
    service = SimpleNamespace(store=store)
    service.automations = AutomationService(
        store, target_resolver=lambda *args: {"version": args[2], "sha256": "a" * 64}
    )
    sid = store.create("claw", "计划研究")["id"]
    body = AutomationCreate(
        name="每日研究",
        target_kind="skill",
        target_id="company-research",
        target_version=1,
        input_template="研究目标",
        schedule={"kind": "daily", "timezone": "Asia/Shanghai", "hour": 9, "minute": 0},
    )
    return store, AutomationDrafts(service), sid, body


def test_prepare_never_creates_or_enables_and_confirmation_is_idempotent(tmp_path):
    store, drafts, sid, body = setup(tmp_path)
    draft = drafts.prepare(sid, body)
    assert store.data["automations"] == {}
    result = drafts.confirm(sid, draft["id"], AutomationCreate.model_validate(draft["body"]))
    assert result["enabled"] is False
    assert (
        drafts.confirm(sid, draft["id"], AutomationCreate.model_validate(draft["body"]))["id"]
        == result["id"]
    )
    assert len(store.data["automations"]) == 1
    assert drafts.list(sid)["items"][0]["status"] == "confirmed"


def test_cancel_and_cross_session_confirmation_are_rejected(tmp_path):
    store, drafts, sid, body = setup(tmp_path)
    draft = drafts.prepare(sid, body)
    other = store.create("claw", "另一会话")["id"]
    with pytest.raises(StoreError):
        drafts.confirm(other, draft["id"], body)
    drafts.dismiss(sid, draft["id"])
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body)
    assert store.data["automations"] == {}


def test_confirmed_draft_never_resurrects_a_deleted_automation(tmp_path):
    store, drafts, sid, body = setup(tmp_path)
    draft = drafts.prepare(sid, body)
    locked = AutomationCreate.model_validate(draft["body"])
    saved = drafts.confirm(sid, draft["id"], locked)
    drafts.research.automations.delete(saved["id"])
    with pytest.raises(StoreError, match="删除"):
        drafts.confirm(sid, draft["id"], locked)
    assert store.data["automations"] == {}


def test_stale_target_fails_and_interrupted_confirmation_does_not_duplicate(tmp_path, monkeypatch):
    store, drafts, sid, body = setup(tmp_path)
    draft = drafts.prepare(sid, body)
    locked = AutomationCreate.model_validate(draft["body"])
    drafts.research.automations.target_resolver = lambda *args: {"version": 1, "sha256": "b" * 64}
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], locked)
    drafts.research.automations.target_resolver = lambda *args: {"version": 1, "sha256": "a" * 64}
    save = store.save
    counter = 0

    def crash():
        nonlocal counter
        counter += 1
        if counter == 2:
            raise StoreError("confirmation checkpoint failed")
        save()

    monkeypatch.setattr(store, "save", crash)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], locked)
    monkeypatch.setattr(store, "save", save)
    reloaded = Store(store.root)
    drafts.research.store = reloaded
    drafts.research.automations.store = reloaded
    recovered = AutomationDrafts(drafts.research)
    result = recovered.confirm(sid, draft["id"], locked)
    assert len(reloaded.data["automations"]) == 1
    assert result["enabled"] is False
