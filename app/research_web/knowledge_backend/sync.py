"""Stable directory snapshots and conditional publication into a single private KB."""

from __future__ import annotations

import asyncio
import hashlib
import os
import plistlib
import re
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, admission

from ..datahub.security import directory, read_file, sync_directory, write_new
from ..store import StoreError
from . import sync_storage
from .client import ORIGINAL_LIMIT
from .storage import canonical, digest, fail
from .sync_storage import SyncStore

log = get_logger(__name__)
DEFAULT_ROOT = Path("/Volumes/WorkDisk/Data/RWB/knowledge-inbox")
WORKDISK_UUID = "2BC466D2-FD62-4395-86AC-45CFF653BC51"
SOURCE_MARKER = ".rwb-knowledge-owner.json"
EXTENSIONS = frozenset({".pdf", ".docx", ".md", ".txt"})
IDENTITY_KEYS = ("origin", "user_id", "workspace_id")
SCAN_TIMEOUT = 60
MAX_SCAN_FILES = 1000
MAX_SCAN_BYTES = 64 * 1024 * 1024
MAX_SKIPPED_ITEMS = 128
MAX_PENDING_PER_SCAN = 8
MAX_CURRENT_AUDITS = 1


def _now():
    return datetime.now(UTC).isoformat()


def _temporary(name):
    lower = name.lower()
    return (
        name.startswith((".", "~$"))
        or name.endswith("~")
        or any(part in lower.split(".") for part in ("tmp", "temp", "part", "swp", "download"))
    )


def verify_workdisk(root):
    """Volume names alone never authorize a write to the resident data drive."""
    if not root.is_relative_to(Path("/Volumes/WorkDisk")):
        return
    try:
        result = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", "/Volumes/WorkDisk"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        info = plistlib.loads(result.stdout)
        if (
            info.get("VolumeUUID", "").upper() != WORKDISK_UUID
            or info.get("FilesystemType") != "apfs"
        ):
            fail("knowledge_sync_volume_identity", 503)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        fail("knowledge_sync_volume_unavailable", 503)


