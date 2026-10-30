"""Path-identity and data-minimization contracts for CI evidence staging."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from scripts import run_ci_pytest_partitions as partitions
from scripts import stage_ci_pytest_evidence as staging

CANARY = "BUSINESS_BODY_CANARY_DO_NOT_STAGE"
SECRET_CANARY = "sk-TEST_SECRET_CANARY_DO_NOT_STAGE_12345"


def _write_worker(root: Path, index: int, nodeids: list[str], plan_sha: str) -> None:
    worker = root / f"worker-{index}"
    worker.mkdir(mode=0o700)
    (worker / "pytest.log").write_text(
        f"raw worker log {CANARY} {SECRET_CANARY}\n", encoding="utf-8"
    )
    cases = "".join(
        f'<testcase name="case-{offset}"><properties>'
        f'<property name="rwb_nodeid" value="{nodeid}" />'
        f"</properties><system-out>{CANARY} {SECRET_CANARY}</system-out></testcase>"
        for offset, nodeid in enumerate(nodeids)
    )
    (worker / "junit.xml").write_text(
        f'<testsuite tests="{len(nodeids)}">{cases}</testsuite>', encoding="utf-8"
    )


def _write_runner_root(runner_temp: Path, scope: str = "research-web") -> Path:
    root = runner_temp / f"rwb-ci-pytest-{scope}"
    root.mkdir(mode=0o700)
    info = root.stat()
    task_id = f"fixture-{scope}"
    (root / partitions.ROOT_MARKER).write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "taskId": task_id,
                "uid": os.getuid(),
                "pid": os.getpid(),
                "device": info.st_dev,
                "inode": info.st_ino,
                "argv": ["fixture"],
                "createdAtNs": 1,
            }
        ),
        encoding="utf-8",
    )
    nodeids = [
        "tests/research_web/test_fixture.py::test_one",
        "tests/research_web/test_fixture.py::test_two",
    ]
    selection = ["tests/research_web/test_fixture.py", "--confcutdir=tests/research_web", "-q"]
    split = partitions.split_nodeids(nodeids)
    plan_sha = partitions._plan_sha256(task_id, selection, nodeids, split)
    root_info = root.stat()
    (root / "partitions.json").write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "taskId": task_id,
                "selection": selection,
                "nodeIds": nodeids,
                "partitions": split,
                "planSha256": plan_sha,
            }
        ),
        encoding="utf-8",
    )
    scheduler = root / "scheduler"
    scheduler.mkdir(mode=0o700)
    (scheduler / "collect.log").write_text(
        f"raw collection log {CANARY} {SECRET_CANARY}\n", encoding="utf-8"
    )
    for index, assigned in enumerate(split):
        _write_worker(root, index, assigned, plan_sha)
        worker = root / f"worker-{index}"
        junit = worker / "junit.xml"
        junit_bytes = junit.read_bytes()
        (worker / "result.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 3,
                    "taskId": task_id,
                    "workerIndex": index,
                    "pid": 31000 + index,
                    "uid": os.getuid(),
                    "rootDevice": root_info.st_dev,
                    "rootInode": root_info.st_ino,
                    "planSha256": plan_sha,
                    "expectedNodeIds": nodeids,
                    "assignedNodeIds": assigned,
                    "execution": [
                        {
                            "nodeId": nodeid,
                            "phases": [
                                {"phase": "setup", "outcome": "passed"},
                                {"phase": "call", "outcome": "passed"},
                                {"phase": "teardown", "outcome": "passed"},
                            ],
                        }
                        for nodeid in assigned
                    ],
                    "collectionFailures": [],
                    "junit": {
                        "sha256": hashlib.sha256(junit_bytes).hexdigest(),
                        "nodeIds": assigned,
                        "tests": len(assigned),
                        "failures": 0,
                        "errors": 0,
                        "skipped": 0,
                    },
                    "pytestExitCode": 0,
                    "status": "passed",
                    "error": None,
                    "failureTaxonomy": None,
                }
            ),
            encoding="utf-8",
        )
        (root / f"worker-{index}.owner.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "name": f"worker-{index}",
                    "pid": 31000 + index,
                    "uid": os.getuid(),
                    "device": root_info.st_dev,
                    "inode": root_info.st_ino,
                    "argv": ["fixture", str(index)],
                    "registeredAtNs": 1,
                }
            ),
            encoding="utf-8",
        )
    (root / "scheduler-result.json").write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "taskId": task_id,
                "selection": selection,
                "status": "passed",
                "partitionSha256": plan_sha,
                "expectedNodeIds": nodeids,
                "actualNodeIds": nodeids,
                "partitionIntersection": [],
                "workerProcesses": [
                    {"pid": 31000 + index, "returnCode": 0, "waited": True} for index in range(2)
                ],
                "workers": [
                    {
                        "workerIndex": index,
                        "pid": 31000 + index,
                        "processReturnCode": 0,
                        "processWaited": True,
                        "status": "passed",
                        "pytestExitCode": 0,
                        "actualNodeIds": assigned,
                        "junit": {
                            "sha256": hashlib.sha256(
                                (root / f"worker-{index}" / "junit.xml").read_bytes()
                            ).hexdigest(),
                            "tests": len(assigned),
                            "failures": 0,
                            "errors": 0,
                            "skipped": 0,
                            "nodeIds": assigned,
                        },
                    }
                    for index, assigned in enumerate(split)
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def _stage(tmp_path: Path, root: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    result = staging.stage_evidence(root.parent, workspace, max_bytes=2_000_000)
    return Path(result["outputPath"])


def _read_result(root: Path, index: int = 0) -> dict[str, Any]:
    path = root / f"worker-{index}" / "result.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_result(root: Path, result: dict[str, Any], index: int = 0) -> None:
    (root / f"worker-{index}" / "result.json").write_text(json.dumps(result), encoding="utf-8")


def _write_progress(root: Path, index: int = 0) -> dict[str, Any]:
    manifest = json.loads((root / "partitions.json").read_text(encoding="utf-8"))
    assigned = manifest["partitions"][index]
    progress = {
        "schemaVersion": 1,
        "phase": "setup",
        "workerIndex": index,
        "planSha256": manifest["planSha256"],
        "nodeId": assigned[0],
        "outcome": "passed",
        "elapsedSeconds": 17,
        "counters": {
            "collected": len(manifest["nodeIds"]),
            "selected": len(assigned),
            "started": 1,
            "completed": 0,
            "passed": 1,
            "skipped": 0,
            "failed": 0,
        },
    }
    (root / f"worker-{index}" / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
    return progress


def _write_scheduler_junit_summary(
    root: Path, index: int, junit_bytes: bytes, counts: dict[str, int]
) -> None:
    path = root / "scheduler-result.json"
    scheduler = json.loads(path.read_text(encoding="utf-8"))
    scheduler["workers"][index]["junit"].update(
        {**counts, "sha256": hashlib.sha256(junit_bytes).hexdigest()}
    )
    path.write_text(json.dumps(scheduler), encoding="utf-8")


def _mark_worker_failed(root: Path, failure_body: str, error_class: str) -> None:
    result = _read_result(root)
    result["status"] = "failed"
    result["pytestExitCode"] = 1
    result["error"] = f"{error_class}: {failure_body}"
    result["failureTaxonomy"] = {
        "phase": "call",
        "errorClass": error_class,
        "errorCode": "pytest_call_failed",
    }
    result["execution"][0]["phases"][1]["outcome"] = "failed"
    junit_path = root / "worker-0" / "junit.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace(
            "</testcase>", f'<failure message="{failure_body}" />\n</testcase>', 1
        ),
        encoding="utf-8",
    )
    junit_bytes = junit_path.read_bytes()
    result["junit"].update({"sha256": hashlib.sha256(junit_bytes).hexdigest(), "failures": 1})
    _write_result(root, result)
    _write_scheduler_junit_summary(
        root, 0, junit_bytes, {"tests": 1, "failures": 1, "errors": 0, "skipped": 0}
    )
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler["status"] = "failed"
    scheduler["actualNodeIds"] = []
    scheduler["workers"][0].update({"status": "failed", "pytestExitCode": 1, "actualNodeIds": []})
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")


def test_rejects_passed_result_with_failed_phase(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    result = _read_result(root)
    execution = result["execution"]
    execution[0]["phases"][1]["outcome"] = "failed"
    _write_result(root, result)

    with pytest.raises(staging.StagingError):
        _stage(tmp_path, root)

    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()


def test_rejects_passed_result_with_junit_failure(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    junit_path = root / "worker-0" / "junit.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace(
            "</testcase>", "<failure>fixture failure</failure></testcase>", 1
        ),
        encoding="utf-8",
    )
    result = _read_result(root)
    junit_bytes = junit_path.read_bytes()
    result["junit"].update(
        {
            "sha256": hashlib.sha256(junit_bytes).hexdigest(),
            "failures": 1,
        }
    )
    _write_scheduler_junit_summary(
        root, 0, junit_bytes, {"tests": 1, "failures": 1, "errors": 0, "skipped": 0}
    )
    _write_result(root, result)

    with pytest.raises(staging.StagingError):
        _stage(tmp_path, root)

    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()


def test_passed_xfail_remains_a_visible_skip(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    junit_path = root / "worker-0" / "junit.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace(
            "</testcase>", '<skipped message="xfail" /></testcase>', 1
        ),
        encoding="utf-8",
    )
    result = _read_result(root)
    result["execution"][0]["phases"][1]["outcome"] = "skipped"
    junit_bytes = junit_path.read_bytes()
    result["junit"].update(
        {
            "sha256": hashlib.sha256(junit_bytes).hexdigest(),
            "skipped": 1,
        }
    )
    _write_scheduler_junit_summary(
        root, 0, junit_bytes, {"tests": 1, "failures": 0, "errors": 0, "skipped": 1}
    )
    _write_result(root, result)

    output = _stage(tmp_path, root)

    skipped = ET.parse(output / "research-web" / "worker-0" / "junit.xml").getroot()
    assert len(skipped.findall(".//testcase/skipped")) == 1


def test_stages_only_sanitized_whitelisted_test_evidence(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)

    output = _stage(tmp_path, root)
    staged = [path for path in output.rglob("*") if path.is_file()]
    staged_bytes = b"".join(path.read_bytes() for path in staged)

    assert output.is_dir()
    assert "research-web/scheduler/collect.log" in {
        path.relative_to(output).as_posix() for path in staged
    }
    assert not any(name.endswith("worker.log") for name in (path.name for path in staged))
    assert CANARY.encode() not in staged_bytes
    assert SECRET_CANARY.encode() not in staged_bytes
    safe_junit = ET.parse(output / "research-web" / "worker-0" / "junit.xml").getroot()
    assert [item.attrib["value"] for item in safe_junit.findall(".//property")] == [
        "tests/research_web/test_fixture.py::test_one"
    ]


def test_failed_worker_staging_keeps_safe_taxonomy_without_failure_body(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    failure_body = "PRIVATE_FAILURE_BODY_CANARY"
    _mark_worker_failed(root, failure_body, "AssertionError")

    output = _stage(tmp_path, root)

    staged = [path for path in output.rglob("*") if path.is_file()]
    staged_bytes = b"".join(path.read_bytes() for path in staged)
    safe_worker = json.loads(
        (output / "research-web" / "worker-0" / "result.json").read_text(encoding="utf-8")
    )
    safe_log = (output / "research-web" / "worker-0" / "pytest.log").read_text(encoding="utf-8")

    assert safe_worker["failureTaxonomy"] == {
        "phase": "call",
        "errorClass": "AssertionError",
        "errorCode": "pytest_call_failed",
    }
    assert "failure phase: call" in safe_log
    assert "failure code: pytest_call_failed" in safe_log
    assert failure_body.encode() not in staged_bytes


def test_missing_final_stages_only_closed_safe_progress_diagnostic(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    expected = _write_progress(root)
    (root / "worker-0" / "result.json").unlink()
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler.update(status="failed", actualNodeIds=[], workers=[])
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")

    output = _stage(tmp_path, root)
    progress = json.loads(
        (output / "research-web" / "worker-0" / "progress.json").read_text(encoding="utf-8")
    )
    safe_result = json.loads(
        (output / "research-web" / "worker-0" / "result.json").read_text(encoding="utf-8")
    )

    assert progress == expected
    assert safe_result["status"] == "missing"
    assert safe_result["progress"] == expected


def test_missing_final_accepts_bounded_startup_lower_bound(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    manifest = json.loads((root / "partitions.json").read_text(encoding="utf-8"))
    startup = {
        "schemaVersion": 1,
        "phase": "startup",
        "workerIndex": 0,
        "planSha256": manifest["planSha256"],
        "nodeId": None,
        "outcome": None,
        "elapsedSeconds": 0,
        "counters": {name: 0 for name in staging.WORKER_PROGRESS_COUNTERS},
    }
    (root / "worker-0" / "progress.json").write_text(json.dumps(startup), encoding="utf-8")
    (root / "worker-0" / "result.json").unlink()
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler.update(status="failed", actualNodeIds=[], workers=[])
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")

    output = _stage(tmp_path, root)
    safe_result = json.loads(
        (output / "research-web" / "worker-0" / "result.json").read_text(encoding="utf-8")
    )
    assert safe_result["progress"] == startup


@pytest.mark.parametrize(
    "tamper",
    [
        "unknown-field",
        "elapsed-bool",
        "elapsed-float",
        "elapsed-large",
        "counter-bool",
        "counter-large",
        "foreign-node",
        "wrong-plan",
    ],
)
def test_progress_diagnostic_rejects_unknown_or_private_fields(tmp_path: Path, tamper: str) -> None:
    assert staging.WORKER_PROGRESS_FIELDS == partitions.WORKER_PROGRESS_FIELDS
    assert staging.WORKER_PROGRESS_PHASES == partitions.WORKER_PROGRESS_PHASES
    assert staging.WORKER_PROGRESS_OUTCOMES == partitions.WORKER_PROGRESS_OUTCOMES
    assert staging.WORKER_PROGRESS_COUNTERS == partitions.WORKER_PROGRESS_COUNTERS
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    progress = _write_progress(root)
    (root / "worker-0" / "result.json").unlink()
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler.update(status="failed", actualNodeIds=[], workers=[])
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")
    if tamper == "unknown-field":
        progress["stdout"] = "PRIVATE_PROGRESS_BODY"
    elif tamper == "elapsed-bool":
        progress["elapsedSeconds"] = True
    elif tamper == "elapsed-float":
        progress["elapsedSeconds"] = 1.5
    elif tamper == "elapsed-large":
        progress["elapsedSeconds"] = staging.MAX_PROGRESS_ELAPSED_SECONDS + 1
    elif tamper == "counter-bool":
        progress["counters"]["failed"] = True
    elif tamper == "counter-large":
        progress["counters"]["started"] = 1_000_000
    elif tamper == "foreign-node":
        progress["nodeId"] = "/private/user/path::test_secret"
    else:
        progress["planSha256"] = "f" * 64
    (root / "worker-0" / "progress.json").write_text(json.dumps(progress), encoding="utf-8")

    with pytest.raises(staging.StagingError, match="progress|execution"):
        _stage(tmp_path, root)


def test_valid_final_ignores_even_malformed_optional_progress(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    (root / "worker-0" / "progress.json").write_text(
        json.dumps({"stdout": "PRIVATE_PROGRESS_BODY", "unknown": True}), encoding="utf-8"
    )

    output = _stage(tmp_path, root)
    safe_result = json.loads(
        (output / "research-web" / "worker-0" / "result.json").read_text(encoding="utf-8")
    )

    assert safe_result["status"] == "passed"
    assert safe_result["progress"] is None
    assert not (output / "research-web" / "worker-0" / "progress.json").exists()


def test_valid_final_does_not_open_unsafe_optional_progress(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    outside = tmp_path / "outside-progress.json"
    outside.write_text('"PRIVATE_PROGRESS_BODY"', encoding="utf-8")
    (root / "worker-0" / "progress.json").symlink_to(outside)

    output = _stage(tmp_path, root)
    staged_bytes = b"".join(path.read_bytes() for path in output.rglob("*") if path.is_file())

    assert b"PRIVATE_PROGRESS_BODY" not in staged_bytes
    assert not (output / "research-web" / "worker-0" / "progress.json").exists()


@pytest.mark.parametrize("failed_subtest", [False, True], ids=["pass-skip", "failed"])
def test_real_pytest9_subtests_keep_final_authoritative_for_staging(
    tmp_path: Path, failed_subtest: bool
) -> None:
    fixture_root = tmp_path / "fixture-project"
    test_root = fixture_root / "tests" / "research_web"
    test_root.mkdir(parents=True)
    failure = (
        "self.assertEqual(value, 99)" if failed_subtest else "self.assertGreaterEqual(value, 0)"
    )
    test_root.joinpath("test_fixture.py").write_text(
        f"""
