"""Host-only weekly execution scope and durable, non-replayable RPC claim.

Neither this scope nor the attempt journal is a model-supplied permission.
The journal lives in the private Run, outside the native script workspace.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from pathlib import PurePosixPath

from core.observability import get_logger

from ..datahub.security import directory, read_file, write_new
from ..store import StoreError
from .models import WorkflowError
from .weekly_quality import (
    freeze_weekly_production,
    trusted_weekly_context,
    weekly_verified_evidence,
)

log = get_logger(__name__)
PROTOCOL = "weekly-admission-v2"
ATTEMPT = "weekly-rpc-attempt.json"
TOOLS = (
    "todo_write",
    "research_run_script",
    "research_check_quality",
    "research_read_source",
    "ask_user_question",
    "datahub_search_news",
    "datahub_search_announcements",
    "datahub_search_research",
    "datahub_search_web",
    "subagent",
    "send_message",
    "interrupt_agent",
    "list_agents",
)
MODEL_FIELDS = ("model", "model_provider", "model_profile_id", "model_connection_binding")


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def has_attempt(root):
    """Any existing claim, including corrupt/symlink claims, prevents a replay."""
    with directory(root) as folder:
        try:
            os.stat(ATTEMPT, dir_fd=folder, follow_symlinks=False)
        except FileNotFoundError:
            return False
    return True


def create_attempt(root, value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    if len(raw) > 16_384 or not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise WorkflowError("周报提交记录无效", "weekly_attempt_invalid", 409)
    try:
        with directory(root) as folder:
            write_new(folder, ATTEMPT, raw)
            os.fsync(folder)
            if json.loads(read_file(folder, ATTEMPT, private=True, limit=16_384)) != value:
                raise ValueError("claim readback mismatch")
    except (OSError, ValueError, StoreError) as exc:
        log.error("weekly_attempt_persist_failed", error_type=type(exc).__name__)
        raise WorkflowError(
            "周报提交记录无法持久保存，未提交", "weekly_attempt_failed", 409
        ) from exc


def _inputs(service, sid, expected=None):
    root = service.store.directory(sid) / "inputs" / "report-workflow"
    files = {}
    if expected is not None:
        for name in expected:
            logical = PurePosixPath(name)
            if (
                logical.is_absolute()
                or "\\" in name
                or any(part in {"", ".", ".."} for part in logical.parts)
            ):
                raise WorkflowError("周报输入路径异常", "weekly_scope_invalid", 409)
    paths = [root / name for name in expected] if expected is not None else sorted(root.rglob("*"))
    for path in paths:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise WorkflowError("周报输入包含链接", "weekly_scope_invalid", 409)
        if path.is_dir():
            continue
        if not stat.S_ISREG(info.st_mode) or len(files) >= 320:
            raise WorkflowError("周报输入类型或数量异常", "weekly_scope_invalid", 409)
        relative = path.relative_to(root)
        with directory(root, relative.parts[:-1]) as folder:
            raw = read_file(folder, relative.name, limit=32 * 1024 * 1024)
        files[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
    if not files:
        raise WorkflowError("周报输入缺失", "weekly_scope_invalid", 409)
    return files


def projection(service, sid, *, initialize=False, prompt=None, formats=None):
    """Revalidate all Host-owned bindings on send and every native admission."""
    frozen = trusted_weekly_context(service, sid)
    if frozen is None:
        return None
    runtime = service.report_workflows.runtime
    run = runtime._run(frozen["run_id"])
    runtime._require_weekly_owner(run.get("owner_id"))
    catalog = runtime.catalog
    workflow = catalog._row(run["workflow_id"])
    if workflow.get("status") != "enabled" or not workflow["versions"].get(
        str(run["version"]), {}
    ).get("published"):
        raise WorkflowError("周报版本已停用", "weekly_scope_invalid", 409)
    manifest = catalog.manifest(run["workflow_id"], run["version"])
    if manifest.weekly_production is None or manifest.version != frozen["version"]:
        raise WorkflowError("周报版本不匹配", "weekly_scope_invalid", 409)
    if run["weekly_production"] != freeze_weekly_production(
        manifest, frozen["data_contract"], execution_purpose=run.get("execution_purpose", "formal")
    ):
        raise WorkflowError("周报锁定版本已改变", "weekly_scope_invalid", 409)
    private_root = runtime.run_path(run["id"])
    with directory(private_root, ("snapshots",)) as folder:
        private_snapshot = read_file(folder, "report-data.json", limit=16 * 1024 * 1024)
    if hashlib.sha256(private_snapshot).hexdigest() != run["dataset_snapshot_sha256"]:
        raise WorkflowError("周报私有快照已改变", "weekly_scope_invalid", 409)
    private_resources = {}
    for resource in manifest.resources:
        logical = PurePosixPath(resource.path)
        with directory(
            service.store.directory(sid), ("inputs", "report-workflow", *logical.parts[:-1])
        ) as folder:
            raw = read_file(folder, logical.name, limit=32 * 1024 * 1024)
        with directory(private_root, logical.parts[:-1]) as folder:
            private_raw = read_file(folder, logical.name, limit=32 * 1024 * 1024)
        private_hash = hashlib.sha256(private_raw).hexdigest()
        # Workbooks are refreshed/materialized by the Host before freezing;
        # their package-original hash is not their legitimate frozen hash.
        if hashlib.sha256(raw).hexdigest() != private_hash or (
            not resource.path.startswith("workbooks/") and private_hash != resource.sha256
        ):
            raise WorkflowError("周报锁定资源已改变", "weekly_scope_invalid", 409)
        private_resources[resource.path] = private_hash
    weekly_verified_evidence(service, sid)
    row = service.store.session(sid)
    service.assert_session_model_profile(row)
    if not service._model_tools_verified(sid):
        raise WorkflowError("周报模型工具未验证", "weekly_model_unverified", 409)
    original = run.get("weekly_execution_scope")
    if initialize and original is None:
        from .evidence import prepare_weekly_evidence

        prepare_weekly_evidence(service, sid)
    binding = {
        "protocol": PROTOCOL,
        "run_id": run["id"],
        "session_id": sid,
        "workflow_id": run["workflow_id"],
        "version": run["version"],
        "owner_id": run.get("owner_id"),
        "purpose": run.get("execution_purpose", "formal"),
        "source_scope": row.get("source_scope", ["datahub", "web", "uploads"]),
        "session_purpose": row.get("purpose", "research"),
        "context_sha256": run["weekly_context_sha256"],
        "snapshot_sha256": run["dataset_snapshot_sha256"],
        "contract_sha256": _digest(frozen["data_contract"]),
        "private_resources": private_resources,
        "formats": [item.value for item in manifest.delivery.formats],
        "model": {name: row.get(name) for name in MODEL_FIELDS},
        "inputs": _inputs(
            service, sid, original.get("inputs") if isinstance(original, dict) else None
        ),
        "tools": list(TOOLS),
    }
    if initialize and original is None:
        if not isinstance(prompt, str) or formats != binding["formats"]:
            raise WorkflowError("周报执行请求不匹配", "weekly_scope_invalid", 409)
        binding["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        binding["sha256"] = _digest(binding)
        runtime._update_run(
            run["id"], weekly_execution_scope=binding, research_submission_protocol=PROTOCOL
        )
        log.info("weekly_execution_scope_frozen", run_id=run["id"])
        return binding
    if not isinstance(original, dict):
        raise WorkflowError("周报执行范围未冻结", "weekly_scope_invalid", 409)
    binding["prompt_sha256"] = original.get("prompt_sha256")
    binding["sha256"] = _digest(binding)
    if (
        original != binding
        or (
            prompt is not None
            and hashlib.sha256(prompt.encode()).hexdigest() != original["prompt_sha256"]
        )
        or (formats is not None and formats != binding["formats"])
    ):
        raise WorkflowError("周报执行范围已改变", "weekly_scope_invalid", 409)
    return original


def claim(service, sid, scope, key):
    checked = projection(service, sid)
    if checked != scope or key != "report-workflow-" + scope["run_id"]:
        raise WorkflowError("周报提交身份不匹配", "weekly_scope_invalid", 409)
    runtime = service.report_workflows.runtime
    create_attempt(
        runtime.run_path(scope["run_id"]),
        {
            "protocol": PROTOCOL,
            "run_id": scope["run_id"],
            "session_id": sid,
            "key": key,
            "scope_sha256": scope["sha256"],
            "attempted_at": time.time(),
        },
    )
    runtime._update_run(
        scope["run_id"],
        research_submission_state="rpc_attempted",
        research_admission_at=time.time(),
    )
    log.info("weekly_rpc_attempt_claimed", run_id=scope["run_id"])
