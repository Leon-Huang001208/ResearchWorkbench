"""Explicit, quiescent, token-preserving transaction for the two control origins.

The caller holds the installation lifecycle lock through prepare/start/commit or
stop/rollback. Persistent intent detects interruption; it never contains backups
of tokens and never authorizes automatic recovery after process loss.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlsplit

from research_workbench_entrypoint import runtime_mode as private

log = logging.getLogger(__name__)
_FILES = ("datahub.json", "mcp-runtime.json")
_JOURNAL = "origin-transaction.json"


class ControlOriginError(RuntimeError):
    """Stable error without paths, tokens, fingerprints or record contents."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(suffix: str) -> NoReturn:
    code = "control_origin_" + suffix
    log.warning("control_origin code=%s", code)
    raise ControlOriginError(code) from None


class ControlRecordError(ValueError):
    """Pure parser code translated by existing service-specific wrappers."""


def checked_control_url(value) -> str:
    """Existing DataHub/MCP loopback predicate, usable without Web dependencies."""
    if not isinstance(value, str):
        raise ControlRecordError("url_type")
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.username is not None or parsed.password is not None
                or "?" in value or "#" in value or parsed.path not in {"", "/"}
                or not parsed.port):
            raise ValueError("not loopback")
        return value.rstrip("/")
    except (ValueError, TypeError):
        raise ControlRecordError("invalid_url") from None


