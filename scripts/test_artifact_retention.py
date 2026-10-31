"""Register and retire local pytest temp roots after independent PASS evidence is sealed."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

try:
    import fcntl
except ImportError:
    fcntl = None

log = logging.getLogger(__name__)
TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_ACTIVE_ROOT_BYTES = 512 * 1024 * 1024
FREE_FLOOR_BYTES = 3 * 1024**3


class RetentionError(RuntimeError):
    """A stable fail-closed reason for an unretired test root."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _free(path: Path) -> int:
    status = os.statvfs(path)
    return status.f_bavail * status.f_frsize


@contextmanager
def _task_lock(parent: Path, task_id: str):
    if fcntl is None:
        raise RetentionError("platform_lock_unavailable")
    lock = parent / f".rwb-test-{task_id}.lock"
    try:
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise RetentionError("task_lock_busy_or_invalid") from error
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise RetentionError("task_lock_identity")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            raise RetentionError("task_lock_busy_or_invalid") from error
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _save(path: Path, record: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except (OSError, ValueError, TypeError):
        temporary.unlink(missing_ok=True)
        raise


def _phase(path: Path, record: dict, status: str) -> None:
    record["status"] = status
    record.setdefault("history", []).append({"status": status, "at": _now()})
    _save(path, record)
    log.info("test_temp_retention status=%s task=%s", status, record["taskId"])


def _load(receipt: Path) -> dict:
    info = receipt.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise RetentionError("receipt_identity")
    try:
        record = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RetentionError("receipt_invalid") from error
    if record.get("schemaVersion") != 1 or not TASK_ID.fullmatch(record.get("taskId", "")):
        raise RetentionError("receipt_invalid")
    return record


def _owner(record: dict, root: Path) -> None:
    try:
        info = root.lstat()
        marker = root / "owner.json"
        mark = marker.lstat()
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RetentionError("root_identity") from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or (info.st_dev, info.st_ino) != (record["device"], record["inode"])
        or not root.name.startswith(f"rwb-test-{record['taskId']}-")
        or not stat.S_ISREG(mark.st_mode)
        or mark.st_nlink != 1
        or value
        != {
            key: record[key]
            for key in (
                "taskId",
                "candidate",
                "root",
                "uid",
                "device",
                "inode",
                "nonce",
                "batchId",
                "nodeIds",
                "exactCheckout",
            )
        }
    ):
        raise RetentionError("root_identity")


def _evidence(path: Path, proof_root: Path) -> dict:
    path = path.absolute()
    try:
        if path.resolve() != path or not path.is_relative_to(proof_root):
            raise RetentionError("evidence_identity")
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_size > MAX_EVIDENCE_BYTES
        ):
            raise RetentionError("evidence_identity")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as error:
        raise RetentionError("evidence_identity") from error
    return {"path": str(path), "sha256": digest, "bytes": info.st_size}


def _junit_passed(path: Path) -> dict:
    try:
        xml = ElementTree.parse(path).getroot()
        suites = list(xml.iter("testsuite"))
        counts = {
            name: sum(int(suite.attrib.get(name, "0")) for suite in suites)
            for name in ("tests", "failures", "errors", "skipped")
        }
        cases = sum(1 for _ in xml.iter("testcase"))
        embedded_failures = any(node.tag in {"failure", "error"} for node in xml.iter())
    except (OSError, ValueError, ElementTree.ParseError) as error:
        raise RetentionError("junit_invalid") from error
    if (
        counts["tests"] < 1
        or counts["tests"] != cases
        or counts["failures"]
        or counts["errors"]
        or embedded_failures
    ):
        raise RetentionError("junit_not_passed")
    return counts


