"""One-shot pack admission and artifact observation on the existing Native bridge.

This is not a runner, queue or inference loop. Only the managed JS tool can submit
actual supervisor completion through the private bridge. Unknown calls never rerun.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import time
from uuid import uuid4

from core.observability import get_logger

from .capabilities.pack_dependencies import runtime_identity
from .capabilities.pack_native import read_regular
from .capabilities.pack_resources import canonical, verify_pack_manifest
from .store import StoreError

log = get_logger(__name__)
POLICY = "scenario-frozen-inputs-v1"


def fail(code):
    log.warning("research_pack_execution_rejected", code=code)
    raise StoreError("组合包执行身份、权限或真实产物无法核验", code, 409)


def _file(root, relative, expected):
    if not isinstance(relative, str) or any(
        not p or p.startswith(".") for p in relative.split("/")
    ):
        fail("pack_resource_path_invalid")
    path = root / relative
    raw = read_regular(path, 64 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        fail("pack_resource_changed")
    info = path.stat()
    return {
        "path": relative,
        "sha256": expected,
        "bytes": len(raw),
        "device": info.st_dev,
        "inode": info.st_ino,
    }


def launcher(root, scope):
    """Fixed code; only Host-validated identities, paths and digests are embedded."""
    data = base64.b64encode(
        canonical(
            {
                "root": str(root),
                "files": scope["file_bindings"],
                "scripts": scope["scripts"],
                "input": scope["input_path"],
                "output": scope["output_root"] + "/v1",
                "binding": scope["binding"],
            }
        )
    ).decode()
    code = f"""import base64,json,sys,hashlib,os,stat
