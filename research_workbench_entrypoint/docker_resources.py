"""Stdlib Docker inventory, explicit disposal plans and recoverable volume archives.

Never log Docker stderr, container environments, secrets or volume contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)
PREFIX = "io.research-workbench."


class ResourceError(RuntimeError):
    """Stable, non-sensitive failure code."""


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def owned(row, kind):
    labels = row.get("labels") or {}
    return (
        labels.get(PREFIX + "project") == "research-workbench"
        or labels.get(PREFIX + "runtime") == "docker"
        or (
            kind == "container"
            and bool(labels.get("rwb.hot.instance") or labels.get("rwb.hot.probe"))
        )
    )


def plan_resources(inventory, protected, retired):
    """A stopped container is not disposable without lifetime or explicit evidence."""
    protected_images = set(protected.get("images", []))
    installations = set(protected.get("installations", []))
    deleted = set()
    rows = []
    for kind, key in (("container", "containers"), ("volume", "volumes"), ("image", "images")):
        for row in inventory[key]:
            identity = row["id"]
            labels = row.get("labels") or {}
            refs = [
                c["id"]
                for c in inventory["containers"]
                if (kind == "volume" and identity in c["volumes"])
                or (kind == "image" and identity == c["image"])
            ]
            evidence = retired.get(kind + ":" + identity)
            temporary = (
                labels.get(PREFIX + "lifetime") == "temporary"
                and labels.get(PREFIX + "completed") == "true"
            )
            reason = "unknown_or_persistent"
            action = "keep"
            if kind == "container":
                if row["running"]:
                    reason = "running"
                elif labels.get(PREFIX + "installation") in installations or (
                    row["image"] in protected_images and not evidence
                ):
                    reason = "accepted_installation_or_rollback"
                elif owned(row, kind) and (temporary or evidence):
                    action, reason = "delete", evidence or "completed_temporary_resource"
                    deleted.add(identity)
            elif kind == "volume":
                if any(ref not in deleted for ref in refs):
                    reason = "retained_container_reference"
                elif evidence or (owned(row, kind) and temporary):
                    action, reason = "archive-delete", evidence or "completed_temporary_resource"
            elif identity in protected_images:
                reason = "accepted_installation_or_rollback"
            elif any(ref not in deleted for ref in refs):
                reason = "retained_container_reference"
            elif owned(row, kind) and (temporary or evidence):
                action, reason = "delete", evidence or "completed_temporary_resource"
            rows.append(
                {
                    "kind": kind,
                    "id": identity,
                    "name": row.get("name") or "|".join(row.get("tags") or []) or identity,
                    "purpose": labels.get(PREFIX + "purpose", "unknown"),
                    "lifetime": labels.get(PREFIX + "lifetime", "unknown"),
                    "action": action,
                    "reason": reason,
                    "references": refs,
                    "bytes": row.get("size_bytes"),
                    "fingerprint": fingerprint(row),
                }
            )
    return {"schema_version": 1, "retired": retired, "resources": rows}


def apply_plan(driver, plan, protected, archive_dir, helper, journal=None):
    """Recompute policy before each exact deletion; fail-stop on any changed identity."""
    receipt = {"schema_version": 1, "ok": True, "items": []}
    if (
        not isinstance(plan, dict)
        or plan.get("schema_version") != 1
        or not isinstance(plan.get("retired"), dict)
        or not isinstance(plan.get("resources"), list)
    ):
        raise ResourceError("resource_plan_invalid")
    order = {"container": 0, "volume": 1, "image": 2}
    seen = set()
    for row in plan["resources"]:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("kind"), str)
            or row.get("kind") not in order
            or not isinstance(row.get("action"), str)
            or row.get("action") not in {"keep", "delete", "archive-delete"}
            or not isinstance(row.get("id"), str)
            or not isinstance(row.get("fingerprint"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", row["fingerprint"])
            or (row["kind"], row["id"]) in seen
        ):
            raise ResourceError("resource_plan_invalid")
        seen.add((row["kind"], row["id"]))
    if journal:
        journal(receipt)
    for planned in sorted(plan["resources"], key=lambda row: order[row["kind"]]):
        if planned["action"] == "keep":
            continue
        item = {"kind": planned["kind"], "id": planned["id"]}
        item["status"] = "pending"
        receipt["items"].append(item)
        try:
            if journal:
                journal(receipt)
            current = driver.inventory()
            protections = protected() if callable(protected) else protected
            fresh = plan_resources(current, protections, plan["retired"])
            match = next(
                (
                    r
                    for r in fresh["resources"]
                    if (r["kind"], r["id"]) == (planned["kind"], planned["id"])
                ),
                None,
            )
            if match is None:
                item["status"] = "already_absent"
            else:
                if (
                    match["action"] != planned["action"]
                    or match["fingerprint"] != planned["fingerprint"]
                ):
                    raise ResourceError("resource_changed_or_protected")
                if planned["kind"] == "volume":
                    if match["references"]:
                        raise ResourceError("volume_still_referenced")
                    item["archive"] = driver.archive(planned["id"], archive_dir, helper)
                    if not item["archive"].get("verified"):
                        raise ResourceError("archive_unverified")
                    if journal:
                        journal(receipt)
                    again = plan_resources(
                        driver.inventory(),
                        protected() if callable(protected) else protected,
                        plan["retired"],
                    )
                    checked = next(
                        r
                        for r in again["resources"]
                        if r["kind"] == "volume" and r["id"] == planned["id"]
                    )
                    if checked["references"] or checked["fingerprint"] != planned["fingerprint"]:
                        raise ResourceError("volume_changed_after_archive")
                driver.remove(planned["kind"], planned["id"])
                if any(
                    r["id"] == planned["id"]
                    for r in driver.inventory()[
                        {"container": "containers", "volume": "volumes", "image": "images"}[
                            planned["kind"]
                        ]
                    ]
                ):
                    raise ResourceError("deletion_unverified")
                item["status"] = "deleted"
            log.info("docker_resource kind=%s status=%s", item["kind"], item["status"])
        except (ResourceError, OSError, ValueError, StopIteration, KeyboardInterrupt) as error:
            item.update(
                status="failed",
                code=(
                    str(error)
                    if isinstance(error, ResourceError)
                    else (
                        "resource_interrupted"
                        if isinstance(error, KeyboardInterrupt)
                        else "resource_io_failed"
                    )
                ),
            )
            receipt["ok"] = False
            log.error("docker_resource code=%s", item["code"])
        if journal:
            journal(receipt)
        if not receipt["ok"]:
            break
    return receipt


class DockerResources:
    """Inspect projections omit credentials, environments, commands and contents."""

    def call(self, *args, timeout=30):
        try:
            completed = subprocess.run(
                ["docker", *args], capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            raise ResourceError("docker_resource_command_timeout") from None
        except (OSError, subprocess.SubprocessError):
            raise ResourceError("docker_resource_command_failed") from None
        if completed.returncode:
            raise ResourceError("docker_resource_command_failed")
        if len(completed.stdout) > 4 * 1024 * 1024:
            raise ResourceError("docker_resource_output_limit")
        return completed.stdout

    def inventory(self):
        data = {"containers": [], "images": [], "volumes": []}
        for identity in self.call("ps", "-aq", "--no-trunc").splitlines():
            raw = self.call(
                "container",
                "inspect",
                "--format",
                '{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},'
                '"running":{{json .State.Running}},"labels":{{json (index .Config "Labels")}},'
                '"mounts":{{json .Mounts}}}',
                identity,
            )
            row = json.loads(raw)
            mounts = row.pop("mounts")
            row["volumes"] = sorted(m["Name"] for m in mounts if m["Type"] == "volume")
            row["binds"] = sorted(m["Source"] for m in mounts if m["Type"] == "bind")
            data["containers"].append(row)
        for identity in sorted(set(self.call("image", "ls", "-aq", "--no-trunc").splitlines())):
            data["images"].append(
                json.loads(
                    self.call(
                        "image",
                        "inspect",
                        "--format",
                        '{"id":{{json .Id}},"tags":{{json .RepoTags}},"labels":{{json (index .Config "Labels")}}}',
                        identity,
                    )
                )
            )
        for identity in self.call("volume", "ls", "-q").splitlines():
            data["volumes"].append(
                json.loads(
                    self.call(
                        "volume",
                        "inspect",
                        "--format",
                        '{"id":{{json .Name}},"labels":{{json .Labels}},"created":{{json .CreatedAt}}}',
                        identity,
                    )
                )
            )
        return data

    def remove(self, kind, identity):
        if kind == "container":
            self.call("rm", identity)  # no force, no implicit volume removal
        else:
            self.call(kind, "rm", identity)

    def resolve(self, kind, identity):
        if kind == "container":
            ids = self.call(
                "ps", "-aq", "--no-trunc", "--filter", "name=^/" + identity + "$"
            ).splitlines()
        elif kind == "image":
            ids = self.call(
                "image", "ls", "-q", "--no-trunc", "--filter", "reference=" + identity
            ).splitlines()
        else:
            ids = [
                name
                for name in self.call(
                    "volume", "ls", "-q", "--filter", "name=" + identity
                ).splitlines()
                if name == identity
            ]
        ids = list(set(ids))
        if len(ids) > 1:
            raise ResourceError("resource_session_identity_ambiguous")
        return ids[0] if ids else None

    def archive(self, identity, directory, helper):
        """Offline tar backup, SHA-256, then real restore into a disposable volume."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identity):
            raise ResourceError("volume_name_invalid")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", helper or ""):
            raise ResourceError("archive_helper_must_be_local_image_id")
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.stat().st_mode & 0o077:
            raise ResourceError("archive_directory_not_private")
        archive = directory / (identity + "-" + uuid4().hex + ".tar")
        source_before = self.call("volume", "inspect", "--format", "{{json .}}", identity)
        restored = "rwb-test-restore-" + uuid4().hex + "-data"
        session = ResourceSession(self, "archive")
        try:
            session.volume(restored)
            common = ["--network", "none", "--entrypoint", "/bin/sh", "--user", "0:0"]
            session.run(
                [
                    *common,
                    "--mount",
                    f"type=volume,src={identity},dst=/source,readonly,volume-nocopy",
                    "--mount",
                    f"type=bind,src={directory},dst=/backup",
                    helper,
                    "-ec",
                    'umask 077; tar -cf "/backup/$1" -C /source .',
                    "archive",
                    archive.name,
                ],
                timeout=300,
            )
            with archive.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            session.run(
                [
                    *common,
                    "--mount",
                    f"type=volume,src={restored},dst=/restore,volume-nocopy",
                    "--mount",
                    f"type=bind,src={directory},dst=/backup,readonly",
                    helper,
                    "-ec",
                    'tar -xf "/backup/$1" -C /restore; tar -df "/backup/$1" -C /restore',
                    "restore",
                    archive.name,
                ],
                timeout=300,
            )
            if self.call("volume", "inspect", "--format", "{{json .}}", identity) != source_before:
                raise ResourceError("archive_source_changed")
            with archive.open("rb") as stream:
                restored_digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if restored_digest != digest:
                raise ResourceError("archive_changed")
            return {
                "path": str(archive),
                "sha256": digest,
                "verified": True,
                "verification": "tar_restore_and_compare",
            }
        finally:
            session.cleanup()


