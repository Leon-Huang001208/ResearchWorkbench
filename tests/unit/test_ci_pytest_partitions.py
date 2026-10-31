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


def test_ci_job_shards_form_a_deterministic_exact_union_before_worker_split() -> None:
    suite = [f"tests/test_api.py::test_api[{index}]" for index in range(12)]

    jobs = [partitions.split_job_nodeids(suite, job_index=index, job_count=2) for index in range(2)]

    assert jobs == [suite[0::2], suite[1::2]]
    assert set(jobs[0]).isdisjoint(jobs[1])
    assert set(jobs[0]) | set(jobs[1]) == set(suite)
    assert all(len(partitions.split_nodeids(job)) == 2 for job in jobs)


def _workflow_job(source: str, job_id: str) -> str:
    lines = source.splitlines()
    start = lines.index(f"  {job_id}:")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])


def _workflow_step(job: str, step_name: str) -> str:
    lines = job.splitlines()
    start = lines.index(f"      - name: {step_name}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("      - name: "):
            end = index
            break
    return "\n".join(lines[start:end])


def _assert_research_web_workflow_contract(workflow: str) -> None:
    jobs_source = workflow.split("\njobs:\n", 1)[1]
    job_ids = [
        line[2:-1]
        for line in jobs_source.splitlines()
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":")
    ]
    assert job_ids == ["python-contracts", "checks"]
    python_job = _workflow_job(workflow, "python-contracts")
    checks_job = _workflow_job(workflow, "checks")
    assert "    name: Python contracts (shard ${{ matrix.pytest_shard }})" in python_job
    assert "      fail-fast: false" in python_job
    assert "      max-parallel: 2" in python_job
    assert "        pytest_shard: [0, 1]" in python_job
    assert '--job-shard-index "${{ matrix.pytest_shard }}"' in python_job
    assert python_job.count("--job-shard-count 2") == 2

    javascript = _workflow_step(python_job, "Run Research Web JavaScript contracts")
    editorial = _workflow_step(
        python_job, "Verify pinned editorial engine without model or paid requests"
    )
    python = _workflow_step(python_job, "Run Research Web Python contracts")
    upload = _workflow_step(python_job, "Upload safe pytest evidence")
    assert "        if: matrix.pytest_shard == 0" in javascript
    assert "        if: (success() || failure()) && matrix.pytest_shard == 0" in editorial
    assert "        if: success() || failure()" in python
    assert python_job.index(javascript) < python_job.index(python)
    assert python_job.index(editorial) < python_job.index(python)
    assert "        uses: actions/upload-artifact@v4" in upload
    assert (
        "          name: research-web-checks-${{ github.run_id }}-"
        "${{ github.run_attempt }}-shard-${{ matrix.pytest_shard }}" in upload
    )

    assert "    if: always()" in checks_job
    assert "    needs: python-contracts" in checks_job
    assert not any(line.startswith("    name:") for line in checks_job.splitlines())
    first_download = _workflow_step(checks_job, "Download Python shard 0 evidence")
    second_download = _workflow_step(checks_job, "Download Python shard 1 evidence")
    assert "        uses: actions/download-artifact@v4" in first_download
    assert "        uses: actions/download-artifact@v4" in second_download
    assert "-shard-0" in first_download and "path: artifacts/shard-0" in first_download
    assert "-shard-1" in second_download and "path: artifacts/shard-1" in second_download
    verify = _workflow_step(checks_job, "Verify exact Python shard union and worker evidence")
    assert "--verify-shards artifacts/shard-0 artifacts/shard-1" in verify
    guard = _workflow_step(checks_job, "Require Python, JavaScript, and editorial job success")
    assert "PYTHON_CONTRACTS_RESULT: ${{ needs.python-contracts.result }}" in guard
    assert 'if [[ "$PYTHON_CONTRACTS_RESULT" != "success" ]]; then' in guard
    assert "exit 1" in guard


