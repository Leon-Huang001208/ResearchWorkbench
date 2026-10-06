"""Validate the derived Docker asset inventory; Native checkouts stay unchanged."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
from pathlib import Path

from . import RUNTIME_CONTRACT

log = logging.getLogger(__name__)
MANIFEST = ".rwb-dsh-runtime.json"
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_ASSETS = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024
REQUIRED_ASSETS = (
    "apps/cli/lib/bin.js",
    "apps/cli/package.json",
    "packages/boot/app-boot/lib/index.js",
)


def _read_regular(path: Path, limit: int) -> bytes:
    # Traverse parents without following aliases; a raced directory replacement
    # must not turn a bounded image read into a read outside the image tree.
    folder = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=folder)
            os.close(folder)
            folder = following
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    finally:
        os.close(folder)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError("unsafe file")
        result = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(result) > limit or (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise ValueError("changed file")
        return result


def _source_facts(value: object) -> dict:
    expected = {
        "commit": RUNTIME_CONTRACT.dsh_commit,
        "remote": RUNTIME_CONTRACT.dsh_remote,
        "pnpm": RUNTIME_CONTRACT.dsh_pnpm,
        "closure_files": RUNTIME_CONTRACT.dsh_closure_files,
    }
    if (
        not isinstance(value, dict)
        or set(value) != {*expected, "closure_sha256"}
        or any(value.get(key) != item for key, item in expected.items())
        or type(value.get("closure_files")) is not int
        or re.fullmatch(r"[a-f0-9]{64}", str(value.get("closure_sha256"))) is None
    ):
        raise ValueError("source facts mismatch")
    return value


def _inventory(root: Path) -> list[dict]:
    if root.absolute() != root.resolve(strict=True) or not root.is_dir():
        raise ValueError("unsafe root")
    entries = []
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in sorted(folders + files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == MANIFEST:
                continue
            metadata = path.lstat()
            entry = {"path": relative}
            if len(relative) > 1024 or len(entries) >= MAX_ASSETS:
                raise ValueError("inventory limit")
            if stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(path)
                if Path(target).is_absolute() or not path.resolve(strict=True).is_relative_to(root):
                    raise ValueError("unsafe link")
                entry.update(type="symlink", target=target)
            elif stat.S_ISDIR(metadata.st_mode):
                entry.update(type="directory")
            elif stat.S_ISREG(metadata.st_mode):
                content = _read_regular(path, MAX_FILE_BYTES)
                entry.update(
                    type="file", size=len(content), mode=stat.S_IMODE(metadata.st_mode),
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            else:
                raise ValueError("unsupported asset")
            entries.append(entry)
    for relative in REQUIRED_ASSETS:
        if not any(item["path"] == relative and item["type"] == "file" for item in entries):
            raise ValueError("required asset missing")
    return sorted(entries, key=lambda item: item["path"])


def _digest(entries: list[dict]) -> str:
    serialized = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def write_staged_manifest(root: Path, verified_source: dict) -> None:
    """Build-only publication after the complete checkout verifier has passed."""
    try:
        facts = _source_facts(verified_source)
        entries = _inventory(root)
        payload = json.dumps({
            "schema_version": 1, "source": facts, "assets": entries,
            "asset_count": len(entries), "assets_sha256": _digest(entries),
        }, sort_keys=True, separators=(",", ":")).encode()
        if len(payload) > MAX_MANIFEST_BYTES:
            raise ValueError("manifest limit")
        with (root / MANIFEST).open("xb") as stream:
            stream.write(payload)
        log.info("staged_runtime_manifest_written assets=%d", len(entries))
    except (OSError, ValueError, RuntimeError) as exc:
        log.error("staged_runtime_manifest_failed error_type=%s", type(exc).__name__)
        raise RuntimeError("staged_runtime_invalid") from exc


def verify_staged_runtime(root: Path, *, required: bool = False) -> dict | None:
    """Fail closed on image assets; return None only for an ordinary Native tree."""
    marker = root / MANIFEST
    if not os.path.lexists(marker) and not required:
        return None
    try:
        if root.absolute() != root.resolve(strict=True):
            raise ValueError("unsafe root")
        value = json.loads(
            _read_regular(marker, MAX_MANIFEST_BYTES), object_pairs_hook=_unique_object
        )
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "source", "assets", "asset_count", "assets_sha256"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or type(value["asset_count"]) is not int
            or not 0 < value["asset_count"] <= MAX_ASSETS
            or not isinstance(value["assets"], list)
            or len(value["assets"]) != value["asset_count"]
        ):
            raise ValueError("invalid manifest")
        facts = _source_facts(value["source"])
        entries = _inventory(root)
        if entries != value["assets"] or _digest(entries) != value["assets_sha256"]:
            raise ValueError("asset mismatch")
        log.info("staged_runtime_verified assets=%d", len(entries))
        return facts
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, RecursionError) as exc:
        log.error("staged_runtime_verification_failed error_type=%s", type(exc).__name__)
        raise RuntimeError("staged_runtime_invalid") from exc