class ResourceSession:
    """One task owns exact helper IDs; always use with/finally for cleanup."""

    def __init__(self, driver, purpose, *, delivery_task=None):
        if not re.fullmatch(r"[a-z0-9-]+", purpose):
            raise ResourceError("resource_purpose_invalid")
        self.driver = driver
        self.purpose = purpose
        self.task = uuid4().hex
        self.delivery_task = delivery_task or os.environ.get("RWB_DELIVERY_TASK_ID")
        if self.delivery_task and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", self.delivery_task):
            raise ResourceError("resource_delivery_task_invalid")
        self.resources = []
        self.pending = set()
        log.info("resource_session task=%s purpose=%s", self.task, self.purpose)

    @property
    def labels(self):
        labels = {
            PREFIX + "project": "research-workbench",
            PREFIX + "purpose": self.purpose,
            PREFIX + "task": self.task,
            PREFIX + "lifetime": "temporary",
        }
        if self.delivery_task:
            labels[PREFIX + "delivery-task"] = self.delivery_task
        return labels

    @property
    def flags(self):
        return [
            value for key, value in self.labels.items() for value in ("--label", key + "=" + value)
        ]

    def volume(self, name=None):
        name = name or f"rwb-test-{self.purpose}-{self.task[:12]}-data"
        self.resources.append(("volume", name))
        self.pending.add(("volume", name))
        self.driver.call("volume", "create", *self.flags, name)
        self.pending.discard(("volume", name))
        return name

    def run(self, args, timeout=30):
        args = list(args)
        image_index = next(
            (i for i, value in enumerate(args) if re.fullmatch(r"sha256:[a-f0-9]{64}", value)), None
        )
        if image_index is None:
            raise ResourceError("resource_helper_must_use_local_image_id")
        declared = (
            json.loads(
                self.driver.call(
                    "image",
                    "inspect",
                    "--format",
                    '{{json (index .Config "Volumes")}}',
                    args[image_index],
                )
            )
            or {}
        )
        # An image VOLUME otherwise silently creates anonymous persistent data.
        # Override unbound destinations with task-local tmpfs before creation.
        bound = {
            part.split("=", 1)[1]
            for value in args[:image_index]
            for part in value.split(",")
            if part.startswith(("dst=", "destination=", "target="))
        }
        ephemeral = [
            value
            for destination in declared
            if destination not in bound
            for value in ("--tmpfs", destination + ":rw,nosuid,nodev")
        ]
        args[image_index:image_index] = ephemeral
        name = f"rwb-test-{self.purpose}-{uuid4().hex[:12]}"
        # Keep a stopped helper until finally so interruptions are also recoverable.
        self.resources.append(("container", name))
        self.pending.add(("container", name))
        identity = self.driver.call("create", "--name", name, *self.flags, *args).strip()
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise ResourceError("resource_helper_identity_invalid")
        self.pending.discard(("container", name))
        self.driver.call("start", "-a", identity, timeout=timeout)
        code = self.driver.call("inspect", "--format", "{{.State.ExitCode}}", identity).strip()
        if code != "0":
            raise ResourceError("resource_helper_failed")

    def build(self, context, *, timeout=300):
        tag = f"research-workbench:test-{self.purpose}-{self.task[:12]}"
        self.resources.append(("image", tag))
        self.pending.add(("image", tag))
        self.driver.call(
            "build", "--pull=false", "-t", tag, *self.flags, str(context), timeout=timeout
        )
        identity = self.driver.call("image", "inspect", "--format", "{{.Id}}", tag).strip()
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", identity):
            raise ResourceError("resource_image_identity_invalid")
        self.pending.discard(("image", tag))
        return identity

    def cleanup(self):
        errors = []
        order = {"container": 0, "volume": 1, "image": 2}
        for kind, name in sorted(self.resources, key=lambda row: order[row[0]]):
            try:
                identity = self.driver.resolve(kind, name)
                if identity is None:
                    if (kind, name) in self.pending:
                        raise ResourceError("resource_creation_unconfirmed")
                    continue
                # A helper may still be running after interruption; stop only our task.
                if kind == "container":
                    labels = json.loads(
                        self.driver.call("inspect", "--format", "{{json .Config.Labels}}", identity)
                    )
                    if labels.get(PREFIX + "task") != self.task:
                        raise ResourceError("resource_session_identity_changed")
                    self.driver.call("stop", "--time", "5", identity)
                elif kind == "volume":
                    labels = json.loads(
                        self.driver.call(
                            "volume", "inspect", "--format", "{{json .Labels}}", identity
                        )
                    )
                    if labels.get(PREFIX + "task") != self.task:
                        raise ResourceError("resource_session_identity_changed")
                else:
                    labels = json.loads(
                        self.driver.call(
                            "image",
                            "inspect",
                            "--format",
                            '{{json (index .Config "Labels")}}',
                            identity,
                        )
                    )
                    if labels.get(PREFIX + "task") != self.task:
                        raise ResourceError("resource_session_identity_changed")
                if kind == "container":
                    self.driver.call("rm", "-v", identity)
                else:
                    self.driver.remove(kind, identity)
                self.pending.discard((kind, name))
            except ResourceError as error:
                errors.append(str(error))
                log.error("docker_resource_cleanup code=%s", error)
        if errors:
            raise ResourceError("resource_session_cleanup_failed")
        self.resources.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cleanup()


