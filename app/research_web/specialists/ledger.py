"""Private, durable collaboration business ledger. DSH owns all execution/history."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import threading
import time
from contextlib import contextmanager
from datetime import date
from uuid import uuid4

from pydantic import ValidationError

from core.observability import get_logger

from ..datahub.security import atomic_json, directory, read_file, sync_directory
from ..report_workflows.catalog import _lock_file, _unlock_file
from .contracts import Budget, NodeResult, PlanUpdate, SpecialistError
from .registry import catalog

log = get_logger(__name__)
_LOCK = threading.RLock()
_LIVE = {"reserved", "dispatching", "accepted", "unknown", "cancel_requested"}
_STOP_REASONS = {"completed", "aborted", "error", "max-tokens", "refusal", "invalid_output"}


def _digest(value):
    try:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        ).hexdigest()
    except (ValueError, TypeError) as exc:
        raise SpecialistError("协作数据必须是有限JSON值") from exc


def _fields(payload, required, optional=()):
    if (
        not isinstance(payload, dict)
        or not set(required) <= payload.keys()
        or (payload.keys() - set(required) - set(optional))
    ):
        raise SpecialistError("协作操作字段无效")


def _frozen_skills(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecialistError("研究方法冻结记录无效")
    allowed = {name for entry in catalog()["roles"].values() for name in entry["skills"]}
    if value.keys() - allowed:
        raise SpecialistError("研究方法尚未发布", "specialist_capability_denied", 403)
    for record in value.values():
        _fields(
            record,
            {
                "id",
                "version",
                "kind",
                "native_name",
                "sha256",
                "resource_path",
                "resource_snapshot_sha256",
            },
        )
        if (
            not isinstance(record["id"], str)
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,100}", record["id"])
            or type(record["version"]) is not int
            or record["version"] < 1
            or record["kind"] != "skill"
            or not isinstance(record["native_name"], str)
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,199}", record["native_name"])
            or record["resource_path"]
            != f"resources/capabilities/{record['id']}/{record['version']}"
            or any(
                not isinstance(record[key], str) or not re.fullmatch(r"[a-f0-9]{64}", record[key])
                for key in ("sha256", "resource_snapshot_sha256")
            )
        ):
            raise SpecialistError("研究方法版本或会话资源身份无效")
    return copy.deepcopy(value)


class SpecialistLedger:
    """An account Store is the authority; callers never supply a directory or owner."""

    def __init__(self, store, *, clock=None):
        self.store = store
        self.clock = clock or time.time

    @contextmanager
    def _exclusive(self, sid):
        self.store.session(sid)
        with (
            _LOCK,
            directory(self.store.root, ("specialists", sid), create=True, private=True) as fd,
        ):
            descriptor = None
            try:
                # The new private directory entries must survive the same crash as
                # the reservation file before native dispatch is permitted.
                with directory(self.store.root, ("specialists",), private=True) as parent:
                    sync_directory(parent)
                with directory(self.store.root) as account:
                    sync_directory(account)
                if isinstance(fd, int):
                    descriptor = os.open(
                        "ledger.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd
                    )
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
                        raise SpecialistError(
                            "协作锁权限异常", "specialist_storage_unavailable", 503
                        )
                    stream = os.fdopen(descriptor, "r+b")
                    descriptor = None
                else:
                    path = fd / "ledger.lock"
                    if path.is_symlink():
                        raise SpecialistError(
                            "协作锁类型异常", "specialist_storage_unavailable", 503
                        )
                    stream = path.open("a+b")
                with stream:
                    _lock_file(stream)
                    try:
                        yield fd
                    finally:
                        _unlock_file(stream)
            except OSError as exc:
                log.error("specialist_storage_failed", error_type=type(exc).__name__)
                raise SpecialistError(
                    "协作记录不可访问", "specialist_storage_unavailable", 503
                ) from exc
            finally:
                if descriptor is not None:
                    os.close(descriptor)

    def _load(self, fd, sid):
        try:
            if isinstance(fd, int):
                os.stat("ledger.json", dir_fd=fd, follow_symlinks=False)
            else:
                (fd / "ledger.json").lstat()
        except FileNotFoundError:
            return {"schema_version": 1, "session_id": sid, "current": None, "runs": {}}
        try:
            value = json.loads(read_file(fd, "ledger.json", private=True, limit=4 * 1024 * 1024))
            if (
                value.get("schema_version") != 1
                or value.get("session_id") != sid
                or not isinstance(value.get("runs"), dict)
                or value.get("current") not in value["runs"]
            ):
                raise ValueError("invalid ledger identity")
            required = {
                "id",
                "session_id",
                "status",
                "budget",
                "model",
                "as_of_date",
                "deadline",
                "registry",
                "attempts",
                "model_requests",
                "active_plan",
                "receipts",
                "creation_digest",
                "request_id",
                "created_at",
                "cancel_requested",
            }
            for run_id, run in value["runs"].items():
                if (
                    not isinstance(run, dict)
                    or not required <= run.keys()
                    or run["id"] != run_id
                    or run["session_id"] != sid
                    or any(
                        not isinstance(run[key], dict)
                        for key in ("attempts", "model_requests", "active_plan", "receipts")
                    )
                ):
                    raise ValueError("invalid run state")
                Budget.model_validate(run["budget"])
                if run["registry"]["digest"] != _digest(run["registry"]["roles"]):
                    raise ValueError("role registry digest mismatch")
            return value
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            log.error("specialist_ledger_unreadable", error_type=type(exc).__name__)
            raise SpecialistError(
                "协作记录损坏；未覆盖", "specialist_storage_unavailable", 503
            ) from exc

    def _save(self, fd, envelope, *, result=None):
        limit = 4 * 1024 * 1024
        if (
            len(json.dumps(envelope, ensure_ascii=False).encode()) > limit
            or len(json.dumps(self._view(envelope, result=result), ensure_ascii=False).encode())
            > limit
        ):
            log.warning("specialist_storage_limit")
            raise SpecialistError("协作记录达到容量上限", "specialist_storage_limit", 409)
        atomic_json(fd, "ledger.json", envelope)

    def _view(self, envelope, *, result=None, replayed=False):
        run = copy.deepcopy(envelope["runs"].get(envelope["current"]))
        if run is None:
            return None
        run.pop("receipts", None)
        run.pop("creation_digest", None)
        run.pop("resume_permitted", None)
        run.pop("resume_plan", None)
        run["previous_runs"] = [
            {"id": entry["id"], "status": entry["status"], "created_at": entry["created_at"]}
            for key, entry in envelope["runs"].items()
            if key != envelope["current"]
        ]
        run["operation_result"] = copy.deepcopy(result or {})
        run["replayed"] = replayed
        run["can_resume"] = bool(
            run["status"] not in {"awaiting_plan", "running", "cancel_pending"}
            and not any(attempt["status"] in _LIVE for attempt in run["attempts"].values())
            and all(item["usage"] is not None for item in run["model_requests"].values())
        )
        run["finalization_ready"] = bool(
            run["status"] == "ready_for_validation"
            and not run["cancel_requested"]
            and run.get("completed_at") is not None
            and run["completed_at"] <= run["deadline"]
            and self._structurally_ready(run)
        )
        return run

    def read(self, sid):
        with self._exclusive(sid) as fd:
            return self._view(self._load(fd, sid))

    def create(self, sid, budget, as_of, model, request_id, *, skills=None):
        try:
            validated = Budget.model_validate(budget).model_dump()
            date.fromisoformat(as_of)
        except (ValidationError, TypeError, ValueError) as exc:
            raise SpecialistError("协作预算必须明确确认且研究截止日有效") from exc
        allowed = {"provider", "model", "profile_id", "model_provider", "model_profile_id"}
        if not isinstance(model, dict) or model.keys() - allowed:
            raise SpecialistError("只允许冻结非秘密模型标识")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 128:
            raise SpecialistError("协作启动标识无效")
        frozen_skills = _frozen_skills(skills)
        creation = _digest([validated, as_of, model, request_id, frozen_skills])
        with self._exclusive(sid) as fd:
            envelope = self._load(fd, sid)
            for previous in envelope["runs"].values():
                if previous["request_id"] == request_id:
                    if previous["creation_digest"] != creation:
                        raise SpecialistError("启动标识已绑定其他输入", "specialist_conflict", 409)
                    if previous["id"] != envelope["current"]:
                        raise SpecialistError("旧运行不能重放", "specialist_conflict", 409)
                    return self._view(envelope, replayed=True)
            old = envelope["runs"].get(envelope["current"])
            if old and (
                any(attempt["status"] in _LIVE for attempt in old["attempts"].values())
                or old["status"] in {"awaiting_plan", "running"}
            ):
                raise SpecialistError("旧运行尚未确认结束", "specialist_unresolved", 409)
            if old and not old.get("resume_permitted"):
                raise SpecialistError("续跑需要明确确认", "specialist_resume_required", 409)
            if old and (old["model"] != model or old["as_of_date"] != as_of):
                raise SpecialistError("续跑须保持冻结模型和截止日", "specialist_conflict", 409)
            if old and old["budget"] != validated:
                raise SpecialistError("续跑不能自动增加已确认预算", "specialist_conflict", 409)
            if old and old.get("skills", {}) != frozen_skills:
                raise SpecialistError("续跑须保持冻结研究方法版本", "specialist_conflict", 409)
            run_id, now = str(uuid4()), self.clock()
            run = {
                "schema_version": 1,
                "id": run_id,
                "session_id": sid,
                "request_id": request_id,
                "creation_digest": creation,
                "previous_run_id": old["id"] if old else None,
                "created_at": now,
                "deadline": now + validated["timeout_seconds"],
                "as_of_date": as_of,
                "model": copy.deepcopy(model),
                "budget": validated,
                "registry": copy.deepcopy(old["registry"]) if old else catalog(),
                "skills": frozen_skills,
                "status": "awaiting_plan",
                "active_plan": {"version": 0, "nodes": []},
                "plan_history": [],
                "attempts": {},
                "model_requests": {},
                "receipts": {},
                "cancel_requested": False,
                "completed_at": None,
                "revisions_used": old.get("revisions_used", 0) if old else 0,
                "reusable_results": {},
                "resume_plan": copy.deepcopy(old["active_plan"]) if old else None,
            }
            if old:
                run["model_requests"] = copy.deepcopy(old["model_requests"])
                old["resume_permitted"] = False
                for node in old["active_plan"]["nodes"]:
                    attempt = self._successful(old, node["id"])
                    if attempt:
                        run["reusable_results"][node["id"]] = {
                            "node": node,
                            "attempt": copy.deepcopy(attempt),
                        }
            envelope["runs"][run_id] = run
            envelope["current"] = run_id
            self._save(fd, envelope)
            log.info("specialist_run_created", session_id=sid, run_id=run_id)
            return self._view(envelope)

    def confirm_not_submitted(self, sid, attempt_ids, observation):
        """Host-only absence proof applies exclusively before durable dispatch intent."""
        _fields(
            observation,
            {
                "parent_session_id",
                "parent_idle",
                "parent_terminal",
                "catalog_complete",
                "child_ids",
            },
        )
        terminal = observation["parent_terminal"]
        _fields(terminal, {"end_seq", "turn", "event_sha256"})
        if (
            observation["parent_session_id"] != sid
            or observation["parent_idle"] is not True
            or observation["catalog_complete"] is not True
            or not isinstance(observation["child_ids"], list)
            or any(not isinstance(value, str) for value in observation["child_ids"])
            or any(
                type(terminal[key]) is not int or terminal[key] < 0 for key in ("end_seq", "turn")
            )
            or not isinstance(terminal["event_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", terminal["event_sha256"])
            or not isinstance(attempt_ids, list)
            or not attempt_ids
            or any(not isinstance(value, str) for value in attempt_ids)
        ):
            raise SpecialistError("未提交见证不完整", "specialist_observation_invalid", 409)
        with self._exclusive(sid) as fd:
            envelope = self._load(fd, sid)
            run = self._current(envelope)
            if set(attempt_ids) - run["attempts"].keys():
                raise SpecialistError("尝试不属于当前运行", "specialist_actor_denied", 403)
            selected = [run["attempts"][key] for key in attempt_ids]
            for attempt in selected:
                prepared = attempt["status"] == "reserved" or (
                    attempt["status"] == "cancel_requested"
                    and attempt.get("cancelled_from_status") == "reserved"
                )
                if (
                    not prepared
                    or attempt.get("dispatch_at") is not None
                    or attempt["child_id"] in observation["child_ids"]
                    or any(
                        record["agent_id"] == attempt["child_id"]
                        for record in run["model_requests"].values()
                    )
                ):
                    raise SpecialistError("无法证明该尝试未提交", "specialist_unresolved", 409)
            for attempt in selected:
                attempt.update(
                    status="not_submitted",
                    terminated_at=self.clock(),
                    not_submitted_observation=copy.deepcopy(observation),
                )
            if not run["cancel_requested"]:
                run["status"] = "needs_attention"
            self._refresh(run)
            self._save(fd, envelope)
            log.info("specialist_unsubmitted_confirmed", run_id=run["id"], count=len(selected))
            return self._view(envelope)

    def resume(self, sid, *, confirmed):
        if confirmed is not True:
            raise SpecialistError("续跑需要明确确认", "specialist_resume_required", 409)
        with self._exclusive(sid) as fd:
            envelope = self._load(fd, sid)
            run = self._current(envelope)
            if any(attempt["status"] in _LIVE for attempt in run["attempts"].values()):
                raise SpecialistError("先核对未知或在途节点", "specialist_unresolved", 409)
            if any(request["usage"] is None for request in run["model_requests"].values()):
                raise SpecialistError("先核对未知用量", "specialist_usage_unknown", 409)
            if run["status"] in {"awaiting_plan", "running", "cancel_pending"}:
                raise SpecialistError("当前研究仍在执行", "specialist_unresolved", 409)
            run["resume_permitted"] = True
            self._save(fd, envelope)
            return self._view(envelope)

    @staticmethod
    def _current(envelope):
        run = envelope["runs"].get(envelope["current"])
        if run is None:
            raise SpecialistError("会话没有协作运行", "specialist_not_found", 404)
        return run

    @staticmethod
    def _successful(run, node_id):
        candidates = [
            attempt
            for attempt in run["attempts"].values()
            if attempt["node_id"] == node_id
            and attempt["status"] == "succeeded"
            and not attempt["invalidated"]
            and SpecialistLedger._snapshot_valid(
                attempt.get("result"), attempt.get("evidence_snapshot")
            )
        ]
        return candidates[-1] if candidates else None

    @staticmethod
    def _snapshot_valid(result, snapshot):
        if not isinstance(result, dict) or not isinstance(snapshot, dict):
            return False
        refs = set(result.get("evidence_ids", [])) | set(result.get("artifact_ids", []))
        return (
            bool(result.get("evidence_ids"))
            and set(snapshot) == refs
            and all(
                isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
                for value in snapshot.values()
            )
        )

    def _structurally_ready(self, run):
        measured_agents = {
            item["agent_id"] for item in run["model_requests"].values() if item["usage"] is not None
        }
        return bool(
            run["active_plan"]["nodes"]
            and run["model_requests"]
            and not run["cancel_requested"]
            and all(self._successful(run, node["id"]) for node in run["active_plan"]["nodes"])
            and run["session_id"] in measured_agents
            and all(
                self._successful(run, node["id"])["child_id"] in measured_agents
                for node in run["active_plan"]["nodes"]
            )
            and all(
                item["usage"] is not None and not item.get("reservation_exceeded")
                for item in run["model_requests"].values()
            )
            and sum(sum(item["usage"].values()) for item in run["model_requests"].values())
            <= run["budget"]["max_tokens"]
        )

    def invalidate_evidence(self, sid, changed_attempt_ids):
        """Host-qualified byte drift invalidates reuse; this method never executes DSH."""
        if (
            not isinstance(changed_attempt_ids, list)
            or not changed_attempt_ids
            or any(not isinstance(value, str) for value in changed_attempt_ids)
        ):
            raise SpecialistError("证据失效尝试标识无效")
        with self._exclusive(sid) as fd:
            envelope = self._load(fd, sid)
            run = self._current(envelope)
            if set(changed_attempt_ids) - run["attempts"].keys():
                raise SpecialistError("证据失效尝试不属于当前运行", "specialist_actor_denied", 403)
            affected = {run["attempts"][key]["node_id"] for key in changed_attempt_ids}
            while True:
                expanded = affected | {
                    node["id"]
                    for node in run["active_plan"]["nodes"]
                    if set(node["depends_on"]) & affected
                }
                if expanded == affected:
                    break
                affected = expanded
            cancellations = []
            for attempt in run["attempts"].values():
                if attempt["node_id"] in affected:
                    attempt["invalidated"] = True
                    attempt["invalidation_reason"] = "evidence_snapshot_changed"
                    if attempt["status"] in _LIVE:
                        if attempt["status"] != "cancel_requested":
                            attempt["cancelled_from_status"] = attempt["status"]
                        attempt["status"] = "cancel_requested"
                        cancellations.append(attempt["id"])
            run["completed_at"] = None
            if not run["cancel_requested"]:
                run["status"] = "needs_attention"
            self._save(fd, envelope)
            log.warning("specialist_evidence_invalidated", run_id=run["id"], count=len(affected))
            return self._view(envelope, result={"cancel_attempt_ids": cancellations})

    @staticmethod
    def _root(run, agent_id):
        if agent_id != run["session_id"]:
            raise SpecialistError("只有根研究Agent可更改计划", "specialist_actor_denied", 403)

    @staticmethod
    def _role(run, role_id):
        entry = run["registry"]["roles"].get(role_id)
        if entry is None:
            raise SpecialistError("本运行未冻结该专业角色", "specialist_capability_denied", 403)
        return entry

    @staticmethod
    def _actor(run, agent_id):
        if agent_id == run["session_id"]:
            return None
        for attempt in run["attempts"].values():
            if attempt["child_id"] == agent_id:
                return attempt
        raise SpecialistError("Agent不属于本次研究", "specialist_actor_denied", 403)

    def apply(self, sid, operation, payload, *, agent_id, call_id):
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 200:
            raise SpecialistError("协作调用标识无效")
        digest = _digest([operation, payload, agent_id])
        with self._exclusive(sid) as fd:
            envelope = self._load(fd, sid)
            run = self._current(envelope)
            self._actor(run, agent_id)
            previous = run["receipts"].get(call_id)
            if previous:
                if previous["digest"] != digest:
                    raise SpecialistError("调用标识冲突", "specialist_conflict", 409)
                return self._view(envelope, result=previous["result"], replayed=True)
            if len(run["receipts"]) >= 512:
                raise SpecialistError("协作操作达到上限", "specialist_budget_exhausted", 409)
            handler = (
                getattr(self, f"_op_{operation}", None)
                if operation
                in {
                    "plan",
                    "reserve",
                    "dispatch",
                    "accepted",
                    "submission_unknown",
                    "submission_rejected",
                    "terminal",
                    "cancel",
                    "recover",
                    "model_request",
                    "model_usage",
                }
                else None
            )
            if handler is None:
                raise SpecialistError("未知协作操作")
            try:
                result = handler(run, payload, agent_id) or {}
            except (ValidationError, ValueError, TypeError, KeyError) as exc:
                log.warning("specialist_operation_invalid", operation=operation)
                raise SpecialistError("协作合同校验失败") from exc
            self._refresh(run)
            run["receipts"][call_id] = {"digest": digest, "result": result}
            self._save(fd, envelope, result=result)
            log.info("specialist_operation_recorded", operation=operation, run_id=run["id"])
            return self._view(envelope, result=result)

    def _admitting(self, run):
        if run["cancel_requested"] or run["status"] in {"cancelled", "needs_attention"}:
            raise SpecialistError("运行已停止，须明确续跑", "specialist_not_admitting", 409)
        if self.clock() >= run["deadline"]:
            raise SpecialistError("协作执行已超时", "specialist_deadline", 409)

    def _op_plan(self, run, payload, agent_id):
        self._root(run, agent_id)
        self._admitting(run)
        plan = PlanUpdate.model_validate(payload).model_dump()
        old = run["active_plan"]
        if plan["expected_version"] != old["version"]:
            raise SpecialistError("计划版本已变化", "specialist_plan_conflict", 409)
        revision = bool(old["version"]) or bool(
            run.get("resume_plan") and run["resume_plan"]["nodes"] != plan["nodes"]
        )
        if revision and run["revisions_used"] >= run["budget"]["max_revisions"]:
            raise SpecialistError("计划修订达到上限", "specialist_revision_limit", 409)
        for node in plan["nodes"]:
            if set(node["skills"]) - set(self._role(run, node["role"])["skills"]):
                raise SpecialistError(
                    "节点引用未发布的领域能力", "specialist_capability_denied", 403
                )
        before, after = {n["id"]: n for n in old["nodes"]}, {n["id"]: n for n in plan["nodes"]}
        affected = {key for key in before if key not in after or before[key] != after[key]}
        while True:
            expanded = (
                affected
                | {node["id"] for node in before.values() if set(node["depends_on"]) & affected}
                | {node["id"] for node in after.values() if set(node["depends_on"]) & affected}
            )
            if expanded == affected:
                break
            affected = expanded
        cancel_ids = []
        for attempt in run["attempts"].values():
            if attempt["node_id"] in affected:
                attempt["invalidated"] = True
                if attempt["status"] in _LIVE:
                    if attempt["status"] != "cancel_requested":
                        attempt["cancelled_from_status"] = attempt["status"]
                    attempt["status"] = "cancel_requested"
                    cancel_ids.append(attempt["id"])
        run["plan_history"].append(copy.deepcopy(old))
        if revision:
            run["revisions_used"] += 1
        run["active_plan"] = {"version": old["version"] + 1, "nodes": plan["nodes"]}
        # Reuse only the exact prior node and an already-reused dependency closure.
        # A changed input cannot smuggle an old downstream review into the new plan.
        remaining = list(plan["nodes"])
        while remaining:
            reused = []
            for node in remaining:
                cached = run["reusable_results"].get(node["id"])
                if (
                    cached
                    and cached["node"] == node
                    and not self._successful(run, node["id"])
                    and all(self._successful(run, dep) for dep in node["depends_on"])
                ):
                    attempt = copy.deepcopy(cached["attempt"])
                    attempt["id"] = str(uuid4())
                    attempt["reused_from_run"] = run["previous_run_id"]
                    attempt["plan_version"] = run["active_plan"]["version"]
                    run["attempts"][attempt["id"]] = attempt
                    reused.append(node)
            if not reused:
                break
            remaining = [node for node in remaining if node not in reused]
        return {"version": run["active_plan"]["version"], "cancel_attempt_ids": cancel_ids}

    def _op_reserve(self, run, payload, agent_id):
        _fields(payload, {"node_id", "expected_version", "max_tokens"})
        self._root(run, agent_id)
        self._admitting(run)
        if (
            type(payload["expected_version"]) is not int
            or payload["expected_version"] != run["active_plan"]["version"]
        ):
            raise SpecialistError("计划版本已变化", "specialist_plan_conflict", 409)
        if type(payload["max_tokens"]) is not int or not 1 <= payload["max_tokens"] <= 65536:
            raise SpecialistError("节点输出限额无效")
        node = next((n for n in run["active_plan"]["nodes"] if n["id"] == payload["node_id"]), None)
        if not node:
            raise SpecialistError("计划节点不存在")
        if any(a["status"] in _LIVE and a["invalidated"] for a in run["attempts"].values()):
            raise SpecialistError("旧节点取消尚未确认", "specialist_cancel_pending", 409)
        if any(
            a["node_id"] == node["id"] and a["status"] in _LIVE for a in run["attempts"].values()
        ) or self._successful(run, node["id"]):
            raise SpecialistError("节点已有尝试，不能重复提交", "specialist_duplicate_node", 409)
        if any(
            a["node_id"] == node["id"] and a["plan_version"] == run["active_plan"]["version"]
            for a in run["attempts"].values()
        ):
            raise SpecialistError(
                "失败节点须显式修订计划或确认续跑", "specialist_retry_required", 409
            )
        if (
            sum(a["status"] in _LIVE for a in run["attempts"].values())
            >= run["budget"]["max_concurrency"]
        ):
            raise SpecialistError("并发额度已占用", "specialist_concurrency_limit", 409)
        inputs = {}
        input_snapshots = {}
        for dependency in node["depends_on"]:
            previous = self._successful(run, dependency)
            if previous is None:
                raise SpecialistError(
                    "依赖尚未形成有效成果", "specialist_dependency_incomplete", 409
                )
            inputs[dependency] = previous["result"]
            input_snapshots[dependency] = previous["evidence_snapshot"]
        selected_skills = node["skills"] or self._role(run, node["role"])["skills"]
        if set(selected_skills) - run.get("skills", {}).keys():
            raise SpecialistError(
                "节点研究方法尚未冻结或不可用", "specialist_skill_unavailable", 409
            )
        skill_records = {name: run["skills"][name] for name in selected_skills}
        attempt_id, child_id = str(uuid4()), str(uuid4())
        prompt = (
            f"你是{node['role']}专业研究节点。{self._role(run, node['role'])['responsibility']}\n"
            "使用独立上下文，不创建子Agent，不自行读取其他任务历史。只使用当前会话获授权工具；"
            "公开来源替代须记录差异和缺口。不得自动重试未知请求。\n"
            f"研究截止日：{run['as_of_date']}。超出截止日披露不可进入当前结论。\n"
            "执行研究前，必须通过原生 skill 工具逐项载入以下冻结的方法；只能读取所列本会话资源路径。"
            "记录要求不代表方法已经载入，不得自行声称已载入。\n"
            f"冻结方法：{json.dumps(skill_records, ensure_ascii=False)}\n"
            f"本轮输入：{json.dumps(node['input'], ensure_ascii=False)}\n"
            f"明确引用的依赖成果：{json.dumps(inputs, ensure_ascii=False)}\n"
            "最终仅返回JSON对象，字段为conclusion,evidence_ids,as_of_date,limitations,artifact_ids。"
            "缺证据须明确限制；模型自评不授予定稿权限。"
        )
        attempt = {
            "id": attempt_id,
            "node_id": node["id"],
            "child_id": child_id,
            "parent_session_id": run["session_id"],
            "plan_version": run["active_plan"]["version"],
            "input_hash": _digest(
                [
                    node,
                    inputs,
                    input_snapshots,
                    run["as_of_date"],
                    run["model"],
                    run["registry"]["digest"],
                    skill_records,
                ]
            ),
            "created_at": self.clock(),
            "status": "reserved",
            "invalidated": False,
            "result": None,
            "usage": None,
            "message_id": None,
            "run_id": None,
            "max_tokens": payload["max_tokens"],
            "required_skill_names": [record["native_name"] for record in skill_records.values()],
            "skill_snapshots": skill_records,
        }
        run["attempts"][attempt_id] = attempt
        return {**attempt, "attempt_id": attempt_id, "prompt": prompt}

    def _attempt(self, run, payload, agent_id, *, terminal=False):
        attempt = run["attempts"].get(payload["attempt_id"])
        if attempt is None or payload.get("child_id", attempt["child_id"]) != attempt["child_id"]:
            raise SpecialistError("子会话与节点尝试不匹配", "specialist_actor_denied", 403)
        if terminal:
            if agent_id != attempt["child_id"] and agent_id != run["session_id"]:
                raise SpecialistError("子会话终态来源不匹配", "specialist_actor_denied", 403)
        else:
            self._root(run, agent_id)
        return attempt

    def _op_accepted(self, run, payload, agent_id):
        _fields(payload, {"attempt_id", "message_id"}, {"child_id"})
        attempt = self._attempt(run, payload, agent_id)
        if not isinstance(payload["message_id"], str) or not payload["message_id"]:
            raise SpecialistError("缺少原生受理标识")
        if attempt["message_id"] is not None and attempt["message_id"] != payload["message_id"]:
            raise SpecialistError("原生受理标识不可覆盖", "specialist_conflict", 409)
        attempt["message_id"] = payload["message_id"]
        if attempt["status"] in {"reserved", "dispatching", "unknown"}:
            attempt["status"] = "accepted"

    def _op_dispatch(self, run, payload, agent_id):
        _fields(payload, {"attempt_id", "child_id"})
        self._admitting(run)
        attempt = self._attempt(run, payload, agent_id)
        if attempt["status"] != "reserved" or attempt.get("dispatch_at") is not None:
            raise SpecialistError("原生提交意图不可重复", "specialist_duplicate_dispatch", 409)
        attempt.update(status="dispatching", dispatch_at=self.clock())
        return {"dispatch_admitted": True}

    def _op_submission_unknown(self, run, payload, agent_id):
        _fields(payload, {"attempt_id"}, {"child_id"})
        attempt = self._attempt(run, payload, agent_id)
        if attempt["status"] in {"reserved", "dispatching"}:
            attempt["status"] = "unknown"

    def _op_submission_rejected(self, run, payload, agent_id):
        _fields(payload, {"attempt_id", "code"}, {"child_id"})
        attempt = self._attempt(run, payload, agent_id)
        if attempt["status"] not in {"reserved", "dispatching"}:
            raise SpecialistError("已提交或未知请求不能标记为未发送", "specialist_conflict", 409)
        attempt.update(status="failed", failure_code=str(payload["code"])[:100])

    def _op_terminal(self, run, payload, agent_id):
        _fields(
            payload,
            {"attempt_id", "child_id", "stop_reason"},
            {
                "run_id",
                "terminal_observation",
                "result",
                "usage",
                "evidence_snapshot",
            },
        )
        attempt = self._attempt(run, payload, agent_id, terminal=True)
        native_run_id = payload.get("run_id")
        observation = payload.get("terminal_observation")
        if payload["stop_reason"] not in _STOP_REASONS or (
            native_run_id is not None
            and (not isinstance(native_run_id, str) or not 1 <= len(native_run_id) <= 200)
        ):
            raise SpecialistError("原生结束事件无效")
        if observation is not None:
            _fields(observation, {"kind", "child_id", "end_seq", "event_sha256", "turn"})
            if (
                observation["kind"] != "history"
                or observation["child_id"] != attempt["child_id"]
                or type(observation["end_seq"]) is not int
                or observation["end_seq"] < 0
                or type(observation["turn"]) is not int
                or observation["turn"] < 0
                or not isinstance(observation["event_sha256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", observation["event_sha256"])
            ):
                raise SpecialistError("历史终态观察身份无效")
        if native_run_id is None and observation is None:
            raise SpecialistError("缺少可信原生或历史终态身份")
        result = None
        stop = payload["stop_reason"]
        if stop == "completed":
            try:
                result = NodeResult.model_validate(payload.get("result")).model_dump()
                if result["as_of_date"] != run["as_of_date"]:
                    raise ValueError("cutoff mismatch")
                if not result["evidence_ids"]:
                    raise ValueError("evidence missing")
                if not self._snapshot_valid(result, payload.get("evidence_snapshot")):
                    raise ValueError("qualified evidence snapshot missing")
            except (ValidationError, ValueError):
                stop = "invalid_output"
        snapshot = payload.get("evidence_snapshot") if stop == "completed" else None
        digest = _digest([attempt["id"], attempt["child_id"], stop, result, snapshot])
        if attempt["status"] not in _LIVE:
            if attempt.get("terminal_fact_digest") == digest:
                # A later verified history observation may corroborate live settlement.
                # It must not replace the native provenance or a frozen outcome.
                if observation and not attempt.get("terminal_observation"):
                    attempt["terminal_observation"] = copy.deepcopy(observation)
                return {"already_recorded": True}
            raise SpecialistError("终态不可覆盖", "specialist_terminal_conflict", 409)
        if payload.get("usage") is not None:
            attempt["usage"] = self._usage(payload["usage"])
        attempt.update(
            run_id=native_run_id,
            native_run_id=native_run_id,
            terminal_observation=copy.deepcopy(observation),
            stop_reason=stop,
            finished_at=self.clock(),
            terminal_fact_digest=digest,
            evidence_snapshot=copy.deepcopy(snapshot),
            status=(
                "succeeded"
                if stop == "completed"
                else "cancelled" if stop == "aborted" else "failed"
            ),
        )
        if attempt["invalidated"] or run["cancel_requested"]:
            attempt["late_result"] = result
            attempt["result"] = None
            attempt["invalidated"] = True
        else:
            attempt["result"] = result
        return {"attempt_id": attempt["id"], "status": attempt["status"]}

    def _op_cancel(self, run, payload, agent_id):
        _fields(payload, set(), {"attempt_id"})
        self._root(run, agent_id)
        selected = payload.get("attempt_id")
        if selected and selected not in run["attempts"]:
            raise SpecialistError("节点尝试不存在")
        if not selected:
            run["cancel_requested"] = True
        pending = []
        for attempt in run["attempts"].values():
            if attempt["status"] in _LIVE and (selected is None or attempt["id"] == selected):
                if attempt["status"] != "cancel_requested":
                    attempt["cancelled_from_status"] = attempt["status"]
                attempt["status"] = "cancel_requested"
                pending.append(attempt["id"])
        return {"cancel_attempt_ids": pending}

    def _op_recover(self, run, payload, agent_id):
        _fields(payload, set())
        self._root(run, agent_id)
        historical_ready = (
            self._structurally_ready(run)
            and run.get("completed_at") is not None
            and run["completed_at"] <= run["deadline"]
        )
        if not historical_ready and run["status"] not in {"cancelled", "incomplete"}:
            run["status"] = "needs_attention"
        run["recovered_at"] = self.clock()
        for attempt in run["attempts"].values():
            if attempt["status"] == "dispatching":
                attempt["status"] = "unknown"
        return {"observation_only": True}

    @staticmethod
    def _usage(value):
        _fields(value, {"input_tokens", "output_tokens"})
        if any(type(count) is not int or count < 0 for count in value.values()):
            raise SpecialistError("原生Token用量无效")
        return dict(value)

    def _op_model_request(self, run, payload, agent_id):
        _fields(payload, {"request_id", "reserved_tokens", "turn", "step"})
        self._admitting(run)
        attempt = self._actor(run, agent_id)
        if attempt and (
            attempt["status"] not in _LIVE
            or attempt["invalidated"]
            or attempt["status"] == "cancel_requested"
            or attempt.get("dispatch_at") is None
        ):
            raise SpecialistError("节点不再允许模型调用", "specialist_not_admitting", 409)
        if type(payload["reserved_tokens"]) is not int or payload["reserved_tokens"] <= 0:
            raise SpecialistError("模型请求必须预留有界Token")
        if not isinstance(payload["request_id"], str) or not 1 <= len(payload["request_id"]) <= 160:
            raise SpecialistError("模型请求标识无效")
        if any(type(payload[key]) is not int or payload[key] < 0 for key in ("turn", "step")):
            raise SpecialistError("模型请求缺少真实回合和步骤")
        key = f"{agent_id}:{payload['request_id']}"
        if key in run["model_requests"]:
            raise SpecialistError("原生模型请求不可重复发送", "specialist_duplicate_request", 409)
        if any(
            item["agent_id"] == agent_id
            and item["turn"] == payload["turn"]
            and item["step"] == payload["step"]
            for item in run["model_requests"].values()
        ):
            raise SpecialistError(
                "同一原生回合步骤不可重复发送", "specialist_duplicate_request", 409
            )
        requests = run["model_requests"].values()
        total = sum(
            sum(item["usage"].values()) if item["usage"] is not None else item["reserved_tokens"]
            for item in requests
        )
        if (
            len(run["model_requests"]) >= run["budget"]["max_calls"]
            or total + payload["reserved_tokens"] > run["budget"]["max_tokens"]
        ):
            raise SpecialistError("模型调用预算不足", "specialist_budget_exhausted", 409)
        run["model_requests"][key] = {
            "request_id": payload["request_id"],
            "agent_id": agent_id,
            "turn": payload["turn"],
            "step": payload["step"],
            "reserved_tokens": payload["reserved_tokens"],
            "usage": None,
            "admitted_at": self.clock(),
        }
        return {
            "admitted": True,
            "remaining_ms": int(max(0, run["deadline"] - self.clock()) * 1000),
        }

    def _op_model_usage(self, run, payload, agent_id):
        _fields(payload, {"request_id", "input_tokens", "output_tokens"})
        key = f"{agent_id}:{payload['request_id']}"
        request = run["model_requests"].get(key)
        if request is None:
            raise SpecialistError("用量没有对应的准入请求", "specialist_request_unknown", 409)
        usage = self._usage({key: payload[key] for key in ("input_tokens", "output_tokens")})
        if request["usage"] is not None and request["usage"] != usage:
            raise SpecialistError("原生用量不可覆盖", "specialist_usage_conflict", 409)
        request["usage"] = usage
        if sum(usage.values()) > request["reserved_tokens"]:
            run["status"] = "needs_attention"
            request["reservation_exceeded"] = True
        return {"usage_recorded": True}

    def _refresh(self, run):
        active = any(a["status"] in _LIVE for a in run["attempts"].values())
        ready = self._structurally_ready(run)
        if not ready:
            run["completed_at"] = None
        if run["cancel_requested"]:
            run["status"] = "cancel_pending" if active else "cancelled"
        elif run["status"] == "needs_attention":
            return
        elif ready:
            if run.get("completed_at") is None and self.clock() <= run["deadline"]:
                run["completed_at"] = self.clock()
            run["status"] = (
                "ready_for_validation"
                if run.get("completed_at") is not None and run["completed_at"] <= run["deadline"]
                else "needs_attention"
            )
        elif self.clock() >= run["deadline"]:
            run["status"] = "needs_attention"
        elif run["active_plan"]["nodes"]:
            if active:
                run["status"] = "running"
            elif any(a["status"] == "failed" for a in run["attempts"].values()):
                run["status"] = "incomplete"
            else:
                run["status"] = "running"
