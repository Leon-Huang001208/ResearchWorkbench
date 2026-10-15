"""Aggregate, lease-aware BuildKit GC; never unlink cache storage or stop services."""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path

from .docker_resources import DockerResources, ResourceError

GIB = 1024**3
log = logging.getLogger(__name__)


def size_bytes(value):
    """Round human Buildx measurements upward rather than certify an underestimate."""
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(B|kB|MB|GB|TB)", value)
    if not match:
        raise ResourceError("cache_measurement_invalid")
    from decimal import Decimal, ROUND_CEILING

    multiplier = {"B": 1, "kB": 1000, "MB": 10**6, "GB": 10**9, "TB": 10**12}[match[2]]
    quantum = Decimal(10) ** -len(match[1].partition(".")[2])
    return int(((Decimal(match[1]) + quantum) * multiplier).to_integral_value(rounding=ROUND_CEILING))


def cache_budget(driver, builders, budget):
    if not builders or len(set(builders)) != len(builders) or budget != 20 * GIB:
        raise ResourceError("aggregate_cache_policy_invalid")
    before = {name: driver.cache_usage(name) for name in builders}
    total = sum(row["bytes"] for row in before.values())
    report = {"budgetBytes": budget, "beforeBytes": total, "items": []}
    # BuildKit itself selects LRU records and refuses in-use refs. Oldest builder first.
    for name in sorted(builders, key=lambda key: before[key]["oldestSeconds"], reverse=True):
        current = {key: driver.cache_usage(key) for key in builders}
        total = sum(row["bytes"] for row in current.values())
        if total <= budget:
            break
        target = max(0, current[name]["bytes"] - (total - budget) - 64 * 1024**2)
        driver.cache_prune(name, target)
        report["items"].append({"builder": name, "targetBytes": target})
    after = {name: driver.cache_usage(name) for name in builders}
    report.update(afterBytes=sum(row["bytes"] for row in after.values()), builders=after)
    report["ok"] = report["afterBytes"] <= budget
    report["status"] = "complete" if report["ok"] else "blocked"
    log.info("iteration_cache status=%s", report["status"])
    return report


@contextmanager
def operation_lock(root):
    """Use the same fail-closed directory lock as rwb-docker (no stale lock deletion)."""
    root = Path(root)
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ResourceError("docker_manager_root_invalid")
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ResourceError("docker_manager_root_not_private")
    lock = root / "operation.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise ResourceError("docker_operation_busy") from None
    identity = lock.stat()
    try:
        yield
    finally:
        now = lock.lstat()
        if (now.st_dev, now.st_ino) != (identity.st_dev, identity.st_ino):
            raise ResourceError("docker_operation_lock_changed")
        lock.rmdir()


