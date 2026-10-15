"""Research definitions, explicit confirmation and immutable run contracts."""

import copy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.research_web.automation.drafts import AutomationDrafts
from app.research_web.automation.models import (
    AutomationCreate,
    AutomationSchedule,
    AutomationUpdate,
)
from app.research_web.automation.schedule import next_occurrence
from app.research_web.automation.service import AutomationService
from app.research_web.store import Store, StoreError


def research_body():
    return AutomationCreate.model_validate(
        {
            "name": "每日收盘点评",
            "target_kind": "research_task",
            "research_task": {
                "schema_version": 1,
                "description": "生成收盘点评，不编造缺失数据。",
                "model_provider": "deepseek-official",
                "model_id": "deepseek-flash",
                "output_requirements": "Markdown 报告及真实文件",
                "approved_data_sources": ["datahub"],
                "approved_tools": [],
            },
            "output_formats": ["md"],
            "schedule": {
                "kind": "weekly",
                "weekdays": [0, 1, 2, 3, 4],
                "timezone": "Asia/Shanghai",
                "hour": 15,
                "minute": 30,
            },
        }
    )


def setup(tmp_path):
    store = Store(tmp_path)
    service = AutomationService(
        store, scheduler=False, now=lambda: datetime(2026, 10, 16, 8, tzinfo=UTC)
    )
    research = SimpleNamespace(store=store, automations=service)
    sid = store.create("claw", "每日收盘点评")["id"]
    return service, AutomationDrafts(research), sid


def test_weekdays_skip_weekend_and_legacy_weekday_is_supported():
    schedule = AutomationSchedule.model_validate(research_body().schedule.model_dump())
    assert next_occurrence(schedule, datetime(2026, 10, 16, 7, 30, tzinfo=UTC)) == datetime(
        2026, 10, 19, 7, 30, tzinfo=UTC
    )
    legacy = AutomationSchedule(
        kind="weekly", weekday=4, timezone="Asia/Shanghai", hour=15, minute=30
    )
    assert next_occurrence(legacy, datetime(2026, 10, 16, 7, 30, tzinfo=UTC)) == datetime(
        2026, 10, 23, 7, 30, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        AutomationSchedule(
            kind="weekly", weekdays=[0, 0], timezone="Asia/Shanghai", hour=15, minute=30
        )


def test_research_confirm_enables_without_run_and_replay_is_idempotent(tmp_path):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    assert service.list()["items"] == []
    saved = drafts.confirm(sid, draft["id"], body, enable=True)
    assert saved["enabled"] is True
    assert saved["definition_version"] == 1
    assert service.list_runs()["items"] == []
    assert drafts.confirm(sid, draft["id"], body, enable=True)["id"] == saved["id"]
    service.delete(saved["id"])
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)


def test_enable_failure_retains_disabled_task_and_retry_does_not_duplicate(tmp_path, monkeypatch):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    original = service.enable

    def fail(_id, **_kwargs):
        raise StoreError("启用失败", "enable_failed", 503)

    monkeypatch.setattr(service, "enable", fail)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    assert len(service.list()["items"]) == 1
    assert service.list()["items"][0]["enabled"] is False
    monkeypatch.setattr(service, "enable", original)
    assert drafts.confirm(sid, draft["id"], body, enable=True)["enabled"] is True
    assert len(service.list()["items"]) == 1


def test_enable_retry_rejects_changed_definition_version(tmp_path, monkeypatch):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    original = service.enable

    def fail(_id, **_kwargs):
        raise StoreError("启用失败", "enable_failed", 503)

    monkeypatch.setattr(service, "enable", fail)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    before = drafts.list(sid)["items"][0]
    updated = service.update(
        before["automation_id"], AutomationUpdate(expected_version=1, name="修改后的定义")
    )
    assert updated["definition_version"] == 2 and updated["enabled"] is False
    monkeypatch.setattr(service, "enable", original)
    with pytest.raises(StoreError) as failure:
        drafts.confirm(sid, draft["id"], body, enable=True)
    assert failure.value.code == "automation_version_conflict"
    assert failure.value.status == 409
    assert service.get(updated["id"])["enabled"] is False
    after = drafts.list(sid)["items"][0]
    assert after["confirmed_definition"] == before["confirmed_definition"]
    assert after["confirmed_version"] == 1
    assert after["confirmed_enabled"] is False
    assert not after.get("enable_completed")
    assert service.list_runs()["items"] == []


