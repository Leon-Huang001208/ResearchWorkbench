"""Administrator-only Docker instance ledger; business containers have no socket.

The outer shell holds one machine ledger lock across admission and mutations.
Never import application state, model credentials, or legacy Native identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

GIB = 1024**3
MEMORY = {"dev": 3 * GIB, "stage": 2 * GIB, "prod": 2 * GIB}
POOL = {"dev": 3 * GIB, "stage": 2 * GIB, "prod": 6 * GIB - 256 * 1024**2}
PREFIX = "io.research-workbench."
LOG = logging.getLogger("rwb.docker.manager")


class Refusal(RuntimeError):
    """Stable, non-secret administrative failure code."""


def command(*args: str, timeout: int = 60) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        # Daemon errors may contain private paths; retain only command category.
        LOG.error("command_failed category=%s exit=%s", args[0], result.returncode)
        raise Refusal("docker_command_failed")
    return result.stdout.strip()


def inspect(kind: str, name: str) -> dict:
    return json.loads(command("docker", kind, "inspect", name))[0]


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".pending")
    if path.is_symlink() or temporary.is_symlink():
        raise Refusal("ledger_alias")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
    temporary.chmod(0o600)
    temporary.replace(path)


def validate_name(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value):
        raise argparse.ArgumentTypeError("instance_name_invalid")
    return value


def identity_projection(container: dict) -> dict:
    """Exclude changing process/health facts; include all authority-bearing config."""
    projection = {key: container[key] for key in ("Id", "Image", "Config", "HostConfig", "Mounts")}
    if isinstance(projection["HostConfig"], dict):
        host = dict(projection["HostConfig"])
        # Docker materializes the enabled OOM killer's unset default at start.
        # Null and false have identical policy; true remains a mismatch.
        if host.get("OomKillDisable") is None:
            host["OomKillDisable"] = False
        projection["HostConfig"] = host
    return projection


class Manager:
    def __init__(self, ledger: Path, host_root: str, worktree: str):
        self.ledger, self.host_root, self.worktree = ledger, host_root, worktree
        self.owner = hashlib.sha256(host_root.encode()).hexdigest()[:16]

    def labels(self, environment: str, instance: str) -> dict:
        return {
            PREFIX + "manager": self.owner,
            PREFIX + "environment": environment,
            PREFIX + "instance": instance,
        }

    def path(self, environment: str, instance: str) -> Path:
        return self.ledger / f"{environment}-{instance}.json"

    def read(self, environment: str, instance: str) -> dict:
        path = self.path(environment, instance)
        if path.is_symlink():
            raise Refusal("ledger_alias")
        record = json.loads(path.read_text())
        if record["labels"] != self.labels(environment, instance):
            raise Refusal("ledger_ownership_mismatch")
        return record

    def admission(self, environment: str, memory: int) -> None:
        reservations = [
            json.loads(path.read_text()) for path in self.ledger.glob(f"{environment}-*.json")
        ]
        reserved = sum(record["memory"] for record in reservations if not record.get("retired"))
        if reserved + memory > POOL[environment]:
            raise Refusal("environment_pool_exceeded")
        # Reject managed containers absent from this ledger (including alternate homes).
        identifiers = command(
            "docker", "ps", "-aq", "--filter", f"label={PREFIX}environment={environment}"
        ).splitlines()
        known = {
            json.loads(path.read_text()).get("container_id")
            for path in self.ledger.glob(f"{environment}-*.json")
        }
        for identifier in identifiers:
            if inspect("container", identifier)["Id"] not in known:
                raise Refusal("unregistered_environment_container")

    def verify_resources(self, record: dict) -> None:
        for volume in record["volumes"].values():
            if inspect("volume", volume).get("Labels") != record["labels"]:
                raise Refusal("volume_ownership_mismatch")
        if inspect("network", record["network"]).get("Labels") != record["labels"]:
            raise Refusal("network_ownership_mismatch")

    def owned(self, record: dict) -> dict:
        self.verify_resources(record)
        container = inspect("container", record["container_id"])
        if identity_projection(container) != identity_projection(record["projection"]):
            raise Refusal("container_ownership_mismatch")
        if container["Name"] != "/" + record["name"]:
            raise Refusal("container_name_mismatch")
        if set(container["NetworkSettings"]["Networks"]) != {record["network"]}:
            raise Refusal("container_network_mismatch")
        mounts = {mount["Destination"]: mount for mount in container["Mounts"]}
        for key, target in {
            "data": "/data/research-web",
            "logs": "/state/logs",
            "credentials": "/run/rwb-secrets",
            "cache": "/cache",
        }.items():
            if mounts.get(target, {}).get("Name") != record["volumes"][key]:
                raise Refusal("container_mounts_mismatch")
        if any("docker.sock" in str(mount) for mount in container["Mounts"]):
            raise Refusal("business_socket_forbidden")
        host = container["HostConfig"]
        if (host["Memory"], host["MemorySwap"], host["NanoCpus"], host["PidsLimit"]) != (
            record["memory"],
            record["memory"],
            2_000_000_000,
            256,
        ) or not host["ReadonlyRootfs"]:
            raise Refusal("container_limits_mismatch")
        return container

    def register(self, arguments: argparse.Namespace) -> dict:
        environment, instance = arguments.environment, arguments.instance
        path = self.path(environment, instance)
        if path.exists():
            record = self.read(environment, instance)
            if (
                (arguments.image and arguments.image != record["image"])
                or (arguments.port and arguments.port != record["port"])
                or (environment == "dev" and record["worktree"] != self.worktree)
            ):
                raise Refusal("instance_registration_mismatch")
            self.verify_resources(record)
            if record["container_id"]:
                self.owned(record)
            if record.get("retired"):
                self.admission(environment, record["memory"])
                record["retired"] = False
                atomic_json(path, record)
            return record
        memory = MEMORY[environment]
        self.admission(environment, memory)
        image = arguments.image
        if not image:
            image = (
                (self.ledger / ("dev.image" if environment == "dev" else "runtime.image"))
                .read_text()
                .strip()
            )
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise Refusal("immutable_image_id_required")
        image_info = inspect("image", image)
        if image_info["Architecture"] != "arm64" or image_info["Os"] != "linux":
            raise Refusal("image_platform_mismatch")
        if (
            environment != "dev"
            and image_info["Config"].get("Labels", {}).get(PREFIX + "runtime") != "docker"
        ):
            raise Refusal("runtime_image_required")
        if (image_info["Config"].get("Labels", {}).get(PREFIX + "role") == "development") != (
            environment == "dev"
        ):
            raise Refusal("image_role_mismatch")
        labels = self.labels(environment, instance)
        name = f"rwb-{environment}-{instance}-{self.owner[:8]}"
        label_args = [
            part for key, value in labels.items() for part in ("--label", f"{key}={value}")
        ]
        # Preflight the entire namespace before creating anything. No existing adoption.
        if command("docker", "ps", "-aq", "--filter", f"name=^/{name}$"):
            raise Refusal("container_unregistered")
        volumes = {key: name + "-" + key for key in ("data", "logs", "credentials", "cache")}
        existing_volumes = command("docker", "volume", "ls", "--format", "{{.Name}}").splitlines()
        existing_networks = command("docker", "network", "ls", "--format", "{{.Name}}").splitlines()
        if (
            any(volume in existing_volumes for volume in volumes.values())
            or name in existing_networks
        ):
            raise Refusal("resource_unregistered")
        if environment != "dev" and not arguments.port:
            raise Refusal("explicit_port_required")
        for volume in volumes.values():
            command("docker", "volume", "create", *label_args, volume)
        command("docker", "network", "create", *label_args, name)
        # A fixed, bounded root initializer only for new owned volumes; no socket/source.
        mounts = [
            part
            for volume in volumes.values()
            for part in ("--mount", f"type=volume,src={volume},dst=/init/{volume}")
        ]
        command(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "0:0",
            "--memory",
            "128m",
            "--memory-swap",
            "128m",
            "--cpus",
            ".5",
            "--pids-limit",
            "32",
            "--log-opt",
            "max-size=10m",
            "--log-opt",
            "max-file=3",
            *mounts,
            "--entrypoint",
            "/bin/sh",
            image,
            "-c",
            "chown 10001:10001 /init/* && chmod 700 /init/*",
        )
        source = command(
            "git", "-c", f"safe.directory={self.worktree}", "-C", self.worktree, "rev-parse", "HEAD"
        )
        record = {
            "schema_version": 1,
            "environment": environment,
            "instance": instance,
            "labels": labels,
            "name": name,
            "image": image,
            "memory": memory,
            "network": name,
            "volumes": volumes,
            "port": arguments.port,
            "worktree": self.worktree if environment == "dev" else None,
            "source_sha": image_info["Config"]
            .get("Labels", {})
            .get("org.opencontainers.image.revision"),
            "registration_source_sha": source,
            "dsh_commit": json.loads(
                (Path(self.worktree) / "runtimes/research_web.json").read_text()
            )["dsh"]["commit"],
            "container_id": None,
            "projection": None,
        }
        atomic_json(path, record)
        return record

    def create(self, record: dict) -> None:
        self.verify_resources(record)
        if command("docker", "ps", "-aq", "--filter", f"name=^/{record['name']}$"):
            raise Refusal("container_unregistered")
        args = [
            "docker",
            "create",
            "--name",
            record["name"],
            "--user",
            "10001:10001",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            str(record["memory"]),
            "--memory-swap",
            str(record["memory"]),
            "--cpus",
            "2",
            "--pids-limit",
            "256",
            "--network",
            record["network"],
            "--oom-kill-disable=false",
            "--stop-timeout",
            "35",
            "--log-driver",
            "json-file",
            "--log-opt",
            "max-size=10m",
            "--log-opt",
            "max-file=3",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,mode=1777,size=256m,"
            + ("exec" if record["environment"] == "dev" else "noexec"),
            "--tmpfs",
            "/home/rwb:rw,nosuid,nodev,uid=10001,gid=10001,mode=700,size=128m",
            "--tmpfs",
            "/state:rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=700,size=1m",
        ]
        for key, target in {
            "data": "/data/research-web",
            "logs": "/state/logs",
            "credentials": "/run/rwb-secrets",
            "cache": "/cache",
        }.items():
            args += ["--mount", f"type=volume,src={record['volumes'][key]},dst={target}"]
        for key, value in record["labels"].items():
            args += ["--label", f"{key}={value}"]
        args += ["--env", "PIP_CACHE_DIR=/cache/pip", "--env", "XDG_CACHE_HOME=/cache"]
        if record["environment"] != "prod":
            args += ["--env", "RESEARCH_AUTOMATIONS_ENABLED=0"]
        if record["environment"] == "dev":
            args += ["--init"]
            args += ["--mount", f"type=bind,src={record['worktree']},dst=/workspace"]
            args += [
                "--env",
                "GIT_CONFIG_COUNT=1",
                "--env",
                "GIT_CONFIG_KEY_0=safe.directory",
                "--env",
                "GIT_CONFIG_VALUE_0=/workspace",
            ]
            # Git worktree .git is a pointer to the common directory at an absolute path.
            common = command(
                "git",
                "-c",
                f"safe.directory={self.worktree}",
                "-C",
                self.worktree,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            )
            args += ["--mount", f"type=bind,src={common},dst={common}"]
        else:
            args += ["--publish", f"127.0.0.1:{record['port']}:8088"]
        args += [record["image"]]
        identifier = command(*args)
        record["container_id"] = identifier
        record["projection"] = identity_projection(inspect("container", identifier))
        atomic_json(self.path(record["environment"], record["instance"]), record)

    def up(self, record: dict) -> dict:
        if record.get("retired"):
            raise Refusal("instance_retired_register_first")
        if record["environment"] == "stage" and command(
            "docker", "ps", "-q", "--filter", "name=^/buildx_buildkit_rwb-dev-builder0$"
        ):
            raise Refusal("cold_build_active_stop_builder_first")
        if not record["container_id"]:
            self.create(record)
        container = self.owned(record)
        if not container["State"]["Running"]:
            used = 0
            for identifier in command("docker", "ps", "-q").splitlines():
                limit = inspect("container", identifier)["HostConfig"]["Memory"]
                if limit <= 0:
                    raise Refusal("unbounded_running_container")
                used += limit
            vm_memory = int(command("docker", "info", "--format", "{{.MemTotal}}"))
            if used + record["memory"] + 2 * GIB > vm_memory:
                raise Refusal("vm_memory_budget_exceeded")
            command("docker", "start", record["container_id"])
        if record["environment"] != "dev":
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state = self.owned(record)["State"]
                if state.get("Health", {}).get("Status") == "healthy":
                    return self.status(record)
                if not state["Running"]:
                    raise Refusal("candidate_exited")
                time.sleep(2)
            raise Refusal("candidate_health_timeout")
        return self.status(record)

    def status(self, record: dict) -> dict:
        self.verify_resources(record)
        container = self.owned(record) if record["container_id"] else None
        return {
            key: record[key]
            for key in (
                "environment",
                "instance",
                "image",
                "source_sha",
                "dsh_commit",
                "worktree",
                "volumes",
                "network",
                "port",
                "memory",
            )
        } | {
            "data_root": {"volume": record["volumes"]["data"], "guest_path": "/data/research-web"},
            "container_id": record["container_id"],
            "state": (
                container["State"]["Status"]
                if container
                else ("retired" if record.get("retired") else "registered")
            ),
            "health": container["State"].get("Health", {}).get("Status") if container else None,
            "docker_socket": False,
            "runtime_limits": (
                {
                    key: container["HostConfig"][key]
                    for key in (
                        "Memory",
                        "MemorySwap",
                        "NanoCpus",
                        "PidsLimit",
                        "ReadonlyRootfs",
                        "LogConfig",
                        "Tmpfs",
                    )
                }
                if container
                else None
            ),
        }

    def stop(self, record: dict) -> None:
        if not record["container_id"]:
            self.verify_resources(record)
            if command("docker", "ps", "-aq", "--filter", f"name=^/{record['name']}$"):
                raise Refusal("container_unregistered")
            return
        container = self.owned(record)
        if container["State"]["Running"]:
            command("docker", "stop", record["container_id"], timeout=60)
        if self.owned(record)["State"]["Running"]:
            raise Refusal("container_stop_unverified")

    def cleanup(self, record: dict) -> None:
        if record["environment"] != "dev":
            raise Refusal("only_dev_cleanup_allowed")
        self.verify_resources(record)
        if record["container_id"]:
            if self.owned(record)["State"]["Running"]:
                raise Refusal("stop_dev_before_cleanup")
            self.owned(record)
            command("docker", "rm", record["container_id"])
        else:
            self.stop(record)
        record.update(container_id=None, projection=None, retired=True)
        atomic_json(self.path(record["environment"], record["instance"]), record)

    def replace_stage_image(self, record: dict, image: str) -> None:
        """Explicit candidate refresh; production promotion remains a G2 contract."""
        if record["environment"] != "stage" or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise Refusal("only_stage_immutable_replace_allowed")
        replacement = inspect("image", image)
        labels = replacement["Config"].get("Labels", {})
        if (
            replacement["Architecture"] != "arm64"
            or replacement["Os"] != "linux"
            or labels.get(PREFIX + "runtime") != "docker"
            or labels.get(PREFIX + "role") == "development"
        ):
            raise Refusal("runtime_image_required")
        self.verify_resources(record)
        if record["container_id"]:
            if self.owned(record)["State"]["Running"]:
                raise Refusal("stop_stage_before_replace")
            self.owned(record)
            command("docker", "rm", record["container_id"])
        else:
            self.stop(record)
        record.update(
            previous_image=record["image"],
            image=replacement["Id"],
            source_sha=labels.get("org.opencontainers.image.revision"),
            container_id=None,
            projection=None,
        )
        atomic_json(self.path(record["environment"], record["instance"]), record)


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("environment", choices=MEMORY)
    parser.add_argument("instance", type=validate_name)
    parser.add_argument(
        "action",
        choices=(
            "register",
            "up",
            "status",
            "doctor",
            "stop",
            "rebuild",
            "exec",
            "cleanup",
            "replace-image",
        ),
    )
    parser.add_argument("--image")
    parser.add_argument("--port", type=int)
    arguments, extra = parser.parse_known_args()
    arguments.command = extra
    if extra and arguments.action != "exec":
        parser.error("unexpected_arguments")
    if arguments.port is not None and arguments.action != "register":
        parser.error("port_is_registration_only")
    if arguments.image and arguments.action not in {"register", "rebuild", "replace-image"}:
        parser.error("image_is_registration_or_dev_rebuild_only")
    if arguments.port is not None and not 1024 <= arguments.port <= 65535:
        parser.error("port_must_be_1024_to_65535")
    ledger = Path("/ledger")
    logging.basicConfig(
        filename=ledger / "logs/manager.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    manager = Manager(ledger, os.environ["RWB_MANAGER_ROOT"], os.environ["RWB_WORKTREE"])
    try:
        record = (
            manager.register(arguments)
            if arguments.action == "register"
            else manager.read(arguments.environment, arguments.instance)
        )
        LOG.info(
            "operation environment=%s instance=%s action=%s",
            arguments.environment,
            arguments.instance,
            arguments.action,
        )
        if arguments.action not in {"status", "doctor", "exec"}:
            print(
                json.dumps(
                    {
                        "action": arguments.action,
                        "target": {
                            "environment": record["environment"],
                            "instance": record["instance"],
                            "image": record["image"],
                            "data_volume": record["volumes"]["data"],
                            "guest_data_root": "/data/research-web",
                            "container_id": record["container_id"],
                        },
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
        if arguments.action == "up":
            output = manager.up(record)
        elif arguments.action == "rebuild":
            if arguments.environment != "dev":
                raise Refusal("only_dev_rebuild_allowed")
            replacement = None
            if arguments.image:
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", arguments.image):
                    raise Refusal("immutable_image_id_required")
                replacement = inspect("image", arguments.image)
                if (
                    replacement["Architecture"] != "arm64"
                    or replacement["Os"] != "linux"
                    or replacement["Config"].get("Labels", {}).get(PREFIX + "role") != "development"
                ):
                    raise Refusal("development_image_required")
            manager.stop(record)
            manager.owned(record)
            command("docker", "rm", record["container_id"])
            record.update(container_id=None, projection=None)
            if replacement:
                record["previous_image"] = record["image"]
                record["image"] = replacement["Id"]
                record["source_sha"] = (
                    replacement["Config"].get("Labels", {}).get("org.opencontainers.image.revision")
                )
            atomic_json(manager.path(arguments.environment, arguments.instance), record)
            output = manager.up(record)
        elif arguments.action == "stop":
            manager.stop(record)
            output = manager.status(record)
        elif arguments.action == "cleanup":
            manager.cleanup(record)
            output = manager.status(record)
        elif arguments.action == "replace-image":
            if not arguments.image:
                raise Refusal("explicit_image_required")
            manager.replace_stage_image(record, arguments.image)
            output = manager.status(record)
        elif arguments.action == "exec":
            if arguments.environment != "dev" or not arguments.command:
                raise Refusal("dev_command_required")
            manager.owned(record)
            cmd = arguments.command
            if cmd[0] == "--":
                cmd = cmd[1:]
            return subprocess.run(
                ["docker", "exec", "--workdir", "/workspace", record["container_id"], *cmd],
                check=False,
            ).returncode
        else:
            output = manager.status(record)
            if arguments.action == "doctor":
                output["capability_gaps"] = {
                    "model_credentials": "model_credential_backend_unavailable",
                    "linux_research_sandbox": "research_sandbox_unsupported",
                    "invited_user_authentication": "NOT_IMPLEMENTED_G4",
                    "public_ingress": "NOT_IMPLEMENTED_G5",
                    "vendor_calls": "NOT_RUN",
                }
        print(json.dumps(output, sort_keys=True))
        return 0
    except (Refusal, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        code = str(error) if isinstance(error, Refusal) else "manager_state_or_command_failed"
        LOG.error("operation_refused code=%s", code)
        print(json.dumps({"ok": False, "issue": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
