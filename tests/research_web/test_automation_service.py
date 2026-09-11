from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.research_web.automation.models import AutomationCreate, AutomationError
from app.research_web.automation.service import AutomationService
from app.research_web.store import Store


def automation_body(**updates):
    value = {
        "name": "每日公司研究",
        "target_kind": "skill",
        "target_id": "company-research",
        "target_version": 2,
        "target_sha256": "a" * 64,
        "input_template": "研究华安基金，并仅使用锁定资料。",
        "workspace_id": "research",
        "output_formats": ["md"],
        "mcp_tools": [],
        "schedule": {
            "kind": "daily",
            "timezone": "Asia/Shanghai",
            "hour": 9,
            "minute": 0,
        },
        "delivery": {"channel_ids": [], "include_attachments": False},
    }
    value.update(updates)
    return AutomationCreate.model_validate(value)


@pytest.mark.asyncio
async def test_create_locks_resolved_version_and_is_disabled(tmp_path):
    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda _kind, _id, _version: {
            "version": 2,
            "sha256": "a" * 64,
            "formats": ["md"],
        },
        executor=lambda *_args, **_kwargs: None,
        scheduler=False,
        now=lambda: datetime(2026, 9, 11, tzinfo=UTC),
    )

    created = service.create(automation_body())

    assert created["enabled"] is False
    assert created["target"] == {
        "kind": "skill",
        "id": "company-research",
        "version": 2,
        "sha256": "a" * 64,
    }
    assert created["next_run_at"] is None


@pytest.mark.asyncio
async def test_tick_coalesces_all_missed_times_into_one_latest_run(tmp_path):
    executions = []

    async def execute(automation, run):
        executions.append((automation["id"], run["scheduled_for"]))
        return {"status": "completed", "session_id": "session-1", "summary": "done"}

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=execute,
        scheduler=False,
        now=lambda: datetime(2026, 9, 11, 1, tzinfo=UTC),
    )
    created = service.create(automation_body())
    service.enable(created["id"])
    service.store.data["automations"][created["id"]]["next_run_at"] = "2026-09-01T01:00:00+00:00"
    service.store.save()

    await service.tick(datetime(2026, 9, 11, 2, tzinfo=UTC))
    await service.wait_for_idle()

    runs = service.list_runs()["items"]
    assert len(runs) == 1
    assert len(executions) == 1
    assert runs[0]["trigger"] == "schedule"
    assert service.get(created["id"])["next_run_at"] > "2026-09-11T02:00:00"


@pytest.mark.asyncio
async def test_overlap_is_recorded_without_starting_second_execution(tmp_path):
    gate = __import__("asyncio").Event()

    async def execute(_automation, _run):
        await gate.wait()
        return {"status": "completed", "session_id": "session-1"}

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=execute,
        scheduler=False,
    )
    created = service.create(automation_body())
    first = await service.run(created["id"])
    second = await service.run(created["id"])
    gate.set()
    await service.wait_for_idle()

    assert first["research_status"] == "queued"
    assert second["research_status"] == "skipped_overlap"


@pytest.mark.asyncio
async def test_version_drift_blocks_run_and_manual_retry_keeps_link(tmp_path):
    current_sha = "b" * 64
    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": current_sha},
        executor=lambda *_args: None,
        scheduler=False,
    )
    created = service.create(automation_body(target_sha256=current_sha))
    current_sha = "c" * 64

    blocked = await service.run(created["id"])
    retried = await service.retry(blocked["id"])

    assert blocked["research_status"] == "blocked_version"
    assert retried["research_status"] == "blocked_version"
    assert retried["retry_of"] == blocked["id"]


def test_scheduled_run_rejects_mcp_tool_without_unattended_read_permission(tmp_path):
    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=lambda *_args: None,
        scheduler=False,
    )
    body = automation_body(
        mcp_tools=[
            {
                "installation_id": "mcp-installation-" + "1" * 32,
                "version": "1.0.0",
                "tool_name": "read_weather",
                "schema_sha256": "b" * 64,
                "risk_tier": "read_only",
                "allow_unattended": False,
            }
        ]
    )

    with pytest.raises(AutomationError, match="无人值守"):
        service.create(body)


def test_create_rejects_missing_or_disabled_delivery_channels(tmp_path):
    class Channels:
        def get(self, channel_id):
            if channel_id == "delivery-disabled":
                return {"id": channel_id, "enabled": False, "configured": True}
            raise AutomationError("交付渠道不存在", "delivery_channel_not_found", 404)

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=lambda *_args: None,
        channel_store=Channels(),
        dispatcher=SimpleNamespace(deliver=None),
        scheduler=False,
    )

    for channel_id in ("delivery-missing", "delivery-disabled"):
        with pytest.raises(AutomationError, match="交付渠道"):
            service.create(
                automation_body(
                    delivery={"channel_ids": [channel_id], "include_attachments": False}
                )
            )


@pytest.mark.asyncio
async def test_delivery_failure_never_changes_completed_research_result(tmp_path):
    class Channels:
        def get(self, _channel_id):
            raise AutomationError("交付渠道不可用", "delivery_channel_not_found", 404)

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=lambda *_args: {
            "status": "completed",
            "session_id": "session-1",
            "summary": "完成",
        },
        channel_store=Channels(),
        dispatcher=SimpleNamespace(deliver=None),
        scheduler=False,
    )
    created = service.create(automation_body())
    service.store.data["automations"][created["id"]]["delivery"] = {
        "channel_ids": ["delivery-missing"],
        "include_attachments": False,
    }

    await service.run(created["id"])
    await service.wait_for_idle()

    run = service.list_runs()["items"][0]
    assert run["research_status"] == "completed"
    assert run["delivery_status"] == "failed"
    assert run["delivery_failure_code"] == "delivery_channel_not_found"


