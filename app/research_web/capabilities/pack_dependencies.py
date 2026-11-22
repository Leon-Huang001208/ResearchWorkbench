"""Bind a frozen pack to the installed, locked schema validator runtime."""

from __future__ import annotations

import csv
import hashlib
import importlib.machinery
import importlib.metadata
import json
import os
import platform
import re
import stat
import sys
import sysconfig
from configparser import ConfigParser
from configparser import Error as ConfigError
from email.parser import BytesParser
from pathlib import Path

from jsonschema import FormatChecker

from core.observability import get_logger

from ..scenarios.packs.format_profile import PROFILE, format_checker, require_local_schema
from ..scenarios.packs.record_contracts import RECORD_SCHEMAS
from .models import CapabilityError
from .pack_import_policy import build_policy, verify_policy

log = get_logger(__name__)
LOCK_PROJECTION = Path(__file__).with_name("pack-runtime-lock.json")
DEPENDENCIES = (
    "jsonschema",
    "jsonschema-specifications",
    "attrs",
    "referencing",
    "rpds-py",
    "typing-extensions",
    "idna",
)
PACKAGE_ROOTS = {
    "jsonschema": ("jsonschema",),
    "jsonschema-specifications": ("jsonschema_specifications",),
    "attrs": ("attr", "attrs"),
    "referencing": ("referencing",),
    "rpds-py": ("rpds",),
    "typing-extensions": ("typing_extensions.py",),
    "idna": ("idna",),
}
INSTALLATION_BOOKKEEPING = {"RECORD", "INSTALLER", "direct_url.json", "REQUESTED"}


