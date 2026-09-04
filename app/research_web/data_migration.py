"""Copy Research Web user data into the Research Workbench data home safely."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.observability import get_logger

log = get_logger(__name__)

MIGRATION_MANIFEST = "migration-manifest.json"
ALLOWED_FILES = {
    Path("index.json"),
    Path("runtime/home/storages/workspace.json"),
    Path("runtime/home/storages/session_projcache.json"),
}
ALLOWED_TREES = (
    Path("sessions"),
    Path("capabilities"),
    Path(".control/calls"),
    Path(".control/snapshots"),
    Path("runtime/home/sessions"),
)
SENSITIVE_PARTS = {".credentials.yaml", "credentials", "secrets", "tokens"}


class DataMigrationError(RuntimeError):
    """A migration could not be completed without risking user data."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


def _is_allowed(relative: Path) -> bool:
    if relative in ALLOWED_FILES:
        return True
    return any(relative == root or root in relative.parents for root in ALLOWED_TREES)


def _is_sensitive(relative: Path) -> bool:
    return any(part.lower() in SENSITIVE_PARTS for part in relative.parts)


def _candidate_files(root: Path) -> Iterable[tuple[Path, Path]]:
    if not root.is_dir() or root.is_symlink():
        raise DataMigrationError(f"源数据目录不存在或不安全：{root}")
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            if _is_allowed(relative):
                raise DataMigrationError(f"迁移范围包含符号链接：{relative}")
            continue
        if path.is_file() and _is_allowed(relative) and not _is_sensitive(relative):
            yield path, relative


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path) -> tuple[FileRecord, ...]:
    return tuple(
        FileRecord(str(relative), path.stat().st_size, _hash_file(path))
        for path, relative in _candidate_files(root)
    )


def _summary(records: tuple[FileRecord, ...]) -> dict[str, object]:
    canonical = json.dumps(
        [record.__dict__ for record in records],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return {
        "file_count": len(records),
        "total_bytes": sum(record.size for record in records),
        "content_sha256": hashlib.sha256(canonical).hexdigest(),
        "files": [record.__dict__ for record in records],
    }


def _existing_manifest(target: Path) -> dict[str, object] | None:
    path = target / MIGRATION_MANIFEST
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataMigrationError("目标迁移清单无法读取") from exc
    return value if isinstance(value, dict) else None


def migrate_data(source: Path, target: Path, *, dry_run: bool = False) -> dict[str, object]:
    """Copy only user-owned research state, excluding credentials and runtime overlays."""

    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    if source == target or source in target.parents or target in source.parents:
        raise DataMigrationError("源目录与目标目录不能相同或互相包含")
    source_records = build_manifest(source)
    source_summary = _summary(source_records)
    if not source_records:
        raise DataMigrationError("源目录没有可迁移的研究数据")

    existing = _existing_manifest(target) if target.exists() else None
    if existing is not None:
        if existing.get("content_sha256") == source_summary["content_sha256"]:
            return {
                "status": "already_migrated",
                "source": str(source),
                "target": str(target),
                **source_summary,
            }
        raise DataMigrationError("目标目录已存在且迁移摘要不一致")
    if target.exists():
        raise DataMigrationError("目标目录已存在但没有可验证的迁移清单")
    if dry_run:
        return {"status": "dry_run", "source": str(source), "target": str(target), **source_summary}

    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.parent.is_symlink():
        raise DataMigrationError("目标父目录不能是符号链接")
    stage = Path(tempfile.mkdtemp(prefix="research-web-migration-", dir=target.parent))
    try:
        for original, relative in _candidate_files(source):
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(original, destination, follow_symlinks=False)
        copied_records = build_manifest(stage)
        if copied_records != source_records:
            raise DataMigrationError("复制后的文件数量、大小或哈希不一致")
        manifest = {
            "version": 1,
            "migrated_at": datetime.now(UTC).isoformat(),
            "source": str(source),
            "target": str(target),
            "excluded": [
                "runtime/home/.credentials.yaml",
                "runtime/home/settings.yaml",
                "runtime/home/profiles",
                "runtime/overlay.yml",
                "runtime/tmp",
                ".control/datahub.json",
                "logs",
            ],
            **source_summary,
        }
        manifest_path = stage / MIGRATION_MANIFEST
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.chmod(manifest_path, 0o600)
        os.replace(stage, target)
        log.info(
            "research_data_migrated",
            file_count=len(source_records),
            total_bytes=source_summary["total_bytes"],
        )
        return {"status": "migrated", **manifest}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def archive_source(source: Path) -> Path:
    """Move a verified legacy source aside and make the backup read-only."""

    source = source.expanduser().resolve()
    if not source.is_dir() or source.is_symlink():
        raise DataMigrationError("待归档的源目录不存在或不安全")
    suffix = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archived = source.with_name(f"{source.name}.migrated-{suffix}")
    if archived.exists():
        raise DataMigrationError(f"归档目标已存在：{archived}")
    os.replace(source, archived)
    for path in sorted(archived.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        mode = 0o500 if path.is_dir() else 0o400
        os.chmod(path, mode)
    os.chmod(archived, 0o500)
    log.info("research_data_source_archived", archive=str(archived))
    return archived
