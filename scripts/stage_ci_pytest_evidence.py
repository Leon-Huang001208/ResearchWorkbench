"""Stage redacted CI pytest evidence through owner-bound, no-follow file handles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCOPES = ("research-web", "unit")
ROOT_MARKER = ".rwb-ci-pytest-root.json"
SOURCE_ALLOWLIST = (
    "partitions.json",
    "scheduler-result.json",
    "scheduler/collect.log",
    "worker-0.owner.json",
    "worker-1.owner.json",
    "worker-0/result.json",
    "worker-0/junit.xml",
    "worker-0/pytest.log",
    "worker-1/result.json",
    "worker-1/junit.xml",
    "worker-1/pytest.log",
)
PROGRESS_ALLOWLIST = ("worker-0/progress.json", "worker-1/progress.json")
MAX_FILE_BYTES = 100 * 1024 * 1024
WORKER_PROGRESS_FIELDS = {
    "schemaVersion",
    "phase",
    "workerIndex",
    "planSha256",
    "nodeId",
    "outcome",
    "elapsedSeconds",
    "counters",
}
WORKER_PROGRESS_PHASES = frozenset({"startup", "collection", "setup", "call", "teardown"})
WORKER_PROGRESS_OUTCOMES = frozenset({"passed", "skipped", "failed"})
WORKER_PROGRESS_COUNTERS = frozenset(
    {"collected", "selected", "started", "completed", "passed", "skipped", "failed"}
)
MAX_PROGRESS_ELAPSED_SECONDS = 7 * 24 * 60 * 60
WORKER_RESULT_FIELDS = {
    "schemaVersion",
    "taskId",
    "workerIndex",
    "pid",
    "uid",
    "rootDevice",
    "rootInode",
    "planSha256",
    "expectedNodeIds",
    "assignedNodeIds",
    "execution",
    "collectionFailures",
    "junit",
    "pytestExitCode",
    "status",
    "error",
    "failureTaxonomy",
}
FAILURE_CODES_BY_PHASE = {
    "collection": {"pytest_collection_failed"},
    "setup": {"pytest_setup_failed"},
    "call": {"pytest_call_failed"},
    "teardown": {"pytest_teardown_failed"},
    "pytest": {"pytest_exit_nonzero"},
    "worker": {
        "pytest_runner_exception",
        "worker_evidence_validation_failed",
        "worker_result_serialization_failed",
    },
}
SAFE_EXCEPTION_CLASSES = frozenset(
    {
        "AssertionError",
        "AttributeError",
        "BaseException",
        "ConnectionError",
        "EOFError",
        "Exception",
        "FileExistsError",
        "FileNotFoundError",
        "ImportError",
        "IndexError",
        "InterruptedError",
        "IsADirectoryError",
        "KeyError",
        "KeyboardInterrupt",
        "MemoryError",
        "ModuleNotFoundError",
        "NameError",
        "NotADirectoryError",
        "NotImplementedError",
        "OSError",
        "OverflowError",
        "PartitionError",
        "PermissionError",
        "RecursionError",
        "RuntimeError",
        "StopAsyncIteration",
        "StopIteration",
        "SyntaxError",
        "SystemError",
        "SystemExit",
        "TimeoutError",
        "TypeError",
        "UnboundLocalError",
        "UnicodeError",
        "UnknownError",
        "ValueError",
        "ZeroDivisionError",
    }
)
SECRET_PATTERNS = (
    re.compile(rb"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(rb"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class StagingError(RuntimeError):
    """Raised when evidence paths, ownership, identity, or content are unsafe."""


def _validate_failure_taxonomy(value: Any, status: Any, index: int) -> None:
    if status == "passed":
        if value is not None:
            raise StagingError(f"worker-{index} passing result contains failure taxonomy")
        return
    if (
        status != "failed"
        or not isinstance(value, dict)
        or set(value)
        != {
            "phase",
            "errorClass",
            "errorCode",
        }
    ):
        raise StagingError(f"worker-{index} failed result has no safe failure taxonomy")
    phase = value["phase"]
    error_class = value["errorClass"]
    error_code = value["errorCode"]
    if (
        not isinstance(phase, str)
        or phase not in FAILURE_CODES_BY_PHASE
        or not isinstance(error_code, str)
        or error_code not in FAILURE_CODES_BY_PHASE[phase]
        or (
            error_class is not None
            and (not isinstance(error_class, str) or error_class not in SAFE_EXCEPTION_CLASSES)
        )
    ):
        raise StagingError(f"worker-{index} failure taxonomy is invalid")


def _secret_scan(data: bytes) -> None:
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise StagingError("public pytest evidence contains a credential-like value")


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory:
        raise StagingError("platform lacks safe directory-open flags")
    return os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _same_dir(left: os.stat_result, right: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_uid")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _open_owned_directory(path: Path) -> tuple[int, os.stat_result, Path]:
    absolute = Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
    if not absolute.name:
        raise StagingError("base evidence/workspace path must not be a filesystem root")
    try:
        canonical_parent = absolute.parent.resolve(strict=True)
        parent_fd = os.open(canonical_parent, _directory_flags())
    except StagingError:
        raise
    except OSError as error:
        raise StagingError(f"cannot safely open base directory parent: {error}") from error
    descriptor: int | None = None
    try:
        before = os.stat(absolute.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid():
            raise StagingError("base evidence/workspace path is not an owned real directory")
        descriptor = os.open(absolute.name, _directory_flags(), dir_fd=parent_fd)
        after = os.fstat(descriptor)
        if not _same_dir(before, after):
            os.close(descriptor)
            descriptor = None
            raise StagingError("base directory identity changed while opening")
        result = descriptor, after, canonical_parent / absolute.name
        descriptor = None
        return result
    except StagingError:
        raise
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise StagingError(f"cannot safely open base directory: {error}") from error
    finally:
        os.close(parent_fd)


def _open_directory_at(
    parent_fd: int,
    name: str,
    *,
    device: int,
    uid: int,
    private: bool = True,
) -> tuple[int, os.stat_result]:
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise StagingError(f"evidence path is not a directory: {name}")
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
        after = os.fstat(descriptor)
    except StagingError:
        raise
    except OSError as error:
        raise StagingError(f"cannot safely open evidence directory {name}: {error}") from error
    if (
        not _same_dir(before, after)
        or after.st_dev != device
        or after.st_uid != uid
        or (private and stat.S_IMODE(after.st_mode) & 0o077)
    ):
        os.close(descriptor)
        raise StagingError(f"evidence directory owner or identity changed: {name}")
    return descriptor, after


def _read_file_at(
    parent_fd: int,
    name: str,
    *,
    device: int,
    uid: int,
) -> tuple[bytes, os.stat_result] | None:
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_dev != device
        or before.st_uid != uid
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > MAX_FILE_BYTES
    ):
        raise StagingError(f"evidence input is not a single-link owner file: {name}")
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise StagingError(f"cannot safely open evidence file {name}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if not _same_file(before, opened):
            raise StagingError(f"evidence input changed while opening: {name}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_FILE_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise StagingError(f"evidence input exceeds per-file size limit: {name}")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _same_file(opened, after) or not _same_file(after, current):
            raise StagingError(f"evidence input changed while reading: {name}")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _read_relative(
    root_fd: int,
    relative: str,
    *,
    root_device: int,
    uid: int,
) -> tuple[bytes, os.stat_result] | None:
    parts = relative.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise StagingError("source allowlist contains an unsafe path")
    descriptors: list[int] = []
    parent_fd = root_fd
    try:
        for component in parts[:-1]:
            try:
                os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return None
            child_fd, _ = _open_directory_at(parent_fd, component, device=root_device, uid=uid)
            descriptors.append(child_fd)
            parent_fd = child_fd
        return _read_file_at(parent_fd, parts[-1], device=root_device, uid=uid)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _verify_directory_entry(parent_fd: int, name: str, expected: os.stat_result) -> None:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError as error:
        raise StagingError(f"evidence directory disappeared: {name}") from error
    if not stat.S_ISDIR(current.st_mode) or not _same_dir(expected, current):
        raise StagingError(f"evidence directory was replaced: {name}")


def _verify_relative(
    root_fd: int,
    relative: str,
    expected: os.stat_result,
    *,
    root_device: int,
    uid: int,
) -> None:
    read = _read_relative(root_fd, relative, root_device=root_device, uid=uid)
    if read is None or not _same_file(expected, read[1]):
        raise StagingError(f"source identity changed before staging: {relative}")


def _read_json(
    data: bytes | None, description: str, *, required: bool = True
) -> dict[str, Any] | None:
    if data is None:
        if required:
            raise StagingError(f"missing required {description}")
        return None
    try:
        value = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise StagingError(f"invalid {description} JSON") from error
    if not isinstance(value, dict):
        raise StagingError(f"{description} JSON root is not an object")
    return value


def _validate_selection(selection: Any) -> list[str]:
    if not isinstance(selection, list) or not selection:
        raise StagingError("manifest selection is missing")
    result: list[str] = []
    for argument in selection:
        if not isinstance(argument, str) or not argument or "\x00" in argument:
            raise StagingError("manifest selection contains invalid text")
        if argument in {"-q", "--quiet"}:
            result.append(argument)
        elif argument.startswith("--confcutdir="):
            if argument not in {
                "--confcutdir=tests/research_web",
                "--confcutdir=tests/unit",
            }:
                raise StagingError("manifest confcutdir is outside the fixed test roots")
            result.append(argument)
        elif argument.startswith("tests/"):
            path = argument.split("::", 1)[0]
            if Path(path).is_absolute() or any(part in {".", ".."} for part in path.split("/")):
                raise StagingError("manifest selection escapes the test roots")
            result.append(argument)
        else:
            raise StagingError("manifest selection is outside the public test allowlist")
    return result


def _validate_manifest(manifest: dict[str, Any], task_id: str) -> dict[str, Any]:
    fields = {"schemaVersion", "taskId", "selection", "nodeIds", "partitions", "planSha256"}
    if (
        set(manifest) != fields
        or type(manifest.get("schemaVersion")) is not int
        or manifest["schemaVersion"] != 2
    ):
        raise StagingError("partition manifest schema is invalid")
    if manifest.get("taskId") != task_id:
        raise StagingError("partition manifest task identity is invalid")
    selection = _validate_selection(manifest.get("selection"))
    nodeids = manifest.get("nodeIds")
    partitions = manifest.get("partitions")
    if (
        not isinstance(nodeids, list)
        or not nodeids
        or any(not isinstance(nodeid, str) or not nodeid.startswith("tests/") for nodeid in nodeids)
        or len(set(nodeids)) != len(nodeids)
        or not isinstance(partitions, list)
        or len(partitions) != 2
        or any(not isinstance(partition, list) for partition in partitions)
    ):
        raise StagingError("partition manifest node ID data is invalid")
    expected = [nodeids[index::2] for index in range(2)]
    if partitions != expected or any(not partition for partition in partitions):
        raise StagingError("partition manifest is not a complete deterministic split")
    payload = {
        "taskId": task_id,
        "selection": selection,
        "nodeIds": nodeids,
        "partitions": partitions,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    if manifest.get("planSha256") != digest:
        raise StagingError("partition manifest digest is invalid")
    return {**manifest, "selection": selection}


def _sanitize_junit(
    data: bytes,
    assigned: list[str],
    *,
    allow_partial: bool,
) -> tuple[bytes, dict[str, Any], dict[str, dict[str, int]]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise StagingError("JUnit XML is malformed") from error
    cases = root.findall(".//testcase")
    nodeids: list[str] = []
    outcomes: dict[str, dict[str, int]] = {}
    for case in cases:
        values = [
            prop.attrib.get("value")
            for prop in case.findall("./properties/property")
            if prop.attrib.get("name") == "rwb_nodeid"
        ]
        if len(values) != 1 or not isinstance(values[0], str):
            raise StagingError("JUnit case lacks exactly one rwb_nodeid")
        nodeid = values[0]
        if nodeid not in assigned:
            raise StagingError("JUnit case is outside its assigned partition")
        nodeids.append(nodeid)
        outcomes[nodeid] = {
            "failure": len(case.findall("failure")),
            "error": len(case.findall("error")),
            "skipped": len(case.findall("skipped")),
        }
    if len(set(nodeids)) != len(nodeids):
        raise StagingError("JUnit case node IDs are duplicated")
    if not allow_partial and nodeids != assigned:
        raise StagingError("passing JUnit does not exactly cover its partition")

    summary = {
        "nodeIds": nodeids,
        "tests": len(nodeids),
        "failures": sum(item["failure"] for item in outcomes.values()),
        "errors": sum(item["error"] for item in outcomes.values()),
        "skipped": sum(item["skipped"] for item in outcomes.values()),
    }
    safe_root = ET.Element(
        "testsuite",
        {
            "name": "Research Web pytest worker",
            "tests": str(summary["tests"]),
            "failures": str(summary["failures"]),
            "errors": str(summary["errors"]),
            "skipped": str(summary["skipped"]),
        },
    )
    for index, nodeid in enumerate(nodeids):
        safe_case = ET.SubElement(
            safe_root, "testcase", {"classname": "pytest", "name": f"case-{index}"}
        )
        properties = ET.SubElement(safe_case, "properties")
        ET.SubElement(properties, "property", {"name": "rwb_nodeid", "value": nodeid})
        for _ in range(outcomes[nodeid]["failure"]):
            ET.SubElement(safe_case, "failure", {"type": "failure"})
        for _ in range(outcomes[nodeid]["error"]):
            ET.SubElement(safe_case, "error", {"type": "error"})
        for _ in range(outcomes[nodeid]["skipped"]):
            ET.SubElement(safe_case, "skipped")
    return ET.tostring(safe_root, encoding="utf-8", xml_declaration=True), summary, outcomes


def _validate_passed_execution(
    execution: Any,
    assigned: list[str],
    junit_outcomes: dict[str, dict[str, int]],
) -> list[str]:
    if not isinstance(execution, list) or len(execution) != len(assigned):
        raise StagingError("passing worker execution records are incomplete")
    nodeids: list[str] = []
    for entry in execution:
        if not isinstance(entry, dict) or set(entry) != {"nodeId", "phases"}:
            raise StagingError("passing worker execution record schema is invalid")
        nodeid = entry.get("nodeId")
        phases = entry.get("phases")
        if not isinstance(nodeid, str) or nodeid not in assigned:
            raise StagingError("passing worker execution record has an unexpected node ID")
        if not isinstance(phases, list) or not phases:
            raise StagingError("passing worker execution record has no pytest phases")
        if any(
            not isinstance(phase, dict)
            or set(phase) != {"phase", "outcome"}
            or phase.get("phase") not in {"setup", "call", "teardown"}
            or phase.get("outcome") not in {"passed", "failed", "skipped"}
            for phase in phases
        ):
            raise StagingError("passing worker pytest phase is malformed")
        names = [phase["phase"] for phase in phases]
        if (
            names[0] != "setup"
            or names[-1] != "teardown"
            or names.count("setup") != 1
            or names.count("teardown") != 1
            or any(name != "call" for name in names[1:-1])
        ):
            raise StagingError("passing worker pytest phase order is invalid")
        call_phases = [phase for phase in phases if phase["phase"] == "call"]
        setup_outcome = phases[0]["outcome"]
        if (setup_outcome == "passed") != bool(call_phases):
            raise StagingError("passing worker call phase does not follow setup outcome")
        if any(phase["outcome"] == "failed" for phase in phases):
            raise StagingError("passing worker contains a failed pytest phase")
        junit_outcome = junit_outcomes.get(nodeid)
        if junit_outcome is None:
            raise StagingError("passing worker node ID is missing from JUnit")
        phase_skipped = any(phase["outcome"] == "skipped" for phase in phases)
        if bool(junit_outcome["skipped"]) != phase_skipped:
            raise StagingError("JUnit skip does not match pytest phase outcomes")
        if junit_outcome["failure"] or junit_outcome["error"]:
            raise StagingError("passing worker JUnit contains a failure or error")
        nodeids.append(nodeid)
    if nodeids != assigned or len(set(nodeids)) != len(nodeids):
        raise StagingError("passing worker execution IDs do not exactly match its assignment")
    return nodeids


def _safe_worker_progress(
    value: Any, *, index: int, manifest: dict[str, Any] | None
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != WORKER_PROGRESS_FIELDS:
        raise StagingError(f"worker-{index} progress schema is invalid")
    if manifest is None:
        raise StagingError(f"worker-{index} progress has no partition manifest")
    phase = value.get("phase")
    node_id = value.get("nodeId")
    outcome = value.get("outcome")
    elapsed = value.get("elapsedSeconds")
    counters = value.get("counters")
    assigned = manifest["partitions"][index]
    if (
        type(value.get("schemaVersion")) is not int
        or value["schemaVersion"] != 1
        or type(value.get("workerIndex")) is not int
        or value["workerIndex"] != index
        or value.get("planSha256") != manifest["planSha256"]
        or not isinstance(phase, str)
        or phase not in WORKER_PROGRESS_PHASES
        or type(elapsed) is not int
        or not 0 <= elapsed <= MAX_PROGRESS_ELAPSED_SECONDS
        or not isinstance(counters, dict)
        or set(counters) != WORKER_PROGRESS_COUNTERS
        or any(type(count) is not int or count < 0 for count in counters.values())
    ):
        raise StagingError(f"worker-{index} progress identity or types are invalid")
    if (
        counters["collected"] > len(manifest["nodeIds"])
        or counters["selected"] > len(assigned)
        or any(
            counters[name] > len(assigned)
            for name in ("started", "completed", "passed", "skipped", "failed")
        )
        or counters["completed"] > counters["started"]
        or counters["passed"] + counters["skipped"] + counters["failed"] != counters["started"]
    ):
        raise StagingError(f"worker-{index} progress counters are out of bounds")
    if phase == "startup":
        if node_id is not None or outcome is not None or any(counters.values()):
            raise StagingError(f"worker-{index} startup progress is inconsistent")
    elif phase == "collection":
        if (
            node_id is not None
            or outcome is not None
            or counters["collected"] != len(manifest["nodeIds"])
            or counters["selected"] != len(assigned)
            or any(
                counters[name] for name in ("started", "completed", "passed", "skipped", "failed")
            )
        ):
            raise StagingError(f"worker-{index} collection progress is inconsistent")
    elif (
        not isinstance(node_id, str)
        or node_id not in assigned
        or outcome not in WORKER_PROGRESS_OUTCOMES
        or counters["collected"] != len(manifest["nodeIds"])
        or counters["selected"] != len(assigned)
        or counters["started"] < 1
        or counters[outcome] < 1
        or phase == "teardown"
        and counters["completed"] < 1
    ):
        raise StagingError(f"worker-{index} execution progress is inconsistent")
    return value


def _safe_worker_summary(
    *,
    index: int,
    task_id: str,
    root_info: os.stat_result,
    manifest: dict[str, Any] | None,
    files: Mapping[str, bytes | None],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    expected_ids = manifest["partitions"][index] if manifest else []
    result_data = files.get(f"worker-{index}/result.json")
    result = _read_json(result_data, f"worker-{index} result", required=False)
    progress = None
    if result is None:
        progress = _safe_worker_progress(
            _read_json(
                files.get(f"worker-{index}/progress.json"),
                f"worker-{index} progress",
                required=False,
            ),
            index=index,
            manifest=manifest,
        )
    owner_data = files.get(f"worker-{index}.owner.json")
    owner = _read_json(owner_data, f"worker-{index} owner", required=False)
    status = "missing"
    pid: int | None = None
    exit_code: int | None = None
    execution_ids: list[str] = []
    junit_summary: dict[str, Any] | None = None
    junit_outcomes: dict[str, dict[str, int]] = {}
    junit_bytes: bytes | None = None
    junit_sha256: str | None = None
    failure_taxonomy: dict[str, str | None] | None = None

    if owner:
        required_owner = {
            "schemaVersion",
            "name",
            "pid",
            "uid",
            "device",
            "inode",
            "argv",
            "registeredAtNs",
        }
        if set(owner) != required_owner or owner.get("name") != f"worker-{index}":
            raise StagingError(f"worker-{index} owner record schema is invalid")
        if (
            type(owner.get("schemaVersion")) is not int
            or owner["schemaVersion"] != 1
            or (owner.get("pid") is not None and type(owner.get("pid")) is not int)
            or type(owner.get("argv")) is not list
            or type(owner.get("registeredAtNs")) is not int
            or type(owner.get("uid")) is not int
            or owner["uid"] != os.getuid()
            or type(owner.get("device")) is not int
            or owner["device"] != root_info.st_dev
            or type(owner.get("inode")) is not int
            or owner["inode"] != root_info.st_ino
            or owner.get("pid") is not None
            and type(owner.get("pid")) is not int
        ):
            raise StagingError(f"worker-{index} owner record identity is invalid")
        pid = owner.get("pid") if type(owner.get("pid")) is int else None
    if progress is not None and owner is None:
        raise StagingError(f"worker-{index} progress has no registered owner")

    if result:
        if set(result) != WORKER_RESULT_FIELDS:
            raise StagingError(f"worker-{index} result schema is invalid")
        if owner is None:
            raise StagingError(f"worker-{index} result has no registered owner")
        if (
            type(result.get("schemaVersion")) is not int
            or result["schemaVersion"] != 3
            or type(result.get("workerIndex")) is not int
            or result["workerIndex"] != index
            or result.get("taskId") != task_id
            or type(result.get("uid")) is not int
            or result["uid"] != os.getuid()
            or type(result.get("rootDevice")) is not int
            or result["rootDevice"] != root_info.st_dev
            or type(result.get("rootInode")) is not int
            or result["rootInode"] != root_info.st_ino
            or result.get("planSha256") != (manifest.get("planSha256") if manifest else None)
            or result.get("expectedNodeIds") != (manifest.get("nodeIds") if manifest else [])
            or result.get("assignedNodeIds") != expected_ids
        ):
            raise StagingError(f"worker-{index} result does not match the manifest")
        if type(result.get("pid")) is not int or pid is None or result["pid"] != pid:
            raise StagingError(f"worker-{index} PID differs from its owner record")
        pid = result.get("pid") if type(result.get("pid")) is int else pid
        exit_code = (
            result.get("pytestExitCode") if type(result.get("pytestExitCode")) is int else None
        )
        raw_execution = result.get("execution")
        if isinstance(raw_execution, list):
            for item in raw_execution:
                if not isinstance(item, dict):
                    continue
                node_id = item.get("nodeId")
                if isinstance(node_id, str):
                    execution_ids.append(node_id)
        status = result.get("status") if result.get("status") in {"passed", "failed"} else "invalid"
        _validate_failure_taxonomy(result.get("failureTaxonomy"), status, index)
        failure_taxonomy = result.get("failureTaxonomy")
        if type(result.get("pytestExitCode")) is not int:
            raise StagingError(f"worker-{index} exit code is invalid")
        if type(result.get("collectionFailures")) is not list:
            raise StagingError(f"worker-{index} collection errors are malformed")
        if status == "passed" and (
            exit_code != 0
            or result.get("error") is not None
            or result.get("collectionFailures") != []
        ):
            raise StagingError(f"worker-{index} passing result has failure metadata")
        raw_junit = files.get(f"worker-{index}/junit.xml")
        if status == "passed" and raw_junit is None:
            raise StagingError(f"worker-{index} passed without a JUnit report")
        if raw_junit is not None:
            junit_sha256 = hashlib.sha256(raw_junit).hexdigest()
            junit_bytes, junit_summary, junit_outcomes = _sanitize_junit(
                raw_junit,
                expected_ids,
                allow_partial=status != "passed",
            )
            result_junit = result.get("junit")
            expected_count_fields = {"sha256", "tests", "failures", "errors", "skipped", "nodeIds"}
            if status == "passed" and not isinstance(result_junit, dict):
                raise StagingError(f"worker-{index} passed without a JUnit summary")
            if result_junit is not None:
                if not isinstance(result_junit, dict) or set(result_junit) != expected_count_fields:
                    raise StagingError(f"worker-{index} JUnit summary schema is invalid")
                if any(result_junit.get(key) != value for key, value in junit_summary.items()):
                    raise StagingError(f"worker-{index} JUnit summary differs from its XML")
                if junit_sha256 != result_junit.get("sha256"):
                    raise StagingError(f"worker-{index} JUnit digest differs from its XML")
        if len(set(execution_ids)) != len(execution_ids) or any(
            nodeid not in expected_ids for nodeid in execution_ids
        ):
            raise StagingError(f"worker-{index} execution IDs are duplicated or unexpected")
        if status == "passed":
            execution_ids = _validate_passed_execution(raw_execution, expected_ids, junit_outcomes)
            if (
                exit_code != 0
                or result.get("error") is not None
                or result.get("collectionFailures") != []
            ):
                raise StagingError(
                    f"worker-{index} passing result lacks exact valid execution evidence"
                )

    safe = {
        "workerIndex": index,
        "pid": pid,
        "status": status,
        "pytestExitCode": exit_code,
        "assignedNodeCount": len(expected_ids),
        "executionNodeIds": execution_ids,
        "junit": junit_summary,
        "junitSha256": junit_sha256,
        "failureTaxonomy": failure_taxonomy,
        "progress": progress if result is None else None,
    }
    scope_files: dict[str, bytes] = {}
    if junit_bytes is not None:
        scope_files[f"worker-{index}/junit.xml"] = junit_bytes
    if result is None and progress is not None:
        scope_files[f"worker-{index}/progress.json"] = (
            json.dumps(progress, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    log_lines = [
        f"worker: {index}",
        f"pid: {pid if pid is not None else 'not-started'}",
        f"status: {status}",
        f"pytest exit code: {exit_code if exit_code is not None else 'not-recorded'}",
        f"assigned node count: {len(expected_ids)}",
        f"executed node count: {len(execution_ids)}",
    ]
    if result is None and progress is not None:
        log_lines.extend(
            [
                f"progress phase: {progress['phase']}",
                f"progress nodeid: {progress['nodeId'] or 'none'}",
                f"progress elapsed seconds: {progress['elapsedSeconds']}",
            ]
        )
    if junit_summary:
        log_lines.extend(
            [
                f"junit tests: {junit_summary['tests']}",
                f"junit failures: {junit_summary['failures']}",
                f"junit errors: {junit_summary['errors']}",
                f"junit skipped: {junit_summary['skipped']}",
            ]
        )
    if failure_taxonomy is not None:
        log_lines.extend(
            [
                f"failure phase: {failure_taxonomy['phase']}",
                f"failure class: {failure_taxonomy['errorClass'] or 'unknown'}",
                f"failure code: {failure_taxonomy['errorCode']}",
            ]
        )
    log_lines.extend(f"nodeid: {nodeid}" for nodeid in execution_ids)
    scope_files[f"worker-{index}/result.json"] = (
        json.dumps(safe, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    scope_files[f"worker-{index}/pytest.log"] = ("\n".join(log_lines) + "\n").encode("utf-8")
    return safe, scope_files


def _scope_artifacts(
    scope: str,
    task_root_fd: int,
    root_info: os.stat_result,
    source_stats: dict[str, os.stat_result],
    source_bytes: dict[str, bytes],
    marker: dict[str, Any],
) -> dict[str, bytes]:
    task_id = marker["taskId"]
    manifest = _read_json(source_bytes.get("partitions.json"), "partition manifest", required=False)
    if manifest is not None:
        manifest = _validate_manifest(manifest, task_id)
    scheduler_result = _read_json(
        source_bytes.get("scheduler-result.json"), "scheduler result", required=False
    )
    if scheduler_result is not None:
        required = {
            "schemaVersion",
            "taskId",
            "selection",
            "status",
            "partitionSha256",
            "expectedNodeIds",
            "actualNodeIds",
            "partitionIntersection",
            "workerProcesses",
            "workers",
        }
        if (
            not required <= set(scheduler_result)
            or not set(scheduler_result) <= required | {"error"}
            or type(scheduler_result.get("schemaVersion")) is not int
            or scheduler_result["schemaVersion"] != 2
            or scheduler_result.get("taskId") != task_id
        ):
            raise StagingError("scheduler result identity/schema is invalid")
        if scheduler_result.get("status") not in {"passed", "failed"}:
            raise StagingError("scheduler result status is invalid")
        if scheduler_result.get("status") == "passed" and scheduler_result.get("error") is not None:
            raise StagingError("passing scheduler summary contains an error")
    if (
        manifest
        and scheduler_result
        and (
            scheduler_result.get("partitionSha256") != manifest["planSha256"]
            or scheduler_result.get("expectedNodeIds") != manifest["nodeIds"]
        )
    ):
        raise StagingError("scheduler summary does not match the partition manifest")

    safe_workers: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    for index in range(2):
        worker, worker_files = _safe_worker_summary(
            index=index,
            task_id=task_id,
            root_info=root_info,
            manifest=manifest,
            files=source_bytes,
        )
        safe_workers.append(worker)
        artifacts.update(worker_files)

    expected_ids = manifest.get("nodeIds", []) if manifest else []
    actual_ids = scheduler_result.get("actualNodeIds", []) if scheduler_result else []
    safe_summary = {
        "schemaVersion": 1,
        "taskId": task_id,
        "scope": scope,
        "status": scheduler_result.get("status", "not-run") if scheduler_result else "not-run",
        "planSha256": manifest.get("planSha256") if manifest else None,
        "expectedNodeCount": len(expected_ids),
        "actualNodeCount": len(actual_ids) if isinstance(actual_ids, list) else 0,
        "partitionIntersectionCount": (
            len(scheduler_result.get("partitionIntersection", [])) if scheduler_result else 0
        ),
        "workers": safe_workers,
    }
    artifacts["scheduler-result.json"] = (
        json.dumps(safe_summary, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if manifest:
        safe_manifest = {
            "schemaVersion": manifest["schemaVersion"],
            "taskId": task_id,
            "selection": manifest["selection"],
            "nodeIds": manifest["nodeIds"],
            "partitions": manifest["partitions"],
            "planSha256": manifest["planSha256"],
        }
        artifacts["partitions.json"] = (
            json.dumps(safe_manifest, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    if safe_summary["status"] == "passed":
        processes = scheduler_result.get("workerProcesses") if scheduler_result else None
        worker_summaries = scheduler_result.get("workers") if scheduler_result else None
        if (
            manifest is None
            or not isinstance(actual_ids, list)
            or actual_ids != manifest["nodeIds"]
            or scheduler_result is None
            or scheduler_result.get("selection") != manifest["selection"]
            or type(scheduler_result.get("partitionIntersection")) is not list
            or scheduler_result["partitionIntersection"] != []
            or len(safe_workers) != 2
            or any(worker["status"] != "passed" for worker in safe_workers)
            or not isinstance(processes, list)
            or len(processes) != 2
            or not isinstance(worker_summaries, list)
            or len(worker_summaries) != 2
        ):
            raise StagingError("PASS scheduler summary lacks exact safe partition evidence")
        process_pids: list[int] = []
        for index, process in enumerate(processes):
            if (
                not isinstance(process, dict)
                or type(process.get("pid")) is not int
                or type(process.get("returnCode")) is not int
                or process["returnCode"] != 0
                or process.get("waited") is not True
                or safe_workers[index]["pid"] != process["pid"]
            ):
                raise StagingError("PASS scheduler summary has invalid worker Popen evidence")
            process_pids.append(process["pid"])
        if len(set(process_pids)) != 2:
            raise StagingError("PASS scheduler summary duplicates worker PIDs")
        for index, summary in enumerate(worker_summaries):
            expected_worker = {
                "workerIndex": index,
                "pid": process_pids[index],
                "processReturnCode": 0,
                "processWaited": True,
                "status": "passed",
                "pytestExitCode": 0,
                "actualNodeIds": manifest["partitions"][index],
            }
            if not isinstance(summary, dict) or any(
                summary.get(key) != value for key, value in expected_worker.items()
            ):
                raise StagingError("PASS scheduler worker summary does not match its process")
            raw_junit = summary.get("junit")
            safe_junit = safe_workers[index]["junit"]
            if (
                not isinstance(raw_junit, dict)
                or safe_junit is None
                or raw_junit.get("sha256") != safe_workers[index]["junitSha256"]
                or any(raw_junit.get(key) != value for key, value in safe_junit.items())
            ):
                raise StagingError("PASS scheduler JUnit summary does not match its report")
    raw_collect_log = source_bytes.get("scheduler/collect.log", b"")
    collect_log = [
        f"scope: {scope}",
        f"collection status: {safe_summary['status']}",
        f"collected node count: {len(expected_ids)}",
        f"collection log sha256: {hashlib.sha256(raw_collect_log).hexdigest()}",
    ]
    artifacts["scheduler/collect.log"] = ("\n".join(collect_log) + "\n").encode("utf-8")

    for relative, expected in source_stats.items():
        _verify_relative(
            task_root_fd,
            relative,
            expected,
            root_device=root_info.st_dev,
            uid=os.getuid(),
        )
    return artifacts


def _load_source_root(
    runner_fd: int,
    runner_info: os.stat_result,
    scope: str,
) -> tuple[int, os.stat_result, dict[str, Any], dict[str, bytes], dict[str, os.stat_result]] | None:
    root_name = f"rwb-ci-pytest-{scope}"
    try:
        os.stat(root_name, dir_fd=runner_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    try:
        root_fd, root_info = _open_directory_at(
            runner_fd,
            root_name,
            device=runner_info.st_dev,
            uid=os.getuid(),
            private=True,
        )
    except FileNotFoundError:
        return None
    try:
        marker_loaded = _read_relative(
            root_fd, ROOT_MARKER, root_device=root_info.st_dev, uid=os.getuid()
        )
        if marker_loaded is None:
            raise StagingError(f"task root owner marker is missing: {scope}")
        marker_data, marker_stat = marker_loaded
        marker = _read_json(marker_data, "task root marker")
        if marker is None:
            raise StagingError(f"task root owner marker is invalid: {scope}")
        task_pattern = re.fullmatch(
            r"(?:github-[0-9]+-[0-9]+-(?:research-web|unit)"
            r"|fixture-[a-z0-9-]+|local-ci-validation)",
            marker.get("taskId", "") if isinstance(marker.get("taskId"), str) else "",
        )
        if (
            set(marker)
            != {"schemaVersion", "taskId", "uid", "pid", "device", "inode", "argv", "createdAtNs"}
            or type(marker.get("schemaVersion")) is not int
            or marker["schemaVersion"] != 1
            or type(marker.get("uid")) is not int
            or marker["uid"] != os.getuid()
            or type(marker.get("pid")) is not int
            or marker["pid"] <= 0
            or type(marker.get("device")) is not int
            or marker["device"] != root_info.st_dev
            or type(marker.get("inode")) is not int
            or marker["inode"] != root_info.st_ino
            or type(marker.get("argv")) is not list
            or any(not isinstance(argument, str) for argument in marker["argv"])
            or type(marker.get("createdAtNs")) is not int
            or task_pattern is None
            or not marker["taskId"].endswith(f"-{scope}")
        ):
            raise StagingError(f"task root owner marker is invalid: {scope}")

        raw_files: dict[str, bytes] = {}
        source_stats: dict[str, os.stat_result] = {ROOT_MARKER: marker_stat}
        for relative in SOURCE_ALLOWLIST:
            loaded = _read_relative(
                root_fd, relative, root_device=root_info.st_dev, uid=os.getuid()
            )
            if loaded is None:
                continue
            raw_files[relative], source_stats[relative] = loaded
        for index, relative in enumerate(PROGRESS_ALLOWLIST):
            if f"worker-{index}/result.json" in raw_files:
                continue
            loaded = _read_relative(
                root_fd, relative, root_device=root_info.st_dev, uid=os.getuid()
            )
            if loaded is None:
                continue
            raw_files[relative], source_stats[relative] = loaded
        _verify_directory_entry(runner_fd, root_name, root_info)
        for relative, expected in source_stats.items():
            _verify_relative(
                root_fd, relative, expected, root_device=root_info.st_dev, uid=os.getuid()
            )
        return root_fd, root_info, marker, raw_files, source_stats
    except BaseException:
        os.close(root_fd)
        raise


def _reopen_same_directory(path: Path, expected: os.stat_result) -> None:
    descriptor, current, _ = _open_owned_directory(path)
    try:
        if not _same_dir(expected, current):
            raise StagingError(f"directory path was replaced: {path.name}")
    finally:
        os.close(descriptor)


def _mkdir_at(parent_fd: int, name: str, *, mode: int = 0o700) -> tuple[int, os.stat_result]:
    try:
        os.mkdir(name, mode=mode, dir_fd=parent_fd)
    except FileExistsError as error:
        raise StagingError(f"staging destination already exists: {name}") from error
    return _open_directory_at(
        parent_fd,
        name,
        device=os.fstat(parent_fd).st_dev,
        uid=os.getuid(),
        private=True,
    )


def _write_file_at(parent_fd: int, name: str, content: bytes) -> os.stat_result:
    if not name or "/" in name or name in {".", ".."}:
        raise StagingError("unsafe staged evidence filename")
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise StagingError(f"cannot create staged evidence file {name}: {error}") from error
    try:
        data = memoryview(content)
        while data:
            written = os.write(descriptor, data)
            if written <= 0:
                raise StagingError(f"short write while staging {name}")
            data = data[written:]
        result = os.fstat(descriptor)
        if (
            not stat.S_ISREG(result.st_mode)
            or result.st_uid != os.getuid()
            or result.st_nlink != 1
            or result.st_size != len(content)
        ):
            raise StagingError(f"staged evidence file identity is invalid: {name}")
        return result
    finally:
        os.close(descriptor)


def _write_tree(root_fd: int, entries: dict[str, bytes]) -> int:
    total = 0
    directories: dict[tuple[str, ...], int] = {(): root_fd}
    owned_fds: list[int] = []
    try:
        for relative, content in sorted(entries.items()):
            parts = relative.split("/")
            if any(not part or part in {".", ".."} for part in parts):
                raise StagingError("unsafe staged evidence path")
            parent_parts = tuple(parts[:-1])
            if parent_parts not in directories:
                prefix: tuple[str, ...] = ()
                for component in parent_parts:
                    next_prefix = (*prefix, component)
                    if next_prefix not in directories:
                        parent_fd = directories[prefix]
                        directory_fd, _ = _mkdir_at(parent_fd, component)
                        directories[next_prefix] = directory_fd
                        owned_fds.append(directory_fd)
                    prefix = next_prefix
            parent_fd = directories[parent_parts]
            _write_file_at(parent_fd, parts[-1], content)
            total += len(content)
            if total > MAX_FILE_BYTES:
                raise StagingError("sanitized evidence exceeds the 100 MiB artifact cap")
        return total
    finally:
        for descriptor in reversed(owned_fds):
            os.close(descriptor)


def stage_evidence(
    runner_temp: Path, workspace: Path, *, max_bytes: int = MAX_FILE_BYTES
) -> dict[str, Any]:
    """Validate task roots, create sanitized evidence, and publish one fresh artifact dir."""
    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > MAX_FILE_BYTES:
        raise StagingError("artifact byte cap is invalid")
    temp_fd, temp_info, canonical_temp = _open_owned_directory(runner_temp)
    workspace_fd, workspace_info, canonical_workspace = _open_owned_directory(workspace)
    roots: list[
        tuple[str, int, os.stat_result, dict[str, Any], dict[str, bytes], dict[str, os.stat_result]]
    ] = []
    artifacts_fd: int | None = None
    stage_fd: int | None = None
    try:
        for scope in SCOPES:
            loaded_root = _load_source_root(temp_fd, temp_info, scope)
            if loaded_root is None:
                continue
            roots.append((scope, *loaded_root))

        scope_artifacts: dict[str, dict[str, bytes]] = {}
        for scope, root_fd, root_info, marker, raw_files, source_stats in roots:
            artifacts = _scope_artifacts(scope, root_fd, root_info, source_stats, raw_files, marker)
            for content in artifacts.values():
                _secret_scan(content)
            scope_artifacts[scope] = artifacts

        entries: dict[str, bytes] = {}
        for scope, artifacts in scope_artifacts.items():
            for relative, content in artifacts.items():
                entries[f"{scope}/{relative}"] = content
        status = {
            "schemaVersion": 1,
            "status": "staged" if roots else "no-evidence",
            "scopes": [scope for scope, *_ in roots],
            "files": sorted([*entries, "status.json"]),
            "contentBytes": sum(len(content) for content in entries.values()),
        }
        entries["status.json"] = (
            json.dumps(status, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        total = sum(len(content) for content in entries.values())
        if total > max_bytes:
            raise StagingError("sanitized evidence exceeds the configured artifact cap")
        for scope, root_fd, root_info, _, _, source_stats in roots:
            _verify_directory_entry(temp_fd, f"rwb-ci-pytest-{scope}", root_info)
            for relative, expected in source_stats.items():
                _verify_relative(
                    root_fd,
                    relative,
                    expected,
                    root_device=root_info.st_dev,
                    uid=os.getuid(),
                )

        _reopen_same_directory(canonical_temp, temp_info)
        _reopen_same_directory(canonical_workspace, workspace_info)

        try:
            os.stat("artifacts", dir_fd=workspace_fd, follow_symlinks=False)
        except FileNotFoundError:
            artifacts_fd, artifacts_info = _mkdir_at(workspace_fd, "artifacts")
        else:
            artifacts_fd, artifacts_info = _open_directory_at(
                workspace_fd,
                "artifacts",
                device=workspace_info.st_dev,
                uid=os.getuid(),
                private=False,
            )

        stage_fd, stage_info = _mkdir_at(artifacts_fd, "research-web-checks")
        _write_tree(stage_fd, entries)

        current_artifacts = os.stat("artifacts", dir_fd=workspace_fd, follow_symlinks=False)
        current_stage = os.stat("research-web-checks", dir_fd=artifacts_fd, follow_symlinks=False)
        if not _same_dir(artifacts_info, current_artifacts) or not _same_dir(
            stage_info, current_stage
        ):
            raise StagingError("artifact parent directory changed during staging")
        _reopen_same_directory(canonical_temp, temp_info)
        _reopen_same_directory(canonical_workspace, workspace_info)
        for scope, root_fd, root_info, _, _, source_stats in roots:
            _verify_directory_entry(temp_fd, f"rwb-ci-pytest-{scope}", root_info)
            for relative, expected in source_stats.items():
                _verify_relative(
                    root_fd,
                    relative,
                    expected,
                    root_device=root_info.st_dev,
                    uid=os.getuid(),
                )
        return {
            "status": status["status"],
            "staged": True,
            "outputPath": str(canonical_workspace / "artifacts" / "research-web-checks"),
            "totalBytes": total,
            "fileCount": len(entries),
            "scopes": status["scopes"],
        }
    finally:
        for _, root_fd, _, _, _, _ in roots:
            os.close(root_fd)
        if stage_fd is not None:
            os.close(stage_fd)
        if artifacts_fd is not None:
            os.close(artifacts_fd)
        os.close(workspace_fd)
        os.close(temp_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-temp", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=MAX_FILE_BYTES)
    args = parser.parse_args(argv)
    try:
        result = stage_evidence(args.runner_temp, args.workspace, max_bytes=args.max_bytes)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, StagingError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "failed", "staged": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
