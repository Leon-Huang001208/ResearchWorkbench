"""Offline real-contract discovery, ownership, immutable evidence and admission tests."""

import asyncio
import copy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.research_web.client import RuntimeFailure
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.discovery import DiscoveryError, DiscoveryService, Prepare
from app.research_web.store import Store, StoreError

EVENT = {
    "id": "event_one",
    "title": "真实来源中的测试事件",
    "revision": 2,
    "updated_at": 1792742307,
    "first_public_at": 1792654810,
    "last_change": "新增进展",
    "groups": ["technology"],
    "priority_reason": "已有判断而非本机核验",
    "extraction": {"new_facts": ["待核实事实"], "pending": ["等待官方披露"]},
    "verification": {"status": "待核实", "blockers": ["缺少反证"], "closed_loop": False},
}
ARTICLE = {
    "id": "article_one",
    "title": "原始报道",
    "source": "公开发布者",
    "url": "https://example.com/article",
    "content": "真实归档正文。",
    "published_at": None,
}


class Client:
    def __init__(self):
        self.native = {}
        self.calls = []
        self.lose_create = None
        self.history_rows = []

    async def rpc(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == "session.list":
            return {"items": list(self.native.values())}
        if method == "session.create":
            if self.lose_create != "absent":
                self.native[params["sessionId"]] = {
                    "sessionId": params["sessionId"],
                    "cwd": params["cwd"],
                }
            if self.lose_create:
                raise RuntimeFailure("reply lost", "fixture_reply_lost")
        return {}

    async def history(self, sid):
        return self.history_rows


class Research:
    def __init__(self, path):
        self.store = Store(path)
        self.lock = asyncio.Lock()
        self.client = Client()
        self.datahub = SimpleNamespace(snapshots=Snapshots(self.store))
        self.default_model = {"provider": "deepseek-official", "model": "deepseek-chat"}
        self.send_calls = []
        self.lose_send = False

    async def ensure_owned(self):
        return None

    def model_profile_identity(self, provider):
        return "profile-fixture"

    def assert_session_model_profile(self, row):
        assert row["model_profile_id"] == "profile-fixture"

    def notify(self):
        return None

    async def send(self, sid, text, key, **kwargs):
        self.send_calls.append((sid, text, key, kwargs))
        self.store.data["receipts"][f"{sid}:{key}"] = {
            "status": "unknown" if self.lose_send else "accepted"
        }
        self.store.save()
        if self.lose_send:
            raise RuntimeFailure("prompt reply lost")
        return {"accepted": True}


@pytest.fixture
def setup(tmp_path):
    research = Research(tmp_path / "user")
    state = {
        "failed": False,
        "event": copy.deepcopy(EVENT),
        "reading": None,
        "calls": [],
        "articles": [copy.deepcopy(ARTICLE)],
        "retrieved_at": None,
    }

    async def reader(path, params=None):
        state["calls"].append((path, params))
        if state["failed"]:
            raise HTTPException(504, detail={"code": "intel_upstream_timeout"})
        if path == "/radar":
            return {"industries": [], "stats": {}}
        if path == "/intelligence":
            return {
                "as_of": None,
                "cache_stale": True,
                "logics": [{"id": "technology", "name": "科技"}],
                "reading": (
                    [copy.deepcopy(state["event"])]
                    if state["reading"] is None
                    else state["reading"]
                ),
                "daily_reading": {"analysis_error": "ValueError"},
            }
        return {
            "event": copy.deepcopy(state["event"]),
            "articles": copy.deepcopy(state["articles"]),
            "revisions": [],
            "retrieved_at": state["retrieved_at"],
        }

    return research, DiscoveryService(research, reader=reader), state


async def request(service, **overrides):
    feed = await service.feed()
    item = feed["themes"][0]
    return Prepare(
        request_id=str(uuid4()),
        feed_id=feed["feed_id"],
        horizon="medium",
        theme_id=item["id"],
        material_ids=[item["materials"][0]["id"]],
        target_mode="fingpt",
        question="请核实事件、传导与反证。",
        **overrides,
    )


@pytest.mark.asyncio
async def test_feed_real_fields_cache_stale_unknown_dates_and_no_model(setup):
    research, service, state = setup
    before = copy.deepcopy(research.store.data)
    feed = await service.feed()
    assert feed["source"] == "golddata_intel" and feed["stale"] is True
    assert feed["source_as_of"] is None
    assert feed["themes"][0]["chain"] == [] and feed["themes"][0]["counter"] == []
    assert feed["themes"][0]["next"] == "等待官方披露"
    assert feed["themes"][0]["materials"][0]["kind"] == "事件归档资料包"
    assert feed["errors"][0]["code"] == "upstream_judgment_unverified"
    assert await service.feed() == feed and len(state["calls"]) == 2
    assert (
        research.store.data == before and research.client.calls == [] and research.send_calls == []
    )
    assert not research.store.index.exists()


@pytest.mark.asyncio
async def test_empty_and_failed_source_never_become_mock_evidence(setup):
    research, service, state = setup
    state["reading"] = []
    assert (await service.feed())["state"] == "empty"
    state["failed"] = True
    fallback = await service.feed(refresh=True)
    assert fallback["state"] == "stale" and fallback["themes"] == []
    other = DiscoveryService(research, reader=service.reader)
    with pytest.raises(DiscoveryError, match="来源暂不可用"):
        await other.feed()
    assert not research.store.data.get("discovery_handoffs")


@pytest.mark.asyncio
async def test_selective_frozen_provenance_and_trusted_context(setup):
    research, service, state = setup
    body = await request(service)
    ready = await service.prepare(body)
    assert ready["state"] == "snapshot_ready" and ready["execution_started"] is False
    assert research.send_calls == []
    assert state["calls"][-1][0] == "/intelligence/events/event_one"
    sid = ready["session_id"]
    session = research.store.session(sid)
    assert (
        session["purpose"] == "discovery_research"
        and "hot_origin" not in session
        and "web_evidence" not in session
    )
    snapshot = research.datahub.snapshots.detail(sid, ready["dataset_id"])
    assert snapshot["source"] == "golddata_intel" and snapshot["source_stale"] is True
    assert (
        snapshot["snapshot_kind"] == "discovery_evidence"
        and snapshot["pagination_complete"] is False
    )
    rows = json.loads(research.datahub.snapshots.read(sid, ready["dataset_id"], "rows.json"))
    assert rows[0]["detail"]["articles"][0] == ARTICLE
    assert ready["materials"][1]["published_at"] is None
    assert "未独立抓取" in ready["materials"][1]["note"]
    context = service.trusted_context(sid)
    assert (
        context["cutoff"] == ready["cutoff"]
        and context["dataset_manifest_sha256"] == snapshot["manifest_sha256"]
    )
    # Ordinary session upgrades preserve the evidence, without acquiring the old handoff authority.
    target = research.store.create("fingpt", "升级研究")
    copied = research.datahub.snapshots.copy_selected(sid, target["id"], [ready["dataset_id"]])
    assert copied[0]["origin_dataset_id"] == ready["dataset_id"]
    assert service.trusted_context(target["id"]) is None


@pytest.mark.asyncio
async def test_changed_preview_selection_and_foreign_material_rejected_before_native(setup):
    research, service, state = setup
    body = await request(service)
    foreign = body.model_copy(update={"material_ids": ["browser_fabricated"]})
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(foreign)
    assert error.value.code == "discovery_selection_invalid"
    state["event"]["revision"] += 1
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(body)
    assert error.value.code == "discovery_evidence_changed"
    assert research.client.calls == [] and research.store.data["sessions"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["market_chain", "counter_evidence", "invalidation"])
async def test_changed_display_semantics_without_metadata_revision_requires_new_confirmation(
    setup, field
):
    research, service, state = setup
    state["event"]["extraction"][field] = ["预览时已有判断"]
    body = await request(service)
    state["event"]["extraction"][field] = ["详情中已改变的判断"]
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(body)
    assert error.value.code == "discovery_evidence_changed"
    assert research.client.calls == [] and research.send_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rank", ["sixty_first", "removed"])
async def test_tracking_refreshes_approved_event_after_it_leaves_discovery_ranking(setup, rank):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state = setup
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    research.automations.executor = tracking.execute

    async def detail(sid):
        return {"status": "completed", "research_quality": {"status": "incomplete"}}

    research.detail = detail
    feed = await service.feed()
    saved = await tracking.save(
        {
            "request_id": str(uuid4()),
            "feed_id": feed["feed_id"],
            "horizon": "medium",
            "theme_id": EVENT["id"],
            "condition": "跟踪已批准事件变化",
            "frequency": "daily",
            "time": "09:00",
        }
    )
    state["event"]["extraction"]["market_chain"] = ["元数据未变但传导判断已改变"]
    state["reading"] = [{**copy.deepcopy(EVENT), "id": f"other_{i}"} for i in range(60)]
    if rank == "sixty_first":
        state["reading"].append(copy.deepcopy(state["event"]))
    assert EVENT["id"] not in [row["id"] for row in (await service.feed(refresh=True))["themes"]]
    state["calls"].clear()
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert len(research.send_calls) == 1
    assert not any(path == "/intelligence" for path, _ in state["calls"])
    assert sum(path == "/intelligence/events/event_one" for path, _ in state["calls"]) == 2
    assert tracking.list()["items"][0]["runs"][0]["execution_status"] == "completed"


@pytest.mark.asyncio
async def test_prepared_request_public_projection_survives_host_rebuild_without_new_identity(setup):
    research, service, _ = setup
    research.client.lose_create = "present"
    body = await request(service)
    first = await service.prepare(body)
    rebuilt = DiscoveryService(research, reader=service.reader)
    recovered = await rebuilt.get_handoff(first["handoff_id"])
    assert recovered["prepare_request"] == body.model_dump(mode="json")
    assert recovered["state"] == "session_configuration_required"
    assert recovered["session_id"] == first["session_id"]
    assert recovered["context_sha256"] == first["context_sha256"]
    assert await rebuilt.prepare(Prepare.model_validate(recovered["prepare_request"]))
    assert sum(method == "session.create" for method, _ in research.client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["priority_reason", "verification", "structure_missing"])
async def test_display_priority_verification_or_missing_structure_cannot_change_under_preview(
    setup, field
):
    research, service, state = setup
    body = await request(service)
    if field == "priority_reason":
        state["event"][field] = "反向优先级理由"
    elif field == "verification":
        state["event"][field]["progression"] = {"next_action": "改变的下一验证点"}
    else:
        state["event"].pop("verification")
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(body)
    assert error.value.code == "discovery_evidence_changed"
    assert research.client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["new_article", "content", "original_content", "source", "published_at"]
)
async def test_tracking_observes_archived_article_changes_without_new_event_metadata(setup, change):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state = setup
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    research.automations.executor = tracking.execute

    async def detail(sid):
        return {"status": "completed", "research_quality": {"status": "incomplete"}}

    research.detail = detail
    feed = await service.feed()
    saved = await tracking.save(
        {
            "request_id": str(uuid4()),
            "feed_id": feed["feed_id"],
            "horizon": "medium",
            "theme_id": EVENT["id"],
            "condition": "跟踪已批准来源归档变化",
            "frequency": "daily",
            "time": "09:00",
        }
    )
    # A refresh's acquisition clock cannot convert the new baseline shape into paid research.
    state["retrieved_at"] = "2026-10-23T10:00:00+08:00"
    state["articles"][0]["acquired_at"] = "2026-10-23T10:00:00+08:00"
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert research.send_calls == []
    assert tracking.list()["items"][0]["runs"][0]["execution_status"] == "skipped_unchanged"
    if change == "new_article":
        state["articles"].append(
            {**copy.deepcopy(ARTICLE), "id": "article_two", "content": "新增归档报道"}
        )
    else:
        state["articles"][0][change] = (
            "2026-10-23T09:00:00+08:00" if change == "published_at" else "真实归档的新字段值"
        )
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert len(research.send_calls) == 1


