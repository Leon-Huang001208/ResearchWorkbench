"""Research Bot contracts over the existing Automation/DSH chain."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.research_web.automation.models import AutomationSchedule
from app.research_web.automation.schedule import next_occurrence
from app.research_web.automation.service import AutomationService
from app.research_web.research_bot_models import BotConfiguration, BotSave
from app.research_web.research_bots import ResearchBots, select_materials
from app.research_web.store import Store, StoreError


def body(**updates):
    return BotSave.model_validate(
        {
            "name": "产业观察",
            "objective": "核实订单兑现",
            "keywords": ["光模块"],
            "model_provider": "deepseek-official",
            "model_id": "deepseek-flash",
            **updates,
        }
    )


def test_interval_is_strict_and_preserves_existing_schedules():
    value = AutomationSchedule(kind="interval", timezone="Asia/Shanghai", interval_minutes=30)
    now = datetime(2026, 11, 13, tzinfo=UTC)
    assert (next_occurrence(value, now) - now).total_seconds() == 1800
    for updates in ({"interval_minutes": 4}, {"interval_minutes": True}, {"hour": 9}):
        with pytest.raises(ValueError):
            AutomationSchedule.model_validate({**value.model_dump(), **updates})
    with pytest.raises(ValueError):
        AutomationSchedule(kind="daily", timezone="UTC", hour=9, minute=0, interval_minutes=30)


def test_bot_configuration_has_bounded_unique_scope():
    assert body().interval_minutes == 30
    for updates in (
        {"name": " "},
        {"keywords": ["a", "a"]},
        {"watchlist": ["x"] * 11},
        {"skills": [{"id": "x", "version": 1, "sha256": "a" * 64}] * 2},
        {"enabled": True},
        {"color": "red;display:none"},
        {"model_id": "provider/model"},
    ):
        with pytest.raises(ValueError):
            body(**updates)


def feed(text="光模块订单", proof="a"):
    return {
        "stale": False,
        "freshness": {"news": {"status": "ready", "cache_status": "not_expired"}},
        "news": [
            {
                "id": "n1",
                "title": text,
                "actionable": True,
                "published_at": "2026-11-13T00:00:00+00:00",
                "materials": [{"content_sha256": proof * 64}],
            }
        ],
    }


def test_source_selection_requires_freshness_and_ignores_unrelated_news():
    now = datetime(2026, 11, 13, 1, tzinfo=UTC)
    assert len(select_materials(feed(), body(), now)) == 1
    assert select_materials(feed("别的行业"), body(), now) == []
    assert select_materials(feed(), body(), datetime(2026, 11, 16, tzinfo=UTC)) == []
    assert select_materials({**feed(), "stale": True}, body(), now)  # unrelated events lane
    for bad in (
        {**feed(), "freshness": {"news": {"status": "unavailable"}}},
        {**feed(), "freshness": {}},
        {**feed(), "news": [{"id": "x", "title": "光模块"}]},
    ):
        with pytest.raises(StoreError):
            select_materials(bad, body(), now)


def setup(tmp_path):
    store = Store(tmp_path)
    research = SimpleNamespace(
        store=store,
        service_only=False,
        capabilities=SimpleNamespace(
            selection=lambda cid, version: {
                "id": cid,
                "version": version,
                "sha256": "a" * 64,
                "kind": "skill",
            }
        ),
    )
    research.automations = AutomationService(store, research=research, scheduler=False)
    return ResearchBots(research), research


def test_save_is_disabled_and_update_uses_same_identity_and_cas(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body(request_id="11111111-1111-4111-8111-111111111111"))
    assert not saved["enabled"] and saved["next_run_at"] is None
    assert bots.save(body(request_id="11111111-1111-4111-8111-111111111111"))["id"] == saved["id"]
    updated = bots.save(body(name="新名称", expected_version=1), saved["id"])
    assert updated["id"] == saved["id"] and updated["definition_version"] == 2
    assert len(research.automations.list(research_bot=True)["items"]) == 1
    research.automations.enable(saved["id"], expected_version=2, research_bot=True)
    updated = bots.save(body(expected_version=2), saved["id"])
    assert updated["enabled"] is False and updated["next_run_at"] is None
    with pytest.raises(StoreError):
        bots.save(body(expected_version=1), saved["id"])


def test_other_automations_and_other_accounts_cannot_be_accessed(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())
    other, _ = setup(tmp_path / "other")
    with pytest.raises(StoreError):
        other.get(saved["id"])
    research.store.data["automations"][saved["id"]]["research_task"].pop("bot")
    with pytest.raises(StoreError):
        bots.get(saved["id"])


def test_service_only_and_tenant_modes_stay_disabled(tmp_path, monkeypatch):
    bots, research = setup(tmp_path)
    research.service_only = True
    with pytest.raises(StoreError):
        bots.save(body())
    research.service_only = False
    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    with pytest.raises(StoreError):
        bots.list()


def test_skill_drift_rejected_before_saving(tmp_path):
    bots, research = setup(tmp_path)
    with pytest.raises(StoreError):
        bots.save(body(skills=[{"id": "skill", "version": 1, "sha256": "b" * 64}]))
    assert research.automations.list(research_bot=True)["items"] == []


@pytest.mark.asyncio
async def test_unchanged_skips_but_source_revision_runs_again(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())

    async def read(**_kwargs):
        return feed()

    research.discovery = SimpleNamespace(feed=read)
    research.automations.now = lambda: datetime(2026, 11, 13, 1, tzinfo=UTC)
    first = {"id": "r1", "trigger": "schedule"}
    await bots.prepare(saved, first)
    assert first["bot_materials"]
    research.store.data["automation_runs"]["r1"] = {
        **first,
        "automation_id": saved["id"],
        "definition_snapshot": saved,
        "research_status": "completed",
        "bot_result": {"headline": "已核验"},
        "updated_at": 1,
    }
    assert await bots.prepare(saved, {"id": "r2", "trigger": "schedule"}) is None
    assert await bots.prepare(saved, {"id": "r3", "trigger": "manual"}) is not None

    async def revised(**_kwargs):
        return feed(proof="b")

    research.discovery.feed = revised
    assert await bots.prepare(saved, {"id": "r4", "trigger": "schedule"}) is not None


def test_bot_config_roundtrip_is_strict():
    config = BotConfiguration.model_validate(
        body().model_dump(
            exclude={"request_id", "expected_version", "name", "model_provider", "model_id"}
        )
    )
    assert config.objective == "核实订单兑现"


def test_legacy_hash_input_has_no_new_null_fields():
    from app.research_web.automation.models import ResearchTaskDefinition

    task = {
        "schema_version": 1,
        "description": "研究",
        "model_provider": "deepseek-official",
        "model_id": "deepseek-flash",
        "output_requirements": "结论",
        "approved_data_sources": ["datahub"],
        "approved_tools": [],
    }
    assert ResearchTaskDefinition.model_validate(task).model_dump(mode="json") == task
    assert (
        "interval_minutes"
        not in AutomationSchedule(kind="daily", timezone="UTC", hour=9, minute=0).model_dump()
    )


@pytest.mark.asyncio
async def test_real_discovery_feed_contract_is_usable_without_events(tmp_path):
    from app.research_web.discovery.reading import build_feed

    async def reader(path, *_args):
        if path == "/intelligence":
            raise OSError("events unavailable")
        return {
            "cache_stale": False,
            "industries": [
                {
                    "items": [
                        {
                            "title": "光模块订单",
                            "url": "https://example.com/news",
                            "source": "test",
                            "ts": 1794528000,
                        }
                    ]
                }
            ],
        }

    value, _ = await build_feed(reader, None, "medium", "2026-11-13T00:00:00+00:00")
    assert value["freshness"]["news"]["status"] == "ready"
    assert select_materials(value, body(), datetime(2026, 11, 13, 1, tzinfo=UTC))


def test_tools_are_explicit_and_cannot_include_management(tmp_path):
    bots, _ = setup(tmp_path)
    saved = bots.save(body(approved_tools=["web_search"]))
    assert saved["research_task"]["approved_tools"] == ["web_search"]
    with pytest.raises(StoreError):
        bots.save(body(approved_tools=["rwb_prepare_automation"]))


@pytest.mark.asyncio
async def test_native_chain_validates_result_and_skips_without_second_submission(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())
    calls = []

    async def read(**_kwargs):
        return feed()

    async def create(*args, **kwargs):
        calls.append("create")
        return {"id": "native-1"}

    async def send(sid, prompt, key, **kwargs):
        calls.append("send")
        assert (
            research.store.data["automation_runs"][kwargs["_research_bot_run_id"]]["session_id"]
            == sid
        )
        assert "光模块" in prompt and kwargs["tool_ids"] == []
        return {"accepted": True}

    result = {
        "signal": "neutral",
        "headline": "待核实",
        "judgment": "观察" * 3000,
        "risks": ["证据不足"],
        "triggers": ["核实公告"],
        "sourceIds": ["n1"],
    }

    async def detail(_sid):
        return {
            "status": "completed",
            "messages": [{"role": "assistant", "text": json.dumps(result, ensure_ascii=False)}],
        }

    research.discovery = SimpleNamespace(feed=read)
    research.create_automation_research_session = create
    research.send, research.detail = send, detail
    research.automations.now = lambda: datetime(2026, 11, 13, 1, tzinfo=UTC)
    run = await research.automations.run(saved["id"], expected_version=1, research_bot=True)
    await research.automations.wait_for_idle()
    stored = research.store.data["automation_runs"][run["id"]]
    assert stored["research_status"] == "completed"
    assert stored["bot_result"]["judgment"] == result["judgment"]  # no 4000-char truncation
    await research.automations.run(saved["id"], trigger="schedule")
    await research.automations.wait_for_idle()
    assert calls == ["create", "send"]


def test_result_requires_trusted_skill_load_and_source_identity(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body(skills=[{"id": "skill", "version": 1, "sha256": "a" * 64}]))
    run = {
        "id": "run",
        "session_id": "sid",
        "definition_snapshot": saved,
        "bot_materials": feed()["news"],
    }
    result = {
        "status": "completed",
        "summary": json.dumps(
            {"signal": "neutral", "headline": "结论", "judgment": "待核实", "sourceIds": ["n1"]}
        ),
    }
    with pytest.raises(StoreError):
        bots.finish(run, result)
    research.store.data["receipts"]["sid:automation:run"] = {
        "native_capabilities": [{"id": "skill", "version": 1, "sha256": "a" * 64}]
    }
    bots.finish(run, result)
    assert run["bot_loaded_skills"][0]["id"] == "skill"
    bad = json.loads(result["summary"])
    bad["sourceIds"] = ["invented"]
    with pytest.raises(StoreError):
        bots.finish(run, {"status": "completed", "summary": json.dumps(bad)})
    bad.update(sourceIds=[], signal="bullish")
    with pytest.raises(StoreError):
        bots.finish(run, {"status": "completed", "summary": json.dumps(bad)})


@pytest.mark.asyncio
async def test_unknown_submission_cannot_be_repeated_by_schedule(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())

    async def read(**_kwargs):
        return feed()

    research.discovery = SimpleNamespace(feed=read)
    research.automations.now = lambda: datetime(2026, 11, 13, 1, tzinfo=UTC)
    run = {"id": "unknown", "trigger": "schedule"}
    await bots.prepare(saved, run)
    research.store.data["automation_runs"]["unknown"] = {
        **run,
        "automation_id": saved["id"],
        "research_status": "interrupted",
    }
    with pytest.raises(StoreError, match="上次"):
        await bots.prepare(saved, {"id": "next", "trigger": "schedule"})
    assert await bots.prepare(saved, {"id": "manual", "trigger": "manual"})


@pytest.mark.asyncio
async def test_run_cas_and_frozen_scope_cannot_be_forged(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())
    with pytest.raises(StoreError):
        await research.automations.run(saved["id"], expected_version=5, research_bot=True)
    assert research.store.data["automation_runs"] == {}
    with pytest.raises(StoreError):
        bots.trusted_selections("foreign-session", "unknown-run")


@pytest.mark.asyncio
async def test_simultaneous_bot_jobs_do_not_fire_next_interval_early(tmp_path):
    bots, research = setup(tmp_path)
    service = research.automations
    now = datetime(2026, 11, 13, 1, tzinfo=UTC)
    service.now = lambda: now
    jobs = {}

    def add_job(callback, _kind, *, id, args, **_kwargs):
        jobs[id] = (callback, args)

    service.scheduler = SimpleNamespace(add_job=add_job, remove_job=lambda key: jobs.pop(key, None))
    service.executor = lambda *_args: {"status": "completed"}
    rows = [bots.save(body(name=name)) for name in ("第一个", "第二个")]
    for row in rows:
        service.enable(row["id"], expected_version=1, research_bot=True)
    original_jobs = list(jobs.values())
    now = datetime(2026, 11, 13, 1, 30, tzinfo=UTC)
    for callback, args in original_jobs:
        await callback(*args)
    await service.wait_for_idle()
    assert [len(bots.runs(row["id"], None)["items"]) for row in rows] == [1, 1]
    assert {service.get(row["id"], research_bot=True)["next_run_at"] for row in rows} == {
        "2026-11-13T02:00:00+00:00"
    }


@pytest.mark.asyncio
async def test_late_bot_job_skips_missed_intervals_and_arms_future_job(tmp_path):
    bots, research = setup(tmp_path)
    service = research.automations
    now = datetime(2026, 11, 13, 1, tzinfo=UTC)
    service.now = lambda: now
    service.executor = lambda *_args: {"status": "completed"}
    jobs = []
    service.scheduler = SimpleNamespace(
        add_job=lambda *_args, **kwargs: jobs.append(kwargs), remove_job=lambda _job_id: None
    )
    bot = bots.save(body(interval_minutes=5))
    original = service.enable(bot["id"], expected_version=1, research_bot=True)
    assert jobs[-1]["misfire_grace_time"] is None
    now += timedelta(hours=1)

    await service._scheduled_fire(bot["id"], original["next_run_at"])
    await service.wait_for_idle()

    runs = bots.runs(bot["id"], None)["items"]
    assert [run["scheduled_for"] for run in runs] == [original["next_run_at"]]
    assert bots.get(bot["id"])["next_run_at"] == (now + timedelta(minutes=5)).isoformat()


@pytest.mark.asyncio
async def test_scheduled_bot_skips_materials_removed_from_window(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())
    value = feed()
    value["news"].append(
        {**value["news"][0], "id": "expired", "published_at": "2026-11-11T02:00:00+00:00"}
    )

    async def read(**_kwargs):
        return value

    research.discovery = SimpleNamespace(feed=read)
    now = datetime(2026, 11, 13, 1, tzinfo=UTC)
    research.automations.now = lambda: now
    run = {"id": "first", "trigger": "schedule"}
    assert await bots.prepare(saved, run) is not None
    assert len(run["bot_materials"]) == 2
    research.store.data["automation_runs"][run["id"]] = {
        **run,
        "automation_id": saved["id"],
        "definition_snapshot": saved,
        "research_status": "completed",
        "bot_result": {"headline": "已核验"},
        "created_at": 1,
    }

    now = datetime(2026, 11, 13, 3, tzinfo=UTC)
    assert await bots.prepare(saved, {"id": "second", "trigger": "schedule"}) is None
    value["news"][0]["materials"] = [{"content_sha256": "b" * 64}]
    assert await bots.prepare(saved, {"id": "third", "trigger": "schedule"}) is not None


@pytest.mark.asyncio
async def test_manual_verified_result_supersedes_older_bot_failure(tmp_path):
    bots, research = setup(tmp_path)
    saved = bots.save(body())

    async def read(**_kwargs):
        return feed()

    research.discovery = SimpleNamespace(feed=read)
    research.automations.now = lambda: datetime(2026, 11, 13, 1, tzinfo=UTC)
    first = {"id": "first", "trigger": "schedule"}
    await bots.prepare(saved, first)
    rows = research.store.data["automation_runs"]
    rows["first"] = {
        **first,
        "automation_id": saved["id"],
        "definition_snapshot": saved,
        "research_status": "interrupted",
        "created_at": 1,
    }
    with pytest.raises(StoreError, match="上次"):
        await bots.prepare(saved, {"id": "second", "trigger": "schedule"})

    manual = {"id": "manual", "trigger": "manual"}
    await bots.prepare(saved, manual)
    rows["manual"] = {
        **manual,
        "automation_id": saved["id"],
        "definition_snapshot": saved,
        "research_status": "completed",
        "bot_result": {"headline": "已核验"},
        "created_at": 3,
    }
    assert await bots.prepare(saved, {"id": "fourth", "trigger": "schedule"}) is None


def test_history_pages_are_scoped_and_list_omits_frozen_materials(tmp_path):
    bots, research = setup(tmp_path)
    bot = bots.save(body())
    other = bots.save(body(name="另一任务"))
    for i in range(22):
        run = research.automations._new_run(
            bot["id"], trigger="manual", scheduled_for=None, retry_of=None, status="completed"
        )
        run.update(created_at=i, bot_materials=[{"id": "large"}])
    foreign = research.automations._new_run(
        other["id"], trigger="manual", scheduled_for=None, retry_of=None, status="failed"
    )
    page = bots.runs(bot["id"], None)
    assert [row["created_at"] for row in page["items"]] == list(range(21, 1, -1))
    older = bots.runs(bot["id"], page["next_before"])
    assert [row["created_at"] for row in older["items"]] == [1, 0]
    assert older["next_before"] is None
    with pytest.raises(StoreError, match="游标"):
        bots.runs(bot["id"], foreign["id"])
    latest = next(row for row in bots.list()["latest_runs"] if row["automation_id"] == bot["id"])
    assert latest["id"] == page["items"][0]["id"]
    assert not {"bot_materials", "definition_snapshot"} & latest.keys()


@pytest.mark.asyncio
async def test_replayed_manual_run_is_idempotent_after_completion_and_edit(tmp_path):
    bots, research = setup(tmp_path)
    bot = bots.save(body())
    attempts = []

    async def execute(_automation, run):
        attempts.append(run["id"])
        return {"status": "completed", "summary": "已完成"}

    research.automations.executor = execute
    kwargs = {
        "expected_version": 1,
        "research_bot": True,
        "request_id": "11111111-1111-4111-8111-111111111111",
    }
    original = await research.automations.run(bot["id"], **kwargs)
    await research.automations.wait_for_idle()
    bots.save(body(expected_version=1), bot["id"])
    replay = await research.automations.run(bot["id"], **kwargs)
    assert replay["id"] == original["id"]
    assert replay["research_status"] == "completed"
    assert attempts == [original["id"]]
    with pytest.raises(StoreError, match="另一版本"):
        await research.automations.run(bot["id"], **{**kwargs, "expected_version": 2})


def test_bot_workflow_dependency_is_frozen_and_required_in_result(tmp_path):
    bots, research = setup(tmp_path)
    picks = {
        "parent": {
            "id": "parent",
            "version": 1,
            "sha256": "a" * 64,
            "kind": "workflow",
            "native_name": "parent",
            "bindings": [{"id": "child", "version": 1, "native_name": "child"}],
        },
        "child": {
            "id": "child",
            "version": 1,
            "sha256": "b" * 64,
            "kind": "skill",
            "native_name": "child",
            "bindings": [],
        },
    }
    research.capabilities.selection = lambda cid, _version: picks[cid]
    bot = bots.save(body(skills=[{"id": "parent", "version": 1, "sha256": "a" * 64}]))
    run = {
        "id": "run",
        "session_id": "sid",
        "definition_snapshot": bot,
        "bot_materials": [],
        "bot_fingerprint": "frozen",
        "research_status": "running",
    }
    research.store.data["automation_runs"]["run"] = run
    frozen = bots.trusted_selections("sid", "run")
    assert frozen == [picks["parent"], picks["child"]]
    receipt = {"research_bot_capabilities": frozen, "native_capabilities": [picks["parent"]]}
    research.store.data["receipts"]["sid:automation:run"] = receipt
    result = {
        "status": "completed",
        "summary": json.dumps({"signal": "neutral", "headline": "缺口", "judgment": "待核对"}),
    }
    with pytest.raises(StoreError):
        bots.finish(run, result)
    receipt["native_capabilities"].append(picks["child"])
    bots.finish(run, result)
    assert [skill["id"] for skill in run["bot_loaded_skills"]] == ["parent", "child"]