def test_research_web_workflow_keeps_four_bounded_workers_and_one_checks_gate() -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/research-web-checks.yml"
    ).read_text(encoding="utf-8")

    _assert_research_web_workflow_contract(workflow)


@pytest.mark.parametrize(
    "tamper",
    [
        "repeat-javascript",
        "repeat-editorial",
        "artifact-collision",
        "missing-second-download",
        "missing-result-guard",
    ],
)
def test_research_web_workflow_contract_rejects_cost_or_gate_regressions(tamper: str) -> None:
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/research-web-checks.yml"
    ).read_text(encoding="utf-8")
    if tamper == "repeat-javascript":
        workflow = workflow.replace("        if: matrix.pytest_shard == 0\n", "", 1)
    elif tamper == "repeat-editorial":
        workflow = workflow.replace(
            "        if: (success() || failure()) && matrix.pytest_shard == 0\n", "", 1
        )
    elif tamper == "artifact-collision":
        workflow = workflow.replace("-shard-${{ matrix.pytest_shard }}", "-shard")
    elif tamper == "missing-second-download":
        workflow = workflow.replace("-shard-1", "-shard-0").replace(
            "path: artifacts/shard-1", "path: artifacts/shard-0"
        )
    else:
        workflow = workflow.replace(
            'if [[ "$PYTHON_CONTRACTS_RESULT" != "success" ]]; then',
            'if [[ "$PYTHON_CONTRACTS_RESULT" == "success" ]]; then',
        )

    with pytest.raises(AssertionError):
        _assert_research_web_workflow_contract(workflow)


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
        "suiteNodeIds": nodeids,
        "jobShardIndex": 0,
        "jobShardCount": 1,
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
                'schemaVersion': 3,
                'taskId': 'forged-result-red',
                'selection': ['tests/test_fixture.py', '--confcutdir=tests', '-q'],
                'suiteNodeIds': nodeids,
                'jobShardIndex': 0,
                'jobShardCount': 1,
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


def _run_worker_with_progress_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, phase: str, outcome: str
) -> tuple[int, dict, partitions.WorkerPlugin]:
    fixture_root = tmp_path / "fixture-project"
    tests = fixture_root / "tests"
    tests.mkdir(parents=True)
    statement = {
        "passed": "assert True",
        "failed": "assert False, 'original failure'",
        "skipped": "import pytest; pytest.skip('original skip')",
    }[outcome]
    filename = f"test_progress_{phase}_{outcome}.py"
    module_name = filename.removesuffix(".py")
    (tests / filename).write_text(
        f"def test_target(): {statement}\ndef test_other(): assert True\n", encoding="utf-8"
    )
    arguments = [f"tests/{filename}", "--confcutdir=tests", "-q"]
    nodeids = [f"tests/{filename}::test_target", f"tests/{filename}::test_other"]
    task_id = "progress-write-failure"
    split = partitions.split_nodeids(nodeids)
    manifest = {
        "schemaVersion": partitions.MANIFEST_SCHEMA_VERSION,
        "taskId": task_id,
        "selection": arguments,
        "suiteNodeIds": nodeids,
        "jobShardIndex": 0,
        "jobShardCount": 1,
        "nodeIds": nodeids,
        "partitions": split,
        "planSha256": partitions._plan_sha256(task_id, arguments, nodeids, split),
    }
    root = tmp_path / "worker-root"
    root.mkdir(mode=0o700)
    worker_dir = root / "worker-0"
    plugin = partitions.WorkerPlugin(0, worker_dir, manifest, arguments, task_id)
    original = partitions._atomic_json

    def fail_selected_progress(path: Path, value: dict) -> None:
        if path.name == "progress.json" and value.get("phase") == phase:
            raise OSError("PRIVATE_PROGRESS_WRITE_FAILURE")
        original(path, value)

    monkeypatch.setattr(partitions, "_atomic_json", fail_selected_progress)
    monkeypatch.setattr(partitions, "PROGRESS_WRITE_INTERVAL_SECONDS", 0)
    monkeypatch.chdir(fixture_root)
    exit_code = partitions._run_worker(plugin, task_id, root.stat())
    sys.modules.pop(module_name, None)
    result = json.loads((worker_dir / "result.json").read_text(encoding="utf-8"))
    return exit_code, result, plugin


