"""Administrator release artifacts and single-writer deployment transactions.

Immutable inputs/records and separate acceptance receipts live outside business
volumes. All container mutations reuse Manager ownership and resource checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import sys
import tarfile
import time
import uuid
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

if __package__:
    from . import manage
else:
    import manage as standalone_manage

    manage = standalone_manage

Refusal = manage.Refusal
LOG = logging.getLogger("rwb.docker.release")
CONTRACT = {
    "control": "release-v1",
    "data": "research-json-v1",
    "credentials": "aes-gcm-v1",
    "dsh": "48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0",
}
IMAGE_PATTERN = r"sha256:[0-9a-f]{64}"
FORMAT_SOURCES = (
    "app/research_web/store.py",
    "app/research_web/credential_backend.py",
    "app/research_web/model_credentials.py",
    "app/research_web/automation/models.py",
    "app/research_web/report_workflows/models.py",
    "app/research_web/report_workflows/migration.py",
    "app/research_web/report_workflows/catalog.py",
)


def canonical_hash(value: Any) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise Refusal("artifact_alias_or_missing")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def tree_hash(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        name = str(path.relative_to(root))
        if path.is_symlink():
            entries.append([name, "link", os.readlink(path)])
        elif path.is_file():
            entries.append([name, "file", stat.S_IMODE(path.stat().st_mode), sha256_file(path)])
        elif path.is_dir():
            entries.append([name, "directory", stat.S_IMODE(path.stat().st_mode)])
    return canonical_hash(entries)


def freeze_source_archive(archive: Path, source: Path) -> None:
    """Safe Git extraction with deterministic public-code modes inside a private root.

    tarfile's data filter intentionally discards directory modes. The manager's
    077 umask must not turn packaged source directories into root-only 0700.
    """
    with tarfile.open(archive) as stream:
        stream.extractall(source, filter="data")
    for path in source.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)


def archive_identity(path: Path, expected_image: str, release_id: str | None = None) -> dict:
    """Stream the standard Docker archive; never extract it before validation."""
    if path.is_symlink():
        raise Refusal("artifact_alias_or_missing")
    members: dict[str, dict] = {}
    manifest, config, index_digest = None, None, None
    config_path = None

    def safe_name(value: str) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value.startswith("/")
            or "\\" in value
            or ".." in PurePosixPath(value).parts
        ):
            raise Refusal("archive_members_invalid")
        return PurePosixPath(value).as_posix()

    try:
        with tarfile.open(path, "r|") as archive:
            for member in archive:
                name = safe_name(member.name)
                if name in members:
                    raise Refusal("archive_members_invalid")
                if member.isdir():
                    members[name] = {"directory": True}
                    continue
                if not member.isfile() or member.size > 32 * manage.GIB:
                    raise Refusal("archive_members_invalid")
                stream = archive.extractfile(member)
                if stream is None:
                    raise Refusal("archive_members_invalid")
                encoded, decoded = hashlib.sha256(), hashlib.sha256()
                parts = []
                is_config = Path(name).name.removesuffix(".json") == expected_image[7:]
                collect = name in {"manifest.json", "index.json"} or is_config
                if collect and member.size > 2 * 1024**2:
                    raise Refusal("archive_metadata_too_large")
                inflater = None
                inflated_size = 0
                first = True
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    if inflater is not None and inflater.eof:
                        raise Refusal("archive_layer_invalid")
                    encoded.update(chunk)
                    if first and chunk[:2] == b"\x1f\x8b":
                        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    first = False
                    if inflater:
                        remaining = chunk
                        while remaining:
                            output = inflater.decompress(remaining, 1024 * 1024)
                            inflated_size += len(output)
                            if inflated_size > 32 * manage.GIB:
                                raise Refusal("archive_layer_too_large")
                            decoded.update(output)
                            if inflater.unused_data:
                                raise Refusal("archive_layer_invalid")
                            remaining = inflater.unconsumed_tail
                    else:
                        decoded.update(chunk)
                    if collect:
                        parts.append(chunk)
                if inflater and not inflater.eof:
                    raise Refusal("archive_layer_invalid")
                members[name] = {
                    "digest": "sha256:" + encoded.hexdigest(),
                    "diff_id": "sha256:" + decoded.hexdigest(),
                }
                if name == "manifest.json":
                    manifest = json.loads(b"".join(parts))
                elif name == "index.json":
                    index_digest = members[name]["digest"]
                elif is_config:
                    config, config_path = json.loads(b"".join(parts)), name
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise Refusal("archive_single_image_required")
        entry = manifest[0]
        if release_id is not None and entry.get("RepoTags") != ["rwb-release:" + release_id]:
            raise Refusal("archive_tags_invalid")
        if (
            not config
            or safe_name(entry.get("Config", "")) != config_path
            or members[config_path]["digest"] != expected_image
        ):
            raise Refusal("archive_image_identity_mismatch")
        if config.get("os") != "linux" or config.get("architecture") != "arm64":
            raise Refusal("release_platform_mismatch")
        layers, diff_ids = entry.get("Layers"), config.get("rootfs", {}).get("diff_ids")
        if (
            not isinstance(layers, list)
            or not isinstance(diff_ids, list)
            or len(layers) != len(diff_ids)
        ):
            raise Refusal("archive_layers_invalid")
        for name, expected_diff in zip(layers, diff_ids, strict=True):
            name = safe_name(name)
            if name not in members or members[name].get("diff_id") != expected_diff:
                raise Refusal("archive_layer_digest_mismatch")
            if (
                name.startswith("blobs/sha256/")
                and members[name]["digest"] != "sha256:" + Path(name).name
            ):
                raise Refusal("archive_layer_digest_mismatch")
        return {
            "config_digest": expected_image,
            "platform": "linux/arm64",
            "labels": config.get("config", {}).get("Labels", {}),
            "archive_manifest_json_digest": members["manifest.json"]["digest"],
            "archive_top_level_index_digest": index_digest,
            "layer_count": len(layers),
        }
    except Refusal:
        raise
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError, zlib.error):
        raise Refusal("archive_format_invalid") from None


def write_once(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise Refusal("record_already_sealed")
    manage.atomic_json(path, value)


def check_compatibility(old: dict, new: dict) -> None:
    if old.get("platform") != "linux/arm64" or new.get("platform") != "linux/arm64":
        raise Refusal("release_platform_mismatch")
    if old.get("compatibility") != CONTRACT or new.get("compatibility") != CONTRACT:
        raise Refusal("release_format_incompatible")
    if old.get("format_source_hashes") != new.get("format_source_hashes"):
        raise Refusal("release_format_compatibility_unknown")


def check_acceptance(sealed: dict, receipt: dict, *, historical: bool = False) -> None:
    if any(
        receipt.get(key) != sealed.get(key) for key in ("release_id", "seal", "controller_hash")
    ):
        raise Refusal("acceptance_identity_mismatch")
    if receipt.get("status") != "PASS":
        raise Refusal("release_not_accepted")
    if not historical and receipt.get("expires_at", 0) <= time.time():
        raise Refusal("acceptance_expired")


class ReleaseStore:
    def __init__(self, root: Path, host_root: str, worktree: str) -> None:
        self.root, self.host_root, self.worktree = Path(root), host_root, worktree
        self.manager = manage.Manager(self.root, host_root, worktree)

    def directory(self, release_id: str) -> Path:
        manage.validate_name(release_id)
        path = self.root / "releases" / release_id
        if path.is_symlink() or path.parent.is_symlink():
            raise Refusal("release_alias")
        return path

    def prepare(self, release_id: str, source: str, reuse: str) -> dict:
        if not re.fullmatch(r"[a-f0-9]{40}", source) or not re.fullmatch(IMAGE_PATTERN, reuse):
            raise Refusal("frozen_source_and_image_required")
        path = self.directory(release_id)
        if path.exists():
            raise Refusal("release_id_already_reserved")
        if shutil.disk_usage(self.root).free < 20 * manage.GIB:
            raise Refusal("release_disk_space_insufficient")
        image = manage.inspect("image", reuse)
        labels = image["Config"].get("Labels", {})
        if image["Os"] != "linux" or image["Architecture"] != "arm64":
            raise Refusal("release_platform_mismatch")
        if labels.get(manage.PREFIX + "model-credentials") != CONTRACT["credentials"]:
            raise Refusal("encrypted_model_image_required")
        source_actual = manage.command(
            "git",
            "-c",
            f"safe.directory={self.worktree}",
            "-C",
            self.worktree,
            "rev-parse",
            source + "^{commit}",
        )
        if source_actual != source:
            raise Refusal("source_sha_mismatch")
        path.mkdir(parents=True, mode=0o700)
        archive = path / "source.tar"
        manage.command(
            "git",
            "-c",
            f"safe.directory={self.worktree}",
            "-C",
            self.worktree,
            "archive",
            "--format=tar",
            "--output=" + str(archive),
            source,
        )
        (path / "source").mkdir(mode=0o700)
        freeze_source_archive(archive, path / "source")
        source_root = path / "source"
        sys.path.insert(0, str(source_root))
        from research_workbench_entrypoint.docker_resources import DockerResources, ResourceSession

        runtime = json.loads((source_root / "runtimes/research_web.json").read_text())
        if runtime["dsh"]["commit"] != CONTRACT["dsh"]:
            raise Refusal("dsh_pin_mismatch")
        # The frozen repository controls the administrator, including the launcher.
        (path / "control").mkdir(mode=0o700)
        for name in ("manage.py", "release.py"):
            shutil.copyfile(source_root / "docker" / name, path / "control" / name)
        shutil.copyfile(source_root / "rwb-docker", path / "control" / "rwb-docker")
        for name, running in (
            ("manage.py", Path(__file__).parent / "manage.py"),
            ("release.py", Path(__file__)),
            ("rwb-docker", Path(self.worktree) / "rwb-docker"),
        ):
            if sha256_file(path / "control" / name) != sha256_file(running):
                raise Refusal("prepare_controller_source_mismatch")
        # A stopped, bounded extraction container; no business data or secrets.
        temporary = f"rwb-release-export-{release_id}-{uuid.uuid4().hex[:8]}"
        bind_args = []
        for name, target in (
            ("data", "/data/research-web"),
            ("state", "/state"),
            ("credentials", "/run/rwb-secrets"),
        ):
            (path / "empty" / name).mkdir(parents=True, mode=0o700)
            bind_args += [
                "--mount",
                f"type=bind,src={self.host_root}/releases/{release_id}/empty/{name},dst={target}",
            ]
        resource_session = ResourceSession(DockerResources(), "g2b-release-export")
        resource_session.resources.append(("container", temporary))
        resource_session.pending.add(("container", temporary))
        identifier = manage.command(
            "docker",
            "create",
            "--name",
            temporary,
            "--read-only",
            "--network",
            "none",
            "--memory",
            "128m",
            "--memory-swap",
            "128m",
            "--cpus",
            ".5",
            "--pids-limit",
            "32",
            "--label",
            manage.PREFIX + "release-export=" + release_id,
            *resource_session.flags,
            *bind_args,
            "--entrypoint",
            "/bin/true",
            reuse,
        )
        # Exit the fixed /bin/true helper before copying; ResourceSession then
        # cleans an exact stopped helper rather than adopting an unstarted one.
        manage.command("docker", "start", "--attach", identifier)
        projection = manage.identity_projection(manage.inspect("container", identifier))
        resource_session.pending.discard(("container", temporary))
        try:
            (path / "dsh").mkdir()
            manage.command(
                "docker",
                "cp",
                identifier + ":/opt/dsh/.",
                str(path / "dsh" / "runtime"),
                timeout=900,
            )
            manage.command(
                "docker",
                "cp",
                identifier + ":/usr/local/lib/node_modules/corepack",
                str(path / "dsh" / "corepack"),
                timeout=120,
            )
        finally:
            current = manage.inspect("container", identifier)
            if manage.identity_projection(current) != projection or current["State"]["Running"]:
                raise Refusal("release_export_ownership_mismatch")
            resource_session.cleanup()
        prepared = {
            "schema": 1,
            "administrative_image_id": os.environ.get("RWB_CONTROL_IMAGE_ID"),
            "release_id": release_id,
            "source_sha": source,
            "source_archive_hash": sha256_file(archive),
            "frozen_tree_hash": tree_hash(source_root),
            "controller_hash": tree_hash(path / "control"),
            "dsh_payload_hash": tree_hash(path / "dsh"),
            "dsh_reused_image_id": reuse,
            "dsh_commit": CONTRACT["dsh"],
            "platform": "linux/arm64",
            "compatibility": CONTRACT,
            "format_source_hashes": {
                name: sha256_file(source_root / name) for name in FORMAT_SOURCES
            },
            "dependency_locks": {
                name: sha256_file(source_root / name)
                for name in ("requirements/web.lock", "runtimes/research_web.json")
            },
            "prepared_at": time.time(),
            "base_images": {
                "python": "python:3.12.13-slim-bookworm",
                "node": "node:24.19.0-bookworm-slim",
            },
        }
        write_once(path / "prepared.json", prepared)
        return prepared

    def seal(self, release_id: str) -> dict:
        path = self.directory(release_id)
        prepared = json.loads((path / "prepared.json").read_text())
        if tree_hash(path / "source") != prepared["frozen_tree_hash"]:
            raise Refusal("frozen_source_changed")
        if tree_hash(path / "control") != prepared["controller_hash"]:
            raise Refusal("controller_changed")
        if tree_hash(path / "dsh") != prepared["dsh_payload_hash"]:
            raise Refusal("dsh_payload_changed")
        metadata = json.loads((path / "build-metadata.json").read_text())
        image_id = metadata.get("containerimage.config.digest")
        if not isinstance(image_id, str) or not re.fullmatch(IMAGE_PATTERN, image_id):
            raise Refusal("build_identity_missing")
        archive = archive_identity(path / "image.tar", image_id, release_id)
        bases = {}
        for name in ("python", "node"):
            descriptor = json.loads((path / ("base-" + name + ".json")).read_text())
            if not re.fullmatch(IMAGE_PATTERN, descriptor.get("digest", "")):
                raise Refusal("base_digest_unavailable")
            bases[name] = {"index_digest": descriptor["digest"], "descriptor": descriptor}
        value = {
            **prepared,
            "base_images": bases,
            "local_image_id": image_id,
            "build_manifest_digest": metadata.get("containerimage.digest"),
            "registry_manifest_digest": None,
            "registry_index_digest": None,
            "registry_reason": "NOT_PUBLISHED",
            "registry_reference": None,
            "export_format": "docker-archive",
            "export_hash": sha256_file(path / "image.tar"),
            "build_identity": metadata.get("buildx.build.ref"),
            "build_metadata_hash": sha256_file(path / "build-metadata.json"),
            "archive_identity": archive,
            "sealed_at": time.time(),
        }
        write_once(path / "release.json", value)
        write_once(path / "seal.json", {"seal": canonical_hash(value)})
        LOG.info("release_sealed release=%s", release_id)
        return self.verify(release_id, require_image=True)

    def verify(self, release_id: str, *, require_image: bool = True) -> dict:
        path = self.directory(release_id)
        value = json.loads((path / "release.json").read_text())
        seal = json.loads((path / "seal.json").read_text())["seal"]
        if canonical_hash(value) != seal or value["release_id"] != release_id:
            raise Refusal("release_seal_mismatch")
        check_compatibility(value, value)
        archive = archive_identity(path / "image.tar", value["local_image_id"], release_id)
        if archive != value["archive_identity"]:
            raise Refusal("archive_image_identity_mismatch")
        if (
            any(
                archive["labels"].get(key) != expected
                for key, expected in {
                    "org.opencontainers.image.revision": value["source_sha"],
                    manage.PREFIX + "release-id": release_id,
                    manage.PREFIX + "release-control": CONTRACT["control"],
                    manage.PREFIX + "model-credentials": CONTRACT["credentials"],
                    manage.PREFIX + "controller-hash": value["controller_hash"],
                    manage.PREFIX + "runtime": "docker",
                }.items()
            )
            or archive["labels"].get(manage.PREFIX + "role") == "development"
        ):
            raise Refusal("release_image_identity_mismatch")
        for name, expected in (
            ("image.tar", value["export_hash"]),
            ("source.tar", value["source_archive_hash"]),
            ("build-metadata.json", value["build_metadata_hash"]),
        ):
            if sha256_file(path / name) != expected:
                raise Refusal("artifact_digest_mismatch")
        if tree_hash(path / "control") != value["controller_hash"]:
            raise Refusal("controller_changed")
        if (
            tree_hash(path / "source") != value["frozen_tree_hash"]
            or tree_hash(path / "dsh") != value["dsh_payload_hash"]
        ):
            raise Refusal("frozen_input_changed")
        if require_image:
            info = manage.inspect("image", value["local_image_id"])
            labels = info["Config"].get("Labels", {})
            if info["Os"] != "linux" or info["Architecture"] != "arm64":
                raise Refusal("release_platform_mismatch")
            if (
                info["Id"] != value["local_image_id"]
                or any(
                    labels.get(key) != expected
                    for key, expected in {
                        "org.opencontainers.image.revision": value["source_sha"],
                        manage.PREFIX + "release-id": release_id,
                        manage.PREFIX + "release-control": CONTRACT["control"],
                        manage.PREFIX + "model-credentials": CONTRACT["credentials"],
                        manage.PREFIX + "controller-hash": value["controller_hash"],
                    }.items()
                )
                or labels.get(manage.PREFIX + "role") == "development"
            ):
                raise Refusal("release_image_identity_mismatch")
        return {**value, "seal": seal}

    def import_artifact(self, release_id: str) -> dict:
        value = self.verify(release_id, require_image=False)
        manage.command(
            "docker", "load", "--input", str(self.directory(release_id) / "image.tar"), timeout=900
        )
        self.verify(release_id)
        return {
            "release_id": release_id,
            "image_id": value["local_image_id"],
            "import_verified": True,
        }

    def bound_controller(self, release_id: str) -> dict:
        value = self.verify(release_id)
        if value.get("administrative_image_id") != os.environ.get("RWB_CONTROL_IMAGE_ID"):
            raise Refusal("sealed_administrative_image_required")
        actual = Path(__file__).resolve().parent
        if (
            actual != (self.directory(release_id) / "control").resolve()
            or tree_hash(actual) != value["controller_hash"]
        ):
            raise Refusal("sealed_controller_required")
        return value

    def control(self, record: dict, action: str, transaction: str) -> dict:
        self.manager.owned(record)
        return json.loads(
            manage.command(
                "docker",
                "exec",
                record["container_id"],
                "/opt/rwb/venv/bin/python",
                "-I",
                "-B",
                "/opt/rwb/app/research_web/maintenance.py",
                action,
                transaction,
                timeout=30,
            )
        )

    def probe(self, record: dict, release: dict) -> dict:
        self.manager.owned(record)
        # Product protocol and installed identity, no paid prompt or secret output.
        code = """import json,urllib.request,sys