class KnowledgeSyncService:
    """Owns mutable source state; the existing Host owns its worker and credentials."""

    def __init__(self, account_root, authorize=None, *, default_root=None):
        self.store = SyncStore(Path(account_root))
        self.authorize = authorize
        self.default_root = Path(default_root) if default_root is not None else DEFAULT_ROOT
        self.lock = asyncio.Lock()
        self.running = False

    def close(self):
        # SQLite connections are scoped to transactions; the Host cancels its worker first.
        pass

    def matches_binding(self, binding):
        config = self.store.config()
        return bool(config and all(config.get(key) == binding.get(key) for key in IDENTITY_KEYS))

    async def _authorized(self):
        if self.authorize is None:
            fail("knowledge_sync_authorization_required", 401)
        client, binding = await self.authorize()
        if self.store.config() and not self.matches_binding(binding):
            fail("knowledge_sync_binding_changed", 403)
        return client, binding

    @staticmethod
    def _root(root):
        verify_workdisk(root)
        try:
            if not root.is_absolute() or root.resolve(strict=True) != root:
                fail("knowledge_sync_root_unsafe", 422)
            for parent in (root, *root.parents):
                if parent.is_symlink():
                    fail("knowledge_sync_root_unsafe", 422)
            info = root.lstat()
            if not stat.S_ISDIR(info.st_mode):
                fail("knowledge_sync_root_unavailable", 503)
            return info
        except OSError:
            fail("knowledge_sync_root_unavailable", 503)

    def _claim(self, root, config):
        self._root(root)
        claim = canonical(
            {
                "schema": 1,
                "owner": self.store.owner,
                "knowledge_base_id": config["knowledge_base_id"],
                **{key: config[key] for key in IDENTITY_KEYS},
            }
        )
        with directory(root) as fd:
            if SOURCE_MARKER not in os.listdir(fd):
                try:
                    write_new(fd, SOURCE_MARKER, claim)
                    sync_directory(fd)
                except StoreError:
                    # Exclusive creation arbitrates two accounts claiming the same source.
                    if read_file(fd, SOURCE_MARKER, private=True, limit=16384) != claim:
                        fail("knowledge_sync_source_bound", 409)
            if read_file(fd, SOURCE_MARKER, private=True, limit=16384) != claim:
                fail("knowledge_sync_source_bound", 409)

    async def configure(self, kb_id, enabled, root=None):
        if (
            not isinstance(kb_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", kb_id) is None
            or not isinstance(enabled, bool)
        ):
            fail("knowledge_sync_configuration_invalid", 422)
        selected = Path(root) if root is not None else self.default_root
        if selected != self.default_root:
            fail("knowledge_sync_root_restricted", 422)
        async with self.lock:
            client, binding = await self._authorized()
            bases = await client.knowledge_bases()
            selected_base = next((row for row in bases if row.get("id") == kb_id), None)
            if selected_base is None:
                fail("knowledge_sync_kb_denied", 403)
            if selected_base.get("source_tenant_id") or (
                selected_base.get("tenant_id") is not None
                and str(selected_base["tenant_id"]) != str(binding["workspace_id"])
            ):
                fail("knowledge_sync_kb_denied", 403)
            previous = self.store.config()
            if previous and previous["knowledge_base_id"] != kb_id:
                fail("knowledge_sync_source_bound", 409)
            config = {
                **(previous or {}),
                **{key: binding[key] for key in IDENTITY_KEYS},
                "knowledge_base_id": kb_id,
                "source_root": str(selected),
                "enabled": enabled,
            }
            self._claim(selected, config)
            self.store.save_config(config)
            log.info("knowledge_sync_configured", enabled=enabled)
            return self.status()

    def status(self):
        config = self.store.config() or {}
        rows = [row for row in self.store.rows() if row["version"] == row["desired_version"]]
        current_rows = self.store.rows(current=True)
        current_ids = {row["path"]: row["document_id"] for row in current_rows}
        items = [
            {
                **row,
                "tombstone": bool(row["tombstone"]),
                "state": "withdrawn" if row["tombstone"] else row["state"],
                "current_document_id": current_ids.get(row["path"]),
            }
            for row in rows
        ]
        by_path = {row["path"]: row for row in items}
        for skipped in config.get("skipped_items", []):
            path = skipped["path"]
            by_path[path] = {
                "path": path,
                "version": None,
                "tombstone": False,
                **by_path.get(path, {}),
                **skipped,
                "state": "skipped",
                "current_document_id": current_ids.get(path),
            }
        return {
            "configured": bool(config),
            "enabled": config.get("enabled", False),
            "source_root": config.get("source_root", str(self.default_root)),
            "knowledge_base_id": config.get("knowledge_base_id"),
            "kb_id": config.get("knowledge_base_id"),
            "running": self.running,
            "last_scan_at": config.get("last_scan_at"),
            "last_scan_result": config.get("last_scan_result", "not_run"),
            "last_error": config.get("last_error"),
            "connectivity": config.get("connectivity", "not_verified"),
            "current_count": len(current_rows),
            "pending_count": sum(
                not row["tombstone"]
                and row["state"] in {"observing", "pending", "uploading", "uncertain"}
                for row in rows
            ),
            "error_count": sum(bool(row["error"]) and not row["tombstone"] for row in rows),
            "document_count": sum(not row["tombstone"] for row in rows),
            "skipped_count": config.get("skipped_count", 0),
            "skipped_items": config.get("skipped_items", []),
            "limits": {
                "max_file_bytes": ORIGINAL_LIMIT,
                "max_scan_files": MAX_SCAN_FILES,
                "max_scan_bytes": MAX_SCAN_BYTES,
                "max_skipped_items": MAX_SKIPPED_ITEMS,
                "max_preservation_bytes": sync_storage.MAX_DATABASE_BYTES,
                "journal_reserve_bytes": sync_storage.SQLITE_RESERVE_BYTES,
                "max_pending_per_scan": MAX_PENDING_PER_SCAN,
                "max_current_audits": MAX_CURRENT_AUDITS,
            },
            "items": sorted(by_path.values(), key=lambda item: item["path"]),
        }

    def current_documents(self):
        config = self.store.config() or {}
        return [
            {**row, "kb_id": config.get("knowledge_base_id")}
            for row in self.store.rows(current=True)
        ]

    def history(self, path=None):
        return self.store.rows(path=path)

    def snapshot(self, sha256):
        return self.store.snapshot(sha256)

    def preservation(self):
        return self.store.preservation()

    @staticmethod
    def _read_at(fd, name):
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(handle, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or not 0 < before.st_size <= ORIGINAL_LIMIT
            ):
                fail("knowledge_sync_file_unsupported", 422)
            raw = stream.read(ORIGINAL_LIMIT + 1)
            after = os.fstat(stream.fileno())
            if len(raw) != before.st_size or (
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                fail("knowledge_sync_source_changing", 409)
            return {"content": raw, "sha256": digest(raw), "md5": hashlib.md5(raw).hexdigest()}

    def _collect(self, root):
        initial = self._root(root)
        observations, present = {}, set()
        skipped, skipped_count, total = [], 0, 0

        def skip(path, info, reason):
            nonlocal skipped_count
            skipped_count += 1
            if len(skipped) < MAX_SKIPPED_ITEMS:
                skipped.append({"path": path, "size": info.st_size, "error": reason})

        def walk(fd, prefix=""):
            nonlocal total
            with os.scandir(fd) as entries:
                for entry in entries:
                    if _temporary(entry.name):
                        continue
                    path = prefix + entry.name
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        child = os.open(
                            entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                        )
                        try:
                            walk(child, path + "/")
                        finally:
                            os.close(child)
                    else:
                        present.add(path)
                        if len(present) > MAX_SCAN_FILES:
                            fail("knowledge_sync_scan_budget", 413)
                        if stat.S_ISLNK(info.st_mode):
                            skip(path, info, "knowledge_sync_symlink_ignored")
                        elif Path(entry.name).suffix.lower() not in EXTENSIONS:
                            skip(path, info, "knowledge_sync_extension_unsupported")
                        elif not stat.S_ISREG(info.st_mode):
                            skip(path, info, "knowledge_sync_file_not_regular")
                        elif info.st_nlink != 1:
                            skip(path, info, "knowledge_sync_hardlink_ignored")
                        elif info.st_size == 0:
                            skip(path, info, "knowledge_sync_file_empty")
                        elif info.st_size > ORIGINAL_LIMIT:
                            skip(path, info, "knowledge_sync_file_too_large")
                        else:
                            observations[path] = self._read_at(fd, entry.name)
                            total += len(observations[path]["content"])
                            if total > MAX_SCAN_BYTES:
                                fail("knowledge_sync_scan_budget", 413)

        with directory(root) as fd:
            walk(fd)
        final = self._root(root)
        if (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino):
            fail("knowledge_sync_root_changed", 503)
        return observations, present, skipped, skipped_count

    async def _verify(self, client, row, meta, kb_id):
        if meta.get("kb_id") != kb_id or meta.get("file_hash") != row["md5"]:
            fail("knowledge_sync_upstream_identity", 502)
        if meta.get("parse_status") in {"failed", "cancelled", "deleting"}:
            fail("knowledge_sync_parse_failed", 409)
        if meta.get("parse_status") != "completed" or meta.get("enable_status") != "enabled":
            return False
        if digest(await client.original(meta["id"])) != row["sha256"]:
            fail("knowledge_sync_upstream_identity", 502)
        return True

    async def _process(self, client, binding, config, row):
        kb_id = config["knowledge_base_id"]
        try:
            identifier = row["document_id"]
            if not identifier:
                # Reuse only a verified identical original, including rename/duplicate and recovery.
                candidates = [
                    item
                    for item in self.store.rows()
                    if item["sha256"] == row["sha256"] and item["document_id"]
                ]
                if not candidates and row["state"] in {"uploading", "uncertain"}:
                    candidates = [
                        {"document_id": item["id"]}
                        for item in await client.documents_in_base(kb_id)
                        if item.get("kb_id") == kb_id and item.get("file_hash") == row["md5"]
                    ]
                if candidates:
                    identifier = candidates[0]["document_id"]
                else:
                    self.store.update(row, state="uploading")
                    meta = await client.upload(
                        kb_id,
                        row["path"],
                        self.snapshot(row["sha256"]),
                        {
                            "rwb_sha256": row["sha256"],
                            "rwb_version": str(row["version"]),
                            "rwb_owner": self.store.owner,
                        },
                    )
                    identifier = meta["id"]
                self.store.update(row, state="pending", document_id=identifier)
            meta = await client.document(identifier)
            if not await self._verify(client, row, meta, kb_id):
                self.store.update(row, state="pending", document_id=identifier)
                return
            _, current_binding = await self._authorized()
            if current_binding != binding:
                fail("knowledge_sync_binding_changed", 403)
            # A post-upload source read closes the long network/parse window before CAS promotion.
            root = Path(config["source_root"])
            self._root(root)
            components = row["path"].split("/")
            with directory(root, tuple(components[:-1])) as fd:
                current = self._read_at(fd, components[-1])
            if current["sha256"] != row["sha256"]:
                self.store.observe(
                    {row["path"]: current}, {item["path"] for item in self.store.rows()}
                )
                return
            if self.store.update(row, state="current", document_id=identifier, promote=True):
                log.info("knowledge_sync_document_promoted", version=row["version"])
        except StoreError as exc:
            if exc.status in {401, 403}:
                raise
            state = (
                "uncertain" if exc.code in {"weknora_timeout", "weknora_unavailable"} else "error"
            )
            self.store.update(row, state=state, error=exc.code)
            log.warning("knowledge_sync_document_failed", code=exc.code)
        except OSError as exc:
            self.store.update(row, state="error", error="knowledge_sync_source_unavailable")
            log.warning("knowledge_sync_source_unavailable", error_type=type(exc).__name__)

    async def scan(self, *, force=False):
        async with self.lock:
            config = self.store.config()
            if not config:
                return self.status()
            if not config["enabled"] and not force:
                return self.status()
            self.running = True
            try:
                with admission():
                    try:
                        async with asyncio.timeout(SCAN_TIMEOUT):
                            client, binding = await self._authorized()
                            root = Path(config["source_root"])
                            self._claim(root, config)
                            observations, present, skipped, skipped_count = self._collect(root)
                            self.store.observe(observations, present)
                            config.update(skipped_items=skipped, skipped_count=skipped_count)
                            eligible = [
                                row
                                for row in self.store.rows()
                                if row["version"] == row["desired_version"]
                                and not row["tombstone"]
                                and row["stable"] >= 2
                                and row["path"] in observations
                                and (row["state"] != "error" or (force and row["document_id"]))
                            ]
                            for phase, limit in (
                                ("pending", MAX_PENDING_PER_SCAN),
                                ("current", MAX_CURRENT_AUDITS),
                            ):
                                rows = [
                                    row
                                    for row in eligible
                                    if (row["state"] == "current") == (phase == "current")
                                ]
                                cursor = config.get(phase + "_cursor", "")
                                rows = [row for row in rows if row["path"] > cursor] + [
                                    row for row in rows if row["path"] <= cursor
                                ]
                                for row in rows[:limit]:
                                    # Persist progress before IO so a deadline or restart cannot starve the suffix.
                                    config[phase + "_cursor"] = row["path"]
                                    self.store.save_config(config)
                                    await self._process(client, binding, config, row)
                            config.update(
                                last_scan_at=_now(),
                                last_scan_result="completed",
                                last_error=None,
                                connectivity="verified",
                            )
                    except (StoreError, OSError, TimeoutError) as exc:
                        code = (
                            exc.code
                            if isinstance(exc, StoreError)
                            else (
                                "knowledge_sync_timeout"
                                if isinstance(exc, TimeoutError)
                                else "knowledge_sync_scan_failed"
                            )
                        )
                        if isinstance(exc, StoreError) and exc.status in {401, 403}:
                            config["enabled"] = False
                        config.update(
                            last_scan_at=_now(),
                            last_scan_result="failed",
                            last_error=code,
                            connectivity="failed",
                        )
                        log.warning("knowledge_sync_scan_failed", code=code)
                    self.store.save_config(config)
            except MaintenanceBusy:
                fail("knowledge_maintenance_busy", 409)
            finally:
                self.running = False
            return self.status()
