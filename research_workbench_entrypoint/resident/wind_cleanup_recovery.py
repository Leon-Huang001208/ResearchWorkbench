"""Read-only Wind cleanup diagnostics. No apply/recover or lifecycle operations.

The immutable deployed supervisor cannot understand a new maintenance journal.
A completed Future and cleanup poison are only observations, never ordinary idle
or permission to restart. A reviewed controller upgrade remains necessary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

from core.observability import get_logger

from . import controller as c
from . import gateway_upgrade as g
from .evidence import UpdateBlocked, read_json

log = get_logger(__name__)
CHECKS = frozenset(
    {
        "research_tasks",
        "approvals",
        "questions",
        "source_requests",
        "automation_runs",
        "history_jobs",
        "sdk_aggregate",
        "wind_api",
        "market",
        "reports",
        "datahub_tasks",
        "storage",
        "asset_directory",
        "asset_tasks",
        "directory_tasks",
    }
)
SOURCES = frozenset({"akshare", "baostock", "tinysoft", "wind"})


def validate_host_witness(value: dict, expected: str) -> None:
    """Reject missing/partial/mixed witnesses without relaxing ordinary active."""
    try:
        if (
            re.fullmatch(r"[a-f0-9]{40}", expected) is None
            or value.get("enabled") is not True
            or value.get("revision") != expected
            or value["active"] is not None
            or value.get("maintenance") is not False
        ):
            raise ValueError
        witness = value["activity_witness"]
        checks, sources = witness["checks"], witness["sources"]
        if (
            set(witness) != {"schema", "checks", "sources"}
            or witness["schema"] != "resident-activity-v1"
            or set(checks) != CHECKS
            or set(sources) != SOURCES
            or checks["sdk_aggregate"] is not None
            or any(checks[key] is not False for key in CHECKS - {"sdk_aggregate"})
        ):
            raise ValueError
        for source in sorted(SOURCES):
            row = sources[source]
            if (
                set(row) != {"running", "cleanup_unconfirmed"}
                or row["running"] is not False
                or row["cleanup_unconfirmed"] is not (source == "wind")
            ):
                raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        log.warning("wind_cleanup_observation_rejected")
        raise UpdateBlocked("wind_cleanup_activity_unverified") from exc


def _directory(path: Path) -> None:
    info = path.lstat()
    if (
        path.resolve(strict=True) != path.absolute()
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise UpdateBlocked("wind_cleanup_directory_unverified")


def _configuration(home: Path) -> tuple[Path, dict]:
    # controller.configured calls private_root (mkdir). Inspection must never
    # create an installation/run directory, including for a nonexistent home.
    root = home / "resident"
    _directory(root)
    config = read_json(root / "config.json")
    for key in ("project", "node", "python", "artifact"):
        path = Path(config[key])
        if not path.is_absolute() or path.resolve(strict=True) != path or not path.exists():
            raise UpdateBlocked("resident_configuration_changed")
    info = Path(config["project"]).stat()
    if [info.st_dev, info.st_ino] != config["project_identity"]:
        raise UpdateBlocked("resident_checkout_identity_changed")
    if c.digest(Path(config["artifact"])) != config["artifact_sha256"]:
        raise UpdateBlocked("resident_controller_changed")
    return root, config


def _accounts(server: Path, primary: str) -> tuple[str, ...]:
    _directory(server)
    _directory(server / "users")
    database = server / "accounts.sqlite3"
    info = database.lstat()
    if (
        database.resolve(strict=True) != database.absolute()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or any(
            (server / (database.name + suffix)).exists()
            or (server / (database.name + suffix)).is_symlink()
            for suffix in ("-wal", "-shm", "-journal")
        )
    ):
        raise UpdateBlocked("wind_cleanup_account_set_unverified")
    with sqlite3.connect(f"file:{quote(str(database))}?mode=ro&immutable=1", uri=True) as db:
        users = tuple(row[0] for row in db.execute("SELECT id FROM accounts ORDER BY id"))
    if (
        not 0 < len(users) <= 128
        or primary not in users
        or any(str(UUID(uid)) != uid for uid in users)
    ):
        raise UpdateBlocked("wind_cleanup_account_set_unverified")
    for folder in (server / "users").iterdir():
        _directory(folder)
        if folder.name not in users:
            raise UpdateBlocked("wind_cleanup_account_set_unverified")
        owner = folder / "state/owner.json"
        if owner.exists() or owner.is_symlink():
            raise UpdateBlocked("wind_cleanup_private_owner_present")
    return users


def _snapshots(home: Path) -> tuple[dict, dict]:
    """Same preservation scopes as deployment, without creating retention locks.

    Do not call gateway preservation or asset_index_snapshot here: their legacy
    defaults intentionally allow creating a missing dossier retention lock.
    """
    from app.research_web.dossier_preservation import snapshot_dossiers
    from app.research_web.multiuser.preservation import snapshot

    from .model_provider_upgrade import read_business_index

    def business(root):
        index = read_business_index(root / "index.json")
        dossiers = snapshot_dossiers(root, create_lock=False)
        if dossiers is not None:
            if "@dossiers" in index:
                raise UpdateBlocked("dossier_preservation_key_conflict")
            index = {**index, "@dossiers": dossiers}
        return {
            key: hashlib.sha256(
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            for key, value in index.items()
        }

    root = home / "research-web"
    preservation: dict[str, Any] = {
        "primary": snapshot(root, create_dossier_lock=False),
        "accounts": c.digest(home / "server/accounts.sqlite3"),
        "private": {},
    }
    indices: dict[str, dict[str, Any]] = {"primary": business(root), "private": {}}
    for folder in sorted((home / "server/users").iterdir()):
        private = folder / "research-web"
        if (private / "index.json").exists():
            preservation["private"][folder.name] = snapshot(private, create_dossier_lock=False)
            indices["private"][folder.name] = business(private)
    return preservation, indices


def _preserved(before: dict, after: dict) -> None:
    """Reuse the original session/model/file comparator, including all accounts."""
    from app.research_web.multiuser.preservation import compare_snapshot

    if after["accounts"] != before["accounts"] or set(after["private"]) != set(before["private"]):
        raise UpdateBlocked("gateway_preservation_failed")
    pairs = [(before["primary"], after["primary"])] + [
        (value, after["private"][uid]) for uid, value in before["private"].items()
    ]
    if not all(compare_snapshot(a, b)["preserved"] for a, b in pairs):
        raise UpdateBlocked("gateway_preservation_failed")


def inspect(home: Path, expected: str) -> dict:
    """Read current real Host/Native/persistent gates; return BLOCKED in all cases.

    No caller-supplied activity, fake binding, locks, fences, journals, signals,
    imports of Office adapters, or startup work are accepted. Reads are repeated
    to detect changes, but cannot close races; this is not transaction admission.
    """
    from app.research_web.multiuser.resident_binding import LegacyBinding, get_json
    from app.research_web.service_manager import WebServiceManager

    from .model_provider_upgrade import (
        asset_queries_idle,
        discovery_background_idle,
        read_business_index,
    )

    try:
        root, config = _configuration(home)
        server = home / "server"
        for journal in (
            root / "transaction.json",
            server / "run/gateway-upgrade.json",
            server / "run/birth-fence.json",
            server / "run/wind-cleanup-recovery.json",
        ):
            if journal.exists() or journal.is_symlink():
                raise UpdateBlocked("wind_cleanup_existing_recovery_pending")
        project = Path(config["project"])
        if c.git(project, "rev-parse", "HEAD") != expected or c.git(
            project, "--no-optional-locks", "status", "--porcelain"
        ):
            raise UpdateBlocked("resident_checkout_changed")
        settings = read_json(server / "resident.json")
        primary = settings["binding"]["primary_user_id"]
        users = _accounts(server, primary)
        binding = LegacyBinding.discover(home, primary)
        if binding.revision != expected:
            raise UpdateBlocked("wind_cleanup_same_revision_required")
        state = binding.verify()
        validate_host_witness(state, expected)
        before, business_before = _snapshots(home)
        manager = WebServiceManager(
            project_root=binding.project,
            data_root=binding.data_root,
            python=str(binding.project / ".venv/bin/python"),
            node=config["node"],
            web_port=binding.web_port,
            runtime_port=binding.runtime_port,
        )
        runtime = [p for p in manager._service_probes() if p.role == "runtime"]
        native = manager._active_research_read_only(runtime[0]) if len(runtime) == 1 else None
        if type(native) is not list or native:
            raise UpdateBlocked("wind_cleanup_native_active_or_unknown")
        if not discovery_background_idle(home):
            raise UpdateBlocked("wind_cleanup_background_active_or_unknown")
        roots = [home / "research-web"] + [
            server / "users" / uid / "research-web"
            for uid in users
            if (server / "users" / uid / "research-web/index.json").exists()
        ]
        if any(not asset_queries_idle(read_business_index(p / "index.json")) for p in roots):
            raise UpdateBlocked("wind_cleanup_assets_active_or_unknown")
        market = get_json(binding.web_port, "/api/research/market")
        if type(market.get("inflight")) is not list or market["inflight"]:
            raise UpdateBlocked("wind_cleanup_market_active_or_unknown")
        g.no_private_processes(server)
        after, business_after = _snapshots(home)
        if _accounts(server, primary) != users or business_after != business_before:
            raise UpdateBlocked("wind_cleanup_observation_changed")
        _preserved(before, after)
        validate_host_witness(binding.verify(), expected)
        g.no_private_processes(server)
        # Do not expose paths, account IDs, model settings, or run content.
        log.info("wind_cleanup_inspection_only", ordinary_idle_certified=False)
        return {
            "status": "blocked",
            "reason": "wind_cleanup_controller_upgrade_required",
            "revision": expected,
            "account_count": len(users),
            "observation": "wind_cleanup_unconfirmed_future_done",
            "ordinary_idle_certified": False,
            "recovery_implemented": False,
            "transaction_admission": "not_run",
            "business_snapshot_sha256": hashlib.sha256(
                json.dumps(business_before, sort_keys=True).encode()
            ).hexdigest(),
        }
    except UpdateBlocked:
        raise
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, RuntimeError) as exc:
        log.warning("wind_cleanup_inspection_unverified", error_type=type(exc).__name__)
        raise UpdateBlocked("wind_cleanup_inspection_unverified") from exc