@pytest.mark.parametrize("missing", ["confirmed_version", "confirmed_definition"])
def test_enable_retry_missing_saved_receipt_fails_closed(tmp_path, monkeypatch, missing):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    original = service.enable

    def fail(_id, **_kwargs):
        raise StoreError("启用失败", "enable_failed", 503)

    monkeypatch.setattr(service, "enable", fail)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    row = drafts.store.data["automation_drafts"][draft["id"]]
    row.pop(missing)
    drafts.store.save()
    monkeypatch.setattr(service, "enable", original)
    with pytest.raises(StoreError) as failure:
        drafts.confirm(sid, draft["id"], body, enable=True)
    assert failure.value.code == "draft_confirmation_receipt_invalid"
    assert failure.value.status == 409
    assert service.get(row["automation_id"])["enabled"] is False
    assert row["confirmed_enabled"] is False
    assert not row.get("enable_completed")
    assert missing not in row


@pytest.mark.asyncio
async def test_update_keeps_id_and_run_snapshot_and_manual_plan_time(tmp_path):
    service, drafts, sid = setup(tmp_path)
    service.executor = lambda *_args: {"status": "completed", "summary": "真实测试替身"}
    saved = service.create(research_body())
    enabled = service.enable(saved["id"])
    run = await service.run(saved["id"])
    await service.wait_for_idle()
    assert service.get(saved["id"])["next_run_at"] == enabled["next_run_at"]
    changed = {**saved["research_task"], "description": "增加明确标注日期的两融数据"}
    update = AutomationUpdate(expected_version=1, research_task=changed)
    draft = drafts.prepare_update(sid, saved["id"], update)
    updated = drafts.confirm_update(sid, draft["id"], update)
    assert updated["id"] == saved["id"] and updated["definition_version"] == 2
    assert updated["schedule"] == saved["schedule"]
    assert updated["research_task"]["model_id"] == saved["research_task"]["model_id"]
    assert drafts.confirm_update(sid, draft["id"], update)["definition_version"] == 2
    old_run = service.list_runs()["items"][0]
    assert old_run["id"] == run["id"]
    assert old_run["definition_version"] == 1
    assert (
        old_run["definition_snapshot"]["research_task"]["description"]
        == saved["research_task"]["description"]
    )
    with pytest.raises(StoreError):
        service.update(saved["id"], update)


def test_replay_does_not_reenable_user_disabled_task(tmp_path):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    saved = drafts.confirm(sid, draft["id"], body, enable=True)
    service.disable(saved["id"])
    assert drafts.confirm(sid, draft["id"], body, enable=True)["enabled"] is False


def test_update_cancel_conflict_and_deleted_replay_do_not_mutate(tmp_path):
    service, drafts, sid = setup(tmp_path)
    saved = service.create(research_body())
    update = AutomationUpdate(expected_version=1, name="增加技术面")
    draft = drafts.prepare_update(sid, saved["id"], update)
    drafts.dismiss(sid, draft["id"])
    with pytest.raises(StoreError):
        drafts.confirm_update(sid, draft["id"], update)
    assert service.get(saved["id"])["definition_version"] == 1
    draft = drafts.prepare_update(sid, saved["id"], update)
    service.update(saved["id"], AutomationUpdate(expected_version=1, name="并发修改"))
    with pytest.raises(StoreError):
        drafts.confirm_update(sid, draft["id"], update)
    service.delete(saved["id"])
    with pytest.raises(StoreError):
        drafts.confirm_update(sid, draft["id"], update)
    assert service.list()["items"] == []