@pytest.mark.parametrize("phase", ["startup", "collection", "setup", "call", "teardown"])
def test_progress_write_oserror_never_changes_passing_worker_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    exit_code, result, plugin = _run_worker_with_progress_failure(
        tmp_path, monkeypatch, phase=phase, outcome="passed"
    )

    assert exit_code == 0
    assert result["status"] == "passed"
    assert result["pytestExitCode"] == 0
    assert result["failureTaxonomy"] is None
    assert plugin.progress_disabled
    assert plugin.progress_error_code == "write_unavailable"
    assert "PRIVATE_PROGRESS_WRITE_FAILURE" not in json.dumps(result)


@pytest.mark.parametrize("outcome", ["failed", "skipped"])
def test_progress_write_oserror_preserves_original_failed_or_skipped_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    exit_code, result, plugin = _run_worker_with_progress_failure(
        tmp_path, monkeypatch, phase="call", outcome=outcome
    )

    assert plugin.progress_disabled
    assert plugin.progress_error_code == "write_unavailable"
    if outcome == "failed":
        assert exit_code == 1
        assert result["status"] == "failed"
        assert result["failureTaxonomy"]["errorCode"] == "pytest_call_failed"
    else:
        assert exit_code == 0
        assert result["status"] == "passed"
        assert result["junit"]["skipped"] == 1
    assert "PRIVATE_PROGRESS_WRITE_FAILURE" not in json.dumps(result)


def test_progress_does_not_swallow_baseexception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = {
        "nodeIds": ["tests/test_fixture.py::test_one", "tests/test_fixture.py::test_two"],
        "partitions": [
            ["tests/test_fixture.py::test_one"],
            ["tests/test_fixture.py::test_two"],
        ],
        "planSha256": "a" * 64,
    }
    plugin = partitions.WorkerPlugin(0, tmp_path, manifest, [], "baseexception")

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(partitions, "_atomic_json", interrupt)
    with pytest.raises(KeyboardInterrupt):
        plugin.write_progress("startup")


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
    progress = [
        json.loads((root / f"worker-{index}" / "progress.json").read_text(encoding="utf-8"))
        for index in range(2)
    ]
    for index, item in enumerate(progress):
        assert set(item) == partitions.WORKER_PROGRESS_FIELDS
        assert item["schemaVersion"] == partitions.WORKER_PROGRESS_SCHEMA_VERSION
        assert item["workerIndex"] == index
        assert item["planSha256"] == manifest["planSha256"]
        assert item["phase"] in {"setup", "call", "teardown"}
        assert item["nodeId"] in manifest["partitions"][index]
        assert item["counters"]["selected"] == len(manifest["partitions"][index])
        assert 1 <= item["counters"]["started"] <= len(manifest["partitions"][index])
        assert item["counters"]["completed"] <= item["counters"]["started"]
        assert (
            sum(item["counters"][name] for name in ("passed", "skipped", "failed"))
            == item["counters"]["started"]
        )


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
        progress = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            progress_paths = [
                result_root / f"worker-{index}" / "progress.json" for index in range(2)
            ]
            if all(path.is_file() for path in progress_paths):
                progress = [json.loads(path.read_text(encoding="utf-8")) for path in progress_paths]
                if all(item["phase"] in {"setup", "call"} for item in progress):
                    break
            time.sleep(0.02)
        assert len(progress) == 2
        assert all(
            item["nodeId"] in item_ids
            for item, item_ids in zip(
                progress,
                json.loads((result_root / "partitions.json").read_text())["partitions"],
                strict=True,
            )
        )
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
