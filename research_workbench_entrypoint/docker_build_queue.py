"""Stdlib administrative build queue; legacy shell owns all Docker mutations.

Capacity queries do not create files, containers or locks. Queue records contain
only source identities, fixed build options, resource summaries and stable codes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from collections import deque
from contextlib import contextmanager
from pathlib import Path

GIB = 1024**3
LOG = logging.getLogger("rwb.docker.build_queue")
PENDING = {"waiting_resources", "running"}
TRANSIENT = {
    "vm_memory_budget",
    "stage_active",
    "stage_reserved",
    "operation_busy",
    "builder_active",
    "build_active",
    "queue_ahead",
}


class QueueError(RuntimeError):
    """Stable, non-sensitive refusal."""


def call(*args: str) -> str:
    """Never expose raw daemon/Git errors, which can contain private data."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QueueError("command_unavailable") from exc
    if result.returncode:
        raise QueueError("command_failed")
    return result.stdout.strip()


def private_directory(path: Path, create: bool = False) -> None:
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise QueueError("queue_directory_unsafe")


def load(path: Path) -> dict:
    if path.is_symlink():
        raise QueueError("queue_record_alias")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 65536
            or info.st_nlink != 1
        ):
            raise QueueError("queue_record_unsafe")
        result = json.load(stream)
    if not isinstance(result, dict):
        raise QueueError("queue_record_invalid")
    return result