def _batch_result(path: Path, proof_root: Path, record: dict, files: dict, counts: dict) -> dict:
    identity = _evidence(path, proof_root)
    try:
        value = json.loads(Path(identity["path"]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RetentionError("batch_result_invalid") from error
    required = {
        "schemaVersion",
        "taskId",
        "candidate",
        "rootNonce",
        "batchId",
        "nodeIds",
        "exitCode",
        "junitSha256",
        "stdoutSha256",
        "stderrSha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["schemaVersion"] != 1
        or value["taskId"] != record["taskId"]
        or value["candidate"] != record["candidate"]
        or value["rootNonce"] != record["nonce"]
        or value["batchId"] != record["batchId"]
        or value["nodeIds"] != record["nodeIds"]
        or len(record["nodeIds"]) != counts["tests"]
        or type(value["exitCode"]) is not int
        or value["exitCode"] != 0
        or value["junitSha256"] != files["junit"]["sha256"]
        or value["stdoutSha256"] != files["stdout"]["sha256"]
        or value["stderrSha256"] != files["stderr"]["sha256"]
    ):
        raise RetentionError("batch_result_not_passed")
    return {**identity, "batchId": value["batchId"], "nodeIds": value["nodeIds"]}


def _has_open_files(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-Fn"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RetentionError("open_file_inventory") from error
    if result.returncode != 0:
        raise RetentionError("open_file_inventory")
    prefix = str(root) + "/"
    return any(
        line.startswith("n") and (line[1:] == str(root) or line[1:].startswith(prefix))
        for line in result.stdout.splitlines()
    )


def _scan(root: Path, device: int) -> dict:
    counts: Counter[tuple[int, int]] = Counter()
    links = {}
    bytes_by_inode = {}
    entries = {}
    folders = 0
    symlinks = 0

    def onerror(error: OSError) -> None:
        raise error

    try:
        for folder, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
            directory = Path(folder)
            paths = ([directory] if directory == root else []) + [
                directory / item for item in dirs + files
            ]
            for name in paths:
                info = name.lstat()
                if (
                    info.st_uid != os.getuid()
                    or info.st_dev != device
                    or getattr(info, "st_flags", 0)
                ):
                    raise RetentionError("nested_identity")
                relative = "." if name == root else name.relative_to(root).as_posix()
                entry = {"device": info.st_dev, "inode": info.st_ino}
                if stat.S_ISDIR(info.st_mode):
                    folders += 1
                    entry["kind"] = "directory"
                elif stat.S_ISLNK(info.st_mode):
                    symlinks += 1
                    entry.update(kind="symlink", target=os.readlink(name))
                elif stat.S_ISREG(info.st_mode):
                    identity = (info.st_dev, info.st_ino)
                    counts[identity] += 1
                    links[identity] = info.st_nlink
                    bytes_by_inode[identity] = info.st_size
                    with name.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    entry.update(kind="file", bytes=info.st_size, sha256=digest)
                else:
                    raise RetentionError("nested_special_file")
                entries[relative] = entry
    except OSError as error:
        raise RetentionError("nested_inventory") from error
    if any(counts[identity] != links[identity] for identity in counts):
        raise RetentionError("external_hardlink")
    return {
        "files": sum(counts.values()),
        "uniqueFiles": len(counts),
        "directories": folders,
        "symlinks": symlinks,
        "logicalBytes": sum(bytes_by_inode.values()),
        "entries": entries,
    }


def _assert_contents(root: Path, record: dict, *, allow_removed: bool) -> None:
    expected = record["contents"]["entries"]
    current = _scan(root, record["device"])["entries"]
    if not allow_removed and current != expected:
        raise RetentionError("root_contents_changed")
    if allow_removed and (
        "." not in current or any(expected.get(path) != value for path, value in current.items())
    ):
        raise RetentionError("root_contents_changed")


def _make_writable(root: Path, device: int) -> int:
    repaired = 0

    def onerror(error: OSError) -> None:
        raise error

    try:
        for folder, dirs, _files in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
            for path in [Path(folder), *(Path(folder) / name for name in dirs)]:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    continue
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_dev != device
                ):
                    raise RetentionError("nested_identity")
                mode = stat.S_IMODE(info.st_mode)
                if not mode & stat.S_IWUSR:
                    os.chmod(path, mode | stat.S_IWUSR, follow_symlinks=False)
                    repaired += 1
    except OSError as error:
        raise RetentionError("permission_repair_failed") from error
    return repaired


def create_root(
    parent: Path,
    receipt: Path,
    *,
    task_id: str,
    candidate: str,
    batch_id: str,
    node_ids: list[str],
    _exact_checkout: bool = False,
) -> Path:
    parent, receipt = Path(parent).absolute(), Path(receipt).absolute()
    if not TASK_ID.fullmatch(task_id) or not SHA.fullmatch(candidate):
        raise RetentionError("task_or_candidate_invalid")
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", batch_id)
        or not isinstance(node_ids, list)
        or not 1 <= len(node_ids) <= 20
        or any(
            not isinstance(node, str) or not node.startswith("tests/") or "::" not in node
            for node in node_ids
        )
        or len(node_ids) != len(set(node_ids))
    ):
        raise RetentionError("batch_identity_invalid")
    if _exact_checkout:
        _checkout_identity(candidate, mode="exact")
    if receipt.exists() or receipt.is_symlink():
        raise RetentionError("receipt_already_exists")
    parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    if (
        parent.resolve() != parent
        or receipt.parent.resolve() != receipt.parent
        or receipt.is_relative_to(parent)
    ):
        raise RetentionError("parent_alias")
    with _task_lock(parent, task_id):
        if _free(parent) < FREE_FLOOR_BYTES:
            raise RetentionError("disk_floor")
        if (
            receipt.exists()
            or receipt.is_symlink()
            or any(
                path.exists() or path.is_symlink() for path in parent.glob(f"rwb-test-{task_id}-*")
            )
        ):
            raise RetentionError("task_root_active")
        root = Path(tempfile.mkdtemp(prefix=f"rwb-test-{task_id}-", dir=parent))
        info = root.lstat()
        record = {
            "schemaVersion": 1,
            "taskId": task_id,
            "candidate": candidate,
            "root": str(root),
            "parent": str(parent),
            "parentDevice": parent.stat().st_dev,
            "parentInode": parent.stat().st_ino,
            "uid": os.getuid(),
            "device": info.st_dev,
            "inode": info.st_ino,
            "nonce": uuid.uuid4().hex,
            "batchId": batch_id,
            "nodeIds": list(node_ids),
            "exactCheckout": _exact_checkout,
            "history": [],
        }
        marker = {
            key: record[key]
            for key in (
                "taskId",
                "candidate",
                "root",
                "uid",
                "device",
                "inode",
                "nonce",
                "batchId",
                "nodeIds",
                "exactCheckout",
            )
        }
        try:
            descriptor = os.open(
                root / "owner.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(marker, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            _phase(receipt, record, "active")
        except (OSError, ValueError, TypeError):
            shutil.rmtree(root)
            raise
    return root


def admit_batch(receipt: Path) -> dict:
    receipt = Path(receipt).absolute()
    record = _load(receipt)
    parent = Path(record["parent"])
    with _task_lock(parent, record["taskId"]):
        if record["status"] != "active":
            raise RetentionError("root_not_active")
        root = Path(record["root"])
        _owner(record, root)
        size = _scan(root, record["device"])["logicalBytes"]
        if size > MAX_ACTIVE_ROOT_BYTES:
            raise RetentionError("active_root_budget")
        free = _free(parent)
        if free < FREE_FLOOR_BYTES:
            raise RetentionError("disk_floor")
        return {"status": "admitted", "logicalBytes": size, "freeBytes": free}


def _usage_bytes(root: Path) -> int:
    seen = set()
    total = 0

    def onerror(error: OSError) -> None:
        raise error

    for folder, _dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        for name in files:
            try:
                info = (Path(folder) / name).lstat()
            except FileNotFoundError:
                continue
            identity = (info.st_dev, info.st_ino)
            if stat.S_ISREG(info.st_mode) and identity not in seen:
                seen.add(identity)
                total += info.st_size
    return total


def _bounded_hash(path: Path) -> str | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EVIDENCE_BYTES:
            return None
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as stream:
            while chunk := stream.read(65536):
                total += len(chunk)
                if total > MAX_EVIDENCE_BYTES:
                    return None
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _capacity_reason(root: Path, files: dict[str, Path]) -> str | None:
    try:
        if _free(root.parent) < FREE_FLOOR_BYTES:
            return "disk_floor_during_test"
        if _usage_bytes(root) > MAX_ACTIVE_ROOT_BYTES:
            return "active_root_budget_during_test"
        output_bytes = 0
        for name in ("junit", "stdout", "stderr"):
            path = files[name]
            if path.is_symlink():
                return "capacity_probe_failed"
            if path.exists():
                size = path.lstat().st_size
                if size > MAX_EVIDENCE_BYTES:
                    return "batch_output_budget_during_test"
                output_bytes += size
        if output_bytes > MAX_EVIDENCE_BYTES:
            return "batch_output_budget_during_test"
    except (OSError, RetentionError):
        return "capacity_probe_failed"
    return None


def _checkout_identity(candidate: str, *, mode: str = "exact") -> Path:
    if mode not in {"exact", "wip"}:
        raise RetentionError("checkout_mode_invalid")

    def git(*args: str) -> str:
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/git",
                    "--no-optional-locks",
                    "-c",
                    "gc.auto=0",
                    "-c",
                    "maintenance.auto=false",
                    *args,
                ],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RetentionError("checkout_identity_unknown") from error
        if completed.returncode != 0:
            raise RetentionError("checkout_identity_unknown")
        return completed.stdout.strip()

    root = Path(git("rev-parse", "--show-toplevel"))
    if root.resolve() != root or git("rev-parse", "HEAD") != candidate:
        raise RetentionError("candidate_head_mismatch")
    if mode == "exact" and git("status", "--porcelain=v1", "--untracked-files=all"):
        raise RetentionError("candidate_worktree_dirty")
    return root


def _terminate_owned(process: subprocess.Popen) -> int:
    for signal_number, timeout in ((signal.SIGTERM, 20), (signal.SIGKILL, 10)):
        try:
            os.killpg(process.pid, signal_number)
        except ProcessLookupError:
            pass
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
    raise RetentionError("pytest_process_unstoppable")


def run_batch(
    parent: Path,
    receipt: Path,
    *,
    task_id: str,
    candidate: str,
    batch_id: str,
    node_ids: list[str],
    python: Path,
    mode: str = "exact",
) -> dict:
    receipt = Path(receipt).absolute()
    checkout = _checkout_identity(candidate, mode=mode)
    proof = receipt.parent
    files = {
        "junit": proof / f"{batch_id}.xml",
        "stdout": proof / f"{batch_id}.stdout",
        "stderr": proof / f"{batch_id}.stderr",
        "result": proof / f"{batch_id}.result.json",
    }
    if any(path.exists() or path.is_symlink() for path in files.values()):
        raise RetentionError("batch_evidence_already_exists")
    root = create_root(
        parent,
        receipt,
        task_id=task_id,
        candidate=candidate,
        batch_id=batch_id,
        node_ids=node_ids,
        _exact_checkout=mode == "exact",
    )
    command = [
        str(python),
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--confcutdir=tests/research_web",
        "-q",
        "--tb=short",
        f"--basetemp={root / 'active'}",
        f"--junitxml={files['junit']}",
        *node_ids,
    ]
    with files["stdout"].open("wb") as stdout, files["stderr"].open("wb") as stderr:
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            cwd=checkout,
        )
        deadline = time.monotonic() + 900
        stop_reason = None
        try:
            while True:
                try:
                    exit_code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    stop_reason = (
                        "pytest_timeout"
                        if time.monotonic() >= deadline
                        else _capacity_reason(root, files)
                    )
                    if stop_reason is None:
                        continue
                    exit_code = _terminate_owned(process)
                break
            if stop_reason is None:
                stop_reason = _capacity_reason(root, files)
        finally:
            if process.poll() is None:
                _terminate_owned(process)
    if stop_reason is None and exit_code == 0 and mode == "exact":
        try:
            _checkout_identity(candidate, mode="exact")
        except RetentionError:
            stop_reason = "source_changed_during_test"
    owner = _load(receipt)
    result = {
        "schemaVersion": 1,
        "taskId": task_id,
        "candidate": candidate,
        "rootNonce": owner["nonce"],
        "batchId": batch_id,
        "nodeIds": node_ids,
        "exitCode": exit_code,
        "junitSha256": _bounded_hash(files["junit"]),
        "stdoutSha256": _bounded_hash(files["stdout"]),
        "stderrSha256": _bounded_hash(files["stderr"]),
    }
    _save(files["result"], result)
    if stop_reason is not None:
        if stop_reason == "source_changed_during_test":
            owner["sourceDrifted"] = True
            _phase(receipt, owner, "source_changed")
        raise RetentionError(stop_reason)
    if exit_code != 0:
        raise RetentionError("pytest_failed")
    return retire_root(
        receipt,
        files["junit"],
        files["stdout"],
        files["stderr"],
        files["result"],
    )