from pathlib import Path
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:8088'+path,timeout=20) as r:
  assert r.status==200
  return r.read()
version=json.loads(get('/api/research/release'))
assert version['source_sha']==sys.argv[1] and version['release_id']==sys.argv[2]
assert version['controller_hash']==sys.argv[3]
runtime=json.loads(get('/api/research/runtime'))
assert runtime['connected'] is True and runtime['health_check_passed'] is True
assert runtime['credential_storage']=='docker_encrypted' and runtime.get('credential_code') is None
assert len(get('/'))>100 and len(get('/static/app.mjs'))>100
print(json.dumps({'protocol':True,'web':True,'static':True,'version':True,'model_backend':True}))
"""
        return json.loads(
            manage.command(
                "docker",
                "exec",
                record["container_id"],
                "/opt/rwb/venv/bin/python",
                "-I",
                "-B",
                "-c",
                code,
                release["source_sha"],
                release["release_id"],
                release["controller_hash"],
                timeout=90,
            )
        )

    def accept(self, release_id: str, instance: str) -> dict:
        value = self.bound_controller(release_id)
        record = self.manager.read("stage", instance)
        if record["image"] != value["local_image_id"] or len(record["volumes"]) != 5:
            raise Refusal("stage_artifact_or_credentials_mismatch")
        self.manager.owned(record)
        result = self.probe(record, value)
        transaction = uuid.uuid4().hex
        state = self.control(record, "status", transaction)
        if state["maintenance"] or state["idle"] is not True:
            raise Refusal("stage_idle_unconfirmed")
        receipt = {
            "schema": 1,
            "release_id": release_id,
            "seal": value["seal"],
            "controller_hash": value["controller_hash"],
            "status": "PASS",
            "probe": result,
            "stage_identity": canonical_hash(record),
            "stage_image_id": record["image"],
            "accepted_at": time.time(),
            "expires_at": time.time() + 86400,
            "real_supplier_for_this_artifact": "NOT_RUN",
        }
        receipt_path = self.directory(release_id) / "acceptance.json"
        receipt_root = self.directory(release_id) / "receipts"
        receipt_root.mkdir(exist_ok=True, mode=0o700)
        write_once(receipt_root / (uuid.uuid4().hex + ".json"), receipt)
        manage.atomic_json(receipt_path, receipt)
        return receipt

    def check_target_plan(self, plan: dict, record: dict) -> None:
        if (
            record.get("purpose") != "rehearsal"
            or plan.get("environment") != record.get("environment")
            or plan.get("instance") != record.get("instance")
        ):
            raise Refusal("explicit_rehearsal_target_required")
        if plan.get("expires_at", 0) <= time.time():
            raise Refusal("plan_expired")
        if plan.get("target_hash") != canonical_hash(record):
            raise Refusal("stale_plan")

    def plan(
        self,
        controller: str,
        environment: str,
        instance: str,
        *,
        rollback: bool = False,
        recovery: bool = False,
    ) -> dict:
        control = self.bound_controller(controller)
        record = self.manager.read(environment, instance)
        self.manager.verify_resources(record)
        if record["container_id"]:
            self.manager.owned(record)
        if record.get("deployment", {}).get("state") == "RECOVERY_REQUIRED" and not recovery:
            raise Refusal("recovery_plan_required")
        target_id = (
            (record.get("accepted_release") if recovery else record.get("previous_release"))
            if rollback
            else controller
        )
        if not target_id:
            raise Refusal("previous_accepted_release_missing")
        target = self.verify(target_id)
        check_compatibility(control, target)
        receipt = json.loads((self.directory(target_id) / "acceptance.json").read_text())
        check_acceptance(target, receipt, historical=rollback)
        if record.get("accepted_release"):
            old = self.verify(record["accepted_release"])
            check_compatibility(old, target)
            if rollback and target_id not in record.get("accepted_history", []):
                raise Refusal("rollback_not_previously_accepted")
        value = {
            "schema": 1,
            "id": uuid.uuid4().hex,
            "action": "rollback" if rollback else "deploy",
            "environment": environment,
            "instance": instance,
            "target_hash": canonical_hash(record),
            "from_release": record.get("accepted_release"),
            "to_release": target_id,
            "release_seal": target["seal"],
            "acceptance_hash": canonical_hash(receipt),
            "controller_release": controller,
            "controller_hash": control["controller_hash"],
            "local_image_id": target["local_image_id"],
            "transport": "verified-docker-archive",
            "registry_digest_verified": False,
            "created_at": time.time(),
            "expires_at": time.time() + 600,
            "recovery": recovery,
        }
        self.check_target_plan(value, record)
        return value

    def _switch(self, record: dict, release: dict) -> None:
        self.manager.verify_resources(record)
        if record["container_id"]:
            self.manager.stop(record)
            self.manager.owned(record)
            manage.command("docker", "rm", record["container_id"])
        record.update(
            image=release["local_image_id"],
            source_sha=release["source_sha"],
            container_id=None,
            projection=None,
        )
        manage.atomic_json(self.manager.path(record["environment"], record["instance"]), record)
        self.manager.up(record)

    def _offline_gate(self, record: dict, transaction: str) -> None:
        self.manager.verify_resources(record)
        if record["container_id"] and self.manager.owned(record)["State"]["Running"]:
            raise Refusal("offline_gate_writer_running")
        code = """import os,json,sys
