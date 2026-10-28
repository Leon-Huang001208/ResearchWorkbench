"""Closed owned-method inputs and real Native completion on the existing bridge.

Only three packaged entrypoints are executable. Source rights and original bytes
are rechecked through the existing scenario lineage on every use and quality check.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger

from .capabilities.pack_native import read_regular
from .capabilities.pack_resources import canonical
from .capabilities.packages import decode_file
from .capabilities.scenario_method_packages import METHODS, scenario_method_packages
from .datahub.security import directory
from .scenario_handoffs import bound_capabilities, fingerprint, resolve_reference, trusted_context
from .store import StoreError

log = get_logger(__name__)
POLICY = "owned-method-frozen-inputs-v1"
MAX_METHOD_BYTES = 16 * 1024 * 1024


def company_calculation_policy(store, sid, contract):
    """Rebuild the policy from Host-owned handoff and frozen contract only."""
    row = store.session(sid)
    handoff_id = row.get("scenario_handoff_id") or row.get("evidence_handoff_id")
    handoff = store.data.get("handoffs", {}).get(handoff_id, {})
    context = handoff.get("scenario_context") or {}
    if not isinstance(context, dict):
        fail("method_company_policy_binding_invalid")
    scenario = context.get("scenario", {})
    if not isinstance(scenario, dict):
        fail("method_company_policy_binding_invalid")
    execution = (contract or {}).get("execution_context", {})
    cid = "owned-company-evidence"
    if scenario.get("scenario_id") != cid and execution.get("scenario_id") != cid:
        return None
    from .scenario_handoffs import execution_context

    capabilities = scenario.get("capabilities", [])
    if (
        handoff.get("state") != "prepared"
        or handoff.get("session_id") != sid
        or scenario.get("scenario_id") != cid
        or scenario.get("version") != "1.0.0"
        or not isinstance(capabilities, list)
        or len(capabilities) != 1
        or not isinstance(capabilities[0], dict)
        or capabilities[0].get("id") != cid
        or not contract
        or any(
            key not in capabilities[0]
            for key in ("version", "sha256", "native_name", "resource_path")
        )
        or execution != execution_context(context, capabilities)
        or contract.get("as_of") != scenario.get("inputs", {}).get("as_of")
    ):
        fail("method_company_policy_binding_invalid")
    return "owned-company-positive-base-v1"


class _Preparation:
    """Own only exclusive births; rollback never removes a reused/replaced object."""

    def __init__(self, root):
        self.root, self.files, self.directories = root, [], []

    def mkdir(self, parts, *, exclusive=False):
        for index, name in enumerate(parts):
            parent = tuple(parts[:index])
            with directory(self.root, parent) as fd:
                parent_id = self.identity(os.fstat(fd))
                try:
                    os.mkdir(name, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    if exclusive and index == len(parts) - 1:
                        fail("method_output_exists")
                else:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    self.directories.append((parent, parent_id, name, self.identity(info)))
            with directory(self.root, (*parent, name)):
                pass

    @staticmethod
    def identity(info):
        return info.st_dev, info.st_ino

    def write(self, relative, raw):
        parts = tuple(relative.split("/"))
        self.mkdir(parts[:-1])
        with directory(self.root, parts[:-1]) as fd:
            try:
                handle = os.open(
                    parts[-1],
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=fd,
                )
            except FileExistsError:
                if read_regular(self.root / relative, MAX_METHOD_BYTES) != raw:
                    fail("method_input_changed")
                return
            self.files.append(
                (
                    parts[:-1],
                    self.identity(os.fstat(fd)),
                    parts[-1],
                    self.identity(os.fstat(handle)),
                )
            )
            try:
                stream = os.fdopen(handle, "wb")
            except (OSError, ValueError):
                os.close(handle)
                raise
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())

    def rollback(self):
        safe = True
        for records, directories in ((self.files, False), (self.directories, True)):
            for parent, parent_id, name, identity in reversed(records):
                try:
                    with directory(self.root, parent) as fd:
                        if self.identity(os.fstat(fd)) != parent_id:
                            safe = False
                            continue
                        try:
                            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                        except FileNotFoundError:
                            continue
                        if (
                            self.identity(info) != identity
                            or (
                                not directories
                                and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)
                            )
                            or (directories and not stat.S_ISDIR(info.st_mode))
                        ):
                            safe = False
                            continue
                        if directories:
                            os.rmdir(name, dir_fd=fd)
                        else:
                            os.unlink(name, dir_fd=fd)
                except (OSError, StoreError):
                    safe = False
        if not safe:
            log.warning("research_method_preparation_rollback_unverified")
        return safe


def fail(code):
    log.warning("research_owned_method_rejected", code=code)
    raise StoreError("方法来源、执行身份或实际产物无法核验", code, 409)


def runtime_identity():
    executable = Path(sys.executable).resolve(strict=True)
    return {
        "python": str(executable),
        "environment": str(Path(sys.prefix).resolve(strict=True)),
        "python_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "python_version": sys.version,
    }


def _file(root, relative, expected):
    if (
        not isinstance(relative, str)
        or not relative.startswith(("inputs/methods/", "resources/capabilities/"))
        or any(not p or p.startswith(".") for p in relative.split("/"))
        or re.search(r"[\\:\x00-\x1f\x7f]", relative)
    ):
        fail("method_resource_path_invalid")
    path = root / relative
    raw = read_regular(path, 16 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        fail("method_resource_changed")
    info = path.stat()
    return {
        "path": relative,
        "sha256": expected,
        "bytes": len(raw),
        "device": info.st_dev,
        "inode": info.st_ino,
    }


def source_context(service, sid, cid, context):
    """Read selected original references; no caller content or source overrides."""
    values = context["scenario"]["inputs"]
    refs = [
        reference
        for reference in context["references"]
        if not (
            (context.get("workspace") or {}).get("schema") == "research-pack-source-selection/v1"
            and reference["reference"]["type"] == "file"
            and re.fullmatch(
                r"inputs/source-selections/[a-f0-9]{64}\.json", reference["reference"]["id"]
            )
        )
    ]
    if not refs or len(refs) > 20:
        fail("method_source_selection_missing")
    key = fingerprint({"context": fingerprint(context), "capability_id": cid})
    base = "inputs/methods/" + key
    result = {
        "schema": "research_method_source_context_v1",
        "method_id": cid,
        "method_version": "1.0.0",
        "subject": values["subject"],
        "as_of": values["as_of"],
        "sources": [],
    }
    bodies, total, originals, seen = {}, 0, [], set()
    for index, reference in enumerate(refs):
        identity = (
            reference["source_session_id"],
            reference["reference"]["type"],
            reference["reference"]["id"],
        )
        if identity in seen:
            continue
        seen.add(identity)
        metadata, manifest, raw = resolve_reference(
            service,
            reference["source_session_id"],
            reference["reference"],
            expected=reference,
            target_sid=sid,
        )
        originals.append((metadata, raw))
        total += len(raw)
        if len(raw) > 8 * 1024 * 1024 or total > 16 * 1024 * 1024:
            fail("method_source_limit")
        try:
            raw.decode("utf-8", errors="strict")
        except UnicodeError:
            fail("method_source_reader_required")
        path = base + f"/source-{index}.source"
        category = (
            "news-body"
            if cid == "owned-news-evidence" and reference["reference"]["type"] == "source"
            else "unclassified"
        )
        full_text = bool(raw.strip())
        if reference["reference"]["type"] == "source":
            from .research_web_sources import capture_proof

            source = (
                service.store.session(reference["source_session_id"], include_deleted=True)
                .get("web_evidence", {})
                .get(reference["reference"]["id"], {})
            )
            full_text = (
                capture_proof(service.store.root, reference["source_session_id"], source, raw)
                is not None
            )
        if reference["reference"]["type"] == "dataset":
            # A bounded feed is not an acquired article body, even if it has text.
            full_text = False
            if manifest.get("capability") == "financials":
                category = "financials" if cid == "owned-company-evidence" else "unclassified"
        source = {
            "source_id": reference["source_session_id"] + ":" + reference["reference"]["id"],
            "path": path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "locator": f"bytes:0-{len(raw)}",
            "publication_date": metadata.get("published_at"),
            "category": category,
            "full_text": full_text,
        }
        if category == "financials":
            source["security"] = (
                manifest.get("query", {}).get("parameters", {}).get("asset", "unknown")
            )
            source["manifest_sha256"] = manifest["manifest_sha256"]
            rows = json.loads(raw)
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                fail("method_financial_rows_invalid")
            if any(row.get("asset") != source["security"] for row in rows):
                fail("method_company_security_mismatch")
            periods = {row.get("report_period") for row in rows}
            if len(periods) == 1 and all(isinstance(period, str) for period in periods):
                source["report_period"] = next(iter(periods))
            native = manifest.get("provider_metadata", {})
            if (
                native.get("schema_version") == "akshare-sina-financial-disclosure-v3"
                and native.get("upstream_id") == "sina"
            ):
                currencies = {row.get("rCurrency") for row in rows}
                if len(currencies) == 1 and all(
                    isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency)
                    for currency in currencies
                ):
                    source["currency"] = next(iter(currencies))
            # Complete acquired rows are distinct from complete company accounts.
            source["full_text"] = (
                bool(rows)
                and len(rows) == manifest.get("row_count")
                and manifest.get("status") in {"snapshot", "complete"}
            )
        result["sources"].append(source)
        bodies[path] = raw
    if cid in {"owned-news-evidence", "owned-research-prep"}:
        from .scenario_method_dedup import build_artifact

        artifact = build_artifact(service, sid, cid, values, originals)
        if artifact is not None:
            artifact_raw = canonical(artifact)
            artifact_path = base + "/c2-dedup.bound"
            bodies[artifact_path] = artifact_raw
            total += len(artifact_raw)
            result["dedup_artifact"] = {
                "path": artifact_path,
                "sha256": hashlib.sha256(artifact_raw).hexdigest(),
            }
    raw = canonical(result)
    if total + len(raw) > 16 * 1024 * 1024:
        fail("method_source_limit")
    bodies[base + "/source-context.bound"] = raw
    return result, bodies, base + "/source-context.bound"


def _resources(service, selected):
    version = service.capabilities.row(selected["id"])["versions"][str(selected["version"])]
    expected = dict(scenario_method_packages())[selected["id"]]
    if {f["path"]: f["sha256"] for f in version["files"]} != {
        f["path"]: f["sha256"] for f in expected["files"]
    }:
        fail("method_code_unverified")
    manifest = next(
        f for f in version["files"] if f["path"] == "references/method-code-manifest.json"
    )
    return version, json.loads(decode_file(manifest))["closure_sha256"]


def launcher(root, scope):
    data = base64.b64encode(
        canonical(
            {
                "root": str(root),
                "files": scope["file_bindings"],
                "scripts": scope["scripts"],
                "input": scope["input_path"],
                "execution_id": scope["binding"]["execution_id"],
            }
        )
    ).decode()
    return f"""import base64,json,sys,hashlib,os,stat
