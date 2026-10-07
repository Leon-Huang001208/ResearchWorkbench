"""Stdlib Hot settings and diagnostic entry; no secrets, Store or research startup."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import stat
import subprocess
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

log = logging.getLogger(__name__)
MAX_BYTES = 65536


class HotError(RuntimeError):
    """Stable errors never contain input, credential values or subprocess output."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "hot_argument_invalid\n")


def _no_alias(path: Path) -> None:
    for parent in reversed((path, *path.parents)):
        try:
            if parent.is_symlink():
                raise HotError("hot_storage_unsafe")
        except OSError:
            raise HotError("hot_storage_unavailable") from None


def _read(path: Path, *, private: bool = False) -> dict:
    _no_alias(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise HotError("hot_config_unsafe")
            if private and (os.name != "posix" or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
                raise HotError("hot_config_unsafe")
            value = json.loads(stream.read(MAX_BYTES + 1))
        if not isinstance(value, dict):
            raise HotError("hot_config_invalid")
        return value
    except HotError:
        raise
    except (OSError, ValueError):
        raise HotError("hot_config_unavailable") from None


def _node() -> str:
    explicit = os.environ.get("RESEARCH_NODE_BINARY")
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    value = explicit or (str(bundled) if bundled.is_file() else shutil.which("node"))
    if not value:
        raise HotError("hot_node_missing")
    return value


def normalize(project: Path, value: dict) -> dict:
    try:
        result = subprocess.run(
            [_node(), str(project / "services/hot/scripts/check-config.ts")],
            input=json.dumps(value), capture_output=True, text=True, timeout=10,
            cwd=project,
        )
        if result.returncode or len(result.stdout.encode()) > MAX_BYTES:
            raise HotError("hot_config_invalid")
        normalized = json.loads(result.stdout)
        if not isinstance(normalized, dict) or "error" in normalized:
            raise HotError("hot_config_invalid")
        return normalized
    except HotError:
        raise
    except (OSError, ValueError, subprocess.SubprocessError):
        raise HotError("hot_configuration_bridge_unavailable") from None


def _record_configuration(project: Path) -> None:
    path = project / "logs" / "hot" / "configuration.jsonl"
    _no_alias(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise HotError("hot_log_unsafe")
            stream.write(json.dumps({"event": "hot_configuration_saved", "time": datetime.now(timezone.utc).isoformat()}) + "\n")
            stream.flush()
    except OSError:
        raise HotError("hot_log_unavailable") from None


def save_settings(project: Path, home: Path, config: dict) -> dict:
    normalized = normalize(project, config)
    target = home / "hot" / "settings.json"
    _no_alias(target)
    parent = target.parent
    try:
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = parent.stat()
    except OSError:
        raise HotError("hot_storage_unavailable") from None
    if os.name != "posix" or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise HotError("hot_storage_unsafe")
    if target.exists():
        previous = _read(target, private=True)
        if previous.get("projectRoot") != str(project):
            raise HotError("hot_foreign_config")
    try:
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise HotError("hot_storage_unavailable") from None
    temporary = "settings-" + uuid4().hex + ".tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schemaVersion": 1, "projectRoot": str(project), "config": normalized}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, "settings.json", src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    except OSError:
        raise HotError("hot_config_write_failed") from None
    finally:
        os.close(directory)
    log.info("hot_configuration_saved")
    try:
        _record_configuration(project)
    except HotError:
        return {"state": "configured" if normalized["enabled"] else "disabled", "enabled": normalized["enabled"],
                "config_saved": True, "logging": "unavailable", "code": "hot_log_unavailable"}
    return {"state": "configured" if normalized["enabled"] else "disabled", "enabled": normalized["enabled"]}


def status(project: Path, home: Path) -> dict:
    target = home / "hot" / "settings.json"
    _no_alias(target)
    if not target.exists():
        return {"state": "disabled", "enabled": False, "service": "not_integrated"}
    record = _read(target, private=True)
    if record.get("schemaVersion") != 1 or record.get("projectRoot") != str(project):
        raise HotError("hot_foreign_config")
    config = record.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("enabled"), bool):
        raise HotError("hot_config_invalid")
    return {"state": "configured" if config["enabled"] else "disabled", "enabled": config["enabled"],
            "service": "not_integrated", "lifecycle": "not_integrated"}


def dispatch(argv: list[str], project: Path) -> int:
    parser = SafeParser(prog="rwb hot", description="Hot configuration and diagnostics; lifecycle integration is in progress.")
    parser.add_argument("--data-home", type=Path, default=Path(os.environ.get("RESEARCH_DATA_HOME", str(Path.home() / ".research-workbench/research-web"))))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "doctor"):
        sub.add_parser(command).add_argument("--json", action="store_true")
    configure = sub.add_parser("configure")
    configure.add_argument("--file", type=Path, required=True)
    configure.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    home = args.data_home.absolute()
    try:
        if args.command == "configure":
            value = save_settings(project, home, _read(args.file.absolute()))
        else:
            value = status(project, home)
            if args.command == "doctor":
                value["checks"] = {"configuration": "configured" if value["enabled"] else "disabled",
                                   "service": "NOT_RUN", "database": "NOT_RUN", "model": "NOT_RUN"}
        print(json.dumps(value, ensure_ascii=False))
        return 1 if value.get("logging") == "unavailable" else 0
    except HotError as error:
        log.warning("hot_operation_failed code=%s", str(error))
        print(json.dumps({"state": "unavailable", "code": str(error)}))
        return 1