def test_update_checkpoint_failure_recovery_preserves_revision_once(tmp_path, monkeypatch):
    service, drafts, sid = setup(tmp_path)
    saved = service.create(research_body())
    update = AutomationUpdate(expected_version=1, name="带技术面点评")
    draft = drafts.prepare_update(sid, saved["id"], update)
    save = service.store.save
    counter = 0

    def interrupted_save():
        nonlocal counter
        counter += 1
        if counter == 2:
            raise StoreError("确认检查点失败")
        save()

    monkeypatch.setattr(service.store, "save", interrupted_save)
    with pytest.raises(StoreError):
        drafts.confirm_update(sid, draft["id"], update)
    restored = Store(service.store.root)
    service.store = restored
    research = SimpleNamespace(store=restored, automations=service)
    recovered = AutomationDrafts(research)
    result = recovered.confirm_update(sid, draft["id"], update)
    assert result["definition_version"] == 2
    assert len(result["definition_revisions"]) == 2


def test_scheduler_arm_failure_rolls_back_enable_persistently(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    saved = service.create(research_body())

    class FailingScheduler:
        def remove_job(self, _id):
            from apscheduler.jobstores.base import JobLookupError

            raise JobLookupError(_id)

        def add_job(self, *_args, **_kwargs):
            raise RuntimeError("scheduler failed")

    service.scheduler = FailingScheduler()
    with pytest.raises(RuntimeError):
        service.enable(saved["id"])
    assert service.get(saved["id"])["enabled"] is False
    assert Store(service.store.root).data["automations"][saved["id"]]["enabled"] is False


@pytest.mark.asyncio
async def test_queued_run_uses_prior_definition_when_task_changes(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    executions = []

    async def execute(definition, _run):
        executions.append(definition)
        return {"status": "completed", "summary": "测试执行"}

    service.executor = execute
    saved = service.create(research_body())
    await service.run(saved["id"])
    service.update(saved["id"], AutomationUpdate(expected_version=1, name="新的名字"))
    await service.wait_for_idle()
    assert executions[0]["name"] == "每日收盘点评"
    assert executions[0]["definition_version"] == 1


@pytest.mark.asyncio
async def test_native_research_run_uses_independent_session_without_fake_skill(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    calls = []

    async def create(name, definition):
        calls.append(("create", name, definition))
        return {"id": "owned-claw-research"}

    async def send(sid, text, key, **kwargs):
        calls.append(("send", sid, text, key, kwargs))
        return {"accepted": True}

    async def monitor(sid):
        return {"status": "completed", "summary": "测试回复", "artifacts": [{"name": "report.md"}]}

    service.research = SimpleNamespace(create_automation_research_session=create, send=send)
    service._monitor_session = monitor
    saved = service.create(research_body())
    run = await service.run(saved["id"])
    await service.wait_for_idle()
    assert calls[0][1:] == ("每日收盘点评", saved["research_task"])
    assert calls[1][-1] == {"formats": ["md"], "tool_ids": []}
    assert "输出要求：Markdown 报告及真实文件" in calls[1][2]
    result = service.list_runs()["items"][0]
    assert result["id"] == run["id"]
    assert result["session_id"] == "owned-claw-research"
    assert result["research_status"] == "completed"
    assert result["artifacts"] == [{"name": "report.md"}]


def test_deleted_task_after_interrupted_create_cannot_be_resurrected(tmp_path, monkeypatch):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    save = service.store.save
    counter = 0

    def interrupted_save():
        nonlocal counter
        counter += 1
        if counter == 2:
            raise StoreError("确认检查点失败")
        save()

    monkeypatch.setattr(service.store, "save", interrupted_save)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    monkeypatch.setattr(service.store, "save", save)
    saved = service.list()["items"][0]
    service.delete(saved["id"])
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    assert service.list()["items"] == []


@pytest.mark.parametrize(
    "tool",
    [
        "rwb_prepare_automation",
        "rwb_automation_action",
        "settings",
        "mcp_external_tool",
        "subagent",
    ],
)
def test_research_create_rejects_nonselectable_tools_without_runtime(tmp_path, tool):
    service, _drafts, _sid = setup(tmp_path)
    payload = research_body().model_dump(mode="json")
    payload["research_task"]["approved_tools"] = [tool]
    with pytest.raises(StoreError, match="管理"):
        service.create(AutomationCreate.model_validate(payload))
    assert service.list()["items"] == []


def test_research_update_and_enable_recheck_selectable_scope(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    saved = service.create(research_body())
    bad_definition = {**saved["research_task"], "approved_tools": ["rwb_prepare_automation"]}
    with pytest.raises(StoreError):
        service.update(
            saved["id"], AutomationUpdate(expected_version=1, research_task=bad_definition)
        )
    assert service.get(saved["id"])["definition_version"] == 1
    from app.research_web.automation.service import _canonical_sha

    row = service.store.data["automations"][saved["id"]]
    row["research_task"] = bad_definition
    row["target"]["sha256"] = _canonical_sha(bad_definition)
    with pytest.raises(StoreError):
        service.enable(saved["id"])
    assert service.get(saved["id"])["enabled"] is False


def test_research_empty_and_selectable_tool_scopes_are_preserved(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    saved = service.create(research_body())
    assert service.enable(saved["id"])["research_task"]["approved_tools"] == []
    definition = {**saved["research_task"], "approved_tools": ["research_document_operation"]}
    updated = service.update(
        saved["id"], AutomationUpdate(expected_version=1, research_task=definition)
    )
    assert updated["research_task"]["approved_tools"] == ["research_document_operation"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["incomplete", "blocked"])
async def test_terminal_incomplete_research_closes_without_retry_or_infinite_monitor(
    tmp_path, status
):
    service, _drafts, _sid = setup(tmp_path)

    async def unexpected_sleep(_seconds):
        pytest.fail("terminal incomplete native execution must not keep polling")

    service.sleep = unexpected_sleep
    result = await service._monitor_session(
        "owned-session",
        initial={
            "status": status,
            "can_cancel": False,
            "messages": [{"role": "assistant", "text": "缺少要求的文件"}],
            "files": [],
        },
    )
    assert result["status"] == "failed"
    assert result["failure_code"] == f"session_{status}"


@pytest.mark.asyncio
async def test_pending_and_cancellable_incomplete_are_not_completed_prematurely(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    pending = [
        {"status": "awaiting_approval", "can_cancel": True},
        {"status": "waiting_input", "can_cancel": True},
        {"status": "incomplete", "can_cancel": True},
        {
            "status": "completed",
            "can_cancel": False,
            "messages": [{"role": "assistant", "text": "真实完成"}],
            "files": [{"name": "report.md"}],
        },
    ]
    delays = []

    async def detail(_sid):
        return pending.pop(0)

    async def sleep(seconds):
        delays.append(seconds)

    service.research = SimpleNamespace(detail=detail)
    service.sleep = sleep
    result = await service._monitor_session("owned-session")
    assert result["status"] == "completed"
    assert result["artifacts"] == [{"name": "report.md"}]
    assert delays == [1, 1, 1]


@pytest.mark.asyncio
async def test_research_prompt_uses_execution_clock_timezone_and_requested_output_scope(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    captured = []

    async def create(_name, _definition):
        return {"id": "owned-session"}

    async def send(_sid, text, _key, **_kwargs):
        captured.append(text)
        return {"accepted": True}

    async def monitor(_sid):
        return {"status": "completed", "summary": "完成", "artifacts": []}

    service.research = SimpleNamespace(create_automation_research_session=create, send=send)
    service._monitor_session = monitor
    saved = service.create(research_body())
    await service.run(saved["id"])
    await service.wait_for_idle()
    assert len(captured) == 1
    assert "2026-10-16T16:00:00+08:00" in captured[0]
    assert "Asia/Shanghai" in captured[0]
    assert "outputs/" in captured[0]
    assert "md" in captured[0]
    assert "不得枚举" in captured[0]
    assert "收盘前" in captured[0]


@pytest.mark.asyncio
async def test_recovered_incomplete_native_run_finishes_failed_without_resubmission(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    saved = service.create(research_body())
    run = service._new_run(
        saved["id"], trigger="manual", scheduled_for=None, retry_of=None, status="running"
    )
    run["session_id"] = "owned-session"

    async def detail(_sid):
        return {"status": "incomplete", "can_cancel": False, "files": [], "messages": []}

    service.research = SimpleNamespace(detail=detail)
    await service._resume(run["id"])
    assert run["research_status"] == "failed"
    assert run["failure_code"] == "session_incomplete"
    assert len(service.list_runs()["items"]) == 1


@pytest.mark.asyncio
async def test_run_notifications_follow_durable_terminal_and_reference_checkpoints(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    observations = []

    def notify():
        restored = Store(service.store.root)
        observations.append([dict(row) for row in restored.data["automation_runs"].values()])

    service.research = SimpleNamespace(notify=notify)

    async def execute(_definition, run):
        service._persist_native_reference(run["id"], session_id="owned-session")
        return {
            "status": "completed",
            "session_id": "owned-session",
            "summary": "已完成",
            "artifacts": [{"name": "report.md"}],
        }

    service.executor = execute
    saved = service.create(research_body())
    run = await service.run(saved["id"])
    await service.wait_for_idle()
    assert any(rows[0]["research_status"] == "queued" for rows in observations)
    assert any(
        rows[0]["research_status"] == "running" and rows[0]["session_id"] == "owned-session"
        for rows in observations
    )
    assert observations[-1][0]["id"] == run["id"]
    assert observations[-1][0]["research_status"] == "completed"
    assert observations[-1][0]["summary"] == "已完成"
    assert observations[-1][0]["artifacts"] == [{"name": "report.md"}]


def test_concurrent_definition_update_accepts_only_one_expected_version(tmp_path, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    service, _drafts, _sid = setup(tmp_path)
    saved = service.create(research_body())
    start = threading.Barrier(2)
    validate = service._validate_research_tools

    def yielding_validation(tools):
        time.sleep(0.04)
        validate(tools)

    monkeypatch.setattr(service, "_validate_research_tools", yielding_validation)

    def update(label):
        start.wait(timeout=2)
        definition = {**saved["research_task"], "description": label}
        try:
            return service.update(
                saved["id"], AutomationUpdate(expected_version=1, research_task=definition)
            )
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["第一修改", "第二修改"]))
    accepted = [result for result in results if isinstance(result, dict)]
    assert len(accepted) == 1
    assert results.count("automation_version_conflict") == 1
    row = service.get(saved["id"])
    assert row["definition_version"] == 2
    assert [version["definition_version"] for version in row["definition_revisions"]] == [1, 2]


@pytest.mark.asyncio
async def test_restricted_native_children_cannot_be_reported_completed(tmp_path):
    service, _drafts, _sid = setup(tmp_path)
    result = await service._monitor_session(
        "owned",
        initial={
            "status": "completed",
            "execution_restricted": True,
            "files": [{"name": "report.md"}],
            "messages": [{"role": "assistant", "text": "不能证明子会话状态"}],
        },
    )
    assert result["status"] == "failed"
    assert result["failure_code"] == "native_child_state_unverified"


@pytest.mark.asyncio
async def test_projection_observer_error_cannot_change_saved_research_success(tmp_path):
    service, _drafts, _sid = setup(tmp_path)

    def failed_notify():
        raise RuntimeError("observer unavailable")

    service.research = SimpleNamespace(notify=failed_notify)
    service.executor = lambda *_args: {
        "status": "completed",
        "summary": "真实持久完成",
        "artifacts": [],
    }
    saved = service.create(research_body())
    await service.run(saved["id"])
    await service.wait_for_idle()
    assert service.list_runs()["items"][0]["research_status"] == "completed"
    restored = Store(service.store.root)
    assert next(iter(restored.data["automation_runs"].values()))["research_status"] == "completed"


def test_confirmed_draft_receipt_preserves_saved_definition_after_update_disable_and_delete(
    tmp_path,
):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    saved = drafts.confirm(sid, draft["id"], body, enable=True)
    receipt = drafts.list(sid)["items"][0]
    assert receipt["confirmed_definition"]["definition_version"] == saved["definition_version"]
    assert receipt["confirmed_definition"]["research_task"] == saved["research_task"]
    assert receipt["confirmed_enabled"] is True
    assert receipt["confirmed_next_run_at"] == saved["next_run_at"]
    original = copy.deepcopy(receipt["confirmed_definition"])
    service.update(saved["id"], AutomationUpdate(expected_version=1, name="changed task"))
    service.disable(saved["id"])
    assert drafts.confirm(sid, draft["id"], body, enable=True)["enabled"] is False
    assert drafts.list(sid)["items"][0]["confirmed_definition"] == original
    assert drafts.list(sid)["items"][0]["confirmed_enabled"] is True
    receipt["confirmed_definition"]["name"] = "caller mutation"
    assert drafts.list(sid)["items"][0]["confirmed_definition"]["name"] == saved["name"]
    service.delete(saved["id"])
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    assert drafts.list(sid)["items"][0]["confirmed_definition"] == original


def test_update_receipt_uses_actual_result_and_duplicate_does_not_follow_later_version(tmp_path):
    service, drafts, sid = setup(tmp_path)
    saved = service.enable(service.create(research_body())["id"])
    update = AutomationUpdate(expected_version=1, name="approved update")
    draft = drafts.prepare_update(sid, saved["id"], update)
    result = drafts.confirm_update(sid, draft["id"], update)
    receipt = drafts.list(sid)["items"][0]
    assert receipt["confirmed_definition"]["definition_version"] == result["definition_version"]
    assert receipt["confirmed_definition"]["name"] == "approved update"
    assert receipt["confirmed_enabled"] is True
    original = copy.deepcopy(receipt["confirmed_definition"])
    service.update(saved["id"], AutomationUpdate(expected_version=2, name="later version"))
    drafts.confirm_update(sid, draft["id"], update)
    assert drafts.list(sid)["items"][0]["confirmed_definition"] == original
    service.delete(saved["id"])
    with pytest.raises(StoreError):
        drafts.confirm_update(sid, draft["id"], update)
    assert drafts.list(sid)["items"][0]["confirmed_definition"] == original


def test_enable_retry_updates_only_actual_enable_receipt_and_keeps_saved_definition(
    tmp_path, monkeypatch
):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    original_enable = service.enable

    def fail(_id, **_kwargs):
        raise StoreError("failed", "enable_failed", 503)

    monkeypatch.setattr(service, "enable", fail)
    with pytest.raises(StoreError):
        drafts.confirm(sid, draft["id"], body, enable=True)
    before = drafts.list(sid)["items"][0]
    assert before["confirmed_enabled"] is False
    assert before["enable_error"] == "enable_failed"
    monkeypatch.setattr(service, "enable", original_enable)
    enabled = drafts.confirm(sid, draft["id"], body, enable=True)
    after = drafts.list(sid)["items"][0]
    assert after["confirmed_definition"] == before["confirmed_definition"]
    assert after["confirmed_at"] == before["confirmed_at"]
    assert after["confirmed_next_run_at"] == enabled["next_run_at"]
    assert after["confirmed_enabled"] is enabled["enabled"] is True
    assert "enable_error" not in after
    assert len(service.list()["items"]) == 1


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("expected_version", [2, 0, True])
def test_enable_compare_and_swap_precedes_already_enabled_shortcut(
    tmp_path, enabled, expected_version
):
    service, _, _ = setup(tmp_path)
    saved = service.create(research_body())
    if enabled:
        service.enable(saved["id"])
    before = service.get(saved["id"])
    with pytest.raises(StoreError) as failure:
        service.enable(saved["id"], expected_version=expected_version)
    assert failure.value.code == "automation_version_conflict"
    assert failure.value.status == 409
    assert service.get(saved["id"]) == before


def test_enable_waiting_for_definition_lock_cannot_enable_intervening_update(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    service, _, _ = setup(tmp_path)
    saved = service.create(research_body())
    started = threading.Event()

    def enable_old_definition():
        started.set()
        return service.enable(saved["id"], expected_version=1)

    with ThreadPoolExecutor(max_workers=1) as worker:
        with service.definition_lock:
            pending = worker.submit(enable_old_definition)
            assert started.wait(timeout=5)
            updated = service.update(
                saved["id"], AutomationUpdate(expected_version=1, name="锁内更新")
            )
            assert updated["definition_version"] == 2
            assert updated["enabled"] is False
        with pytest.raises(StoreError) as failure:
            pending.result(timeout=5)
    assert failure.value.code == "automation_version_conflict"
    assert service.get(saved["id"]) == updated
    assert service.list_runs()["items"] == []


def test_legacy_confirmed_receipt_never_guesses_definition_from_current_task(tmp_path):
    service, drafts, sid = setup(tmp_path)
    draft = drafts.prepare(sid, research_body())
    body = AutomationCreate.model_validate(draft["body"])
    saved = drafts.confirm(sid, draft["id"], body, enable=True)
    row = drafts.store.data["automation_drafts"][draft["id"]]
    row.pop("confirmed_definition", None)
    row.pop("confirmed_version", None)
    service.update(saved["id"], AutomationUpdate(expected_version=1, name="new definition"))
    drafts.confirm(sid, draft["id"], body, enable=True)
    assert "confirmed_definition" not in drafts.list(sid)["items"][0]
    assert "confirmed_version" not in drafts.list(sid)["items"][0]


def chat_trial_fixture(tmp_path, text, *, version=1, context=False):
    """Exercise the real admission method without starting a scheduler or model."""
    from app.research_web.service import ResearchService

    store = Store(tmp_path)
    sid = store.create("claw", "试跑授权")["id"]
    aid = "automation-" + "3a" * 32
    definition = {"id": aid, "name": "每日收盘点评·执行流验收", "definition_version": version}
    if context:
        store.session(sid)["automation_trial_context"] = {"automation_id": aid}
    runs = {}

    async def history(_sid):
        return [
            {
                "event": {
                    "seq": 1,
                    "type": "user/message",
                    "time": 1,
                    "data": {"content": [{"type": "text", "text": text.replace("TASK_ID", aid)}]},
                }
            }
        ]

    async def run(task_id, **kwargs):
        assert task_id == aid and kwargs == {"trigger": "manual"}
        runs["run"] = {"id": "run", "automation_id": aid}
        return runs["run"]

    owner = SimpleNamespace(
        store=store,
        client=SimpleNamespace(history=history),
        automations=SimpleNamespace(
            get=lambda _id: definition, run=run, _run_row=lambda rid: runs[rid], _public=dict
        ),
        notify=lambda: None,
    )
    return lambda: ResearchService.run_automation_from_chat(owner, sid, aid), runs, store


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "先跑一次刚创建的「每日收盘点评·执行流验收」（TASK_ID）v1。只运行这一任务，按已批准定义写入和读回真实MD；不要联网、不修改日程和下次执行时间。",
        "请再试跑一次刚修改的“每日收盘点评·执行流验收” v1。不要联网。",
        "帮我运行一次 TASK_ID v1。按已批准定义生成 Markdown 文件。",
        "先跑一次每日收盘点评·执行流验收。",
    ],
)
async def test_named_trial_first_sentence_with_constraints_is_explicit_and_idempotent(
    tmp_path, text
):
    invoke, runs, _store = chat_trial_fixture(tmp_path, text)
    first = await invoke()
    assert first["id"] == "run"
    assert await invoke() == first
    assert len(runs) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "解释一下先跑一次「每日收盘点评·执行流验收」",
        "“先跑一次每日收盘点评·执行流验收”",
        "请解释“先跑一次每日收盘点评·执行流验收”的含义。",
        "不要先跑一次每日收盘点评·执行流验收。",
        "如果资料齐全，先跑一次每日收盘点评·执行流验收。",
        "先跑一次每日收盘点评·执行流验收，如果资料齐全。",
        "先跑一次每日收盘点评·执行流验收。若需要则运行。",
        "先跑一次每日收盘点评·执行流验收。不要真正运行。",
        "先跑一次每日收盘点评·执行流验收。然后运行另一个任务。",
        "先跑一次另一个任务（TASK_ID）v1。",
        "先跑一次「每日收盘点评·执行流验收」（automation-wrong）v1。",
        "先跑一次TASK_ID-other v1。",
        "增加",
        "需要",
    ],
)
async def test_long_trial_explanation_negation_condition_or_mismatched_target_denied(
    tmp_path, text
):
    invoke, runs, store = chat_trial_fixture(tmp_path, text, context=True)
    with pytest.raises(StoreError) as failure:
        await invoke()
    assert failure.value.code == "automation_trial_not_requested"
    assert runs == {} and not store.data.get("automation_trial_requests")


@pytest.mark.asyncio
async def test_explicit_trial_version_mismatch_never_runs_newer_definition(tmp_path):
    invoke, runs, store = chat_trial_fixture(
        tmp_path, "先跑一次刚修改的「每日收盘点评·执行流验收」v1。不要联网。", version=2
    )
    with pytest.raises(StoreError) as failure:
        await invoke()
    assert failure.value.code == "automation_version_conflict"
    assert runs == {} and not store.data.get("automation_trial_requests")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constraint",
    [
        "按已批准定义等待我确认后再启动",
        "按已批准定义暂时不要启动",
        "按已批准定义只是说明上述命令的意思",
        "不要修改日程且必须获得我的确认后才启动",
    ],
)
async def test_trial_constraint_prefix_cannot_hide_waiting_negation_or_explanation(
    tmp_path, constraint
):
    invoke, runs, store = chat_trial_fixture(
        tmp_path, "先跑一次每日收盘点评·执行流验收。" + constraint
    )
    with pytest.raises(StoreError) as failure:
        await invoke()
    assert failure.value.code == "automation_trial_not_requested"
    assert runs == {} and not store.data.get("automation_trial_requests")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constraint",
    [
        "按已批准定义写入和读回真实MD",
        "按当前要求生成Markdown文件",
        "不要改变模型和权限",
        "不修改日程和下次执行时间",
        "不要创建定时任务",
    ],
)
async def test_trial_accepts_only_complete_finite_constraints(tmp_path, constraint):
    invoke, runs, _store = chat_trial_fixture(
        tmp_path, "先跑一次每日收盘点评·执行流验收。" + constraint
    )
    assert (await invoke())["id"] == "run"
    assert len(runs) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constraint",
    [
        "按当前要求生成Markdown文件后等待确认",
        "不要联网但暂不启动",
        "不修改模型与权限直到我允许",
        "不要新增定时任务并等待用户确认",
        "按既有范围保存报告但只需解释",
    ],
)
async def test_trial_finite_constraint_rejects_unknown_or_appended_prose(tmp_path, constraint):
    invoke, runs, store = chat_trial_fixture(
        tmp_path, "先跑一次每日收盘点评·执行流验收。" + constraint
    )
    with pytest.raises(StoreError) as failure:
        await invoke()
    assert failure.value.code == "automation_trial_not_requested"
    assert runs == {} and not store.data.get("automation_trial_requests")
