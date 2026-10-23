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
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import research_admission

from .models import AutomationCreate, AutomationError, AutomationUpdate
from .schedule import next_occurrence

log = get_logger(__name__)
ACTIVE_RESEARCH = {"queued", "running"}


def _definition_transaction(method):
    """Serialize synchronous definition CAS and snapshots, never native awaits."""

    @wraps(method)
    def locked(self, *args, **kwargs):
        with self.definition_lock:
            return method(self, *args, **kwargs)

    return locked


def automation_feature_enabled() -> bool:
    return os.environ.get("RESEARCH_AUTOMATIONS_ENABLED", "1").strip().lower() in {
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
        eligibility=None,
        resume_executor=None,
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
        self.eligibility = eligibility
        self.resume_executor = resume_executor
        self.now = now or (lambda: datetime.now(UTC))
        self.sleep = sleep
        self.tasks: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.definition_lock = RLock()
        self.store.data.setdefault("automations", {})
        self.store.data.setdefault("automation_runs", {})
        self.store.data.setdefault("delivery_channels", {})

    def _eligible(self, automation: dict) -> bool:
        """An optional tenant restriction cannot grant general Automation access."""
        if self.eligibility is None:
            return True
        try:
            return self.eligibility(automation) is True
        except Exception as exc:  # noqa: BLE001 - a scope probe always fails closed.
            log.warning("automation_scope_check_failed", error_type=type(exc).__name__)
            return False

    def _require_eligible(self, automation: dict) -> None:
        if not self._eligible(automation):
            raise AutomationError("该任务不在当前受限调度范围", "automation_scope_denied", 403)

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

    def _notify_research(self) -> None:
        notify = getattr(self.research, "notify", None)
        if callable(notify):
            try:
                notify()
            except Exception as exc:  # noqa: BLE001 - an observer cannot alter committed Run facts.
                log.warning("automation_projection_notify_failed", error_type=type(exc).__name__)

    @_definition_transaction
    def _persist_native_reference(self, run_id: str, **references: str | None) -> None:
        """Persist known references before any further native submission or wait."""
        row = self._run_row(run_id)
        before = copy.deepcopy(row)
        required = "report_run_id" if "report_run_id" in references else "session_id"
        if not isinstance(references.get(required), str) or not references[required]:
            raise AutomationError("缺少可信原生运行关联", "automation_reference_invalid", 409)
        for key, value in references.items():
            if key not in {"session_id", "report_run_id"} or (
                value is not None and not isinstance(value, str)
            ):
                raise AutomationError("原生运行关联无效", "automation_reference_invalid", 409)
            if value is not None and (not value or (row.get(key) and row[key] != value)):
                raise AutomationError("原生运行关联冲突", "automation_reference_conflict", 409)
        for key, value in references.items():
            if value is not None:
                row[key] = value
        row["updated_at"] = time.time()
        try:
            self.store.save()
        except Exception as exc:  # Do not submit after a failed checkpoint.
            row.clear()
            row.update(before)
            log.error("automation_reference_persistence_failed", error_type=type(exc).__name__)
            raise AutomationError(
                "原生运行关联保存失败；未继续提交研究",
                "automation_reference_persistence_failed",
                503,
            ) from exc
        log.info("automation_native_reference_saved", run_id_digest=_id_digest(run_id))
        self._notify_research()

    async def _checkpoint_report_reference(
        self, run_id: str, report: dict, *, newly_created: bool = False
    ) -> None:
        target = self._row(self._run_row(run_id)["automation_id"])["target"]
        if (
            target["kind"] != "report_workflow"
            or report.get("workflow_id") != target["id"]
            or type(report.get("version")) is not int
            or report["version"] != target["version"]
        ):
            raise AutomationError(
                "报告运行关联不属于锁定任务", "automation_reference_conflict", 409
            )
        try:
            self._persist_native_reference(
                run_id, report_run_id=report.get("id"), session_id=report.get("session_id")
            )
        except AutomationError as error:
            if (
                newly_created
                and error.code == "automation_reference_persistence_failed"
                and report.get("status")
                in {"queued", "preparing_data", "running", "blocked_approval", "validating"}
            ):
                try:
                    await self.research.report_workflows.runtime.cancel(report["id"])
                except Exception as exc:  # noqa: BLE001 - only this newly associated run.
                    log.error(
                        "automation_uncheckpointed_report_stop_failed",
                        error_type=type(exc).__name__,
                    )
            raise

    @staticmethod
    def _public(value: dict) -> dict:
        return copy.deepcopy(value)

    @_definition_transaction
    def list(self) -> dict:
        rows = sorted(
            self.store.data["automations"].values(),
            key=lambda item: (item["name"].casefold(), item["id"]),
        )
        return {"items": [self._public(row) for row in rows]}

    @_definition_transaction
    def get(self, automation_id: str) -> dict:
        return self._public(self._row(automation_id))

    @_definition_transaction
    def list_runs(self, *, automation_id: str | None = None) -> dict:
        rows = [
            row
            for row in self.store.data["automation_runs"].values()
            if automation_id is None or row["automation_id"] == automation_id
        ]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return {"items": [self._public(row) for row in rows]}

    @_definition_transaction
    def create(
        self, body: AutomationCreate, *, creation_key: str | None = None, before_save=None
    ) -> dict:
        creation_sha = _canonical_sha(body.model_dump(mode="json"))
        automation_id = (
            "automation-" + hashlib.sha256(creation_key.encode()).hexdigest()
            if creation_key is not None
            else f"automation-{uuid4().hex}"
        )
        existing = self.store.data["automations"].get(automation_id)
        if automation_id in self.store.data.get("automation_tombstones", {}):
            raise AutomationError("原日程已删除，不能重放创建确认", "draft_automation_deleted", 409)
        if existing is not None:
            if existing.get("creation_sha256") != creation_sha:
                raise AutomationError(
                    "确认内容与已保存任务不一致", "draft_confirmation_conflict", 409
                )
            return self._public(existing)
        resolved = self.resolve_definition(body)
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
        payload = body.model_dump(mode="json")
        row: dict[str, Any] = {
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
            "definition_version": 1,
        }
        if payload["research_task"] is not None:
            row["research_task"] = payload["research_task"]
            if hasattr(self.research, "model_profile_identity"):
                row["model_profile_id"] = self.research.model_profile_identity(
                    payload["research_task"]["model_provider"]
                )
        row["definition_revisions"] = [self._definition_snapshot(row)]
        if creation_key is not None:
            row["creation_sha256"] = creation_sha
        self.store.data["automations"][automation_id] = row
        rollback = None
        try:
            if before_save is not None:
                rollback = before_save(self._public(row))
            self.store.save()
        except Exception:
            self.store.data["automations"].pop(automation_id, None)
            if rollback is not None:
                rollback()
            log.error("automation_create_failed")
            raise
        log.info(
            "automation_created",
            automation_id_digest=_id_digest(automation_id),
            status="disabled",
        )
        return self._public(row)

    @staticmethod
    def _definition_snapshot(row: dict) -> dict:
        return copy.deepcopy(
            {
                key: row[key]
                for key in (
                    "id",
                    "name",
                    "target",
                    "input_template",
                    "workspace_id",
                    "output_formats",
                    "mcp_tools",
                    "schedule",
                    "delivery",
                    "research_task",
                    "model_profile_id",
                    "definition_version",
                )
                if key in row
            }
        )

    def resolve_definition(self, body: AutomationCreate) -> dict:
        if body.target_kind == "research_task":
            if body.research_task is None:
                raise AutomationError("研究定义缺失", "research_task_required", 409)
            self._validate_research_tools(body.research_task.approved_tools)
            return {
                "version": 1,
                "sha256": _canonical_sha(body.research_task.model_dump(mode="json")),
            }
        if body.target_id is None or body.target_version is None:
            raise AutomationError("能力版本缺失", "target_required", 409)
        return self.target_resolver(body.target_kind, body.target_id, body.target_version)

    @staticmethod
    def _validate_research_tools(tools: Sequence[str]) -> None:
        from ..capabilities.tools import SELECTABLE

        if any(tool not in SELECTABLE for tool in tools):
            raise AutomationError(
                "研究日程只能批准可选择的研究工具，不能授予管理或外部 MCP 权限",
                "automation_tool_scope_denied",
                409,
            )

    @_definition_transaction
    def update(
        self, automation_id: str, body: AutomationUpdate, *, mutation_key: str | None = None
    ) -> dict:
        row = self._row(automation_id)
        mutation_sha = _canonical_sha(body.model_dump(mode="json"))
        if mutation_key is not None:
            previous_mutation = next(
                (
                    revision
                    for revision in row.get("definition_revisions", [])
                    if revision.get("mutation_key") == mutation_key
                ),
                None,
            )
            if previous_mutation is not None:
                if previous_mutation.get("mutation_sha256") != mutation_sha:
                    raise AutomationError("确认内容已变化", "draft_confirmation_conflict", 409)
                return self._public(row)
        version = row.get("definition_version", 1)
        if (body.expected_version is not None and body.expected_version != version) or (
            row["target"]["kind"] == "research_task" and body.expected_version is None
        ):
            raise AutomationError(
                "日程定义版本已变化，请重新确认", "automation_version_conflict", 409
            )
        if body.research_task is not None and row["target"]["kind"] != "research_task":
            raise AutomationError("任务类型不能修改", "target_kind_conflict", 409)
        if body.research_task is not None:
            self._validate_research_tools(body.research_task.approved_tools)
        if (
            row["target"]["kind"] == "research_task"
            and body.input_template is not None
            and (
                body.research_task is None or body.input_template != body.research_task.description
            )
        ):
            raise AutomationError(
                "研究描述必须随定义确认", "research_task_description_conflict", 409
            )
        updates = body.model_dump(mode="json", exclude_none=True)
        if "research_task" in updates:
            updates["input_template"] = updates["research_task"]["description"]
        if "delivery" in updates:
            self._validate_delivery(updates["delivery"])
        previous = copy.deepcopy(row)
        if "definition_revisions" not in row:
            row["definition_version"] = version
            row["definition_revisions"] = [self._definition_snapshot(row)]
        for field in (
            "name",
            "input_template",
            "output_formats",
            "schedule",
            "delivery",
            "research_task",
        ):
            if field in updates:
                row[field] = updates[field]
        if "research_task" in updates:
            row["target"]["sha256"] = _canonical_sha(updates["research_task"])
            if hasattr(self.research, "model_profile_identity"):
                row["model_profile_id"] = self.research.model_profile_identity(
                    updates["research_task"]["model_provider"]
                )
        row["definition_version"] = version + 1
        revision = self._definition_snapshot(row)
        if mutation_key is not None:
            revision.update(mutation_key=mutation_key, mutation_sha256=mutation_sha)
        row["definition_revisions"].append(revision)
        row["updated_at"] = time.time()
        if row["enabled"] and "schedule" in updates:
            row["next_run_at"] = self._next_iso(row["schedule"], self.now())
        try:
            self.store.save()
            self._arm(row)
        except Exception:
            row.clear()
            row.update(previous)
            self.store.save()
            self._arm(row)
            log.error("automation_update_failed", automation_id_digest=_id_digest(automation_id))
            raise
        log.info(
            "automation_updated",
            automation_id_digest=_id_digest(automation_id),
            status="updated",
        )
        return self._public(row)

    @_definition_transaction
    def delete(self, automation_id: str) -> dict:
        row = self._row(automation_id)
        if self._active_run(automation_id):
            raise AutomationError("Automation 正在运行", "automation_busy", 409)
        self._remove_job(automation_id)
        self.store.data["automations"].pop(automation_id)
        tombstones = self.store.data.setdefault("automation_tombstones", {})
        tombstones[automation_id] = {"deleted_at": time.time()}
        try:
            self.store.save()
        except Exception:
            self.store.data["automations"][automation_id] = row
            tombstones.pop(automation_id, None)
            self._arm(row)
            log.error("automation_delete_failed", automation_id_digest=_id_digest(automation_id))
            raise
        log.info(
            "automation_deleted",
            automation_id_digest=_id_digest(automation_id),
            status="deleted",
        )
        return {"deleted": True, "id": row["id"]}

    @_definition_transaction
    def enable(self, automation_id: str, *, expected_version: int | None = None) -> dict:
        row = self._row(automation_id)
        self._require_eligible(row)
        if expected_version is not None and (
            type(expected_version) is not int
            or expected_version < 1
            or expected_version != row.get("definition_version")
        ):
            log.warning(
                "automation_enable_version_conflict", automation_id_digest=_id_digest(automation_id)
            )
            raise AutomationError(
                "日程定义版本已变化，请重新确认", "automation_version_conflict", 409
            )
        if row["enabled"]:
            return self._public(row)
        self._validate_lock(row)
        self._validate_delivery(row.get("delivery", {}))
        previous = copy.deepcopy(row)
        row["enabled"] = True
        row["next_run_at"] = self._next_iso(row["schedule"], self.now())
        row["updated_at"] = time.time()
        try:
            self.store.save()
            self._arm(row)
        except Exception:
            row.clear()
            row.update(previous)
            self._remove_job(automation_id)
            self.store.save()
            log.error("automation_enable_failed", automation_id_digest=_id_digest(automation_id))
            raise
        log.info(
            "automation_enabled",
            automation_id_digest=_id_digest(automation_id),
            status="enabled",
        )
        return self._public(row)

    @_definition_transaction
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

    @_definition_transaction
    def _validate_lock(self, row: dict) -> dict:
        target = row["target"]
        if target["kind"] == "research_task":
            from .models import ResearchTaskDefinition

            definition = ResearchTaskDefinition.model_validate(row.get("research_task"))
            self._validate_research_tools(definition.approved_tools)
            digest = _canonical_sha(definition.model_dump(mode="json"))
            if digest != target["sha256"]:
                raise AutomationError("研究定义已变化", "blocked_version", 409)
            return {"version": 1, "sha256": digest}
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

    @_definition_transaction
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
        row: dict[str, Any] = {
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
            "definition_version": self._row(automation_id).get("definition_version", 1),
            "definition_snapshot": self._definition_snapshot(self._row(automation_id)),
        }
        self.store.data["automation_runs"][run_id] = row
        self._row(automation_id)["last_run_id"] = run_id
        self.store.save()
        self._notify_research()
        return row

    @research_admission
    async def run(
        self,
        automation_id: str,
        *,
        trigger: str = "manual",
        scheduled_for: str | None = None,
        retry_of: str | None = None,
    ) -> dict:
        async with self.lock:
            row = self._admit_run(
                automation_id,
                trigger=trigger,
                scheduled_for=scheduled_for,
                retry_of=retry_of,
            )
            if row["research_status"] == "queued":
                task = asyncio.create_task(self._execute(row["id"]), name=f"automation-{row['id']}")
                self.tasks[row["id"]] = task
            return self._public(row)

    @_definition_transaction
    def _admit_run(self, automation_id, *, trigger, scheduled_for, retry_of):
        automation = self._row(automation_id)
        self._require_eligible(automation)
        status = "queued"
        if self._active_run(automation_id):
            status = "skipped_overlap"
        else:
            try:
                self._validate_lock(automation)
            except AutomationError:
                status = "blocked_version"
        row = self._new_run(
            automation_id,
            trigger=trigger,
            scheduled_for=scheduled_for,
            retry_of=retry_of,
            status=status,
        )
        if status == "blocked_version":
            row["failure_code"] = "blocked_version"
            self.store.save()
            self._notify_research()
        return row

    async def retry(self, run_id: str) -> dict:
        run = self._run_row(run_id)
        if run["research_status"] in ACTIVE_RESEARCH:
            raise AutomationError("运行仍在进行", "automation_run_busy", 409)
        return await self.run(run["automation_id"], trigger="retry", retry_of=run_id)

    @research_admission
    async def _execute(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = row.get("definition_snapshot") or self._row(row["automation_id"])
        row["research_status"] = "running"
        row["updated_at"] = time.time()
        self.store.save()
        self._notify_research()
        try:
            self._require_eligible(automation)
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
                research_status=(
                    "interrupted"
                    if getattr(exc, "code", None)
                    in {"native_submission_unconfirmed", "admission_unknown"}
                    else "failed"
                ),
                failure_code=getattr(exc, "code", "research_failed"),
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
            self._notify_research()

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

    @research_admission
    async def tick(self, now: datetime | None = None) -> None:
        now = now or self.now()
        due = [
            row
            for row in self.store.data["automations"].values()
            if row.get("enabled")
            and self._eligible(row)
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
            automation = self.store.data["automations"].get(run.get("automation_id"), {})
            if not self._eligible(automation):
                continue
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
        resident = os.environ.get("RESEARCH_RESIDENT_HOME")
        if resident and (Path(resident) / "transaction.json").exists():
            # Candidate startup must become healthy before the updater releases
            # admission. Retain this task so close() cancels it on rollback.
            self.tasks["resident-startup-tick"] = asyncio.create_task(self.tick(self.now()))
        else:
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
        if not self._eligible(row):
            return
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
        if not self._eligible(row):
            return
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

    @_definition_transaction
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

    @_definition_transaction
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

    @research_admission
    async def _resume(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = row.get("definition_snapshot") or self._row(row["automation_id"])
        try:
            self._require_eligible(automation)
            if self.resume_executor is not None:
                resumed = self.resume_executor(run_id)
                if resumed is not None:
                    await resumed
                    return
            if row.get("report_run_id"):
                if automation["target"]["kind"] != "report_workflow":
                    raise AutomationError(
                        "原生运行关联类型不匹配", "automation_reference_conflict", 409
                    )
                result = await self._monitor_report_run(
                    row["report_run_id"],
                    automation.get("mcp_tools", []),
                    expected_target=automation["target"],
                    automation_run_id=run_id,
                )
            elif row.get("session_id"):
                if automation["target"]["kind"] == "report_workflow":
                    raise AutomationError("缺少报告运行关联", "automation_reference_conflict", 409)
                detail = await self.research.detail(row["session_id"])
                if detail.get("status") not in {
                    "running",
                    "queued",
                    "pending",
                    "waiting",
                    "waiting_input",
                    "waiting_approval",
                    "awaiting_approval",
                    "busy",
                    "cancelling",
                    "completed",
                    "incomplete",
                    "blocked",
                    "failed",
                    "cancelled",
                    "interrupted",
                    "disconnected",
                }:
                    raise AutomationError(
                        "原生任务提交尚未得到证据确认；未重新发送",
                        "native_submission_unconfirmed",
                        409,
                    )
                self._bind_mcp(row["session_id"], automation.get("mcp_tools", []))
                result = await self._monitor_session(row["session_id"], initial=detail)
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
                failure_code=getattr(exc, "code", "service_restarted"),
                updated_at=time.time(),
            )
            self.store.save()
            log.warning("automation_resume_failed", error_type=type(exc).__name__)
        finally:
            self.tasks.pop(run_id, None)
            self._notify_research()

    async def _resume_delivery(self, run_id: str) -> None:
        row = self._run_row(run_id)
        automation = row.get("definition_snapshot") or self._row(row["automation_id"])
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
            self._notify_research()

    @staticmethod
    def _session_summary(detail: dict) -> str | None:
        messages = detail.get("messages") or []
        for item in reversed(messages):
            if item.get("role") == "assistant" and isinstance(item.get("text"), str):
                return item["text"][:4000]
        return None

    async def _monitor_session(self, session_id: str, *, initial: dict | None = None) -> dict:
        while True:
            detail = initial if initial is not None else await self.research.detail(session_id)
            initial = None
            status = detail.get("status")
            if detail.get("execution_restricted") is True:
                log.warning("automation_native_child_state_unverified")
                return {
                    "status": "failed",
                    "failure_code": "native_child_state_unverified",
                    "summary": self._session_summary(detail),
                    "artifacts": detail.get("files", []),
                }
            if status == "completed":
                return {
                    "status": "completed",
                    "summary": self._session_summary(detail),
                    "artifacts": detail.get("files", []),
                }
            if status in {"incomplete", "blocked"} and detail.get("can_cancel") is not True:
                log.warning("automation_session_terminal_incomplete", status=status)
                return {
                    "status": "failed",
                    "failure_code": f"session_{status}",
                    "summary": self._session_summary(detail),
                    "artifacts": detail.get("files", []),
                }
            if status in {"failed", "cancelled", "interrupted", "disconnected"}:
                return {
                    "status": "failed" if status == "failed" else "interrupted",
                    "failure_code": f"session_{status}",
                }
            await self.sleep(1)

    async def _monitor_report_run(
        self,
        report_run_id: str,
        tools: Sequence[dict],
        *,
        expected_target: dict | None = None,
        automation_run_id: str | None = None,
    ) -> dict:
        bound_session = None
        while True:
            report = self.research.report_workflows.runtime._run(report_run_id)
            if expected_target is not None and (
                report.get("id") != report_run_id
                or report.get("workflow_id") != expected_target["id"]
                or report.get("version") != expected_target["version"]
            ):
                raise AutomationError(
                    "报告运行不属于锁定任务", "automation_reference_conflict", 409
                )
            if report.get("session_id") and report["session_id"] != bound_session:
                if automation_run_id is not None:
                    await self._checkpoint_report_reference(automation_run_id, report)
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
            runtime = self.research.report_workflows.runtime
            existing_reports = set(runtime.catalog.data["runs"])
            returned = await runtime.start_run(
                target["id"], trigger="automation", version=target["version"]
            )
            report_id = returned.get("id")
            if not isinstance(report_id, str) or not report_id:
                raise AutomationError("缺少可信报告运行关联", "automation_reference_invalid", 409)
            if report_id in existing_reports or report_id not in runtime.catalog.data["runs"]:
                raise AutomationError(
                    "报告运行未证明为本次创建", "automation_reference_conflict", 409
                )
            report = runtime._run(report_id)
            if report.get("id") != report_id or report.get("trigger") != "automation":
                raise AutomationError("报告运行归属无法确认", "automation_reference_conflict", 409)
            await self._checkpoint_report_reference(run["id"], report, newly_created=True)
            result = await self._monitor_report_run(
                report["id"],
                automation["mcp_tools"],
                expected_target=target,
                automation_run_id=run["id"],
            )
            return {
                **result,
                "session_id": result.get("session_id") or report.get("session_id"),
                "report_run_id": report["id"],
            }
        if target["kind"] == "research_task":
            session = await self.research.create_automation_research_session(
                automation["name"],
                automation["research_task"],
                **(
                    {"model_profile_id": automation["model_profile_id"]}
                    if "model_profile_id" in automation
                    else {}
                ),
            )
        else:
            session = await self.research.create("claw", f"{automation['name']} · Automation")
        session_id = session.get("id")
        self._persist_native_reference(run["id"], session_id=session_id)
        self._bind_mcp(session_id, automation["mcp_tools"])
        arguments = {"formats": automation["output_formats"]}
        prompt = automation["input_template"]
        if target["kind"] == "research_task":
            arguments["tool_ids"] = automation["research_task"]["approved_tools"]
            prompt += "\n\n输出要求：" + automation["research_task"]["output_requirements"]
            timezone = automation["schedule"]["timezone"]
            executed_at = self.now().astimezone(ZoneInfo(timezone))
            formats = ", ".join(automation["output_formats"]) or "仅对话回复（未请求文件格式）"
            prompt += (
                f"\n\n本次实际执行时间：{executed_at.isoformat()}；时区：{timezone}。"
                "“今日”以该实际执行日期为准，不得沿用历史样例日期。"
                "收盘前执行时不得声称当日已经收盘；交易状态与数据日期须依实际可核对来源标注，"
                "无法核实时明确写未取得或受限，不得编造收盘数据。"
                f"\n只生成明确请求的文件格式：{formats}；文件写入本会话 outputs/ 目录。"
                "不得额外生成未请求的格式；不得枚举 cwd 或宿主目录、扫描主机文件、"
                "读取会话范围外的文件。仅使用已批准资料范围及工具完成任务。"
            )
            if (
                automation["output_formats"]
                and "research_run_script" in automation["research_task"]["approved_tools"]
            ):
                prompt += (
                    "\n文件交付顺序：完成必要取证后，立即调用 research_run_script 生成实际文件，"
                    "再用同一工具读回核对内容，最后才发最终答复。"
                    "联网检索控制在四轮内；取不到的专业数据写明缺口，不要反复重试不可用工具。"
                    "Markdown 可直接用 Path('outputs/报告.md').write_text(完整正文, encoding='utf-8')。"
                    "所有请求章节应有真实内容或具体缺口；不要写空白占位文件。"
                    "没有收到生成工具的成功结果就不能宣称文件已交付，也不能以‘现在生成文件’的承诺结束。"
                )
        else:
            arguments.update(capability_id=target["id"], capability_version=target["version"])
        admission = await self.research.send(
            session_id,
            prompt,
            f"automation:{run['id']}",
            **arguments,
        )
        if not isinstance(admission, dict) or admission.get("accepted") is not True:
            raise AutomationError(
                "原生任务提交尚未确认；未继续监控或重新发送",
                "native_submission_unconfirmed",
                409,
            )
        result = await self._monitor_session(session_id)
        return {**result, "session_id": session_id}
