"""Explicit, fingerprint-bound recovery of the registered local BuildKit builder.

Only allowlisted projections are archived. A failed transaction preserves its
archive and resources; recovery verifies their recorded identities before reuse.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
from pathlib import Path

from .docker_resources import DockerResources, ResourceError
from .iteration_cache import GIB, operation_lock

log = logging.getLogger(__name__)
BUILDER = "rwb-dev-builder"
CONTAINER = "buildx_buildkit_rwb-dev-builder0"
VOLUME = "rwb-dev-builder-state"
IMAGE = "moby/buildkit:v0.28.0"
LABEL = "io.research-workbench.manager"
FORMAT = '{{.Id}} {{.Config.Image}} {{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}} {{.HostConfig.PidsLimit}} {{.HostConfig.LogConfig.Type}} {{index .HostConfig.LogConfig.Config "max-size"}} {{index .HostConfig.LogConfig.Config "max-file"}} {{index .Config.Labels "io.research-workbench.manager"}}'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_safe(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise ResourceError("builder_record_unsafe")
    return path.read_text()


def write_json(path, value):
    if path.is_symlink() or path.with_suffix(".pending").is_symlink():
        raise ResourceError("builder_archive_alias")
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    pending.chmod(0o600)
    pending.replace(path)


class BuilderReconcile(DockerResources):
    def __init__(self, root, project):
        self.root, self.project = Path(root), Path(project)

    def call(self, *args, timeout=30):
        # Still inspect the user's current selection, but pin every resource
        # operation so a concurrent `docker context use` cannot redirect it.
        if args == ("context", "show"):
            return super().call(*args, timeout=timeout)
        return super().call("--context", "desktop-linux", *args, timeout=timeout)

    def binding(self):
        if any(
            os.environ.get(key)
            for key in (
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_TLS_VERIFY",
                "DOCKER_CERT_PATH",
                "BUILDX_BUILDER",
                "BUILDX_CONFIG",
                "DOCKER_CONFIG",
            )
        ):
            raise ResourceError("builder_environment_override")
        if self.call("context", "show").strip() != "desktop-linux":
            raise ResourceError("builder_context_changed")
        endpoint = json.loads(
            self.call(
                "context", "inspect", "desktop-linux", "--format", "{{json .Endpoints.docker.Host}}"
            )
        )
        if endpoint != "unix://" + str(Path.home() / ".docker/run/docker.sock"):
            raise ResourceError("builder_socket_changed")
        info = json.loads(self.call("info", "--format", "{{json .}}"))
        if (
            not info.get("ID")
            or info.get("OperatingSystem") != "Docker Desktop"
            or info.get("OSType") != "linux"
        ):
            raise ResourceError("builder_engine_invalid")
        text = self.call("buildx", "inspect", BUILDER)
        names = re.findall(r"^Name:\s+(\S+)\s*$", text, re.MULTILINE)
        drivers = re.findall(r"^Driver:\s+(\S+)\s*$", text, re.MULTILINE)
        endpoints = re.findall(r"^Endpoint:\s+(\S+)\s*$", text, re.MULTILINE)
        options = re.findall(r"^Driver Options:\s*(.*)$", text, re.MULTILINE)
        statuses = re.findall(r"^Status:\s+(\S+)\s*$", text, re.MULTILINE)
        flags = re.findall(r"^BuildKit daemon flags:\s*(.*)$", text, re.MULTILINE)
        parsed_options = (
            dict(re.findall(r'([\w-]+)="([\w-]+)"', options[0])) if len(options) == 1 else {}
        )
        option_remainder = re.sub(r'[\w-]+="[\w-]+"', "", options[0] if options else "")
        if (
            names != [BUILDER, BUILDER + "0"]
            or drivers != ["docker-container"]
            or endpoints != ["desktop-linux"]
            or parsed_options
            not in (
                {
                    "cpu-period": "100000",
                    "cpu-quota": "200000",
                    "memory": "3g",
                    "memory-swap": "3g",
                },
                {
                    "cpu-period": "100000",
                    "cpu-quota": "200000",
                    "memory": "5g",
                    "memory-swap": "5g",
                },
            )
            or len(re.findall(r'([\w-]+)="([\w-]+)"', options[0] if options else "")) != 4
            or option_remainder.strip()
            or statuses not in (["inactive"], ["stopped"], ["running"])
            or flags != ["--allow-insecure-entitlement=network.host"]
        ):
            raise ResourceError("builder_binding_changed")
        self.builder_status = statuses[0]
        # Do not persist unrestricted inspect text (driver env may contain secrets).
        projection = {
            "names": names,
            "drivers": drivers,
            "endpoints": endpoints,
            "driverOptions": parsed_options,
            "flags": flags,
        }
        return {
            "engine": info["ID"],
            "endpoint": endpoint,
            "context": "desktop-linux",
            "buildx": projection,
        }

    def active_build(self):
        try:
            result = subprocess.run(
                ["ps", "-axo", "args="], capture_output=True, text=True, check=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            raise ResourceError("builder_process_check_failed") from None
        if len(result.stdout) > 2 * 1024 * 1024:
            raise ResourceError("builder_process_output_limit")
        for line in result.stdout.splitlines():
            # Match only the process executable, never command text embedded in
            # our invoking shell or a probe script. Global Docker options may
            # precede buildx/build, so scan subsequent tokens conservatively.
            first = line.strip().split(maxsplit=1)[0] if line.strip() else ""
            if Path(first).name not in {"docker", "docker-buildx", "buildx", "com.docker.cli"}:
                continue
            if len(line) > 16384:
                raise ResourceError("builder_process_output_limit")
            try:
                arguments = shlex.split(line)
            except ValueError:
                raise ResourceError("builder_process_check_failed") from None
            if {"build", "bake"}.intersection(arguments[1:]):
                raise ResourceError("builder_build_active")

    def resources(self):
        containers = self.call(
            "ps", "-aq", "--no-trunc", "--filter", f"name=^/{CONTAINER}$"
        ).splitlines()
        volumes = self.call("volume", "ls", "-q", "--filter", f"name=^{VOLUME}$").splitlines()
        if len(containers) > 1 or volumes not in ([], [VOLUME]):
            raise ResourceError("builder_resource_ambiguous")
        return containers, volumes

    def record(self):
        value = read_safe(self.root / "builder.id").strip()
        expected = f"{IMAGE} {5 * GIB} {5 * GIB} 200000 100000 256 json-file 10m 3 {self.root}"
        identity, separator, rest = value.partition(" ")
        if not separator or not re.fullmatch("[0-9a-f]{64}", identity) or rest != expected:
            raise ResourceError("builder_old_record_invalid")
        config = read_safe(self.root / "buildkitd.toml")
        if config != read_safe(self.project / "docker/buildkitd.toml"):
            raise ResourceError("builder_configuration_changed")
        return value, config

    def budget(self, owned_running=None):
        if self.call(
            "ps", "-q", "--filter", "label=io.research-workbench.environment=stage"
        ).strip():
            raise ResourceError("builder_stage_active")
        reservations = []
        for identity in self.call("ps", "-q", "--no-trunc").splitlines():
            if identity == owned_running:
                continue
            memory = int(self.call("inspect", "--format", "{{.HostConfig.Memory}}", identity))
            if memory <= 0:
                raise ResourceError("builder_unbounded_service")
            reservations.append([identity, memory])
        total = int(self.call("info", "--format", "{{.MemTotal}}"))
        if sum(row[1] for row in reservations) + 7 * GIB > total:
            raise ResourceError("builder_memory_gate")
        return {"running": sorted(reservations), "vmMemory": total}

    def volume_identity(self):
        row = json.loads(self.call("volume", "inspect", VOLUME))[0]
        return {
            key: row.get(key)
            for key in ("Name", "CreatedAt", "Driver", "Labels", "Options", "Scope")
        }

    def verify(self, expected_id=None):
        raw = json.loads(self.call("inspect", CONTAINER))[0]
        projection = self.call("inspect", "--format", FORMAT, CONTAINER).strip()
        old, _ = self.record()
        expected = (expected_id or old.split(" ", 1)[0]) + " " + old.split(" ", 1)[1]
        labels = json.loads(self.call("volume", "inspect", "--format", "{{json .Labels}}", VOLUME))
        mounts = raw.get("Mounts", [])
        volume_mount = {"Type": "volume", "Name": VOLUME, "Destination": "/var/lib/buildkit"}
        bind_mount = {
            "Type": "bind",
            "Source": str(self.root / "buildkitd.toml"),
            "Destination": "/etc/buildkit/buildkitd.toml",
            "RW": False,
        }
        if (
            projection != expected
            or raw.get("Id") != expected.split(" ", 1)[0]
            or labels != {LABEL: str(self.root)}
            or len(mounts) != 2
            or not all(
                any(all(m.get(k) == v for k, v in target.items()) for m in mounts)
                for target in (volume_mount, bind_mount)
            )
            or raw.get("Config", {}).get("Labels") != {LABEL: str(self.root)}
            or raw.get("HostConfig", {}).get("Privileged") is not True
            or raw.get("Config", {}).get("Cmd") != ["--config", "/etc/buildkit/buildkitd.toml"]
            or raw.get("HostConfig", {}).get("PortBindings") not in (None, {})
        ):
            raise ResourceError("builder_resource_identity_changed")
        return raw, projection

    def preview(self):
        binding = self.binding()
        self.active_build()
        old, config = self.record()
        containers, volumes = self.resources()
        if bool(containers) != bool(volumes):
            raise ResourceError("builder_resources_partially_missing")
        status = "restore_absent"
        if not containers and self.builder_status == "running":
            raise ResourceError("builder_running")
        if containers:
            raw, _ = self.verify()
            if raw["State"]["Running"]:
                raise ResourceError("builder_running")
            status = "healthy"
        snapshot = {
            "schemaVersion": 1,
            "status": status,
            "binding": binding,
            "oldRecord": old,
            "config": config,
            "budget": self.budget(),
            "volumeIdentity": self.volume_identity() if volumes else None,
            "acknowledgement": "Current local Docker Desktop engine verified; legacy builder.id does not prove the original engine or why resources are absent.",
        }
        return {**snapshot, "fingerprint": digest(snapshot)}

    def apply(self, fingerprint, recover=False):
        archives = self.root / "builder-reconcile"
        if archives.is_symlink():
            raise ResourceError("builder_archive_alias")
        archive = archives / fingerprint
        if not re.fullmatch("[a-f0-9]{64}", fingerprint):
            raise ResourceError("builder_fingerprint_invalid")
        if recover:
            if archive.is_symlink():
                raise ResourceError("builder_archive_alias")
            journal = json.loads(read_safe(archive / "journal.json"))
            preview = json.loads(read_safe(archive / "preview.json"))
            if preview["binding"] != self.binding() or preview["fingerprint"] != fingerprint:
                raise ResourceError("builder_recovery_binding_changed")
            if journal["phase"] not in {
                "prepared",
                "volume_created",
                "container_created",
                "started",
                "complete",
            }:
                raise ResourceError("builder_recovery_phase_invalid")
            containers, volumes = self.resources()
            if journal.get("volumeCreated"):
                if volumes != [VOLUME] or journal.get("volumeIdentity") != self.volume_identity():
                    raise ResourceError("builder_recovery_volume_changed")
            elif containers or volumes:
                raise ResourceError("builder_recovery_unknown_resources")
            if journal["phase"] == "complete":
                raw, _ = self.verify(journal["containerId"])
                if raw["State"]["Running"]:
                    raise ResourceError("builder_running")
                return {"status": "healthy", "fingerprint": fingerprint}
            self.active_build()
            if self.record() != (preview["oldRecord"], preview["config"]):
                raise ResourceError("builder_recovery_record_changed")
            raw = None
            if journal.get("containerId"):
                raw, _ = self.verify(journal["containerId"])
                if containers != [journal["containerId"]]:
                    raise ResourceError("builder_recovery_unknown_resources")
            elif containers:
                raise ResourceError("builder_recovery_unknown_resources")
            self.budget(journal["containerId"] if raw and raw["State"]["Running"] else None)
            # All records, volume, binding, active-build and capacity gates pass
            # before the first mutation, including stopping our journaled ID.
            if raw and raw["State"]["Running"]:
                self.call("stop", "--time", "15", journal["containerId"], timeout=45)
        else:
            preview = self.preview()
            if preview["fingerprint"] != fingerprint:
                raise ResourceError("builder_preview_changed")
            if preview["status"] == "healthy":
                return {"status": "healthy", "fingerprint": fingerprint}
            archives.mkdir(mode=0o700, exist_ok=True)
            archive.mkdir(mode=0o700)
            write_json(archive / "preview.json", preview)
            (archive / "builder.id").write_text(preview["oldRecord"] + "\n")
            (archive / "buildkitd.toml").write_text(preview["config"])
            journal = {"phase": "prepared", "containerId": None, "volumeCreated": False}
            write_json(archive / "journal.json", journal)
        try:
            containers, volumes = self.resources()
            if journal["phase"] == "prepared":
                if containers or volumes:
                    raise ResourceError("builder_recovery_unknown_resources")
                self.call("volume", "create", "--label", f"{LABEL}={self.root}", VOLUME)
                journal.update(
                    phase="volume_created",
                    volumeCreated=True,
                    volumeIdentity=self.volume_identity(),
                )
                write_json(archive / "journal.json", journal)
            if journal.get("volumeIdentity") != self.volume_identity():
                raise ResourceError("builder_recovery_volume_changed")
            if journal["phase"] == "volume_created":
                containers, volumes = self.resources()
                labels = json.loads(
                    self.call("volume", "inspect", "--format", "{{json .Labels}}", VOLUME)
                )
                if containers or volumes != [VOLUME] or labels != {LABEL: str(self.root)}:
                    raise ResourceError("builder_recovery_unknown_resources")
                proxy = self.call("info", "--format", "{{.HTTPProxy}}").strip()
                if proxy not in (
                    "",
                    "http.docker.internal:3128",
                    "http://http.docker.internal:3128",
                ):
                    raise ResourceError("builder_proxy_requires_configuration")
                proxy = "http://http.docker.internal:3128" if proxy else ""
                identity = self.call(
                    "create",
                    "--name",
                    CONTAINER,
                    "--privileged",
                    "--memory",
                    "5g",
                    "--memory-swap",
                    "5g",
                    "--cpu-period",
                    "100000",
                    "--cpu-quota",
                    "200000",
                    "--pids-limit",
                    "256",
                    "--log-driver",
                    "json-file",
                    "--log-opt",
                    "max-size=10m",
                    "--log-opt",
                    "max-file=3",
                    "--label",
                    f"{LABEL}={self.root}",
                    "--env",
                    f"HTTP_PROXY={proxy}",
                    "--env",
                    f"HTTPS_PROXY={proxy}",
                    "--mount",
                    f"type=volume,src={VOLUME},dst=/var/lib/buildkit",
                    "--mount",
                    f"type=bind,src={self.root}/buildkitd.toml,dst=/etc/buildkit/buildkitd.toml,readonly",
                    IMAGE,
                    "--config",
                    "/etc/buildkit/buildkitd.toml",
                    timeout=180,
                ).strip()
                if not re.fullmatch("[a-f0-9]{64}", identity):
                    raise ResourceError("builder_created_identity_invalid")
                journal.update(phase="container_created", containerId=identity)
                write_json(archive / "journal.json", journal)
            identity = journal["containerId"]
            if self.binding() != preview["binding"]:
                raise ResourceError("builder_recovery_binding_changed")
            self.verify(identity)
            # Start only our newly created ID, test BuildKit, then stop that ID.
            self.call("start", identity)
            journal["phase"] = "started"
            write_json(archive / "journal.json", journal)
            self.call("buildx", "inspect", BUILDER, "--bootstrap", timeout=90)
            self.active_build()
            self.verify(identity)
            self.call("stop", "--time", "15", identity, timeout=45)
            raw, projection = self.verify(identity)
            if raw["State"]["Running"]:
                raise ResourceError("builder_stop_unverified")
            pending = self.root / "builder.pending"
            if pending.is_symlink():
                raise ResourceError("builder_record_alias")
            pending.write_text(projection + "\n")
            pending.chmod(0o600)
            pending.replace(self.root / "builder.id")
            journal["phase"] = "complete"
            write_json(archive / "journal.json", journal)
            log.info("builder_reconcile status=complete")
            return {"status": "restored_stopped", "fingerprint": fingerprint}
        except (ResourceError, OSError, ValueError):
            log.error("builder_reconcile status=recovery_required")
            # Never claim rollback or remove cache resources after a failure.
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", metavar="PREVIEW_FINGERPRINT")
    parser.add_argument("--recover", metavar="PREVIEW_FINGERPRINT")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.recover:
        parser.error("choose_apply_or_recover")
    root = Path(os.environ.get("RWB_DOCKER_HOME", str(Path.home() / ".local/share/rwb-docker")))
    try:
        with operation_lock(root):
            logs = root / "logs"
            if logs.is_symlink():
                raise ResourceError("builder_logs_alias")
            logs.mkdir(mode=0o700, exist_ok=True)
            logfile = logs / "builder-reconcile.log"
            if logfile.is_symlink():
                raise ResourceError("builder_logs_alias")
            logging.basicConfig(filename=logfile, level=logging.INFO)
            manager = BuilderReconcile(root, Path(__file__).resolve().parent.parent)
            result = (
                manager.apply(args.apply or args.recover, bool(args.recover))
                if args.apply or args.recover
                else manager.preview()
            )
            print(json.dumps(result, sort_keys=True))
        return 0
    except (ResourceError, OSError, ValueError, KeyError, TypeError) as exc:
        code = str(exc) if isinstance(exc, ResourceError) else "builder_reconcile_failed"
        log.error("builder_reconcile code=%s", code)
        print(json.dumps({"status": "blocked", "error": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
