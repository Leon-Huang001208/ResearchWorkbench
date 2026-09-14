"""Strict, bounded and atomic storage shared by framework-specific snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from core.observability import get_logger

from .base import FrameworkError

log = get_logger(__name__)
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
SnapshotT = TypeVar("SnapshotT", bound=BaseModel)


def compute_revision(value: dict) -> str:
    payload = {key: item for key, item in value.items() if key != "revision"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reject_symlink_components(path: Path) -> None:
    """Reject any existing symlink before resolving or opening a framework path."""

    candidate = path.expanduser()
    current = Path(candidate.anchor) if candidate.is_absolute() else Path.cwd()
    parts = candidate.parts[1:] if candidate.is_absolute() else candidate.parts
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise FrameworkError("框架数据路径不能包含符号链接", "unsafe_framework_path", 503)


class AtomicSnapshotStore(Generic[SnapshotT]):
    """Schema-aware snapshot store; domain stores retain their concrete type."""

    def __init__(
        self,
        root: Path,
        *,
        model: type[SnapshotT],
        seed_factory: Callable[[], SnapshotT],
        schema_version: int,
        framework_label: str,
    ) -> None:
        reject_symlink_components(root)
        self.root = root
        self.path = root / "snapshot.json"
        self.model = model
        self.seed_factory = seed_factory
        self.schema_version = schema_version
        self.framework_label = framework_label
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        reject_symlink_components(self.path)
        if not self.path.exists():
            self.write(seed_factory())
        else:
            self._migrate_legacy_snapshot()

    def _read_json(self) -> dict:
        reject_symlink_components(self.path)
        try:
            if self.path.stat().st_size > MAX_SNAPSHOT_BYTES:
                raise FrameworkError("框架快照超过大小限制", "framework_snapshot_too_large", 503)
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FrameworkError:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            log.error(
                "framework_snapshot_read_failed",
                framework=self.framework_label,
                error_type=type(exc).__name__,
            )
            raise FrameworkError(
                f"{self.framework_label}框架快照不可读", "framework_snapshot_invalid", 503
            ) from exc
        if not isinstance(value, dict):
            raise FrameworkError(
                f"{self.framework_label}框架快照不可读", "framework_snapshot_invalid", 503
            )
        return value

    def _migrate_legacy_snapshot(self) -> None:
        value = self._read_json()
        if value.get("schema_version") == self.schema_version:
            return
        old_version = value.get("schema_version")
        suffix = f"v{old_version}" if isinstance(old_version, int) else "v0"
        backup = self.root / f"snapshot.legacy-{suffix}.json"
        reject_symlink_components(backup)
        if backup.exists():
            raise FrameworkError("旧框架快照备份已存在", "framework_legacy_backup_exists", 503)
        try:
            os.replace(self.path, backup)
            self.write(self.seed_factory())
            log.info(
                "framework_snapshot_legacy_migrated",
                framework=self.framework_label,
                from_version=old_version,
                to_version=self.schema_version,
                backup_name=backup.name,
            )
        except FrameworkError:
            if not self.path.exists() and backup.exists():
                os.replace(backup, self.path)
            raise
        except OSError as exc:
            if not self.path.exists() and backup.exists():
                os.replace(backup, self.path)
            log.error(
                "framework_snapshot_migration_failed",
                framework=self.framework_label,
                error_type=type(exc).__name__,
            )
            raise FrameworkError(
                f"旧{self.framework_label}框架快照迁移失败",
                "framework_snapshot_migration_failed",
                503,
            ) from exc

    def read(self) -> SnapshotT:
        try:
            snapshot = self.model.model_validate(self._read_json())
            if snapshot.revision != compute_revision(snapshot.model_dump(mode="json")):
                raise FrameworkError("框架快照版本校验失败", "framework_snapshot_invalid", 503)
            return snapshot
        except FrameworkError:
            raise
        except (ValidationError, TypeError, ValueError) as exc:
            log.error(
                "framework_snapshot_validation_failed",
                framework=self.framework_label,
                error_type=type(exc).__name__,
            )
            raise FrameworkError(
                f"{self.framework_label}框架快照不可读", "framework_snapshot_invalid", 503
            ) from exc

    def write(self, snapshot: SnapshotT) -> SnapshotT:
        reject_symlink_components(self.path)
        value = snapshot.model_dump(mode="json")
        value["revision"] = compute_revision(value)
        validated = self.model.model_validate(value)
        payload = json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        if len(payload.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise FrameworkError("框架快照超过大小限制", "framework_snapshot_too_large", 503)
        descriptor, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=self.root)
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return validated
        except OSError as exc:
            log.error(
                "framework_snapshot_write_failed",
                framework=self.framework_label,
                error_type=type(exc).__name__,
            )
            raise FrameworkError(
                f"{self.framework_label}框架快照写入失败",
                "framework_snapshot_write_failed",
                503,
            ) from exc
        finally:
            Path(temporary).unlink(missing_ok=True)