def protections(homes):
    result = {"images": [], "installations": []}
    for home in homes:
        root = Path(home)
        for name in ("docker-manifest.json", "docker-previous-manifest.json"):
            path = root / "install" / name
            if path.exists():
                from .runtime_mode import _read_bytes

                value = json.loads(_read_bytes(path)[0])
                if value.get("status") != "installed" or not re.fullmatch(
                    r"sha256:[a-f0-9]{64}", value.get("image_id", "")
                ):
                    raise ResourceError("protected_manifest_invalid")
                result["images"].append(value["image_id"])
        mode = root / "install/runtime.json"
        if mode.exists():
            from .runtime_mode import RuntimeModeStore

            result["installations"].append(RuntimeModeStore(root).read().installation_id)
    return result


@contextmanager
def cleanup_locks(homes):
    """Share installation publication locks; acquire roots in stable order."""
    from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError

    from .docker_runtime import DockerRuntime
    from .runtime_mode import RuntimeModeError, RuntimeModeStore

    try:
        with ExitStack() as stack:
            for root in sorted({Path(home).absolute() for home in homes}):
                if not root.exists():
                    raise ResourceError("cleanup_home_missing")
                lease = stack.enter_context(
                    LifecycleLock(
                        root / "run/lifecycle.lock", DockerRuntime._pid_exists, trusted_root=root
                    )
                )
                stack.enter_context(RuntimeModeStore(root)._write_lock(strict_parent=True))
                lease.assert_held()
            yield
    except (LifecycleLockError, RuntimeModeError):
        raise ResourceError("cleanup_installation_lock_unavailable") from None


