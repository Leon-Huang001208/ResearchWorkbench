"""Explicit, append-only cross-common evidence import; no ref or service mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import uuid4

from .admission import MaintenanceBusy, file_lock
from .maintenance_evidence import GitHubEvidence, UpdateBlocked

log = logging.getLogger(__name__)
LIMIT = 1_000_000
REPOSITORY = "Leon-Huang001208/ResearchWorkbench"


class MaintenanceParser(argparse.ArgumentParser):
    def error(self, message):
        print(
            json.dumps({"status": "blocked", "code": "maintenance_arguments_invalid"}),
            file=sys.stderr,
        )
        raise SystemExit(2)


class TransferBlocked(UpdateBlocked):
    """A stable reason; never turns missing evidence into an approval."""


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _no_links(path):
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise TransferBlocked("evidence_path_alias")


def _git(project, *args):
    try:
        return subprocess.run(
            [
                "/usr/bin/git",
                "--no-optional-locks",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(project),
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TransferBlocked("evidence_git_unavailable") from exc


def _common(project):
    _no_links(project)
    return Path(_git(project, "rev-parse", "--path-format=absolute", "--git-common-dir"))


def _remote(project):
    remote = _git(project, "remote", "get-url", "origin")
    if remote not in [
        f"git@github.com:{REPOSITORY}.git",
        f"https://github.com/{REPOSITORY}.git",
        f"https://github.com/{REPOSITORY}",
    ]:
        raise TransferBlocked("evidence_repository_mismatch")
    return REPOSITORY


def _read(path):
    _no_links(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_size > LIMIT
            ):
                raise TransferBlocked("evidence_record_invalid")
            if getattr(info, "st_flags", 0) & getattr(stat, "SF_DATALESS", 0x40000000):
                raise TransferBlocked("evidence_record_offline")
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT or not isinstance(json.loads(raw.decode("utf8")), dict):
            raise TransferBlocked("evidence_record_invalid")
        return raw
    except TransferBlocked:
        raise
    except (OSError, ValueError) as exc:
        raise TransferBlocked("evidence_record_unreadable") from exc


def _identity(common):
    _no_links(common)
    s = common.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid():
        raise TransferBlocked("evidence_common_invalid")
    return [s.st_dev, s.st_ino]


def _qualify(common, target, gh):
    return GitHubEvidence(Path(gh), REPOSITORY, common).qualify(target)


def preview(source, destination, task, target, gh=None):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", task or "") or not re.fullmatch(
        r"[a-f0-9]{40}", target or ""
    ):
        raise TransferBlocked("evidence_arguments_invalid")
    if _remote(source) != _remote(destination):
        raise TransferBlocked("evidence_repository_mismatch")
    src, dst = _common(source), _common(destination)
    identities = [_identity(src), _identity(dst)]
    if identities[0] == identities[1]:
        raise TransferBlocked("evidence_same_common")
    files = {}
    for folder in ["deliveries", "git-safety/reviews"]:
        rel = f"leon-engineering/{folder}/{task}.json"
        raw = _read(src / rel)
        files[rel] = {"sha256": _digest(raw), "bytes": len(raw)}
    record = json.loads(_read(src / f"leon-engineering/deliveries/{task}.json"))
    review = json.loads(_read(src / f"leon-engineering/git-safety/reviews/{task}.json"))
    if (
        record.get("remoteCommit") != target
        or record.get("status") not in ["ci_passed", "cleaned"]
        or record.get("mode") != "pr"
        or record.get("ci", {}).get("status") != "passed"
        or record.get("verification", {}).get("status") != "passed"
    ):
        raise TransferBlocked("evidence_delivery_unqualified")
    if review.get("status") != "PASS" or review.get("reviewedCommit") != record.get(
        "integrationCommit"
    ):
        raise TransferBlocked("evidence_review_missing_or_changed")
    executable = gh or shutil.which("gh")
    if not executable:
        raise TransferBlocked("evidence_gh_missing")
    proof = _qualify(src, target, executable)
    selected_pr = record.get("pullRequest")
    if (
        not isinstance(selected_pr, dict)
        or type(selected_pr.get("number")) is not int
        or proof.get("sha") != target
        or proof.get("head") != review["reviewedCommit"]
        or proof.get("pull_request") != selected_pr["number"]
    ):
        raise TransferBlocked("evidence_remote_mismatch")
    result = {
        "schema_version": 1,
        "source": str(source),
        "destination": str(destination),
        "task": task,
        "target": target,
        "common_identities": identities,
        "files": files,
        "gh": str(executable),
        "proof": proof,
    }
    result["seal"] = _digest(json.dumps(result, sort_keys=True).encode())
    log.info("resident_evidence_transfer_preview_verified")
    return result


def _private_dir(path):
    _no_links(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    for p in [path, *path.parents]:
        if p.name == ".git":
            break
        if p.stat().st_uid != os.getuid():
            raise TransferBlocked("evidence_directory_owner")


def _stage(path, raw):
    _private_dir(path.parent)
    temp = path.with_name("." + path.name + "." + uuid4().hex + ".transfer-staging")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return temp


def _fsync_parent(path):
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _atomic(path, raw):
    temp = _stage(path, raw)
    try:
        os.replace(temp, path)
        _fsync_parent(path)
    finally:
        if temp.exists():
            temp.unlink()


def _file_identity(path):
    _no_links(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise TransferBlocked("evidence_record_identity_invalid")
    return [info.st_dev, info.st_ino]


def _seal(plan):
    body = {k: v for k, v in plan.items() if k != "seal"}
    if plan.get("seal") != _digest(json.dumps(body, sort_keys=True).encode()):
        raise TransferBlocked("evidence_plan_changed")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", plan.get("task", "")):
        raise TransferBlocked("evidence_arguments_invalid")
    expected = {
        f"leon-engineering/{folder}/{plan['task']}.json"
        for folder in ("deliveries", "git-safety/reviews")
    }
    if set(plan["files"]) != expected:
        raise TransferBlocked("evidence_plan_paths_invalid")


@contextmanager
def repository_metadata_lock(common):
    """Share the managed Git writer fence; never remove a pre-existing lock."""
    folder = common / "leon-engineering/git-safety"
    _private_dir(folder)
    path = folder / "repository.lock"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise TransferBlocked("evidence_repository_busy") from exc
    nonce = uuid4().hex
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"pid": os.getpid(), "nonce": nonce}, f)
            f.flush()
            os.fsync(f.fileno())
        yield
    finally:
        current = path.lstat()
        if (
            current.st_dev != identity.st_dev
            or current.st_ino != identity.st_ino
            or path.is_symlink()
        ):
            raise TransferBlocked("evidence_repository_lock_changed")
        owner = json.loads(_read(path))
        if owner.get("nonce") != nonce or owner.get("pid") != os.getpid():
            raise TransferBlocked("evidence_repository_lock_changed")
        path.unlink()
        _fsync_parent(path)


@contextmanager
def repository_metadata_locks(commons):
    with ExitStack() as stack:
        for common in sorted(set(commons)):
            stack.enter_context(repository_metadata_lock(common))
        yield


def apply(plan):
    _seal(plan)
    try:
        current = preview(
            Path(plan["source"]),
            Path(plan["destination"]),
            plan["task"],
            plan["target"],
            plan["gh"],
        )
    except UpdateBlocked as exc:
        raise TransferBlocked("evidence_source_changed_or_unqualified") from exc
    if current != plan:
        raise TransferBlocked("evidence_source_changed")
    src, dst = _common(Path(plan["source"])), _common(Path(plan["destination"]))
    import_root = dst / "leon-engineering/evidence-imports"
    _private_dir(import_root)
    with (
        repository_metadata_locks([src, dst]),
        file_lock(import_root, "import.lock", exclusive=True),
    ):
        journal = import_root / (plan["task"] + ".json")
        state = json.loads(_read(journal)) if journal.exists() else None
        if state and (state.get("plan") != plan or state["state"] == "rolling_back"):
            raise TransferBlocked("evidence_journal_conflict")
        raws = {rel: _read(src / rel) for rel in plan["files"]}
        if state is None or state["state"] == "rolled_back":
            state = {
                "state": "prepared",
                "plan": plan,
                "created": {},
                "identities": {},
                "stages": {},
            }
            for rel in raws:
                state["created"][rel] = not (dst / rel).exists()
                if not state["created"][rel]:
                    state["identities"][rel] = _file_identity(dst / rel)
        for rel, raw in raws.items():
            if _digest(raw) != plan["files"][rel]["sha256"]:
                raise TransferBlocked("evidence_source_changed")
            target = dst / rel
            if target.exists():
                if _file_identity(target) != state["identities"].get(rel):
                    raise TransferBlocked("evidence_destination_conflict")
                old_stage = state["stages"].get(rel)
                if old_stage:
                    stage = target.parent / old_stage
                    if stage.exists():
                        if (
                            _file_identity(stage) != state["identities"][rel]
                            or stage.stat().st_nlink != 2
                        ):
                            raise TransferBlocked("evidence_stage_identity_changed")
                        stage.unlink()
                if _read(target) != raw:
                    raise TransferBlocked("evidence_destination_conflict")
        _atomic(journal, json.dumps(state, sort_keys=True).encode())
        # Exact review publication precedes delivery; link() cannot replace a
        # concurrently created destination, even when its bytes are identical.
        for rel in sorted(raws, key=lambda x: 0 if "/reviews/" in x else 1):
            target = dst / rel
            if target.exists():
                continue
            temp = _stage(target, raws[rel])
            state["identities"][rel] = _file_identity(temp)
            state["stages"][rel] = temp.name
            _atomic(journal, json.dumps(state, sort_keys=True).encode())
            try:
                try:
                    os.link(temp, target, follow_symlinks=False)
                except FileExistsError as exc:
                    raise TransferBlocked("evidence_destination_conflict") from exc
                _fsync_parent(target)
            finally:
                if temp.exists() and _file_identity(temp) == state["identities"][rel]:
                    temp.unlink()
        for rel, raw in raws.items():
            if _read(dst / rel) != raw:
                raise TransferBlocked("evidence_transfer_readback_failed")
        state["state"] = "verified"
        _atomic(journal, json.dumps(state, sort_keys=True).encode())
    log.info("resident_evidence_transfer_verified")
    return {
        "status": "verified",
        "target": plan["target"],
        "head": plan["proof"]["head"],
        "task": plan["task"],
    }


def verify(plan):
    """Observe imported exact bytes and requalify remote evidence; no state write."""
    _seal(plan)
    common = _common(Path(plan["destination"]))
    if _identity(common) != plan["common_identities"][1]:
        raise TransferBlocked("evidence_common_changed")
    for rel, expected in plan["files"].items():
        raw = _read(common / rel)
        if _digest(raw) != expected["sha256"] or len(raw) != expected["bytes"]:
            raise TransferBlocked("evidence_transfer_readback_failed")
    proof = _qualify(common, plan["target"], plan["gh"])
    if proof.get("sha") != plan["target"] or proof.get("head") != plan["proof"]["head"]:
        raise TransferBlocked("evidence_remote_mismatch")
    return {"status": "verified", "target": plan["target"]}


def load_plan(destination, task):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", task or ""):
        raise TransferBlocked("evidence_arguments_invalid")
    common = _common(Path(destination))
    state = json.loads(_read(common / "leon-engineering/evidence-imports" / (task + ".json")))
    plan = state["plan"]
    _seal(plan)
    if _identity(common) != plan["common_identities"][1]:
        raise TransferBlocked("evidence_common_changed")
    return plan


def rollback(plan, resident_home):
    """Only this import's unchanged inodes may be retired, under rebind's lock."""
    _seal(plan)
    common = _common(Path(plan["destination"]))
    if _identity(common) != plan["common_identities"][1]:
        raise TransferBlocked("evidence_common_changed")
    resident = Path(resident_home) / "resident"
    import_root = common / "leon-engineering/evidence-imports"
    with (
        file_lock(resident, "supervisor.lock", exclusive=True),
        repository_metadata_lock(common),
        file_lock(import_root, "import.lock", exclusive=True),
    ):
        config = json.loads(_read(resident / "config.json"))
        if Path(config["source_common"]).resolve() == common.resolve():
            raise TransferBlocked("evidence_rollback_target_in_use")
        journal = import_root / (plan["task"] + ".json")
        state = json.loads(_read(journal))
        if state.get("plan") != plan:
            raise TransferBlocked("evidence_journal_conflict")
        if state["state"] == "rolled_back":
            return {"status": "rolled_back"}
        for rel, created in state["created"].items():
            path = common / rel
            if not path.exists() and created and state["state"] in {"prepared", "rolling_back"}:
                continue
            if (
                _file_identity(path) != state["identities"].get(rel)
                or _digest(_read(path)) != plan["files"][rel]["sha256"]
            ):
                raise TransferBlocked("evidence_rollback_changed")
        state["state"] = "rolling_back"
        _atomic(journal, json.dumps(state, sort_keys=True).encode())
        for rel, created in state["created"].items():
            if created and (common / rel).exists():
                if (
                    _file_identity(common / rel) != state["identities"][rel]
                    or _digest(_read(common / rel)) != plan["files"][rel]["sha256"]
                ):
                    raise TransferBlocked("evidence_rollback_changed")
                (common / rel).unlink()
                _fsync_parent(common / rel)
        state["state"] = "rolled_back"
        _atomic(journal, json.dumps(state, sort_keys=True).encode())
    log.info("resident_evidence_transfer_rolled_back")
    return {"status": "rolled_back"}


def main():
    parser = MaintenanceParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("operation", choices=["preview", "apply", "verify", "rollback"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--target")
    parser.add_argument("--expected-seal")
    parser.add_argument("--resident-home", type=Path)
    args = parser.parse_args()
    try:
        if args.operation in {"verify", "rollback"}:
            plan = load_plan(args.destination, args.task)
        else:
            if args.source is None or args.target is None:
                raise TransferBlocked("evidence_arguments_invalid")
            plan = preview(args.source, args.destination, args.task, args.target)
        if args.operation == "apply":
            if args.expected_seal != plan["seal"]:
                raise TransferBlocked("evidence_preview_required")
            print(json.dumps(apply(plan)))
        elif args.operation == "verify":
            print(json.dumps(verify(plan)))
        elif args.operation == "rollback":
            if args.resident_home is None:
                raise TransferBlocked("evidence_rollback_home_required")
            print(json.dumps(rollback(plan, args.resident_home)))
        else:
            print(json.dumps(plan))
        return 0
    except (UpdateBlocked, MaintenanceBusy, OSError, ValueError, RuntimeError) as exc:
        code = str(exc) if isinstance(exc, UpdateBlocked) else "evidence_transfer_io_failed"
        cause = exc.__cause__
        while cause is not None and cause.__cause__ is not None:
            cause = cause.__cause__
        if isinstance(cause, subprocess.TimeoutExpired):
            code = "evidence_remote_timeout"
        log.warning("resident_evidence_transfer_blocked", extra={"code": code})
        print(json.dumps({"status": "blocked", "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