from pathlib import Path
_v=json.loads(base64.b64decode({data!r}))
for _f in _v['files']:
 _p=_v['root']+'/'+_f['path']
 with os.fdopen(os.open(_p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as _s:
  _b=os.fstat(_s.fileno());_h=hashlib.file_digest(_s,'sha256').hexdigest();_a=os.fstat(_s.fileno())
 if not stat.S_ISREG(_b.st_mode) or _b.st_nlink!=1 or (_b.st_dev,_b.st_ino,_b.st_size)!=(_f['device'],_f['inode'],_f['bytes']) or (_a.st_dev,_a.st_ino,_a.st_size,_a.st_mtime_ns,_a.st_ctime_ns)!=(_b.st_dev,_b.st_ino,_b.st_size,_b.st_mtime_ns,_b.st_ctime_ns) or _h!=_f['sha256']:
  raise ValueError('method_resource_changed')
sys.path.insert(0,_v['root']+'/'+_v['scripts'])
from check_sources import execute
_context=json.loads(Path(_v['root']+'/'+_v['input']).read_bytes())
print(json.dumps(execute(Path(_v['root']),_context,_v['execution_id']),ensure_ascii=False,separators=(',',':')))
"""


def prepare_execution(service, sid, descriptor, call_id, *, start=False):
    if (
        not isinstance(descriptor, dict)
        or set(descriptor) != {"capability_id", "version", "context_sha256"}
        or descriptor.get("capability_id") not in METHODS
        or type(descriptor.get("version")) is not int
        or not isinstance(call_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", call_id)
    ):
        fail("method_execution_descriptor_invalid")
    context = trusted_context(service, sid)
    if (
        not context
        or context["scenario"]["scenario_id"] != descriptor["capability_id"]
        or context.get("pack_seal")
    ):
        fail("method_selection_missing")
    required = bound_capabilities(service, context)
    selected = next((ref for ref in required if ref["id"] == descriptor["capability_id"]), None)
    if selected is None or descriptor != {
        "capability_id": selected["id"],
        "version": selected["version"],
        "context_sha256": fingerprint(context),
    }:
        fail("method_execution_binding_changed")
    receipt, _ = service._task_capabilities(sid)
    if (
        not receipt
        or receipt.get("scenario_discovered_capabilities")
        != [ref["native_name"] for ref in required]
        or not any(
            all(ref.get(k) == selected[k] for k in ("id", "version", "sha256"))
            for ref in receipt.get("native_capabilities", [])
        )
    ):
        fail("method_capability_not_loaded")
    contract = receipt.get("research_contract", {})
    if contract.get("execution_context", {}).get("context_sha256") != fingerprint(
        context
    ) or not re.fullmatch(r"[a-f0-9]{24}", contract.get("task_id", "")):
        fail("method_task_unverified")
    projected, bodies, input_path = source_context(service, sid, selected["id"], context)
    version, closure = _resources(service, selected)
    if not start:
        return {
            "admitted": True,
            "status": "limited",
            "missing": context["scenario"]["missing"],
            "omitted_sections": [],
            "read_paths": [],
        }
    executions = receipt.get("method_executions", [])
    if len(executions) >= 64 or any(
        item.get("call_id") == call_id
        or item["binding"].get("task_id") == contract["task_id"]
        and item["binding"].get("capability_id") == selected["id"]
        for item in executions
    ):
        fail("method_execution_unknown_do_not_retry")
    root = service.store.root / "sessions" / sid
    resources = [
        {"path": selected["resource_path"] + "/SKILL.md", "sha256": selected["sha256"]},
        *[
            {"path": selected["resource_path"] + "/" + item["path"], "sha256": item["sha256"]}
            for item in version["files"]
        ],
    ]
    if len(resources) + len(bodies) > 320:
        fail("method_resource_limit")
    try:
        resource_bindings = [_file(root, item["path"], item["sha256"]) for item in resources]
        runtime = runtime_identity()
    except OSError as exc:
        log.warning("research_method_resource_preflight_failed", error_type=type(exc).__name__)
        raise StoreError("方法资源预检失败", "method_preparation_failed", 409) from exc
    if (
        sum(item["bytes"] for item in resource_bindings) + sum(map(len, bodies.values()))
        > MAX_METHOD_BYTES
    ):
        fail("method_resource_limit")
    receipt_key = next(
        (key for key, value in service.store.data["receipts"].items() if value is receipt), None
    )
    if receipt_key is None:
        fail("method_task_unverified")
    return _freeze_preparation(
        service,
        sid,
        receipt,
        receipt_key,
        executions,
        selected,
        context,
        contract,
        projected,
        bodies,
        input_path,
        resource_bindings,
        closure,
        runtime,
        call_id,
    )


def _save_outcome(service, receipt_key, previous, execution_id):
    """A failed atomic save may have committed; uncertain commits stay unknown."""
    try:
        disk = json.loads(read_regular(service.store.index, 64 * 1024 * 1024))
        actual = disk["receipts"][receipt_key].get("method_executions", [])
        if any(item["binding"]["execution_id"] == execution_id for item in actual):
            return "present"
        return "absent" if actual == previous else "unknown"
    except (OSError, StoreError, ValueError, KeyError, TypeError):
        log.warning("research_method_preparation_save_unknown")
        return "unknown"


def _freeze_preparation(
    service,
    sid,
    receipt,
    receipt_key,
    executions,
    selected,
    context,
    contract,
    projected,
    bodies,
    input_path,
    resources,
    closure,
    runtime,
    call_id,
):
    root = service.store.root / "sessions" / sid
    execution_id = uuid4().hex
    output_root = "outputs/method-results/" + execution_id
    binding = {
        "execution_id": execution_id,
        "task_id": contract["task_id"],
        "contract_sha256": contract["sha256"],
        "call_id": call_id,
        "context_sha256": fingerprint(context),
        "input_sha256": hashlib.sha256(canonical(projected)).hexdigest(),
        "capability_id": selected["id"],
        "version": selected["version"],
        "closure_sha256": closure,
    }
    scope = {
        "admitted": True,
        "status": "limited",
        "missing": context["scenario"]["missing"],
        "omitted_sections": [],
        "input_policy": POLICY,
        "output_root": output_root,
        "input_path": input_path,
        "scripts": selected["resource_path"] + "/scripts",
        "binding": binding,
        "runtime": runtime,
    }
    # Upper bound the fixed launcher using 64-bit dev/inode placeholders before writes.
    preview = [
        *resources,
        *[
            {
                "path": p,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "device": 2**64 - 1,
                "inode": 2**64 - 1,
            }
            for p, raw in bodies.items()
        ],
    ]
    if len(launcher(root, {**scope, "file_bindings": preview}).encode()) > 65536:
        fail("method_launcher_limit")
    transaction = _Preparation(service.store.root)
    retained = False
    had_executions = "method_executions" in receipt
    try:
        for relative, raw in bodies.items():
            transaction.write("sessions/" + sid + "/" + relative, raw)
        inputs = [
            _file(root, relative, hashlib.sha256(raw).hexdigest())
            for relative, raw in bodies.items()
        ]
        # Recheck the same exact resource identities after input IO, before publication.
        if any(_file(root, item["path"], item["sha256"]) != item for item in resources):
            fail("method_resource_changed")
        transaction.mkdir(tuple(("sessions/" + sid + "/" + output_root).split("/")), exclusive=True)
        scope["file_bindings"] = [*resources, *inputs]
        scope["read_paths"] = [item["path"] for item in scope["file_bindings"]]
        scope["code"] = launcher(root, scope)
        scope["code_sha256"] = hashlib.sha256(scope["code"].encode()).hexdigest()
        if len(scope["code"].encode()) > 65536:
            fail("method_launcher_limit")
        record = {
            "schema": "research_owned_method_execution_v1",
            "state": "started",
            "started_at": time.time(),
            "call_id": call_id,
            "binding": binding,
            "scope": copy.deepcopy(scope),
            "output_root": output_root,
        }
        receipt["method_executions"] = [*executions, record]
        try:
            service.store.save()
        except (OSError, StoreError):
            outcome = _save_outcome(service, receipt_key, executions, execution_id)
            if outcome != "absent":
                retained = True
                if outcome == "unknown":
                    if had_executions:
                        receipt["method_executions"] = executions
                    else:
                        receipt.pop("method_executions", None)
                fail("method_preparation_outcome_unknown")
            raise
    except (OSError, StoreError, ValueError) as exc:
        if retained:
            raise
        if had_executions:
            receipt["method_executions"] = executions
        else:
            receipt.pop("method_executions", None)
        if not transaction.rollback():
            raise StoreError(
                "方法准备回滚无法确认，保留未知对象", "method_preparation_rollback_unverified", 409
            ) from exc
        log.warning("research_method_preparation_rolled_back", error_type=type(exc).__name__)
        if isinstance(exc, StoreError) and exc.code.startswith("method_"):
            raise
        raise StoreError("方法准备失败，未启动Native", "method_preparation_failed", 409) from exc
    log.info("research_owned_method_started", execution_id=execution_id)
    return scope


def _readback(service, sid, execution):
    context = trusted_context(service, sid)
    receipt, _ = service._task_capabilities(sid)
    binding = execution["binding"]
    if (
        not context
        or fingerprint(context) != binding["context_sha256"]
        or receipt.get("research_contract", {}).get("sha256") != binding["contract_sha256"]
        or execution["scope"]["runtime"] != runtime_identity()
    ):
        fail("method_execution_binding_changed")
    selected = next(
        (
            ref
            for ref in bound_capabilities(service, context)
            if ref["id"] == binding["capability_id"]
        ),
        None,
    )
    if selected is None:
        fail("method_selection_missing")
    _resources(service, selected)
    root = service.store.root / "sessions" / sid
    for item in execution["scope"]["file_bindings"]:
        if _file(root, item["path"], item["sha256"]) != item:
            fail("method_resource_changed")
    projected, bodies, input_path = source_context(service, sid, selected["id"], context)
    if (
        hashlib.sha256(canonical(projected)).hexdigest() != binding["input_sha256"]
        or input_path != execution["scope"]["input_path"]
        or any(read_regular(root / p, 16 * 1024 * 1024) != b for p, b in bodies.items())
    ):
        fail("method_input_changed")
    # Resource hashes above equal this Host's reviewed packaged source. Recompute
    # using those exact functions, without executing a resource as arbitrary code.
    action_path = selected["resource_path"] + "/scripts/source_actions.py"
    action_raw = read_regular(root / action_path, 65536)
    from .skills._shared import source_actions

    if action_raw != Path(source_actions.__file__).read_bytes():
        fail("method_code_unverified")
    actions = {
        "owned-company-evidence": source_actions.inspect_company_sources,
        "owned-news-evidence": source_actions.inspect_news_sources,
        "owned-research-prep": source_actions.inspect_research_materials,
    }
    expected = actions[selected["id"]](root, projected)
    path = execution["output_root"] + "/ledger.json"
    raw = read_regular(root / path, 65536)
    if raw != canonical(expected):
        fail("method_output_changed")
    return {
        "artifact": {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        "analysis_status": expected["status"],
        "missing": expected["missing"],
        "counts": expected["counts"],
    }


def complete_execution(service, sid, execution_id, call_id, result):
    receipt, _ = service._task_capabilities(sid)
    execution = next(
        (
            item
            for item in receipt.get("method_executions", [])
            if item["binding"]["execution_id"] == execution_id and item["call_id"] == call_id
        ),
        None,
    )
    if execution is None or execution["state"] != "started":
        fail("method_execution_unknown_do_not_retry")
    from .delivery import accepted_task_cancel

    key = service.store.session(sid).get("delivery_key")
    delivery = service.delivery.current(sid)
    contract = receipt.get("research_contract")
    task_id = execution["binding"].get("task_id")
    if (
        not isinstance(delivery, dict)
        or not isinstance(contract, dict)
        or not isinstance(key, str)
        or not key
        or not isinstance(task_id, str)
        or not task_id
        or not isinstance(delivery.get("marker"), str)
        or not delivery["marker"]
        or receipt is not service.store.data["receipts"].get(f"{sid}:{key}")
        or delivery.get("task_id") != execution["binding"]["task_id"]
        or contract.get("task_id") != execution["binding"]["task_id"]
    ):
        fail("method_execution_unknown_do_not_retry")
    try:
        if (
            not isinstance(result, dict)
            or set(result) != {"status", "stdout", "stderr", "exit_code", "error"}
            or result.get("status")
            not in {"completed", "failed", "timed_out", "output_limit", "cancelled"}
            or any(not isinstance(result.get(k), str) for k in ("stdout", "stderr"))
            or len(result["stdout"].encode()) + len(result["stderr"].encode()) > 65536
            or result["exit_code"] is not None
            and type(result["exit_code"]) is not int
            or result["error"] is not None
            and not isinstance(result["error"], str)
        ):
            fail("method_runner_result_invalid")
        execution["native_result"] = copy.deepcopy(result)
        if accepted_task_cancel(receipt, delivery, key, task_id=execution["binding"]["task_id"]):
            execution.update(state="cancelled", finished_at=time.time())
            service.store.save()
            log.info("research_owned_method_completion_cancelled", execution_id=execution_id)
            return {"state": "cancelled", "research_quality": "NOT_RUN"}
        if (
            result["status"] != "completed"
            or result["exit_code"] != 0
            or result["error"] is not None
        ):
            state = "cancelled" if result["status"] == "cancelled" else "failed"
            execution.update(state=state, finished_at=time.time())
            service.store.save()
            return {"state": state, "research_quality": "NOT_RUN"}
        observed = _readback(service, sid, execution)
        if json.loads(result["stdout"]) != observed["artifact"]:
            fail("method_stdout_unverified")
        execution.update(state="saved", finished_at=time.time(), **observed)
        service.store.save()
        log.info("research_owned_method_saved", execution_id=execution_id)
        return {
            "state": "saved",
            "analysis_status": observed["analysis_status"],
            "research_quality": "NOT_RUN",
        }
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        execution.update(state="invalid", finished_at=time.time())
        service.store.save()
        fail("method_completion_invalid")


def quality_issues(service, sid, receipt):
    validate_storage(service, sid)
    ids = {
        ref["id"]
        for ref in [
            *receipt.get("scenario_required_capabilities", []),
            receipt.get("capability") or {},
        ]
        if ref.get("id") in METHODS
    }
    issues = []
    for cid in ids:
        candidates = [
            item
            for item in receipt.get("method_executions", [])
            if item["binding"]["capability_id"] == cid
        ]
        if any(item["state"] == "invalid" for item in candidates):
            fail("method_execution_invalid")
        saved = [item for item in candidates if item["state"] == "saved"]
        if not saved:
            issues.append("method_execution_not_verified:" + cid)
        for item in saved:
            observed = _readback(service, sid, item)
            if observed != {key: item[key] for key in observed}:
                fail("method_output_changed")
            if observed["missing"]:
                issues.append("method_source_incomplete:" + cid)
    return issues


def validate_storage(service, sid):
    """An orphan or damaged private binding cannot become a new input alias."""
    root = service.store.root / "sessions" / sid
    folder = root / "inputs" / "methods"
    registered = {}
    for key, receipt in service.store.data.get("receipts", {}).items():
        if not key.startswith(sid + ":"):
            continue
        executions = receipt.get("method_executions", [])
        if not isinstance(executions, list):
            fail("method_execution_record_invalid")
        for execution in executions:
            if execution.get("schema") != "research_owned_method_execution_v1" or execution.get(
                "state"
            ) not in {"started", "saved", "failed", "cancelled", "invalid"}:
                fail("method_execution_record_invalid")
            for binding in execution.get("scope", {}).get("file_bindings", []):
                relative = binding.get("path", "")
                if relative.startswith("inputs/methods/"):
                    if relative in registered and registered[relative] != binding:
                        fail("method_input_changed")
                    registered[relative] = binding
    if folder.is_symlink():
        fail("method_input_changed")
    actual = set()
    if folder.exists():
        for path in folder.rglob("*"):
            if path.is_symlink():
                fail("method_input_changed")
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
    if actual != set(registered):
        fail("method_input_unbound")
    for relative, binding in registered.items():
        if _file(root, relative, binding["sha256"]) != binding:
            fail("method_input_changed")


def original_evidence_files(service, sid, files):
    """Exclude only privately registered generated inputs from source discovery.

    The original selected references and old page-evidence copies remain under
    the original reader. An arbitrary filename/prefix never creates an exemption.
    """
    generated = {
        binding["path"]
        for key, receipt in service.store.data.get("receipts", {}).items()
        if key.startswith(sid + ":")
        for execution in receipt.get("method_executions", [])
        if execution.get("schema") == "research_owned_method_execution_v1"
        for binding in execution.get("scope", {}).get("file_bindings", [])
        if binding.get("path", "").startswith("inputs/methods/")
    }
    paths = service.store.session(sid).get("files", {})
    return [item for item in files if paths.get(item.get("id")) not in generated]