def write_receipt(path, value):
    """Durable journal: an interrupted process leaves its last pending item."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", action="append", default=[])
    parser.add_argument("--retired", type=Path, help="Audited kind:ID -> reason JSON")
    parser.add_argument("--plan", type=Path, help="Save exact preview")
    parser.add_argument("--apply", type=Path, help="Apply saved preview after rechecking")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--helper-image", help="Existing immutable local image ID with sh/tar")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    logs = Path("logs")
    logs.mkdir(exist_ok=True)
    logging.basicConfig(filename=logs / "docker-resources.log", level=logging.INFO)
    driver = DockerResources()
    homes = args.home or [str(Path.home() / ".research-workbench")]
    try:
        if args.apply:
            if not args.receipt or not args.archive:
                parser.error("--apply requires --receipt and --archive")
            plan = json.loads(args.apply.read_text())
            with cleanup_locks(homes):
                report = apply_plan(
                    driver,
                    plan,
                    lambda: protections(homes),
                    args.archive,
                    args.helper_image,
                    journal=lambda value: write_receipt(args.receipt, value),
                )
        else:
            retired = json.loads(args.retired.read_text()) if args.retired else {}
            if not isinstance(retired, dict) or any(
                not isinstance(v, str) or not v for v in retired.values()
            ):
                raise ResourceError("retirement_evidence_invalid")
            report = plan_resources(driver.inventory(), protections(homes), retired)
            if args.plan:
                args.plan.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok", True) else 1
    except (ResourceError, OSError, ValueError) as error:
        code = str(error) if isinstance(error, ResourceError) else "resource_io_failed"
        log.error("docker_resources code=%s", code)
        print(json.dumps({"ok": False, "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
