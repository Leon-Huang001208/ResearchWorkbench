"""Contract checks for the stdlib two-process CI pytest scheduler."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts import run_ci_pytest_partitions as partitions


def test_safe_exception_class_rejects_identifier_shaped_failure_body() -> None:
    assert partitions._safe_exception_class("PRIVATE_FAILURE_BODY_CANARY") is None
    assert partitions._safe_exception_class(AssertionError()) == "AssertionError"
    assert partitions._safe_exception_class(partitions.PartitionError()) == "PartitionError"

    class PrivateFailureBodyCanary(Exception):
        pass

    assert partitions._safe_exception_class(PrivateFailureBodyCanary()) == "UnknownError"


def test_split_round_robins_nodeids_from_large_modules() -> None:
    nodeids = [f"tests/test_api.py::test_api[{index}]" for index in range(120)]
    nodeids += [f"tests/test_other.py::test_other[{index}]" for index in range(31)]

    first, second = partitions.split_nodeids(nodeids)

    assert len(first) == 76
    assert len(second) == 75
    assert set(first).isdisjoint(second)
    assert set(first) | set(second) == set(nodeids)
    assert first[0].startswith("tests/test_api.py::")
    assert second[0].startswith("tests/test_api.py::")


@pytest.mark.parametrize(
    "nodeids",
    [[], ["one::test"], ["same::test", "same::test"]],
    ids=["empty", "one-item", "duplicate"],
)
def test_split_rejects_non_partitionable_collection(nodeids: list[str]) -> None:
    with pytest.raises(partitions.PartitionError):
        partitions.split_nodeids(nodeids)


def test_manifest_requires_exact_collection_order_and_full_disjoint_union() -> None:
    nodeids = [f"tests/test_api.py::test_api[{index}]" for index in range(4)]
    selection = ["tests/test_api.py", "--confcutdir=tests"]
    split = partitions.split_nodeids(nodeids)
    manifest = {
        "schemaVersion": partitions.MANIFEST_SCHEMA_VERSION,
        "taskId": "unit-test-task",
        "selection": selection,
        "nodeIds": nodeids,
        "partitions": split,
        "planSha256": partitions._plan_sha256("unit-test-task", selection, nodeids, split),
    }

    assert (
        partitions.validate_partition_manifest(manifest, nodeids, selection, "unit-test-task")
        == nodeids
    )
    with pytest.raises(partitions.PartitionError, match="exactly match"):
        partitions.validate_partition_manifest(
            manifest, list(reversed(nodeids)), selection, "unit-test-task"
        )

    manifest["partitions"] = [[nodeids[0], nodeids[1]], [nodeids[1], nodeids[3]]]
    with pytest.raises(partitions.PartitionError, match="overlap"):
        partitions.validate_partition_manifest(manifest, nodeids, selection, "unit-test-task")

    manifest["partitions"] = [[nodeids[0]], [nodeids[3]]]
    with pytest.raises(partitions.PartitionError, match="do not cover"):
        partitions.validate_partition_manifest(manifest, nodeids, selection, "unit-test-task")


def test_junit_requires_exact_nodeid_cases_not_just_a_lower_bound(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        """<testsuite tests="2">
  <testcase classname="fixture" name="one">
    <properties><property name="rwb_nodeid" value="tests/test_fixture.py::test_one" /></properties>
  </testcase>
  <testcase classname="fixture" name="unexpected">
    <properties>
      <property name="rwb_nodeid" value="tests/test_fixture.py::test_extra" />
    </properties>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )

    with pytest.raises(partitions.PartitionError):
        partitions._parse_junit(
            report,
            ["tests/test_fixture.py::test_one", "tests/test_fixture.py::test_two"],
        )


