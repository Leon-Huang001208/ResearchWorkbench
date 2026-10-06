"""Stdlib private endpoint metadata; candidates are not listener reservations."""

from __future__ import annotations

import errno
import json
import logging
import os
import re
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

from . import runtime_mode as private

log = logging.getLogger(__name__)


class EndpointError(RuntimeError):
    """Stable path-free endpoint failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> NoReturn:
    log.warning("runtime_endpoints code=%s", code)
    raise EndpointError(code) from None


def _port(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 65535:
        _fail("endpoint_invalid_port")
    return value


def _mode(value: object) -> str:
    if type(value) is not str or value not in {"native", "docker"}:
        _fail("endpoint_invalid_mode")
    return value


@dataclass(frozen=True, slots=True)
class EndpointSnapshot:
    """Selected ports and an opaque generation used for compare-and-swap."""

    mode: str
    web_port: int
    runtime_port: int | None
    revision: str


def _record(mode: str, value: object) -> EndpointSnapshot:
    keys = {"web_port", "revision"} | ({"runtime_port"} if mode == "native" else set())
    if type(value) is not dict or set(value) != keys:
        _fail("endpoint_schema")
    web = _port(value["web_port"])
    runtime = _port(value["runtime_port"]) if mode == "native" else None
    if runtime == web:
        _fail("endpoint_invalid_pair")
    revision = value["revision"]
    if type(revision) is not str or re.fullmatch(r"[a-f0-9]{32}", revision) is None:
        _fail("endpoint_schema")
    return EndpointSnapshot(mode, web, runtime, revision)


class EndpointStore:
    """Independent per-mode CAS records; read never creates or repairs files."""

    def __init__(self, home: Path) -> None:
        self.home = Path(home).absolute()
        self.path = self.home / "install" / "endpoints.json"
        self._lock = private.RuntimeModeStore(self.home)

    def _validate_path(self) -> None:
        if os.name != "posix":
            _fail("endpoint_platform_unverified")
        private._validate_existing_prefix(self.path)
        try:
            private._validate_posix_private_directory(self.home.lstat())
        except FileNotFoundError:
            pass

    def _load(self):
        self._validate_path()
        try:
            raw, identity = private._read_bytes(self.path)
        except FileNotFoundError:
            return {}, None
        try:
            value = json.loads(raw, object_pairs_hook=private._unique_object)
        except (ValueError, RecursionError):
            _fail("endpoint_schema")
        if (type(value) is not dict or set(value) != {"schema_version", "records"}
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or type(value["records"]) is not dict):
            _fail("endpoint_schema")
        records = {_mode(mode): _record(_mode(mode), record)
                   for mode, record in value["records"].items()}
        return records, identity

    def read(self, mode: str) -> EndpointSnapshot | None:
        try:
            _mode(mode)
            records, _ = self._load()
            return records.get(mode)
        except private.RuntimeModeError as error:
            _fail("endpoint_" + error.code.removeprefix("runtime_mode_"))
        except (OSError, ValueError, TypeError):
            _fail("endpoint_io")

    def publish(self, mode: str, web_port: int, runtime_port: int | None = None,
                *, expected: EndpointSnapshot | None) -> EndpointSnapshot:
        try:
            _mode(mode)
            _port(web_port)
            if mode == "native":
                _port(runtime_port)
                if runtime_port == web_port:
                    _fail("endpoint_invalid_pair")
            elif runtime_port is not None:
                _fail("endpoint_invalid_pair")
            self._validate_path()
            with self._lock._write_lock(strict_parent=True):
                records, identity = self._load()
                if records.get(mode) != expected:
                    _fail("endpoint_conflict")
                result = EndpointSnapshot(mode, web_port, runtime_port, uuid4().hex)
                records[mode] = result
                values = {}
                for key, record in records.items():
                    values[key] = {"web_port": record.web_port, "revision": record.revision}
                    if key == "native":
                        values[key]["runtime_port"] = record.runtime_port
                raw = json.dumps({"schema_version": 1, "records": values}).encode()
                published = private._atomic_write_posix(self.path, raw, identity, strict_parent=True)
                checked, after = self._load()
                if not private._same_identity(published, after) or checked != records:
                    _fail("endpoint_changed")
                log.debug("runtime_endpoints operation=publish code=ok")
                return result
        except private.RuntimeModeError as error:
            _fail("endpoint_" + error.code.removeprefix("runtime_mode_"))
        except (OSError, ValueError, TypeError):
            _fail("endpoint_io")

    def verify_facts(self, mode: str, web_port: int, runtime_port: int | None = None) -> None:
        """Compare caller-verified facts; this does not prove process ownership."""
        _port(web_port)
        if runtime_port is not None:
            _port(runtime_port)
        record = self.read(mode)
        if record is None or (record.web_port, record.runtime_port) != (web_port, runtime_port):
            _fail("endpoint_facts_mismatch")

    def restore(self, mode: str, previous: EndpointSnapshot | None,
                *, expected: EndpointSnapshot) -> EndpointSnapshot | None:
        """Restore logical ports only while this exact publication is still current.

        Restoration gets a fresh revision, so rollback cannot revive an obsolete
        CAS generation. Other-mode records remain unchanged.
        """
        _mode(mode)
        if not isinstance(expected, EndpointSnapshot) or expected.mode != mode:
            _fail("endpoint_conflict")
        if previous is not None:
            if not isinstance(previous, EndpointSnapshot) or previous.mode != mode:
                _fail("endpoint_conflict")
            return self.publish(mode, previous.web_port, previous.runtime_port, expected=expected)
        try:
            self._validate_path()
            with self._lock._write_lock(strict_parent=True):
                records, identity = self._load()
                if records.get(mode) != expected:
                    _fail("endpoint_conflict")
                del records[mode]
                values = {key: {"web_port": item.web_port, "revision": item.revision,
                                **({"runtime_port": item.runtime_port} if key == "native" else {})}
                          for key, item in records.items()}
                raw = json.dumps({"schema_version": 1, "records": values}).encode()
                published = private._atomic_write_posix(self.path, raw, identity, strict_parent=True)
                checked, after = self._load()
                if not private._same_identity(published, after) or checked != records:
                    _fail("endpoint_changed")
                log.debug("runtime_endpoints operation=restore code=ok")
                return None
        except private.RuntimeModeError as error:
            _fail("endpoint_" + error.code.removeprefix("runtime_mode_"))
        except (OSError, ValueError, TypeError):
            _fail("endpoint_io")


def select_port(
    preferred: int, *, explicit: bool = False, excluded: Iterable[int] = ()
) -> int:
    """Try preferred, then bounded OS loopback candidates; caller must bind/retry."""
    _port(preferred)
    excluded = tuple(_port(port) for port in excluded)
    for attempt in range(17):
        candidate = preferred if attempt == 0 else 0
        if candidate in excluded:
            if explicit:
                _fail("endpoint_port_in_use")
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", candidate))
                selected = probe.getsockname()[1]
                if selected not in excluded:
                    return selected
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                _fail("endpoint_bind_failed")
            if explicit:
                _fail("endpoint_port_in_use")
    _fail("endpoint_candidates_exhausted")