def _read_dependency(path):
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or path.is_symlink()
        or path.resolve(strict=True) != path
        or before.st_size > 32 * 1024 * 1024
    ):
        raise ValueError("unsafe dependency file")
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(32 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    identity = lambda info: (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_nlink,
    )
    if (
        identity(before) != identity(opened)
        or identity(opened) != identity(after)
        or identity(after) != identity(path.lstat())
        or len(raw) != before.st_size
    ):
        raise ValueError("dependency file changed")
    return raw


def _dependency_identity(name, version, environment):
    """Independently enumerate the complete managed import/data roots, including pyc.

    Rebuilt bytecode may block an otherwise harmless relocation. Never ignore it
    to claim a stronger compatibility result than the actual bytes establish.
    """
    dist = importlib.metadata.distribution(name)
    base = Path(dist.locate_file("")).resolve(strict=True)
    metadata_root = Path(dist._path)
    if not base.is_relative_to(environment) or metadata_root.is_symlink():
        raise ValueError("dependency origin outside managed environment")
    metadata_root = metadata_root.resolve(strict=True)
    if metadata_root.parent != base or not metadata_root.name.endswith(".dist-info"):
        raise ValueError("dependency metadata origin invalid")
    meta = BytesParser().parsebytes(_read_dependency(metadata_root / "METADATA"))
    normalized_name = lambda value: re.sub(r"[-_.]+", "-", value).lower()
    if (
        normalized_name(meta.get("Name", "")) != normalized_name(name)
        or meta.get("Version") != version
        or not (metadata_root / "WHEEL").is_file()
    ):
        raise ValueError("dependency metadata not at locked identity")
    console_names = set()
    entry_points = metadata_root / "entry_points.txt"
    if entry_points.exists():
        config = ConfigParser(interpolation=None)
        config.read_string(_read_dependency(entry_points).decode("utf-8"))
        if config.has_section("console_scripts"):
            console_names = set(config["console_scripts"])
    roots = [base / relative for relative in PACKAGE_ROOTS[name]]
    modules = {}
    for package_root in roots:
        module = package_root.stem if package_root.suffix == ".py" else package_root.name
        spec = importlib.machinery.PathFinder.find_spec(module, [str(base)])
        if spec is None or not spec.origin:
            raise ValueError("dependency import root unavailable")
        origin = Path(spec.origin)
        if package_root.suffix == ".py":
            if origin != package_root:
                raise ValueError("dependency import shadowed")
        elif not origin.is_relative_to(package_root):
            raise ValueError("dependency import outside package root")
        modules[module] = origin.relative_to(base).as_posix()

    def enumerate_files():
        found = set()
        excluded = [
            {
                "path": metadata_root.name + "/" + name,
                "reason": "installation_bookkeeping_not_executed",
            }
            for name in sorted(INSTALLATION_BOOKKEEPING)
        ]
        for root in (*roots, metadata_root):
            if root.is_symlink() or root.resolve(strict=True) != root:
                raise ValueError("symlinked dependency root")
            candidates = [root] if root.is_file() else list(root.rglob("*"))
            for candidate in candidates:
                if candidate.is_symlink() or candidate.resolve(strict=True) != candidate:
                    raise ValueError("symlinked dependency resource")
                if candidate.is_dir():
                    continue
                if candidate.parent == metadata_root and candidate.name in INSTALLATION_BOOKKEEPING:
                    continue
                else:
                    found.add(candidate)
        for root in roots:
            if root.suffix == ".py":
                cache = base / "__pycache__"
                if cache.exists():
                    if cache.is_symlink():
                        raise ValueError("symlinked dependency cache")
                    found.update(cache.glob(root.stem + ".*.pyc"))
        if not found or len(found) > 4096:
            raise ValueError("dependency file count invalid")
        if sum(path.lstat().st_size for path in found) > 128 * 1024 * 1024:
            raise ValueError("dependency tree byte limit exceeded")
        return found, sorted(excluded, key=lambda item: item["path"])

    selected, excluded = enumerate_files()
    records = list(
        csv.reader(_read_dependency(metadata_root / "RECORD").decode("utf-8").splitlines())
    )
    if len(records) > 8192:
        raise ValueError("distribution ledger too large")
    for entry in records:
        if len(entry) != 3:
            raise ValueError("distribution ledger invalid")
        relative = entry[0]
        candidate = base / relative
        if (
            candidate in selected
            or candidate.parent == metadata_root
            and candidate.name in INSTALLATION_BOOKKEEPING
        ):
            continue
        console = re.fullmatch(r"(?:\.\./)+(?:bin|Scripts)/([A-Za-z0-9_.-]+)", relative)
        if console and console[1].removesuffix(".exe") in console_names:
            excluded.append({"path": relative, "reason": "external_console_entry_not_executed"})
        else:
            raise ValueError("unrecognized distribution file outside runtime roots")
    files = [
        {
            "path": path.relative_to(base).as_posix(),
            "sha256": hashlib.sha256(_read_dependency(path)).hexdigest(),
        }
        for path in sorted(selected)
    ]
    after, after_excluded = enumerate_files()
    if (
        selected != after
        or [item for item in excluded if item["reason"] != "external_console_entry_not_executed"]
        != after_excluded
    ):
        raise ValueError("dependency tree changed")
    encoded = json.dumps(files, separators=(",", ":")).encode()
    return {
        "name": name,
        "version": version,
        "origin": str(base),
        "roots": list(PACKAGE_ROOTS[name]),
        "modules": modules,
        "file_count": len(files),
        "closure_sha256": hashlib.sha256(encoded).hexdigest(),
        "excluded": sorted(excluded, key=lambda item: item["path"]),
    }


def runtime_identity():
    """Hash actual package files as well as metadata/version, interpreter and lock.

    Only the Host's own installed distributions are considered. Paths are not accepted
    from a caller. A different install is a different binding, even at equal versions.
    """
    try:
        if sys.pycache_prefix is not None:
            raise ValueError("external bytecode cache prefix unsupported")
        projection = json.loads(LOCK_PROJECTION.read_bytes())
        if (
            set(projection) != {"schema", "lock_sha256", "versions"}
            or projection["schema"] != "research_pack_runtime_lock_v2"
            or not re.fullmatch(r"[a-f0-9]{64}", projection["lock_sha256"])
            or set(projection["versions"]) != set(DEPENDENCIES)
        ):
            raise ValueError("lock projection invalid")
        # A source checkout can verify the full original. Installed wheels own
        # the tested package-data projection and never require a repository tree.
        lock_path = Path(__file__).parents[3] / "requirements/web.lock"
        lock = lock_path.read_bytes() if lock_path.is_file() else None
        if lock is not None and hashlib.sha256(lock).hexdigest() != projection["lock_sha256"]:
            raise ValueError("lock projection changed")
        packages = []
        for name in DEPENDENCIES:
            version = projection["versions"][name]
            if lock is not None and not re.search(
                rb"(?m)^"
                + re.escape(name.encode())
                + rb"=="
                + re.escape(version.encode())
                + rb"(?:\s|$)",
                lock,
            ):
                raise ValueError("dependency is not at locked version")
            packages.append(
                _dependency_identity(name, version, Path(sys.prefix).resolve(strict=True))
            )
        for schema in RECORD_SCHEMAS.values():
            require_local_schema(schema)
        # Reuse only immutable syntax facts within this one fresh binding.
        # Both passes still read current bytes and verify all resolution state.
        source_facts = {}
        try:
            policy = build_policy(packages, _source_facts=source_facts)
            verify_policy(policy, packages, _source_facts=source_facts)
        finally:
            source_facts.clear()
        executable = Path(sys.executable).resolve(strict=True)
        return {
            "schema": "research_pack_runtime_v3",
            "import_policy": policy,
            "import_guard_sha256": hashlib.sha256(
                Path(__file__).with_name("pack_import_policy.py").read_bytes()
            ).hexdigest(),
            "validation_profile": {
                "schema": PROFILE,
                "sha256": hashlib.sha256(
                    (Path(__file__).parents[1] / "scenarios/packs/format_profile.py").read_bytes()
                ).hexdigest(),
                "formats": sorted(format_checker().checkers),
            },
            "fingerprint_policy": "import_roots_and_metadata_including_pyc_v1",
            "pyc_policy": "package_caches_hashed_external_prefix_rejected_v1",
            "entry_policy": "managed_python_module_no_console_v1",
            "python": str(executable),
            "environment": str(Path(sys.prefix).resolve(strict=True)),
            "python_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "python_version": sys.version,
            "python_abi": sysconfig.get_config_var("SOABI"),
            "implementation": sys.implementation.name,
            "platform": sys.platform,
            "machine": platform.machine(),
            "lock_sha256": projection["lock_sha256"],
            "dependencies": packages,
            "format_checkers": sorted(FormatChecker.checkers),
        }
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        SyntaxError,
        ImportError,
        csv.Error,
        ConfigError,
        importlib.metadata.PackageNotFoundError,
    ) as exc:
        log.warning("research_pack_dependency_binding_rejected", error_type=type(exc).__name__)
        raise CapabilityError(
            "组合包受管解释器或锁定依赖不可核验", "pack_runtime_unverified", 503
        ) from exc