def _retire_root_under_lock(
    receipt: Path,
    junit: Path,
    stdout: Path,
    stderr: Path,
    result: Path,
    *,
    open_files=None,
) -> dict:
    receipt = Path(receipt).absolute()
    record = _load(receipt)
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RetentionError("safe_rmtree_unavailable")
    root = Path(record["root"])
    parent = Path(record["parent"])
    quarantine_path = Path(record["quarantine"]) if record.get("quarantine") else None
    if receipt.is_relative_to(root) or any(
        Path(path).absolute().is_relative_to(root)
        or (quarantine_path is not None and Path(path).absolute().is_relative_to(quarantine_path))
        for path in (junit, stdout, stderr, result)
    ):
        raise RetentionError("evidence_inside_root")
    if (
        parent.resolve() != parent
        or (parent.stat().st_dev, parent.stat().st_ino)
        != (record["parentDevice"], record["parentInode"])
        or root.parent != parent
    ):
        raise RetentionError("parent_identity")
    if record["status"] not in {"active", "sealed", "intent", "quarantined", "delete_intent"}:
        raise RetentionError("receipt_status")
    proof_root = receipt.parent
    files = {
        name: _evidence(Path(path), proof_root)
        for name, path in (("junit", junit), ("stdout", stdout), ("stderr", stderr))
    }
    counts = _junit_passed(Path(files["junit"]["path"]))
    batch = _batch_result(result, proof_root, record, files, counts)
    if record["status"] == "active":
        _owner(record, root)
        record["evidence"] = files
        record["batchResult"] = batch
        record["junitCounts"] = counts
        _phase(receipt, record, "sealed")
    elif (
        record.get("evidence") != files
        or record.get("batchResult") != batch
        or record.get("junitCounts") != counts
    ):
        raise RetentionError("sealed_evidence_changed")

    checker = open_files or _has_open_files
    if record["status"] == "sealed":
        _owner(record, root)
        if checker(root):
            raise RetentionError("root_in_use")
        record["contents"] = _scan(root, record["device"])
        quarantine = Path(tempfile.mkdtemp(prefix=".rwb-test-retire-", dir=parent))
        record["quarantine"] = str(quarantine)
        record["quarantineDevice"] = quarantine.stat().st_dev
        record["quarantineInode"] = quarantine.stat().st_ino
        record["freeBefore"] = _free(parent)
        _phase(receipt, record, "intent")

    quarantine = Path(record["quarantine"])
    if (
        quarantine.parent != parent
        or not quarantine.name.startswith(".rwb-test-retire-")
        or (quarantine.lstat().st_dev, quarantine.lstat().st_ino)
        != (record["quarantineDevice"], record["quarantineInode"])
    ):
        raise RetentionError("quarantine_identity")
    target = quarantine / root.name
    if record["status"] == "intent":
        if root.exists() and not target.exists():
            _owner(record, root)
            if checker(root):
                raise RetentionError("root_in_use")
            _assert_contents(root, record, allow_removed=False)
            parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            quarantine_fd = os.open(quarantine, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.rename(root.name, root.name, src_dir_fd=parent_fd, dst_dir_fd=quarantine_fd)
                os.fsync(parent_fd)
                os.fsync(quarantine_fd)
            finally:
                os.close(quarantine_fd)
                os.close(parent_fd)
        elif root.exists() or not target.exists():
            raise RetentionError("quarantine_transition")
        _owner(record, target)
        _assert_contents(target, record, allow_removed=False)
        _phase(receipt, record, "quarantined")

    if root.exists():
        raise RetentionError("root_reappeared")
    if target.exists():
        if record["status"] == "delete_intent":
            remaining_root = target.lstat()
            if (
                not stat.S_ISDIR(remaining_root.st_mode)
                or remaining_root.st_uid != os.getuid()
                or (remaining_root.st_dev, remaining_root.st_ino)
                != (record["device"], record["inode"])
            ):
                raise RetentionError("quarantine_identity")
        else:
            _owner(record, target)
        if checker(target):
            raise RetentionError("root_in_use")
        _assert_contents(target, record, allow_removed=record["status"] == "delete_intent")
        record["permissionRepairs"] = _make_writable(target, record["device"])
        _phase(receipt, record, "delete_intent")
        quarantine_fd = os.open(quarantine, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            current = os.stat(root.name, dir_fd=quarantine_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (record["device"], record["inode"]):
                raise RetentionError("quarantine_identity")
            _assert_contents(target, record, allow_removed=True)
            shutil.rmtree(root.name, dir_fd=quarantine_fd)
            os.fsync(quarantine_fd)
        finally:
            os.close(quarantine_fd)
    elif record["status"] != "delete_intent":
        raise RetentionError("quarantine_missing")
    quarantine.rmdir()
    record["freeAfter"] = _free(parent)
    record["physicalReclaimedBytes"] = record["freeAfter"] - record["freeBefore"]
    _phase(receipt, record, "retired")
    return record


def retire_root(
    receipt: Path,
    junit: Path,
    stdout: Path,
    stderr: Path,
    result: Path,
    *,
    open_files=None,
) -> dict:
    receipt = Path(receipt).absolute()
    record = _load(receipt)
    with _task_lock(Path(record["parent"]), record["taskId"]):
        if record.get("exactCheckout") is True:
            _checkout_identity(record["candidate"], mode="exact")
        return _retire_root_under_lock(
            receipt, junit, stdout, stderr, result, open_files=open_files
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--parent", type=Path, required=True)
    create.add_argument("--receipt", type=Path, required=True)
    create.add_argument("--task-id", required=True)
    create.add_argument("--candidate", required=True)
    create.add_argument("--batch-id", required=True)
    create.add_argument("--node-id", action="append", required=True)
    run = sub.add_parser("run")
    run.add_argument("--parent", type=Path, required=True)
    run.add_argument("--receipt", type=Path, required=True)
    run.add_argument("--task-id", required=True)
    run.add_argument("--candidate", required=True)
    run.add_argument("--batch-id", required=True)
    run.add_argument("--node-id", action="append", required=True)
    run.add_argument("--python", type=Path, default=Path(sys.executable))
    run.add_argument("--mode", choices=("exact", "wip"), default="exact")
    admit = sub.add_parser("admit")
    admit.add_argument("--receipt", type=Path, required=True)
    retire = sub.add_parser("retire")
    retire.add_argument("--receipt", type=Path, required=True)
    retire.add_argument("--junit", type=Path, required=True)
    retire.add_argument("--stdout", type=Path, required=True)
    retire.add_argument("--stderr", type=Path, required=True)
    retire.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "create":
            root = create_root(
                args.parent,
                args.receipt,
                task_id=args.task_id,
                candidate=args.candidate,
                batch_id=args.batch_id,
                node_ids=args.node_id,
            )
            print(json.dumps({"status": "active", "root": str(root)}))
        elif args.action == "admit":
            print(json.dumps(admit_batch(args.receipt)))
        elif args.action == "run":
            record = run_batch(
                args.parent,
                args.receipt,
                task_id=args.task_id,
                candidate=args.candidate,
                batch_id=args.batch_id,
                node_ids=args.node_id,
                python=args.python,
                mode=args.mode,
            )
            print(
                json.dumps(
                    {
                        "status": record["status"],
                        "physicalReclaimedBytes": record["physicalReclaimedBytes"],
                    }
                )
            )
        else:
            record = retire_root(args.receipt, args.junit, args.stdout, args.stderr, args.result)
            print(
                json.dumps(
                    {
                        "status": record["status"],
                        "physicalReclaimedBytes": record["physicalReclaimedBytes"],
                    }
                )
            )
        return 0
    except (RetentionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, RetentionError) else "retention_io_error"
        log.error("test_temp_retention status=blocked code=%s", code)
        print(json.dumps({"status": "blocked", "code": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