@pytest.mark.asyncio
async def test_tracking_baseline_and_second_freeze_reject_semantic_drift(setup):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state = setup
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    feed = await service.feed()
    state["event"]["extraction"]["counter_evidence"] = ["预览后新增反证"]
    with pytest.raises(StoreError) as error:
        await tracking.save(
            {
                "request_id": str(uuid4()),
                "feed_id": feed["feed_id"],
                "horizon": "medium",
                "theme_id": EVENT["id"],
                "condition": "不得静默替换判断",
                "frequency": "daily",
                "time": "09:00",
            }
        )
    assert error.value.code == "discovery_evidence_changed"
    assert not research.store.data.get("discovery_tracks") and research.send_calls == []
    # The same closed event source may refresh off-ranking, but not switch IDs or URLs.
    with pytest.raises(DiscoveryError):
        await service.refresh_theme("medium", EVENT["id"], ["http://127.0.0.1/private"])
    refreshed = await service.refresh_theme("medium", EVENT["id"], [EVENT["id"]])
    event = refreshed["themes"][0]
    state["articles"][0]["content"] = "刷新后又变化的归档证据"
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(
            Prepare(
                request_id=str(uuid4()),
                feed_id=refreshed["feed_id"],
                horizon="medium",
                theme_id=event["id"],
                material_ids=[event["materials"][0]["id"]],
                question="冻结同一版本",
            )
        )
    assert error.value.code == "discovery_evidence_changed" and research.client.calls == []