from pathlib import Path
p=Path('/data/research-web/.release-maintenance.json')
if p.is_symlink(): raise RuntimeError('alias')
q=p.with_suffix('.pending')
if q.exists() or q.is_symlink(): raise RuntimeError('unfinished')
if p.exists():
 prior=json.loads(p.read_text())
 assert prior['schema']==1 and (prior['transaction']==sys.argv[1] or prior.get('state')=='released')
with q.open('x') as f:
 os.chmod(q,0o600);json.dump({'schema':1,'transaction':sys.argv[1],'state':'maintenance'},f);f.flush();os.fsync(f.fileno())
q.replace(p)
fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
try: os.fsync(fd)
finally: os.close(fd)
print('gate_ready')
"""
        manage.command(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "10001:10001",
            "--memory",
            "128m",
            "--memory-swap",
            "128m",
            "--cpus",
            ".5",
            "--pids-limit",
            "32",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--mount",
            f"type=volume,src={record['volumes']['data']},dst=/data/research-web",
            "--mount",
            f"type=volume,src={record['volumes']['credentials']},dst=/run/rwb-secrets,readonly",
            "--tmpfs",
            "/state:rw,size=1m",
            "--entrypoint",
            "/opt/rwb/venv/bin/python",
            record["image"],
            "-I",
            "-B",
            "-c",
            code,
            transaction,
        )

    def apply(self, controller: str, plan: dict) -> dict:
        control = self.bound_controller(controller)
        if (
            plan.get("controller_release") != controller
            or plan.get("controller_hash") != control["controller_hash"]
        ):
            raise Refusal("plan_controller_mismatch")
        record = self.manager.read(plan["environment"], plan["instance"])
        journal = record.get("deployment", {})
        if journal.get("plan_id") == plan.get("id") and journal.get("state") == "accepted":
            if journal.get("plan_hash") != canonical_hash(plan):
                raise Refusal("completed_plan_changed")
            self.manager.owned(record)
            return self.status(record)
        if (
            journal
            and journal.get("state") not in {"accepted", "refused", "restored"}
            and not plan.get("recovery")
        ):
            raise Refusal("unfinished_transaction_recovery_required")
        self.check_target_plan(plan, record)
        target = self.verify(plan["to_release"])
        if (
            target["seal"] != plan["release_seal"]
            or target["local_image_id"] != plan["local_image_id"]
        ):
            raise Refusal("plan_release_identity_mismatch")
        receipt = json.loads((self.directory(plan["to_release"]) / "acceptance.json").read_text())
        check_acceptance(target, receipt, historical=plan["action"] == "rollback")
        if canonical_hash(receipt) != plan["acceptance_hash"]:
            raise Refusal("acceptance_changed")
        old = self.verify(record["accepted_release"]) if record.get("accepted_release") else None
        check_compatibility(old or target, target)
        if len(record["volumes"]) != 5 or record.get("model_store_state") != "ready":
            raise Refusal("independent_model_initialization_required")
        transaction = journal.get("transaction") if plan.get("recovery") else uuid.uuid4().hex
        if not transaction:
            raise Refusal("recovery_transaction_unknown")
        self.check_target_plan(plan, record)
        self.manager.verify_resources(record)
        if record["container_id"]:
            self.manager.owned(record)
        record["deployment"] = {
            "plan_id": plan["id"],
            "plan_hash": canonical_hash(plan),
            "transaction": transaction,
            "state": "prepared",
            "from": record.get("accepted_release"),
            "to": plan["to_release"],
            "controller": controller,
        }
        ledger = self.manager.path(record["environment"], record["instance"])
        manage.atomic_json(ledger, record)
        writer_running = bool(
            record["container_id"] and self.manager.owned(record)["State"]["Running"]
        )
        switched = False
        resume_attempted = False
        try:
            if writer_running:
                self.control(record, "begin", transaction)
                deadline = time.monotonic() + 30
                while True:
                    state = self.control(record, "status", transaction)
                    if state["maintenance"] and state["idle"] is True:
                        break
                    if time.monotonic() >= deadline:
                        resume_attempted = True
                        self.control(record, "end", transaction)
                        record["deployment"]["state"] = "refused"
                        manage.atomic_json(ledger, record)
                        raise Refusal("tasks_busy_or_idle_unknown")
                    time.sleep(1)
            else:
                self._offline_gate(record, transaction)
            record["deployment"]["state"] = "switching"
            manage.atomic_json(ledger, record)
            switched = True
            self._switch(record, target)
            self.probe(record, target)
            state = self.control(record, "status", transaction)
            if not state["maintenance"] or state["idle"] is not True:
                raise Refusal("candidate_idle_unconfirmed")
            previous = record.get("accepted_release")
            record["previous_release"] = previous
            record["accepted_release"] = target["release_id"]
            history = record.setdefault("accepted_history", [])
            if target["release_id"] not in history:
                history.append(target["release_id"])
            record["deployment"]["state"] = "accepted_maintenance"
            manage.atomic_json(ledger, record)
            resume_attempted = True
            self.control(record, "end", transaction)
            record["deployment"]["state"] = "accepted"
            manage.atomic_json(ledger, record)
            LOG.info(
                "release_accepted instance=%s release=%s", record["instance"], target["release_id"]
            )
            return self.status(record)
        except Exception as exc:
            LOG.error(
                "deployment_failed instance=%s category=%s", record["instance"], type(exc).__name__
            )
            if record["deployment"]["state"] == "refused":
                raise
            record["deployment"]["state"] = "RECOVERY_REQUIRED"
            manage.atomic_json(ledger, record)
            if resume_attempted:
                # end may have admitted new research. Never stop or automatically
                # switch a writer after that boundary, even on an ambiguous reply.
                raise Refusal("RECOVERY_REQUIRED") from None
            if switched and old:
                # No old writer until candidate exit is positively confirmed.
                self.manager.stop(record)
                check_compatibility(old, target)
                self._switch(record, old)
                self.probe(record, old)
                state = self.control(record, "status", transaction)
                if state["maintenance"] and state["idle"] is True:
                    record["accepted_release"] = old["release_id"]
                    record["deployment"]["state"] = "restored"
                    manage.atomic_json(ledger, record)
                    self.control(record, "end", transaction)
                    raise Refusal("candidate_failed_previous_restored") from None
            raise Refusal("RECOVERY_REQUIRED") from None

    def status(self, record: dict) -> dict:
        value = self.manager.status(record)
        return {
            **value,
            "purpose": record.get("purpose"),
            "actual_image": record["image"],
            "accepted_release": record.get("accepted_release"),
            "previous_release": record.get("previous_release"),
            "deployment": record.get("deployment"),
        }

    def resume(self, controller: str, environment: str, instance: str) -> dict:
        self.bound_controller(controller)
        record = self.manager.read(environment, instance)
        journal = record.get("deployment", {})
        if journal.get("state") not in {"accepted", "restored"} or not record.get(
            "accepted_release"
        ):
            raise Refusal("accepted_resume_required")
        accepted = self.verify(record["accepted_release"])
        if record["image"] != accepted["local_image_id"]:
            raise Refusal("accepted_image_mismatch")
        self.probe(record, accepted)
        state = self.control(record, "status", journal["transaction"])
        if state["idle"] is not True:
            raise Refusal("tasks_busy_or_idle_unknown")
        if state["maintenance"]:
            self.control(record, "end", journal["transaction"])
        return self.status(record)

    def registry_plan(self, release_id: str) -> dict:
        value = self.bound_controller(release_id)
        reference = (
            f"ghcr.io/leon-huang001208/researchworkbench:{release_id}-{value['local_image_id'][7:]}"
        )
        return {
            "release_id": release_id,
            "seal": value["seal"],
            "reference": reference,
            "image_id": value["local_image_id"],
            "platform": "linux/arm64",
            "authorization": "explicit-publish-required",
            "visibility_change": False,
            "registry_publish": "NOT_RUN",
            "registry_digest_pull": "NOT_RUN",
        }

    def registry_selection(self, release_id: str) -> dict:
        plan = self.registry_plan(release_id)
        path = self.directory(release_id)
        descriptor_path, manifest_path = (
            path / "registry-descriptor.json",
            path / "registry-raw-manifest.json",
        )
        sha256_file(descriptor_path)
        sha256_file(manifest_path)
        descriptor = json.loads(descriptor_path.read_text())
        raw = json.loads(manifest_path.read_text())
        top = descriptor.get("digest")
        if not isinstance(top, str) or not re.fullmatch(IMAGE_PATTERN, top):
            raise Refusal("registry_digest_unavailable")
        candidates = raw.get("manifests")
        if candidates is not None:
            selected = [
                item
                for item in candidates
                if item.get("platform", {}).get("os") == "linux"
                and item.get("platform", {}).get("architecture") == "arm64"
            ]
            if len(selected) != 1:
                raise Refusal("registry_platform_manifest_ambiguous")
            platform_digest, index_digest = selected[0].get("digest"), top
        else:
            if raw.get("mediaType") not in {
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.docker.distribution.manifest.v2+json",
            }:
                raise Refusal("registry_manifest_invalid")
            platform_digest, index_digest = top, None
        if not isinstance(platform_digest, str) or not re.fullmatch(IMAGE_PATTERN, platform_digest):
            raise Refusal("registry_digest_unavailable")
        selected = {
            "release_id": release_id,
            "seal": plan["seal"],
            "reference": plan["reference"],
            "manifest_digest": platform_digest,
            "index_digest": index_digest,
            "pull_reference": plan["reference"].split(":", 1)[0] + "@" + platform_digest,
        }
        manage.atomic_json(path / "registry-selection.json", selected)
        return selected

    def registry_record(self, release_id: str) -> dict:
        value = self.bound_controller(release_id)
        path = self.directory(release_id)
        selected = self.registry_selection(release_id)
        sha256_file(path / "registry-pulled-image.json")
        pulled = json.loads((path / "registry-pulled-image.json").read_text())
        if pulled != {"image_id": value["local_image_id"], "os": "linux", "architecture": "arm64"}:
            raise Refusal("registry_pulled_artifact_mismatch")
        inspected = manage.inspect("image", selected["pull_reference"])
        if (
            inspected["Id"] != value["local_image_id"]
            or inspected["Architecture"] != "arm64"
            or inspected["Os"] != "linux"
        ):
            raise Refusal("registry_pulled_artifact_mismatch")
        receipt = {
            **selected,
            "registry_publish": "PASS",
            "registry_digest_pull": "PASS",
            "image_id": inspected["Id"],
            "platform": "linux/arm64",
            "verified_at": time.time(),
            "visibility_change": False,
            "controller_hash": value["controller_hash"],
        }
        receipt_root = path / "receipts"
        receipt_root.mkdir(exist_ok=True, mode=0o700)
        write_once(receipt_root / ("registry-" + uuid.uuid4().hex + ".json"), receipt)
        manage.atomic_json(path / "registry.json", receipt)
        return receipt


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("release_id", type=manage.validate_name)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "seal",
            "inspect",
            "verify",
            "import",
            "accept",
            "deploy-plan",
            "rollback-plan",
            "apply",
            "status",
            "resume",
            "registry-plan",
            "registry-selection",
            "registry-record",
        ),
    )
    parser.add_argument("--source")
    parser.add_argument("--reuse-dsh-image")
    parser.add_argument("--environment", choices=("stage", "prod"), default="prod")
    parser.add_argument("--instance", type=manage.validate_name, default="g2b-rehearsal")
    parser.add_argument("--plan")
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        filename="/ledger/logs/release.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    store = ReleaseStore(
        Path("/ledger"), os.environ["RWB_MANAGER_ROOT"], os.environ["RWB_WORKTREE"]
    )
    try:
        if args.action == "prepare":
            output = store.prepare(args.release_id, args.source or "", args.reuse_dsh_image or "")
        elif args.action == "seal":
            output = store.seal(args.release_id)
        elif args.action == "import":
            output = store.import_artifact(args.release_id)
        elif args.action == "accept":
            output = store.accept(args.release_id, args.instance)
        elif args.action in {"deploy-plan", "rollback-plan"}:
            output = store.plan(
                args.release_id,
                args.environment,
                args.instance,
                rollback=args.action == "rollback-plan",
                recovery=args.recovery,
            )
        elif args.action == "apply":
            path = Path(args.plan or "")
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(
                Path("/ledger/plans").resolve(strict=True)
            ):
                raise Refusal("managed_plan_path_required")
            output = store.apply(args.release_id, json.loads(path.read_text()))
        elif args.action == "status":
            store.bound_controller(args.release_id)
            output = store.status(store.manager.read(args.environment, args.instance))
        elif args.action == "resume":
            output = store.resume(args.release_id, args.environment, args.instance)
        elif args.action == "registry-plan":
            output = store.registry_plan(args.release_id)
        elif args.action == "registry-selection":
            output = store.registry_selection(args.release_id)
        elif args.action == "registry-record":
            output = store.registry_record(args.release_id)
        else:
            output = store.verify(args.release_id)
        print(json.dumps(output, sort_keys=True))
        return 0
    except Exception as exc:
        LOG.error("release_operation_refused category=%s", type(exc).__name__)
        print(
            str(exc) if isinstance(exc, Refusal) else "release_operation_failed",
            file=__import__("sys").stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
