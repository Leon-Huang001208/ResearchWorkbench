"""Run an existing pytest selection in two exact, isolated CI partitions."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PARTITION_COUNT = 2
INTERNAL_PREFIX = "--rwb-internal-"
ROOT_MARKER = ".rwb-ci-pytest-root.json"
MANIFEST_SCHEMA_VERSION = 2
WORKER_RESULT_SCHEMA_VERSION = 3
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
SAFE_EXCEPTION_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")


class PartitionError(RuntimeError):
    """Raised when a suite cannot be split or its evidence is incomplete."""


def _safe_exception_class(value: Any) -> str | None:
    if isinstance(value, BaseException):
        candidate = type(value).__name__
    elif isinstance(value, str):
        candidate = value.strip().split(":", 1)[0].rsplit(".", 1)[-1]
    else:
        return None
    return candidate if SAFE_EXCEPTION_CLASS.fullmatch(candidate) else None


def _failure_taxonomy(phase: str, error_class: Any, error_code: str) -> dict[str, str | None]:
    return {
        "phase": phase,
        "errorClass": _safe_exception_class(error_class),
        "errorCode": error_code,
    }


def _validate_failure_taxonomy(value: Any, status: Any) -> None:
    if status == "passed":
        if value is not None:
            raise PartitionError("passing worker contains failure taxonomy")
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
        raise PartitionError("failed worker is missing safe failure taxonomy")
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
            and (
                not isinstance(error_class, str) or not SAFE_EXCEPTION_CLASS.fullmatch(error_class)
            )
        )
    ):
        raise PartitionError("worker failure taxonomy is invalid")


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_selection(arguments: Sequence[str], repository_root: Path) -> None:
    """Accept only test paths and the selection options used by the CI contract."""
    if not arguments:
        raise PartitionError("pytest selection must not be empty")

    repo = _canonical(repository_root)
    expecting_confcutdir = False
    paths_seen = 0
    for argument in arguments:
        if expecting_confcutdir:
            candidate = Path(argument)
            expecting_confcutdir = False
        elif argument == "--confcutdir":
            expecting_confcutdir = True
            continue
        elif argument.startswith("--confcutdir="):
            candidate = Path(argument.split("=", 1)[1])
        elif argument in {"-q", "--quiet"}:
            continue
        elif argument.startswith("-"):
            raise PartitionError(f"unsupported pytest option in fixed CI scope: {argument}")
        else:
            candidate = Path(argument.split("::", 1)[0])
            paths_seen += 1

        if candidate.is_absolute():
            raise PartitionError(f"absolute pytest paths are not allowed: {argument}")
        resolved = _canonical(repo / candidate)
        if not _is_within(resolved, repo):
            raise PartitionError(f"pytest path escapes repository root: {argument}")
        if not resolved.exists():
            raise PartitionError(f"pytest path does not exist: {argument}")

    if expecting_confcutdir:
        raise PartitionError("--confcutdir requires a path")
    if paths_seen == 0:
        raise PartitionError("pytest selection must include at least one test path")


def split_nodeids(nodeids: Sequence[str], count: int = PARTITION_COUNT) -> list[list[str]]:
    """Round-robin the real collection order to balance even large single modules."""
    if count != PARTITION_COUNT:
        raise PartitionError("this runner supports exactly two pytest partitions")
    if not nodeids:
        raise PartitionError("pytest collection returned no node IDs")
    if any(not isinstance(nodeid, str) or not nodeid for nodeid in nodeids):
        raise PartitionError("pytest collection returned an invalid node ID")
    if len(set(nodeids)) != len(nodeids):
        raise PartitionError("pytest collection returned duplicate node IDs")
    if len(nodeids) < count:
        raise PartitionError("the selected pytest scope needs at least two collected node IDs")

    partitions = [list(nodeids[index::count]) for index in range(count)]
    if any(not part for part in partitions):
        raise PartitionError("pytest partition unexpectedly has no node IDs")
    return partitions


def _plan_sha256(
    task_id: str,
    selection: Sequence[str],
    nodeids: Sequence[str],
    partitions: Sequence[Sequence[str]],
) -> str:
    payload = {
        "taskId": task_id,
        "selection": list(selection),
        "nodeIds": list(nodeids),
        "partitions": [list(part) for part in partitions],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def validate_partition_manifest(
    manifest: dict[str, Any],
    actual_nodeids: Sequence[str],
    selection: Sequence[str],
    task_id: str,
) -> list[str]:
    """Require exact ordered collection equality and a disjoint two-way union."""
    expected_fields = {
        "schemaVersion",
        "taskId",
        "selection",
        "nodeIds",
        "partitions",
        "planSha256",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise PartitionError("parent partition manifest schema is incomplete or unknown")
    if (
        type(manifest.get("schemaVersion")) is not int
        or manifest["schemaVersion"] != MANIFEST_SCHEMA_VERSION
    ):
        raise PartitionError("unsupported or missing partition manifest schema")
    if manifest.get("taskId") != task_id:
        raise PartitionError("partition manifest task identity does not match its root")
    expected = manifest.get("nodeIds")
    partitions = manifest.get("partitions")
    if manifest.get("selection") != list(selection):
        raise PartitionError("worker selection does not match the parent selection")
    if not isinstance(expected, list) or list(actual_nodeids) != expected:
        raise PartitionError("worker collection does not exactly match the parent node IDs")
    if not isinstance(partitions, list) or len(partitions) != PARTITION_COUNT:
        raise PartitionError("partition manifest must contain exactly two partitions")
    if any(not isinstance(part, list) for part in partitions):
        raise PartitionError("partition manifest contains a malformed partition")
    first, second = partitions
    if not first or not second:
        raise PartitionError("partition manifest contains an empty worker assignment")
    if set(first) & set(second):
        raise PartitionError("partition assignments overlap")
    if len(first) != len(set(first)) or len(second) != len(set(second)):
        raise PartitionError("partition assignment contains duplicate node IDs")
    if set(first) | set(second) != set(expected):
        raise PartitionError("partition assignments do not cover the parent collection")
    if partitions != split_nodeids(expected):
        raise PartitionError("partition assignments are not the deterministic split")
    if manifest.get("planSha256") != _plan_sha256(task_id, selection, expected, partitions):
        raise PartitionError("partition plan digest does not match its selection and node IDs")
    return list(expected)


def create_task_root(candidate: Path, allowed_parent: Path, task_id: str) -> Path:
    """Create a fresh, owner-checked task directory under its allowed temp parent."""
    parent = _canonical(allowed_parent)
    root = _canonical(candidate)
    if not root.is_absolute() or root.parent != parent:
        raise PartitionError("task result root must be a direct child of the allowed temp root")
    try:
        parent_info = parent.stat()
    except OSError as error:
        raise PartitionError(f"cannot inspect temp root: {error}") from error
    if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid():
        raise PartitionError("temp root must be a directory owned by the current user")
    if root.exists() or root.is_symlink():
        raise PartitionError("task result root already exists; refusing to overwrite it")
    root.mkdir(mode=0o700)
    info = root.stat()
    marker = {
        "schemaVersion": 1,
        "taskId": task_id,
        "uid": os.getuid(),
        "pid": os.getpid(),
        "device": info.st_dev,
        "inode": info.st_ino,
        "argv": list(sys.argv),
        "createdAtNs": time.time_ns(),
    }
    (root / ROOT_MARKER).write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
    return root


def validate_task_root(root: Path, allowed_parent: Path) -> dict[str, Any]:
    """Reject symlinks, foreign roots, and roots whose registered inode changed."""
    parent = _canonical(allowed_parent)
    canonical_root = _canonical(root)
    if canonical_root.parent != parent or root.is_symlink():
        raise PartitionError("worker result root is outside its task temp parent")
    info = canonical_root.stat()
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PartitionError("worker result root permissions are not private to the owner")
    marker_path = canonical_root / ROOT_MARKER
    if marker_path.is_symlink() or not marker_path.is_file():
        raise PartitionError("worker result root marker is missing or unsafe")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("uid") != os.getuid() or info.st_uid != os.getuid():
        raise PartitionError("worker result root is not owned by the current user")
    if marker.get("device") != info.st_dev or marker.get("inode") != info.st_ino:
        raise PartitionError("worker result root identity changed after registration")
    return marker


@dataclass
class CollectionPlugin:
    nodeids: list[str] | None = None
    failures: list[str] | None = None

    def __post_init__(self) -> None:
        self.failures = []

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            assert self.failures is not None
            self.failures.append(str(report.longrepr))

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        self.nodeids = [item.nodeid for item in items]


@dataclass
class WorkerPlugin:
    worker_index: int
    worker_dir: Path
    manifest: dict[str, Any]
    arguments: list[str]
    task_id: str

    def __post_init__(self) -> None:
        self.collection_failures: list[str] = []
        self.expected = list(self.manifest.get("nodeIds", []))
        self.assigned = list(self.manifest.get("partitions", [[], []])[self.worker_index])
        self.execution_reports: dict[str, list[dict[str, str]]] = {}
        self.failure_taxonomy: dict[str, str | None] | None = None

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.collection_failures.append(str(report.longrepr))
            if self.failure_taxonomy is None:
                reprcrash = getattr(report.longrepr, "reprcrash", None)
                self.failure_taxonomy = _failure_taxonomy(
                    "collection",
                    getattr(reprcrash, "message", None),
                    "pytest_collection_failed",
                )

    def pytest_collection_modifyitems(self, session: Any, config: Any, items: list[Any]) -> None:
        actual = [item.nodeid for item in items]
        if self.collection_failures:
            import pytest

            pytest.exit("pytest collection reported errors", returncode=2)
        try:
            validate_partition_manifest(self.manifest, actual, self.arguments, self.task_id)
            assigned = set(self.assigned)
            for item in items:
                existing = [name for name, _ in item.user_properties if name == "rwb_nodeid"]
                if item.nodeid in assigned and existing:
                    raise PartitionError("test already defines reserved rwb_nodeid JUnit property")
            deselected = [item for item in items if item.nodeid not in assigned]
            if deselected:
                config.hook.pytest_deselected(items=deselected)
            items[:] = [item for item in items if item.nodeid in assigned]
            for item in items:
                item.user_properties.append(("rwb_nodeid", item.nodeid))
        # Any bad partition evidence must abort collection instead of selecting a partial suite.
        except Exception as error:  # noqa: BLE001
            import pytest

            pytest.exit(str(error), returncode=2)

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when not in {"setup", "call", "teardown"}:
            return
        if report.outcome == "failed" and self.failure_taxonomy is None:
            self.failure_taxonomy = _failure_taxonomy(
                report.when,
                getattr(getattr(report.longrepr, "reprcrash", None), "message", None),
                f"pytest_{report.when}_failed",
            )
        self.execution_reports.setdefault(report.nodeid, []).append(
            {"phase": report.when, "outcome": report.outcome}
        )


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _pythonpath(repository_root: Path, existing: str) -> str:
    root = str(_canonical(repository_root))
    components = [
        component
        for component in existing.split(os.pathsep)
        if component and _canonical(Path(component)) != Path(root)
    ]
    return os.pathsep.join([root, *components])


def _register_process(root: Path, name: str, pid: int | None, argv: Sequence[str]) -> None:
    try:
        root_info = root.stat()
    except OSError as error:
        raise PartitionError(f"cannot register worker without root identity: {error}") from error
    _atomic_json(
        root / f"{name}.owner.json",
        {
            "schemaVersion": 1,
            "name": name,
            "pid": pid,
            "uid": os.getuid(),
            "device": root_info.st_dev,
            "inode": root_info.st_ino,
            "argv": list(argv),
            "registeredAtNs": time.time_ns(),
        },
    )


def _worker_command(
    script: Path,
    worker_index: int,
    root: Path,
    repository_root: Path,
    allowed_parent: Path,
    plan_sha256: str,
    arguments: Sequence[str],
) -> list[str]:
    return [
        sys.executable,
        "-P",
        str(script),
        f"{INTERNAL_PREFIX}worker={worker_index}",
        f"{INTERNAL_PREFIX}root={root}",
        f"{INTERNAL_PREFIX}repo={repository_root}",
        f"{INTERNAL_PREFIX}parent={allowed_parent}",
        f"{INTERNAL_PREFIX}plan={plan_sha256}",
        "--",
        *arguments,
    ]


def _pytest_arguments(arguments: Sequence[str], worker_dir: Path) -> list[str]:
    return [
        *arguments,
        f"--basetemp={worker_dir / 'basetemp'}",
        "-o",
        f"cache_dir={worker_dir / 'pytest-cache'}",
        f"--junitxml={worker_dir / 'junit.xml'}",
    ]


def _pytest_collection_arguments(arguments: Sequence[str], scheduler_dir: Path) -> list[str]:
    return [
        *arguments,
        "--collect-only",
        f"--basetemp={scheduler_dir / 'basetemp'}",
        "-o",
        f"cache_dir={scheduler_dir / 'pytest-cache'}",
    ]


def _parse_junit(path: Path, assigned: Sequence[str]) -> dict[str, Any]:
    if not path.is_file():
        raise PartitionError(f"JUnit report is missing: {path.name}")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise PartitionError(f"JUnit report is invalid: {error}") from error
    cases = root.findall(".//testcase")
    if len(cases) != len(assigned):
        raise PartitionError(
            f"JUnit case count {len(cases)} does not match assigned node count {len(assigned)}"
        )
    nodeids: list[str] = []
    case_outcomes: dict[str, dict[str, bool]] = {}
    counts = {"tests": len(cases), "failures": 0, "errors": 0, "skipped": 0}
    for case in cases:
        properties = [
            item.attrib.get("value")
            for item in case.findall("./properties/property")
            if item.attrib.get("name") == "rwb_nodeid"
        ]
        if len(properties) != 1 or not isinstance(properties[0], str) or not properties[0]:
            raise PartitionError("JUnit testcase must contain exactly one rwb_nodeid property")
        nodeid = properties[0]
        nodeids.append(nodeid)
        case_outcomes[nodeid] = {
            "failure": bool(case.findall("failure")),
            "error": bool(case.findall("error")),
            "skipped": bool(case.findall("skipped")),
        }
        counts["failures"] += len(case.findall("failure"))
        counts["errors"] += len(case.findall("error"))
        counts["skipped"] += len(case.findall("skipped"))
    if len(set(nodeids)) != len(nodeids):
        raise PartitionError("JUnit report duplicates an rwb_nodeid")
    if nodeids != list(assigned):
        raise PartitionError("JUnit testcase node IDs do not exactly match the worker assignment")
    return {**counts, "nodeIds": nodeids, "caseOutcomes": case_outcomes}


def _validate_execution_records(
    execution: Any,
    assigned: Sequence[str],
    junit: dict[str, Any],
) -> list[str]:
    if not isinstance(execution, list):
        raise PartitionError("worker execution evidence must be a list")
    nodeids = [entry.get("nodeId") if isinstance(entry, dict) else None for entry in execution]
    if nodeids != list(assigned) or len(set(nodeids)) != len(nodeids):
        raise PartitionError(
            "worker executed node IDs are missing, unexpected, duplicated, or reordered"
        )
    if junit.get("nodeIds") != nodeids:
        raise PartitionError("JUnit node IDs do not match executed node IDs")

    for entry in execution:
        phases = entry.get("phases")
        if not isinstance(phases, list) or not phases:
            raise PartitionError("worker node is missing pytest phase evidence")
        if any(
            not isinstance(phase, dict)
            or set(phase) != {"phase", "outcome"}
            or phase.get("phase") not in {"setup", "call", "teardown"}
            or phase.get("outcome") not in {"passed", "failed", "skipped"}
            for phase in phases
        ):
            raise PartitionError("worker pytest phase evidence is malformed")
        phase_names = [phase["phase"] for phase in phases]
        if phase_names[0] != "setup" or phase_names[-1] != "teardown":
            raise PartitionError("worker pytest phase evidence must include setup and teardown")
        if phase_names.count("setup") != 1 or phase_names.count("teardown") != 1:
            raise PartitionError("worker pytest setup/teardown phase count is invalid")
        if any(name != "call" for name in phase_names[1:-1]):
            raise PartitionError("worker pytest call phase ordering is invalid")
        setup_outcome = phases[0]["outcome"]
        call_phases = [phase for phase in phases if phase["phase"] == "call"]
        if setup_outcome == "passed" and not call_phases:
            raise PartitionError("passed setup is missing call-phase evidence")
        if setup_outcome != "passed" and call_phases:
            raise PartitionError("call-phase evidence is invalid after setup failure or skip")
        if any(phase["outcome"] == "failed" for phase in phases):
            raise PartitionError("passing worker contains a failed pytest phase")
        skipped = any(phase["outcome"] == "skipped" for phase in phases)
        if junit["caseOutcomes"][entry["nodeId"]]["skipped"] != skipped:
            raise PartitionError("JUnit skip evidence does not match pytest phase outcomes")
        case_outcome = junit["caseOutcomes"][entry["nodeId"]]
        if case_outcome["failure"] or case_outcome["error"]:
            raise PartitionError("passing worker JUnit contains a failure or error")
    return nodeids


def _validate_worker_result(
    result: Any,
    *,
    worker_index: int,
    process_pid: int,
    task_id: str,
    root_info: os.stat_result,
    manifest: dict[str, Any],
    worker_dir: Path,
) -> dict[str, Any]:
    if not isinstance(result, dict) or set(result) != WORKER_RESULT_FIELDS:
        raise PartitionError(
            f"worker-{worker_index} result schema is missing, unknown, or malformed"
        )
    if result["schemaVersion"] != WORKER_RESULT_SCHEMA_VERSION:
        raise PartitionError(f"worker-{worker_index} result schema version is invalid")
    _validate_failure_taxonomy(result["failureTaxonomy"], result["status"])
    if (
        not isinstance(result["taskId"], str)
        or result["taskId"] != task_id
        or type(result["workerIndex"]) is not int
        or result["workerIndex"] != worker_index
    ):
        raise PartitionError(f"worker-{worker_index} result identity is invalid")
    if type(result["pid"]) is not int or result["pid"] <= 0 or result["pid"] != process_pid:
        raise PartitionError(f"worker-{worker_index} result PID does not match its Popen PID")
    if type(result["uid"]) is not int or result["uid"] != os.getuid():
        raise PartitionError(f"worker-{worker_index} result UID does not match the current user")
    if (
        type(result["rootDevice"]) is not int
        or type(result["rootInode"]) is not int
        or result["rootDevice"] != root_info.st_dev
        or result["rootInode"] != root_info.st_ino
    ):
        raise PartitionError(f"worker-{worker_index} result root identity is invalid")
    if result["planSha256"] != manifest["planSha256"]:
        raise PartitionError(f"worker-{worker_index} result partition digest is invalid")
    if result["expectedNodeIds"] != manifest["nodeIds"]:
        raise PartitionError(f"worker-{worker_index} result parent node IDs are invalid")
    assigned = manifest["partitions"][worker_index]
    if result["assignedNodeIds"] != assigned:
        raise PartitionError(f"worker-{worker_index} result assignment is invalid")
    if (
        result["status"] != "passed"
        or type(result["pytestExitCode"]) is not int
        or result["pytestExitCode"] != 0
        or result["error"] is not None
        or result["collectionFailures"] != []
    ):
        raise PartitionError(f"worker-{worker_index} did not pass pytest cleanly")

    junit_path = worker_dir / "junit.xml"
    junit = _parse_junit(junit_path, assigned)
    junit_info = result["junit"]
    expected_junit_fields = {"sha256", "nodeIds", "tests", "failures", "errors", "skipped"}
    if not isinstance(junit_info, dict) or set(junit_info) != expected_junit_fields:
        raise PartitionError(f"worker-{worker_index} JUnit summary schema is invalid")
    if (
        not isinstance(junit_info["sha256"], str)
        or type(junit_info["nodeIds"]) is not list
        or any(not isinstance(nodeid, str) for nodeid in junit_info["nodeIds"])
        or any(
            type(junit_info[key]) is not int for key in ("tests", "failures", "errors", "skipped")
        )
    ):
        raise PartitionError(f"worker-{worker_index} JUnit summary types are invalid")
    digest = hashlib.sha256(junit_path.read_bytes()).hexdigest()
    parsed_junit = {key: value for key, value in junit.items() if key != "caseOutcomes"}
    parsed_junit["sha256"] = digest
    if junit_info != parsed_junit:
        raise PartitionError(f"worker-{worker_index} JUnit summary does not match its XML file")
    actual = _validate_execution_records(result["execution"], assigned, junit)
    return {"nodeIds": actual, "junit": parsed_junit}


def _validate_worker_owner(
    root: Path,
    worker_index: int,
    process: subprocess.Popen[bytes],
    root_info: os.stat_result,
) -> None:
    path = root / f"worker-{worker_index}.owner.json"
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PartitionError(f"worker-{worker_index} owner record is missing or invalid") from error
    expected_fields = {
        "schemaVersion",
        "name",
        "pid",
        "uid",
        "device",
        "inode",
        "argv",
        "registeredAtNs",
    }
    if not isinstance(owner, dict) or set(owner) != expected_fields:
        raise PartitionError(f"worker-{worker_index} owner record schema is invalid")
    if (
        type(owner["schemaVersion"]) is not int
        or owner["schemaVersion"] != 1
        or owner["name"] != f"worker-{worker_index}"
        or type(owner["pid"]) is not int
        or owner["pid"] != process.pid
        or type(owner["uid"]) is not int
        or owner["uid"] != os.getuid()
        or type(owner["device"]) is not int
        or owner["device"] != root_info.st_dev
        or type(owner["inode"]) is not int
        or owner["inode"] != root_info.st_ino
        or owner["argv"] != process.args
        or type(owner["registeredAtNs"]) is not int
    ):
        raise PartitionError(f"worker-{worker_index} owner identity does not match Popen")


def _worker_result(
    plugin: WorkerPlugin,
    *,
    task_id: str,
    root_info: os.stat_result,
    exit_code: int,
    error: str | None,
) -> dict[str, Any]:
    execution = [
        {"nodeId": nodeid, "phases": plugin.execution_reports.get(nodeid, [])}
        for nodeid in plugin.assigned
        if nodeid in plugin.execution_reports
    ]
    junit: dict[str, Any] | None = None
    junit_path = plugin.worker_dir / "junit.xml"
    if junit_path.is_file():
        parsed = _parse_junit(junit_path, plugin.assigned)
        junit = {key: value for key, value in parsed.items() if key != "caseOutcomes"}
        junit["sha256"] = hashlib.sha256(junit_path.read_bytes()).hexdigest()
    return {
        "schemaVersion": WORKER_RESULT_SCHEMA_VERSION,
        "taskId": task_id,
        "workerIndex": plugin.worker_index,
        "pid": os.getpid(),
        "uid": os.getuid(),
        "rootDevice": root_info.st_dev,
        "rootInode": root_info.st_ino,
        "planSha256": plugin.manifest["planSha256"],
        "expectedNodeIds": plugin.expected,
        "assignedNodeIds": plugin.assigned,
        "execution": execution,
        "collectionFailures": plugin.collection_failures,
        "junit": junit,
        "pytestExitCode": exit_code,
        "status": "passed" if exit_code == 0 and error is None else "failed",
        "error": error,
        "failureTaxonomy": plugin.failure_taxonomy,
    }


def _run_worker(plugin: WorkerPlugin, task_id: str, root_info: os.stat_result) -> int:
    worker_dir = plugin.worker_dir
    worker_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    (worker_dir / "basetemp").mkdir(mode=0o700, exist_ok=True)
    (worker_dir / "pytest-cache").mkdir(mode=0o700, exist_ok=True)
    import pytest

    previous_environment = os.environ.copy()
    worker_environment = dict(previous_environment)
    worker_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    worker_environment["PYTHONPATH"] = _pythonpath(
        Path.cwd(), worker_environment.get("PYTHONPATH", "")
    )
    os.environ.update(worker_environment)
    error: str | None = None
    exit_code = 1
    try:
        exit_code = int(
            pytest.main(_pytest_arguments(plugin.arguments, worker_dir), plugins=[plugin])
        )
        if exit_code != 0 and plugin.failure_taxonomy is None:
            if plugin.collection_failures:
                plugin.failure_taxonomy = _failure_taxonomy(
                    "collection", None, "pytest_collection_failed"
                )
            else:
                plugin.failure_taxonomy = _failure_taxonomy("pytest", None, "pytest_exit_nonzero")
        if plugin.collection_failures:
            error = "pytest worker collection reported errors"
        if exit_code == 0 and error is None:
            junit = _parse_junit(worker_dir / "junit.xml", plugin.assigned)
            execution = [
                {"nodeId": nodeid, "phases": plugin.execution_reports.get(nodeid, [])}
                for nodeid in plugin.assigned
                if nodeid in plugin.execution_reports
            ]
            _validate_execution_records(execution, plugin.assigned, junit)
    # Catch interrupts at the worker boundary so the failed result is still written for the parent.
    except BaseException as caught:  # noqa: BLE001
        error = f"{type(caught).__name__}: {caught}"
        if plugin.failure_taxonomy is None:
            plugin.failure_taxonomy = _failure_taxonomy(
                "worker",
                caught,
                (
                    "worker_evidence_validation_failed"
                    if isinstance(caught, PartitionError)
                    else "pytest_runner_exception"
                ),
            )
        if isinstance(caught, KeyboardInterrupt):
            exit_code = 130
        elif exit_code == 0:
            exit_code = 1
    finally:
        try:
            result = _worker_result(
                plugin,
                task_id=task_id,
                root_info=root_info,
                exit_code=exit_code,
                error=error,
            )
        # Even serialization errors must produce a failed worker record rather than a silent exit.
        except BaseException as caught:  # noqa: BLE001
            error = f"{type(caught).__name__}: {caught}"
            exit_code = 1
            result = {
                "schemaVersion": WORKER_RESULT_SCHEMA_VERSION,
                "taskId": task_id,
                "workerIndex": plugin.worker_index,
                "pid": os.getpid(),
                "uid": os.getuid(),
                "rootDevice": root_info.st_dev,
                "rootInode": root_info.st_ino,
                "planSha256": plugin.manifest.get("planSha256"),
                "expectedNodeIds": plugin.expected,
                "assignedNodeIds": plugin.assigned,
                "execution": [],
                "collectionFailures": plugin.collection_failures,
                "junit": None,
                "pytestExitCode": exit_code,
                "status": "failed",
                "error": error,
                "failureTaxonomy": _failure_taxonomy(
                    "worker", caught, "worker_result_serialization_failed"
                ),
            }
        _atomic_json(worker_dir / "result.json", result)
        os.environ.clear()
        os.environ.update(previous_environment)
    return exit_code


def _internal_worker(argv: Sequence[str]) -> int:
    values: dict[str, str] = {}
    remaining: list[str] = []
    delimiter = False
    for argument in argv:
        if delimiter:
            remaining.append(argument)
        elif argument == "--":
            delimiter = True
        elif argument.startswith(INTERNAL_PREFIX) and "=" in argument:
            key, value = argument[len(INTERNAL_PREFIX) :].split("=", 1)
            values[key] = value
        else:
            raise PartitionError(f"unexpected internal worker argument: {argument}")
    expected_keys = {"worker", "root", "repo", "parent", "plan"}
    if not delimiter or set(values) != expected_keys:
        raise PartitionError("internal worker arguments are incomplete")

    root = Path(values["root"])
    repository = _canonical(Path(values["repo"]))
    allowed_parent = Path(values["parent"])
    if repository != _canonical(Path.cwd()):
        raise PartitionError("worker repository path does not match its working directory")
    if _canonical(root).parent != _canonical(allowed_parent):
        raise PartitionError("worker root does not belong to its registered task temp parent")
    marker = validate_task_root(root, allowed_parent)
    if type(marker.get("pid")) is not int or marker["pid"] != os.getppid():
        raise PartitionError("worker parent PID does not match task root owner")
    root_info = root.stat()
    worker_index = int(values["worker"])
    if worker_index not in range(PARTITION_COUNT):
        raise PartitionError("unknown internal worker index")
    manifest = json.loads((root / "partitions.json").read_text(encoding="utf-8"))
    if values["plan"] != manifest.get("planSha256"):
        raise PartitionError("worker command plan digest does not match the parent manifest")
    worker_dir = root / f"worker-{worker_index}"
    worker_dir.mkdir(mode=0o700, exist_ok=True)
    if manifest.get("taskId") != marker.get("taskId"):
        raise PartitionError("partition manifest task ID does not match root ownership")
    plugin = WorkerPlugin(worker_index, worker_dir, manifest, remaining, marker["taskId"])
    return _run_worker(plugin, marker["taskId"], root_info)


def run_suite(
    arguments: Sequence[str],
    task_root: Path,
    allowed_parent: Path,
    repository_root: Path,
    task_id: str,
) -> int:
    validate_selection(arguments, repository_root)
    root = create_task_root(task_root, allowed_parent, task_id)
    root_marker = validate_task_root(root, allowed_parent)
    if root_marker.get("taskId") != task_id or root_marker.get("pid") != os.getpid():
        raise PartitionError("task root registration does not belong to the current scheduler")
    root_info = root.stat()
    repository = _canonical(repository_root)
    scheduler_dir = root / "scheduler"
    scheduler_dir.mkdir(mode=0o700)
    (scheduler_dir / "basetemp").mkdir(mode=0o700)
    (scheduler_dir / "pytest-cache").mkdir(mode=0o700)
    signal_number: int | None = None

    def stop_workers(signum: int, _frame: Any) -> None:
        nonlocal signal_number
        signal_number = signum

    previous_handlers = {
        number: signal.signal(number, stop_workers) for number in (signal.SIGINT, signal.SIGTERM)
    }
    manifest: dict[str, Any] | None = None
    worker_processes: list[subprocess.Popen[bytes]] = []
    process_evidence: list[dict[str, Any]] = []
    startup_error: str | None = None
    collection_error: str | None = None
    try:
        import pytest

        previous_environment = os.environ.copy()
        previous_sys_path = list(sys.path)
        environment = dict(previous_environment)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = _pythonpath(repository, environment.get("PYTHONPATH", ""))
        os.environ.update(environment)
        if not sys.path or _canonical(Path(sys.path[0] or ".")) != repository:
            sys.path.insert(0, str(repository))
        collection_plugin = CollectionPlugin()
        try:
            with (
                (scheduler_dir / "collect.log").open("w", encoding="utf-8") as log,
                contextlib.redirect_stdout(log),
                contextlib.redirect_stderr(log),
            ):
                collection_code = int(
                    pytest.main(
                        _pytest_collection_arguments(arguments, scheduler_dir),
                        plugins=[collection_plugin],
                    )
                )
        finally:
            os.environ.clear()
            os.environ.update(previous_environment)
            sys.path[:] = previous_sys_path

        nodeids = collection_plugin.nodeids or []
        if signal_number is not None:
            collection_error = "scheduler interrupted during pytest collection"
        elif collection_code != 0 or collection_plugin.failures:
            collection_error = "pytest collection failed; see scheduler/collect.log"
        else:
            partitions = split_nodeids(nodeids)
            manifest = {
                "schemaVersion": MANIFEST_SCHEMA_VERSION,
                "taskId": task_id,
                "selection": list(arguments),
                "nodeIds": nodeids,
                "partitions": partitions,
                "planSha256": _plan_sha256(task_id, arguments, nodeids, partitions),
            }
            _atomic_json(root / "partitions.json", manifest)

        if manifest is not None and collection_error is None:
            environment["PYTHONPATH"] = _pythonpath(repository, environment.get("PYTHONPATH", ""))
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            for worker_index in range(PARTITION_COUNT):
                worker_dir = root / f"worker-{worker_index}"
                worker_dir.mkdir(mode=0o700)
                command = _worker_command(
                    script=Path(__file__).resolve(),
                    worker_index=worker_index,
                    root=root,
                    repository_root=repository,
                    allowed_parent=_canonical(allowed_parent),
                    plan_sha256=manifest["planSha256"],
                    arguments=arguments,
                )
                _register_process(root, f"worker-{worker_index}", None, command)
                try:
                    with (worker_dir / "pytest.log").open("wb") as log:
                        process = subprocess.Popen(
                            command,
                            cwd=repository,
                            env=environment,
                            stdin=subprocess.DEVNULL,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    worker_processes.append(process)
                    _register_process(root, f"worker-{worker_index}", process.pid, command)
                except OSError as error:
                    startup_error = f"worker-{worker_index} could not start: {error}"
                    break
                if signal_number is not None:
                    break

        while (
            startup_error is None
            and signal_number is None
            and any(process.poll() is None for process in worker_processes)
        ):
            time.sleep(0.05)

        if startup_error is not None or signal_number is not None:
            signum = signal_number or signal.SIGTERM
            for process in worker_processes:
                if process.poll() is None:
                    try:
                        process.send_signal(signum)
                    except ProcessLookupError:
                        pass

        for process in worker_processes:
            try:
                return_code = process.wait(timeout=10 if (startup_error or signal_number) else None)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=5)
            process_evidence.append({"pid": process.pid, "returnCode": return_code, "waited": True})
    # This boundary owns all Popen children and must reap them on interruption or internal failure.
    except BaseException as error:  # noqa: BLE001
        if manifest is None:
            collection_error = f"{type(error).__name__}: {error}"
        else:
            startup_error = f"{type(error).__name__}: {error}"
        recorded_pids = {item["pid"] for item in process_evidence}
        for process in worker_processes:
            if process.pid in recorded_pids:
                continue
            if process.poll() is None:
                try:
                    process.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                return_code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=5)
            process_evidence.append({"pid": process.pid, "returnCode": return_code, "waited": True})
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)

    summary: dict[str, Any] = {
        "schemaVersion": 2,
        "taskId": task_id,
        "selection": list(arguments),
        "status": "failed",
        "partitionSha256": manifest.get("planSha256") if manifest else None,
        "expectedNodeIds": manifest.get("nodeIds", []) if manifest else [],
        "actualNodeIds": [],
        "partitionIntersection": [],
        "workerProcesses": process_evidence,
        "workers": [],
    }
    if collection_error:
        summary["error"] = collection_error
    if startup_error:
        summary["error"] = startup_error
    if signal_number is not None:
        summary["error"] = f"scheduler interrupted by signal {signal_number}"

    if (
        manifest is not None
        and collection_error is None
        and startup_error is None
        and signal_number is None
        and len(worker_processes) == PARTITION_COUNT
        and len(process_evidence) == PARTITION_COUNT
    ):
        try:
            process_pids = [process.pid for process in worker_processes]
            if (
                any(type(pid) is not int or pid <= 0 for pid in process_pids)
                or len(set(process_pids)) != PARTITION_COUNT
            ):
                raise PartitionError("worker Popen identities are missing or duplicated")
            validated: list[dict[str, Any]] = []
            for index, (process, process_state) in enumerate(
                zip(worker_processes, process_evidence, strict=True)
            ):
                if process_state["pid"] != process.pid or not process_state["waited"]:
                    raise PartitionError(f"worker-{index} process was not identified and reaped")
                if process_state["returnCode"] != 0:
                    raise PartitionError(f"worker-{index} process exited nonzero")
                _validate_worker_owner(root, index, process, root_info)
                worker_dir = root / f"worker-{index}"
                result_path = worker_dir / "result.json"
                if not result_path.is_file():
                    raise PartitionError(f"worker-{index} did not write a result record")
                result = json.loads(result_path.read_text(encoding="utf-8"))
                validated.append(
                    _validate_worker_result(
                        result,
                        worker_index=index,
                        process_pid=process.pid,
                        task_id=task_id,
                        root_info=root_info,
                        manifest=manifest,
                        worker_dir=worker_dir,
                    )
                )
            actual_lists = [proof["nodeIds"] for proof in validated]
            intersection = sorted(set(actual_lists[0]) & set(actual_lists[1]))
            actual_union = [nodeid for part in actual_lists for nodeid in part]
            if intersection:
                raise PartitionError("worker execution evidence overlaps")
            if set(actual_union) != set(manifest["nodeIds"]) or len(actual_union) != len(
                manifest["nodeIds"]
            ):
                raise PartitionError(
                    "worker execution evidence is not an exact parent collection union"
                )
            summary["actualNodeIds"] = list(manifest["nodeIds"])
            summary["partitionIntersection"] = intersection
            summary["workers"] = [
                {
                    "workerIndex": index,
                    "pid": process.pid,
                    "processReturnCode": process_state["returnCode"],
                    "processWaited": process_state["waited"],
                    "status": "passed",
                    "pytestExitCode": 0,
                    "actualNodeIds": proof["nodeIds"],
                    "junit": proof["junit"],
                }
                for index, (process, process_state, proof) in enumerate(
                    zip(worker_processes, process_evidence, validated, strict=True)
                )
            ]
            summary["status"] = "passed"
        except (OSError, json.JSONDecodeError, PartitionError, TypeError) as error:
            summary["error"] = str(error)
    _atomic_json(root / "scheduler-result.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if signal_number == signal.SIGINT:
        return 130
    if signal_number == signal.SIGTERM:
        return 143
    return 0 if summary["status"] == "passed" else 1


def main(argv: Sequence[str] | None = None) -> int:
    provided = list(sys.argv[1:] if argv is None else argv)
    if provided and provided[0].startswith(INTERNAL_PREFIX):
        return _internal_worker(provided)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument(
        "--allowed-parent",
        type=Path,
        default=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())),
    )
    parser.add_argument(
        "--task-id", default=os.environ.get("RWB_DELIVERY_TASK_ID", "local-ci-validation")
    )
    parser.add_argument("selection", nargs=argparse.REMAINDER)
    options = parser.parse_args(provided)
    selection = list(options.selection)
    if selection and selection[0] == "--":
        selection.pop(0)
    return run_suite(
        selection, options.task_root, options.allowed_parent, Path.cwd(), options.task_id
    )


if __name__ == "__main__":
    raise SystemExit(main())
