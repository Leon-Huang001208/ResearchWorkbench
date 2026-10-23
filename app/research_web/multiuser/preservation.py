"""Content-only preservation proofs; never read a model credential value."""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

from core.observability import get_logger

log = get_logger(__name__)


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def snapshot(root: Path) -> dict:
    """Hash existing session bytes and non-secret model settings under admission."""
    try:
        if root.resolve() != root.absolute() or root.is_symlink():
            raise ValueError("preservation_root_unsafe")
        index_path = root / "index.json"
        if not stat.S_ISREG(index_path.lstat().st_mode):
            raise ValueError("preservation_index_unsafe")
        index = json.loads(index_path.read_text())
        if not isinstance(index, dict) or not isinstance(index.get("sessions"), dict):
            raise TypeError("preservation_index_invalid")
        files = {}
        from ..dossier_preservation import snapshot_dossiers

        dossiers = snapshot_dossiers(root)
        if dossiers is not None:
            files.update(dossiers["files"])
        folders = [root / "sessions", root / "runtime/home/sessions"]
        if dossiers is not None:
            # Pinned public material and its private originals form one proof.
            folders.extend([root / ".control/snapshots", root / ".control/calls"])
        for folder in folders:
            present = True
            ancestor = root
            for part in folder.relative_to(root).parts:
                ancestor = ancestor / part
                try:
                    info = ancestor.lstat()
                except FileNotFoundError:
                    present = False
                    break
                if not stat.S_ISDIR(info.st_mode):
                    raise ValueError("preservation_scan_root_unsafe")
            if not present:
                continue
            for path in folder.rglob("*"):
                relative = path.relative_to(root)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("preservation_link_unknown")
                if stat.S_ISDIR(info.st_mode):
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("preservation_file_unknown")
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                files[str(relative)] = digest.hexdigest()
        models = {k: v for k, v in index.items() if k.startswith(("model", "compatible_model"))}
        return {
            "sessions": {k: _digest(v) for k, v in index["sessions"].items()},
            "models_hash": _digest(models),
            "files": files,
        }
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        log.error("multiuser_preservation_snapshot_failed", error_type=type(exc).__name__)
        raise RuntimeError("preservation_snapshot_failed") from exc


def compare_snapshot(before: dict, after: dict) -> dict:
    """New verification sessions are allowed; every original object must remain."""
    changed_files = [p for p, digest in before["files"].items() if after["files"].get(p) != digest]
    changed_sessions = [
        sid for sid, digest in before["sessions"].items() if after["sessions"].get(sid) != digest
    ]
    model_preserved = before["models_hash"] == after["models_hash"]
    return {
        "preserved": not changed_files and not changed_sessions and model_preserved,
        "original_sessions": len(before["sessions"]),
        "original_files": len(before["files"]),
        "changed_file_count": len(changed_files),
        "changed_session_count": len(changed_sessions),
        "model_settings_preserved": model_preserved,
    }
