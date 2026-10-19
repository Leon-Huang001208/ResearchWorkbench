"""Persistent admission tests: no daemon, vendor calls or protected resource stops."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from research_workbench_entrypoint import docker_build_queue as queue


@pytest.fixture
def manager(tmp_path, monkeypatch):
    home = tmp_path / "ledger"
    home.mkdir(mode=0o700)
    project = tmp_path / "project"
    project.mkdir()
    subject = queue.BuildQueue(home, project)
    monkeypatch.setattr(subject, "source", lambda: "a" * 40)
    monkeypatch.setattr(subject, "owner", lambda _pid: "live-owner")
    monkeypatch.setattr(
        subject,
        "snapshot",
        lambda: {
            "ready": True,
            "reason": "ready",
            "containers": [],
            "vm_bytes": 12 * queue.GIB,
            "required_bytes": 7 * queue.GIB,
        },
    )
    monkeypatch.setattr(subject, "execute", lambda _job: (0, "success"))
    monkeypatch.setattr(subject, "artifact_valid", lambda _job: True)
    return subject


def test_waiting_is_durable_deduplicated_and_does_not_hold_operation_lock(manager, monkeypatch):
    monkeypatch.setattr(manager, "snapshot", lambda: {"ready": False, "reason": "vm_memory_budget"})
    first = manager.submit("dsh-task", False)
    second = manager.submit("dsh-task", False)
    assert first["job_id"] == second["job_id"]
    assert first["status"] == "waiting_resources"
    assert len(list((manager.home / "build-queue").glob("*.json"))) == 1
    assert not (manager.home / "operation.lock").exists()
    monkeypatch.setattr(manager, "snapshot", lambda: {"ready": True, "reason": "ready"})
    assert manager.resume("dsh-task")["status"] == "completed"
    assert manager.resume("dsh-task")["status"] == "completed"


def test_same_commit_different_refresh_is_a_different_job(manager):
    assert manager.submit("dsh-task", False)["job_id"] != manager.submit("dsh-task", True)["job_id"]


def test_lock_busy_preserves_job_without_removing_unknown_lock(manager):
    lock = manager.home / "operation.lock"
    lock.mkdir()
    result = manager.submit("dsh-task", False)
    assert result["status"] == "waiting_resources"
    assert result["reason"] == "operation_busy"
    assert lock.is_dir()


def test_source_change_invalidates_old_job_without_building(manager, monkeypatch):
    (manager.home / "operation.lock").mkdir()
    manager.submit("dsh-task", False)
    (manager.home / "operation.lock").rmdir()
    monkeypatch.setattr(manager, "source", lambda: "b" * 40)
    monkeypatch.setattr(manager, "execute", lambda _: pytest.fail("stale source built"))
    assert manager.resume("dsh-task")["status"] == "invalidated"


def test_failed_build_is_not_retried_or_marked_complete(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(manager, "execute", lambda job: (calls.append(job) or 1, "build_failed"))
    assert manager.submit("dsh-task", False)["status"] == "failed"
    assert manager.resume("dsh-task")["status"] == "failed"
    assert len(calls) == 1


def test_live_claim_prevents_second_build_and_dead_claim_recovers(manager, monkeypatch):
    (manager.home / "operation.lock").mkdir()
    result = manager.submit("dsh-task", False)
    (manager.home / "operation.lock").rmdir()
    path = manager.directory / (result["job_id"] + ".json")
    job = json.loads(path.read_text())
    job.update(status="running", owner_pid=os.getpid(), owner_stamp="live-owner")
    queue.save(path, job)
    assert manager.resume("dsh-task")["reason"] == "build_active"
    monkeypatch.setattr(manager, "owner", lambda _: "replacement-owner")
    assert manager.resume("dsh-task")["status"] == "completed"


def test_wait_notice_is_emitted_once_after_24_hours(manager, monkeypatch):
    monkeypatch.setattr(manager, "snapshot", lambda: {"ready": False, "reason": "stage_active"})
    monkeypatch.setattr(queue.time, "time", lambda: 1)
    assert not manager.submit("dsh-task", False)["notify"]
    monkeypatch.setattr(queue.time, "time", lambda: 86402)
    assert manager.resume("dsh-task")["notify"]
    assert not manager.resume("dsh-task")["notify"]


def test_queue_rejects_alias_and_tampered_arguments(manager):
    manager.directory.mkdir(mode=0o700)
    path = manager.directory / ("a" * 64 + ".json")
    path.symlink_to(manager.home / "outside")
    with pytest.raises(queue.QueueError):
        manager.resume("dsh-task")


def test_capacity_keeps_actual_usage_distinct_from_limits(tmp_path):
    def run(*args):
        if args[:2] == ("docker", "info"):
            return str(12 * queue.GIB)
        if args[:2] == ("docker", "ps"):
            return "service"
        if args[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {
                        "Id": "service",
                        "Name": "/service",
                        "State": {"Running": True},
                        "Config": {"Labels": {}},
                        "HostConfig": {"Memory": 3 * queue.GIB},
                    }
                ]
            )
        if args[:2] == ("docker", "stats"):
            return '{"ID":"service","MemUsage":"768KiB / 3GiB"}'
        raise AssertionError(args)

    result = queue.capacity(tmp_path, run)
    assert result["ready"]
    assert result["reserved_bytes"] == 3 * queue.GIB
    assert result["required_bytes"] == 10 * queue.GIB
    assert result["containers"][0]["actual_usage_display"] == "768KiB / 3GiB"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "limit,labels,reason",
    [
        (0, {}, "unbounded_container"),
        (2 * queue.GIB, {"io.research-workbench.environment": "stage"}, "stage_active"),
    ],
)
def test_unsafe_capacity_does_not_allow_build(tmp_path, limit, labels, reason):
    def run(*args):
        if args[:2] == ("docker", "info"):
            return str(12 * queue.GIB)
        if args[:2] == ("docker", "ps"):
            return "c"
        if args[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {
                        "Id": "c",
                        "Name": "/c",
                        "State": {"Running": True},
                        "Config": {"Labels": labels},
                        "HostConfig": {"Memory": limit},
                    }
                ]
            )
        return '{"ID":"c","MemUsage":"0B / 2GiB"}'

    result = queue.capacity(tmp_path, run)
    assert not result["ready"]
    assert result["reason"] == reason


def test_finished_artifact_survives_busy_finalization_without_rebuilding(manager, monkeypatch):
    calls = []

    def execute(job):
        calls.append(job)
        (manager.home / "operation.lock").mkdir()
        return 0, "completed"

    monkeypatch.setattr(manager, "execute", execute)
    assert manager.submit("dsh-task", False)["status"] == "waiting_resources"
    (manager.home / "operation.lock").rmdir()
    assert manager.resume("dsh-task")["status"] == "completed"
    assert len(calls) == 1


def test_handoff_lock_race_can_resume_a_real_attempt(manager, monkeypatch):
    calls = []

    def execute(job):
        calls.append(job)
        return (1, "operation_busy") if len(calls) == 1 else (0, "completed")

    monkeypatch.setattr(manager, "execute", execute)
    assert manager.submit("dsh-task", False)["status"] == "waiting_resources"
    assert manager.resume("dsh-task")["status"] == "completed"
    assert len(calls) == 2


def test_changed_artifact_is_never_reused(manager, monkeypatch):
    assert manager.submit("dsh-task", False)["status"] == "completed"
    monkeypatch.setattr(manager, "artifact_valid", lambda _: False)
    assert manager.resume("dsh-task")["status"] == "invalidated"


def test_busy_lock_emits_only_one_notice_after_24_hours(manager, monkeypatch):
    (manager.home / "operation.lock").mkdir()
    monkeypatch.setattr(queue.time, "time", lambda: 1)
    assert not manager.submit("dsh-task", False)["notify"]
    monkeypatch.setattr(queue.time, "time", lambda: 86402)
    assert manager.resume("dsh-task")["notify"]
    assert not manager.resume("dsh-task")["notify"]
    assert (manager.home / "operation.lock").is_dir()


def test_other_tasks_durable_completion_cannot_block_fifo(manager, monkeypatch):
    def execute(_job):
        (manager.home / "operation.lock").mkdir()
        return 0, "completed"

    monkeypatch.setattr(manager, "execute", execute)
    assert manager.submit("old-task", False)["status"] == "waiting_resources"
    (manager.home / "operation.lock").rmdir()
    monkeypatch.setattr(manager, "execute", lambda _job: (0, "completed"))
    assert manager.submit("next-task", False)["status"] == "completed"


def test_stopped_unretired_stage_still_reserves_slot(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    queue.save(home / "stage-candidate.json", {"retired": False})
    result = queue.capacity(home, lambda *args: str(12 * queue.GIB) if args[1] == "info" else "")
    assert not result["ready"]
    assert result["reason"] == "stage_reserved"


def test_failed_cleanup_is_terminal_and_never_retried(manager, monkeypatch):
    monkeypatch.setattr(manager, "execute", lambda _job: (1, "builder_cleanup_incomplete"))
    assert manager.submit("dsh-task", False)["status"] == "blocked"
    monkeypatch.setattr(manager, "execute", lambda _: pytest.fail("unsafe cleanup retried"))
    assert manager.resume("dsh-task")["status"] == "blocked"


def test_archive_uses_committed_bytes_despite_concurrent_worktree_changes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    git = "/usr/bin/git" if sys.platform == "darwin" else "git"

    def run(*args):
        return subprocess.check_output([git, "-C", str(project), *args], text=True).strip()

    run("init", "-q")
    (project / "source.txt").write_text("committed")
    run("add", "source.txt")
    run(
        "-c",
        "user.name=Queue Test",
        "-c",
        "user.email=queue@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    home = tmp_path / "home"
    manager = queue.BuildQueue(home, project)
    manager.initialize()
    sha = manager.source()
    (project / "source.txt").write_text("concurrent edit")
    (project / "untracked.txt").write_text("not an input")

    def build(_job, context):
        assert (context / "source.txt").read_text() == "committed"
        assert not (context / "untracked.txt").exists()
        return 0, "completed"

    monkeypatch.setattr(manager, "run_build", build)
    assert manager.execute({"job_id": "a" * 64, "source_sha": sha}) == (0, "completed")
    assert not list((manager.directory / "contexts").iterdir())


def test_capacity_shell_entry_does_not_create_state_or_start_containers(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(
        '#!/bin/sh\ncase "$1" in info) echo 12884901888;; ps) :;; *) exit 99;; esac\n'
    )
    docker.chmod(0o755)
    home = tmp_path / "nonexistent"
    entry = Path(__file__).resolve().parents[2] / "rwb-docker"
    result = subprocess.run(
        [str(entry), "capacity", "--json"],
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            PATH=f"{binary}:{Path(sys.executable).parent}:/usr/bin:/bin",
            RWB_DOCKER_HOME=str(home),
        ),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ready"]
    assert not home.exists()


@pytest.mark.parametrize(
    "message,reason",
    [
        ("stop_stage_before_cold_build", "stage_active"),
        ("docker_operation_busy", "operation_busy"),
        ("vm_budget_requires_stopping_dev_or_16g_vm", "vm_memory_budget"),
    ],
)
def test_real_child_admission_failure_remains_resumable(manager, monkeypatch, message, reason):
    manager.initialize()
    entry = manager.project / "rwb-docker"
    entry.write_text(f"#!/bin/sh\necho {message}\nexit 1\n")
    entry.chmod(0o755)
    # A competing builder is never inspected/stopped after our child lost the lock.
    monkeypatch.setattr(queue, "call", lambda *args: pytest.fail("foreign builder inspected"))
    monkeypatch.setattr(manager, "execute", lambda job: manager.run_build(job, manager.project))
    result = manager.submit("dsh-task", False)
    assert result["status"] == "waiting_resources"
    assert result["reason"] == reason
    monkeypatch.setattr(manager, "execute", lambda _: (0, "completed"))
    assert manager.resume("dsh-task")["status"] == "completed"


def test_both_runtime_and_development_image_revisions_must_match(manager, monkeypatch):
    runtime, development = "sha256:" + "1" * 64, "sha256:" + "2" * 64
    job = {"image": runtime, "development_image": development, "source_sha": "a" * 40}
    monkeypatch.setattr(queue, "call", lambda *args: "a" * 40)
    assert queue.BuildQueue.artifact_valid(manager, job)
    monkeypatch.setattr(
        queue, "call", lambda *args: "b" * 40 if args[-1] == development else "a" * 40
    )
    assert not queue.BuildQueue.artifact_valid(manager, job)


def test_next_rejects_jobs_from_another_repository(manager, tmp_path, monkeypatch):
    (manager.home / "operation.lock").mkdir()
    manager.submit("dsh-task", False)
    (manager.home / "operation.lock").rmdir()
    other_project = tmp_path / "other"
    other_project.mkdir()
    other = queue.BuildQueue(manager.home, other_project)
    monkeypatch.setattr(queue.BuildQueue, "repository", lambda subject: subject.project / ".git")
    with pytest.raises(queue.QueueError, match="repository_mismatch"):
        other.next()


def test_success_requires_own_verified_cleanup_marker(manager):
    manager.initialize()
    entry = manager.project / "rwb-docker"
    entry.write_text("#!/bin/sh\necho candidate_image=sha256:test\nexit 0\n")
    entry.chmod(0o755)
    job = {"job_id": "a" * 64, "task_id": "dsh-task", "source_sha": "a" * 40, "refresh": False}
    assert manager.run_build(job, manager.project) == (1, "builder_cleanup_incomplete")


def test_archived_entry_script_is_used_instead_of_mutable_worktree(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    git = "/usr/bin/git" if sys.platform == "darwin" else "git"

    def run(*args):
        return subprocess.check_output([git, "-C", str(project), *args], text=True).strip()

    run("init", "-q")
    entry = project / "rwb-docker"
    entry.write_text("#!/bin/sh\necho queue_builder_cleanup=stopped\nexit 0\n")
    entry.chmod(0o755)
    run("add", "rwb-docker")
    run(
        "-c",
        "user.name=Queue Test",
        "-c",
        "user.email=queue@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    subject = queue.BuildQueue(tmp_path / "home", project)
    subject.initialize()
    sha = subject.source()
    entry.write_text("#!/bin/sh\nexit 99\n")
    monkeypatch.setattr(subject, "artifact_valid", lambda _: True)
    assert subject.execute(
        {"job_id": "a" * 64, "task_id": "dsh-task", "source_sha": sha, "refresh": False}
    ) == (0, "completed")


def test_context_failure_is_persisted_and_never_rebuilt(manager, monkeypatch):
    def fail(_job):
        raise OSError("private context failure")

    monkeypatch.setattr(manager, "execute", fail)
    assert manager.submit("dsh-task", False)["status"] == "blocked"
    monkeypatch.setattr(manager, "execute", lambda _: pytest.fail("failed context rebuilt"))
    assert manager.resume("dsh-task")["reason"] == "build_context_failed"
