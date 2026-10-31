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
                "schemaVersion": 3,
                "taskId": task_id,
                "selection": selection,
                "suiteNodeIds": nodeids,
                "jobShardIndex": 0,
                "jobShardCount": 1,
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


def test_missing_final_never_opens_a_live_pytest_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    _write_progress(root)
    (root / "worker-0" / "result.json").unlink()
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler.update(status="failed", actualNodeIds=[], workers=[])
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")
    original = staging._read_relative

    def reject_live_log(*args, **kwargs):
        relative = args[1]
        if relative.endswith("pytest.log") or relative == "worker-0/junit.xml":
            raise AssertionError("live pytest/JUnit output must not be opened without final")
        return original(*args, **kwargs)

    monkeypatch.setattr(staging, "_read_relative", reject_live_log)

    output = _stage(tmp_path, root)

    assert (output / "research-web" / "worker-0" / "progress.json").is_file()


def test_changed_progress_snapshot_is_rejected_instead_of_staged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = _write_runner_root(runner_temp)
    _write_progress(root)
    (root / "worker-0" / "result.json").unlink()
    scheduler_path = root / "scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler.update(status="failed", actualNodeIds=[], workers=[])
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")
    original = staging._read_relative
    changed = False

    def change_progress_after_read(*args, **kwargs):
        nonlocal changed
        loaded = original(*args, **kwargs)
        if args[1] == "worker-0/progress.json" and not changed:
            changed = True
            progress_path = root / "worker-0" / "progress.json"
            progress_path.write_text(
                progress_path.read_text(encoding="utf-8") + " ", encoding="utf-8"
            )
        return loaded

    monkeypatch.setattr(staging, "_read_relative", change_progress_after_read)

    with pytest.raises(staging.StagingError, match="changed|identity"):
        _stage(tmp_path, root)

    assert changed


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
    link = root / "worker-0" / "junit.xml"
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
    junit = root / "worker-0" / "junit.xml"
    junit.unlink()
    os.link(outside, junit)

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
    junit = root / "worker-0" / "junit.xml"
    junit.unlink()
    junit.symlink_to(outside)
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


def _write_safe_shard_artifact(
    root: Path,
    shard_index: int,
    *,
    artifact_slot: int | None = None,
    scopes: tuple[str, ...] = ("research-web",),
    scope_shard_indices: dict[str, int] | None = None,
    selection_suffixes: dict[str, str] | None = None,
) -> Path:
    slot = shard_index if artifact_slot is None else artifact_slot
    artifact = root / f"shard-{slot}"
    artifact.mkdir()
    selected_indices = scope_shard_indices or {}
    suffixes = selection_suffixes or {}
    for scope_name in scopes:
        actual_shard = selected_indices.get(scope_name, shard_index)
        test_root = "research_web" if scope_name == "research-web" else "unit"
        scope = artifact / scope_name
        scope.mkdir()
        suite = [f"tests/{test_root}/test_fixture.py::test_{index}" for index in range(8)]
        nodeids = suite[actual_shard::2]
        worker_partitions = [nodeids[index::2] for index in range(2)]
        task_id = f"github-123-1-shard-{actual_shard}-{scope_name}"
        suffix = suffixes.get(scope_name, "")
        selection = [
            f"tests/{test_root}/test_fixture{suffix}.py",
            f"--confcutdir=tests/{test_root}",
            "-q",
        ]
        plan_sha256 = partitions._plan_sha256(
            task_id,
            selection,
            nodeids,
            worker_partitions,
            suite_nodeids=suite,
            job_shard_index=actual_shard,
            job_shard_count=2,
        )
        manifest = {
            "schemaVersion": 3,
            "taskId": task_id,
            "selection": selection,
            "suiteNodeIds": suite,
            "jobShardIndex": actual_shard,
            "jobShardCount": 2,
            "nodeIds": nodeids,
            "partitions": worker_partitions,
            "planSha256": plan_sha256,
        }
        (scope / "partitions.json").write_text(json.dumps(manifest), encoding="utf-8")
        workers = []
        for worker_index, assigned in enumerate(worker_partitions):
            worker = scope / f"worker-{worker_index}"
            worker.mkdir()
            cases = "".join(
                '<testcase><properties><property name="rwb_nodeid" '
                f'value="{nodeid}" /></properties></testcase>'
                for nodeid in assigned
            )
            junit = f'<testsuite tests="{len(assigned)}">{cases}</testsuite>'.encode()
            (worker / "junit.xml").write_bytes(junit)
            safe_junit = {
                "nodeIds": assigned,
                "tests": len(assigned),
                "failures": 0,
                "errors": 0,
                "skipped": 0,
            }
            result = {
                "workerIndex": worker_index,
                "pid": 40000 + actual_shard * 10 + worker_index,
                "status": "passed",
                "pytestExitCode": 0,
                "assignedNodeCount": len(assigned),
                "executionNodeIds": assigned,
                "junit": safe_junit,
                "junitSha256": hashlib.sha256(junit).hexdigest(),
                "artifactJunitSha256": hashlib.sha256(junit).hexdigest(),
                "failureTaxonomy": None,
                "progress": None,
            }
            (worker / "result.json").write_text(json.dumps(result), encoding="utf-8")
            workers.append(result)
        (scope / "scheduler-result.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "taskId": task_id,
                    "scope": scope_name,
                    "status": "passed",
                    "planSha256": manifest["planSha256"],
                    "expectedNodeCount": len(nodeids),
                    "actualNodeCount": len(nodeids),
                    "partitionIntersectionCount": 0,
                    "workers": workers,
                }
            ),
            encoding="utf-8",
        )
    files = sorted(
        str(path.relative_to(artifact)) for path in artifact.rglob("*") if path.is_file()
    )
    content_bytes = sum(path.stat().st_size for path in artifact.rglob("*") if path.is_file())
    (artifact / "status.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "status": "staged",
                "scopes": list(scopes),
                "files": sorted([*files, "status.json"]),
                "contentBytes": content_bytes,
            }
        ),
        encoding="utf-8",
    )
    return artifact


