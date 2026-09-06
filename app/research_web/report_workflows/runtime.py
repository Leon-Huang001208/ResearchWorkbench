"""Persistent report Workflow scheduler delegating execution to native Claw."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import shutil
import threading
import time
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

from ..delivery import FINAL
from .models import RefreshStatus, WorkflowError, WorkflowSchedule

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
ACTIVE = {"queued", "preparing_data", "running", "blocked_approval", "validating"}


class ReportWorkflowRuntime:
    def __init__(self, service, catalog, refresh) -> None:
        self.service = service
        self.catalog = catalog
        self.refresh = refresh
        self.tasks: dict[str, asyncio.Task] = {}
        self.cancellations: dict[str, threading.Event] = {}
        self.scheduler_task: asyncio.Task | None = None
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        self.scheduler_task = asyncio.create_task(
            self._scheduler(), name="report-workflow-scheduler"
        )

    async def close(self) -> None:
        if self.scheduler_task:
            self.scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.scheduler_task
        tasks = list(self.tasks.values())
        for cancellation in self.cancellations.values():
            cancellation.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _run(self, run_id: str) -> dict:
        with self.catalog._exclusive():
            try:
                return copy.deepcopy(self.catalog.data["runs"][run_id])
            except KeyError as exc:
                raise WorkflowError("报告运行不存在", "run_not_found", 404) from exc

    def _update_run(self, run_id: str, **updates) -> dict:
        with self.catalog._exclusive():
            try:
                row = self.catalog.data["runs"][run_id]
            except KeyError as exc:
                raise WorkflowError("报告运行不存在", "run_not_found", 404) from exc
            row.update(updates, updated_at=time.time())
            self.catalog._save()
            return copy.deepcopy(row)

    def _append_refresh_manifest(self, run_id: str, path: str) -> dict:
        with self.catalog._exclusive():
            try:
                row = self.catalog.data["runs"][run_id]
            except KeyError as exc:
                raise WorkflowError("报告运行不存在", "run_not_found", 404) from exc
            manifests = row.setdefault("refresh_manifests", [])
            if path not in manifests:
                manifests.append(path)
            row["updated_at"] = time.time()
            self.catalog._save()
            return copy.deepcopy(row)

    def run_path(self, run_id: str) -> Path:
        row = self._run(run_id)
        root = self.catalog.root / "runs"
        path = Path(row["path"])
        if (
            path.is_symlink()
            or not path.is_dir()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise WorkflowError("报告运行目录不可读取", "unsafe_run_directory", 409)
        return path

    def assert_not_active(self, workflow_id: str) -> None:
        with self.catalog._exclusive():
            if any(
                row.get("workflow_id") == workflow_id and row.get("status") in ACTIVE
                for row in self.catalog.data["runs"].values()
            ):
                raise WorkflowError(
                    "Workflow 正在运行；当前运行继续使用锁定版本",
                    "workflow_busy",
                    409,
                )

    def _new_run(
        self, run_id: str, workflow_id: str, version: int, trigger: str, status: str
    ) -> dict:
        row = {
            "id": run_id,
            "workflow_id": workflow_id,
            "version": version,
            "trigger": trigger,
            "status": status,
            "delivery_status": "pending",
            "session_id": None,
            "refresh_manifests": [],
            "artifacts": [],
            "missing": [],
            "failure_code": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "path": str(self.catalog.root / "runs" / run_id),
        }
        with self.catalog._exclusive():
            self.catalog.data["runs"][run_id] = row
            self.catalog._save()
        return copy.deepcopy(row)

    @staticmethod
    def public_run(row: dict) -> dict:
        return {key: value for key, value in row.items() if key != "path"}

    def runs(self, workflow_id: str) -> list[dict]:
        with self.catalog._exclusive():
            self.catalog._row(workflow_id)
            rows = [
                copy.deepcopy(item)
                for item in self.catalog.data["runs"].values()
                if item.get("workflow_id") == workflow_id
            ]
        return [
            self.public_run(row)
            for row in sorted(rows, key=lambda item: item["created_at"], reverse=True)
        ]

    async def start_run(
        self, workflow_id: str, *, trigger: str = "manual", version: int | None = None
    ) -> dict:
        async with self.lock:
            with self.catalog._exclusive():
                workflow = self.catalog._row(workflow_id)
                selected = version or workflow.get("current_version")
                if selected is None or not workflow.get("versions", {}).get(str(selected), {}).get(
                    "published"
                ):
                    raise WorkflowError("Workflow 尚无已发布版本", "version_required", 409)
                if workflow.get("status", "enabled") == "disabled":
                    raise WorkflowError("Workflow 已停用", "workflow_disabled", 409)
                run_id = uuid4().hex
                if any(
                    item.get("workflow_id") == workflow_id and item.get("status") in ACTIVE
                    for item in self.catalog.data["runs"].values()
                ):
                    return self.public_run(
                        self._new_run(run_id, workflow_id, selected, trigger, "skipped_overlap")
                    )
                workspace = self.catalog.create_run_workspace(workflow_id, selected)
                run_id = workspace["run_id"]
                row = self.catalog.data["runs"][run_id]
                row.update(
                    id=run_id,
                    trigger=trigger,
                    status="queued",
                    delivery_status="pending",
                    session_id=None,
                    refresh_manifests=[],
                    artifacts=[],
                    missing=[],
                    failure_code=None,
                    created_at=time.time(),
                    updated_at=time.time(),
                )
                workflow = self.catalog._row(workflow_id)
                workflow["latest_run"] = run_id
                self.catalog._save()
                public = self.public_run(copy.deepcopy(row))
            self.cancellations[run_id] = threading.Event()
            self.tasks[run_id] = asyncio.create_task(
                self._execute(run_id), name=f"report-workflow-{run_id}"
            )
            return public

    async def _execute(self, run_id: str) -> None:
        run = self._run(run_id)
        try:
            run = self._update_run(run_id, status="preparing_data")
            manifest = self.catalog.manifest(run["workflow_id"], run["version"])
            for policy in manifest.workbook_policies:
                result = await self._refresh_workbook(run_id, policy.workbook)
                if result.status is not RefreshStatus.READY:
                    self._update_run(
                        run_id,
                        status="blocked_data",
                        failure_code=result.code or "workbook_refresh_failed",
                        missing=[policy.workbook],
                    )
                    return
                run = self._append_refresh_manifest(run_id, result.manifest_path)
            session = await self.service.create("claw", f"{manifest.name} · 报告 Workflow")
            sid = session["id"]
            run = self._update_run(run_id, session_id=sid)
            session_row = self.service.store.session(sid)
            session_row["report_workflow"] = {
                "workflow_id": run["workflow_id"],
                "version": run["version"],
                "run_id": run_id,
            }
            target = self.service.store.directory(sid) / "inputs" / "report-workflow"
            shutil.copytree(self.run_path(run_id), target, dirs_exist_ok=True)
            context = {
                "workflow_id": run["workflow_id"],
                "version": run["version"],
                "run_id": run_id,
                "delivery": json.loads(manifest.delivery.model_dump_json()),
                "blocks": json.loads(
                    json.dumps([json.loads(block.model_dump_json()) for block in manifest.blocks])
                ),
                "refresh_manifests": [Path(path).name for path in run["refresh_manifests"]],
            }
            (target / "run-context.json").write_text(
                json.dumps(context, ensure_ascii=False, indent=2)
            )
            self.service.store.save()
            await self.service.send(
                sid,
                (
                    f"执行锁定的 Report Workflow《{manifest.name}》v{run['version']}。"
                    "先读取 inputs/report-workflow/run-context.json、workflow.yaml、模板和已刷新底稿；"
                    "复杂报告至少使用两个原生子 Agent，共享同一底稿快照。"
                    "按命名占位符组装文件并执行交付检查，不调用旧报告执行链。"
                ),
                f"report-workflow-{run_id}",
                formats=[item.value for item in manifest.delivery.formats],
                capability_id="report-production-workflow",
            )
            self._update_run(run_id, status="running")
            self.service.store.audit(
                "report_workflow", "started", session_id=sid, report_run_id=run_id
            )
            wait = self._wait_for_delivery(run_id)
            if inspect.isawaitable(wait):
                await wait
        except asyncio.CancelledError:
            if run.get("session_id"):
                with suppress(Exception):
                    await self.service.cancel(run["session_id"])
            self._update_run(run_id, status="cancelled", delivery_status="incomplete")
            raise
        except Exception as exc:  # noqa: BLE001 - background boundary fails closed.
            log.error("report_workflow_run_failed", error_type=type(exc).__name__)
            self._update_run(run_id, status="failed", failure_code="report_execution_failed")
        finally:
            self.tasks.pop(run_id, None)
            self.cancellations.pop(run_id, None)

    async def _refresh_workbook(self, run_id: str, workbook: str):
        """Keep the event loop responsive and wait for bounded worker cleanup on cancel."""

        cancellation = self.cancellations.setdefault(run_id, threading.Event())
        worker = asyncio.create_task(
            asyncio.to_thread(
                self.catalog.refresh_workbook,
                run_id,
                workbook,
                refresh_service=self.refresh,
                cancellation_event=cancellation,
            ),
            name=f"report-workbook-refresh-{run_id}",
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancellation.set()
            # The core terminates the provider process group and reported Excel
            # children. Cancellation is complete only after that cleanup returns.
            with suppress(Exception):
                await worker
            raise

    async def _wait_for_delivery(self, run_id: str) -> None:
        run = self._run(run_id)
        for _ in range(7200):
            await asyncio.sleep(1)
            detail = await self.service.detail(run["session_id"])
            if detail.get("approvals"):
                self._update_run(run_id, status="blocked_approval")
            elif detail.get("can_cancel") or detail.get("status") == "running":
                self._update_run(run_id, status="running")
            else:
                delivery = detail.get("delivery") or {}
                if delivery.get("status") not in FINAL:
                    self._update_run(run_id, status="validating")
                    continue
                complete = delivery.get("status") == "completed"
                self._update_run(
                    run_id,
                    status="completed" if complete else "delivery_incomplete",
                    delivery_status="complete" if complete else "incomplete",
                    artifacts=delivery.get("files", []),
                    missing=delivery.get("missing_formats", []),
                )
                return
        self._update_run(run_id, status="failed", failure_code="report_timeout")

    async def cancel(self, run_id: str) -> dict:
        run = self._run(run_id)
        if run["status"] not in ACTIVE:
            raise WorkflowError("报告运行已结束", "run_not_active", 409)
        if run.get("session_id"):
            await self.service.cancel(run["session_id"])
        task = self.tasks.get(run_id)
        if task:
            self.cancellations.setdefault(run_id, threading.Event()).set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        run = self._update_run(run_id, status="cancelled", delivery_status="incomplete")
        return self.public_run(run)

    async def retry(self, run_id: str) -> dict:
        run = self._run(run_id)
        if run["status"] in ACTIVE:
            raise WorkflowError("报告运行仍在进行", "run_active", 409)
        return await self.start_run(run["workflow_id"], trigger="retry", version=run["version"])

    def schedule(self, workflow_id: str) -> dict:
        row = self.catalog._row(workflow_id)
        return row.get("schedule") or {
            "kind": "manual",
            "enabled": False,
            "timezone": "Asia/Shanghai",
            "once_at": None,
            "weekday": None,
            "hour": None,
            "minute": None,
            "next_run_at": None,
            "last_triggered_at": None,
        }

    def put_schedule(self, workflow_id: str, body: dict, *, now: datetime | None = None) -> dict:
        contract = WorkflowSchedule.model_validate(body)
        value = json.loads(contract.model_dump_json())
        value["next_run_at"] = self._next_run(value, now or datetime.now(UTC))
        with self.catalog._exclusive():
            row = self.catalog._row(workflow_id)
            value["last_triggered_at"] = row.get("schedule", {}).get("last_triggered_at")
            row["schedule"] = value
            self.catalog._save()
        return value

    @staticmethod
    def _next_run(schedule: dict, now: datetime) -> str | None:
        if not schedule["enabled"]:
            return None
        if schedule["kind"] == "once":
            value = datetime.fromisoformat(schedule["once_at"])
            if value.tzinfo is None:
                value = value.replace(tzinfo=SHANGHAI)
            return value.astimezone(UTC).isoformat()
        local = now.astimezone(SHANGHAI)
        target = local.replace(
            hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0
        )
        target += timedelta(days=(schedule["weekday"] - target.weekday()) % 7)
        if target <= local:
            target += timedelta(days=7)
        return target.astimezone(UTC).isoformat()

    def _set_schedule_due_for_test(self, workflow_id: str, value: datetime) -> None:
        with self.catalog._exclusive():
            row = self.catalog._row(workflow_id)
            row.setdefault("schedule", {})["next_run_at"] = value.astimezone(UTC).isoformat()
            self.catalog._save()

    async def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        with self.catalog._exclusive():
            scheduled = [
                (workflow_id, copy.deepcopy(row.get("schedule") or {}))
                for workflow_id, row in self.catalog.data["workflows"].items()
            ]
        for workflow_id, schedule in scheduled:
            due = schedule.get("next_run_at")
            if not schedule.get("enabled") or not due or datetime.fromisoformat(due) > now:
                continue
            await self.start_run(workflow_id, trigger="schedule")
            with self.catalog._exclusive():
                # start_run may update the persisted catalog. Re-read while holding
                # the lock instead of mutating the stale schedule captured above.
                row = self.catalog._row(workflow_id)
                schedule = row.get("schedule") or {}
                schedule["last_triggered_at"] = now.isoformat()
                if schedule["kind"] == "once":
                    schedule.update(enabled=False, next_run_at=None)
                else:
                    schedule["next_run_at"] = self._next_run(schedule, now)
                self.catalog._save()

    async def _scheduler(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 - scheduler must survive a bad record.
                log.error("report_workflow_scheduler_failed", error_type=type(exc).__name__)
            await asyncio.sleep(15)