from pathlib import Path
_v=json.loads(base64.b64decode({data!r}))
for _f in _v['files']:
 _p=_v['root']+'/'+_f['path']
 with os.fdopen(os.open(_p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as _s:
  _b=os.fstat(_s.fileno());_h=hashlib.file_digest(_s,'sha256').hexdigest();_a=os.fstat(_s.fileno())
 if not stat.S_ISREG(_b.st_mode) or _b.st_nlink!=1 or (_b.st_dev,_b.st_ino,_b.st_size)!=(_f['device'],_f['inode'],_f['bytes']) or (_a.st_dev,_a.st_ino,_a.st_size,_a.st_mtime_ns,_a.st_ctime_ns)!=(_b.st_dev,_b.st_ino,_b.st_size,_b.st_mtime_ns,_b.st_ctime_ns) or _h!=_f['sha256']:
  raise ValueError('pack_resource_changed')
sys.path.insert(0,_v['root']+'/'+_v['scripts'])
from calculate import execute
print(json.dumps(execute(Path(_v['root']+'/'+_v['input']),Path(_v['root']+'/'+_v['output']),_v['binding']),ensure_ascii=False,separators=(',',':')))
"""
    if len(code.encode()) > 65536:
        fail("pack_launcher_limit")
    return code


def prepare_execution(service, sid, descriptor, call_id, *, start=False):
    from .datahub.security import directory
    from .scenario_handoffs import bound_capabilities, fingerprint, trusted_context
    from .scenario_pack_inputs import verify_pack_seal

    if (
        not isinstance(descriptor, dict)
        or set(descriptor)
        != {"capability_id", "version", "context_sha256", "input_manifest_sha256"}
        or not isinstance(call_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", call_id)
    ):
        fail("pack_execution_descriptor_invalid")
    if (
        type(descriptor["version"]) is not int
        or descriptor["version"] < 1
        or any(
            not isinstance(descriptor[key], str)
            or not re.fullmatch(r"[a-f0-9]{64}", descriptor[key])
            for key in ("context_sha256", "input_manifest_sha256")
        )
    ):
        fail("pack_execution_descriptor_invalid")
    context = trusted_context(service, sid)
    if not context or not context.get("pack_seal"):
        fail("pack_input_unsealed")
    seal = verify_pack_seal(service, sid, context)
    if descriptor != {
        "capability_id": seal["capability_id"],
        "version": seal["version"],
        "context_sha256": fingerprint(context),
        "input_manifest_sha256": seal["manifest_sha256"],
    }:
        fail("pack_execution_binding_changed")
    required = bound_capabilities(service, context)
    selected = next((item for item in required if item["id"] == seal["capability_id"]), None)
    receipt, _ = service._task_capabilities(sid)
    if (
        selected is None
        or not receipt
        or not any(
            all(item.get(k) == selected[k] for k in ("id", "version", "sha256"))
            for item in receipt.get("native_capabilities", [])
        )
    ):
        fail("pack_capability_not_loaded")
    task_id = receipt.get("research_contract", {}).get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-f0-9]{24}", task_id):
        fail("pack_task_unverified")
    executions = receipt.get("pack_executions", [])
    if any(
        item.get("call_id") == call_id
        or item["binding"].get("context_sha256") == fingerprint(context)
        and item["binding"].get("task_id") == task_id
        for item in executions
    ):
        fail("pack_execution_unknown_do_not_retry")
    if len(executions) >= 64:
        fail("pack_execution_limit")
    version = service.capabilities.row(selected["id"])["versions"][str(selected["version"])]
    code_manifest = verify_pack_manifest(version["files"])
    if code_manifest is None or code_manifest["closure_sha256"] != seal["closure_sha256"]:
        fail("pack_code_unverified")
    root = service.store.root / "sessions" / sid
    files = [
        {"path": selected["resource_path"] + "/SKILL.md", "sha256": selected["sha256"]},
        *[
            {"path": selected["resource_path"] + "/" + item["path"], "sha256": item["sha256"]}
            for item in version["files"]
        ],
        {"path": seal["input_path"], "sha256": seal["input_sha256"]},
        {"path": seal["manifest_path"], "sha256": seal["manifest_sha256"]},
    ]
    if len(files) > 320:
        fail("pack_resource_limit")
    bindings = [_file(root, item["path"], item["sha256"]) for item in files]
    installed = json.loads(
        read_regular(root / selected["resource_path"] / "references/runtime.json", 65536)
    )
    if installed != runtime_identity():
        fail("pack_runtime_changed")
    if not start:
        return {
            "admitted": True,
            "status": "limited",
            "missing": context["pack_qualification"]["missing"],
            "omitted_sections": [],
            "read_paths": [],
        }
    execution_id = uuid4().hex
    output_root = "outputs/scenario-results/" + execution_id
    with directory(
        service.store.root, ("sessions", sid, "outputs", "scenario-results"), create=True
    ):
        (root / output_root).mkdir(mode=0o700)
    binding = {
        "execution_id": execution_id,
        "task_id": task_id,
        "call_id": call_id,
        "context_sha256": fingerprint(context),
        "input_sha256": seal["input_sha256"],
        "input_manifest_sha256": seal["manifest_sha256"],
        "closure_sha256": seal["closure_sha256"],
        "capability_id": selected["id"],
        "version": selected["version"],
        "pack_id": seal["pack_id"],
    }
    scope = {
        "admitted": True,
        "status": "limited",
        "missing": context["pack_qualification"]["missing"],
        "omitted_sections": [],
        "input_policy": POLICY,
        "read_paths": [item["path"] for item in bindings],
        "file_bindings": bindings,
        "output_root": output_root,
        "input_path": seal["input_path"],
        "scripts": selected["resource_path"] + "/scripts",
        "binding": binding,
        "runtime": installed,
    }
    code = launcher(root, scope)
    scope["code"] = code
    scope["code_sha256"] = hashlib.sha256(code.encode()).hexdigest()
    receipt.setdefault("pack_executions", []).append(
        {
            "schema": "research_pack_execution_v1",
            "state": "started",
            "started_at": time.time(),
            "call_id": call_id,
            "binding": binding,
            "scope": copy.deepcopy(scope),
            "output_root": output_root,
            "code_sha256": scope["code_sha256"],
        }
    )
    service.store.save()
    log.info("research_pack_execution_started task_id=%s execution_id=%s", task_id, execution_id)
    return scope


def read_artifacts(root, execution):
    """Independently reopen exact output names; no paths from stdout are used."""
    base = root / execution["output_root"] / "v1"
    raw = {
        name: read_regular(
            base / (name + ".json"), 16 * 1024 * 1024 if name == "full-result" else 65536
        )
        for name in ("full-result", "receipt", "manifest")
    }
    values = {name: json.loads(content) for name, content in raw.items()}
    if any(not isinstance(value, dict) for value in values.values()):
        fail("pack_output_schema_invalid")
    from .capabilities.pack_result_contracts import validate as validate_output_contract

    validate_output_contract(
        values["receipt"], values["full-result"], execution["binding"]["pack_id"]
    )
    if any(canonical(values[name]) != content for name, content in raw.items()):
        fail("pack_output_json_invalid")
    manifest, receipt, full = values["manifest"], values["receipt"], values["full-result"]
    if (
        manifest.get("schema") != "research_pack_artifact_manifest_v1"
        or manifest.get("binding") != execution["binding"]
        or full.get("schema") != "research_pack_full_result_v1"
        or full.get("schema_version") != 1
        or type(full.get("schema_version")) is not int
        or full.get("root_rows_kind") != "component_references"
        or set(full)
        != {"schema", "schema_version", "root_rows_kind", "root", "components", "counts"}
    ):
        fail("pack_output_binding_changed")
    if (
        set(manifest) != {"schema", "binding", "status", "artifacts", "counts"}
        or set(manifest["artifacts"]) != {"full-result", "receipt"}
        or receipt.get("schema_version") != 1
        or receipt.get("host_qualification") != "NOT_RUN"
        or receipt.get("research_quality") != "NOT_RUN"
        or receipt.get("status")
        not in {"complete", "partial", "insufficient_data", "blocked", "failed"}
    ):
        fail("pack_output_schema_invalid")
    for name in ("full-result", "receipt"):
        if manifest["artifacts"][name] != {
            "file": name + ".json",
            "sha256": hashlib.sha256(raw[name]).hexdigest(),
            "bytes": len(raw[name]),
        }:
            fail("pack_output_hash_changed")
    components = full["components"]
    from .scenarios.packs import METHODS, PACKS

    if not isinstance(components, list) or any(
        not isinstance(item, dict)
        or item.get("method") not in PACKS[execution["binding"]["pack_id"]]
        for item in components
    ):
        fail("pack_output_components_missing")
    input_raw = read_regular(root / execution["scope"]["input_path"], 64 * 1024 * 1024)
    if hashlib.sha256(input_raw).hexdigest() != execution["binding"]["input_sha256"]:
        fail("pack_input_changed")
    sealed = json.loads(input_raw)
    inputs = sealed["records_by_kind"]
    parameters = sealed["parameters"]

    def project_parameter(value):
        if isinstance(value, list):
            return {
                "input_collection_sha256": hashlib.sha256(
                    json.dumps(
                        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).hexdigest(),
                "item_count": len(value),
            }
        if isinstance(value, dict):
            return {key: project_parameter(item) for key, item in value.items()}
        return value

    if full["root"]["parameters"] != project_parameter(parameters):
        fail("pack_output_input_binding_invalid")
    normalized = hashlib.sha256(
        canonical(
            {
                "records": inputs,
                "parameters": parameters,
                "source_coverage": sealed["source_coverage"],
            }
        )
    ).hexdigest()
    if (
        full["root"]["input_sha256"] != normalized
        or full["root"]["canonical_input_sha256"] != normalized
        or full["root"]["input_digest_kind"] != "normalized_canonical_json_v1"
    ):
        fail("pack_output_input_binding_invalid")
    if full["root"]["processed_input_rows"] != sum(len(rows) for rows in inputs.values()) or full[
        "root"
    ]["metrics"]["subresults_executed"] != len(components):
        fail("pack_output_input_counts_invalid")
    for component in components:
        selected = {
            kind: rows for kind, rows in inputs.items() if kind in METHODS[component["method"]][1]
        }
        expected_digest = hashlib.sha256(
            canonical(
                {
                    "records": selected,
                    "parameters": {"as_of": parameters["as_of"], **parameters[component["method"]]},
                }
            )
        ).hexdigest()
        atom_parameters = {"as_of": parameters["as_of"], **parameters[component["method"]]}
        if component["parameters"] != project_parameter(atom_parameters) or component["metrics"][
            "input_counts"
        ] != {kind: len(rows) for kind, rows in selected.items()}:
            fail("pack_output_input_binding_invalid")
        if (
            component["input_sha256"] != expected_digest
            or component["canonical_input_sha256"] != expected_digest
        ):
            fail("pack_output_input_binding_invalid")
        if type(component["processed_input_rows"]) is not int or component[
            "processed_input_rows"
        ] != sum(
            len(rows) for kind, rows in inputs.items() if kind in METHODS[component["method"]][1]
        ):
            fail("pack_output_input_counts_invalid")
    counts = {
        "root": len(full["root"]["rows"]),
        "components": {item["method"]: len(item["rows"]) for item in components},
    }
    if (
        len(counts["components"]) != len(components)
        or canonical(manifest["counts"]) != canonical(counts)
        or canonical(full["counts"])
        != canonical(
            {"root_output_rows": counts["root"], "component_output_rows": counts["components"]}
        )
        or receipt["method"] != "pack:" + execution["binding"]["pack_id"]
        or full["root"]["method"] != receipt["method"]
        or receipt["result_sha256"] != full["root"]["receipt_sha256"]
        or receipt["status"] != full["root"]["status"]
        or manifest["status"] != receipt["status"]
    ):
        fail("pack_output_count_or_schema_invalid")
    previews = {item["method"]: item for item in receipt["rows"]}
    if set(previews) != set(counts["components"]) or {
        item["component_id"] for item in full["root"]["rows"]
    } != set(previews):
        fail("pack_output_components_missing")
    root = full["root"]
    if (
        receipt["row_delivery"]
        != {
            "mode": "inline",
            "total_output_rows": len(root["rows"]),
            "inline_output_rows": len(receipt["rows"]),
            "omitted_output_rows": len(root["rows"]) - len(receipt["rows"]),
        }
        or root["legacy_normalized_input_sha256"] != receipt["input_sha256"]
        or any(
            root.get(key) != value
            for key, value in receipt.items()
            if key not in {"rows", "row_delivery", "result_sha256", "input_sha256"}
        )
    ):
        fail("pack_output_metadata_invalid")
    for item in (full["root"], *components):
        if (
            item["counts"]
            != {
                "processed_input_rows": item["processed_input_rows"],
                "total_output_rows": len(item["rows"]),
                "missing_count": len(item["missing"]),
                "rejected_count": len(item["rejected_rows"]),
                "source_ref_count": len(item["source_refs"]),
            }
            or any(type(count) is not int for count in item["counts"].values())
            or item["host_qualification"] != "NOT_RUN"
            or item["research_quality"] != "NOT_RUN"
        ):
            fail("pack_output_count_or_schema_invalid")
    for component in components:
        preview = previews[component["method"]]
        display = preview["result"]
        delivery = display["row_delivery"]
        if (
            preview["receipt_sha256"] != component["receipt_sha256"]
            or display["rows"] != component["rows"][: len(display["rows"])]
            or delivery["total_output_rows"] != len(component["rows"])
            or delivery["inline_output_rows"] != len(display["rows"])
            or delivery["omitted_output_rows"] != len(component["rows"]) - len(display["rows"])
            or len(display["rows"]) > 128
            or component["legacy_normalized_input_sha256"] != display["input_sha256"]
            or any(
                component.get(key) != value
                for key, value in display.items()
                if key not in {"rows", "row_delivery", "result_sha256", "input_sha256"}
            )
        ):
            fail("pack_output_preview_invalid")
    return {
        "artifacts": {
            name: {
                "path": execution["output_root"] + "/v1/" + name + ".json",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            for name, content in raw.items()
        },
        "counts": counts,
        "computation_status": receipt["status"],
        "missing": receipt["missing"],
    }


def complete_execution(service, sid, execution_id, call_id, result):
    from .scenario_handoffs import fingerprint, trusted_context

    context = trusted_context(service, sid)
    receipt, _ = service._task_capabilities(sid)
    execution = next(
        (
            item
            for item in receipt.get("pack_executions", [])
            if item["binding"]["execution_id"] == execution_id and item["call_id"] == call_id
        ),
        None,
    )
    if execution is None or execution["state"] != "started":
        fail("pack_execution_unknown_do_not_retry")
    try:
        if (
            not isinstance(result, dict)
            or set(result) != {"status", "stdout", "stderr", "exit_code", "error"}
            or result.get("status")
            not in {"completed", "failed", "timed_out", "output_limit", "cancelled"}
            or not isinstance(result.get("stdout"), str)
            or not isinstance(result.get("stderr"), str)
            or len(result["stdout"].encode()) + len(result["stderr"].encode()) > 65536
            or result["exit_code"] is not None
            and type(result["exit_code"]) is not int
            or result["error"] is not None
            and not isinstance(result["error"], str)
        ):
            fail("pack_runner_result_invalid")
        rendered = json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        execution.update(
            native_result=copy.deepcopy(result),
            native_result_sha256=hashlib.sha256(canonical(result)).hexdigest(),
            native_rendered_content=rendered,
            native_rendered_sha256=hashlib.sha256(rendered.encode()).hexdigest(),
            stdout_sha256=hashlib.sha256(result["stdout"].encode()).hexdigest(),
            stderr_sha256=hashlib.sha256(result["stderr"].encode()).hexdigest(),
        )
        if (
            result["status"] != "completed"
            or result["exit_code"] != 0
            or result["error"] is not None
        ):
            state = "cancelled" if result.get("status") == "cancelled" else "failed"
            execution.update(
                state=state,
                finished_at=time.time(),
                actual_exit_code=result.get("exit_code"),
                runner_status=result.get("status"),
            )
            service.store.save()
            return {"state": state, "research_quality": "NOT_RUN"}
        root = service.store.root / "sessions" / sid
        for item in execution["scope"]["file_bindings"]:
            if _file(root, item["path"], item["sha256"]) != item:
                fail("pack_resource_changed")
        runtime = json.loads(
            read_regular(
                root
                / execution["scope"]["scripts"].removesuffix("/scripts")
                / "references/runtime.json",
                65536,
            )
        )
        if runtime != runtime_identity():
            fail("pack_runtime_changed")
        if execution["binding"]["context_sha256"] != fingerprint(context):
            fail("pack_execution_binding_changed")
        envelope = json.loads(result["stdout"])
        observed = read_artifacts(root, execution)
        if (
            set(envelope)
            != {"schema", "execution_id", "status", "artifacts", "counts", "research_quality"}
            or envelope.get("research_quality") != "NOT_RUN"
            or envelope.get("schema") != "research_pack_execution_envelope_v1"
            or envelope.get("execution_id") != execution_id
            or envelope.get("counts") != observed["counts"]
            or envelope.get("status") != observed["computation_status"]
            or len(result["stdout"].encode()) > 65536
            or envelope.get("artifacts")
            != {
                name: {
                    "file": name + ".json",
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                }
                for name, item in observed["artifacts"].items()
            }
        ):
            fail("pack_stdout_unverified")
        execution.update(
            state="saved",
            finished_at=time.time(),
            actual_exit_code=0,
            runner_status="completed",
            stdout_sha256=hashlib.sha256(result["stdout"].encode()).hexdigest(),
            **observed,
        )
        service.store.save()
        log.info(
            "research_pack_execution_saved task_id=%s execution_id=%s computation=%s",
            execution["binding"]["task_id"],
            execution_id,
            observed["computation_status"],
        )
        return {
            "state": "saved",
            "computation_status": observed["computation_status"],
            "research_quality": "NOT_RUN",
        }
    except (OSError, ValueError, KeyError, TypeError, StoreError):
        execution.update(state="invalid", finished_at=time.time())
        service.store.save()
        fail("pack_completion_invalid")


def quality_issues(service, sid, receipt, context):
    from .scenario_handoffs import fingerprint

    candidates = [
        item
        for item in receipt.get("pack_executions", [])
        if item.get("state") == "saved"
        and item["binding"]["context_sha256"] == fingerprint(context)
    ]
    if not candidates:
        return ["pack_execution_not_verified"]
    for execution in candidates:
        observed = read_artifacts(service.store.root / "sessions" / sid, execution)
        if observed != {key: execution[key] for key in observed}:
            fail("pack_output_changed")
    return (
        []
        if all(item["computation_status"] == "complete" for item in candidates)
        and not context["pack_qualification"]["missing"]
        else ["pack_computation_or_source_incomplete"]
    )