@pytest.mark.parametrize("tamper", ["missing-final", "missing-junit", "overlap"])
def test_shard_gate_rejects_missing_worker_evidence_and_bad_union(
    tmp_path: Path, tamper: str
) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    if tamper == "missing-final":
        (shards[1] / "research-web/worker-1/result.json").unlink()
    elif tamper == "missing-junit":
        (shards[1] / "research-web/worker-1/junit.xml").unlink()
    else:
        manifest_path = shards[1] / "research-web/partitions.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["nodeIds"] = json.loads(
            (shards[0] / "research-web/partitions.json").read_text(encoding="utf-8")
        )["nodeIds"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(staging.StagingError):
        staging.verify_shard_evidence(shards, scopes=("research-web",))


def test_shard_gate_accepts_only_exact_passed_union_with_owned_junit(tmp_path: Path) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]

    result = staging.verify_shard_evidence(shards, scopes=("research-web",))

    assert result == {
        "status": "passed",
        "jobShardCount": 2,
        "scopes": {"research-web": {"suiteNodeCount": 8, "executedNodeCount": 8}},
    }


def test_shard_gate_rejects_symlink_artifact_root(tmp_path: Path) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    alias = tmp_path / "shard-root-alias"
    alias.symlink_to(shards[0], target_is_directory=True)

    with pytest.raises(staging.StagingError):
        staging.verify_shard_evidence([alias, shards[1]], scopes=("research-web",))


@pytest.mark.parametrize("target", ["file", "intermediate"])
def test_shard_gate_rejects_symlink_artifact_entries(tmp_path: Path, target: str) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    if target == "file":
        junit = shards[0] / "research-web/worker-0/junit.xml"
        outside = tmp_path / "outside-junit.xml"
        outside.write_bytes(junit.read_bytes())
        junit.unlink()
        junit.symlink_to(outside)
    else:
        worker = shards[0] / "research-web/worker-0"
        moved = shards[0] / "research-web/worker-0-real"
        worker.rename(moved)
        worker.symlink_to(moved, target_is_directory=True)

    with pytest.raises(staging.StagingError):
        staging.verify_shard_evidence(shards, scopes=("research-web",))


def test_shard_gate_rejects_hardlinked_artifact_file(tmp_path: Path) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    junit = shards[0] / "research-web/worker-0/junit.xml"
    outside = tmp_path / "outside-junit.xml"
    outside.write_bytes(junit.read_bytes())
    junit.unlink()
    os.link(outside, junit)

    with pytest.raises(staging.StagingError):
        staging.verify_shard_evidence(shards, scopes=("research-web",))


@pytest.mark.parametrize("outcome", ["failure", "error"])
def test_shard_gate_rejects_coherent_failed_junit_claimed_as_pass(
    tmp_path: Path, outcome: str
) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    worker = shards[0] / "research-web/worker-0"
    junit_path = worker / "junit.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace(
            "</testcase>", f'<{outcome} type="fixture" /></testcase>', 1
        ),
        encoding="utf-8",
    )
    junit_bytes = junit_path.read_bytes()
    result_path = worker / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["junit"][f"{outcome}s"] = 1
    result["junitSha256"] = hashlib.sha256(junit_bytes).hexdigest()
    result["artifactJunitSha256"] = hashlib.sha256(junit_bytes).hexdigest()
    result_path.write_text(json.dumps(result), encoding="utf-8")
    scheduler_path = shards[0] / "research-web/scheduler-result.json"
    scheduler = json.loads(scheduler_path.read_text(encoding="utf-8"))
    scheduler["workers"][0] = result
    scheduler_path.write_text(json.dumps(scheduler), encoding="utf-8")

    with pytest.raises(staging.StagingError, match="final and JUnit"):
        staging.verify_shard_evidence(shards, scopes=("research-web",))