@pytest.mark.asyncio
async def test_private_tracking_refresh_does_not_replace_home_feed_or_invent_old_prepare_request(
    setup,
):
    research, service, _ = setup
    home = await service.feed()
    refreshed = await service.refresh_theme("medium", EVENT["id"], [EVENT["id"]])
    assert refreshed["feed_id"] != home["feed_id"]
    assert (await service.feed())["feed_id"] == home["feed_id"]
    prepared = await service.prepare(await request(service))
    record = service._record(prepared["handoff_id"])
    record.pop("prepare_request")
    recovered = await service.get_handoff(prepared["handoff_id"])
    assert "prepare_request" not in recovered
    assert recovered["session_id"] == prepared["session_id"]
    assert sum(method == "session.create" for method, _ in research.client.calls) == 1


@pytest.mark.asyncio
async def test_public_prepare_request_must_match_its_original_host_hash(setup):
    _, service, _ = setup
    prepared = await service.prepare(await request(service))
    service._record(prepared["handoff_id"])["prepare_request"][
        "question"
    ] = "未经原请求确认的另一问题"
    with pytest.raises(DiscoveryError) as error:
        await service.get_handoff(prepared["handoff_id"])
    assert error.value.code == "discovery_request_conflict"


@pytest.mark.asyncio
async def test_compact_feed_requires_read_only_full_selection_before_manual_prepare(setup):
    research, service, state = setup
    state["event"]["extraction"]["market_chain"] = ["详情归档中的完整传导判断"]
    compact = copy.deepcopy(state["event"])
    compact.pop("extraction")
    compact.pop("verification")
    compact.pop("priority_reason")
    state["reading"] = [compact]
    feed = await service.feed()
    before = copy.deepcopy(research.store.data)
    selected = await service.selection_preview(feed["feed_id"], EVENT["id"], "medium")
    assert selected["feed_id"] != feed["feed_id"] and selected["horizon"] == "medium"
    current = selected["themes"][0]
    assert current["chain"][0]["title"] == "详情归档中的完整传导判断"
    assert current["materials"][0]["evidence_sha256"]
    cached = service.cached_preview(selected["feed_id"], "medium")
    assert cached == selected
    cached["themes"][0]["title"] = "浏览器不能修改Host预览"
    assert (
        service.cached_preview(selected["feed_id"], "medium")["themes"][0]["title"]
        == current["title"]
    )
    assert (await service.feed())["feed_id"] == feed["feed_id"]
    assert (
        research.store.data == before and research.send_calls == [] and research.client.calls == []
    )
    assert not research.store.index.exists()
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    saved = await tracking.save(
        {
            "request_id": str(uuid4()),
            "feed_id": selected["feed_id"],
            "horizon": "medium",
            "theme_id": EVENT["id"],
            "condition": "确认完整预览后保存跟踪草稿",
            "frequency": "daily",
            "time": "09:00",
        }
    )
    assert saved["enabled"] is False
    assert research.send_calls == [] and research.client.calls == []
    prepared = await service.prepare(
        Prepare(
            request_id=str(uuid4()),
            feed_id=selected["feed_id"],
            horizon="medium",
            theme_id=EVENT["id"],
            material_ids=[current["materials"][0]["id"]],
            question="核对当前详情预览后开始冻结",
        )
    )
    assert prepared["state"] == "snapshot_ready"
    assert research.send_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", ["expired", "foreign_feed", "wrong_theme", "wrong_horizon", "arbitrary_url"]
)
async def test_selection_preview_never_fetches_unapproved_or_expired_feed_scope(setup, invalid):
    from app.research_web.discovery.service import FEED_RETENTION_SECONDS

    research, service, state = setup
    feed = await service.feed()
    feed_id, theme_id, horizon = feed["feed_id"], EVENT["id"], "medium"
    if invalid == "expired":
        service._feeds[feed_id]["time"] -= FEED_RETENTION_SECONDS + 1
    elif invalid == "foreign_feed":
        feed_id = str(uuid4())
    elif invalid == "wrong_theme":
        theme_id = "not_approved"
    elif invalid == "wrong_horizon":
        horizon = "short"
    else:
        theme_id = "http://127.0.0.1/private"
    state["calls"].clear()
    with pytest.raises(DiscoveryError) as error:
        await service.selection_preview(feed_id, theme_id, horizon)
    assert error.value.code in {"discovery_feed_expired", "discovery_selection_invalid"}
    assert state["calls"] == [] and research.client.calls == [] and research.send_calls == []
    assert research.store.data["sessions"] == {}