class ManagedCaches(DockerResources):
    """Only the explicitly approved Desktop cache and registered RWB builder."""

    names = ("desktop-linux", "rwb-dev-builder")

    def __init__(self, home):
        self.home = Path(home)
        self.bindings = {}

    def builder_binding(self, builder):
        text = self.call("buildx", "inspect", builder)
        names = re.findall(r"^Name:\s+(\S+)\s*$", text, re.MULTILINE)
        drivers = re.findall(r"^Driver:\s+(\S+)\s*$", text, re.MULTILINE)
        endpoints = re.findall(r"^Endpoint:\s+(\S+)\s*$", text, re.MULTILINE)
        expected_names = ["rwb-dev-builder", "rwb-dev-builder0"] if builder == "rwb-dev-builder" else ["desktop-linux", "desktop-linux"]
        expected_driver = "docker-container" if builder == "rwb-dev-builder" else "docker"
        endpoint = json.loads(self.call("context", "inspect", "desktop-linux", "--format", "{{json .Endpoints.docker.Host}}"))
        if names != expected_names or drivers != [expected_driver] or endpoints != ["desktop-linux"] or endpoint != "unix://" + str(Path.home() / ".docker/run/docker.sock"):
            raise ResourceError("cache_builder_binding_changed")
        binding = (tuple(names), tuple(drivers), tuple(endpoints), endpoint)
        if builder in self.bindings and self.bindings[builder] != binding:
            raise ResourceError("cache_builder_binding_changed")
        self.bindings[builder] = binding
        return binding

    def inspect(self, name):
        return json.loads(self.call("inspect", name))[0]

    def cache_usage(self, builder):
        if builder not in self.names:
            raise ResourceError("cache_builder_not_managed")
        self.builder_binding(builder)
        values = self.call("buildx", "du", "--builder", builder, "--format=json", timeout=120)
        rows = [json.loads(line) for line in values.splitlines()]
        ages = []
        for row in rows:
            match = re.search(r"(\d+) (second|minute|hour|day|week|month)", row["LastUsedAt"] or "")
            ages.append(int(match[1]) * {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000}[match[2]] if match else 0)
        return {"bytes": sum(size_bytes(row["Size"]) for row in rows), "oldestSeconds": max(ages, default=0), "inUse": sum(not row["Reclaimable"] for row in rows), "records": len(rows)}

    def cache_prune(self, builder, target):
        if builder not in self.names or target < 0:
            raise ResourceError("cache_builder_not_managed")
        self.builder_binding(builder)
        self.call("buildx", "prune", "--builder", builder, "--all", "--force", "--max-used-space", str(target), "--reserved-space", "0", timeout=900)

    @contextmanager
    def maintenance(self):
        with operation_lock(self.home):
            context = self.call("context", "show").strip()
            if context != "desktop-linux":
                raise ResourceError("docker_context_changed")
            for builder in self.names:
                self.builder_binding(builder)
            name = "buildx_buildkit_rwb-dev-builder0"
            original = self.inspect(name)
            projection = self.call("inspect", "--format", '{{.Id}} {{.Config.Image}} {{.HostConfig.Memory}} {{.HostConfig.MemorySwap}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuPeriod}} {{.HostConfig.PidsLimit}} {{.HostConfig.LogConfig.Type}} {{index .HostConfig.LogConfig.Config "max-size"}} {{index .HostConfig.LogConfig.Config "max-file"}} {{index .Config.Labels "io.research-workbench.manager"}}', name).strip()
            record = self.home / "builder.id"
            if record.is_symlink() or projection != record.read_text().strip():
                raise ResourceError("cache_builder_identity_changed")
            mounts = [row for row in original["Mounts"] if row["Type"] == "volume"]
            if len(mounts) != 1 or mounts[0]["Name"] != "rwb-dev-builder-state":
                raise ResourceError("cache_volume_identity_changed")
            labels = json.loads(self.call("volume", "inspect", "--format", "{{json .Labels}}", mounts[0]["Name"]))
            if labels.get("io.research-workbench.manager") != str(self.home):
                raise ResourceError("cache_volume_not_owned")
            if original["State"]["Running"]:
                raise ResourceError("cache_builder_active")
            # GC needs less memory than compilation. Temporarily reserve2GiB, restore
            # the exact stopped builder's old limits; never stop another service.
            running = self.call("ps", "-q").splitlines()
            reservations = 0
            for identity in running:
                memory = self.inspect(identity)["HostConfig"]["Memory"]
                if not memory:
                    raise ResourceError("cache_unbounded_running_service")
                reservations += memory
            available = int(self.call("info", "--format", "{{.MemTotal}}"))
            if reservations + 2 * GIB + GIB > available:
                raise ResourceError("cache_maintenance_memory_gate")
            old = original["HostConfig"]
            started = False
            try:
                self.call("update", "--memory", str(2 * GIB), "--memory-swap", str(2 * GIB), original["Id"])
                self.call("start", original["Id"])
                started = True
                # Wait for BuildKit readiness without starting a build or changing config.
                self.call("buildx", "inspect", "rwb-dev-builder", "--bootstrap", timeout=90)
                yield
            finally:
                now = self.inspect(name)
                if now["Id"] != original["Id"] or now["Image"] != original["Image"] or now["Mounts"] != original["Mounts"]:
                    raise ResourceError("cache_builder_changed_during_maintenance")
                if started and self.cache_usage("rwb-dev-builder")["inUse"]:
                    raise ResourceError("cache_builder_in_use_restore_blocked")
                if now["State"]["Running"]:
                    self.call("stop", "--time", "15", original["Id"], timeout=45)
                self.call("update", "--memory", str(old["Memory"]), "--memory-swap", str(old["MemorySwap"]), original["Id"])
                restored = self.inspect(name)
                if restored["State"]["Running"] or any(restored["HostConfig"][key] != old[key] for key in ("Memory", "MemorySwap")):
                    raise ResourceError("cache_builder_restore_unverified")
