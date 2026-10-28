"""Atomic single-process product ownership index. DSH owns all transcripts."""

import copy
import hashlib
import json
import mimetypes
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path
from threading import RLock
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)
_OPTIONAL_ASSET_DEFAULTS = {
    "asset_history_jobs": {},
    "asset_history_keys": {},
    "chart_preferences": {"panels": ["volume", "macd"], "revision": 0},
}
PUBLIC_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".md",
    ".txt",
    ".csv",
    ".xlsx",
    ".docx",
    ".pptx",
    ".html",
    ".svg",
    ".json",
}


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


class StoreError(Exception):
    def __init__(self, message: str, code: str = "invalid_resource", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class Store:
    def __init__(self, root: Path):
        # Shared by full save and watchlist snapshot/stage/rollback; one Store only.
        self.write_lock = RLock()
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.index = self.root / "index.json"
        try:
            self.data = (
                json.loads(self.index.read_text(encoding="utf-8"))
                if self.index.exists()
                else {"sessions": {}, "receipts": {}}
            )
        except (OSError, ValueError) as exc:
            log.error("research_index_unreadable", error_type=type(exc).__name__)
            raise StoreError("会话索引不可读取；未覆盖原索引") from exc
        self._persisted_asset_keys = _OPTIONAL_ASSET_DEFAULTS.keys() & self.data.keys()
        # Additive local indexes keep earlier Research Web data readable.
        self.data.setdefault("sessions", {})
        self.data.setdefault("receipts", {})
        self.data.setdefault("data_queries", {})
        self.data.setdefault("data_query_keys", {})
        self.data.setdefault("handoffs", {})
        self.data.setdefault("handoff_keys", {})
        self.data.setdefault("operation_audit", [])
        self.data.setdefault("asset_observations", {})
        self.data.setdefault("asset_observation_keys", {})
        for key, value in _OPTIONAL_ASSET_DEFAULTS.items():
            self.data.setdefault(key, copy.deepcopy(value))
        self.data.setdefault("watchlists", {})
        self.data.setdefault("asset_notes", {})
        self.data.setdefault("asset_alerts", {})
        self.data.setdefault("asset_notifications", {})
        self.data.setdefault("report_projects", {})
        self.data.setdefault("report_runs", {})
        self.data.setdefault("report_schedules", {})
        self.data.setdefault("report_migrations", [])
        self.data.setdefault("automations", {})
        self.data.setdefault("automation_runs", {})
        self.data.setdefault("delivery_channels", {})

    def save(self):
        with self.write_lock:
            # Startup may save unrelated services. Keep unused extensions in memory
            # until first use, preserving the old on-disk missing/empty distinction.
            payload = {
                key: value
                for key, value in self.data.items()
                if key not in _OPTIONAL_ASSET_DEFAULTS
                or key in self._persisted_asset_keys
                or value != _OPTIONAL_ASSET_DEFAULTS[key]
                # JSON distinguishes booleans from numeric defaults where Python == does not.
                or json.dumps(value, sort_keys=True)
                != json.dumps(_OPTIONAL_ASSET_DEFAULTS[key], sort_keys=True)
            }
            fd, name = tempfile.mkstemp(prefix="index-", dir=self.root)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.index)
                self._persisted_asset_keys = _OPTIONAL_ASSET_DEFAULTS.keys() & payload.keys()
            except OSError as exc:
                log.error("research_index_write_failed", error_type=type(exc).__name__)
                raise StoreError("会话索引保存失败") from exc
            finally:
                if os.path.exists(name):
                    os.unlink(name)

    def create(self, mode: str, title: str) -> dict:
        sid = str(uuid4())
        row: dict = {
            "id": sid,
            "mode": mode,
            "title": title,
            "workspace_id": "research",
            "status": "idle",
            "model": None,
            "updated_at": time.time(),
            "files": {},
            "created": False,
        }
        self.data["sessions"][sid] = row
        for folder in ("inputs", "outputs"):
            (self.directory(sid) / folder).mkdir(parents=True, mode=0o700)
        self.save()
        log.info("research_session_registered", session_id=sid, mode=mode)
        return row

    def reserve_hot_session(self, sid: str, mode: str, origin: dict) -> dict:
        """Persist the preallocated identity before native creation; never adopt another row."""
        from .datahub.security import directory, make_directory

        if (
            not isinstance(sid, str)
            or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", sid)
            or mode not in {"fingpt", "claw"}
            or not isinstance(origin, dict)
            or set(origin) != {"runId", "instanceId", "manifestHash"}
            or any(
                not isinstance(origin[k], str)
                or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", origin[k])
                for k in ["runId", "instanceId"]
            )
            or not isinstance(origin["manifestHash"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", origin["manifestHash"])
        ):
            raise StoreError("研究交接保留身份非法")
        if sid in self.data["sessions"]:
            row = self.session(sid)
            if row.get("hot_origin") != origin or row["mode"] != mode:
                raise StoreError("目标会话属于其他交接")
        else:
            with directory(self.root, ("sessions",), create=True) as parent:
                if sid in os.listdir(parent):
                    raise StoreError("目标会话目录已存在但没有归属")
            row = {
                "id": sid,
                "mode": mode,
                "title": "热点与事件研究",
                "workspace_id": "research",
                "status": "idle",
                "model": None,
                "updated_at": time.time(),
                "files": {},
                "created": False,
                "purpose": "hot_research",
                "hot_origin": dict(origin),
                "hot_creation_state": "reserved",
            }
            self.data["sessions"][sid] = row
            self.save()
            log.info("hot_session_reserved", session_id=sid)
        # Recovery can finish directory preparation from the durable matching row.
        with directory(self.root, ("sessions", sid), create=True) as parent:
            for name in ["inputs", "outputs"]:
                if name not in os.listdir(parent):
                    make_directory(parent, name)
                with directory(self.root, ("sessions", sid, name)):
                    pass
        return row

    def reserve_discovery_session(self, sid: str, mode: str, origin: dict, title: str) -> dict:
        """Reserve only a caller-preallocated discovery identity before native RPC."""
        from .datahub.security import directory, make_directory

        identity = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"
        if (
            not isinstance(sid, str)
            or not re.fullmatch(identity, sid)
            or mode not in {"fingpt", "claw"}
            or not isinstance(origin, dict)
            or set(origin) != {"handoff_id", "selection_sha256"}
            or not re.fullmatch(identity, str(origin.get("handoff_id", "")))
            or not re.fullmatch(r"[a-f0-9]{64}", str(origin.get("selection_sha256", "")))
            or not isinstance(title, str)
            or not 1 <= len(title) <= 120
        ):
            raise StoreError("今日发现研究身份非法", "discovery_identity_invalid", 409)
        if sid in self.data["sessions"]:
            row = self.session(sid)
            if row.get("discovery_origin") != origin or row["mode"] != mode:
                raise StoreError("目标会话属于其他研究", "discovery_session_foreign", 409)
        else:
            with directory(self.root, ("sessions",), create=True) as parent:
                if sid in os.listdir(parent):
                    raise StoreError("目标会话目录归属未知", "discovery_session_foreign", 409)
            row = {
                "id": sid,
                "mode": mode,
                "title": title,
                "workspace_id": "research",
                "status": "idle",
                "model": None,
                "updated_at": time.time(),
                "files": {},
                "created": False,
                "purpose": "discovery_research",
                "discovery_origin": dict(origin),
                "discovery_creation_state": "reserved",
                "research_depth": "instant",
                "source_scope": ["datahub", "web", "uploads"],
            }
            if mode == "fingpt":
                row["research_mode"] = "quick"
            self.data["sessions"][sid] = row
            try:
                self.save()
            except StoreError:
                self.data["sessions"].pop(sid, None)
                raise
            log.info("discovery_session_reserved", session_id=sid)
        with directory(self.root, ("sessions", sid), create=True) as parent:
            for name in ("inputs", "outputs"):
                if name not in os.listdir(parent):
                    make_directory(parent, name)
                with directory(self.root, ("sessions", sid, name)):
                    pass
        return row

    def audit(self, kind: str, outcome: str, **safe_metadata) -> None:
        """Persist a bounded, content-free operational event."""
        allowed = {
            "session_id",
            "tool",
            "source",
            "capability",
            "duration_ms",
            "rows",
            "failure_code",
            "project_id",
            "report_run_id",
        }
        event = {
            "kind": kind,
            "outcome": outcome,
            "at": time.time(),
            **{key: value for key, value in safe_metadata.items() if key in allowed},
        }
        events = self.data["operation_audit"]
        events.append(event)
        if len(events) > 10000:
            del events[:-10000]
        self.save()

    def session(self, sid: str, *, include_deleted: bool = False) -> dict:
        if not re.fullmatch(r"[a-f0-9-]{36}", sid) or sid not in self.data["sessions"]:
            raise StoreError("研究会话不存在或不属于当前产品")
        row = self.data["sessions"][sid]
        if row.get("deleted_at") is not None and not include_deleted:
            raise StoreError("研究会话已移至已删除", "session_deleted", 410)
        return row

    def soft_delete(self, sid: str) -> dict:
        row = self.session(sid, include_deleted=True)
        if row.get("deleted_at") is None:
            row["deleted_at"] = time.time()
            self.save()
            log.info("research_session_soft_deleted", session_id=sid, mode=row.get("mode"))
        return row

    def restore(self, sid: str) -> dict:
        row = self.session(sid, include_deleted=True)
        if row.get("purge_started_at") is not None:
            raise StoreError(
                "会话永久删除已经开始，不能恢复；可重试完成清理",
                "session_purge_started",
                409,
            )
        if row.get("deleted_at") is not None:
            row.pop("deleted_at", None)
            row.pop("native_deleted_at", None)
            self.save()
            log.info("research_session_restored", session_id=sid, mode=row.get("mode"))
        return row

    def mark_native_deleted(self, sid: str) -> dict:
        row = self.session(sid, include_deleted=True)
        if row.get("deleted_at") is None:
            raise StoreError("会话必须先移至已删除", "session_not_deleted", 409)
        if row.get("native_deleted_at") is None:
            row["native_deleted_at"] = time.time()
            row["purge_started_at"] = time.time()
            self.save()
        return row

    def _remove_owned_tree(self, path: Path) -> None:
        """Remove a service-owned tree without following nested symbolic links."""
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise StoreError("非法会话目录") from exc
        if not relative.parts:
            raise StoreError("非法会话目录")
        if _is_reparse_point(path):
            if path.is_symlink():
                path.unlink()
                return
            raise StoreError("会话目录状态非法", "session_purge_failed", 503)
        if not path.exists():
            return
        if not path.is_dir():
            raise StoreError("会话目录状态非法", "session_purge_failed", 503)

        for current, directories, files in os.walk(path, topdown=True, followlinks=False):
            directory = Path(current)
            directory.chmod(
                directory.stat(follow_symlinks=False).st_mode | stat.S_IWUSR | stat.S_IXUSR
            )
            directories[:] = [
                name for name in directories if not _is_reparse_point(directory / name)
            ]
            for name in files:
                child = directory / name
                if not _is_reparse_point(child):
                    child.chmod(child.stat(follow_symlinks=False).st_mode | stat.S_IWUSR)
        shutil.rmtree(path)

    def purge(self, sid: str) -> None:
        """Permanently remove one deleted Workbench session and its owned records."""
        from .dossiers.lock import retention_lock
        from .dossiers.storage import DossierStore

        with retention_lock(self.root):
            DossierStore(self.root).assert_deletable(sid)
            self._purge_retention_checked(sid)

    def _purge_retention_checked(self, sid: str) -> None:
        """Only called with the shared archive/native-deletion fence held."""
        from .scenario_handoffs import assert_handoff_deletable

        assert_handoff_deletable(self, sid)
        row = self.session(sid, include_deleted=True)
        if row.get("deleted_at") is None:
            raise StoreError("会话必须先移至已删除", "session_not_deleted", 409)
        if row.get("native_deleted_at") is None:
            raise StoreError("DSH 原生日志尚未删除", "native_session_not_deleted", 409)
        if any(
            job.get("session_id") == sid
            and job.get("state") in {"queued", "running", "cancelling", "draining"}
            for job in self.data["asset_history_jobs"].values()
        ):
            raise StoreError("历史任务仍在读取或排空，未删除会话数据", "history_jobs_active", 409)

        chunks = {}
        for job in self.data["asset_history_jobs"].values():
            if job.get("session_id") != sid:
                continue
            for chunk in job.get("chunks", []):
                if not re.fullmatch(
                    r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json", chunk.get("name", "")
                ):
                    raise StoreError(
                        "历史缓存归属无法确认，未清理", "history_cache_ownership_unknown", 409
                    )
                chunks[chunk["name"]] = (chunk, job["observation_id"])
        if chunks:
            from .datahub.security import directory, read_file, unlink_file

            with directory(self.root, (".control", "asset-history", "chunks"), private=True) as fd:
                for name, (chunk, oid) in chunks.items():
                    if name not in os.listdir(fd):
                        continue
                    raw = read_file(fd, name, private=True)
                    try:
                        value = json.loads(raw)
                    except ValueError as exc:
                        raise StoreError(
                            "历史缓存无法读取，未清理", "history_cache_invalid", 409
                        ) from exc
                    if (
                        hashlib.sha256(raw).hexdigest() != chunk.get("sha256")
                        or value.get("session_id") != sid
                        or value.get("observation_id") != oid
                    ):
                        raise StoreError(
                            "历史缓存归属或哈希无法确认，未清理",
                            "history_cache_ownership_unknown",
                            409,
                        )
                for name in chunks:
                    if name in os.listdir(fd):
                        unlink_file(fd, name)
            log.info("asset_history_session_cache_purged", session_id=sid, chunks=len(chunks))

        paths = [
            self.root / "sessions" / sid,
            self.root / ".control" / "snapshots" / sid,
            self.root / ".control" / "calls" / sid,
        ]
        try:
            for path in paths:
                self._remove_owned_tree(path)
        except OSError as exc:
            log.warning(
                "research_session_purge_files_failed",
                session_id=sid,
                error_type=type(exc).__name__,
            )
            raise StoreError(
                "会话文件清理失败，可重试完成永久删除",
                "session_purge_failed",
                503,
            ) from exc

        removed = {
            "data_queries": {
                key
                for key, value in self.data["data_queries"].items()
                if value.get("session_id") == sid
            },
            "handoffs": {
                key
                for key, value in self.data["handoffs"].items()
                if value.get("session_id") == sid
            },
            "asset_observations": {
                key
                for key, value in self.data["asset_observations"].items()
                if value.get("session_id") == sid
            },
            "asset_history_jobs": {
                key
                for key, value in self.data["asset_history_jobs"].items()
                if value.get("session_id") == sid
            },
            "report_runs": {
                key
                for key, value in self.data["report_runs"].items()
                if sid
                in {
                    value.get("session_id"),
                    value.get("research_session_id"),
                    value.get("delivery_session_id"),
                }
            },
        }
        for table, keys in removed.items():
            for key in keys:
                self.data[table].pop(key, None)
        for key, value in list(self.data["data_query_keys"].items()):
            if value in removed["data_queries"]:
                self.data["data_query_keys"].pop(key, None)
        for key, value in list(self.data["handoff_keys"].items()):
            if value in removed["handoffs"]:
                self.data["handoff_keys"].pop(key, None)
        for key, value in list(self.data["asset_observation_keys"].items()):
            if value in removed["asset_observations"]:
                self.data["asset_observation_keys"].pop(key, None)
        for key, value in list(self.data["asset_history_keys"].items()):
            if value in removed["asset_history_jobs"]:
                self.data["asset_history_keys"].pop(key, None)
        for key in list(self.data["receipts"]):
            if key.startswith(f"{sid}:"):
                self.data["receipts"].pop(key, None)
        self.data["operation_audit"] = [
            event for event in self.data["operation_audit"] if event.get("session_id") != sid
        ]
        for project in self.data["report_projects"].values():
            if project.get("latest_run") in removed["report_runs"]:
                project["latest_run"] = None
        self.data["sessions"].pop(sid, None)
        self.save()
        log.info("research_session_purged", session_id=sid, mode=row.get("mode"))

    def directory(self, sid: str) -> Path:
        self.session(sid)
        path = self.root / "sessions" / sid
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise StoreError("非法会话目录")
        return path

    def reserve(self, sid: str, key: str, digest: str, delivery: dict | None = None) -> bool:
        self.session(sid)
        name = f"{sid}:{key}"
        if name in self.data["receipts"]:
            if self.data["receipts"][name]["digest"] != digest:
                raise StoreError("幂等键不能用于不同问题")
            return False
        self.data["receipts"][name] = {"digest": digest, "status": "pending"}
        if delivery is not None:
            self.data["receipts"][name]["delivery"] = delivery
            self.session(sid)["delivery_key"] = key
        self.save()
        return True

    def receipt(self, sid, key, status=None):
        receipt = self.data["receipts"][f"{sid}:{key}"]
        if status:
            receipt["status"] = status
            self.save()
        return receipt

    def files(self, sid: str) -> list[dict]:
        row, root = self.session(sid), self.directory(sid)
        items = []
        changed = False
        for folder in ("inputs", "outputs"):
            base = root / folder
            if base.is_symlink():
                raise StoreError("文件目录不能为符号链接")
            for path in base.rglob("*"):
                relative = path.relative_to(root)
                if (
                    relative.parts[:2] == ("inputs", "datasets")
                    or not path.is_file()
                    or (
                        path.suffix.lower() not in PUBLIC_EXTENSIONS
                        and not (
                            path.suffix.lower() == ".zip"
                            and folder == "outputs"
                            and row.get("purpose") == "capability_creation"
                        )
                    )
                    or any(part.startswith(".") for part in relative.parts)
                    or any(p.is_symlink() for p in (path, *path.parents) if p != self.root)
                    or not path.resolve().is_relative_to(base.resolve())
                ):
                    continue
                fid = hashlib.sha256(str(relative).encode()).hexdigest()[:24]
                if row["files"].get(fid) != str(relative):
                    row["files"][fid] = str(relative)
                    changed = True
                url = f"/api/research/sessions/{sid}/files/{fid}"
                items.append(
                    {
                        "id": fid,
                        "name": path.name,
                        "size": path.stat().st_size,
                        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        "url": url + "/download",
                        "preview_url": url + "/preview",
                        "kind": folder,
                    }
                )
        if changed:
            self.save()
        return items

    def file_path(self, sid: str, fid: str) -> Path:
        row = self.session(sid)
        if fid not in row["files"] or not re.fullmatch(r"[a-f0-9]{24}", fid):
            raise StoreError("文件不存在")
        root = self.directory(sid)
        relative = Path(row["files"][fid])
        if relative.parts[:2] == ("inputs", "datasets"):
            raise StoreError(
                "数据集须通过来源鉴权入口读取", "dataset_file_requires_datahub_authorization", 403
            )
        if relative.is_absolute() or ".." in relative.parts:
            raise StoreError("文件访问被拒绝")
        path = root / relative
        owned_chain = [
            root.joinpath(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)
        ]
        if (
            any(_is_reparse_point(candidate) for candidate in owned_chain)
            or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())
        ):
            raise StoreError("文件访问被拒绝")
        return path

    def open_file(self, sid: str, fid: str):
        """Open beneath directory descriptors so a concurrent symlink swap cannot escape."""
        row = self.session(sid)
        if not re.fullmatch(r"[a-f0-9]{24}", fid) or fid not in row["files"]:
            raise StoreError("文件不存在")
        relative = Path(row["files"][fid])
        if relative.parts[:2] == ("inputs", "datasets"):
            raise StoreError(
                "数据集须通过来源鉴权入口读取", "dataset_file_requires_datahub_authorization", 403
            )
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] not in {"inputs", "outputs"}
        ):
            raise StoreError("文件访问被拒绝")
        if os.name == "nt":
            path = self.file_path(sid, fid)
            try:
                before = path.lstat()
                if (
                    _is_reparse_point(path)
                    or not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                ):
                    raise StoreError("仅允许下载独立普通文件")
                stream = path.open("rb")
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    stream.close()
                    raise StoreError("仅允许下载独立普通文件")
                return stream, relative.name
            except StoreError:
                raise
            except OSError as exc:
                log.warning(
                    "research_windows_download_denied",
                    session_id=sid,
                    error_type=type(exc).__name__,
                )
                raise StoreError("文件访问被拒绝") from exc
        descriptor = None
        try:
            descriptor = os.open(self.directory(sid), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for component in relative.parts[:-1]:
                child = os.open(
                    component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
                )
                os.close(descriptor)
                descriptor = child
            fd = os.open(
                relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
            )
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(fd)
                raise StoreError("仅允许下载独立普通文件")
            return os.fdopen(fd, "rb"), relative.name
        except OSError as exc:
            log.warning("research_download_denied", session_id=sid, error_type=type(exc).__name__)
            raise StoreError("文件访问被拒绝") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
