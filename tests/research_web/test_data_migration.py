import json
import stat
from pathlib import Path

import pytest

from app.research_web.data_migration import (
    DataMigrationError,
    archive_source,
    migrate_data,
)


def _seed_legacy_data(root: Path) -> None:
    files = {
        "index.json": b'{"sessions": []}',
        "sessions/s-1/inputs/report.pdf": b"pdf",
        "sessions/s-1/outputs/report.xlsx": b"xlsx",
        "sessions/s-1/resources/dataset.json": b"[]",
        "capabilities/catalog.json": b"{}",
        "capabilities/versions/fund/v1/SKILL.md": b"# fund",
        ".control/calls/s-1/call.json": b"{}",
        ".control/snapshots/s-1/snapshot.json": b"{}",
        "runtime/home/storages/workspace.json": b"{}",
        "runtime/home/storages/session_projcache.json": b"{}",
        "runtime/home/sessions/native-session.json": b"{}",
        "runtime/home/.credentials.yaml": b"secret: must-not-copy",
        "runtime/home/settings.yaml": b"credentialRef: old-key",
        ".control/datahub.json": b'{"token": "must-not-copy"}',
        "runtime/overlay.yml": b"absolute: old-path",
        "runtime/tmp/cache": b"temporary",
        "logs/sandbox.log": b"private log",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_migration_preserves_research_state_and_excludes_credentials(tmp_path: Path):
    source = tmp_path / "legacy"
    target = tmp_path / "new" / "research-web"
    _seed_legacy_data(source)

    result = migrate_data(source, target)

    assert result["status"] == "migrated"
    assert (target / "sessions/s-1/inputs/report.pdf").read_bytes() == b"pdf"
    assert (target / "sessions/s-1/outputs/report.xlsx").read_bytes() == b"xlsx"
    assert (target / "runtime/home/sessions/native-session.json").exists()
    assert not (target / "runtime/home/.credentials.yaml").exists()
    assert not (target / ".control/datahub.json").exists()
    assert not (target / "runtime/overlay.yml").exists()
    manifest = json.loads((target / "migration-manifest.json").read_text())
    assert manifest["file_count"] == result["file_count"]
    assert manifest["content_sha256"] == result["content_sha256"]


def test_migration_dry_run_is_read_only(tmp_path: Path):
    source = tmp_path / "legacy"
    target = tmp_path / "target"
    _seed_legacy_data(source)
    result = migrate_data(source, target, dry_run=True)
    assert result["status"] == "dry_run"
    assert result["file_count"] > 0
    assert not target.exists()


def test_migration_is_idempotent_when_manifest_matches(tmp_path: Path):
    source = tmp_path / "legacy"
    target = tmp_path / "target"
    _seed_legacy_data(source)
    migrate_data(source, target)
    result = migrate_data(source, target)
    assert result["status"] == "already_migrated"


def test_migration_rejects_symlink_inside_allowed_tree(tmp_path: Path):
    source = tmp_path / "legacy"
    target = tmp_path / "target"
    _seed_legacy_data(source)
    (source / "sessions/s-1/inputs/link").symlink_to(source / "index.json")
    with pytest.raises(DataMigrationError, match="符号链接"):
        migrate_data(source, target)


def test_migration_refuses_unverified_existing_target(tmp_path: Path):
    source = tmp_path / "legacy"
    target = tmp_path / "target"
    _seed_legacy_data(source)
    target.mkdir()
    (target / "unknown").write_text("do not overwrite")
    with pytest.raises(DataMigrationError, match="没有可验证"):
        migrate_data(source, target)


def test_archive_source_moves_and_makes_backup_read_only(tmp_path: Path):
    source = tmp_path / "legacy"
    _seed_legacy_data(source)
    archived = archive_source(source)
    assert not source.exists()
    assert archived.is_dir()
    assert stat.S_IMODE(archived.stat().st_mode) == 0o500
    assert stat.S_IMODE((archived / "index.json").stat().st_mode) == 0o400
