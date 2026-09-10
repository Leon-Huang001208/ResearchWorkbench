"""Atomic local registry catalog and query-keyed cache."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from core.observability import get_logger

from .models import REGISTRY_ID_PATTERN

log = get_logger(__name__)
OFFICIAL_REGISTRY_ID = "official"
OFFICIAL_REGISTRY_URL = "https://registry.modelcontextprotocol.io"
MAX_CATALOG_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_STATUS_BYTES = 1024 * 1024


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class CatalogError(RuntimeError):
    """Stable local catalog failure."""


class RegistryCatalog:
    def __init__(self, data_root: Path) -> None:
        self.root = Path(data_root) / "mcp-registry"
        self.cache_root = self.root / "cache"
        self.status_root = self.root / "status"
        self._lock = RLock()
        for directory in (self.root, self.cache_root, self.status_root):
            if directory.is_symlink():
                raise CatalogError("unsafe_registry_directory")
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "catalog.json"
        self.data = self._load_catalog()
        if OFFICIAL_REGISTRY_ID not in self.data["registries"]:
            now = timestamp()
            self.data["registries"][OFFICIAL_REGISTRY_ID] = {
                "id": OFFICIAL_REGISTRY_ID,
                "name": "Official MCP Registry",
                "base_url": OFFICIAL_REGISTRY_URL,
                "official": True,
                "immutable": True,
                "auth": {"type": "none"},
                "created_at": now,
                "updated_at": now,
            }
            self.save()

    def _load_catalog(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "registries": {}}
        try:
            if self.path.is_symlink() or self.path.stat().st_size > MAX_CATALOG_BYTES:
                raise ValueError("unsafe catalog")
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or value.get("schema_version") != 1
                or not isinstance(value.get("registries"), dict)
            ):
                raise ValueError("invalid catalog")
            return value
        except (OSError, ValueError) as exc:
            log.error("mcp_registry_catalog_read_failed", error_type=type(exc).__name__)
            raise CatalogError("registry_catalog_unavailable") from exc

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any], maximum: int) -> None:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > maximum:
            raise CatalogError("registry_cache_too_large")
        fd: int | None = None
        temporary: Path | None = None
        try:
            fd, name = tempfile.mkstemp(prefix=f".{path.stem}-", dir=path.parent)
            temporary = Path(name)
            os.chmod(temporary, 0o600)
            stream = os.fdopen(fd, "wb")
            fd = None
            with stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError as exc:
                log.warning(
                    "mcp_registry_directory_fsync_failed",
                    path_name=path.name,
                    error_type=type(exc).__name__,
                )
        except OSError as exc:
            log.error(
                "mcp_registry_atomic_write_failed",
                path_name=path.name,
                error_type=type(exc).__name__,
            )
            raise CatalogError("registry_storage_unavailable") from exc
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    log.warning(
                        "mcp_registry_temporary_cleanup_failed",
                        path_name=path.name,
                        error_type=type(exc).__name__,
                    )

    def save(self) -> None:
        with self._lock:
            self._atomic_write(self.path, self.data, MAX_CATALOG_BYTES)

    def rows(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(row) for row in self.data["registries"].values()]

    def row(self, registry_id: str) -> dict[str, Any]:
        import re

        if not isinstance(registry_id, str) or not re.fullmatch(REGISTRY_ID_PATTERN, registry_id):
            raise CatalogError("registry_not_found")
        row = self.data["registries"].get(registry_id)
        if row is None:
            raise CatalogError("registry_not_found")
        return copy.deepcopy(row)

    def create(self, name: str, base_url: str, auth: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            registry_id = f"local-{uuid4().hex}"
            now = timestamp()
            row = {
                "id": registry_id,
                "name": name,
                "base_url": base_url,
                "official": False,
                "immutable": False,
                "auth": copy.deepcopy(auth),
                "created_at": now,
                "updated_at": now,
            }
            self.data["registries"][registry_id] = row
            try:
                self.save()
            except CatalogError:
                self.data["registries"].pop(registry_id, None)
                raise
            return copy.deepcopy(row)

    def update(self, registry_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self.row(registry_id)
            if current["immutable"]:
                raise CatalogError("official_registry_immutable")
            replacement = {**current, **copy.deepcopy(changes), "updated_at": timestamp()}
            self.data["registries"][registry_id] = replacement
            try:
                self.save()
            except CatalogError:
                self.data["registries"][registry_id] = current
                raise
            return copy.deepcopy(replacement)

    def delete(self, registry_id: str) -> None:
        with self._lock:
            current = self.row(registry_id)
            if current["immutable"]:
                raise CatalogError("official_registry_immutable")
            del self.data["registries"][registry_id]
            try:
                self.save()
            except CatalogError:
                self.data["registries"][registry_id] = current
                raise
            for path in (
                self.cache_root / f"{registry_id}.json",
                self.status_root / f"{registry_id}.json",
            ):
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    log.warning(
                        "mcp_registry_cleanup_failed",
                        registry_id=registry_id,
                        path_name=path.name,
                        error_type=type(exc).__name__,
                    )

    def cache_path(self, registry_id: str) -> Path:
        self.row(registry_id)
        return self.cache_root / f"{registry_id}.json"

    @staticmethod
    def query_key(kind: str, **values: Any) -> str:
        raw = json.dumps({"kind": kind, **values}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_cache(self, registry_id: str) -> dict[str, Any]:
        path = self.cache_path(registry_id)
        if not path.exists():
            return {"schema_version": 1, "registry_id": registry_id, "pages": {}, "details": {}}
        try:
            if path.is_symlink() or path.stat().st_size > MAX_CACHE_BYTES:
                raise ValueError("unsafe cache")
            value = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or value.get("schema_version") != 1
                or value.get("registry_id") != registry_id
                or not isinstance(value.get("pages"), dict)
                or not isinstance(value.get("details"), dict)
            ):
                raise ValueError("invalid cache")
            return value
        except (OSError, ValueError) as exc:
            log.warning(
                "mcp_registry_cache_read_failed",
                registry_id=registry_id,
                error_type=type(exc).__name__,
            )
            raise CatalogError("registry_cache_unavailable") from exc

    def cached_page(self, registry_id: str, *, cursor: str | None, search: str | None, limit: int):
        key = self.query_key("page", cursor=cursor, search=search, limit=limit)
        return copy.deepcopy(self._load_cache(registry_id)["pages"].get(key))

    def save_page(
        self,
        registry_id: str,
        *,
        cursor: str | None,
        search: str | None,
        limit: int,
        value: dict[str, Any],
        expected_source_url: str | None = None,
    ) -> None:
        with self._lock:
            if (
                expected_source_url is not None
                and self.row(registry_id)["base_url"] != expected_source_url
            ):
                raise CatalogError("registry_source_changed")
            cache = self._load_cache(registry_id)
            key = self.query_key("page", cursor=cursor, search=search, limit=limit)
            cache["pages"][key] = copy.deepcopy(value)
            self._atomic_write(self.cache_path(registry_id), cache, MAX_CACHE_BYTES)

    def cached_detail(self, registry_id: str, server_name: str, version: str):
        key = self.query_key("detail", server_name=server_name, version=version)
        return copy.deepcopy(self._load_cache(registry_id)["details"].get(key))

    def save_detail(
        self,
        registry_id: str,
        server_name: str,
        version: str,
        value: dict[str, Any],
        *,
        expected_source_url: str | None = None,
    ) -> None:
        with self._lock:
            if (
                expected_source_url is not None
                and self.row(registry_id)["base_url"] != expected_source_url
            ):
                raise CatalogError("registry_source_changed")
            cache = self._load_cache(registry_id)
            key = self.query_key("detail", server_name=server_name, version=version)
            cache["details"][key] = copy.deepcopy(value)
            self._atomic_write(self.cache_path(registry_id), cache, MAX_CACHE_BYTES)

    def status_path(self, registry_id: str) -> Path:
        self.row(registry_id)
        return self.status_root / f"{registry_id}.json"

    def _load_status(self, registry_id: str) -> dict[str, Any]:
        path = self.status_path(registry_id)
        if not path.exists():
            return {"schema_version": 1, "registry_id": registry_id, "pages": {}, "details": {}}
        try:
            if path.is_symlink() or path.stat().st_size > MAX_STATUS_BYTES:
                raise ValueError("unsafe status")
            value = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(value, dict)
                or value.get("schema_version") != 1
                or value.get("registry_id") != registry_id
                or not isinstance(value.get("pages"), dict)
                or not isinstance(value.get("details"), dict)
            ):
                raise ValueError("invalid status")
            return value
        except (OSError, ValueError) as exc:
            log.warning(
                "mcp_registry_status_read_failed",
                registry_id=registry_id,
                error_type=type(exc).__name__,
            )
            raise CatalogError("registry_status_unavailable") from exc

    def sync_status(self, registry_id: str, kind: str, **values: Any) -> dict[str, Any] | None:
        bucket = "pages" if kind == "page" else "details"
        key = self.query_key(kind, **values)
        return copy.deepcopy(self._load_status(registry_id)[bucket].get(key))

    def set_sync_status(
        self,
        registry_id: str,
        kind: str,
        value: dict[str, Any] | None,
        **values: Any,
    ) -> None:
        with self._lock:
            status = self._load_status(registry_id)
            bucket = "pages" if kind == "page" else "details"
            key = self.query_key(kind, **values)
            if value is None:
                if key not in status[bucket]:
                    return
                del status[bucket][key]
            else:
                status[bucket][key] = copy.deepcopy(value)
            self._atomic_write(self.status_path(registry_id), status, MAX_STATUS_BYTES)
