"""Retire old control metadata only after a proved macOS kernel boot change."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

from core.observability import get_logger

from .runtime import RuntimeErrorSafe, _create_private, _directory, _read_private

log = get_logger(__name__)


def boot_identity() -> str:
    try:
        value = (
            subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"], text=True, timeout=5
            )
            .strip()
            .lower()
        )
        return str(UUID(value))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RuntimeErrorSafe("server_boot_identity_unavailable") from exc


def retire_previous_boot(user_root: Path, *, current_boot: str, accounts, archive: Path) -> None:
    """No PID is signalled. A same-boot crash or unsigned old record stays blocked."""
    try:
        _directory(user_root, create=False)
        _directory(user_root / "state", create=False)
        user_id = str(UUID(user_root.name))
        accounts.get_user(user_id)
        owner = user_root / "state/owner.json"
        raw = _read_private(owner)
        record = json.loads(raw)
        if (
            set(record) != {"version", "instance", "user", "pids", "boot_id"}
            or record["version"] != 1
            or record["user"] != user_id
            or not re.fullmatch(r"[a-f0-9]{32}", record["instance"])
            or not isinstance(record["pids"], list)
            or len(record["pids"]) > 2
            or any(type(pid) is not int or pid <= 0 for pid in record["pids"])
            or str(UUID(record["boot_id"])) != record["boot_id"]
            or str(UUID(current_boot)) != current_boot
            or record["boot_id"] == current_boot
        ):
            raise ValueError
        _directory(archive)
        destination = archive / uuid4().hex
        _directory(destination)
        _create_private(destination / "owner.json", raw)
        key = user_root / "state/gateway.key"
        if key.exists() or key.is_symlink():
            _create_private(destination / "gateway.key", _read_private(key))
        if _read_private(owner) != raw:
            raise ValueError
        if key.exists():
            key.unlink()
        owner.unlink()
        log.info("multiuser_previous_boot_retired", user_id=user_id)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise RuntimeErrorSafe("runtime_stale_owner") from exc
