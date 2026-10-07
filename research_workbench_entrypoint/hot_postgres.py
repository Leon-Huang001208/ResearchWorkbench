"""Owned project PostgreSQL container; stop/rebuild never deletes its data volume."""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import time
from pathlib import Path

from .hot import HotError, _no_alias

log = logging.getLogger(__name__)
IMAGE = "postgres@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826"


class ManagedPostgres:
    def __init__(self, home: Path, instance: str):
        if len(instance) != 36 or any(value not in "0123456789abcdef-" for value in instance):
            raise HotError("hot_instance_invalid")
        self.home = home
        self.instance = instance
        self.name = "rwb-hot-db-" + instance.replace("-", "")[:16]
        self.volume = self.name + "-data"

    def _docker(self, args: list[str], timeout: int = 30) -> str:
        try:
            value = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
            if value.returncode or len(value.stdout.encode()) > 65536:
                raise HotError("hot_postgres_control_failed")
            return value.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise HotError("hot_postgres_unavailable") from None

    def start(self, password: str) -> dict:
        if not password or len(password) > 4096:
            raise HotError("hot_postgres_secret_missing")
        secret = self.home / "hot" / "pg-secret-export" / "password"
        _no_alias(secret)
        secret.parent.mkdir(mode=0o700, exist_ok=True)
        directory = secret.parent.stat()
        if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) != 0o700:
            raise HotError("hot_postgres_secret_unsafe")
        # This is an explicitly controlled container input export, never the credential authority.
        descriptor = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise HotError("hot_postgres_secret_unsafe")
            stream.truncate(0)
            stream.write(password)
            stream.flush()
            os.fsync(stream.fileno())
        volumes = self._docker(["volume", "ls", "--format", "{{.Name}}"] ).splitlines()
        if self.volume not in volumes:
            self._docker(["volume", "create", "--label", "rwb.hot.instance=" + self.instance, self.volume])
        volume = json.loads(self._docker(["volume", "inspect", self.volume]))[0]
        if volume.get("Labels", {}).get("rwb.hot.instance") != self.instance:
            raise HotError("hot_postgres_foreign_volume")
        names = self._docker(["ps", "-a", "--format", "{{.Names}}"] ).splitlines()
        if self.name not in names:
            try:
                self._docker(["image", "inspect", IMAGE])
            except HotError:
                self._docker(["pull", IMAGE], timeout=180)
            self._docker(["run", "-d", "--name", self.name, "--label", "rwb.hot.instance=" + self.instance,
                          "--env", "POSTGRES_PASSWORD_FILE=/run/rwb-pg-password", "--env", "POSTGRES_DB=rwb_hot",
                          "--mount", "type=bind,source=" + str(secret) + ",target=/run/rwb-pg-password,readonly",
                          "-v", self.volume + ":/var/lib/postgresql/data", "-p", "127.0.0.1::5432", IMAGE])
        state = json.loads(self._docker(["inspect", self.name]))[0]
        if state.get("Config", {}).get("Image") != IMAGE or state.get("Config", {}).get("Labels", {}).get("rwb.hot.instance") != self.instance:
            raise HotError("hot_postgres_foreign_container")
        mounts = state.get("Mounts", [])
        if not any(row.get("Type") == "volume" and row.get("Name") == self.volume and row.get("Destination") == "/var/lib/postgresql/data" for row in mounts):
            raise HotError("hot_postgres_foreign_volume")
        if not any(row.get("Type") == "bind" and row.get("Source") == str(secret) and row.get("Destination") == "/run/rwb-pg-password" and row.get("RW") is False for row in mounts):
            raise HotError("hot_postgres_secret_binding_invalid")
        bindings = state.get("HostConfig", {}).get("PortBindings", {})
        declared = bindings.get("5432/tcp", [])
        if set(bindings) != {"5432/tcp"} or len(declared) != 1 or declared[0].get("HostIp") != "127.0.0.1" or state.get("HostConfig", {}).get("NetworkMode") == "host":
            raise HotError("hot_postgres_public_binding")
        if not state["State"]["Running"]:
            self._docker(["start", self.name])
            state = json.loads(self._docker(["inspect", self.name]))[0]
        ports = state["NetworkSettings"]["Ports"]["5432/tcp"]
        if len(ports) != 1 or ports[0]["HostIp"] != "127.0.0.1":
            raise HotError("hot_postgres_public_binding")
        deadline = time.monotonic() + 30
        while True:
            try:
                self._docker(["exec", self.name, "pg_isready", "-h", "127.0.0.1", "-p", "5432", "-U", "postgres", "-d", "rwb_hot"], timeout=3)
                break
            except HotError:
                if time.monotonic() >= deadline:
                    raise HotError("hot_postgres_not_ready") from None
                time.sleep(0.2)
        log.info("hot_postgres_started")
        return {"host": "127.0.0.1", "port": int(ports[0]["HostPort"]), "name": "rwb_hot", "container": self.name, "volume": self.volume}
