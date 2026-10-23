"""Persistent report Workflow scheduler delegating execution to native Claw."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import re
import shutil
import threading
import time
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.observability import get_logger

from ..client import RuntimeFailure
from ..delivery import FINAL
from ..projection import content_text
from ..report_rendering import render_report_payload
from ..store import StoreError
from .models import RefreshStatus, WorkflowError, WorkflowSchedule
from .tooling import materialize_report_snapshot
from .weekly_quality import (
    INSUFFICIENT_NEWS,
    POLICY_ID,
    bind_weekly_projection,
    finalization_binding,
    freeze_weekly_production,
    stage_weekly_projection,
    weekly_enabled,
)

log = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
ACTIVE = {
    "queued",
    "preparing_data",
    "running",
    "blocked_approval",
    "validating",
    "needs_attention",
}


def _public_metadata(value):
    """Recursively redact host paths if an internal adapter returns one unexpectedly."""

    if isinstance(value, dict):
        return {
            key: _public_metadata(item)
            for key, item in value.items()
            if key not in {"source_path", "stored_path"}
        }
    if isinstance(value, list):
        return [_public_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_public_metadata(item) for item in value]
    if (
        isinstance(value, str)
        and not value.startswith("/api/research/")
        and (Path(value).is_absolute() or PureWindowsPath(value).is_absolute())
    ):
        return "private-file"
    return value


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
        await self._recover_weekly_runs()
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
            before = copy.deepcopy(row)
            row.update(updates, updated_at=time.time())
            # A failed admission write cannot remain accepted in memory while
            # the durable catalog still holds the earlier state.
            try:
                self.catalog._save()
            except Exception:
                row.clear()
                row.update(before)
                log.warning("report_workflow_run_save_failed")
                raise
            return copy.deepcopy(row)

    def _accepted_weekly_submission(self, run: dict) -> bool:
        sid = run.get("session_id")
        if not sid:
            return False
        expected_key = "report-workflow-" + run["id"]
        try:
            if self.service.store.session(sid).get("delivery_key") != expected_key:
                return False
            receipt = self.service.store.data["receipts"].get(f"{sid}:{expected_key}", {})
            expected_task = hashlib.sha256(f"{sid}:{expected_key}".encode()).hexdigest()[:24]
            return (
                receipt.get("status") == "accepted"
                and receipt.get("delivery", {}).get("task_id") == expected_task
            )
        except StoreError:
            return False

    async def _recover_weekly_runs(self) -> None:
        """Resume only observation of accepted work; never replay a submission."""
        with self.catalog._exclusive():
            runs = [
                copy.deepcopy(row)
                for row in self.catalog.data["runs"].values()
                if row.get("weekly_data_contract") and row.get("status") in ACTIVE
            ]
        for run in runs:
            run_id = run.get("id")
            if not run_id or run_id in self.tasks:
                continue
            try:
                self._require_weekly_owner(run.get("owner_id"))
                if self._accepted_weekly_submission(run):
                    from .weekly_quality import trusted_weekly_context

                    if trusted_weekly_context(self.service, run["session_id"]) is None:
                        raise WorkflowError(
                            "恢复上下文未知", "weekly_recovery_context_unknown", 409
                        )
                    self._update_run(
                        run_id,
                        status="validating",
                        research_submission_state="accepted",
                        recovered_at=time.time(),
                    )
                    self.tasks[run_id] = asyncio.create_task(
                        self._resume_delivery(run_id), name=f"report-weekly-recover-{run_id}"
                    )
                else:
                    self._update_run(
                        run_id,
                        status="needs_attention",
                        finalization_status="blocked",
                        failure_code="weekly_recovery_unknown",
                        recovered_at=time.time(),
                    )
            except (StoreError, OSError, ValueError, KeyError, TypeError) as exc:
                log.warning("report_weekly_recovery_blocked", error_type=type(exc).__name__)
                self._update_run(
                    run_id,
                    status="needs_attention",
                    finalization_status="blocked",
                    failure_code=getattr(exc, "code", "weekly_recovery_context_unknown"),
                )

    def _append_refresh_manifest(self, run_id: str, path: str | None) -> dict:
        run_root = self.catalog.run_path(run_id)
        if path is None:
            raise WorkflowError("刷新清单引用无效", "refresh_manifest_invalid", 409)
        logical = PurePosixPath(path)
        if (
            logical.is_absolute()
            or "\\" in path
            or len(logical.parts) != 2
            or logical.parts[0] != "refresh-manifests"
            or not re.fullmatch(r"[a-f0-9]{64}\.json", logical.name)
        ):
            raise WorkflowError("刷新清单引用无效", "refresh_manifest_invalid", 409)
        manifest = run_root.joinpath(*logical.parts)
        if (
            manifest.is_symlink()
            or not manifest.is_file()
            or not manifest.resolve().is_relative_to(run_root.resolve())
        ):
            raise WorkflowError("刷新清单引用无效", "refresh_manifest_invalid", 409)
        reference = logical.as_posix()
        with self.catalog._exclusive():
            try:
                row = self.catalog.data["runs"][run_id]
            except KeyError as exc:
                raise WorkflowError("报告运行不存在", "run_not_found", 404) from exc
            manifests = row.setdefault("refresh_manifests", [])
            if reference not in manifests:
                manifests.append(reference)
            row["updated_at"] = time.time()
            self.catalog._save()
            return copy.deepcopy(row)

    def run_path(self, run_id: str) -> Path:
        return self.catalog.run_path(run_id)

    def _session_payload(self, session_id: str) -> Path | None:
        """Return a bounded, session-owned payload path when it arrived after projection."""

        root = self.service.store.directory(session_id)
        payload = root / "outputs" / "report_payload.json"
        try:
            if (
                payload.is_symlink()
                or not payload.is_file()
                or payload.stat().st_size <= 0
                or payload.stat().st_size > 2_000_000
                or not payload.resolve().is_relative_to(root.resolve())
            ):
                return None
        except OSError:
            return None
        return payload

    def _rearm_delivery_validation(self, session_id: str) -> None:
        """Let the existing delivery contract inspect files created by the reviewed renderer."""

        try:
            delivery = self.service.delivery.current(session_id)
        except StoreError:
            # Synthetic adapters may return a terminal delivery without a local
            # receipt; there is nothing to re-arm in that case.
            return
        if not delivery:
            return
        delivery.update(
            status="pending",
            files=[],
            reasons=[],
            missing_formats=list(delivery.get("required_formats") or []),
        )
        delivery.pop("failure_code", None)
        delivery.pop("checked_at", None)
        self.service.store.save()

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
            "run_ref": f"runs/{run_id}",
        }
        with self.catalog._exclusive():
            self.catalog.data["runs"][run_id] = row
            self.catalog._save()
        return copy.deepcopy(row)

    def public_run(self, row: dict) -> dict:
        row = copy.deepcopy(row)
        if row.get("finalization_status") == "finalized":
            try:
                binding = finalization_binding(self.service, row["session_id"])
                if any(
                    binding.get(key) != row.get("finalization_binding", {}).get(key)
                    for key in (
                        "task_id",
                        "contract_sha256",
                        "canonical_sha256",
                        "snapshot_sha256",
                        "artifacts",
                    )
                ):
                    raise WorkflowError("周报定稿字节已经改变", "weekly_finalization_changed", 409)
            except (StoreError, OSError, ValueError, KeyError, TypeError):
                row.update(finalization_status="invalidated", quality_status="invalid")
        return _public_metadata({key: value for key, value in row.items() if key != "path"})

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
                workflow_status = workflow.get("status", "draft")
                if workflow_status == "disabled":
                    raise WorkflowError("Workflow 已停用", "workflow_disabled", 409)
                if workflow_status != "enabled":
                    raise WorkflowError("Workflow 尚未启用", "workflow_not_enabled", 409)
                manifest = self.catalog.manifest(workflow_id, selected)
                weekly_contract = None
                owner: dict = {}
                if weekly_enabled(manifest):
                    from .weekly_data import build_weekly_data_contract

                    owner = self._require_weekly_owner()
                    if manifest.weekly_production.data_source == "wind_excel" and trigger not in {
                        "manual",
                        "retry",
                    }:
                        raise WorkflowError(
                            "Excel 周报仍需本期人工准备，暂不支持启用定时",
                            "weekly_excel_schedule_disabled",
                            409,
                        )
                    if trigger not in {"manual", "retry"} and not self._manual_weekly_passed(
                        workflow_id, selected
                    ):
                        raise WorkflowError(
                            "周报自动运行前必须完成本版本的真实手动定稿", "manual_run_required", 409
                        )
                    weekly_contract = build_weekly_data_contract(datetime.now(UTC))
                    if trigger != "retry":
                        previous = next(
                            (
                                item
                                for item in reversed(list(self.catalog.data["runs"].values()))
                                if item.get("workflow_id") == workflow_id
                                and item.get("weekly_cutoff") == weekly_contract["cutoff"]
                                and (
                                    manifest.weekly_production.data_source != "wind_excel"
                                    or (
                                        item.get("version") == selected
                                        and item.get("weekly_data_source") == "wind_excel"
                                    )
                                )
                            ),
                            None,
                        )
                        if previous is not None:
                            return self.public_run(copy.deepcopy(previous))
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
                    run_ref=f"runs/{run_id}",
                )
                row.pop("path", None)
                if weekly_contract is not None:
                    row.update(
                        owner_id=owner["id"],
                        weekly_cutoff=weekly_contract["cutoff"],
                        weekly_data_contract=weekly_contract,
                        weekly_data_source=manifest.weekly_production.data_source,
                        quality_status="pending",
                        finalization_status="pending",
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

    def _require_weekly_owner(self, owner_id: str | None = None) -> dict:
        authorizer = getattr(self.service.report_workflows, "require_weekly_owner", None)
        if not callable(authorizer):
            raise WorkflowError("周报管理员身份尚未验证", "weekly_owner_unavailable", 403)
        return authorizer(expected_owner_id=owner_id)

    def _manual_weekly_passed(self, workflow_id: str, version: int) -> bool:
        return any(
            row.get("workflow_id") == workflow_id
            and row.get("version") == version
            and row.get("trigger") == "manual"
            and row.get("status") == "completed"
            and row.get("delivery_status") == "complete"
            and row.get("finalization_status") == "finalized"
            and self.public_run(row).get("finalization_status") == "finalized"
            for row in self.catalog.data["runs"].values()
        )

    async def _execute(self, run_id: str) -> None:
        run = self._run(run_id)
        try:
            run = self._update_run(run_id, status="preparing_data")
            manifest = self.catalog.manifest(run["workflow_id"], run["version"])
            formal = weekly_enabled(manifest)
            sid = None
            workbook_projection = None
            if formal:
                self._require_weekly_owner(run.get("owner_id"))
                sid = run.get("session_id")
                if sid is None:
                    session = await self.service.create("claw", f"{manifest.name} · 报告 Workflow")
                    sid = session["id"]
                existing = self.service.store.session(sid).get("report_workflow")
                minimal = {
                    "workflow_id": run["workflow_id"],
                    "version": run["version"],
                    "run_id": run_id,
                }
                if manifest.weekly_production.data_source == "wind_excel":
                    minimal["weekly_data_source"] = run.get("weekly_data_source")
                    minimal["owner_id"] = run.get("owner_id")
                if existing and any(existing.get(key) != value for key, value in minimal.items()):
                    raise WorkflowError(
                        "恢复会话不属于本次周报", "weekly_recovery_context_unknown", 409
                    )
                self.service.store.session(sid)["report_workflow"] = minimal
                self.service.store.save()
                run = self._update_run(run_id, session_id=sid)
                collector = getattr(self.service.datahub, "collect_report_weekly", None)
                if not callable(collector):
                    self._update_run(
                        run_id,
                        status="blocked_data",
                        failure_code="weekly_data_collector_unavailable",
                        finalization_status="blocked",
                    )
                    return
                collected = await collector(
                    sid,
                    f"report-weekly-data-{run_id}",
                    cutoff=run["weekly_data_contract"]["cutoff"],
                    run_root=self.run_path(run_id),
                    manifest=manifest,
                    prepare_excel=lambda: self._prepare_weekly_excel(run_id, manifest),
                )
                assessment = collected.get("assessment") or {}
                if (
                    assessment.get("status") != "passed"
                    or collected.get("contract") != run["weekly_data_contract"]
                ):
                    self._update_run(
                        run_id,
                        status="blocked_data",
                        failure_code="weekly_data_unverified",
                        missing=list(assessment.get("issues") or ["weekly_data_unverified"]),
                        finalization_status="blocked",
                    )
                    return
                from ..datahub.security import atomic_json, directory, read_file

                with directory(self.run_path(run_id), ("snapshots",), create=True) as folder:
                    atomic_json(folder, "report-data.json", collected["snapshot"])
                    raw = read_file(folder, "report-data.json", limit=16 * 1024 * 1024)
                snapshot = {
                    "path": "snapshots/report-data.json",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                from .weekly_data import materialize_weekly_workbooks

                workbook_projection = await asyncio.to_thread(
                    materialize_weekly_workbooks,
                    collected["snapshot"],
                    self.run_path(run_id),
                    manifest,
                )
                if workbook_projection.get("snapshot_sha256") != snapshot["sha256"]:
                    raise WorkflowError(
                        "周报底稿与本期快照不一致", "weekly_workbook_projection_invalid", 409
                    )
                run = self._update_run(
                    run_id,
                    weekly_production=freeze_weekly_production(manifest, collected["contract"]),
                    weekly_data_assessment={
                        key: assessment.get(key)
                        for key in ("status", "issues", "contract_sha256", "snapshot_sha256")
                    },
                )
            else:
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
                snapshot = await asyncio.to_thread(
                    materialize_report_snapshot,
                    self.run_path(run_id),
                    manifest,
                    run["refresh_manifests"],
                )
            run = self._update_run(
                run_id,
                dataset_snapshot=snapshot["path"],
                dataset_snapshot_sha256=snapshot["sha256"],
            )
            if sid is None:
                session = await self.service.create("claw", f"{manifest.name} · 报告 Workflow")
                sid = session["id"]
            run = self._update_run(run_id, session_id=sid)
            session_row = self.service.store.session(sid)
            session_row["report_workflow"] = {
                "workflow_id": run["workflow_id"],
                "version": run["version"],
                "run_id": run_id,
            }
            if formal:
                session_row["report_workflow"]["quality_policy"] = POLICY_ID
            target = self.service.store.directory(sid) / "inputs" / "report-workflow"
            shutil.copytree(self.run_path(run_id), target, dirs_exist_ok=True)
            context = {
                "workflow_id": run["workflow_id"],
                "name": manifest.name,
                "version": run["version"],
                "run_id": run_id,
                "delivery": json.loads(manifest.delivery.model_dump_json()),
                "primary_workbook": manifest.delivery.primary_workbook,
                "blocks": json.loads(
                    json.dumps([json.loads(block.model_dump_json()) for block in manifest.blocks])
                ),
                "refresh_manifests": [Path(path).name for path in run["refresh_manifests"]],
                "dataset_snapshot": snapshot["path"],
                "dataset_snapshot_sha256": snapshot["sha256"],
                "minimum_subagents": manifest.minimum_subagents,
            }
            if formal:
                context["weekly_production"] = run["weekly_production"]
                context["workbook_projection"] = workbook_projection
                context["template_resources"] = [
                    {"path": item.path, "sha256": item.sha256}
                    for item in manifest.resources
                    if item.path.startswith(("templates/", "assets/"))
                ]
                from ..datahub.security import atomic_json, directory, read_file

                with directory(target) as folder:
                    atomic_json(folder, "run-context.json", context)
                    context_raw = read_file(folder, "run-context.json", limit=1_000_000)
                self._update_run(
                    run_id, weekly_context_sha256=hashlib.sha256(context_raw).hexdigest()
                )
                self._require_weekly_owner(run.get("owner_id"))
            else:
                (target / "run-context.json").write_text(
                    json.dumps(context, ensure_ascii=False, indent=2)
                )
            self.service.store.save()
            prompt = (
                f"执行锁定的 Report Workflow《{manifest.name}》v{run['version']}。"
                "先读取 inputs/report-workflow/run-context.json、workflow.yaml、模板和已刷新底稿；"
                f"必须创建并完成至少 {manifest.minimum_subagents} 个原生子 Agent；所有子 Agent "
                f"只能共用快照 SHA-256 {snapshot['sha256']}，不得重复刷新或取数。"
                "研究结束后必须写入 outputs/report_payload.json，结构为 "
                "{title, summary, as_of, sections:[{id,title,content}], sources, missing}；"
                "sections 必须使用 run-context.json 中声明的区块 id。"
                "文件组装和交付检查由后端受审查 Tool 完成，不调用旧报告执行链。"
            )
            if formal:
                prompt = (
                    f"执行锁定的华安 ETF 周报 v{run['version']}。先读取 inputs/report-workflow/run-context.json、模板及共享数据快照。"
                    "本轮仅使用已核验事实、确定性比较和有原文出处的观点；数据、计算、截止和实际交易日期以 Host 冻结合同为准。"
                    "正文的唯一可修改真源为 outputs/research-report.json，必须使用原生 report_plan，sections.id 对应全部原报告区块，coverage 绑定本轮研究合同要求。"
                    "区块 id 是绑定依据；report_plan 的 heading 使用不含数词的中性名称，交付原标题由 Host 按锁定区块元数据恢复，不手写数字标题绕过质量门。"
                    "开始日期和结束日期是 Host 冻结的 workbook 元数据，不加入 report_plan 正文；其余区块 id 与研究合同要求必须完整覆盖。"
                    "不要另写 report_payload.json 或自行组装 Office；Host 将规范正文投影到原模板。"
                    f"仅 run-context 中 news_block_ids 允许声明：{INSUFFICIENT_NEWS} 必须保留真实取证记录，不能用训练知识补新闻。"
                    "调用 research_check_quality；只允许原回合一次有界补查，失败保留 incomplete，不新建研究或放宽要求。"
                    f"子 Agent 只复用已冻结快照 SHA-256 {snapshot['sha256']}，不得重复刷新底稿。"
                )
            if formal:
                self._update_run(
                    run_id,
                    research_admission_at=time.time(),
                    research_submission_state="submitting",
                )
            await self.service.send(
                sid,
                prompt,
                f"report-workflow-{run_id}",
                formats=[item.value for item in manifest.delivery.formats],
                capability_id="report-production-workflow",
            )
            self._update_run(
                run_id,
                status="running",
                research_started_at=time.time(),
                **({"research_submission_state": "accepted"} if formal else {}),
            )
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
            current = self._run(run_id)
            if current.get("weekly_data_contract") and current.get("research_admission_at"):
                self._update_run(
                    run_id,
                    status="needs_attention",
                    finalization_status="blocked",
                    failure_code="weekly_monitor_interrupted",
                )
            else:
                self._update_run(run_id, status="cancelled", delivery_status="incomplete")
            raise
        except Exception as exc:  # noqa: BLE001 - background boundary fails closed.
            log.error("report_workflow_run_failed", error_type=type(exc).__name__)
            current = self._run(run_id)
            unknown = bool(
                current.get("research_admission_at") and not current.get("research_started_at")
            )
            admitted = bool(
                current.get("weekly_data_contract") and current.get("research_admission_at")
            )
            self._update_run(
                run_id,
                status="needs_attention" if admitted else "failed",
                failure_code=(
                    "research_submission_unknown"
                    if unknown
                    else getattr(exc, "code", "report_execution_failed")
                ),
                **(
                    {
                        "finalization_status": "blocked",
                        "research_submission_state": (
                            "unknown"
                            if unknown
                            else current.get("research_submission_state", "not_submitted")
                        ),
                    }
                    if current.get("weekly_data_contract")
                    else {}
                ),
            )
        finally:
            self.tasks.pop(run_id, None)
            self.cancellations.pop(run_id, None)

    async def _refresh_workbook(
        self, run_id: str, workbook: str, *, refresh_date: date | None = None
    ):
        """Keep the event loop responsive and wait for bounded worker cleanup on cancel."""

        cancellation = self.cancellations.setdefault(run_id, threading.Event())
        worker = asyncio.create_task(
            asyncio.to_thread(
                self.catalog.refresh_workbook,
                run_id,
                workbook,
                refresh_service=self.refresh,
                refresh_date=refresh_date,
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

    async def _prepare_weekly_excel(self, run_id: str, manifest) -> dict:
        """Only the admitted first-calibration path may refresh owned Run copies."""
        from .weekly_sources import freeze_weekly_workbook_dates

        current = self._run(run_id)
        self._require_weekly_owner(current.get("owner_id"))
        frozen = await asyncio.to_thread(
            freeze_weekly_workbook_dates,
            self.run_path(run_id),
            manifest,
            current["weekly_data_contract"],
        )
        self._update_run(
            run_id,
            weekly_excel_cutoff=frozen["cutoff"],
            weekly_excel_sources={item["path"]: item["sha256"] for item in frozen["workbooks"]},
        )
        for policy in manifest.workbook_policies:
            result = await self._refresh_workbook(
                run_id,
                policy.workbook,
                refresh_date=date.fromisoformat(current["weekly_data_contract"]["period_end"]),
            )
            if result.status is not RefreshStatus.READY:
                raise WorkflowError(
                    "本期 Excel 校准底稿刷新未通过",
                    result.code or "weekly_excel_refresh_failed",
                    409,
                )
            self._append_refresh_manifest(run_id, result.manifest_path)
        return {
            "refresh_manifests": self._run(run_id)["refresh_manifests"],
            "cutoff": current["weekly_data_contract"]["cutoff"],
        }

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
                current = self._run(run_id)
                # A model-created Office file is never the final report artifact.
                # Every Report Workflow must project the structured payload through
                # the reviewed deterministic renderer before delivery can pass.
                if not current.get("projection_attempted_at"):
                    manifest = self.catalog.manifest(current["workflow_id"], current["version"])
                    self._update_run(
                        run_id,
                        status="validating",
                        projection_attempted_at=time.time(),
                    )
                    formal = weekly_enabled(manifest)
                    try:
                        staged = (
                            stage_weekly_projection(self.service, current["session_id"])
                            if formal
                            else {}
                        )
                        projection = await render_report_payload(
                            self.service.store,
                            current["session_id"],
                            [item.value for item in manifest.delivery.formats],
                        )
                        if formal and projection.get("status") == "completed":
                            self._require_weekly_owner(current.get("owner_id"))
                            bind_weekly_projection(
                                self.service, current["session_id"], staged, projection
                            )
                    except (StoreError, ValueError, TypeError, KeyError, OSError) as exc:
                        log.warning(
                            "report_weekly_projection_failed", error_type=type(exc).__name__
                        )
                        projection = {
                            "status": "failed",
                            "files": [],
                            "code": getattr(exc, "code", "weekly_projection_invalid"),
                        }
                    projection_status = str(projection.get("status") or "failed")
                    if projection_status == "completed":
                        self._rearm_delivery_validation(current["session_id"])
                    self._update_run(
                        run_id,
                        projection_status=projection_status,
                        projection_missing_blocks=list(projection.get("missing_blocks") or []),
                    )
                    if projection_status == "completed":
                        detail = await self.service.detail(current["session_id"])
                        delivery = detail.get("delivery") or {}
                        if delivery.get("status") not in FINAL:
                            continue
                current = self._run(run_id)
                manifest = self.catalog.manifest(current["workflow_id"], current["version"])
                by_id = {
                    item.get("id"): item
                    for item in [
                        *(current.get("subagents") or []),
                        *(detail.get("subagents") or []),
                    ]
                    if isinstance(item, dict) and item.get("id")
                }
                subagents = _public_metadata(list(by_id.values()))
                completed_subagents = [
                    item
                    for item in subagents
                    if isinstance(item, dict)
                    and item.get("id")
                    and item.get("status") == "completed"
                ]
                missing = list(delivery.get("missing_formats", []))
                missing.extend(
                    f"block:{item}" for item in current.get("projection_missing_blocks") or []
                )
                if current.get("projection_status") != "completed":
                    missing.append(
                        "projection:" + str(current.get("projection_status") or "not_attempted")
                    )
                if len(completed_subagents) < manifest.minimum_subagents:
                    missing.append(f"subagents:{manifest.minimum_subagents}")
                file_complete = delivery.get("status") == "completed" and not missing
                complete = file_complete
                formal = weekly_enabled(manifest)
                quality_status = "pending"
                finalization_status = "blocked"
                binding = None
                if formal:
                    from ..research_quality_service import check_quality

                    drained = all(
                        item.get("status") in {"completed", "failed", "cancelled", "canceled"}
                        for item in subagents
                    )
                    if not drained:
                        self._update_run(
                            run_id,
                            status="validating",
                            quality_status="pending",
                            finalization_status="pending",
                        )
                        continue
                    try:
                        self._require_weekly_owner(current.get("owner_id"))
                        checked = await check_quality(self.service, current["session_id"])
                        quality_status = checked.get("status", "incomplete")
                        if complete and quality_status == "passed":
                            binding = finalization_binding(self.service, current["session_id"])
                            finalization_status = "finalized"
                        else:
                            complete = False
                            missing.extend(
                                "quality:" + str(issue) for issue in checked.get("issues", [])
                            )
                    except (StoreError, ValueError, TypeError, KeyError, OSError) as exc:
                        log.warning(
                            "report_weekly_finalization_blocked", error_type=type(exc).__name__
                        )
                        quality_status = "invalid"
                        complete = False
                        missing.append(getattr(exc, "code", "weekly_finalization_invalid"))
                updates = {
                    "status": (
                        "completed"
                        if complete
                        else (
                            "quality_incomplete"
                            if formal and file_complete
                            else "delivery_incomplete"
                        )
                    ),
                    "delivery_status": "complete" if file_complete else "incomplete",
                    "artifacts": delivery.get("files", []),
                    "missing": missing,
                    "subagents": subagents,
                }
                if formal:
                    updates.update(
                        execution_status="completed",
                        quality_status=quality_status,
                        finalization_status=finalization_status,
                        finalization_binding=binding,
                    )
                self._finish_run(run_id, updates)
                return
        timed_out = self._run(run_id)
        self._update_run(
            run_id,
            status="needs_attention" if timed_out.get("weekly_data_contract") else "failed",
            failure_code="report_timeout",
        )

    def _finish_run(self, run_id: str, updates: dict) -> None:
        """Publish the accepted run and latest-final pointer in one catalog write."""
        if updates.get("finalization_status") == "finalized":
            self._require_weekly_owner(self._run(run_id).get("owner_id"))
        with self.catalog._exclusive():
            row = self.catalog.data["runs"][run_id]
            workflow = self.catalog._row(row["workflow_id"])
            before_run, before_workflow = copy.deepcopy(row), copy.deepcopy(workflow)
            row.update(updates, updated_at=time.time())
            if updates.get("finalization_status") == "finalized":
                workflow["last_finalized_run"] = run_id
                workflow["last_finalized"] = {
                    "run_id": run_id,
                    "session_id": row.get("session_id"),
                    "binding": copy.deepcopy(updates["finalization_binding"]),
                }
            try:
                self.catalog._save()
            except Exception:
                row.clear()
                row.update(before_run)
                workflow.clear()
                workflow.update(before_workflow)
                log.warning("report_workflow_final_save_failed")
                raise

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
        current = self._run(run_id)
        run = self._update_run(
            run_id,
            status=(
                "needs_attention"
                if current.get("weekly_data_contract") and current.get("research_admission_at")
                else "cancelled"
            ),
            delivery_status="incomplete",
        )
        return self.public_run(run)

    async def retry(self, run_id: str) -> dict:
        run = self._run(run_id)
        if run.get("weekly_data_contract") and run.get("status") == "needs_attention":
            return await self._inspect_weekly_run(run_id)
        if run["status"] in ACTIVE:
            raise WorkflowError("报告运行仍在进行", "run_active", 409)
        if (
            run.get("finalization_status") == "finalized"
            and self.public_run(run).get("finalization_status") == "finalized"
        ):
            return self.public_run(run)
        if run.get("weekly_data_contract") and (
            run.get("research_admission_at") or run.get("research_started_at")
        ):
            # A delivery action never starts another paid research turn. Keep the
            # original session, cutoff and evidence; only reproject/recheck bytes.
            if not run.get("session_id") or not run.get("dataset_snapshot_sha256"):
                raise WorkflowError(
                    "本轮研究结果未知，需要人工核查", "weekly_research_unknown", 409
                )
            root = self.service.store.directory(run["session_id"])
            canonical = root / "outputs" / "research-report.json"
            if canonical.is_symlink() or not canonical.is_file():
                raise WorkflowError(
                    "本轮缺少规范报告，不能自动重做研究", "weekly_canonical_missing", 409
                )
            self._require_weekly_owner(run.get("owner_id"))
            self._update_run(
                run_id,
                status="validating",
                delivery_status="pending",
                quality_status="pending",
                finalization_status="pending",
                projection_attempted_at=None,
                projection_status=None,
                missing=[],
            )
            self.tasks[run_id] = asyncio.create_task(
                self._resume_delivery(run_id), name=f"report-weekly-recheck-{run_id}"
            )
            return self.public_run(self._run(run_id))
        if (
            run["status"] == "delivery_incomplete"
            and run.get("session_id")
            and run.get("dataset_snapshot_sha256")
        ):
            if self._session_payload(run["session_id"]):
                self._update_run(
                    run_id,
                    status="validating",
                    delivery_status="pending",
                    projection_attempted_at=None,
                    projection_status=None,
                    missing=[],
                )
                self.tasks[run_id] = asyncio.create_task(
                    self._resume_delivery(run_id),
                    name=f"report-delivery-late-payload-{run_id}",
                )
                return self.public_run(self._run(run_id))
            attempt = int(run.get("delivery_retry_attempt") or 0) + 1
            previous_session_id = run["session_id"]
            session = await self.service.create("claw", f"{run['workflow_id']} · 报告交付续跑")
            delivery_session_id = session["id"]
            source = (
                self.service.store.directory(previous_session_id) / "inputs" / "report-workflow"
            )
            target = (
                self.service.store.directory(delivery_session_id) / "inputs" / "report-workflow"
            )
            if source.is_symlink() or not source.is_dir():
                raise WorkflowError("锁定的报告资源不存在", "workflow_resources_missing", 409)
            shutil.copytree(source, target, dirs_exist_ok=True)
            session_row = self.service.store.session(delivery_session_id)
            session_row["report_workflow"] = {
                "workflow_id": run["workflow_id"],
                "version": run["version"],
                "run_id": run_id,
                "delivery_retry": attempt,
            }
            self.service.store.save()
            self._update_run(
                run_id,
                status="running",
                delivery_status="pending",
                delivery_retry_attempt=attempt,
                research_session_id=run.get("research_session_id") or previous_session_id,
                session_id=delivery_session_id,
                delivery_session_id=delivery_session_id,
                projection_attempted_at=None,
                projection_status=None,
                missing=[],
            )
            manifest = self.catalog.manifest(run["workflow_id"], run["version"])
            await self.service.send(
                delivery_session_id,
                (
                    "这是报告交付续跑。不要规划、刷新底稿、联网或创建子 Agent。"
                    "第一步必须直接调用 research_run_script 写入 "
                    "outputs/report_payload.json；必须覆盖 run-context.json 的全部必需区块，"
                    "只写可由快照支持的结论，缺失信息放入 missing。写完后结束回合，"
                    "DOCX/HTML/XLSX 由后端确定性组装。"
                ),
                f"report-delivery-retry-{run_id}-{attempt}",
                formats=[item.value for item in manifest.delivery.formats],
                capability_id="report-production-workflow",
            )
            self.tasks[run_id] = asyncio.create_task(
                self._resume_delivery(run_id), name=f"report-delivery-retry-{run_id}"
            )
            return self.public_run(self._run(run_id))
        return await self.start_run(run["workflow_id"], trigger="retry", version=run["version"])

    async def _inspect_weekly_run(self, run_id: str) -> dict:
        """Explicit reconciliation reuses the original session and admission keys."""
        run = self._run(run_id)
        self._require_weekly_owner(run.get("owner_id"))
        if run_id in self.tasks:
            return self.public_run(run)
        sid = run.get("session_id")
        if run.get("research_admission_at") or run.get("research_started_at"):
            if not sid:
                raise WorkflowError("模型受理结果未知，不能重发", "weekly_research_unknown", 409)
            try:
                await self.service.detail(sid)
                key = "report-workflow-" + run_id
                receipt = self.service.store.data["receipts"].get(f"{sid}:{key}", {})
                marker = receipt.get("delivery", {}).get("marker")
                seen = isinstance(marker, str) and any(
                    entry.get("event", {}).get("type") == "user/message"
                    and marker in content_text(entry["event"].get("data", {}).get("content"))
                    for entry in self.service.events.get(sid, {}).values()
                )
                if seen and self.service.store.session(sid).get("delivery_key") == key:
                    self.service.store.receipt(sid, key, "accepted")
                if not self._accepted_weekly_submission(run):
                    self._update_run(run_id, failure_code="weekly_native_submission_unconfirmed")
                    return self.public_run(self._run(run_id))
            except (StoreError, RuntimeFailure, OSError, ValueError, KeyError, TypeError) as exc:
                log.warning(
                    "report_weekly_submission_recheck_failed", error_type=type(exc).__name__
                )
                self._update_run(run_id, failure_code="weekly_native_submission_unconfirmed")
                return self.public_run(self._run(run_id))
            self._update_run(
                run_id,
                status="validating",
                research_submission_state="accepted",
                research_observed_at=time.time(),
                failure_code=None,
            )
            self.tasks[run_id] = asyncio.create_task(
                self._resume_delivery(run_id), name=f"report-weekly-reconcile-{run_id}"
            )
        else:
            if sid:
                receipt = self.service.datahub.snapshots.receipt(
                    sid, f"report-weekly-data-{run_id}"
                )
                if receipt and receipt.get("status") != "completed":
                    self._update_run(run_id, failure_code="weekly_data_admission_unknown")
                    return self.public_run(self._run(run_id))
            # The durable journal is absent: no model RPC has been attempted.
            # Completed data is consumed under the same sid/call_id; an unknown
            # data receipt is never replayed above.
            self._update_run(run_id, status="queued", failure_code=None)
            self.tasks[run_id] = asyncio.create_task(
                self._execute(run_id), name=f"report-weekly-continue-{run_id}"
            )
        return self.public_run(self._run(run_id))

    async def _resume_delivery(self, run_id: str) -> None:
        try:
            await self._wait_for_delivery(run_id)
        except asyncio.CancelledError:
            current = self._run(run_id)
            if current.get("weekly_data_contract"):
                self._update_run(
                    run_id,
                    status="needs_attention",
                    finalization_status="blocked",
                    failure_code="weekly_monitor_interrupted",
                )
            else:
                self._update_run(run_id, status="cancelled", delivery_status="incomplete")
            raise
        except Exception as exc:  # noqa: BLE001 - resumed background boundary.
            log.error("report_delivery_retry_failed", error_type=type(exc).__name__)
            current = self._run(run_id)
            self._update_run(
                run_id,
                status="needs_attention" if current.get("weekly_data_contract") else "failed",
                failure_code="delivery_retry_failed",
            )
        finally:
            self.tasks.pop(run_id, None)

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
        workflow = self.catalog._row(workflow_id)
        selected = workflow.get("current_version")
        formal = selected is not None and weekly_enabled(
            self.catalog.manifest(workflow_id, selected)
        )
        owner = self._require_weekly_owner() if formal else None
        if (
            formal
            and contract.enabled
            and self.catalog.manifest(workflow_id, selected).weekly_production.data_source
            == "wind_excel"
        ):
            raise WorkflowError(
                "Excel 周报仍需本期人工准备，暂不支持启用定时",
                "weekly_excel_schedule_disabled",
                409,
            )
        if (
            formal
            and contract.enabled
            and (
                contract.kind.value != "weekly"
                or contract.timezone != "Asia/Shanghai"
                or (contract.weekday, contract.hour, contract.minute) != (4, 15, 30)
            )
        ):
            raise WorkflowError(
                "华安周报固定于北京时间每周五15:30启动", "weekly_schedule_invalid", 409
            )
        if contract.enabled:
            with self.catalog._exclusive():
                manual_passed = (
                    self._manual_weekly_passed(workflow_id, selected)
                    if formal
                    else any(
                        row.get("workflow_id") == workflow_id
                        and row.get("trigger") == "manual"
                        and row.get("status") == "completed"
                        and row.get("delivery_status") == "complete"
                        for row in self.catalog.data["runs"].values()
                    )
                )
            if not manual_passed:
                raise WorkflowError(
                    "Workflow 必须先完成一次真实手动运行，才能启用日程",
                    "manual_run_required",
                    409,
                )
        value = json.loads(contract.model_dump_json())
        if owner is not None:
            value["owner_id"] = owner["id"]
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

    def _record_schedule_failure(
        self, workflow_id: str, code: str, now: datetime, *, disable: bool = False
    ) -> None:
        safe_code = code if re.fullmatch(r"[a-z0-9_]{1,64}", code) else "schedule_failed"
        with self.catalog._exclusive():
            row = self.catalog.data["workflows"].get(workflow_id)
            if row is None:
                return
            schedule = row.get("schedule")
            if not isinstance(schedule, dict):
                schedule = {"kind": "manual", "enabled": False}
                row["schedule"] = schedule
            schedule.update(
                last_error_code=safe_code,
                last_error_at=now.astimezone(UTC).isoformat(),
            )
            if disable:
                schedule.update(enabled=False, next_run_at=None)
            self.catalog._save()
        log.warning(
            "report_workflow_schedule_failed",
            workflow_id=workflow_id,
            error_code=safe_code,
        )

    async def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        with self.catalog._exclusive():
            scheduled = [
                (workflow_id, copy.deepcopy(row.get("schedule") or {}))
                for workflow_id, row in self.catalog.data["workflows"].items()
            ]
        for workflow_id, schedule in scheduled:
            if not schedule.get("enabled"):
                continue
            if schedule.get("owner_id"):
                try:
                    self._require_weekly_owner(schedule["owner_id"])
                except WorkflowError as exc:
                    self._record_schedule_failure(workflow_id, exc.code, now, disable=True)
                    continue
            try:
                due = schedule.get("next_run_at")
                if not isinstance(due, str):
                    raise TypeError("missing due time")
                if datetime.fromisoformat(due) > now:
                    continue
            except (TypeError, ValueError):
                self._record_schedule_failure(workflow_id, "schedule_invalid", now, disable=True)
                continue
            try:
                await self.start_run(workflow_id, trigger="schedule")
            except WorkflowError as exc:
                disable = exc.code in {
                    "workflow_disabled",
                    "workflow_not_enabled",
                    "version_required",
                    "manual_run_required",
                    "weekly_excel_schedule_disabled",
                }
                self._record_schedule_failure(workflow_id, exc.code, now, disable=disable)
                continue
            except Exception as exc:  # noqa: BLE001 - isolate each persisted schedule.
                log.error(
                    "report_workflow_schedule_trigger_failed",
                    workflow_id=workflow_id,
                    error_type=type(exc).__name__,
                )
                self._record_schedule_failure(workflow_id, "schedule_trigger_failed", now)
                continue
            with self.catalog._exclusive():
                # start_run may update the persisted catalog. Re-read while holding
                # the lock instead of mutating the stale schedule captured above.
                row = self.catalog._row(workflow_id)
                schedule = row.get("schedule") or {}
                schedule["last_triggered_at"] = now.isoformat()
                schedule["last_error_code"] = None
                schedule["last_error_at"] = None
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
