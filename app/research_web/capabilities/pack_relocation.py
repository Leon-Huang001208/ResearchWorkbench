"""Narrow builtin relocation eligibility; no dependency or code upgrade policy."""

from __future__ import annotations

import copy
import hashlib
import json
import stat
from pathlib import Path

from core.observability import get_logger

from .models import CapabilityError
from .pack_native import read_regular
from .pack_resources import MANIFEST_PATH, PACK_NAMES, verify_pack_manifest
from .packages import decode_file

log = get_logger(__name__)
PACK_IDS = frozenset("research-pack-" + pack for pack in PACK_NAMES)
RUNTIME_PATH = "references/runtime.json"
CONTENT_FIELDS = (
    "metadata",
    "instructions",
    "steps",
    "method_spec",
    "reviewed_scripts",
    "import_issues",
    "file_issues",
)


def runtime_from(record):
    return json.loads(
        decode_file(next(file for file in record["files"] if file["path"] == RUNTIME_PATH))
    )


def _static_files(record):
    return {
        file["path"]: decode_file(file)
        for file in record["files"]
        if file["path"] not in {RUNTIME_PATH, MANIFEST_PATH}
    }


def _relative(path, root):
    path, root = Path(path), Path(root)
    if not path.is_absolute() or not root.is_absolute() or ".." in path.parts or ".." in root.parts:
        raise ValueError("noncanonical runtime prefix")
    return path.relative_to(root).as_posix()


def relocation_decision(row, active, curated):
    """Return an explicit reason; metadata and every reviewed byte must match."""
    try:
        if (
            row.get("id") not in PACK_IDS
            or row.get("source") != "builtin"
            or row.get("kind") != "skill"
            or row.get("origin") is not None
        ):
            return False, "pack_runtime_source_untrusted"
        if row.get("has_draft") or row.get("status") not in {"enabled", "disabled"}:
            return False, "pack_runtime_draft_conflict"
        if (
            any(
                active.get(key) != curated.get(key) or row["draft"].get(key) != curated.get(key)
                for key in CONTENT_FIELDS
            )
            or active.get("bindings") != []
        ):
            return False, "pack_runtime_content_changed"
        old_manifest, new_manifest = verify_pack_manifest(active["files"]), verify_pack_manifest(
            curated["files"]
        )
        if (
            old_manifest is None
            or new_manifest is None
            or {
                key: value
                for key, value in old_manifest.items()
                if key not in {"files", "closure_sha256"}
            }
            != {
                key: value
                for key, value in new_manifest.items()
                if key not in {"files", "closure_sha256"}
            }
        ):
            return False, "pack_runtime_manifest_changed"
        if _static_files(active) != _static_files(curated) or {
            file["path"]: decode_file(file) for file in row["draft"]["files"]
        } != {file["path"]: decode_file(file) for file in active["files"]}:
            return False, "pack_runtime_content_changed"
        old, new = runtime_from(active), runtime_from(curated)
        if old == new:
            return False, "current"
        if (
            set(old) != set(new)
            or old.get("schema") != "research_pack_runtime_v2"
            or old.get("entry_policy") != "managed_python_module_no_console_v1"
        ):
            return False, "pack_runtime_policy_changed"
        old_normal, new_normal = copy.deepcopy(old), copy.deepcopy(new)
        previous, target = old_normal.pop("environment"), new_normal.pop("environment")
        if not Path(previous).is_absolute() or not Path(target).is_absolute() or previous == target:
            return False, "pack_runtime_not_prefix_relocation"
        old_python, new_python = old_normal.pop("python"), new_normal.pop("python")
        if old_python != new_python and _relative(old_python, previous) != _relative(
            new_python, target
        ):
            return False, "pack_runtime_interpreter_changed"
        for key in (
            "python_sha256",
            "python_version",
            "python_abi",
            "implementation",
            "platform",
            "machine",
        ):
            if old_normal.get(key) != new_normal.get(key):
                return False, "pack_runtime_interpreter_changed"
        if len(old_normal["dependencies"]) != 6 or len(new_normal["dependencies"]) != 6:
            return False, "pack_runtime_dependency_changed"
        for left, right in zip(old_normal["dependencies"], new_normal["dependencies"], strict=True):
            old_origin, new_origin = left.pop("origin"), right.pop("origin")
            if _relative(old_origin, previous) != _relative(new_origin, target) or left != right:
                return False, "pack_runtime_dependency_changed"
        if old_normal != new_normal:
            return False, "pack_runtime_policy_changed"
        return True, "relocation"
    except (CapabilityError, OSError, ValueError, KeyError, TypeError, StopIteration):
        log.warning("research_pack_relocation_unverified")
        return False, "pack_runtime_manifest_invalid"


def verify_version_tree(catalog, row, active):
    """No healing of modified/unlisted files or native projections during migration."""
    version = row["version"]
    if type(version) is not int or version < 1 or active["native_name"] != row["id"]:
        raise ValueError("pack version identity invalid")
    _name, compiled = catalog._compile(row, version)
    expected = {
        "SKILL.md": hashlib.sha256(compiled.encode()).hexdigest(),
        **{file["path"]: file["sha256"] for file in active["files"]},
    }
    if expected["SKILL.md"] != active["compiled_sha256"]:
        raise ValueError("pack compilation changed")
    expected_directories = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent != Path(".")
    }

    def check_tree(root):
        paths = list(root.rglob("*"))
        if (
            any(
                path.is_symlink() or not path.is_dir() and not stat.S_ISREG(path.lstat().st_mode)
                for path in paths
            )
            or {path.relative_to(root).as_posix() for path in paths if path.is_file()}
            != set(expected)
            or {path.relative_to(root).as_posix() for path in paths if path.is_dir()}
            != expected_directories
        ):
            raise ValueError("pack resource set changed")
        for name, digest in expected.items():
            if hashlib.sha256(read_regular(root / name, 10 * 1024 * 1024)).hexdigest() != digest:
                raise ValueError("pack resource bytes changed")

    check_tree(catalog.version_path(row["id"], version))
    if row["status"] == "enabled":
        check_tree(catalog.native_root / active["native_name"])
