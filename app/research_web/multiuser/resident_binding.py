"""Read-only attachment of exactly one administrator to the original resident."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from core.observability import get_logger

from .accounts import AccountError, AccountStore
from .runtime import Backend, RuntimeErrorSafe

log = get_logger(__name__)


def read_json(path: Path) -> dict:
    """Configuration records are private, bounded, regular and never symlinked."""
    from .runtime import _read_private

    try:
        value = json.loads(_read_private(path))
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeErrorSafe("resident_record_invalid") from exc


def get_json(port: int, path: str) -> dict:
    """Only fixed owned loopback endpoints; proxy environment and redirects excluded."""
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        raw = response.read(65537)
        if response.status != 200 or len(raw) > 65536:
            raise ValueError
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (OSError, ValueError, TypeError, http.client.HTTPException) as exc:
        raise RuntimeErrorSafe("legacy_instance_unavailable") from exc
    finally:
        connection.close()


@dataclass(frozen=True)
class LegacyBinding:
    primary_user_id: str
    home: Path
    revision: str
    web_port: int
    runtime_port: int
    project: Path
    project_identity: tuple[int, int]
    data_identity: tuple[int, int]

    @property
    def data_root(self) -> Path:
        return self.home / "research-web"

    def public_config(self) -> dict:
        value = asdict(self)
        for key in ("home", "project"):
            value[key] = str(value[key])
        return value

    @classmethod
    def from_config(cls, value: dict) -> LegacyBinding:
        try:
            return cls(
                value["primary_user_id"],
                Path(value["home"]),
                value["revision"],
                value["web_port"],
                value["runtime_port"],
                Path(value["project"]),
                tuple(value["project_identity"]),
                tuple(value["data_identity"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeErrorSafe("legacy_binding_invalid") from exc

    @classmethod
    def discover(cls, home: Path, primary_user_id: str) -> LegacyBinding:
        config = read_json(home / "resident/config.json")
        project = Path(config["project"])
        data = home / "research-web"
        manifest = read_json(home / "install/manifest.json")
        return cls(
            primary_user_id,
            home,
            manifest["code_commit"],
            config["web_port"],
            config["runtime_port"],
            project,
            (project.stat().st_dev, project.stat().st_ino),
            (data.stat().st_dev, data.stat().st_ino),
        )

    def verify(self) -> dict:
        """Verify the actual original instance; never start, stop or adopt a process."""
        from ..service_manager import WebServiceManager

        try:
            if str(UUID(self.primary_user_id)) != self.primary_user_id:
                raise ValueError
            for path, identity in (
                (self.project, self.project_identity),
                (self.data_root, self.data_identity),
            ):
                info = path.lstat()
                if (
                    path.resolve() != path.absolute()
                    or not stat.S_ISDIR(info.st_mode)
                    or info.st_uid != os.getuid()
                    or (info.st_dev, info.st_ino) != identity
                ):
                    raise ValueError
            config = read_json(self.home / "resident/config.json")
            manifest = read_json(self.home / "install/manifest.json")
            if (
                config["project"] != str(self.project)
                or config["web_port"] != self.web_port
                or config["runtime_port"] != self.runtime_port
                or manifest.get("status") != "installed"
                or manifest.get("code_commit") != self.revision
            ):
                raise ValueError
            actual = subprocess.check_output(
                ["/usr/bin/git", "-C", str(self.project), "rev-parse", "HEAD"], text=True, timeout=5
            ).strip()
            if actual != self.revision:
                raise ValueError
            manager = WebServiceManager(
                project_root=self.project,
                data_root=self.data_root,
                python=str(self.project / ".venv/bin/python"),
                node=config["node"],
                web_port=self.web_port,
                runtime_port=self.runtime_port,
            )
            services = manager.status()["services"]
            if not all(
                services[role].get("ready") and services[role].get("running")
                for role in ("web", "runtime")
            ):
                raise ValueError
            state = get_json(self.web_port, "/api/research/resident")
            runtime = get_json(self.web_port, "/api/research/runtime")
            if (
                state.get("enabled") is not True
                or state.get("revision") != self.revision
                or not all(
                    runtime.get(k) is True
                    for k in ("connected", "owned_runtime", "health_check_passed")
                )
            ):
                raise ValueError
            return state
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            log.warning("multiuser_legacy_binding_unverified", error_type=type(exc).__name__)
            raise RuntimeErrorSafe("legacy_instance_unverified") from exc


class AttachedPool:
    """Primary keeps its original directory and key namespace; others use the private pool."""

    def __init__(self, accounts: AccountStore, private_pool, binding: LegacyBinding, revision: str):
        self.accounts, self.private_pool, self.binding, self.revision = (
            accounts,
            private_pool,
            binding,
            revision,
        )
        primary = accounts.get_user(binding.primary_user_id)
        if primary.role != "admin" or not primary.enabled:
            raise RuntimeErrorSafe("legacy_owner_account_invalid")
        self.primary_user_id = primary.id
        self._verification_lock = asyncio.Lock()
        self._verified_at = 0.0

    async def _verify(self) -> None:
        async with self._verification_lock:
            if time.monotonic() - self._verified_at < 3:
                return
            await asyncio.to_thread(self.binding.verify)
            self._verified_at = time.monotonic()

    async def start(self) -> None:
        for attempt in range(30):
            try:
                await self._verify()
                return
            except RuntimeErrorSafe:
                if attempt == 29:
                    raise
                await asyncio.sleep(2)

    async def backend_for(self, user_id: str) -> Backend:
        if user_id == self.primary_user_id:
            await self._verify()
            # The original loopback service retains its resident authentication
            # contract. It is reachable externally only through this gateway.
            return Backend(f"http://127.0.0.1:{self.binding.web_port}", "")
        return await self.private_pool.backend_for(user_id)

    async def health(self) -> dict:
        # Anonymous probes must never run subprocesses or touch the old runtime.
        return {
            "status": "ready" if self._verified_at else "starting",
            "revision": self.revision,
            "primary_last_verified": bool(self._verified_at),
        }

    async def stop(self, user_id: str) -> None:
        if user_id == self.primary_user_id:
            raise AccountError("primary_account_protected", 409)
        await self.private_pool.stop(user_id)

    async def close(self) -> None:
        await self.private_pool.close()