@pytest.mark.parametrize(
    "mode",
    ["missing-property", "duplicate-nodeid", "extra-case"],
    ids=["missing-nodeid", "duplicate-nodeid", "extra-case"],
)
def test_junit_rejects_missing_duplicate_or_extra_nodeid_cases(tmp_path: Path, mode: str) -> None:
    report = tmp_path / "junit.xml"
    first = (
        '<testcase><properties><property name="rwb_nodeid" value="node-a" />'
        "</properties></testcase>"
    )
    second = (
        '<testcase><properties><property name="rwb_nodeid" value="node-a" />'
        "</properties></testcase>"
        if mode == "duplicate-nodeid"
        else (
            "<testcase />"
            if mode == "missing-property"
            else (
                '<testcase><properties><property name="rwb_nodeid" value="node-b" />'
                "</properties></testcase>"
            )
        )
    )
    extra = (
        '<testcase><properties><property name="rwb_nodeid" value="node-extra" />'
        "</properties></testcase>"
        if mode == "extra-case"
        else ""
    )
    report.write_text(f"<testsuite>{first}{second}{extra}</testsuite>", encoding="utf-8")

    with pytest.raises(partitions.PartitionError):
        partitions._parse_junit(report, ["node-a", "node-b"])


@pytest.mark.parametrize(
    "tamper",
    [
        "missing-schema",
        "wrong-schema",
        "wrong-worker",
        "wrong-pid",
        "wrong-plan",
        "wrong-exit",
        "missing-node",
        "duplicate-node",
        "unexpected-node",
        "wrong-junit",
        "missing-junit",
    ],
)
def test_scheduler_rejects_forged_worker_results(tmp_path: Path, tamper: str) -> None:
    fixture_root = tmp_path / "fixture-project"
    test_root = fixture_root / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_fixture.py").write_text(
        "def test_one(): pass\ndef test_two(): pass\n", encoding="utf-8"
    )
    allowed_parent = tmp_path / "temp"
    allowed_parent.mkdir()
    result_root = allowed_parent / "forged-results"
    driver = tmp_path / "fake_scheduler.py"
    driver.write_text(
        """
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts import run_ci_pytest_partitions as runner

class FakeProcess:
    sequence = 0
    def __init__(self, command, **kwargs):
        root_arg = next(arg for arg in command if arg.startswith('--rwb-internal-root='))
        mode_arg = next(arg for arg in command if arg.startswith('--rwb-internal-worker='))
        root = Path(root_arg.split('=', 1)[1])
        mode = mode_arg.split('=', 1)[1]
        self.index = 0 if mode == 'leader' else (1 if mode == 'child' else int(mode))
        self.args = command
        self.pid = os.getpid() + 10000 + self.index
        self.returncode = 0
        plan_path = root / 'partitions.json'
        if plan_path.exists():
            plan = json.loads(plan_path.read_text(encoding='utf-8'))
        else:
            nodeids = ['tests/test_fixture.py::test_one', 'tests/test_fixture.py::test_two']
            partitions = runner.split_nodeids(nodeids)
            plan = {
                'schemaVersion': 2,
                'taskId': 'forged-result-red',
                'selection': ['tests/test_fixture.py', '--confcutdir=tests', '-q'],
                'nodeIds': nodeids,
                'partitions': partitions,
                'planSha256': 'a' * 64,
            }
            plan_path.write_text(json.dumps(plan), encoding='utf-8')
        indices = range(2) if mode == 'leader' else [self.index]
        for index in indices:
            worker = root / f'worker-{index}'
            worker.mkdir(exist_ok=True)
            assigned = plan['partitions'][index]
            worker_pid = os.getpid() + 10000 + index
            cases = ''.join(
                f'<testcase classname="fixture" name="item-{position}">'
                f'<properties><property name="rwb_nodeid" value="{nodeid}" />'
                '</properties></testcase>'
                for position, nodeid in enumerate(assigned)
            )
            junit = f'<testsuite tests="{len(assigned)}">{cases}</testsuite>'
            junit_path = worker / 'junit.xml'
            if sys.argv[3] == 'wrong-junit' and index == 0:
                junit = junit.replace(assigned[0], 'tests/test_fixture.py::test_unexpected')
            if sys.argv[3] != 'missing-junit':
                junit_path.write_text(junit, encoding='utf-8')
            report = ET.fromstring(junit)
            report_nodeids = [prop.attrib['value'] for prop in report.findall('.//property')]
            result = {
                'schemaVersion': 3,
                'taskId': plan['taskId'],
                'workerIndex': index,
                'pid': worker_pid,
                'uid': os.getuid(),
                'rootDevice': root.stat().st_dev,
                'rootInode': root.stat().st_ino,
                'planSha256': plan['planSha256'],
                'expectedNodeIds': plan['nodeIds'],
                'assignedNodeIds': assigned,
                'execution': [
                    {
                        'nodeId': nodeid,
                        'phases': [
                            {'phase': 'setup', 'outcome': 'passed'},
                            {'phase': 'call', 'outcome': 'passed'},
                            {'phase': 'teardown', 'outcome': 'passed'},
                        ],
                    }
                    for nodeid in assigned
                ],
                'junit': {
                    'sha256': hashlib.sha256(junit.encode()).hexdigest(),
                    'nodeIds': report_nodeids,
                    'tests': len(report_nodeids),
                    'failures': 0,
                    'errors': 0,
                    'skipped': 0,
                },
                'pytestExitCode': 0,
                'status': 'passed',
                'failureTaxonomy': None,
            }
            if sys.argv[3] == 'missing-schema' and index == 0: result.pop('schemaVersion')
            if sys.argv[3] == 'wrong-schema' and index == 0: result['schemaVersion'] = 99
            if sys.argv[3] == 'wrong-worker' and index == 0: result['workerIndex'] = 1
            if sys.argv[3] == 'wrong-pid' and index == 0: result['pid'] += 1
            if sys.argv[3] == 'wrong-plan' and index == 0: result['planSha256'] = 'b' * 64
            if sys.argv[3] == 'wrong-exit' and index == 0: result['pytestExitCode'] = 4
            if sys.argv[3] == 'missing-node' and index == 0: result['execution'].pop()
            if sys.argv[3] == 'duplicate-node' and index == 0:
                result['execution'].append(result['execution'][0])
            if sys.argv[3] == 'unexpected-node' and index == 0:
                result['execution'].append({'nodeId': 'unexpected::test', 'phases': []})
            if sys.argv[3] == 'missing-junit' and index == 0: result.pop('junit')
            (worker / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    def poll(self): return 0
    def wait(self, timeout=None): return 0

runner.subprocess.Popen = FakeProcess
root = Path(sys.argv[1])
parent = Path(sys.argv[2])
code = runner.run_suite(
    ['tests/test_fixture.py', '--confcutdir=tests', '-q'],
    root,
    parent,
    Path.cwd(),
    'forged-result-red',
)
raise SystemExit(code)
""",
        encoding="utf-8",
    )
    command = [sys.executable, "-P", str(driver), str(result_root), str(allowed_parent), tamper]
    completed = subprocess.run(
        command,
        cwd=fixture_root,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True,
        text=True,
        check=False,
    )

    summary = json.loads((result_root / "scheduler-result.json").read_text(encoding="utf-8"))
    assert completed.returncode != 0
    assert summary["status"] == "failed"


