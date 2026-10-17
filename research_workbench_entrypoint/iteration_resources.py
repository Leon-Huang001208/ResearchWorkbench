"""Task-owned iteration closeout using the existing Docker disposal controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from .docker_resources import (
    DockerResources,
    ResourceError,
    apply_plan,
    cleanup_locks,
    owned,
    plan_resources,
    protections,
    write_receipt,
)
from .iteration_cache import GIB, ManagedCaches, cache_budget, operation_lock

log = logging.getLogger(__name__)
DEPENDENCIES = (
    "node_modules",
    "services/hot/node_modules",
    "services/ai_news/vendor/aihot/node_modules",
    ".venv",
    ".validation-tools",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)
EMPTY_DIRECTORIES = ("data/markdown", "data/objects", "data/raw_text")


def dependency_path(relative):
    return (
        relative in DEPENDENCIES
        or relative.endswith("/__pycache__")
        or relative == "__pycache__"
        or bool(
            re.fullmatch(
                r"logs/(?:[A-Za-z0-9_.-]+/){0,6}runtime/dsh/[0-9a-f]{40}/node_modules", relative
            )
        )
    )


def git(root, *args):
    result = subprocess.run(
        [
            "/usr/bin/git",
            "--no-optional-locks",
            "-c",
            "gc.auto=0",
            "-c",
            "maintenance.auto=false",
            "-C",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ResourceError("closeout_git_check_failed")
    return result.stdout.strip()


def occupied(path):
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "+D", str(path)], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return True
    if result.returncode != 1 or result.stderr.strip():
        raise ResourceError("closeout_process_check_failed")
    # mmap/package files may be closed; also protect cwd and executable arguments.
    commands = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True, check=True
    ).stdout
    rows = [line.strip().split(None, 2) for line in commands.splitlines()]
    processes = {int(row[0]): (int(row[1]), row[2]) for row in rows if len(row) == 3}
    ancestors = set()
    pid = os.getpid()
    while pid in processes and pid not in ancestors:
        ancestors.add(pid)
        pid = processes[pid][0]
    # lsof above still protects ancestor cwd/FDs; only the controller's own
    # command-line source path is exempt from the additional argv heuristic.
    return any(
        str(path) in command for pid, (_, command) in processes.items() if pid not in ancestors
    )


def register_directory(root, path, kind):
    root, path = Path(root), Path(path)
    if root.resolve() != root or path.resolve() != path or path.is_symlink() or not path.is_dir():
        raise ResourceError("closeout_directory_alias")
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        raise ResourceError("closeout_directory_outside_task") from None
    if (
        (kind == "dependency" and not dependency_path(relative))
        or (kind == "evidence" and relative != "logs")
        or (kind == "empty-directory" and relative not in EMPTY_DIRECTORIES)
        or kind not in {"dependency", "evidence", "empty-directory"}
    ):
        raise ResourceError("closeout_directory_not_allowed")
    if kind == "empty-directory" and next(path.iterdir(), None) is not None:
        raise ResourceError("closeout_directory_not_empty")
    stat = path.stat()
    return {
        "root": str(root),
        "path": str(path),
        "kind": kind,
        "device": stat.st_dev,
        "inode": stat.st_ino,
    }


def clean_dependencies(records, *, occupied=occupied, tracked=None, journal=None):
    tracked = tracked or (
        lambda row: bool(
            git(row["root"], "ls-files", "--", str(Path(row["path"]).relative_to(row["root"])))
        )
    )
    result = {"ok": True, "items": []}
    for row in records:
        if row["kind"] not in {"dependency", "empty-directory"}:
            continue
        path = Path(row["path"])
        item = {"path": str(path), "status": "pending"}
        result["items"].append(item)
        try:
            if not path.exists() and not path.is_symlink():
                item["status"] = "already_absent"
            else:
                current = register_directory(Path(row["root"]), path, row["kind"])
                if current != row or occupied(path) or tracked(row):
                    raise ResourceError("closeout_dependency_changed_or_in_use")
                item["allocatedBytesBefore"] = (
                    int(subprocess.check_output(["du", "-sk", str(path)], text=True).split()[0])
                    * 1024
                )
                if journal:
                    journal(result)
                # rmtree never follows internal symlinks; unknown sibling paths are untouched.
                if row["kind"] == "empty-directory":
                    path.rmdir()  # Atomic refusal if a file appeared after inspection.
                else:
                    shutil.rmtree(path)
                if path.exists():
                    raise ResourceError("closeout_dependency_deletion_unverified")
                item["status"] = "reclaimed"
                log.info("iteration_dependency status=reclaimed")
        except (ResourceError, OSError, subprocess.SubprocessError) as error:
            item.update(
                status="blocked",
                code=(
                    str(error)
                    if isinstance(error, ResourceError)
                    else "closeout_dependency_io_failed"
                ),
            )
            result["ok"] = False
            log.error("iteration_dependency code=%s", item["code"])
        if journal:
            journal(result)
    return result


def file_manifest(root):
    """Hash evidence only; dependency caches never enter the permanent evidence copy."""
    result = {}
    for path in Path(root).rglob("*"):
        if path.is_symlink():
            raise ResourceError("closeout_evidence_alias")
        if path.is_file():
            with path.open("rb") as stream:
                result[str(path.relative_to(root))] = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest()
    return result


def preserve_evidence(records, destination):
    result = []
    for row in records:
        if row["kind"] != "evidence":
            continue
        source = Path(row["path"])
        target = Path(destination) / hashlib.sha256(row["root"].encode()).hexdigest()[:16]
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        archive = target / "logs"
        manifest_path = target / "manifest.json"
        if not source.exists():
            if not manifest_path.exists() or file_manifest(archive) != json.loads(
                manifest_path.read_text()
            ):
                raise ResourceError("closeout_evidence_missing")
            result.append({"status": "already_preserved", "archive": str(archive)})
            continue
        if register_directory(Path(row["root"]), source, "evidence") != row or occupied(source):
            raise ResourceError("closeout_evidence_changed_or_in_use")
        current = file_manifest(source)
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if any(manifest.get(key) != value for key, value in current.items()):
                raise ResourceError("closeout_evidence_source_changed")
        else:
            if archive.exists():
                raise ResourceError("closeout_evidence_target_exists")
            manifest = current
            write_receipt(manifest_path, manifest)
        archive.mkdir(mode=0o700, exist_ok=True)
        saved = file_manifest(archive)
        if any(manifest.get(key) != value for key, value in saved.items()):
            raise ResourceError("closeout_evidence_archive_changed")
        for relative in manifest:
            if relative not in saved:
                if relative not in current:
                    raise ResourceError("closeout_evidence_copy_incomplete")
                destination_file = archive / relative
                destination_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                staging = target / "partial"
                staging.mkdir(mode=0o700, exist_ok=True)
                if staging.is_symlink():
                    raise ResourceError("closeout_evidence_alias")
                partial = staging / (hashlib.sha256(relative.encode()).hexdigest() + ".part")
                descriptor = os.open(
                    partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
                )
                with (
                    os.fdopen(descriptor, "wb") as output,
                    (source / relative).open("rb") as input_stream,
                ):
                    shutil.copyfileobj(input_stream, output, length=65536)
                    output.flush()
                    os.fsync(output.fileno())
                with partial.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != manifest[relative]:
                        raise ResourceError("closeout_evidence_copy_unverified")
                os.replace(partial, destination_file)
                shutil.copystat(source / relative, destination_file, follow_symlinks=False)
        if manifest != file_manifest(archive) or any(
            manifest.get(key) != value for key, value in file_manifest(source).items()
        ):
            raise ResourceError("closeout_evidence_copy_unverified")
        shutil.rmtree(source)
        result.append({"status": "preserved", "archive": str(archive), "files": len(manifest)})
        log.info("iteration_evidence status=preserved files=%d", len(manifest))
    return result


def state_paths(project, task):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", task):
        raise ResourceError("closeout_task_invalid")
    project = Path(project).resolve()
    common = Path(git(project, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (project / common).resolve()
    state = common / "leon-engineering" / "resource-closeout" / task
    for parent in [state, *state.parents]:
        if parent.is_symlink():
            raise ResourceError("closeout_state_alias")
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state.stat().st_mode & 0o077:
        raise ResourceError("closeout_state_not_private")
    delivery = common / "leon-engineering" / "deliveries" / (task + ".json")
    if delivery.is_symlink():
        raise ResourceError("closeout_delivery_alias")
    receipt = json.loads(delivery.read_text())
    if receipt.get("taskId") != task:
        raise ResourceError("closeout_task_mismatch")
    return project, state, receipt


def task_resource_plan(inventory, protected, task):
    retired = {}
    for kind, key in (("container", "containers"), ("image", "images"), ("volume", "volumes")):
        for row in inventory[key]:
            labels = row.get("labels") or {}
            if (
                owned(row, kind)
                and labels.get("io.research-workbench.delivery-task") == task
                and labels.get("io.research-workbench.lifetime") == "temporary"
            ):
                retired[kind + ":" + row["id"]] = "accepted_delivery_temporary_resource"
    plan = plan_resources(inventory, protected, retired)
    for row in plan["resources"]:
        if row["kind"] + ":" + row["id"] not in retired:
            row.update(action="keep", reason="other_task_or_persistent")
    return plan


def record_task(project, task):
    project, state, receipt = state_paths(project, task)
    ledger = state / "resources.json"
    old = (
        json.loads(ledger.read_text())
        if ledger.exists()
        else {"taskId": task, "roots": {}, "directories": []}
    )
    if old["taskId"] != task:
        raise ResourceError("closeout_task_mismatch")
    roots = [
        receipt.get("featureWorktree"),
        receipt.get("integrationWorktree"),
        *[v["worktree"] for v in receipt.get("integrationHistory", [])],
    ]
    for value in filter(None, roots):
        root = Path(value)
        if not root.exists():
            continue

        def common(where):
            value = Path(git(where, "rev-parse", "--git-common-dir"))
            return value.resolve() if value.is_absolute() else (where / value).resolve()

        if common(root) != common(project):
            raise ResourceError("closeout_worktree_not_owned")
        stat = root.stat()
        identity = [stat.st_dev, stat.st_ino]
        if str(root) in old["roots"] and old["roots"][str(root)] != identity:
            raise ResourceError("closeout_worktree_changed")
        old["roots"][str(root)] = identity
        known = {row["path"]: row for row in old["directories"]}
        generated = git(
            root, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"
        ).split("\0")
        extras = [
            value.rstrip("/") for value in generated if value.rstrip("/").endswith("__pycache__")
        ]
        # Installer-owned DSH checkouts live inside logs; strip their dependencies
        # before evidence preservation so repeated installs do not become archives.
        extras.extend(
            str(value.relative_to(root))
            for value in root.glob("logs/**/runtime/dsh/*/node_modules")
        )
        for relative in dict.fromkeys([*DEPENDENCIES, *extras, "logs"]):
            path = root / relative
            if path.exists():
                row = register_directory(
                    root, path, "evidence" if relative == "logs" else "dependency"
                )
                if str(path) in known and known[str(path)] != row:
                    raise ResourceError("closeout_registered_directory_changed")
                if str(path) not in known:
                    old["directories"].append(row)
        for relative in EMPTY_DIRECTORIES:
            path = root / relative
            if path.is_dir() and not path.is_symlink() and next(path.iterdir(), None) is None:
                row = register_directory(root, path, "empty-directory")
                if str(path) in known and known[str(path)] != row:
                    raise ResourceError("closeout_registered_directory_changed")
                if str(path) not in known:
                    old["directories"].append(row)
    write_receipt(ledger, old)
    return {"ok": True, "registeredDirectories": len(old["directories"]), "state": str(state)}


def closeout(project, task, policy):
    project, state, delivery = state_paths(project, task)
    if delivery.get("status") != "ci_passed" or delivery.get("ci", {}).get("status") != "passed":
        raise ResourceError("closeout_delivery_not_accepted")
    git(project, "merge-base", "--is-ancestor", delivery["integrationCommit"], "origin/master")
    ledger = json.loads((state / "resources.json").read_text())
    report = {
        "taskId": task,
        "ok": False,
        "status": "running",
        "reclaimed": [],
        "retained": [],
        "blocked": [],
        "diskBefore": shutil.disk_usage(project)._asdict(),
    }
    journal = lambda: write_receipt(state / "receipt.json", report)
    journal()
    try:
        for value, identity in ledger["roots"].items():
            root = Path(value)
            if root.exists():
                stat = root.stat()
                if (
                    root.resolve() != root
                    or [stat.st_dev, stat.st_ino] != identity
                    or occupied(root)
                ):
                    raise ResourceError("closeout_worktree_changed_or_in_use")
                if git(root, "status", "--porcelain", "--untracked-files=all"):
                    raise ResourceError("closeout_worktree_dirty")
        dependencies = clean_dependencies(
            ledger["directories"],
            journal=lambda result: write_receipt(state / "dependencies.json", result),
        )
        report["reclaimed"].extend(v for v in dependencies["items"] if v["status"] != "blocked")
        report["blocked"].extend(v for v in dependencies["items"] if v["status"] == "blocked")
        if not dependencies["ok"]:
            raise ResourceError("closeout_dependencies_blocked")
        # Existing disposal planning remains the single authority for data-bearing
        # Docker objects. Only this delivery's temporary objects become retired.
        driver = DockerResources()
        inventory = driver.inventory()
        homes = [Path.home() / ".research-workbench"]
        with cleanup_locks(homes), operation_lock(Path.home() / ".local/share/rwb-docker"):

            def protected():
                result = protections(homes)
                manager = Path.home() / ".local/share/rwb-docker"
                for path in manager.glob("*.json"):
                    if path.is_symlink():
                        raise ResourceError("closeout_manager_record_alias")
                    value = json.loads(path.read_text())
                    if value.get("retired"):
                        continue
                    for key in ("image", "previous_image"):
                        image = value.get(key)
                        if image:
                            if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
                                raise ResourceError("closeout_manager_image_invalid")
                            result["images"].append(image)
                return result

            plan = task_resource_plan(inventory, protected(), task)
            retired = plan["retired"]
            write_receipt(state / "docker-plan.json", plan)
            docker = apply_plan(
                driver,
                plan,
                protected,
                state / "volumes",
                policy["archiveHelperImage"],
                journal=lambda value: write_receipt(state / "docker-receipt.json", value),
            )
        report["retained"] = [row for row in plan["resources"] if row["action"] == "keep"]
        if not docker["ok"]:
            raise ResourceError("closeout_docker_objects_blocked")
        report["reclaimed"].extend(docker["items"])
        if any(
            row["kind"] == "container"
            and row["reason"] == "running"
            and row["kind"] + ":" + row["id"] in retired
            for row in plan["resources"]
        ):
            raise ResourceError("closeout_temporary_task_still_running")
        caches = ManagedCaches(Path.home() / ".local/share/rwb-docker")
        with caches.maintenance():
            report["cache"] = cache_budget(caches, list(caches.names), policy["cacheBudgetBytes"])
            journal()
        if not report["cache"]["ok"]:
            raise ResourceError("closeout_cache_over_budget")
        report["evidence"] = preserve_evidence(ledger["directories"], state / "evidence")
        report.update(ok=True, status="resources_complete_git_cleanup_pending")
    except (ResourceError, OSError, ValueError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, ResourceError) else "closeout_io_failed"
        report["blocked"].append({"code": code})
        report["status"] = "blocked"
        log.error("iteration_closeout code=%s", code)
    report["diskAfter"] = shutil.disk_usage(project)._asdict()
    journal()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--phase", required=True, choices=["record", "cleanup"])
    args = parser.parse_args()
    try:
        _, state, _ = state_paths(args.project, args.task_id)
        (state / "logs").mkdir(mode=0o700, exist_ok=True)
        logging.basicConfig(filename=state / "logs/operations.log", level=logging.INFO)
        policy = json.loads(
            (Path(__file__).resolve().parents[1] / ".agents/resource-closeout.json").read_text()
        )
        if (
            policy.get("schemaVersion") != 1
            or policy.get("cacheBudgetBytes") != 20 * GIB
            or policy.get("managedBuilders") != list(ManagedCaches.names)
            or policy.get("acceptedImageRetention") != 2
            or policy.get("automaticAfterAcceptedMerge") is not True
        ):
            raise ResourceError("closeout_policy_invalid")
        result = (
            record_task(args.project, args.task_id)
            if args.phase == "record"
            else closeout(args.project, args.task_id, policy)
        )
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in ("ok", "status", "state", "registeredDirectories")
                    if key in result
                }
            )
        )
        return 0 if result["ok"] else 1
    except (ResourceError, OSError, ValueError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, ResourceError) else "closeout_io_failed"
        log.error("iteration_closeout code=%s", code)
        print(json.dumps({"ok": False, "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
