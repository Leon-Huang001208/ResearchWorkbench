"""Read-only identity check for the packaged AlphaDesk frontend."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

QA_BUNDLE_FILES = ("qa.js", "qa.css", "THIRD_PARTY_LICENSES.md")
QA_MANIFEST = "build.json"
QA_FRONTEND = "qa_frontend"
QA_ASSET_PATH = Path("ui", "qa-dist")
_SOURCE_SUFFIXES = {".css", ".json", ".md", ".mjs", ".ts", ".tsx", ".txt"}
_MAX_ASSET_BYTES = 8 * 1024 * 1024
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _plain_path(path: Path, expected) -> os.stat_result:
    identity = path.lstat()
    if not expected(identity.st_mode) or getattr(identity, "st_file_attributes", 0) & _REPARSE:
        raise ValueError("qa_unsafe_build_path")
    return identity


def qa_file_digest(path: Path) -> str:
    identity = _plain_path(path, stat.S_ISREG)
    if not 0 < identity.st_size <= _MAX_ASSET_BYTES:
        raise ValueError("qa_build_file_size_invalid")
    with path.open("rb") as stream:
        body = stream.read(_MAX_ASSET_BYTES + 1)
    if len(body) != identity.st_size:
        raise ValueError("qa_build_file_changed")
    return hashlib.sha256(body).hexdigest()


def qa_source_files(source: Path) -> list[Path]:
    _plain_path(source, stat.S_ISDIR)
    files = []
    for root, folders, names in os.walk(source):
        folders[:] = sorted(
            name for name in folders if name != "node_modules" and not name.startswith(".")
        )
        for name in folders:
            _plain_path(Path(root) / name, stat.S_ISDIR)
        files.extend(
            Path(root) / name
            for name in names
            if not name.startswith(".") and Path(name).suffix in _SOURCE_SUFFIXES
        )
    if not all(source / name in files for name in ("package.json", "package-lock.json")):
        raise ValueError("qa_dependency_lock_missing")
    return sorted(files)


def qa_source_digest(source: Path) -> str:
    identity = {
        path.relative_to(source).as_posix(): qa_file_digest(path)
        for path in qa_source_files(source)
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def qa_build_manifest(source: Path, assets: Path) -> dict[str, object]:
    _plain_path(assets, stat.S_ISDIR)
    return {
        "schema_version": 1,
        "source_sha256": qa_source_digest(source),
        "files": {name: qa_file_digest(assets / name) for name in QA_BUNDLE_FILES},
    }


def _valid_build(assets: Path, expected_source: str | None) -> bool:
    try:
        _plain_path(assets.parent, stat.S_ISDIR)
        _plain_path(assets, stat.S_ISDIR)
        if {file.name for file in assets.iterdir()} != {*QA_BUNDLE_FILES, QA_MANIFEST}:
            return False
        marker = assets / QA_MANIFEST
        if _plain_path(marker, stat.S_ISREG).st_size > 1024:
            return False
        proof = json.loads(marker.read_text(encoding="utf-8"))
        return (
            isinstance(proof, dict)
            and proof.get("schema_version") == 1
            and isinstance(proof.get("source_sha256"), str)
            and (expected_source is None or proof["source_sha256"] == expected_source)
            and proof.get("files")
            == {name: qa_file_digest(assets / name) for name in QA_BUNDLE_FILES}
        )
    except (OSError, ValueError):
        return False


def qa_assets_root(app_root: Path) -> Path | None:
    """Find verified local bytes, or a wheel built from the same frontend source."""
    source = app_root / QA_FRONTEND
    try:
        expected_source = qa_source_digest(source)
    except FileNotFoundError:
        if source.is_symlink() or source.exists():
            return None
        expected_source = None
    except (OSError, ValueError):
        return None
    direct = app_root / QA_ASSET_PATH
    if _valid_build(direct, expected_source):
        return direct
    if expected_source is None:
        return None
    try:
        wheel = distribution("research-workbench").locate_file("app/research_web/ui/qa-dist")
    except PackageNotFoundError:
        return None
    wheel_assets = Path(wheel)
    return wheel_assets if _valid_build(wheel_assets, expected_source) else None


def qa_assets_diagnostic(app_root: Path) -> dict[str, object]:
    ready = qa_assets_root(app_root) is not None
    return {
        "status": "assets_ready" if ready else "assets_missing_or_invalid",
        "assets_ready": ready,
        "model_acceptance": "NOT_RUN",
    }
