"""Host-owned canonical projection and exact-byte Huaan finalization bindings.

The native research quality gate still judges evidence and content. This module
only scopes the report workflow, independently rereads its frozen input, and
binds files produced by the existing reviewed renderer. Model output is never a
projection receipt or a quality verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from core.observability import get_logger

from ..datahub.security import atomic_json, directory, read_file
from ..resources.research_report import validate_payload
from ..store import StoreError
from .models import WorkflowError

log = get_logger(__name__)
POLICY_ID = "huaan-etf-weekly-v1"
WORKFLOW_ID = "huaan-etf-weekly"
INSUFFICIENT_NEWS = "本期未取得足够可核验材料。"
_SNAPSHOT = "inputs/report-workflow/snapshots/report-data.json"
_CONTEXT = "inputs/report-workflow/run-context.json"
_CANONICAL = "outputs/research-report.json"
_LIMIT = 16 * 1024 * 1024


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_digest(value) -> str:
    return _digest(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )


def _core_digest(value: dict) -> str:
    return _json_digest(
        {
            key: item
            for key, item in value.items()
            if key not in {"artifacts", "audit_attachment", "report_formats"}
        }
    )


def _read(root: Path, relative: str, *, limit: int = _LIMIT) -> bytes:
    logical = PurePosixPath(relative)
    if (
        logical.is_absolute()
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in logical.parts)
    ):
        raise WorkflowError("周报文件引用无效", "weekly_file_invalid", 409)
    with directory(root, logical.parts[:-1]) as folder:
        return read_file(folder, logical.name, limit=limit)


def _write(root: Path, relative: str, value: dict) -> None:
    logical = PurePosixPath(relative)
    with directory(root, logical.parts[:-1], create=True) as folder:
        atomic_json(folder, logical.name, value)


def weekly_enabled(manifest) -> bool:
    return (
        manifest.workflow_id == WORKFLOW_ID
        and getattr(manifest, "weekly_production", None) is not None
    )


def freeze_weekly_production(manifest, data_contract: dict) -> dict:
    """Freeze original block obligations and explicitly permitted news gaps."""
    if not weekly_enabled(manifest):
        raise WorkflowError("周报自动定稿策略未启用", "weekly_policy_missing", 409)
    return {
        "policy_id": POLICY_ID,
        "workflow_id": manifest.workflow_id,
        "version": manifest.version,
        "cutoff": data_contract["cutoff"],
        "as_of": data_contract["cutoff"][:10],
        "data_contract": data_contract,
        "news_block_ids": list(manifest.weekly_production.news_block_ids),
        "requirements": [
            {"id": block.id, "text": block.title} for block in manifest.blocks if block.required
        ],
    }


def trusted_weekly_context(service, sid: str) -> dict | None:
    """Accept only the run and exact input bytes frozen by the Host runtime."""
    marker = service.store.session(sid).get("report_workflow") or {}
    if marker.get("quality_policy") != POLICY_ID:
        return None
    try:
        if marker.get("workflow_id") != WORKFLOW_ID:
            raise ValueError("wrong workflow")
        run = service.report_workflows.runtime._run(marker["run_id"])
        if (
            any(run.get(key) != marker.get(key) for key in ("workflow_id", "version"))
            or run.get("id") != marker["run_id"]
            or run.get("session_id") != sid
        ):
            raise ValueError("wrong run")
        root = service.store.directory(sid)
        raw = _read(root, _CONTEXT, limit=1_000_000)
        context = json.loads(raw)
        frozen = run.get("weekly_production")
        if (
            not isinstance(frozen, dict)
            or frozen.get("policy_id") != POLICY_ID
            or frozen != context.get("weekly_production")
            or _digest(raw) != run.get("weekly_context_sha256")
        ):
            raise ValueError("changed context")
        snapshot = _read(root, _SNAPSHOT)
        if _digest(snapshot) != run.get("dataset_snapshot_sha256"):
            raise ValueError("changed snapshot")
        return {
            **frozen,
            "run_id": run["id"],
            "session_id": sid,
            "snapshot_sha256": _digest(snapshot),
        }
    except (OSError, ValueError, TypeError, KeyError, StoreError) as exc:
        log.warning("report_weekly_context_rejected", error_type=type(exc).__name__)
        raise WorkflowError("周报受信上下文校验失败", "weekly_context_invalid", 409) from None


def weekly_verified_evidence(service, sid: str) -> dict | None:
    """Rebuild observations from the same owned bytes on every quality check."""
    frozen = trusted_weekly_context(service, sid)
    if frozen is None:
        return None
    from .weekly_data import assess_weekly_snapshot

    raw = _read(service.store.directory(sid), _SNAPSHOT)
    try:
        snapshot = json.loads(raw)
        assessment = assess_weekly_snapshot(snapshot, frozen["data_contract"])
        if assessment.get("status") != "passed":
            raise ValueError("weekly data no longer verified")
        service.store.files(sid)
        fid = hashlib.sha256(_SNAPSHOT.encode()).hexdigest()[:24]
        if service.store.session(sid).get("files", {}).get(fid) != _SNAPSHOT:
            raise ValueError("snapshot not registered")
        return {
            "assessment": assessment,
            "snapshot": snapshot,
            "source_id": "file:" + fid,
            "source_sha256": _digest(raw),
            "content": raw.decode("utf-8", errors="strict"),
        }
    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
        log.warning("report_weekly_evidence_rejected", error_type=type(exc).__name__)
        raise WorkflowError("周报原始数据不再通过核验", "weekly_evidence_invalid", 409) from None


def canonical_projection(value: dict, context: dict, binding: dict) -> dict:
    """Map the only editable report body into the existing template renderer."""
    try:
        validate_payload(value)
        if value["task_id"] != binding["task_id"]:
            raise ValueError("wrong task")
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowError("规范报告身份或结构无效", "weekly_canonical_invalid", 409) from exc
    declared = {block["id"]: block for block in context.get("blocks", [])}
    sections = {section.get("id"): section for section in value["sections"]}
    required = {key for key, block in declared.items() if block.get("required", True)}
    if (
        not required.issubset(sections)
        or None in sections
        or any(not sections[key]["text"].strip() for key in required)
        or not set(sections).issubset(declared)
    ):
        raise WorkflowError("规范报告缺少必需区块或包含未知区块", "weekly_blocks_incomplete", 409)
    return {
        "title": value["title"],
        "summary": value.get("summary", ""),
        "as_of": value.get("as_of", ""),
        "sections": [
            {"id": key, "title": sections[key]["heading"], "content": sections[key]["text"]}
            for key in declared
            if key in sections
        ],
        "sources": value.get("sources", []),
        "missing": value.get("missing", []),
        "binding": dict(binding),
    }


def stage_weekly_projection(service, sid: str) -> dict:
    frozen = trusted_weekly_context(service, sid)
    if frozen is None:
        raise WorkflowError("周报自动定稿策略未启用", "weekly_policy_missing", 409)
    root = service.store.directory(sid)
    raw = _read(root, _CANONICAL, limit=2_000_000)
    canonical = json.loads(raw)
    session = service.store.session(sid)
    receipt = service.store.data["receipts"].get(f"{sid}:{session.get('delivery_key', '')}", {})
    contract = receipt.get("research_contract") or {}
    if (
        canonical.get("task_id") != contract.get("task_id")
        or canonical.get("as_of") != frozen["as_of"]
    ):
        raise WorkflowError("规范报告与冻结任务不一致", "weekly_canonical_task_mismatch", 409)
    context = json.loads(_read(root, _CONTEXT, limit=1_000_000))
    binding = {
        "policy_id": POLICY_ID,
        "task_id": contract["task_id"],
        "contract_sha256": contract["sha256"],
        "canonical_core_sha256": _core_digest(canonical),
        "snapshot_sha256": frozen["snapshot_sha256"],
        "workflow_id": WORKFLOW_ID,
        "version": frozen["version"],
        "run_id": frozen["run_id"],
    }
    payload = canonical_projection(canonical, context, binding)
    _write(root, "outputs/report_payload.json", payload)
    binding["payload_sha256"] = _digest(_read(root, "outputs/report_payload.json", limit=2_000_000))
    binding["preprojection_canonical_sha256"] = _digest(raw)
    log.info("report_weekly_canonical_projected", session_id=sid)
    return binding


def _validate_artifact(name: str, raw: bytes) -> None:
    suffix = name.rsplit(".", 1)[-1]
    if suffix == "html":
        text = raw.decode("utf-8", errors="strict")
    elif suffix in {"docx", "xlsx", "pptx"}:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) > 2048 or sum(item.file_size for item in members) > 32 * 1024 * 1024:
                raise ValueError("weekly artifact archive limit")
            if suffix == "docx" and "word/document.xml" not in archive.namelist():
                raise ValueError("weekly document missing")
            text = "".join(
                archive.read(item.filename).decode("utf-8", errors="strict")
                for item in members
                if item.filename.endswith(".xml")
            )
    elif suffix == "pdf":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("weekly pdf invalid")
        text = ""
    else:
        raise ValueError("weekly artifact unsupported")
    if re.search(r"\{\{[^{}]{1,200}\}\}", re.sub(r"<[^>]*>", "", text)):
        raise ValueError("weekly artifact placeholder remains")


def bind_weekly_projection(service, sid: str, staged: dict, projection: dict) -> dict:
    """Record a Host-produced projection before the unchanged quality gate runs."""
    frozen = trusted_weekly_context(service, sid)
    root = service.store.directory(sid)
    raw = _read(root, _CANONICAL, limit=2_000_000)
    if (
        frozen is None
        or _digest(raw) != staged.get("preprojection_canonical_sha256")
        or _digest(_read(root, "outputs/report_payload.json", limit=2_000_000))
        != staged.get("payload_sha256")
    ):
        raise WorkflowError("规范报告在排版过程中发生变化", "weekly_projection_changed", 409)
    canonical = json.loads(raw)
    artifacts = []
    for relative in projection.get("files", []):
        if not isinstance(relative, str) or not re.fullmatch(
            r"outputs/[A-Za-z0-9][A-Za-z0-9._-]{0,149}", relative
        ):
            raise WorkflowError("周报产物引用无效", "weekly_artifact_invalid", 409)
        body = _read(root, relative)
        _validate_artifact(relative, body)
        artifacts.append({"name": PurePosixPath(relative).name, "sha256": _digest(body)})
    if not artifacts or len({item["name"] for item in artifacts}) != len(artifacts):
        raise WorkflowError("周报产物不完整", "weekly_artifact_missing", 409)
    native = [
        item for item in artifacts if item["name"].rsplit(".", 1)[-1] in {"html", "docx", "pdf"}
    ]
    if not native:
        raise WorkflowError("周报缺少规范文档产物", "weekly_artifact_missing", 409)
    context = json.loads(_read(root, _CONTEXT, limit=1_000_000))
    required_blocks = {
        item["id"]
        for item in context.get("blocks", [])
        if item.get("required", True) and item.get("kind") in {"chart", "table"}
    }
    block_bindings = projection.get("weekly_block_bindings") or []
    if (
        not isinstance(block_bindings, list)
        or {item.get("id") for item in block_bindings if isinstance(item, dict)} != required_blocks
        or len(block_bindings) != len(required_blocks)
        or any(
            item.get("snapshot_sha256") != frozen["snapshot_sha256"]
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("content_sha256", "")))
            for item in block_bindings
        )
    ):
        raise WorkflowError(
            "周报图表或表格未绑定本期数据", "weekly_structured_blocks_unverified", 409
        )
    templates = []
    for item in context.get("template_resources", []):
        relative = "inputs/report-workflow/" + item["path"]
        actual = _digest(_read(root, relative))
        if actual != item["sha256"]:
            raise WorkflowError("周报模板发生变化", "weekly_template_changed", 409)
        templates.append({"path": relative, "sha256": actual})
    if not any(item["path"].lower().endswith(".docx") for item in templates):
        raise WorkflowError("周报缺少原版 Word 模板", "weekly_template_missing", 409)
    workbooks = []
    for item in (context.get("workbook_projection") or {}).get("workbooks", []):
        relative = "inputs/report-workflow/" + item["path"]
        actual = _digest(_read(root, relative))
        if actual != item["sha256"]:
            raise WorkflowError("周报底稿发生变化", "weekly_workbook_changed", 409)
        workbooks.append({"path": relative, "sha256": actual})
    canonical["artifacts"] = native
    canonical["report_formats"] = [item["name"].rsplit(".", 1)[-1] for item in native]
    _write(root, _CANONICAL, canonical)
    record = {
        **staged,
        "canonical_sha256": _digest(_read(root, _CANONICAL, limit=2_000_000)),
        "context_sha256": _digest(_read(root, _CONTEXT, limit=1_000_000)),
        "artifacts": artifacts,
        "templates": templates,
        "workbooks": workbooks,
        "block_bindings": block_bindings,
        "created_at": time.time(),
    }
    session = service.store.session(sid)
    receipt = service.store.data["receipts"][f"{sid}:{session['delivery_key']}"]
    if receipt.get("research_contract", {}).get("sha256") != staged["contract_sha256"]:
        raise WorkflowError("周报研究任务已改变", "weekly_contract_changed", 409)
    receipt["weekly_projection"] = record
    service.store.save()
    log.info("report_weekly_projection_bound", session_id=sid, artifact_count=len(artifacts))
    return record


def has_weekly_policy(store, sid: str) -> bool:
    return (store.session(sid).get("report_workflow") or {}).get("quality_policy") == POLICY_ID


def verify_weekly_rendered_artifact(store, sid: str, payload: dict, kind: str, body: bytes) -> None:
    """The template-specific check requires a private Host receipt, never a flag."""
    try:
        session = store.session(sid)
        marker = session.get("report_workflow") or {}
        receipt = store.data["receipts"].get(f"{sid}:{session.get('delivery_key', '')}", {})
        binding = receipt.get("weekly_projection") or {}
        contract = receipt.get("research_contract") or {}
        if (
            not has_weekly_policy(store, sid)
            or binding.get("policy_id") != POLICY_ID
            or binding.get("workflow_id") != WORKFLOW_ID
            or any(
                binding.get(key) != marker.get(key) for key in ("workflow_id", "version", "run_id")
            )
            or binding.get("task_id") != payload.get("task_id")
            or binding.get("task_id") != contract.get("task_id")
            or binding.get("contract_sha256") != contract.get("sha256")
        ):
            raise ValueError("weekly projection scope invalid")
        root = store.directory(sid)
        if (
            _digest(_read(root, _CANONICAL, limit=2_000_000)) != binding.get("canonical_sha256")
            or _core_digest(payload) != binding.get("canonical_core_sha256")
            or _digest(_read(root, _SNAPSHOT)) != binding.get("snapshot_sha256")
            or _digest(_read(root, _CONTEXT, limit=1_000_000)) != binding.get("context_sha256")
        ):
            raise ValueError("weekly projection content changed")
        for template in [*binding.get("templates", []), *binding.get("workbooks", [])]:
            if _digest(_read(root, template["path"])) != template["sha256"]:
                raise ValueError("weekly template changed")
        candidates = [
            item for item in binding.get("artifacts", []) if item["name"].rsplit(".", 1)[-1] == kind
        ]
        if len(candidates) != 1 or candidates[0]["sha256"] != _digest(body):
            raise ValueError("weekly projection artifact changed")
        _validate_artifact(candidates[0]["name"], body)
        log.info("report_weekly_render_verified", format=kind)
    except (OSError, ValueError, KeyError, TypeError, StoreError, zipfile.BadZipFile) as exc:
        log.warning("report_weekly_render_rejected", error_type=type(exc).__name__)
        raise ValueError("research_report_weekly_render_binding_changed") from None


def finalization_binding(service, sid: str) -> dict:
    """Fail closed unless the Host checked these exact canonical and file bytes."""
    evidence = weekly_verified_evidence(service, sid)
    session = service.store.session(sid)
    receipt = service.store.data["receipts"].get(f"{sid}:{session.get('delivery_key', '')}", {})
    projection = receipt.get("weekly_projection") or {}
    checked = receipt.get("quality_last_result") or {}
    canonical_raw = _read(service.store.directory(sid), _CANONICAL, limit=2_000_000)
    canonical = json.loads(canonical_raw)
    if (
        evidence is None
        or checked.get("status") != "passed"
        or checked.get("report_content_sha256") != _digest(canonical_raw)
        or projection.get("canonical_sha256") != _digest(canonical_raw)
        or checked.get("contract") != receipt.get("research_contract")
    ):
        raise WorkflowError("周报质量结果尚未绑定当前版本", "weekly_quality_unbound", 409)
    from ..research_quality_service import report_delivery

    archived = report_delivery(service, sid, receipt, _digest(canonical_raw))
    if archived.get("status") != "bound" or archived.get("quality_status") != "passed":
        raise WorkflowError("周报定稿归档未绑定当前版本", "weekly_archive_unbound", 409)
    for item in projection.get("artifacts", []):
        body = _read(service.store.directory(sid), "outputs/" + item["name"])
        if _digest(body) != item["sha256"]:
            raise WorkflowError("周报产物已改变", "weekly_artifact_changed", 409)
        if item["name"].rsplit(".", 1)[-1] in {"html", "docx", "pdf"}:
            verify_weekly_rendered_artifact(
                service.store, sid, canonical, item["name"].rsplit(".", 1)[-1], body
            )
    return {
        "policy_id": POLICY_ID,
        "task_id": canonical["task_id"],
        "contract_sha256": receipt["research_contract"]["sha256"],
        "canonical_sha256": _digest(canonical_raw),
        "snapshot_sha256": evidence["source_sha256"],
        "artifacts": projection["artifacts"],
        "archive": {
            key: archived[key]
            for key in ("version_id", "files", "report_content_sha256", "quality_status")
        },
        "finalized_at": time.time(),
    }