def test_shard_gate_rejects_artifact_file_swapped_during_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    original_open = staging.os.open
    swapped = False

    def swap_junit_before_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == "junit.xml" and not swapped:
            swapped = True
            os.rename(
                "junit.xml",
                "junit-original.xml",
                src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd,
            )
            replacement = original_open(
                "junit.xml",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=dir_fd,
            )
            try:
                os.write(replacement, b"<testsuite />")
            finally:
                os.close(replacement)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(staging.os, "open", swap_junit_before_open)

    with pytest.raises(staging.StagingError, match="changed while opening"):
        staging.verify_shard_evidence(shards, scopes=("research-web",))

    assert swapped


def test_shard_gate_rejects_artifact_file_over_size_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shards = [_write_safe_shard_artifact(tmp_path, index) for index in range(2)]
    junit = shards[0] / "research-web/worker-0/junit.xml"
    other_sizes = [
        path.stat().st_size
        for shard in shards
        for path in shard.rglob("*")
        if path.is_file() and path != junit
    ]
    limit = max(other_sizes) + 1
    junit.write_bytes(junit.read_bytes() + b" " * (limit + 1))
    monkeypatch.setattr(staging, "MAX_FILE_BYTES", limit)

    with pytest.raises(staging.StagingError, match="single-link owner file|size limit"):
        staging.verify_shard_evidence(shards, scopes=("research-web",))


def _write_production_shards(tmp_path: Path) -> list[Path]:
    return [
        _write_safe_shard_artifact(tmp_path, index, scopes=staging.SCOPES) for index in range(2)
    ]


def _run_shard_gate_cli(shards: list[Path]) -> tuple[int, dict[str, Any]]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = staging.main(["--verify-shards", str(shards[0]), str(shards[1])])
    return exit_code, json.loads(output.getvalue())


def test_shard_gate_cli_accepts_download_layout_with_both_production_scopes(
    tmp_path: Path,
) -> None:
    shards = _write_production_shards(tmp_path)

    exit_code, result = _run_shard_gate_cli(shards)

    assert exit_code == 0
    assert result == {
        "status": "passed",
        "jobShardCount": 2,
        "scopes": {
            "research-web": {"suiteNodeCount": 8, "executedNodeCount": 8},
            "unit": {"suiteNodeCount": 8, "executedNodeCount": 8},
        },
    }
    for shard in shards:
        assert (shard / "status.json").is_file()
        assert (shard / "research-web").is_dir()
        assert (shard / "unit").is_dir()


@pytest.mark.parametrize(
    "tamper",
    [
        "missing-shard-root",
        "missing-unit",
        "cross-scope-index",
        "missing-final",
        "missing-junit",
        "changed-junit",
        "different-selection",
        "duplicate-shard",
    ],
)
def test_shard_gate_cli_rejects_incomplete_or_mixed_download_artifacts(
    tmp_path: Path, tamper: str
) -> None:
    if tamper == "cross-scope-index":
        shards = [
            _write_safe_shard_artifact(
                tmp_path,
                index,
                scopes=staging.SCOPES,
                scope_shard_indices={"unit": 1 - index},
            )
            for index in range(2)
        ]
    elif tamper == "different-selection":
        shards = [
            _write_safe_shard_artifact(tmp_path, 0, scopes=staging.SCOPES),
            _write_safe_shard_artifact(
                tmp_path,
                1,
                scopes=staging.SCOPES,
                selection_suffixes={"unit": "_different"},
            ),
        ]
    elif tamper == "duplicate-shard":
        shards = [
            _write_safe_shard_artifact(tmp_path, 0, artifact_slot=slot, scopes=staging.SCOPES)
            for slot in range(2)
        ]
    else:
        shards = _write_production_shards(tmp_path)

    if tamper == "missing-shard-root":
        shards[1] = tmp_path / "missing-shard"
    elif tamper == "missing-unit":
        (shards[1] / "unit").rename(shards[1] / "unit-missing")
    elif tamper == "missing-final":
        (shards[1] / "unit/worker-1/result.json").unlink()
    elif tamper == "missing-junit":
        (shards[1] / "unit/worker-1/junit.xml").unlink()
    elif tamper == "changed-junit":
        junit = shards[1] / "unit/worker-1/junit.xml"
        junit.write_bytes(junit.read_bytes() + b" ")

    exit_code, result = _run_shard_gate_cli(shards)

    assert exit_code == 1
    assert result["status"] == "failed"
    assert result["staged"] is False