import unittest

class TestSubtests(unittest.TestCase):
    def test_many(self):
        for value in range(9):
            with self.subTest(value=value):
                if value == 7 and not {failed_subtest!r}:
                    self.skipTest('subtest skip')
                {failure}

    def test_other(self):
        self.assertTrue(True)
""",
        encoding="utf-8",
    )
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = runner_temp / "rwb-ci-pytest-research-web"
    command = [
        sys.executable,
        "-P",
        str(Path(partitions.__file__).resolve()),
        "--task-root",
        str(root),
        "--allowed-parent",
        str(runner_temp),
        "--task-id",
        "fixture-research-web",
        "--",
        "tests/research_web/test_fixture.py",
        "--confcutdir=tests/research_web",
        "-q",
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = partitions._pythonpath(
        fixture_root, environment.get("PYTHONPATH", "")
    )
    completed = subprocess.run(
        command,
        cwd=fixture_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    summary = json.loads((root / "scheduler-result.json").read_text(encoding="utf-8"))
    if failed_subtest:
        assert completed.returncode != 0
        assert summary["status"] == "failed"
    else:
        assert completed.returncode == 0
        assert summary["status"] == "passed"

    output = _stage(tmp_path, root)
    safe_summary = json.loads(
        (output / "research-web" / "scheduler-result.json").read_text(encoding="utf-8")
    )
    assert safe_summary["status"] == summary["status"]


def test_rejects_identifier_shaped_error_class_in_raw_schema_v3_result(tmp_path: Path) -> None:
    assert staging.SAFE_EXCEPTION_CLASSES == partitions.SAFE_EXCEPTION_CLASSES
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    _mark_worker_failed(root, "private failure body", "PRIVATE_FAILURE_BODY_CANARY")

    with pytest.raises(staging.StagingError, match="failure taxonomy is invalid"):
        _stage(tmp_path, root)

    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()


def test_real_worker_private_exception_name_never_reaches_staged_artifact(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture-project"
    test_root = fixture_root / "tests" / "research_web"
    test_root.mkdir(parents=True)
    test_root.joinpath("test_fixture.py").write_text(
        """
