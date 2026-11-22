"""Frozen stdlib-only writer around one approved pure calculation.

Called only by the Host-generated launcher. Returned descriptors are claims until
the Host independently reopens the files and binds the real Native completion.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
from pathlib import Path

log = logging.getLogger(__name__)
MAX_INPUT = 64 * 1024 * 1024
MAX_FULL = 16 * 1024 * 1024


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def read_regular(path, limit):
    """Reject links, aliases and concurrent file replacement before/after read."""
    path = Path(path)
    if path.resolve(strict=True) != path or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("pack_file_unsafe")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
        raise ValueError("pack_file_unsafe")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    if (
        identity(before) != identity(opened)
        or identity(opened) != identity(after)
        or identity(after) != identity(path.lstat())
        or len(raw) > limit
    ):
        raise ValueError("pack_file_changed")
    return raw


def write_new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if read_regular(path, len(raw)) != raw:
        raise ValueError("pack_output_readback_failed")


def run(input_path, output_path, binding, *, calculator=None):
    """Write complete, receipt and manifest once, then atomically publish v1."""
    try:
        raw = read_regular(Path(input_path), MAX_INPUT)
        if hashlib.sha256(raw).hexdigest() != binding.get("input_sha256"):
            raise ValueError("input_hash_mismatch")
        value = json.loads(raw)
        if (
            set(value) != {"schema", "pack_id", "records_by_kind", "parameters", "source_coverage"}
            or value["schema"] != "research_pack_input_v1"
            or value["pack_id"] != binding["pack_id"]
        ):
            raise ValueError("pack_input_invalid")
        target = Path(output_path)
        if target.exists() or target.is_symlink():
            raise ValueError("output_exists")
        if target.parts[-4:] != ("outputs", "scenario-results", binding["execution_id"], "v1"):
            raise ValueError("pack_output_identity_mismatch")
        parent = target.parent
        if parent.resolve(strict=True) != parent or any(
            p.is_symlink() for p in (parent, *parent.parents)
        ):
            raise ValueError("pack_output_unsafe")
        stage = parent / (target.name + "-staging")
        stage.mkdir(mode=0o700)
        if calculator is None:
            from rwb_pack_core import execute_pack_bundle

            calculator = execute_pack_bundle
        bundle = calculator(
            value["pack_id"],
            value["records_by_kind"],
            value["parameters"],
            source_coverage=value["source_coverage"],
        )
        full_raw = bundle.full_result.canonical_json
        receipt_raw = canonical(bundle.receipt)
        if len(full_raw) > MAX_FULL or len(receipt_raw) > 65536:
            raise ValueError("pack_output_limit")
        files = {"full-result": full_raw, "receipt": receipt_raw}
        artifacts = {}
        for name, content in files.items():
            write_new(stage / (name + ".json"), content)
            artifacts[name] = {
                "file": name + ".json",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        manifest = {
            "schema": "research_pack_artifact_manifest_v1",
            "binding": binding,
            "status": bundle.receipt["status"],
            "artifacts": artifacts,
            "counts": {
                "root": bundle.full_result.root_row_count,
                "components": dict(bundle.full_result.component_row_counts),
            },
        }
        manifest_raw = canonical(manifest)
        if len(manifest_raw) > 65536:
            raise ValueError("pack_manifest_limit")
        write_new(stage / "manifest.json", manifest_raw)
        artifacts = {
            **artifacts,
            "manifest": {
                "file": "manifest.json",
                "sha256": hashlib.sha256(manifest_raw).hexdigest(),
                "bytes": len(manifest_raw),
            },
        }
        envelope = {
            "schema": "research_pack_execution_envelope_v1",
            "execution_id": binding["execution_id"],
            "status": bundle.receipt["status"],
            "artifacts": {
                name: {
                    **item,
                    "path": "outputs/scenario-results/"
                    + binding["execution_id"]
                    + "/v1/"
                    + name
                    + ".json",
                }
                for name, item in artifacts.items()
            },
            "counts": manifest["counts"],
            "research_quality": "NOT_RUN",
        }
        if len(canonical(envelope)) > 65536:
            raise ValueError("pack_envelope_limit")
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if target.exists() or target.is_symlink():
            raise ValueError("output_exists")
        stage.rename(target)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        log.info(
            "research_pack_artifacts_saved execution_id=%s bytes=%d",
            binding["execution_id"],
            len(full_raw),
        )
        return envelope
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.error("research_pack_write_failed error_type=%s", type(exc).__name__)
        raise
