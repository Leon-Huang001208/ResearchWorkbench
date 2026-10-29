"""Path-identity and data-minimization contracts for CI evidence staging."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

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
                    "schemaVersion": 2,
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
                    {"pid": 31000 + index, "returnCode": 0, "waited": True}
                    for index in range(2)
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


def _read_result(root: Path, index: int = 0) -> dict[str, object]:
    path = root / f"worker-{index}" / "result.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_result(root: Path, result: dict[str, object], index: int = 0) -> None:
    (root / f"worker-{index}" / "result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )


def _write_scheduler_junit_summary(
    root: Path, index: int, junit_bytes: bytes, counts: dict[str, int]
) -> None:
    path = root / "scheduler-result.json"
    scheduler = json.loads(path.read_text(encoding="utf-8"))
    scheduler["workers"][index]["junit"].update(
        {**counts, "sha256": hashlib.sha256(junit_bytes).hexdigest()}
    )
    path.write_text(json.dumps(scheduler), encoding="utf-8")


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
            "</testcase>", "<skipped message=\"xfail\" /></testcase>", 1
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