def save(path: Path, value: dict, exclusive: bool = False) -> None:
    if path.is_symlink():
        raise QueueError("queue_record_alias")
    temporary = path.parent / (".pending-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            temporary.chmod(0o600)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            try:
                os.link(temporary, path)
            except FileExistsError:
                load(path)  # Existing records must still pass ownership checks.
        else:
            temporary.replace(path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def capacity(home: Path, run=call) -> dict:
    """Use hard limits for admission; actual usage is explicitly informational."""
    if home.exists() or home.is_symlink():
        private_directory(home)
    vm = int(run("docker", "info", "--format", "{{.MemTotal}}"))
    if vm <= 0:
        raise QueueError("vm_capacity_invalid")
    identities = run("docker", "ps", "-q", "--no-trunc").splitlines()
    rows, reasons = [], []
    if identities:
        containers = json.loads(run("docker", "inspect", *identities))
        stats = [
            json.loads(line)
            for line in run(
                "docker", "stats", "--no-stream", "--no-trunc", "--format", "{{json .}}"
            ).splitlines()
        ]
        usage = {row["ID"]: row["MemUsage"] for row in stats}
        for item in containers:
            limit = item["HostConfig"]["Memory"]
            if not isinstance(limit, int) or limit < 0:
                raise QueueError("container_limit_invalid")
            name = item["Name"].lstrip("/")
            rows.append(
                {
                    "id": item["Id"],
                    "name": name,
                    "limit_bytes": limit,
                    "actual_usage_display": usage.get(item["Id"], "unavailable"),
                }
            )
            if limit == 0:
                reasons.append("unbounded_container")
            if item["Config"].get("Labels", {}).get("io.research-workbench.environment") == "stage":
                reasons.append("stage_active")
            if name == "buildx_buildkit_rwb-dev-builder0":
                reasons.append("builder_active")
    for path in home.glob("stage-*.json"):
        if not load(path).get("retired", False):
            reasons.append("stage_reserved")
    reserved = sum(row["limit_bytes"] for row in rows)
    required = reserved + 5 * GIB + 2 * GIB
    if required > vm:
        reasons.append("vm_memory_budget")
    if (home / "operation.lock").exists():
        reasons.append("operation_busy")
    reason = next(
        (
            value
            for value in (
                "unbounded_container",
                "stage_active",
                "stage_reserved",
                "builder_active",
                "operation_busy",
                "vm_memory_budget",
            )
            if value in reasons
        ),
        "ready",
    )
    return {
        "ready": not reasons,
        "reason": reason,
        "vm_bytes": vm,
        "reserved_bytes": reserved,
        "builder_bytes": 5 * GIB,
        "headroom_bytes": 2 * GIB,
        "required_bytes": required,
        "shortfall_bytes": max(0, required - vm),
        "containers": rows,
    }


class BuildQueue:
    """One machine queue, with per-task source bindings and no sleeping lock."""

    def __init__(self, home: Path, project: Path):
        self.home = home
        self.project = project.resolve(strict=True)
        self.directory = home / "build-queue"

    def initialize(self) -> None:
        private_directory(self.home, create=True)
        private_directory(self.directory, create=True)
        private_directory(self.directory / "results", create=True)
        private_directory(self.directory / "notices", create=True)
        private_directory(self.directory / "contexts", create=True)
        private_directory(self.home / "logs", create=True)

    def source(self) -> str:
        git = "/usr/bin/git" if sys.platform == "darwin" else "git"
        if (
            Path(call(git, "-C", str(self.project), "rev-parse", "--show-toplevel")).resolve()
            != self.project
        ):
            raise QueueError("source_root_mismatch")
        sha = call(git, "-C", str(self.project), "rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise QueueError("source_sha_invalid")
        if call(git, "-C", str(self.project), "status", "--porcelain", "--untracked-files=normal"):
            raise QueueError("source_worktree_dirty")
        return sha

    def repository(self) -> Path:
        git = "/usr/bin/git" if sys.platform == "darwin" else "git"
        return Path(
            call(
                git,
                "-C",
                str(self.project),
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            )
        ).resolve(strict=True)

    def next(self) -> dict:
        """Resume one registered request from this repository, never a new task."""
        self.initialize()
        pending = [job for job in self.records() if job["status"] in PENDING]
        if not pending:
            return {"status": "idle", "reason": "queue_empty", "notify": False}
        job = pending[0]
        if not Path(job["project"]).is_dir():
            with self.lock():
                job.update(status="invalidated", reason="source_removed")
                return self.report(job)
        target = BuildQueue(self.home, Path(job["project"]))
        if target.repository() != self.repository():
            raise QueueError("queue_repository_mismatch")
        return target.resume(job["task_id"], job["job_id"])

    @staticmethod
    def owner(pid: int) -> str | None:
        try:
            text = call("ps", "-p", str(pid), "-o", "lstart=", "-o", "comm=")
        except QueueError:
            return None
        return hashlib.sha256(text.encode()).hexdigest() if text else None

    def snapshot(self) -> dict:
        return capacity(self.home)

    @staticmethod
    def key(task: str, project: str, sha: str, refresh: bool) -> str:
        return hashlib.sha256(json.dumps([task, project, sha, refresh]).encode()).hexdigest()

    def records(self) -> list[dict]:
        result = []
        for path in self.directory.glob("*.json"):
            job = load(path)
            if not isinstance(job.get("refresh"), bool) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", job.get("task_id", "")
            ):
                raise QueueError("queue_record_invalid")
            expected = self.key(job["task_id"], job["project"], job["source_sha"], job["refresh"])
            if job.get("job_id") != expected or path.stem != expected:
                raise QueueError("queue_identity_mismatch")
            result.append(job)
        return sorted(result, key=lambda job: (job["created_at"], job["job_id"]))

    @contextmanager
    def lock(self):
        path = self.home / "operation.lock"
        try:
            path.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise QueueError("operation_busy") from exc
        identity = path.stat()
        try:
            yield
        finally:
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (
                identity.st_dev,
                identity.st_ino,
            ) or not stat.S_ISDIR(current.st_mode):
                raise QueueError("operation_lock_changed")
            path.rmdir()  # Never remove foreign/stale locks or unknown contents.

    def report(self, job: dict, reason: str | None = None, persist: bool = True) -> dict:
        reason = reason or job.get("reason", job["status"])
        key = reason if reason not in TRANSIENT else "wait_24h"
        notify = False
        if reason not in TRANSIENT or time.time() - job["created_at"] >= 86400:
            notice = (
                self.directory
                / "notices"
                / hashlib.sha256((job["job_id"] + key).encode()).hexdigest()
            )
            try:
                descriptor = os.open(notice, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if notice.is_symlink() or not notice.is_file():
                    raise QueueError("queue_notice_unsafe")
            else:
                os.close(descriptor)
                notify = True
        if persist:
            save(self.directory / (job["job_id"] + ".json"), job)
        LOG.info("build_queue status=%s reason=%s", job["status"], reason)
        return {
            "job_id": job["job_id"],
            "task_id": job["task_id"],
            "source_sha": job["source_sha"],
            "status": job["status"] if persist else "waiting_resources",
            "reason": reason,
            "notify": notify,
            "image": job.get("image"),
        }

    def reconcile(self, records: list[dict]) -> list[dict]:
        """Consume every durable completion before FIFO, including dead owners."""
        for job in records:
            result_path = self.directory / "results" / (job["job_id"] + ".json")
            if job["status"] != "running" or not result_path.exists():
                continue
            result = load(result_path)
            if (
                result.get("job_id") != job["job_id"]
                or result.get("owner_stamp") != job["owner_stamp"]
            ):
                raise QueueError("queue_result_mismatch")
            job.update(result)
            if job["status"] == "completed" and not self.artifact_valid(job):
                job.update(status="invalidated", reason="artifact_missing_or_changed")
            save(self.directory / (job["job_id"] + ".json"), job)
            if job["status"] == "waiting_resources":
                result_path.unlink()
        return records

    def submit(self, task: str, refresh: bool) -> dict:
        self.initialize()
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", task):
            raise QueueError("task_id_invalid")
        sha = self.source()
        identity = self.key(task, str(self.project), sha, refresh)
        job = {
            "schema_version": 1,
            "job_id": identity,
            "task_id": task,
            "project": str(self.project),
            "source_sha": sha,
            "refresh": refresh,
            "created_at": time.time(),
            "status": "waiting_resources",
            "notices": [],
        }
        save(self.directory / (identity + ".json"), job, exclusive=True)
        return self.resume(task, identity)

    def artifact_valid(self, job: dict) -> bool:
        for key in ("image", "development_image"):
            image = job.get(key, "")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                return False
            try:
                revision = call(
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "org.opencontainers.image.revision"}}',
                    image,
                )
            except QueueError:
                return False
            if revision != job["source_sha"]:
                return False
        return True

    def resume(self, task: str, identity: str | None = None) -> dict:
        self.initialize()
        records = self.records()
        matches = [
            job for job in records if job["task_id"] == task and job["project"] == str(self.project)
        ]
        if not matches:
            raise QueueError("queue_task_not_found")
        pending = [job for job in matches if job["status"] in PENDING]
        job = (
            next((row for row in matches if row["job_id"] == identity), None)
            if identity
            else (pending[0] if pending else matches[-1])
        )
        if job is None:
            raise QueueError("queue_task_not_found")
        try:
            with self.lock():
                # Reread after acquiring the shared lock: no stale claims/notices.
                before = self.records()
                current = next(row for row in before if row["job_id"] == job["job_id"])
                had_result = (
                    current["status"] == "running"
                    and (self.directory / "results" / (job["job_id"] + ".json")).exists()
                )
                records = self.reconcile(before)
                job = next(row for row in records if row["job_id"] == job["job_id"])
                if self.source() != job["source_sha"]:
                    job.update(status="invalidated", reason="source_changed")
                    return self.report(job)
                if had_result:
                    return self.report(job)
                if job["status"] == "completed":
                    if not self.artifact_valid(job):
                        job.update(status="invalidated", reason="artifact_missing_or_changed")
                    return self.report(job)
                if job["status"] not in PENDING:
                    return self.report(job)
                for other in records:
                    if (
                        other["status"] == "running"
                        and self.owner(other["owner_pid"]) == other["owner_stamp"]
                    ):
                        return self.report(job, "build_active")
                ahead = [
                    row
                    for row in records
                    if row["status"] in PENDING
                    and row["job_id"] != job["job_id"]
                    and (row["created_at"], row["job_id"]) < (job["created_at"], job["job_id"])
                ]
                if ahead:
                    return self.report(job, "queue_ahead")
                snapshot = self.snapshot()
                # Our lock is expected here, but every other admission gate remains.
                if snapshot["reason"] == "operation_busy":
                    snapshot["ready"] = snapshot["required_bytes"] <= snapshot["vm_bytes"]
                    snapshot["reason"] = "ready" if snapshot["ready"] else "vm_memory_budget"
                if not snapshot["ready"]:
                    job.update(status="waiting_resources", reason=snapshot["reason"])
                    return self.report(job)
                stamp = self.owner(os.getpid())
                if stamp is None:
                    raise QueueError("queue_owner_unavailable")
                job.update(
                    status="running",
                    reason="building",
                    owner_pid=os.getpid(),
                    owner_stamp=stamp,
                )
                save(self.directory / (job["job_id"] + ".json"), job)
        except QueueError as exc:
            if str(exc) != "operation_busy":
                raise
            # Busy locks are never removed. Initial enqueue is already durable.
            return self.report(job, "operation_busy", persist=False)
        # The legacy shell reacquires the SAME lock and checks capacity again.
        # A competing operation in this short handoff cannot bypass admission.
        try:
            code, reason = self.execute(job)
        except (QueueError, OSError, tarfile.TarError) as exc:
            code, reason = 1, "build_context_failed"
            LOG.error("queued_build_failed category=%s", type(exc).__name__)
        except KeyboardInterrupt:
            code, reason = 130, "cancelled"
        job.update(status="completed" if code == 0 else "failed", reason=reason)
        if reason in TRANSIENT:
            job.update(status="waiting_resources")
        if reason in {
            "builder_cleanup_incomplete",
            "context_cleanup_incomplete",
            "build_context_failed",
        }:
            job.update(status="blocked")
        # Persist completion before competing operations can delay finalization.
        # Resume consumes this result rather than starting a second build.
        save(self.directory / "results" / (job["job_id"] + ".json"), job)
        return self.resume(task, job["job_id"])

    def execute(self, job: dict) -> tuple[int, str]:
        """Archive committed bytes; concurrent worktree edits cannot enter a build."""
        result = None
        try:
            with tempfile.TemporaryDirectory(
                prefix=job["job_id"] + "-", dir=self.directory / "contexts"
            ) as folder:
                context = Path(folder)
                archive = context / "source.tar"
                git = "/usr/bin/git" if sys.platform == "darwin" else "git"
                call(
                    git,
                    "-C",
                    str(self.project),
                    "archive",
                    "--format=tar",
                    "--output=" + str(archive),
                    job["source_sha"],
                )
                source = context / "source"
                source.mkdir(mode=0o700)
                with tarfile.open(archive) as bundle:
                    bundle.extractall(source, filter="data")
                result = self.run_build(job, source)
        except OSError:
            if result is None:
                raise
            # A completed build followed by failed context cleanup must not be
            # mistaken for a dead request and executed a second time.
            return 1, "context_cleanup_incomplete"
        if result is None:
            raise QueueError("build_result_missing")
        return result

    def run_build(self, job: dict, context: Path) -> tuple[int, str]:
        log = self.home / "logs" / ("build-" + job["job_id"] + "-" + uuid.uuid4().hex + ".log")
        args = [str(context / "rwb-docker"), "build"]
        if job["refresh"]:
            args.append("--refresh-dsh")
        env = dict(
            os.environ,
            RWB_DOCKER_HOME=str(self.home),
            RWB_DELIVERY_TASK_ID=job["task_id"],
            RWB_QUEUE_CONTEXT=str(context),
            RWB_QUEUE_SOURCE_SHA=job["source_sha"],
            RWB_QUEUE_PYTHON=sys.executable,
        )
        interrupted = False
        with log.open("x", encoding="utf-8") as stream:
            log.chmod(0o600)
            child = subprocess.Popen(
                args, stdout=stream, stderr=stream, env=env, start_new_session=True
            )

            def cancel(_signum, _frame):
                nonlocal interrupted
                interrupted = True
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)

            previous = {sig: signal.signal(sig, cancel) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                code = child.wait()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        with log.open() as stream:
            lines = list(deque(stream, maxlen=64))
        # The shell reports its own identity-verified cleanup while holding the
        # lock. Inspecting a builder AFTER release could inspect somebody else's.
        if any(line.strip() == "queue_builder_cleanup=blocked" for line in lines):
            return 1, "builder_cleanup_incomplete"
        if code:
            reason = "build_failed"
            for line in lines:
                if "docker_operation_busy" in line:
                    reason = "operation_busy"
                elif "vm_budget_requires_stopping_dev_or_16g_vm" in line:
                    reason = "vm_memory_budget"
                elif "stop_stage_before_cold_build" in line:
                    reason = "stage_active"
                elif line.startswith('{"ready":'):
                    reason = json.loads(line)["reason"]
            return code, "cancelled" if interrupted else reason
        if not any(line.strip() == "queue_builder_cleanup=stopped" for line in lines):
            return 1, "builder_cleanup_incomplete"
        for line in lines:
            if line.startswith("candidate_image="):
                job["image"] = line.strip().partition("=")[2]
            elif line.startswith("development_image="):
                job["development_image"] = line.strip().partition("=")[2]
        if not self.artifact_valid(job):
            return 1, "artifact_missing_or_changed"
        return 0, "completed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capacity", "admit", "submit", "resume"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--refresh-dsh", action="store_true")
    args = parser.parse_args()
    try:
        if args.action in {"capacity", "admit"}:
            snapshot = capacity(args.home)
            if args.action == "admit" and snapshot["reason"] == "operation_busy":
                snapshot["ready"] = snapshot["required_bytes"] <= snapshot["vm_bytes"]
                snapshot["reason"] = "ready" if snapshot["ready"] else "vm_memory_budget"
            print(json.dumps(snapshot))
            return 0 if args.action == "capacity" or snapshot["ready"] else 75
        if not args.task_id and not (args.action == "resume" and args.next):
            raise QueueError("task_id_required")
        if args.next and args.task_id:
            raise QueueError("queue_arguments_invalid")
        manager = BuildQueue(args.home, args.project)
        manager.initialize()
        log_path = args.home / "logs" / "build-queue.log"
        if log_path.is_symlink():
            raise QueueError("queue_log_alias")
        os.umask(0o077)
        logging.basicConfig(filename=log_path, level=logging.INFO)
        result = (
            manager.next()
            if args.next
            else (
                manager.submit(args.task_id, args.refresh_dsh)
                if args.action == "submit"
                else manager.resume(args.task_id)
            )
        )
        print(json.dumps(result))
        return (
            0
            if result["status"] in {"completed", "idle"}
            else 75 if result["status"] == "waiting_resources" else 1
        )
    except (QueueError, OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        code = str(exc) if isinstance(exc, QueueError) else "queue_state_unavailable"
        LOG.error("build_queue refused=%s", code)
        print(json.dumps({"status": "blocked", "reason": code, "notify": True}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
