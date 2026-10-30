"""Read-only relocation inventory. Unknown state is protected, never disposable."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .delivery_transfer import MaintenanceParser

log = logging.getLogger(__name__)


def read_metadata(path):
    try:
        s = path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_size > 1000000:
            return {"status": "unsafe"}
        if getattr(s, "st_flags", 0) & getattr(stat, "SF_DATALESS", 0x40000000):
            return {"status": "offline"}
        raw = path.read_bytes()
        return {
            "status": "readable",
            "text": raw.decode("utf8").strip(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    except FileNotFoundError:
        return {"status": "missing"}
    except (OSError, UnicodeError):
        return {"status": "unreadable"}


def git_observation(project, args, timeout=8):
    argv = [
        "/usr/bin/git",
        "--no-optional-locks",
        "-c",
        "gc.auto=0",
        "-c",
        "maintenance.auto=false",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(project),
        *args,
    ]
    try:
        r = subprocess.run(argv, check=False, capture_output=True, timeout=timeout)
        if r.returncode:
            return {
                "status": "failed",
                "exit": r.returncode,
                "stderr_sha256": hashlib.sha256(r.stderr).hexdigest(),
            }
        return {"status": "observed", "stdout": r.stdout.decode("utf8", "strict")}
    except subprocess.TimeoutExpired:
        return {"status": "READ_TIMEOUT"}
    except (OSError, UnicodeError):
        return {"status": "unavailable"}


def worktree_row(registration):
    gitdir = read_metadata(registration / "gitdir")
    head = read_metadata(registration / "HEAD")
    row = {
        "registration": registration.name,
        "gitdir": gitdir,
        "head": head,
        "disposition": "protected",
        "occupancy": "not_certified",
    }
    if gitdir["status"] != "readable":
        return row
    path = Path(gitdir["text"]).parent
    row["path"] = str(path)
    if not path.is_dir() or path.is_symlink():
        row["working_state"] = {"status": "missing_or_alias"}
        return row
    row["working_state"] = git_observation(
        path, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    status = row["working_state"]
    if status["status"] == "observed":
        text = status.pop("stdout")
        entries = text.split("\0")
        status["entries"] = [x for x in entries if x]
        status["clean"] = not text
    return row


def inventory(project, destination):
    project, destination = Path(project).absolute(), Path(destination).absolute()
    common = git_observation(project, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
    if common["status"] != "observed":
        raise RuntimeError("migration_common_unavailable")
    root = Path(common["stdout"].strip())
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise RuntimeError("migration_common_unsafe")
    regs = sorted((root / "worktrees").iterdir()) if (root / "worktrees").is_dir() else []
    before = [(p.name, p.stat().st_ino, p.stat().st_mtime_ns) for p in regs]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(worktree_row, regs))
    after = [
        (p.name, p.stat().st_ino, p.stat().st_mtime_ns)
        for p in (sorted((root / "worktrees").iterdir()) if (root / "worktrees").is_dir() else [])
    ]
    refs = git_observation(project, ["for-each-ref", "--format=%(refname) %(objectname)"])
    result = {
        "schema_version": 1,
        "source": str(project),
        "destination": str(destination),
        "source_common": str(root),
        "source_identity": [root.stat().st_dev, root.stat().st_ino],
        "registry_stable": before == after,
        "worktree_count": len(rows),
        "worktrees": rows,
        "primary_state": git_observation(
            project, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        ),
        "refs": refs,
        "source_lock": read_metadata(root / "leon-engineering/git-safety/repository.lock"),
        "destination_state": git_observation(
            destination, ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
        ),
        "apply_authorized": False,
    }
    result["manifest_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()
    log.info("resident_source_inventory_completed", extra={"worktrees": len(rows)})
    return result


def main():
    parser = MaintenanceParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inventory(args.source, args.destination)))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        log.warning("resident_source_inventory_blocked", extra={"error_type": type(exc).__name__})
        print(json.dumps({"status": "blocked", "code": "source_inventory_unavailable"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