@pytest.mark.parametrize(
    "selection",
    [
        ["/tmp/test_api.py"],
        ["tests/../outside.py"],
        ["--collect-only", "tests/test_api.py"],
        ["--confcutdir"],
    ],
    ids=["absolute", "escaped", "unsupported-option", "missing-confcutdir-path"],
)
def test_selection_rejects_unowned_or_unknown_inputs(tmp_path: Path, selection: list[str]) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_api.py").write_text("def test_example(): pass\n", encoding="utf-8")

    with pytest.raises(partitions.PartitionError):
        partitions.validate_selection(selection, tmp_path)


def test_task_root_is_fresh_owner_bound_and_inode_bound(tmp_path: Path) -> None:
    root = tmp_path / "task-results"
    created = partitions.create_task_root(root, tmp_path, "task-test")
    marker = partitions.validate_task_root(created, tmp_path)

    assert marker["taskId"] == "task-test"
    assert marker["uid"] == partitions.os.getuid()
    assert marker["device"] == created.stat().st_dev
    assert marker["inode"] == created.stat().st_ino
    with pytest.raises(partitions.PartitionError, match="already exists"):
        partitions.create_task_root(root, tmp_path, "task-test")


def test_internal_worker_rejects_repository_path_outside_its_working_directory(
    tmp_path: Path,
) -> None:
    argv = [
        f"{partitions.INTERNAL_PREFIX}worker=0",
        f"{partitions.INTERNAL_PREFIX}root={tmp_path / 'task-root'}",
        f"{partitions.INTERNAL_PREFIX}repo={tmp_path / 'other-repository'}",
        f"{partitions.INTERNAL_PREFIX}parent={tmp_path}",
        f"{partitions.INTERNAL_PREFIX}plan={'a' * 64}",
        "--",
        "tests/test_fixture.py",
    ]

    with pytest.raises(partitions.PartitionError, match="repository path"):
        partitions._internal_worker(argv)