class PRIVATE_FAILURE_BODY_CANARY(Exception):
    pass

def test_private_failure():
    raise PRIVATE_FAILURE_BODY_CANARY()

def test_passes():
    assert True
""",
        encoding="utf-8",
    )
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = runner_temp / "rwb-ci-pytest-research-web"
    command = [
        sys.executable,
        "-P",
        str(Path(partitions.__file__).resolve()),
        "--task-root",
        str(root),
        "--allowed-parent",
        str(runner_temp),
        "--task-id",
        "fixture-research-web",
        "--",
        "tests/research_web/test_fixture.py",
        "--confcutdir=tests/research_web",
        "-q",
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = partitions._pythonpath(
        fixture_root, environment.get("PYTHONPATH", "")
    )

    completed = subprocess.run(
        command,
        cwd=fixture_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    failed_results = [
        _read_result(root, index)
        for index in range(2)
        if _read_result(root, index)["status"] == "failed"
    ]
    assert len(failed_results) == 1

    output = _stage(tmp_path, root)
    staged_bytes = b"".join(path.read_bytes() for path in output.rglob("*") if path.is_file())

    assert b"PRIVATE_FAILURE_BODY_CANARY" not in staged_bytes
    assert failed_results[0]["failureTaxonomy"]["errorClass"] is None


def test_symlink_source_cannot_read_or_stage_external_sentinel(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    outside = tmp_path / "outside.txt"
    outside.write_text("EXTERNAL_SENTINEL", encoding="utf-8")
    link = root / "worker-0" / "pytest.log"
    link.unlink()
    link.symlink_to(outside)

    with pytest.raises(staging.StagingError):
        _stage(tmp_path, root)

    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()
    assert outside.read_text(encoding="utf-8") == "EXTERNAL_SENTINEL"


def test_hardlinked_source_is_rejected_without_staging_sentinel(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    outside = tmp_path / "outside.txt"
    outside.write_text("HARDLINK_SENTINEL", encoding="utf-8")
    log = root / "worker-0" / "pytest.log"
    log.unlink()
    os.link(outside, log)

    with pytest.raises(staging.StagingError):
        _stage(tmp_path, root)

    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()
    assert outside.read_text(encoding="utf-8") == "HARDLINK_SENTINEL"


def test_root_symlink_is_rejected_without_following_external_directory(tmp_path: Path) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "scheduler-result.json").write_text("ROOT_SENTINEL", encoding="utf-8")
    (runner_temp / "rwb-ci-pytest-research-web").symlink_to(outside, target_is_directory=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(staging.StagingError):
        staging.stage_evidence(runner_temp, workspace, max_bytes=2_000_000)

    assert not (workspace / "artifacts" / "research-web-checks").exists()
    assert (outside / "scheduler-result.json").read_text(encoding="utf-8") == "ROOT_SENTINEL"


def test_cli_returns_nonzero_when_an_allowlisted_input_is_a_symlink(
    tmp_path: Path,
) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    outside = tmp_path / "outside.txt"
    outside.write_text("CLI_SENTINEL", encoding="utf-8")
    log = root / "worker-0" / "pytest.log"
    log.unlink()
    log.symlink_to(outside)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = staging.main(
            [
                "--runner-temp",
                str(runner_temp),
                "--workspace",
                str(workspace),
                "--max-bytes",
                "2000000",
            ]
        )

    assert exit_code == 1
    assert json.loads(output.getvalue())["staged"] is False
    assert not (workspace / "artifacts" / "research-web-checks").exists()
    assert outside.read_text(encoding="utf-8") == "CLI_SENTINEL"


def test_replaced_parent_directory_is_detected_before_staging(tmp_path: Path, monkeypatch) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "pytest.log").write_text("REPLACEMENT_SENTINEL", encoding="utf-8")
    original_open = staging.os.open
    root_fd: int | None = None
    replaced = False

    def replace_worker_directory(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal root_fd, replaced
        fd = original_open(path, flags, mode, dir_fd=dir_fd)
        if path == root.name:
            root_fd = fd
        elif path == "worker-0" and dir_fd == root_fd and not replaced:
            os.rename("worker-0", "worker-0-original", src_dir_fd=root_fd, dst_dir_fd=root_fd)
            os.symlink(outside, "worker-0", target_is_directory=True, dir_fd=root_fd)
            replaced = True
        return fd

    monkeypatch.setattr(staging.os, "open", replace_worker_directory)
    with pytest.raises(staging.StagingError):
        _stage(tmp_path, root)

    assert replaced
    assert not (tmp_path / "workspace" / "artifacts" / "research-web-checks").exists()
    assert (outside / "pytest.log").read_text(encoding="utf-8") == "REPLACEMENT_SENTINEL"
