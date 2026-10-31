"""Successful test fixtures retire early without weakening evidence or ownership checks."""

import hashlib
import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from scripts import test_artifact_retention as retention
from scripts.test_artifact_retention import (
    RetentionError,
    admit_batch,
)
from scripts.test_artifact_retention import create_root as product_create_root
from scripts.test_artifact_retention import retire_root as product_retire_root

CANDIDATE = "a" * 40


def create_root(parent, receipt, *, task_id, candidate):
    return product_create_root(
        parent,
        receipt,
        task_id=task_id,
        candidate=candidate,
        batch_id="batch-01",
        node_ids=["tests/test_fixture.py::test_safe"],
    )


def evidence(folder: Path, *, failed: bool = False) -> tuple[Path, Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    junit = folder / "batch.xml"
    junit.write_text(
        f'<testsuites><testsuite tests="1" failures="{int(failed)}" errors="0">'
        '<testcase classname="test_fixture" name="test_safe"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    stdout = folder / "stdout.log"
    stdout.write_text("1 passed\n", encoding="utf-8")
    stderr = folder / "stderr.log"
    stderr.write_text("", encoding="utf-8")
    return junit, stdout, stderr


def retire_root(receipt, junit, stdout, stderr, *, open_files, exit_code=0):
    owner = json.loads(receipt.read_text())
    result = receipt.parent / "batch-result.json"
    result.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "taskId": owner["taskId"],
                "candidate": owner["candidate"],
                "rootNonce": owner["nonce"],
                "batchId": "batch-01",
                "nodeIds": ["tests/test_fixture.py::test_safe"],
                "exitCode": exit_code,
                "junitSha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
                "stdoutSha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
                "stderrSha256": hashlib.sha256(stderr.read_bytes()).hexdigest(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return product_retire_root(receipt, junit, stdout, stderr, result, open_files=open_files)


def test_passed_root_with_internal_hardlinks_and_read_only_directory_retires(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    nested = root / "active" / "fixture"
    nested.mkdir(parents=True)
    (nested / "original.txt").write_text("proof", encoding="utf-8")
    os.link(nested / "original.txt", nested / "second-view.txt")
    nested.chmod(0o555)
    files = evidence(receipt.parent)

    result = retire_root(receipt, *files, open_files=lambda _path: False)

    assert result["status"] == "retired"
    assert result["permissionRepairs"] >= 1
    assert not root.exists()
    assert all(path.exists() for path in files)
    assert json.loads(receipt.read_text())["status"] == "retired"


def test_external_hardlink_keeps_root_and_sealed_evidence(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    outside = tmp_path / "outside.txt"
    outside.write_text("shared", encoding="utf-8")
    os.link(outside, root / "shared.txt")
    files = evidence(receipt.parent)

    with pytest.raises(RetentionError, match="external_hardlink"):
        retire_root(receipt, *files, open_files=lambda _path: False)

    assert root.exists()
    assert outside.read_text() == "shared"
    assert json.loads(receipt.read_text())["status"] == "sealed"


def test_failed_junit_cannot_retire_root(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(receipt.parent, failed=True)

    with pytest.raises(RetentionError, match="junit_not_passed"):
        retire_root(receipt, *files, open_files=lambda _path: False)

    assert root.exists()
    assert json.loads(receipt.read_text())["status"] == "active"


def test_replaced_root_inode_is_rejected(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    root.rename(root.with_name("kept-original"))
    root.mkdir()
    files = evidence(receipt.parent)

    with pytest.raises(RetentionError, match="root_identity"):
        retire_root(receipt, *files, open_files=lambda _path: False)

    assert root.exists()
    assert root.with_name("kept-original").exists()


def test_symlinked_evidence_is_rejected(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    junit, stdout, stderr = evidence(receipt.parent)
    other = tmp_path / "outside.log"
    other.write_text("untrusted", encoding="utf-8")
    stdout.unlink()
    stdout.symlink_to(other)

    with pytest.raises(RetentionError, match="evidence_identity"):
        retire_root(receipt, junit, stdout, stderr, open_files=lambda _path: False)

    assert root.exists()


def test_evidence_inside_deleted_root_is_not_mistaken_for_external_proof(tmp_path):
    receipt = tmp_path / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(root / "active" / "proof")

    with pytest.raises(RetentionError, match="evidence_inside_root"):
        retire_root(receipt, *files, open_files=lambda _path: False)

    assert root.exists()
    assert all(path.exists() for path in files)


def test_junit_summary_cannot_hide_embedded_failure(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    junit, stdout, stderr = evidence(receipt.parent)
    junit.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0">'
        '<testcase name="test_failed"><failure>real failure</failure></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )

    with pytest.raises(RetentionError, match="junit_not_passed"):
        retire_root(receipt, junit, stdout, stderr, open_files=lambda _path: False)

    assert root.exists()


def test_second_active_root_for_same_task_is_refused(tmp_path):
    parent = tmp_path / "test-temp"
    first = create_root(
        parent, tmp_path / "proof" / "first.json", task_id="retention-test", candidate=CANDIDATE
    )

    with pytest.raises(RetentionError, match="task_root_active"):
        create_root(
            parent,
            tmp_path / "proof" / "second.json",
            task_id="retention-test",
            candidate=CANDIDATE,
        )

    assert first.exists()


def test_create_refuses_insufficient_physical_space(tmp_path, monkeypatch):
    monkeypatch.setattr(retention, "_free", lambda _path: 3 * 1024**3 - 1)

    with pytest.raises(RetentionError, match="disk_floor"):
        create_root(
            tmp_path / "test-temp",
            tmp_path / "proof" / "lease.json",
            task_id="retention-test",
            candidate=CANDIDATE,
        )


def test_batch_admission_checks_size_and_current_free_space(tmp_path, monkeypatch):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    (root / "fixture.txt").write_text("data", encoding="utf-8")

    with monkeypatch.context() as patch:
        patch.setattr(retention, "MAX_ACTIVE_ROOT_BYTES", 1)
        with pytest.raises(RetentionError, match="active_root_budget"):
            admit_batch(receipt)

    with monkeypatch.context() as patch:
        patch.setattr(retention, "_free", lambda _path: 3 * 1024**3 - 1)
        with pytest.raises(RetentionError, match="disk_floor"):
            admit_batch(receipt)

    assert admit_batch(receipt)["status"] == "admitted"


def test_old_pass_junit_does_not_override_nonzero_batch_exit(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(receipt.parent)

    with pytest.raises(RetentionError, match="batch_result_not_passed"):
        retire_root(receipt, *files, open_files=lambda _path: False, exit_code=1)

    assert root.exists()
    assert json.loads(receipt.read_text())["status"] == "active"


def test_run_requires_real_clean_checkout_matching_candidate(tmp_path, monkeypatch):
    repository = tmp_path / "checkout"
    repository.mkdir()
    subprocess.run(["/usr/bin/git", "init", "-q", str(repository)], check=True)
    (repository / "source.txt").write_text("frozen", encoding="utf-8")
    subprocess.run(["/usr/bin/git", "-C", str(repository), "add", "source.txt"], check=True)
    subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(repository),
            "-c",
            "user.name=RWB Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    head = subprocess.check_output(
        ["/usr/bin/git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()
    monkeypatch.chdir(repository)

    with pytest.raises(RetentionError, match="candidate_head_mismatch"):
        retention._checkout_identity("a" * 40)
    (repository / "untracked.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(RetentionError, match="candidate_worktree_dirty"):
        retention._checkout_identity(head)
    assert retention._checkout_identity(head, mode="wip") == repository
    (repository / "untracked.txt").unlink()
    assert retention._checkout_identity(head) == repository


def test_low_level_exact_flag_cannot_be_asserted_without_matching_checkout(tmp_path):
    parent = tmp_path / "test-temp"
    with pytest.raises(RetentionError, match="candidate_head_mismatch"):
        product_create_root(
            parent,
            tmp_path / "proof" / "lease.json",
            task_id="retention-test",
            candidate="a" * 40,
            batch_id="batch-01",
            node_ids=["tests/test_fixture.py::test_safe"],
            _exact_checkout=True,
        )
    assert not parent.exists() or not list(parent.glob("rwb-test-*"))


def test_open_test_root_remains_available_for_diagnosis(tmp_path):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(receipt.parent)

    with pytest.raises(RetentionError, match="root_in_use"):
        retire_root(receipt, *files, open_files=lambda _path: True)

    assert root.exists()
    assert json.loads(receipt.read_text())["status"] == "sealed"


def test_interrupted_delete_can_resume_without_replacing_evidence(tmp_path, monkeypatch):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    (root / "fixture.txt").write_text("reproducible", encoding="utf-8")
    files = evidence(receipt.parent)
    actual_rmtree = retention.shutil.rmtree

    def interrupted_rmtree(path, *args, **kwargs):
        if kwargs.get("dir_fd") is not None:
            frozen = json.loads(receipt.read_text())
            (Path(frozen["quarantine"]) / root.name / "owner.json").unlink()
            raise PermissionError("simulated interrupted deletion")
        return actual_rmtree(path, *args, **kwargs)

    interrupted_rmtree.avoids_symlink_attacks = actual_rmtree.avoids_symlink_attacks
    with monkeypatch.context() as patch:
        patch.setattr(retention.shutil, "rmtree", interrupted_rmtree)
        with pytest.raises(PermissionError, match="simulated interrupted deletion"):
            retire_root(receipt, *files, open_files=lambda _path: False)

    interrupted = json.loads(receipt.read_text())
    assert interrupted["status"] == "delete_intent"
    assert not root.exists()
    quarantined = Path(interrupted["quarantine"]) / root.name
    assert quarantined.exists()
    (quarantined / "unregistered.txt").write_text("must not be deleted", encoding="utf-8")

    with pytest.raises(RetentionError, match="root_contents_changed"):
        retire_root(receipt, *files, open_files=lambda _path: False)

    assert (quarantined / "unregistered.txt").read_text() == "must not be deleted"
    (quarantined / "unregistered.txt").unlink()

    completed = retire_root(receipt, *files, open_files=lambda _path: False)
    assert completed["status"] == "retired"
    assert not Path(interrupted["quarantine"]).exists()
    assert all(path.exists() for path in files)


def test_file_added_after_quarantine_rename_blocks_delete(tmp_path, monkeypatch):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(receipt.parent)
    actual_rename = retention.os.rename

    def injected_rename(source, destination, **kwargs):
        actual_rename(source, destination, **kwargs)
        if kwargs.get("dst_dir_fd") is not None:
            record = json.loads(receipt.read_text())
            target = Path(record["quarantine"]) / root.name
            (target / "new-after-rename.txt").write_text("unsealed", encoding="utf-8")

    with monkeypatch.context() as patch:
        patch.setattr(retention.os, "rename", injected_rename)
        with pytest.raises(RetentionError, match="root_contents_changed"):
            retire_root(receipt, *files, open_files=lambda _path: False)

    record = json.loads(receipt.read_text())
    assert record["status"] == "intent"
    assert (Path(record["quarantine"]) / root.name / "new-after-rename.txt").exists()


def test_concurrent_retirement_cannot_split_one_root_across_quarantines(tmp_path, monkeypatch):
    receipt = tmp_path / "proof" / "lease.json"
    root = create_root(
        tmp_path / "test-temp", receipt, task_id="retention-test", candidate=CANDIDATE
    )
    files = evidence(receipt.parent)
    with pytest.raises(RetentionError, match="root_in_use"):
        retire_root(receipt, *files, open_files=lambda _path: True)
    result = receipt.parent / "batch-result.json"
    entered = threading.Event()
    release = threading.Event()
    actual_scan = retention._scan
    outcomes = []

    def held_scan(path, device):
        if path == root:
            entered.set()
            assert release.wait(timeout=5)
        return actual_scan(path, device)

    def first_retirement():
        try:
            outcomes.append(
                product_retire_root(receipt, *files, result, open_files=lambda _path: False)[
                    "status"
                ]
            )
        except (OSError, RetentionError) as error:
            outcomes.append(type(error).__name__ + ":" + str(error))

    with monkeypatch.context() as patch:
        patch.setattr(retention, "_scan", held_scan)
        thread = threading.Thread(target=first_retirement)
        thread.start()
        assert entered.wait(timeout=5)
        with pytest.raises(RetentionError, match="task_lock_busy_or_invalid"):
            product_retire_root(receipt, *files, result, open_files=lambda _path: False)
        release.set()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert outcomes == ["retired"]
    assert not root.exists()
    assert json.loads(receipt.read_text())["status"] == "retired"


@pytest.mark.parametrize(
    ("usage", "reason"),
    [
        ("oversize", "active_root_budget_during_test"),
        ("unreadable", "capacity_probe_failed"),
        ("output", "batch_output_budget_during_test"),
    ],
)
def test_running_batch_stops_on_capacity_growth_and_keeps_repro(
    tmp_path, monkeypatch, usage, reason
):
    class FakeProcess:
        pid = 4242

        def __init__(self):
            self.calls = 0
            self.returncode = None

        def wait(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("pytest", timeout)
            self.returncode = -15
            return self.returncode

        def poll(self):
            return self.returncode

    process = FakeProcess()
    signalled = []
    monkeypatch.setattr(retention, "_checkout_identity", lambda _candidate, **_kwargs: Path.cwd())

    def popen(_command, **kwargs):
        if usage == "output":
            kwargs["stdout"].write(b"xx")
            kwargs["stdout"].flush()
        return process

    monkeypatch.setattr(retention.subprocess, "Popen", popen)

    def usage_probe(_root):
        if usage == "unreadable":
            raise PermissionError("simulated unreadable fixture")
        if usage == "output":
            return 0
        return retention.MAX_ACTIVE_ROOT_BYTES + 1

    monkeypatch.setattr(retention, "_usage_bytes", usage_probe)
    if usage == "output":
        monkeypatch.setattr(retention, "MAX_EVIDENCE_BYTES", 1)
    monkeypatch.setattr(retention.os, "killpg", lambda pid, sig: signalled.append((pid, sig)))
    receipt = tmp_path / "proof" / "lease.json"

    with pytest.raises(RetentionError, match=reason):
        retention.run_batch(
            tmp_path / "test-temp",
            receipt,
            task_id="retention-test",
            candidate=CANDIDATE,
            batch_id="batch-01",
            node_ids=["tests/test_fixture.py::test_safe"],
            python=Path("/usr/bin/python3"),
        )

    record = json.loads(receipt.read_text())
    assert record["status"] == "active"
    assert Path(record["root"]).exists()
    result = json.loads((receipt.parent / "batch-01.result.json").read_text())
    assert result["exitCode"] == -15
    if usage == "output":
        assert result["stdoutSha256"] is None
    assert signalled == [(4242, retention.signal.SIGTERM)]


def test_exact_run_keeps_root_if_checkout_changes_during_test(tmp_path, monkeypatch):
    class CompletedProcess:
        pid = 4343

        def wait(self, timeout):
            return 0

        def poll(self):
            return 0

    checks = 0

    def checkout(_candidate, *, mode):
        nonlocal checks
        assert mode == "exact"
        checks += 1
        if checks == 3:
            raise RetentionError("candidate_worktree_dirty")
        return Path.cwd()

    def popen(command, **kwargs):
        junit = next(value.split("=", 1)[1] for value in command if value.startswith("--junitxml="))
        Path(junit).write_text(
            '<testsuites><testsuite tests="1" failures="0" errors="0">'
            '<testcase name="test_safe"/></testsuite></testsuites>'
        )
        kwargs["stdout"].write(b"1 passed\n")
        return CompletedProcess()

    monkeypatch.setattr(retention, "_checkout_identity", checkout)
    monkeypatch.setattr(retention.subprocess, "Popen", popen)
    receipt = tmp_path / "proof" / "lease.json"

    with pytest.raises(RetentionError, match="source_changed_during_test"):
        retention.run_batch(
            tmp_path / "test-temp",
            receipt,
            task_id="retention-test",
            candidate=CANDIDATE,
            batch_id="batch-01",
            node_ids=["tests/test_fixture.py::test_safe"],
            python=Path("/usr/bin/python3"),
        )

    record = json.loads(receipt.read_text())
    assert checks == 3
    assert record["status"] == "source_changed"
    assert Path(record["root"]).exists()
    assert json.loads((receipt.parent / "batch-01.result.json").read_text())["exitCode"] == 0
