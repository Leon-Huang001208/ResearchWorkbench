"""AI news owned PostgreSQL, isolated from the Hot database and volume."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from .ai_news_transport import AiNewsError
from .docker_resources import ResourceError
from .hot import HotError
from .hot_postgres import IMAGE, ManagedPostgres
from .iteration_cache import operation_lock

log = logging.getLogger(__name__)
LABEL = "rwb.ai-news.instance"


class AiNewsPostgres(ManagedPostgres):
    """Reuse the existing bounded Docker driver and pinned PostgreSQL image."""

    def __init__(self, home: Path, instance: str, database_name: str = "rwb_ai_news"):
        super().__init__(home, instance)
        if database_name not in {"rwb_ai_news", "rwb_ai_news_test"}:
            raise AiNewsError("ai_news_database_name_invalid")
        self.database_name = database_name
        self.name = "rwb-ai-news-db-" + instance.replace("-", "")[:16]
        self.volume = self.name + "-data"

    def _labels(self):
        labels = {
            LABEL: self.instance,
            "io.research-workbench.project": "research-workbench",
            "io.research-workbench.purpose": "ai-news-database",
            "io.research-workbench.lifetime": (
                "temporary" if self.database_name.endswith("_test") else "persistent"
            ),
        }
        task = os.environ.get("RWB_DELIVERY_TASK_ID")
        if self.database_name.endswith("_test") and not task:
            raise AiNewsError("ai_news_delivery_task_required")
        if task:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", task):
                raise AiNewsError("ai_news_delivery_task_invalid")
            labels["io.research-workbench.delivery-task"] = task
        return [part for key, value in labels.items() for part in ("--label", key + "=" + value)]

    def call(self, args, timeout=30):
        try:
            return self._docker(args, timeout)
        except HotError:
            log.warning("ai_news_postgres_operation_failed")
            raise AiNewsError("ai_news_postgres_unavailable") from None

    def inspect(self):
        rows = json.loads(self.call(["inspect", self.name]))
        if not isinstance(rows, list) or len(rows) != 1:
            raise AiNewsError("ai_news_postgres_identity_invalid")
        row = rows[0]
        labels = row.get("Config", {}).get("Labels", {}) or {}
        mounts = row.get("Mounts", [])
        binding = row.get("HostConfig", {}).get("PortBindings", {})
        secret = str(self.home / "ai-news" / "secrets" / "database")
        if (
            row.get("Config", {}).get("Image") != IMAGE
            or labels.get(LABEL) != self.instance
            or not re.fullmatch(r"[0-9a-f]{64}", row.get("Id", ""))
            or not any(
                m.get("Type") == "volume"
                and m.get("Name") == self.volume
                and m.get("Destination") == "/var/lib/postgresql/data"
                for m in mounts
            )
            or not any(
                m.get("Type") == "bind"
                and m.get("Source") == secret
                and m.get("Destination") == "/run/rwb-ai-news-password"
                and m.get("RW") is False
                for m in mounts
            )
            or set(binding) != {"5432/tcp"}
            or len(binding["5432/tcp"]) != 1
            or binding["5432/tcp"][0].get("HostIp") != "127.0.0.1"
            or row.get("HostConfig", {}).get("NetworkMode") == "host"
            or "POSTGRES_DB=" + self.database_name not in row.get("Config", {}).get("Env", [])
        ):
            raise AiNewsError("ai_news_postgres_foreign")
        volume = json.loads(self.call(["volume", "inspect", self.volume]))[0]
        if (volume.get("Labels") or {}).get(LABEL) != self.instance:
            raise AiNewsError("ai_news_postgres_foreign_volume")
        return row

    def start(self, password=None):
        root = Path(os.environ.get("RWB_DOCKER_HOME", str(Path.home() / ".local/share/rwb-docker")))
        try:
            with operation_lock(root):
                return self._start()
        except ResourceError:
            log.warning("ai_news_docker_operation_denied")
            raise AiNewsError("ai_news_docker_operation_denied") from None

    def _start(self):
        # Never pull an image, adopt an existing volume or use a business database.
        self.call(["image", "inspect", IMAGE])
        available = int(self.call(["info", "--format", "{{.MemTotal}} "]))
        running = self.call(["ps", "-q"]).splitlines()
        committed = 0
        for identity in running:
            row = json.loads(self.call(["inspect", identity]))[0]
            if row.get("Name") == "/" + self.name:
                continue
            memory = row.get("HostConfig", {}).get("Memory", 0)
            if type(memory) is not int or memory <= 0:
                raise AiNewsError("ai_news_resource_admission_unknown")
            committed += memory
        log.info(
            "ai_news_resource_admission total_bytes=%s committed_bytes=%s requested_bytes=%s reserve_bytes=%s running_count=%s",
            available,
            committed,
            768 * 1024**2,
            1024**3,
            len(running),
        )
        available -= committed
        if available < 2 * 1024**3:
            raise AiNewsError("ai_news_resource_admission_denied")
        volumes = self.call(["volume", "ls", "--format", "{{.Name}}"]).splitlines()
        names = self.call(["ps", "-a", "--format", "{{.Names}}"]).splitlines()
        if self.volume not in volumes:
            self.call(
                [
                    "volume",
                    "create",
                    *self._labels(),
                    self.volume,
                ]
            )
        volume = json.loads(self.call(["volume", "inspect", self.volume]))[0]
        if (volume.get("Labels") or {}).get(LABEL) != self.instance:
            raise AiNewsError("ai_news_postgres_foreign_volume")
        if self.name not in names:
            self.call(
                [
                    "create",
                    "--name",
                    self.name,
                    *self._labels(),
                    "--memory",
                    "768m",
                    "--cpus",
                    "1",
                    "--pids-limit",
                    "128",
                    "--env",
                    "POSTGRES_PASSWORD_FILE=/run/rwb-ai-news-password",
                    "--env",
                    "POSTGRES_DB=" + self.database_name,
                    "--mount",
                    "type=bind,source="
                    + str(self.home / "ai-news/secrets/database")
                    + ",target=/run/rwb-ai-news-password,readonly",
                    "--mount",
                    "type=volume,source=" + self.volume + ",target=/var/lib/postgresql/data",
                    "-p",
                    "127.0.0.1::5432",
                    IMAGE,
                ]
            )
        row = self.inspect()
        if not row["State"]["Running"]:
            self.call(["start", row["Id"]])
            row = self.inspect()
        ports = row["NetworkSettings"]["Ports"]["5432/tcp"]
        if len(ports) != 1 or ports[0]["HostIp"] != "127.0.0.1":
            raise AiNewsError("ai_news_postgres_public_binding")
        deadline = time.monotonic() + 30
        while True:
            try:
                self.call(
                    ["exec", row["Id"], "pg_isready", "-U", "postgres", "-d", self.database_name], 3
                )
                break
            except AiNewsError:
                if time.monotonic() >= deadline:
                    raise AiNewsError("ai_news_postgres_not_ready") from None
                time.sleep(0.2)
        log.info("ai_news_postgres_started")
        return {
            "host": "127.0.0.1",
            "port": int(ports[0]["HostPort"]),
            "name": self.database_name,
            "user": "postgres",
        }

    def stop(self):
        row = self.inspect()
        if row["State"]["Running"]:
            self.call(["stop", "--time", "15", row["Id"]])
        log.info("ai_news_postgres_stopped")
