"""Bounded, strict and atomic local storage for the Goldar snapshot."""

import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from core.observability import get_logger

from ..base import FrameworkError
from .contracts import GoldSnapshot
from .seed import build_seed, compute_revision

log = get_logger(__name__)
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
LEGACY_BACKUP_NAME = "snapshot.legacy-v0.json"


class GoldSnapshotStore:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "snapshot.json"
        if root.is_symlink():
            raise FrameworkError("框架数据目录不能是符号链接", "unsafe_framework_path", 503)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            self.write(build_seed())
        else:
            self._migrate_legacy_snapshot()

    def _migrate_legacy_snapshot(self) -> None:
        """Preserve the old UI-shaped fixture before installing the v1 contract."""
        if self.path.is_symlink():
            raise FrameworkError("框架快照不能是符号链接", "unsafe_framework_path", 503)
        try:
            if self.path.stat().st_size > MAX_SNAPSHOT_BYTES:
                raise FrameworkError("框架快照超过大小限制", "framework_snapshot_too_large", 503)
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FrameworkError:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            log.error("gold_snapshot_migration_read_failed", error_type=type(exc).__name__)
            raise FrameworkError("黄金框架快照不可读", "framework_snapshot_invalid", 503) from exc

        if isinstance(value, dict) and value.get("schema_version") == 1:
            return
        if not isinstance(value, dict) or not {
            "market_context",
            "research_state",
            "pricing_drivers",
        }.issubset(value):
            return

        backup = self.root / LEGACY_BACKUP_NAME
        if backup.exists() or backup.is_symlink():
            raise FrameworkError("旧框架快照备份已存在", "framework_legacy_backup_exists", 503)
        try:
            os.replace(self.path, backup)
            self.write(build_seed())
            log.info("gold_snapshot_legacy_migrated", backup_name=LEGACY_BACKUP_NAME)
        except FrameworkError:
            if not self.path.exists() and backup.exists():
                os.replace(backup, self.path)
            raise
        except OSError as exc:
            if not self.path.exists() and backup.exists():
                os.replace(backup, self.path)
            log.error("gold_snapshot_migration_failed", error_type=type(exc).__name__)
            raise FrameworkError(
                "旧黄金框架快照迁移失败", "framework_snapshot_migration_failed", 503
            ) from exc

    def read(self) -> GoldSnapshot:
        if self.path.is_symlink():
            raise FrameworkError("框架快照不能是符号链接", "unsafe_framework_path", 503)
        try:
            if self.path.stat().st_size > MAX_SNAPSHOT_BYTES:
                raise FrameworkError("框架快照超过大小限制", "framework_snapshot_too_large", 503)
            value = json.loads(self.path.read_text(encoding="utf-8"))
            snapshot = GoldSnapshot.model_validate(value)
            if snapshot.revision != compute_revision(snapshot.model_dump(mode="json")):
                raise FrameworkError("框架快照版本校验失败", "framework_snapshot_invalid", 503)
            return snapshot
        except FrameworkError:
            raise
        except (OSError, json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            log.error("gold_snapshot_read_failed", error_type=type(exc).__name__)
            raise FrameworkError("黄金框架快照不可读", "framework_snapshot_invalid", 503) from exc

    def write(self, snapshot: GoldSnapshot) -> None:
        if self.path.is_symlink():
            raise FrameworkError("框架快照不能是符号链接", "unsafe_framework_path", 503)
        value = snapshot.model_dump(mode="json")
        value["revision"] = compute_revision(value)
        validated = GoldSnapshot.model_validate(value)
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
        except OSError as exc:
            log.error("gold_snapshot_write_failed", error_type=type(exc).__name__)
            raise FrameworkError(
                "黄金框架快照写入失败", "framework_snapshot_write_failed", 503
            ) from exc
        finally:
            Path(temporary).unlink(missing_ok=True)
