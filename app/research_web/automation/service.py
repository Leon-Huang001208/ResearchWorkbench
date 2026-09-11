"""Persistent Automation orchestration over the existing native Claw runtime."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import os
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.observability import get_logger

from .models import AutomationCreate, AutomationError, AutomationUpdate
from .schedule import next_occurrence

log = get_logger(__name__)
ACTIVE_RESEARCH = {"queued", "running"}


def automation_feature_enabled() -> bool:
    return os.environ.get("RESEARCH_AUTOMATIONS_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _canonical_sha(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _id_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class AutomationService:
    """Keep Automation/Run JSON as the fact source and schedule only next fires."""

    def __init__(
        self,
        store,
        *,
        research=None,
        target_resolver=None,
        executor=None,
        dispatcher=None,
        channel_store=None,
        scheduler=None,
        now=None,
        sleep=asyncio.sleep,
    ) -> None:
        self.store = store
        self.research = research
        self.target_resolver = target_resolver or self._resolve_target
        self.executor = executor or self._execute_native
        self.dispatcher = dispatcher
        self.channel_store = channel_store
        self.channels = channel_store
        self.scheduler = scheduler
        self.now = now or (lambda: datetime.now(UTC))
        self.sleep = sleep
        self.tasks: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.store.data.setdefault("automations", {})
        self.store.data.setdefault("automation_runs", {})
        self.store.data.setdefault("delivery_channels", {})

    def _row(self, automation_id: str) -> dict:
        try:
            return self.store.data["automations"][automation_id]
        except KeyError as exc:
            raise AutomationError("Automation 不存在", "automation_not_found", 404) from exc

    def _run_row(self, run_id: str) -> dict:
        try:
            return self.store.data["automation_runs"][run_id]
        except KeyError as exc:
            raise AutomationError("Automation Run 不存在", "automation_run_not_found", 404) from exc

    @staticmethod
    def _public(value: dict) -> dict:
        return copy.deepcopy(value)

    def list(self) -> dict:
        rows = sorted(
            self.store.data["automations"].values(),
            key=lambda item: (item["name"].casefold(), item["id"]),
        )
        return {"items": [self._public(row) for row in rows]}

    def get(self, automation_id: str) -> dict:
        return self._public(self._row(automation_id))

    def list_runs(self, *, automation_id: str | None = None) -> dict:
        rows = [
            row
            for row in self.store.data["automation_runs"].values()
            if automation_id is None or row["automation_id"] == automation_id
        ]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return {"items": [self._public(row) for row in rows]}

    def create(self, body: AutomationCreate) -> dict:
        resolved = self.target_resolver(body.target_kind, body.target_id, body.target_version)
        if resolved["version"] != body.target_version or (
            body.target_sha256 is not None and resolved["sha256"] != body.target_sha256
        ):
            raise AutomationError("目标版本或内容哈希已变化", "target_version_conflict", 409)
        for tool in body.mcp_tools:
            if tool.risk_tier != "read_only" or not tool.allow_unattended:
                raise AutomationError(
                    "无人值守任务只允许显式批准自动运行的只读 MCP Tool",
                    "mcp_unattended_denied",
                    409,
                )
        self._validate_delivery(body.delivery.model_dump(mode="json"))
        automation_id = f"automation-{uuid4().hex}"
        payload = body.model_dump(mode="json")
        row = {
            "id": automation_id,
            "name": payload["name"],
            "target": {
                "kind": payload["target_kind"],
                "id": payload["target_id"],
                "version": payload["target_version"],
                "sha256": resolved["sha256"],
            },
            "input_template": payload["input_template"],
            "workspace_id": payload["workspace_id"],
            "output_formats": payload["output_formats"],
            "mcp_tools": payload["mcp_tools"],
            "schedule": payload["schedule"],
            "delivery": payload["delivery"],
            "enabled": False,
            "next_run_at": None,
            "last_run_id": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.store.data["automations"][automation_id] = row
        self.store.save()
        log.info(
            "automation_created",
            automation_id_digest=_id_digest(automation_id),
            status="disabled",
        )
        return self._public(row)

    def update(self, automation_id: str, body: AutomationUpdate) -> dict:
        row = self._row(automation_id)
        updates = body.model_dump(mode="json", exclude_none=True)
        if "delivery" in updates:
            self._validate_delivery(updates["delivery"])
        for field in ("name", "input_template", "output_formats", "schedule", "delivery"):
            if field in updates:
                row[field] = updates[field]
        row["updated_at"] = time.time()
        if row["enabled"] and "schedule" in updates:
            row["next_run_at"] = self._next_iso(row["schedule"], self.now())
        self.store.save()
        self._arm(row)
        log.info(
            "automation_updated",
            automation_id_digest=_id_digest(automation_id),
            status="updated",
        )
        return self._public(row)

    def delete(self, automation_id: str) -> dict:
        row = self._row(automation_id)
        if self._active_run(automation_id):
            raise AutomationError("Automation 正在运行", "automation_busy", 409)
        self._remove_job(automation_id)
        self.store.data["automations"].pop(automation_id)
        self.store.save()
        log.info(
            "automation_deleted",
            automation_id_digest=_id_digest(automation_id),
            status="deleted",
        )
        return {"deleted": True, "id": row["id"]}

    def enable(self, automation_id: str) -> dict:
        row = self._row(automation_id)
        self._validate_lock(row)
        self._validate_delivery(row.get("delivery", {}))
        row["enabled"] = True
        row["next_run_at"] = self._next_iso(row["schedule"], self.now())
        row["updated_at"] = time.time()
        self.store.save()
        self._arm(row)
        log.info(
            "automation_enabled",
            automation_id_digest=_id_digest(automation_id),
            status="enabled",
        )
        return self._public(row)

    def disable(self, automation_id: str) -> dict:
        row = self._row(automation_id)
        row["enabled"] = False
        row["next_run_at"] = None
        row["updated_at"] = time.time()
        self.store.save()
        self._remove_job(automation_id)
        log.info(
            "automation_disabled",
            automation_id_digest=_id_digest(automation_id),
            status="disabled",
        )
        return self._public(row)

    def _validate_lock(self, row: dict) -> dict:
        target = row["target"]
        try:
            resolved = self.target_resolver(target["kind"], target["id"], target["version"])
        except Exception as exc:
            raise AutomationError("锁定能力版本当前不可用", "blocked_version", 409) from exc
        if resolved["version"] != target["version"] or resolved["sha256"] != target["sha256"]:
            raise AutomationError("锁定能力版本当前不可用", "blocked_version", 409)
        return resolved

    def _active_run(self, automation_id: str) -> dict | None:
        return next(
            (
                row
                for row in self.store.data["automation_runs"].values()
                if row["automation_id"] == automation_id
                and row["research_status"] in ACTIVE_RESEARCH
            ),
            None,
        )

    def _validate_delivery(self, delivery: dict) -> None:
        channel_ids = delivery.get("channel_ids", [])
        if not channel_ids:
            return
        if self.channel_store is None or self.dispatcher is None:
            raise AutomationError("交付服务不可用", "delivery_unavailable", 503)
        for channel_id in channel_ids:
            channel = self.channel_store.get(channel_id)
            if not channel.get("enabled") or not channel.get("configured"):
                raise AutomationError("交付渠道未启用或未配置", "delivery_channel_unavailable", 409)

    def _new_run(
        self,
        automation_id: str,
        *,
        trigger: str,
        scheduled_for: str | None,
        retry_of: str | None,
        status: str,
    ) -> dict:
        run_id = f"automation-run-{uuid4().hex}"
        row = {
            "id": run_id,
            "automation_id": automation_id,
            "trigger": trigger,
            "scheduled_for": scheduled_for,
            "retry_of": retry_of,
            "session_id": None,
            "report_run_id": None,
            "research_status": status,
            "delivery_status": "not_requested",
            "failure_code": None,
            "delivery_failure_code": None,
            "delivery_attempts": 0,
            "summary": None,
            "artifacts": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.store.data["automation_runs"][run_id] = row
        self._row(automation_id)["last_run_id"] = run_id
        self.store.save()
        return row

    async def run(
        self,
        automation_id: str,
        *,
        trigger: str = "manual",
        scheduled_for: str | None = None,
        retry_of: str | None = None,
    ) -> dict:
        async with self.lock:
            automation = self._row(automation_id)
            if self._active_run(automation_id):
                return self._public(
                    self._new_run(
                        automation_id,
                        trigger=trigger,
                        scheduled_for=scheduled_for,
                        retry_of=retry_of,
                        status="skipped_overlap",
                    )
                )
            try:
                self._validate_lock(automation)
            except AutomationError:
                row = self._new_run(
                    automation_id,
                    trigger=trigger,
                    scheduled_for=scheduled_for,
                    retry_of=retry_of,
                    status="blocked_version",
                )
                row["failure_code"] = "blocked_version"
                self.store.save()
                return self._public(row)
            row = self._new_run(
                automation_id,
                trigger=trigger,
                scheduled_for=scheduled_for,
                retry_of=retry_of,
                status="queued",
            )
            task = asyncio.create_task(self._execute(row["id"]), name=f"automation-{row['id']}")
            self.tasks[row["id"]] = task
            return self._public(row)

    async def retry(self, run_id: str) -> dict:
        run = self._run_row(run_id)
        if run["research_status"] in ACTIVE_RESEARCH:
            raise AutomationError("运行仍在进行", "automation_run_busy", 409)
        return await self.run(run["automation_id"], trigger="retry", retry_of=run_id)

    async def _execute(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = self._row(row["automation_id"])
        row["research_status"] = "running"
        row["updated_at"] = time.time()
        self.store.save()
        try:
            result = self.executor(self._public(automation), self._public(row))
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, dict):
                raise TypeError("automation_executor_invalid")
            row.update(
                research_status=result.get("status", "completed"),
                session_id=result.get("session_id"),
                report_run_id=result.get("report_run_id"),
                summary=result.get("summary"),
                artifacts=result.get("artifacts", []),
                failure_code=result.get("failure_code"),
                updated_at=time.time(),
            )
            self.store.save()
            if row["research_status"] == "completed":
                try:
                    await self._deliver(automation, row)
                except Exception as exc:  # noqa: BLE001 - delivery must not alter research.
                    row.update(
                        delivery_status="failed",
                        delivery_failure_code=getattr(exc, "code", "delivery_failed"),
                        updated_at=time.time(),
                    )
                    self.store.save()
                    log.warning(
                        "automation_delivery_failed",
                        automation_id_digest=_id_digest(automation["id"]),
                        error_type=type(exc).__name__,
                    )
        except asyncio.CancelledError:
            if row.get("research_status") == "completed":
                row.update(
                    delivery_status="failed",
                    delivery_failure_code="service_stopped",
                    updated_at=time.time(),
                )
            else:
                row.update(
                    research_status="interrupted",
                    failure_code="service_stopped",
                    updated_at=time.time(),
                )
            self.store.save()
            raise
        except Exception as exc:  # noqa: BLE001 - persist every executor failure.
            row.update(
                research_status="failed",
                failure_code="research_failed",
                updated_at=time.time(),
            )
            self.store.save()
            log.error(
                "automation_run_failed",
                automation_id_digest=_id_digest(automation["id"]),
                error_type=type(exc).__name__,
            )
        finally:
            self.tasks.pop(run_id, None)

    async def _deliver(self, automation: dict, run: dict) -> None:
        channels = automation.get("delivery", {}).get("channel_ids", [])
        if not channels:
            run["delivery_status"] = "not_requested"
            self.store.save()
            return
        run["delivery_status"] = "pending"
        self.store.save()
        results = []
        event_id = f"automation-event-{run['id']}"
        event = {
            "event_id": event_id,
            "status": run["research_status"],
            "summary": run.get("summary") or "",
            "session_url": (
                f"/#/claw?session={run['session_id']}" if run.get("session_id") else None
            ),
        }
        if automation.get("delivery", {}).get("include_attachments"):
            event["attachments"] = run.get("artifacts", [])
        for channel_id in channels:
            try:
                channel = self.channel_store.get(channel_id)
                if not channel.get("enabled") or not channel.get("configured"):
                    raise AutomationError(
                        "交付渠道未启用或未配置", "delivery_channel_unavailable", 409
                    )
                results.append(await self.dispatcher.deliver(run, channel, event))
            except Exception as exc:  # noqa: BLE001 - isolate each configured channel.
                results.append(
                    {
                        "status": "failed",
                        "attempts": 0,
                        "failure_code": getattr(exc, "code", "delivery_failed"),
                    }
                )
        failed = [item for item in results if item["status"] != "delivered"]
        run["delivery_status"] = "failed" if failed else "delivered"
        run["delivery_failure_code"] = (
            (failed[0].get("failure_code") or "delivery_failed") if failed else None
        )
        run["delivery_attempts"] = max((item["attempts"] for item in results), default=0)
        self.store.save()

    async def wait_for_idle(self) -> None:
        tasks = list(self.tasks.values())
        if tasks:
            await asyncio.gather(*tasks)

    async def tick(self, now: datetime | None = None) -> None:
        now = now or self.now()
        due = [
            row
            for row in self.store.data["automations"].values()
            if row.get("enabled")
            and row.get("next_run_at")
            and datetime.fromisoformat(row["next_run_at"]) <= now
        ]
        for row in due:
            scheduled_for = row["next_run_at"]
            row["next_run_at"] = self._next_iso(row["schedule"], now)
            if row["next_run_at"] is None:
                row["enabled"] = False
            row["updated_at"] = time.time()
            self.store.save()
            await self.run(row["id"], trigger="schedule", scheduled_for=scheduled_for)
            self._arm(row)

    async def start(self) -> None:
        for run in list(self.store.data["automation_runs"].values()):
            if (
                run.get("research_status") == "completed"
                and run.get("delivery_status") == "pending"
            ):
                task = asyncio.create_task(
                    self._resume_delivery(run["id"]),
                    name=f"automation-delivery-resume-{run['id']}",
                )
                self.tasks[run["id"]] = task
                continue
            if run.get("research_status") not in ACTIVE_RESEARCH:
                continue
            if run.get("session_id") or run.get("report_run_id"):
                task = asyncio.create_task(
                    self._resume(run["id"]), name=f"automation-resume-{run['id']}"
                )
                self.tasks[run["id"]] = task
            else:
                run.update(
                    research_status="interrupted",
                    failure_code="service_restarted",
                    updated_at=time.time(),
                )
        self.store.save()
        await self.tick(self.now())
        if self.scheduler is None:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            self.scheduler = AsyncIOScheduler(timezone=UTC)
        if self.scheduler is not False:
            for row in self.store.data["automations"].values():
                self._arm(row)
            if not self.scheduler.running:
                self.scheduler.start()

    async def close(self) -> None:
        if self.scheduler not in (None, False) and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        for task in list(self.tasks.values()):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    def _arm(self, row: dict) -> None:
        if self.scheduler in (None, False):
            return
        self._remove_job(row["id"])
        if row.get("enabled") and row.get("next_run_at"):
            self.scheduler.add_job(
                self._scheduled_fire,
                "date",
                id=f"automation:{row['id']}",
                run_date=datetime.fromisoformat(row["next_run_at"]),
                args=[row["id"]],
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )

    def _remove_job(self, automation_id: str) -> None:
        if self.scheduler in (None, False):
            return
        try:
            self.scheduler.remove_job(f"automation:{automation_id}")
        except Exception as exc:  # noqa: BLE001 - APScheduler owns the exception.
            if type(exc).__name__ != "JobLookupError":
                log.warning(
                    "automation_schedule_remove_failed",
                    automation_id_digest=_id_digest(automation_id),
                    error_type=type(exc).__name__,
                )

    async def _scheduled_fire(self, automation_id: str) -> None:
        row = self._row(automation_id)
        due = row.get("next_run_at")
        if due:
            await self.tick(datetime.fromisoformat(due))

    @staticmethod
    def _next_iso(schedule: dict, after: datetime) -> str | None:
        from .models import AutomationSchedule

        value = next_occurrence(AutomationSchedule.model_validate(schedule), after)
        return value.isoformat() if value else None

    def _resolve_target(self, kind: str, target_id: str, version: int) -> dict:
        if self.research is None:
            raise AutomationError("研究服务不可用", "automation_unavailable", 503)
        if kind in {"skill", "workflow"}:
            selection = self.research.capabilities.selection(target_id, version)
            if selection["kind"] != kind:
                raise AutomationError("能力类型不匹配", "target_kind_conflict", 409)
            return {
                "version": selection["version"],
                "sha256": selection["sha256"],
                "formats": selection.get("default_formats", []),
            }
        manifest = self.research.report_workflows.catalog.manifest(target_id, version)
        payload = manifest.model_dump(mode="json")
        return {
            "version": version,
            "sha256": _canonical_sha(payload),
            "formats": payload.get("delivery", {}).get("formats", []),
        }

    @staticmethod
    def _legacy_schedule(value: dict) -> dict:
        kind = value.get("kind")
        if kind == "once":
            return {
                "kind": "once",
                "timezone": value.get("timezone") or "Asia/Shanghai",
                "once_at": value.get("once_at"),
            }
        if kind == "weekly":
            return {
                "kind": "weekly",
                "timezone": value.get("timezone") or "Asia/Shanghai",
                "weekday": value.get("weekday"),
                "hour": value.get("hour"),
                "minute": value.get("minute"),
            }
        raise AutomationError("旧报告日程不受支持", "schedule_migration_unsupported", 409)

    def preview_report_schedule_migrations(self) -> dict:
        if self.research is None:
            raise AutomationError("研究服务不可用", "automation_unavailable", 503)
        catalog = self.research.report_workflows.catalog
        items = []
        for workflow_id, row in catalog.data.get("workflows", {}).items():
            schedule = row.get("schedule") or {}
            version = row.get("current_version")
            if not schedule.get("enabled") or version is None:
                continue
            try:
                manifest = catalog.manifest(workflow_id, version)
                payload = manifest.model_dump(mode="json")
                normalized = self._legacy_schedule(schedule)
            except (AutomationError, OSError, ValueError, TypeError) as exc:
                items.append(
                    {
                        "workflow_id": workflow_id,
                        "eligible": False,
                        "reason": getattr(exc, "code", "schedule_migration_invalid"),
                    }
                )
                continue
            items.append(
                {
                    "workflow_id": workflow_id,
                    "name": payload.get("name") or workflow_id,
                    "version": version,
                    "schedule": normalized,
                    "eligible": True,
                }
            )
        return {"items": items}

    def apply_report_schedule_migrations(self, workflow_ids: Sequence[str]) -> dict:
        if self.research is None:
            raise AutomationError("研究服务不可用", "automation_unavailable", 503)
        catalog = self.research.report_workflows.catalog
        store_before = copy.deepcopy(self.store.data)
        catalog_before = copy.deepcopy(catalog.data)
        created_ids: list[str] = []
        migrated = []
        try:
            for workflow_id in workflow_ids:
                row = catalog.data.get("workflows", {}).get(workflow_id)
                if not row or not (row.get("schedule") or {}).get("enabled"):
                    raise AutomationError(
                        "旧报告日程不存在或未启用", "schedule_migration_not_found", 404
                    )
                version = row.get("current_version")
                if version is None:
                    raise AutomationError("旧报告日程没有可锁定版本", "blocked_version", 409)
                manifest = catalog.manifest(workflow_id, version)
                payload = manifest.model_dump(mode="json")
                body = AutomationCreate.model_validate(
                    {
                        "name": f"{payload.get('name') or workflow_id} · 自动运行",
                        "target_kind": "report_workflow",
                        "target_id": workflow_id,
                        "target_version": version,
                        "target_sha256": _canonical_sha(payload),
                        "input_template": f"执行锁定的报告 Workflow {workflow_id} v{version}",
                        "workspace_id": "research",
                        "output_formats": payload.get("delivery", {}).get("formats", []),
                        "mcp_tools": [],
                        "schedule": self._legacy_schedule(row["schedule"]),
                        "delivery": {"channel_ids": [], "include_attachments": False},
                    }
                )
                automation = self.create(body)
                created_ids.append(automation["id"])
                automation = self.enable(automation["id"])
                row["schedule"].update(
                    enabled=False,
                    next_run_at=None,
                    migrated_automation_id=automation["id"],
                )
                catalog._save()
                migrated.append({"workflow_id": workflow_id, "automation_id": automation["id"]})
        except Exception as exc:
            for automation_id in created_ids:
                self._remove_job(automation_id)
            self.store.data = store_before
            catalog.data = catalog_before
            self.store.save()
            catalog._save()
            log.warning("automation_schedule_migration_failed", error_type=type(exc).__name__)
            raise AutomationError(
                "旧报告日程迁移失败；原日程保持不变",
                "schedule_migration_failed",
                409,
            ) from exc
        log.info("automation_schedule_migrated", count=len(migrated), status="completed")
        return {"migrated": migrated}

    async def _resume(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = self._row(row["automation_id"])
        try:
            if row.get("session_id"):
                self._bind_mcp(row["session_id"], automation.get("mcp_tools", []))
                result = await self._monitor_session(row["session_id"])
            elif row.get("report_run_id"):
                result = await self._monitor_report_run(
                    row["report_run_id"], automation.get("mcp_tools", [])
                )
            else:
                raise RuntimeError("automation_resume_reference_missing")
            row.update(
                research_status=result["status"],
                summary=result.get("summary"),
                artifacts=result.get("artifacts", []),
                failure_code=result.get("failure_code"),
                updated_at=time.time(),
            )
            self.store.save()
            if row["research_status"] == "completed":
                await self._deliver(automation, row)
        except asyncio.CancelledError:
            if row.get("research_status") == "completed":
                row.update(
                    delivery_status="failed",
                    delivery_failure_code="service_stopped",
                    updated_at=time.time(),
                )
                self.store.save()
            raise
        except Exception as exc:  # noqa: BLE001 - unresolved recovery becomes interrupted.
            row.update(
                research_status="interrupted",
                failure_code="service_restarted",
                updated_at=time.time(),
            )
            self.store.save()
            log.warning("automation_resume_failed", error_type=type(exc).__name__)
        finally:
            self.tasks.pop(run_id, None)

    async def _resume_delivery(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = self._row(row["automation_id"])
        try:
            await self._deliver(automation, row)
        except asyncio.CancelledError:
            row.update(
                delivery_status="failed",
                delivery_failure_code="service_stopped",
                updated_at=time.time(),
            )
            self.store.save()
            raise
        except Exception as exc:  # noqa: BLE001 - persist delivery recovery failure.
            row.update(
                delivery_status="failed",
                delivery_failure_code=getattr(exc, "code", "delivery_failed"),
                updated_at=time.time(),
            )
            self.store.save()
            log.warning(
                "automation_delivery_resume_failed",
                automation_id_digest=_id_digest(automation["id"]),
                error_type=type(exc).__name__,
            )
        finally:
            self.tasks.pop(run_id, None)

    @staticmethod
    def _session_summary(detail: dict) -> str | None:
        messages = detail.get("messages") or []
        for item in reversed(messages):
            if item.get("role") == "assistant" and isinstance(item.get("text"), str):
                return item["text"][:4000]
        return None

    async def _monitor_session(self, session_id: str) -> dict:
        while True:
            detail = await self.research.detail(session_id)
            status = detail.get("status")
            if status == "completed":
                return {
                    "status": "completed",
                    "summary": self._session_summary(detail),
                    "artifacts": detail.get("files", []),
                }
            if status in {"failed", "cancelled", "interrupted", "disconnected"}:
                return {
                    "status": "failed" if status == "failed" else "interrupted",
                    "failure_code": f"session_{status}",
                }
            await self.sleep(1)

    async def _monitor_report_run(self, report_run_id: str, tools: Sequence[dict]) -> dict:
        bound_session = None
        while True:
            report = self.research.report_workflows.runtime._run(report_run_id)
            if report.get("session_id") and report["session_id"] != bound_session:
                self._bind_mcp(report["session_id"], tools)
                bound_session = report["session_id"]
            status = report.get("status")
            if status == "completed":
                return {
                    "status": "completed",
                    "session_id": report.get("session_id"),
                    "artifacts": report.get("artifacts", []),
                }
            if status not in {
                "queued",
                "preparing_data",
                "running",
                "blocked_approval",
                "validating",
            }:
                return {
                    "status": "failed" if status not in {"cancelled"} else "interrupted",
                    "failure_code": report.get("failure_code") or f"report_{status}",
                    "session_id": report.get("session_id"),
                }
            await self.sleep(1)

    def _bind_mcp(self, session_id: str, tools: Sequence[dict]) -> None:
        for tool in tools:
            self.research.mcp_runtime.authorize_session(
                session_id,
                **{
                    key: tool[key]
                    for key in (
                        "installation_id",
                        "version",
                        "tool_name",
                        "schema_sha256",
                    )
                },
            )
        if tools:
            self.research.mcp_runtime.register_automation_session(session_id, tools)

    async def _execute_native(self, automation: dict, run: dict) -> dict:
        if self.research is None:
            raise AutomationError("研究服务不可用", "automation_unavailable", 503)
        target = automation["target"]
        if target["kind"] == "report_workflow":
            report = await self.research.report_workflows.runtime.start_run(
                target["id"], trigger="automation", version=target["version"]
            )
            result = await self._monitor_report_run(report["id"], automation["mcp_tools"])
            return {
                **result,
                "session_id": result.get("session_id") or report.get("session_id"),
                "report_run_id": report["id"],
            }
        session = await self.research.create("claw", f"{automation['name']} · Automation")
        session_id = session["id"]
        self._bind_mcp(session_id, automation["mcp_tools"])
        await self.research.send(
            session_id,
            automation["input_template"],
            f"automation:{run['id']}",
            capability_id=target["id"],
            capability_version=target["version"],
            formats=automation["output_formats"],
        )
        result = await self._monitor_session(session_id)
        return {**result, "session_id": session_id}