@pytest.mark.asyncio
async def test_duplicate_prepare_uses_same_identity_and_different_body_conflicts(setup):
    research, service, state = setup
    body = await request(service)
    first = await service.prepare(body)
    assert await service.prepare(body) == first
    with pytest.raises(DiscoveryError) as error:
        await service.prepare(body.model_copy(update={"question": "另一问题"}))
    assert error.value.code == "discovery_request_conflict"
    assert len([method for method, _ in research.client.calls if method == "session.create"]) == 1
    assert len([path for path, _ in state["calls"] if "/events/" in path]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("lost", ["absent", "present"])
async def test_lost_creation_receipt_never_recreates_and_get_only_observes(setup, lost):
    research, service, _ = setup
    research.client.lose_create = lost
    prepared = await service.prepare(await request(service))
    assert prepared["state"] == "session_outcome_unknown"
    before = len(research.client.calls)
    result = await service.get_handoff(prepared["handoff_id"])
    assert result["state"] == (
        "session_outcome_unknown" if lost == "absent" else "session_configuration_required"
    )
    assert [method for method, _ in research.client.calls[before:]] == ["session.list"]
    await service.execute(prepared["handoff_id"], str(uuid4()))
    assert len([method for method, _ in research.client.calls if method == "session.create"]) == 1
    assert len(research.send_calls) == (0 if lost == "absent" else 1)


@pytest.mark.asyncio
async def test_foreign_native_cwd_and_mutated_context_fail_closed(setup):
    research, service, _ = setup
    research.client.lose_create = "present"
    prepared = await service.prepare(await request(service))
    research.client.native[prepared["session_id"]]["cwd"] = "/somewhere/else"
    with pytest.raises(DiscoveryError) as error:
        await service.get_handoff(prepared["handoff_id"])
    assert error.value.code == "discovery_session_foreign"
    path = research.store.directory(prepared["session_id"]) / "inputs/discovery-context.json"
    path.write_text("{}")
    with pytest.raises(DiscoveryError) as error:
        service.trusted_context(prepared["session_id"])
    assert error.value.code == "discovery_context_changed"
    assert research.send_calls == []


@pytest.mark.asyncio
async def test_snapshot_material_bytes_altered_rejected(setup):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    path = (
        research.store.directory(prepared["session_id"])
        / "inputs/datasets"
        / prepared["dataset_id"]
        / "rows.json"
    )
    path.write_text("[]")
    with pytest.raises(DiscoveryError):
        await service.execute(prepared["handoff_id"], str(uuid4()))
    assert research.send_calls == []


@pytest.mark.asyncio
async def test_execute_at_most_once_with_new_request_and_lost_admission(setup):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    research.lose_send = True
    first = await service.execute(prepared["handoff_id"], str(uuid4()))
    assert first["state"] == "execution_outcome_unknown" and first["execution_started"] is None
    second = await service.execute(prepared["handoff_id"], str(uuid4()))
    assert second["state"] == "execution_outcome_unknown" and len(research.send_calls) == 1
    assert "不要自行开启跟踪" in research.send_calls[0][1]
    assert research.send_calls[0][2].startswith("discovery:")
    sid, _, key, _ = research.send_calls[0]
    research.store.data["receipts"][f"{sid}:{key}"]["status"] = "accepted"
    assert (await service.get_handoff(prepared["handoff_id"]))["state"] == "running"


@pytest.mark.asyncio
async def test_store_failure_before_native_and_request_limits(setup, monkeypatch):
    research, service, _ = setup
    body = await request(service)

    def fail():
        raise StoreError("fixture persistence failure")

    monkeypatch.setattr(research.store, "save", fail)
    with pytest.raises(StoreError):
        await service.prepare(body)
    assert research.client.calls == [] and service._table() == {}
    assert "discovery_handoffs" not in research.store.data
    with pytest.raises(ValidationError):
        Prepare.model_validate({**body.model_dump(), "arbitrary_url": "http://private"})
    with pytest.raises(ValidationError):
        Prepare.model_validate({**body.model_dump(), "material_ids": ["same", "same"]})
    with pytest.raises(ValidationError):
        Prepare.model_validate({**body.model_dump(), "question": " "})


@pytest.mark.asyncio
async def test_restart_unknown_receipt_and_cross_user_identity_fail_closed(setup, tmp_path):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    research.lose_send = True
    await service.execute(prepared["handoff_id"], str(uuid4()))
    research.store = Store(research.store.root)
    research.datahub = SimpleNamespace(snapshots=Snapshots(research.store))
    restarted = DiscoveryService(research, reader=service.reader)
    await restarted.execute(prepared["handoff_id"], str(uuid4()))
    assert len(research.send_calls) == 1
    other = DiscoveryService(Research(tmp_path / "other-user"), reader=service.reader)
    with pytest.raises(DiscoveryError) as error:
        await other.get_handoff(prepared["handoff_id"])
    assert error.value.code == "discovery_handoff_not_found"


@pytest.mark.asyncio
async def test_raw_archive_tamper_rejected_and_missing_table_preserved(setup):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    path = (
        research.store.root
        / ".control/snapshots"
        / prepared["session_id"]
        / prepared["dataset_id"]
        / "raw-0001.bin"
    )
    path.write_bytes(b"{}")
    with pytest.raises(DiscoveryError):
        service.trusted_context(prepared["session_id"])
    assert research.send_calls == []


@pytest.mark.asyncio
async def test_execution_reservation_save_failure_rolls_back_before_send(setup, monkeypatch):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    original = research.store.save

    def fail_before_send():
        if service._record(prepared["handoff_id"])["state"] == "execution_starting":
            raise StoreError("fixture reservation save failed")
        original()

    monkeypatch.setattr(research.store, "save", fail_before_send)
    with pytest.raises(StoreError):
        await service.execute(prepared["handoff_id"], str(uuid4()))
    assert service._record(prepared["handoff_id"])["state"] == "snapshot_ready"
    assert research.send_calls == []


@pytest.mark.asyncio
async def test_execute_passes_only_host_bound_approved_tools(setup):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    research.store.session(prepared["session_id"])["automation_research_scope"] = {
        "approved_tools": ["datahub_query"]
    }
    await service.execute(prepared["handoff_id"], str(uuid4()))
    assert research.send_calls[0][3] == {"formats": ["md"], "tool_ids": ["datahub_query"]}


@pytest.mark.asyncio
async def test_read_only_native_list_outage_recovers_existing_ready_identity(setup, monkeypatch):
    research, service, _ = setup
    prepared = await service.prepare(await request(service))
    original = research.client.rpc

    async def unavailable(method, params):
        raise RuntimeFailure("fixture list timeout")

    monkeypatch.setattr(research.client, "rpc", unavailable)
    assert (await service.get_handoff(prepared["handoff_id"]))["state"] == "session_outcome_unknown"
    monkeypatch.setattr(research.client, "rpc", original)
    recovered = await service.get_handoff(prepared["handoff_id"])
    assert recovered["state"] == "snapshot_ready" and "code" not in recovered
    assert len([method for method, _ in research.client.calls if method == "session.create"]) == 1


@pytest.fixture
def news_setup(setup):
    research, old, legacy = setup
    raw = {
        "title": "最新原始资讯",
        "url": "https://example.com/raw",
        "source": "原始发布者",
        "ts": 1792840000,
        "time": "刚刚",
        "summary": "来源摘要",
        "raw_content": "来源归档正文",
    }
    state = {"raw": raw, "gone": False, "news_failed": False, "events_failed": False, "calls": []}

    async def reader(path, params=None):
        state["calls"].append((path, params))
        if path == "/radar":
            if state["news_failed"]:
                raise HTTPException(504, detail={"code": "fixture_unavailable"})
            return {
                "industries": [
                    {
                        "name": "科技",
                        "items": [] if state["gone"] else [copy.deepcopy(state["raw"])],
                    }
                ],
                "stats": {"failed_sources": 2},
                **state.get("metadata", {}),
            }
        if path == "/intelligence" and state["events_failed"]:
            raise HTTPException(504, detail={"code": "fixture_unavailable"})
        return await old.reader(path, params)

    return research, DiscoveryService(research, reader=reader), state, legacy


@pytest.mark.asyncio
async def test_news_freshness_lanes_refresh_and_zero_writes(news_setup):
    research, service, state, _legacy = news_setup
    before = copy.deepcopy(research.store.data)
    feed = await service.feed()
    assert feed["news"][0]["source_kind"] == "news"
    assert feed["news"][0]["state"] == "未形成研判"
    assert feed["freshness"]["news"]["status"] == "ready"
    assert feed["freshness"]["events"]["cache_status"] == "expired"
    assert feed["news"][0]["judgment_as_of"] is None
    assert "event_id" not in feed["news"][0]["materials"][0]
    assert await service.feed() == feed
    state["raw"]["title"] = "新事实"
    refreshed = await service.feed(refresh=True)
    assert refreshed["news"][0]["title"] == "新事实"
    assert refreshed["news"][0]["id"] == feed["news"][0]["id"]
    assert (
        refreshed["news"][0]["materials"][0]["content_sha256"]
        != feed["news"][0]["materials"][0]["content_sha256"]
    )
    assert research.store.data == before and not research.client.calls and not research.send_calls
    assert not research.store.index.exists()


@pytest.mark.asyncio
async def test_news_and_events_fail_independently_without_freshening_old_bytes(news_setup):
    _, service, state, _ = news_setup
    first = await service.feed()
    state["events_failed"] = True
    state["raw"]["title"] = "事件汇总失败时仍有新稿"
    second = await service.feed(refresh=True)
    assert second["news"][0]["title"] == "事件汇总失败时仍有新稿"
    assert second["freshness"]["events"]["status"] == "unavailable"
    assert second["freshness"]["news"]["status"] == "ready"
    state["news_failed"] = True
    state["events_failed"] = False
    third = await service.feed(refresh=True)
    assert third["news"] == second["news"]
    assert third["freshness"]["news"]["status"] == "unavailable"
    assert third["freshness"]["news"]["retrieved_at"] == second["freshness"]["news"]["retrieved_at"]
    assert third["freshness"]["news"]["last_attempt_at"] != first["retrieved_at"]


@pytest.mark.asyncio
async def test_news_selection_freeze_raw_tamper_and_exact_association(news_setup):
    research, service, state, legacy = news_setup
    feed = await service.feed()
    news = feed["news"][0]
    preview = await service.selection_preview(feed["feed_id"], news["id"], "medium")
    assert not research.store.index.exists() and not research.client.calls
    body = Prepare(
        request_id=str(uuid4()),
        feed_id=preview["feed_id"],
        horizon="medium",
        theme_id=news["id"],
        material_ids=[preview["themes"][0]["materials"][0]["id"]],
        target_mode="claw",
        question="核验原始资讯",
    )
    state["raw"]["raw_content"] = "正文变化，即使标题没变也拒绝"
    with pytest.raises(DiscoveryError, match="变化"):
        await service.prepare(body)
    assert not research.store.data.get("sessions")
    state["raw"]["raw_content"] = "来源归档正文"
    legacy["articles"][0]["url"] = state["raw"]["url"]
    linked = await service.associate(feed["feed_id"], news["id"], EVENT["id"], "medium")
    assert linked["themes"][0]["related_events"][0]["event_id"] == EVENT["id"]
    linked_body = body.model_copy(
        update={
            "feed_id": linked["feed_id"],
            "material_ids": [linked["themes"][0]["materials"][0]["id"]],
        }
    )
    prepared = await service.prepare(linked_body)
    assert prepared["execution_started"] is False
    context = service.trusted_context(prepared["session_id"])
    assert context["materials"][0]["source_kind"] == "news"
    dataset = research.datahub.snapshots.detail(prepared["session_id"], prepared["dataset_id"])
    assert dataset["snapshot_kind"] == "discovery_evidence"
    assert not research.send_calls
    restarted = Research(research.store.root)
    cold = DiscoveryService(restarted, reader=service.reader)
    assert (
        cold.trusted_context(prepared["session_id"])["context_sha256"] == context["context_sha256"]
    )
    assert not restarted.client.calls and not restarted.send_calls
    legacy["articles"][0]["url"] = "https://example.com/different"
    with pytest.raises(DiscoveryError, match="关联"):
        await service.associate(feed["feed_id"], news["id"], EVENT["id"], "medium")


@pytest.mark.asyncio
async def test_news_stable_fingerprint_and_missing_observation(news_setup):
    _, service, state, _ = news_setup
    feed = await service.feed()
    news = feed["news"][0]
    first = await service.refresh_news("medium", news["id"])
    state["raw"]["time"] = "1分钟前"
    second = await service.refresh_news("medium", news["id"])
    assert (
        first["themes"][0]["materials"][0]["evidence_sha256"]
        == second["themes"][0]["materials"][0]["evidence_sha256"]
    )
    state["gone"] = True
    with pytest.raises(DiscoveryError, match="不可观察"):
        await service.refresh_news("medium", news["id"])


@pytest.mark.asyncio
async def test_raw_tracking_disabled_creation_and_cold_read_without_scheduler(news_setup):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state, _ = news_setup
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    feed = await service.feed()
    identifier = feed["news"][0]["id"]
    preview = await service.selection_preview(feed["feed_id"], identifier, "medium")
    body = {
        "request_id": str(uuid4()),
        "feed_id": preview["feed_id"],
        "horizon": "medium",
        "theme_id": identifier,
        "condition": "仅核对本条归档及已核验关联事件；不扩展来源范围",
        "frequency": "daily",
        "time": "08:30",
    }
    saved = await tracking.save(body)
    assert not saved["enabled"]
    row, automation = tracking._owned(saved["id"])
    assert row["approved_news_ids"] == [identifier] and row["approved_event_ids"] == []
    assert row["schema"] == "discovery-tracking-v1"
    resumed = DiscoveryTracking(research, service)
    assert resumed.eligible(automation) and not resumed.has_enabled()
    assert not research.client.calls and not research.send_calls
    row["approved_event_ids"] = ["unapproved-event"]
    assert not resumed.eligible(automation)
    row["approved_event_ids"] = []
    assert resumed.eligible(automation)
    state["gone"] = True
    with pytest.raises(DiscoveryError, match="不可观察"):
        await service.refresh_news("medium", identifier)
    assert not research.send_calls and not resumed._owned(saved["id"])[1]["enabled"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing_url", "unknown_time", "conflict"])
async def test_news_unknown_identity_time_and_conflicting_versions_fail_honestly(
    news_setup, change
):
    research, service, state, _ = news_setup
    if change == "missing_url":
        state["raw"]["url"] = "javascript:unsafe"
    elif change == "unknown_time":
        state["raw"]["ts"] = "10-24 10:00"
    else:
        original = service.reader

        async def conflicting(path, params=None):
            value = await original(path, params)
            if path == "/radar":
                value["industries"][0]["items"].append(
                    {**state["raw"], "raw_content": "conflicting archive"}
                )
            return value

        service.reader = conflicting
    feed = await service.feed()
    item = feed["news"][0]
    if change == "unknown_time":
        assert item["published_at"] is None and item["materials"][0]["published_at"] is None
    else:
        assert item["actionable"] is False
        with pytest.raises(DiscoveryError):
            await service.selection_preview(feed["feed_id"], item["id"], "medium")
    assert not research.client.calls and not research.store.data.get("discovery_handoffs")


@pytest.mark.asyncio
async def test_news_association_rejects_foreign_scopes_and_keeps_multiple_verified_links(
    news_setup,
):
    _, service, state, legacy = news_setup
    second = {**copy.deepcopy(EVENT), "id": "event_two", "title": "独立事件记录"}
    legacy["reading"] = [copy.deepcopy(EVENT), second]
    legacy["articles"][0]["url"] = state["raw"]["url"]
    original = service.reader

    async def reader(path, params=None):
        if path == "/intelligence/events/event_two":
            return {"event": second, "articles": copy.deepcopy(legacy["articles"])}
        return await original(path, params)

    service.reader = reader
    feed = await service.feed()
    identifier = feed["news"][0]["id"]
    with pytest.raises(DiscoveryError):
        await service.associate(str(uuid4()), identifier, EVENT["id"], "medium")
    with pytest.raises(DiscoveryError):
        await service.associate(feed["feed_id"], identifier, "unselected", "medium")
    await service.associate(feed["feed_id"], identifier, EVENT["id"], "medium")
    linked = await service.associate(feed["feed_id"], identifier, "event_two", "medium")
    assert {x["event_id"] for x in linked["themes"][0]["related_events"]} == {
        EVENT["id"],
        "event_two",
    }
    assert all(x["judgment_as_of"] is None for x in linked["themes"][0]["related_events"])


def test_legacy_context_bytes_have_the_original_exact_contract():
    from app.research_web.datahub.security import json_bytes
    from app.research_web.discovery.handoff import context_bytes
    from app.research_web.discovery.sources import SOURCE_POLICY

    record = {
        key: "fixture-" + key
        for key in [
            "handoff_id",
            "session_id",
            "target_mode",
            "dataset_id",
            "dataset_manifest_sha256",
            "selection_sha256",
            "cutoff",
            "retrieved_at",
            "question",
            "horizon",
        ]
    }
    record["materials"] = [{"event_id": "unchanged"}]
    import hashlib

    assert (
        hashlib.sha256(SOURCE_POLICY.encode()).hexdigest()
        == "3ba4e0ace445c59c0120eec34891747629085c25fe6832f7f71490ea5c9162ff"
    )
    expected = {"schema_version": "discovery-handoff-1", **record, "source_policy": SOURCE_POLICY}
    assert context_bytes(record) == json_bytes(expected)
    assert "source_kind" not in json.loads(context_bytes(record))


@pytest.mark.asyncio
async def test_explicit_raw_cache_expiry_propagates_without_creating_novelty_or_tracking(
    news_setup,
):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state, _ = news_setup
    state["metadata"] = {
        "cache_stale": True,
        "as_of": 1792742307,
        "generated_at": "2026-10-24 12:00",
    }
    feed = await service.feed()
    assert feed["freshness"]["news"]["cache_status"] == "expired"
    assert feed["freshness"]["news"]["source_as_of"] is not None
    identifier = feed["news"][0]["id"]
    preview = await service.selection_preview(feed["feed_id"], identifier, "medium")
    assert preview["stale"] is True and preview["freshness"]["news"]["cache_status"] == "expired"
    first = preview["themes"][0]["materials"][0]["evidence_sha256"]
    state["metadata"]["as_of"] += 100
    newer = await service.refresh_news("medium", identifier)
    assert newer["themes"][0]["materials"][0]["evidence_sha256"] == first
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    with pytest.raises(StoreError, match="来源本次不可用"):
        await tracking.save(
            {
                "request_id": str(uuid4()),
                "feed_id": preview["feed_id"],
                "horizon": "medium",
                "theme_id": identifier,
                "condition": "核查原始资料",
                "frequency": "daily",
                "time": "08:30",
            }
        )
    assert not research.store.data.get("discovery_tracks") and not research.send_calls


@pytest.mark.asyncio
async def test_raw_tracking_unknown_admission_does_not_retry_after_cold_tracking(news_setup):
    from app.research_web.automation.service import AutomationService
    from app.research_web.discovery.tracking import DiscoveryTracking

    research, service, state, _ = news_setup
    research.automations = AutomationService(research.store, research=research, scheduler=False)
    tracking = DiscoveryTracking(research, service)
    research.automations.executor = tracking.execute

    async def detail(sid):
        return {
            "id": sid,
            "status": "disconnected",
            "files": [],
            "research_quality": {"status": "incomplete"},
        }

    research.detail = detail
    feed = await service.feed()
    identifier = feed["news"][0]["id"]
    preview = await service.selection_preview(feed["feed_id"], identifier, "medium")
    saved = await tracking.save(
        {
            "request_id": str(uuid4()),
            "feed_id": preview["feed_id"],
            "horizon": "medium",
            "theme_id": identifier,
            "condition": "核对批准原始归档",
            "frequency": "daily",
            "time": "08:30",
        }
    )
    assert not saved["enabled"]
    state["raw"]["raw_content"] = "新的来源正文"
    research.lose_send = True
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert tracking.list()["items"][0]["runs"][0]["execution_status"] == "interrupted"
    assert len(research.send_calls) == 1
    cold = DiscoveryTracking(research, service)
    assert cold.eligible(research.automations._row(saved["id"]))
    research.automations.executor = cold.execute
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert cold.list()["items"][0]["runs"][0]["execution_status"] == "skipped_unchanged"
    assert len(research.send_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("unattended", [False, True])
async def test_news_freeze_uses_current_observation_and_blocks_unattended_expiry(
    news_setup, unattended
):
    research, service, state, _ = news_setup
    state["metadata"] = {"cache_stale": False, "as_of": 1792742307}
    feed = await service.feed()
    item = feed["news"][0]
    preview = await service.selection_preview(feed["feed_id"], item["id"], "medium")
    state["metadata"] = {"cache_stale": True, "as_of": 1792742407}
    body = Prepare(
        request_id=str(uuid4()),
        feed_id=preview["feed_id"],
        horizon="medium",
        theme_id=item["id"],
        material_ids=[preview["themes"][0]["materials"][0]["id"]],
        target_mode="fingpt",
        question="核验当前冻结来源",
    )
    if unattended:
        with pytest.raises(DiscoveryError, match="缓存已过期"):
            await service.prepare(body, require_fresh=True)
        assert not research.store.data.get("sessions") and not research.store.data.get(
            "discovery_handoffs"
        )
        assert not research.client.calls
    else:
        prepared = await service.prepare(body)
        snapshot = research.datahub.snapshots.detail(prepared["session_id"], prepared["dataset_id"])
        assert snapshot["source_stale"] is True
        assert snapshot["discovery"]["source_states"]["news"]["cache_status"] == "expired"
        assert snapshot["source_as_of"] != preview["source_as_of"]
    assert not research.send_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["cache_stale", "as_of", "generated_at"])
async def test_news_association_transport_metadata_does_not_trigger_novelty(news_setup, field):
    from app.research_web.discovery import news

    _, service, state, legacy = news_setup
    legacy["articles"][0]["url"] = state["raw"]["url"]
    feed = await service.feed()
    identifier = feed["news"][0]["id"]
    detail = await service._read_news(identifier, [EVENT["id"]])
    original = news.fingerprint(detail)
    changed = copy.deepcopy(detail)
    changed["associations"][0]["detail"][field] = (
        True if field == "cache_stale" else "2026-10-24T12:00:00Z"
    )
    assert news.fingerprint(changed) == original
    for path, value in [
        (("articles", "content"), "新原文"),
        (("articles", "published_at"), "2026-10-24T12:00:00Z"),
        (("event", "judgment_as_of"), "2026-10-24T12:00:00Z"),
    ]:
        changed = copy.deepcopy(detail)
        archive = changed["associations"][0]["detail"]
        target = archive[path[0]][0] if path[0] == "articles" else archive[path[0]]
        target[path[1]] = value
        assert news.fingerprint(changed) != original