def parse_datahub_control(raw: bytes, url: str | None) -> dict:
    """Original reader schema, including its additional valid JSON fields."""
    try:
        config = json.loads(raw)
        if (not isinstance(config, dict) or not isinstance(config.get("token"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", config["token"])):
            raise ValueError("invalid token")
        checked_control_url(config["url"])
        if url is not None and config["url"] != url:
            raise ControlRecordError("origin_mismatch")
        return config
    except ControlRecordError:
        raise
    except (ValueError, KeyError, TypeError):
        raise ControlRecordError("invalid") from None


def parse_mcp_control(raw: bytes, expected_url: str) -> dict:
    """Original MCP reader predicate; transaction adds its own strictness."""
    try:
        value = json.loads(raw)
        if (not isinstance(value, dict) or value.get("version") != 1
                or not isinstance(value.get("token"), str)
                or re.fullmatch(r"[A-Za-z0-9_-]{43,128}", value["token"]) is None
                or value.get("url") != expected_url):
            raise ValueError("invalid MCP control")
        checked_control_url(value["url"])
        return value
    except (KeyError, TypeError, ValueError):
        raise ControlRecordError("invalid") from None


def _checked_origin(value: str) -> str:
    try:
        return checked_control_url(value)
    except ControlRecordError:
        _fail("invalid_origin")


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")


def _decode(name: str, raw: bytes, origin: str) -> dict:
    if len(raw) > 4096:
        _fail("schema")
    try:
        value = json.loads(raw, object_pairs_hook=private._unique_object,
                           parse_constant=lambda _: _fail("schema"))
        if type(value) is not dict:
            _fail("schema")
        if name == "mcp-runtime.json":
            if type(value.get("version")) is not int or value["version"] != 1:
                _fail("schema")
            return parse_mcp_control(raw, origin)
        return parse_datahub_control(raw, origin)
    except (ValueError, TypeError, RecursionError, private.RuntimeModeError):
        _fail("schema")


class ControlOriginTransaction:
    """Prepare updates existing records; commit/rollback require owned identities."""

    def __init__(self, data_root: Path, previous_origin: str, next_origin: str, *, quiescent):
        self.root = Path(data_root).absolute()
        self.folder = self.root / ".control"
        self.previous = _checked_origin(previous_origin)
        self.next = _checked_origin(next_origin)
        self.quiescent = quiescent
        self._state = "new"
        self._root_identity = None
        self._parent_identity = None
        self._before: dict[str, tuple[bytes, os.stat_result] | None] = {}
        self._written: dict[str, tuple[bytes, os.stat_result]] = {}
        self._journal_identity = None

    def _quiet(self) -> None:
        try:
            result = self.quiescent()
        except Exception:
            _fail("not_quiescent")
        if result is not True:
            _fail("not_quiescent")

    def _guard(self) -> None:
        private._validate_existing_prefix(self.folder / _JOURNAL)
        root = self.root.lstat()
        private._validate_posix_private_directory(root)
        if self._root_identity is not None and private._node_identity(root) != self._root_identity:
            _fail("recovery_unverified")
        if self._parent_identity is not None:
            current = self.folder.lstat()
            private._validate_posix_private_directory(current)
            if private._node_identity(current) != self._parent_identity:
                _fail("recovery_unverified")

    def _read(self, name: str):
        self._guard()
        try:
            return private._read_bytes(self.folder / name)
        except FileNotFoundError:
            return None

    def _write(self, name: str, raw: bytes, expected):
        self._guard()
        result = private._atomic_write_posix(
            self.folder / name, raw, expected, strict_parent=True
        )
        self._guard()
        return result

    def _journal(self, phase: str) -> None:
        facts = {}
        for name, original in self._before.items():
            current = self._written.get(name, original)
            facts[name] = None if current is None else {
                "identity": list(private._identity(current[1])),
                "sha256": hashlib.sha256(current[0]).hexdigest(),
            }
        raw = _json_bytes({
            "version": 1, "previous_origin": self.previous, "next_origin": self.next,
            "phase": phase, "files": facts,
        })
        self._journal_identity = self._write(_JOURNAL, raw, self._journal_identity)

    def _verify_owned(self) -> None:
        self._guard()
        for name, original in self._before.items():
            expected = self._written.get(name, original)
            current = self._read(name)
            if expected is None:
                if current is not None:
                    _fail("recovery_unverified")
            elif (current is None or current[0] != expected[0]
                  or not private._same_identity(current[1], expected[1])):
                _fail("recovery_unverified")
        journal = self._read(_JOURNAL)
        if self._journal_identity is None:
            if journal is not None:
                _fail("recovery_unverified")
        elif journal is None or not private._same_identity(journal[1], self._journal_identity):
            _fail("recovery_unverified")

    def _discard_journal(self) -> None:
        if self._journal_identity is None:
            return
        self._guard()
        path = self.folder / _JOURNAL
        with private._pin_posix_parents(path, node_only=True) as parent:
            private._validate_posix_private_directory(os.fstat(parent))
            if not private._same_identity(
                private._leaf_identity_at(parent, _JOURNAL), self._journal_identity
            ):
                _fail("recovery_unverified")
            os.unlink(_JOURNAL, dir_fd=parent)
            os.fsync(parent)
        self._journal_identity = None

    def prepare(self) -> None:
        try:
            if os.name != "posix":
                _fail("platform_unverified")
            if self._state != "new":
                _fail("state")
            self._quiet()
            self._guard()
            self._root_identity = private._node_identity(self.root.lstat())
            try:
                parent = self.folder.lstat()
            except FileNotFoundError:
                self._state = "prepared"
                return
            private._validate_posix_private_directory(parent)
            self._parent_identity = private._node_identity(parent)
            if self._read(_JOURNAL) is not None:
                _fail("interrupted")
            values = {}
            for name in _FILES:
                record = self._read(name)
                self._before[name] = record
                if record is not None:
                    values[name] = _decode(name, record[0], self.previous)
            if self.previous == self.next or not values:
                self._state = "prepared"
                return
            targets = {}
            for name, value in values.items():
                raw = _json_bytes({**value, "url": self.next})
                _decode(name, raw, self.next)
                targets[name] = raw
            self._journal("preparing")
            try:
                for name, raw in targets.items():
                    self._quiet()
                    self._verify_owned()
                    identity = self._write(name, raw, self._before[name][1])
                    self._written[name] = (raw, identity)
                    self._journal("preparing")
                self._verify_owned()
                self._journal("prepared")
            except Exception:
                # Validate the entire pair first. A write with an unknown
                # publication result leaves intent intact, never guessed recovery.
                self._state = "prepared"
                self.rollback()
                raise
            self._state = "prepared"
            log.info("control_origin operation=prepare code=ok")
        except ControlOriginError:
            raise
        except (OSError, private.RuntimeModeError, ValueError, TypeError):
            _fail("io")

    def commit(self) -> None:
        """Discard owned intent only; target may now be running under caller lock."""
        try:
            if self._state != "prepared":
                _fail("state")
            if self._parent_identity is not None:
                self._verify_owned()
                self._discard_journal()
            self._before.clear()
            self._written.clear()
            self._state = "committed"
            log.info("control_origin operation=commit code=ok")
        except ControlOriginError:
            raise
        except (OSError, private.RuntimeModeError):
            _fail("recovery_unverified")

    def rollback(self) -> None:
        """After caller stops target, restore exact in-memory bytes if still owned."""
        try:
            if self._state != "prepared":
                _fail("state")
            self._quiet()
            if self._parent_identity is not None:
                self._verify_owned()
                for name in reversed(tuple(self._written)):
                    self._quiet()
                    self._verify_owned()
                    raw = self._before[name][0]
                    identity = self._write(name, raw, self._written[name][1])
                    self._written[name] = (raw, identity)
                    self._journal("rolling_back")
                self._verify_owned()
                self._discard_journal()
            self._before.clear()
            self._written.clear()
            self._state = "rolled_back"
            log.info("control_origin operation=rollback code=ok")
        except ControlOriginError:
            raise
        except (OSError, private.RuntimeModeError):
            _fail("recovery_unverified")