def _run_fixture_suite(tmp_path: Path, source: str) -> tuple[int, Path]:
    fixture_root = tmp_path / "fixture-project"
    test_root = fixture_root / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_fixture.py").write_text(source, encoding="utf-8")
    allowed_parent = tmp_path / "temp"
    allowed_parent.mkdir()
    result_root = allowed_parent / "task-results"
    command = [
        sys.executable,
        "-P",
        str(Path(partitions.__file__).resolve()),
        "--task-root",
        str(result_root),
        "--allowed-parent",
        str(allowed_parent),
        "--task-id",
        "partition-test-task",
        "--",
        "tests/test_fixture.py",
        "--confcutdir=tests",
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
    return completed.returncode, result_root


def test_two_workers_execute_exact_partition_and_keep_skip_visible(tmp_path: Path) -> None:
    exit_code, root = _run_fixture_suite(
        tmp_path,
        """
import pytest

@pytest.mark.parametrize('value', [1, 2, 3, 4])
def test_parameterized(value):
    assert value > 0

def test_explicit_skip():
    pytest.skip('fixture skip must remain visible')
""",
    )

    summary = json.loads((root / "scheduler-result.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "partitions.json").read_text(encoding="utf-8"))
    results = [
        json.loads((root / f"worker-{index}" / "result.json").read_text(encoding="utf-8"))
        for index in range(2)
    ]

    assert exit_code == 0
    assert summary["status"] == "passed"
    assert summary["partitionSha256"] == manifest["planSha256"]
    assert summary["actualNodeIds"] == manifest["nodeIds"]
    assert summary["partitionIntersection"] == []
    assert set(results[0]["assignedNodeIds"]).isdisjoint(results[1]["assignedNodeIds"])
    assert set(results[0]["assignedNodeIds"]) | set(results[1]["assignedNodeIds"]) == set(
        manifest["nodeIds"]
    )
    assert sum(result["junit"]["tests"] for result in results) == len(manifest["nodeIds"])
    assert sum(result["junit"]["skipped"] for result in results) == 1
    assert all((root / f"worker-{index}" / "pytest.log").is_file() for index in range(2))
    assert all((root / f"worker-{index}" / "junit.xml").is_file() for index in range(2))
    assert all((root / f"worker-{index}" / "basetemp").is_dir() for index in range(2))
    assert all((root / f"worker-{index}" / "pytest-cache").is_dir() for index in range(2))
    assert ET.parse(root / "worker-0" / "junit.xml").getroot().findall(".//testcase")
    assert ET.parse(root / "worker-1" / "junit.xml").getroot().findall(".//testcase")


def test_original_worker_failure_cannot_be_reported_as_pass(tmp_path: Path) -> None:
    exit_code, root = _run_fixture_suite(
        tmp_path,
        """
def test_passes():
    assert True

def test_fails():
    assert False, 'fixture failure must propagate'
""",
    )

    summary = json.loads((root / "scheduler-result.json").read_text(encoding="utf-8"))
    results = [
        json.loads((root / f"worker-{index}" / "result.json").read_text(encoding="utf-8"))
        for index in range(2)
    ]

    assert exit_code != 0
    assert summary["status"] == "failed"
    assert any(result["junit"]["failures"] for result in results)
    failed_result = next(result for result in results if result["status"] == "failed")
    assert failed_result["failureTaxonomy"] == {
        "phase": "call",
        "errorClass": "AssertionError",
        "errorCode": "pytest_call_failed",
    }


def test_setup_and_teardown_failures_keep_their_pytest_phases(tmp_path: Path) -> None:
    exit_code, root = _run_fixture_suite(
        tmp_path,
        """
import pytest

@pytest.fixture
def setup_error():
    raise RuntimeError('setup failure must remain visible')

@pytest.fixture
def teardown_error():
    yield
    raise RuntimeError('teardown failure must remain visible')

def test_setup_failure(setup_error):
    assert True

def test_teardown_failure(teardown_error):
    assert True
""",
    )

    summary = json.loads((root / "scheduler-result.json").read_text(encoding="utf-8"))
    results = [
        json.loads((root / f"worker-{index}" / "result.json").read_text(encoding="utf-8"))
        for index in range(2)
    ]
    setup_phases = results[0]["execution"][0]["phases"]
    teardown_phases = results[1]["execution"][0]["phases"]

    assert exit_code != 0
    assert summary["status"] == "failed"
    assert setup_phases == [
        {"phase": "setup", "outcome": "failed"},
        {"phase": "teardown", "outcome": "passed"},
    ]
    assert teardown_phases == [
        {"phase": "setup", "outcome": "passed"},
        {"phase": "call", "outcome": "passed"},
        {"phase": "teardown", "outcome": "failed"},
    ]


def test_collection_error_cannot_be_reported_as_pass(tmp_path: Path) -> None:
    exit_code, root = _run_fixture_suite(
        tmp_path,
        "def test_valid():\n    assert True\n\ndef test_invalid(:\n    pass\n",
    )

    summary = json.loads((root / "scheduler-result.json").read_text(encoding="utf-8"))

    assert exit_code != 0
    assert summary["status"] == "failed"
    assert "collection" in summary["error"]
    assert summary["workerProcesses"] == []
    assert not (root / "worker-1" / "result.json").exists()
    assert not (root / "partitions.json").exists()


def test_interruption_cannot_be_reported_as_pass(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture-project"
    test_root = fixture_root / "tests"
    test_root.mkdir(parents=True)
    (test_root / "test_fixture.py").write_text(
        "import time\n\ndef test_slow_a(): time.sleep(10)\ndef test_slow_b(): time.sleep(10)\n",
        encoding="utf-8",
    )
    allowed_parent = tmp_path / "temp"
    allowed_parent.mkdir()
    result_root = allowed_parent / "interrupt-results"
    runner_script = Path(partitions.__file__).resolve()
    command = [
        sys.executable,
        "-P",
        str(runner_script),
        "--task-root",
        str(result_root),
        "--allowed-parent",
        str(allowed_parent),
        "--task-id",
        "partition-interruption-test",
        "--",
        "tests/test_fixture.py",
        "--confcutdir=tests",
        "-q",
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = partitions._pythonpath(
        Path.cwd(), environment.get("PYTHONPATH", "")
    )
    log_path = tmp_path / "interruption-runner.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=fixture_root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    try:
        deadline = time.monotonic() + 10
        child_started = False
        while time.monotonic() < deadline and process.poll() is None:
            child_owner = result_root / "worker-1.owner.json"
            if child_owner.exists():
                owner = json.loads(child_owner.read_text(encoding="utf-8"))
                child_started = owner.get("pid") is not None
                if child_started:
                    break
            time.sleep(0.02)
        assert child_started, log_path.read_text(encoding="utf-8")
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=5) == 143
        summary = json.loads((result_root / "scheduler-result.json").read_text(encoding="utf-8"))
        assert summary["status"] == "failed"
        worker_processes = summary["workerProcesses"]
        assert len(worker_processes) == 2
        assert len({item["pid"] for item in worker_processes}) == 2
        assert all(item["waited"] and item["returnCode"] != 0 for item in worker_processes)
        assert all(
            item["pid"]
            == json.loads((result_root / f"worker-{index}.owner.json").read_text(encoding="utf-8"))[
                "pid"
            ]
            for index, item in enumerate(worker_processes)
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