@pytest.mark.asyncio
async def test_service_stop_during_delivery_keeps_completed_research_result(tmp_path):
    entered = asyncio.Event()

    class Channels:
        def get(self, channel_id):
            return {"id": channel_id, "enabled": True, "configured": True}

    class Dispatcher:
        async def deliver(self, _run, _channel, _event):
            entered.set()
            await asyncio.Event().wait()

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=lambda *_args: {"status": "completed", "session_id": "session-1"},
        channel_store=Channels(),
        dispatcher=Dispatcher(),
        scheduler=False,
    )
    created = service.create(
        automation_body(delivery={"channel_ids": ["delivery-1"], "include_attachments": False})
    )

    await service.run(created["id"])
    await entered.wait()
    await service.close()

    run = service.list_runs()["items"][0]
    assert run["research_status"] == "completed"
    assert run["delivery_status"] == "failed"
    assert run["delivery_failure_code"] == "service_stopped"


@pytest.mark.asyncio
async def test_start_resumes_pending_delivery_without_rerunning_research(tmp_path):
    delivered = []

    class Channels:
        def get(self, channel_id):
            return {"id": channel_id, "enabled": True, "configured": True}

    class Dispatcher:
        async def deliver(self, run, channel, event):
            delivered.append((run["id"], channel["id"], event["event_id"]))
            return {"status": "delivered", "attempts": 1, "failure_code": None}

    service = AutomationService(
        Store(tmp_path),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        executor=lambda *_args: pytest.fail("completed research must not rerun"),
        channel_store=Channels(),
        dispatcher=Dispatcher(),
        scheduler=False,
    )
    created = service.create(
        automation_body(delivery={"channel_ids": ["delivery-1"], "include_attachments": False})
    )
    run = service._new_run(
        created["id"], trigger="schedule", scheduled_for=None, retry_of=None, status="completed"
    )
    run.update(session_id="session-existing", delivery_status="pending")
    service.store.save()

    await service.start()
    await service.wait_for_idle()

    restored = service.list_runs()["items"][0]
    assert restored["research_status"] == "completed"
    assert restored["delivery_status"] == "delivered"
    assert delivered == [(run["id"], "delivery-1", f"automation-event-{run['id']}")]


@pytest.mark.asyncio
async def test_start_resumes_confirmed_running_session_and_completes(tmp_path):
    store = Store(tmp_path)
    details = iter(
        [
            {"status": "running", "can_cancel": True},
            {
                "status": "completed",
                "can_cancel": False,
                "messages": [{"role": "assistant", "text": "完成摘要"}],
            },
        ]
    )

    class Research:
        async def detail(self, _session_id):
            return next(details)

    service = AutomationService(
        store,
        research=Research(),
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
        scheduler=False,
        sleep=lambda _delay: __import__("asyncio").sleep(0),
    )
    created = service.create(automation_body())
    run = service._new_run(
        created["id"], trigger="manual", scheduled_for=None, retry_of=None, status="running"
    )
    run["session_id"] = "session-existing"
    store.save()

    await service.start()
    await service.wait_for_idle()

    resumed = service.list_runs()["items"][0]
    assert resumed["research_status"] == "completed"
    assert resumed["summary"] == "完成摘要"


def test_report_schedule_migration_saves_automation_before_disabling_legacy(tmp_path):
    store = Store(tmp_path)
    manifest = SimpleNamespace(
        model_dump=lambda mode="json": {
            "workflow_id": "weekly-report",
            "name": "周报",
            "version": 3,
            "delivery": {"formats": ["docx"]},
        }
    )
    catalog = SimpleNamespace(
        data={
            "workflows": {
                "weekly-report": {
                    "current_version": 3,
                    "schedule": {
                        "kind": "weekly",
                        "enabled": True,
                        "timezone": "Asia/Shanghai",
                        "weekday": 4,
                        "hour": 18,
                        "minute": 0,
                        "next_run_at": "2026-09-11T10:00:00+00:00",
                    },
                }
            }
        },
        manifest=lambda _workflow_id, _version: manifest,
        _save=lambda: None,
    )
    research = SimpleNamespace(report_workflows=SimpleNamespace(catalog=catalog))
    service = AutomationService(store, research=research, scheduler=False)

    preview = service.preview_report_schedule_migrations()
    applied = service.apply_report_schedule_migrations(["weekly-report"])

    assert preview["items"][0]["workflow_id"] == "weekly-report"
    automation = service.list()["items"][0]
    assert automation["target"]["version"] == 3
    assert automation["enabled"] is True
    assert catalog.data["workflows"]["weekly-report"]["schedule"]["enabled"] is False
    assert applied["migrated"][0]["automation_id"] == automation["id"]


def test_report_schedule_migration_rolls_back_both_indexes_on_failure(tmp_path):
    store = Store(tmp_path)
    catalog = SimpleNamespace(
        data={
            "workflows": {
                "broken": {
                    "current_version": 1,
                    "schedule": {
                        "kind": "weekly",
                        "enabled": True,
                        "timezone": "Asia/Shanghai",
                        "weekday": 0,
                        "hour": 9,
                        "minute": 0,
                    },
                }
            }
        },
        manifest=lambda *_args: (_ for _ in ()).throw(OSError("unavailable")),
        _save=lambda: None,
    )
    before = deepcopy(catalog.data)
    service = AutomationService(
        store,
        research=SimpleNamespace(report_workflows=SimpleNamespace(catalog=catalog)),
        scheduler=False,
    )

    with pytest.raises(AutomationError, match="迁移失败"):
        service.apply_report_schedule_migrations(["broken"])

    assert service.list()["items"] == []
    assert catalog.data == before
