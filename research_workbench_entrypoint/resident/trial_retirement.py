"""Offline trial retirement within the existing resident operator transaction.

No signal, installation, session.delete acknowledgement or native settlement is
produced here. The operator must already hold its locks and a stopped boundary.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import stat
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from . import trial_discard_backup as backup
from .evidence import UpdateBlocked

log = logging.getLogger(__name__)
MODE = "operator-authorized-trial-retirement-v1"
PREVIOUS = "b800e50366d1a0868372bbf173822976066c143f"
PAYLOAD = "db2ae9a48ceca365852072e622aa6627aa7d0b83"
CONSENT = "USER_AUTHORIZED_DISCARD"
ACTIVE_REPORT = {
    "queued",
    "preparing_data",
    "running",
    "blocked_approval",
    "validating",
    "needs_attention",
    "waiting",
    "pending",
}
STOP_FIELDS = frozenset(
    {
        "status",
        "research_status",
        "delivery_status",
        "updated_at",
        "completed_at",
        "error",
        "failure_code",
        "last_error",
        "finalization_status",
        "recovery_failure_code",
        "recovered_at",
        "monitoring_disposition",
    }
)


def _rows(index: dict, name: str) -> dict:
    rows = index.get(name, {})
    if not isinstance(rows, dict) or any(not isinstance(row, dict) for row in rows.values()):
        raise UpdateBlocked("trial_retirement_producer_shape_unknown:" + name)
    return rows


def _linked(row: dict, sessions: set[str]) -> bool:
    return any(
        isinstance(row.get(key), str) and row[key] in sessions
        for key in (
            "session_id",
            "sessionId",
            "research_session_id",
            "delivery_session_id",
            "source_session_id",
        )
    )


def _unlinked(namespace: str, key: str) -> None:
    reference = hashlib.sha256(str(key).encode()).hexdigest()[:16]
    log.warning(
        "trial_retirement_producer_scope_unknown namespace=%s reference=%s", namespace, reference
    )
    raise UpdateBlocked("trial_retirement_producer_scope_unknown:" + namespace + ":" + reference)


def retire_producers(index: dict, catalog: dict | None = None) -> tuple[dict, dict | None]:
    """Retire only restart producers traceable to the frozen trial sessions."""
    result, changed_catalog = deepcopy(index), deepcopy(catalog)
    sessions = set(_rows(index, "sessions"))
    report_ids, workflow_ids, automation_ids = set(), set(), set()
    report_tables = [("report_runs", _rows(result, "report_runs"))]
    if changed_catalog is not None:
        report_tables.append(("workflow_runs", _rows(changed_catalog, "runs")))
    for namespace, table in report_tables:
        for key, row in table.items():
            linked = _linked(row, sessions)
            if linked:
                report_ids.add(key)
                if isinstance(row.get("workflow_id"), str):
                    workflow_ids.add(row["workflow_id"])
            if row.get("status") in ACTIVE_REPORT:
                if not linked:
                    _unlinked(namespace, key)
                row.update(
                    status="cancelled",
                    monitoring_disposition="ended_by_user",
                    failure_code="user_authorized_discard",
                )
    for key, row in _rows(result, "automation_runs").items():
        linked = _linked(row, sessions) or row.get("report_run_id") in report_ids
        if linked and isinstance(row.get("automation_id"), str):
            automation_ids.add(row["automation_id"])
        active = row.get("research_status") in {"queued", "running"} or (
            row.get("research_status") == "completed" and row.get("delivery_status") == "pending"
        )
        if active:
            if not linked:
                _unlinked("automation_runs", key)
            if row.get("research_status") in {"queued", "running"}:
                row["research_status"] = "interrupted"
            row.update(delivery_status="cancelled", failure_code="user_authorized_discard")
    for namespace in ("automations", "report_schedules", "discovery_tracks"):
        for key, row in _rows(result, namespace).items():
            if row.get("enabled"):
                linked = (
                    _linked(row, sessions)
                    or (namespace == "automations" and key in automation_ids)
                    or row.get("workflow_id") in workflow_ids
                )
                if not linked:
                    _unlinked(namespace, key)
                row.update(enabled=False, next_run_at=None)
    if changed_catalog is not None:
        for key, row in _rows(changed_catalog, "workflows").items():
            schedule = row.get("schedule")
            if schedule is not None and not isinstance(schedule, dict):
                raise UpdateBlocked("trial_retirement_producer_shape_unknown:workflow_schedules")
            if schedule and schedule.get("enabled"):
                if key not in workflow_ids and not _linked(schedule, sessions):
                    _unlinked("workflow_schedules", key)
                schedule.update(enabled=False, next_run_at=None)
    result["sessions"] = {}
    return result, changed_catalog


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _scope_content(
    index: dict, sessions: set[str], *, catalog: bool = False, report_ids: set[str] | None = None
) -> dict:
    result = deepcopy(index)
    if not catalog:
        for row in _rows(result, "sessions").values():
            for key in STOP_FIELDS:
                row.pop(key, None)
    namespaces = (
        ("runs",)
        if catalog
        else ("report_runs", "automation_runs", "data_queries", "asset_history_jobs", "handoffs")
    )
    for name in namespaces:
        for row in _rows(result, name).values():
            if _linked(row, sessions) or (
                name == "automation_runs"
                and isinstance(row.get("report_run_id"), str)
                and row["report_run_id"] in (report_ids or set())
            ):
                for key in STOP_FIELDS:
                    row.pop(key, None)
    return result


def _native_scope(root: Path) -> dict:
    result = {}
    for relative in ("sessions", "runtime/home/sessions"):
        path = root / relative
        if not path.exists() and not path.is_symlink():
            result[relative] = {"status": "missing"}
            continue
        info = backup._directory(path)
        entries = {}
        with backup._anchored_parent(path) as (fd, _), os.scandir(fd) as listing:
            for entry in listing:
                item = entry.stat(follow_symlinks=False)
                if item.st_uid != os.getuid() or not (
                    stat.S_ISREG(item.st_mode) or stat.S_ISDIR(item.st_mode)
                ):
                    raise UpdateBlocked("trial_retirement_native_scope_unknown")
                if len(entries) >= 10000:
                    raise UpdateBlocked("trial_retirement_native_scope_budget_exceeded")
                entries[entry.name] = "directory" if stat.S_ISDIR(item.st_mode) else "file"
        result[relative] = {
            "status": "present",
            "identity": [info.st_dev, info.st_ino],
            "entries": entries,
        }
    return result


def scope_snapshot(home: Path) -> dict:
    """Compute consent scope from owned files; never accept a caller's scope claim."""
    inventory = backup.preview(home)
    info = backup._directory(home)
    roots = []
    for row in inventory["roots"]:
        relative = _index_relative(row)
        root = home / relative.parent
        index = {}
        if row["index"] == "present":
            index, _, identity = backup._json(home / relative, backup.MAX_ASSET_INDEX_BYTES)
            if identity != row["index_identity"]:
                raise UpdateBlocked("trial_retirement_scope_changed")
        sessions = set(_rows(index, "sessions"))
        catalog = None
        catalog_state = row["catalog"]
        if catalog_state["status"] == "present":
            catalog, _, identity = backup._json(
                root / "report-workflows/catalog.json", backup.MAX_ASSET_INDEX_BYTES
            )
            if identity != catalog_state["identity"]:
                raise UpdateBlocked("trial_retirement_scope_changed")
        report_ids = {
            key for key, value in _rows(index, "report_runs").items() if _linked(value, sessions)
        }
        if catalog is not None:
            report_ids.update(
                key for key, value in _rows(catalog, "runs").items() if _linked(value, sessions)
            )
        roots.append(
            {
                "account_id": row["account_id"],
                "kind": row["kind"],
                "root_identity": row.get("root_identity"),
                "index": row["index"],
                "session_ids": sorted(sessions),
                "native_sessions": _native_scope(root) if "root_identity" in row else None,
                "protected_index_sha256": digest(
                    _scope_content(index, sessions, report_ids=report_ids)
                ),
                "catalog": catalog_state["status"],
                "catalog_directory": catalog_state.get("directory_identity", "missing"),
                "protected_catalog_sha256": (
                    digest(_scope_content(catalog, sessions, catalog=True))
                    if catalog is not None
                    else None
                ),
            }
        )
    return {
        "home_identity": [info.st_dev, info.st_ino],
        "accounts_sha256": inventory["accounts_identity"]["sha256"],
        "binding_sha256": inventory["binding_identity"]["sha256"],
        "roots": roots,
    }


def authorize(
    home: Path, manifest: dict, expected_digest: str, *, stopped_snapshot: bool = False
) -> dict:
    """Bind explicit consent to the exact roots and observed session inventory."""
    observed = backup.preview(home)
    info = home.lstat()
    expected = {
        "version": 1,
        "profile": MODE,
        "previous": PREVIOUS,
        "payload": PAYLOAD,
        "home_identity": [info.st_dev, info.st_ino],
        "inventory_seal": manifest.get("inventory_seal") if stopped_snapshot else observed["seal"],
        "scope_sha256": digest(scope_snapshot(home)),
        "authorization": CONSENT,
        "scope": "all_historical_rwb_trial_sessions",
        "wind_cleanup": "UNKNOWN_ACCEPTED_NO_NATIVE_ACK",
        "preserve": ["accounts", "models", "non_session_business_data"],
    }
    if manifest != expected or digest(manifest) != expected_digest:
        raise UpdateBlocked("trial_retirement_consent_mismatch")
    log.info("trial_retirement_authorization_verified roots=%s", len(observed["roots"]))
    return observed


def preservation_delta(before: dict) -> dict:
    """Expected preserved scopes after authorized discard, never an idle witness.

    The result must be recorded as an explicit trial delta, not overwrite the
    original full snapshot or be described as preserving historical sessions.
    """
    result = deepcopy(before)
    for scope in [result["primary"], *result["private"].values()]:
        scope["sessions"] = {}
        scope["files"] = {
            path: value
            for path, value in scope["files"].items()
            if not path.startswith(("sessions/", "runtime/home/sessions/"))
        }
    return result


def asset_delta(before: dict, record: dict | None = None) -> dict:
    """Freeze all original business values except the declared empty sessions."""
    result = deepcopy(before)
    if record is not None:
        validate_record(record)
        return deepcopy(record["planned_asset_index"])
    empty_hash = hashlib.sha256(b"{}").hexdigest()
    for scope in [result["primary"], *result["private"].values()]:
        scope["sessions"] = empty_hash
    return result


def preservation_baseline(before: dict, record: dict) -> dict:
    """Permit trial-stop deltas while requiring all unrelated preservation scopes."""
    validate_record(record)
    stopped_before = record["stopped_preservation"]
    if preservation_delta(before) != preservation_delta(stopped_before):
        raise UpdateBlocked("trial_retirement_stopped_preservation_changed")
    return deepcopy(stopped_before)


def validate_record(record: dict) -> None:
    """Recovery validates persisted consent without requiring original live bytes."""
    try:
        authorization = record["authorization"]
        inventory = record["inventory"]
        inventory_seal = hashlib.sha256(
            json.dumps(
                {
                    "binding": inventory["binding_identity"],
                    "accounts": inventory["accounts_identity"],
                    "roots": inventory["roots"],
                },
                sort_keys=True,
                ensure_ascii=True,
            ).encode()
        ).hexdigest()
        if (
            record["version"] != 1
            or record["status"] not in {"staging", "prepared", "retired_offline", "restored"}
            or record["native_cleanup"] != "UNKNOWN"
            or record["trial_outcome"] != CONSENT
            or record["data_retirement_committed"] is not (record["status"] == "retired_offline")
            or record["code_rollback_preserves_disposition"] is not True
            or record["manual_restore_requires_fence"] is not True
            or authorization["profile"] != MODE
            or authorization["previous"] != PREVIOUS
            or authorization["payload"] != PAYLOAD
            or authorization["authorization"] != CONSENT
            or authorization["scope"] != "all_historical_rwb_trial_sessions"
            or authorization["wind_cleanup"] != "UNKNOWN_ACCEPTED_NO_NATIVE_ACK"
            or authorization["preserve"] != ["accounts", "models", "non_session_business_data"]
            or digest(authorization) != record["authorization_sha256"]
            or digest({"plan": record["plan"]}) != record["plan_sha256"]
            or record["backup"]["status"] != "restore_verified"
            or record["backup"]["source_seal"] != inventory["seal"]
            or inventory_seal != inventory["seal"]
            or digest(record["stopped_scope"]) != authorization["scope_sha256"]
            or digest(
                {
                    "preservation": record["stopped_preservation"],
                    "assets": record["stopped_asset_index"],
                    "planned": record["planned_asset_index"],
                }
            )
            != record["baselines_sha256"]
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("trial_retirement_record_invalid")
        raise UpdateBlocked("trial_retirement_record_invalid") from exc


def _verify_record_roots(home: Path, record: dict) -> None:
    info = backup._directory(home)
    if [info.st_dev, info.st_ino] != record["authorization"]["home_identity"]:
        raise UpdateBlocked("trial_retirement_home_changed")
    _, accounts = backup._read(home / "server/accounts.sqlite3", backup.DB_LIMIT)
    if accounts["sha256"] != record["inventory"]["accounts_identity"]["sha256"]:
        raise UpdateBlocked("trial_retirement_accounts_changed")
    for row in record["inventory"]["roots"]:
        root = home / _index_relative(row).parent
        if "root_identity" not in row:
            if root.exists() or root.is_symlink():
                raise UpdateBlocked("trial_retirement_root_changed")
            continue
        info = backup._directory(root)
        if [info.st_dev, info.st_ino] != row["root_identity"]:
            raise UpdateBlocked("trial_retirement_root_changed")
        expected = row["catalog"].get("directory_identity")
        if expected is not None:
            info = backup._directory(root / "report-workflows")
            if [info.st_dev, info.st_ino] != expected:
                raise UpdateBlocked("trial_retirement_catalog_directory_changed")


def _held(path: Path) -> None:
    """Require an existing contended lock; never create an alleged caller lock."""
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise UpdateBlocked("trial_retirement_lock_invalid")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        raise UpdateBlocked("trial_retirement_lock_not_held")
    finally:
        os.close(fd)


def stopped(ops) -> None:
    """Recheck existing operator fences and actual absence before every mutation."""
    from . import gateway_upgrade as gateway
    from . import model_provider_upgrade as upgrade

    if not isinstance(ops, upgrade.Operations) or ops.state.get("mode") != MODE:
        raise UpdateBlocked("trial_retirement_operator_required")
    for path in (
        ops.root / "supervisor.lock",
        ops.root / "admission.lock",
        ops.server / "run/operator.lock",
    ):
        _held(path)
    ops.manager._assert_installation_scope(ops.lease)
    if ops.fence is None or ops.fence.retain is not True:
        raise UpdateBlocked("trial_retirement_birth_fence_required")
    if not (ops.root / "transaction.json").is_file():
        raise UpdateBlocked("trial_retirement_journal_required")
    gateway.no_private_processes(ops.server)
    probes = list(ops.manager._service_probes())
    if len(probes) != 2 or {p.role for p in probes} != {"web", "runtime"}:
        raise UpdateBlocked("trial_retirement_writer_unknown")
    if any(p.process != "missing" or p.port_state != "closed" for p in probes):
        raise UpdateBlocked("trial_retirement_writer_not_stopped")
    if gateway.job_state() is not None or gateway.listener_pids():
        raise UpdateBlocked("trial_retirement_gateway_not_stopped")
    if not upgrade.ports_are_free(
        (ops.state["config"]["web_port"], ops.state["config"]["runtime_port"])
    ):
        raise UpdateBlocked("trial_retirement_ports_not_free")


def _index_relative(row: dict) -> Path:
    return (
        Path("research-web/index.json")
        if row["kind"] == "primary"
        else Path("server/users") / row["account_id"] / "research-web/index.json"
    )


def _tree(path: Path) -> dict:
    """Bounded no-follow file inventory; unknown filesystem objects block."""
    files = {}
    total = 0

    def scan_failed(error):
        log.warning("trial_retirement_archive_scan_failed error_type=%s", type(error).__name__)
        raise UpdateBlocked("trial_retirement_archive_unreadable") from error

    for folder, dirs, names in os.walk(path, followlinks=False, onerror=scan_failed):
        for name in dirs:
            directory = Path(folder) / name
            info = backup._directory(directory)
            if len(files) >= 10000:
                raise UpdateBlocked("trial_retirement_archive_budget_exceeded")
            files[str(directory.relative_to(path))] = {
                "kind": "directory",
                "dev": info.st_dev,
                "ino": info.st_ino,
                "mode": stat.S_IMODE(info.st_mode),
                "size": 0,
            }
        for name in names:
            item = Path(folder) / name
            if item.lstat().st_size == 0:
                backup._ancestors(item)
                descriptor = os.open(item, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    info = os.fstat(descriptor)
                    current = item.lstat()
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_uid != os.getuid()
                        or info.st_size != 0
                        or (info.st_dev, info.st_ino, info.st_mtime_ns)
                        != (current.st_dev, current.st_ino, current.st_mtime_ns)
                    ):
                        raise UpdateBlocked("trial_retirement_archive_changed")
                    raw = b""
                    identity = {
                        "dev": info.st_dev,
                        "ino": info.st_ino,
                        "size": 0,
                        "mode": stat.S_IMODE(info.st_mode),
                        "mtime_ns": info.st_mtime_ns,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                finally:
                    os.close(descriptor)
            else:
                raw, identity = backup._read(item, backup.MAX_ASSET_INDEX_BYTES)
            total += len(raw)
            if total > backup.MAX_TOTAL_BYTES or len(files) >= 10000:
                raise UpdateBlocked("trial_retirement_archive_budget_exceeded")
            files[str(item.relative_to(path))] = identity
    return files


def _replace(path: Path, raw: bytes, expected: str) -> None:
    """Pinned directory and exact prior bytes; fsync before the atomic rename."""
    with backup._anchored_parent(path.parent) as (fd, _):
        current, mode = backup._read_at(fd, path.name, backup.MAX_ASSET_INDEX_BYTES)
        if hashlib.sha256(current).hexdigest() != expected:
            raise UpdateBlocked("trial_retirement_index_drift")
        name = ".trial-retirement-index"
        backup._write_new(fd, name, raw, mode)
        os.rename(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)


def prepare(ops, manifest: dict, expected_digest: str, backup_parent: Path) -> dict:
    """Stage a verified backup and journal its exact plan before changing data."""
    stopped(ops)
    inventory = authorize(ops.home, manifest, expected_digest, stopped_snapshot=True)
    from . import model_provider_upgrade as upgrade

    stopped_preservation = upgrade.g.preservation(ops.home)
    stopped_assets = upgrade.asset_index_snapshot(ops.home)
    planned_assets = deepcopy(stopped_assets)
    stopped_scope = scope_snapshot(ops.home)
    receipt = backup.backup(ops.home, backup_parent, inventory["seal"])
    plan = []
    archive_bytes = inventory["total_bytes"]
    archive_files = 0
    for row in inventory["roots"]:
        if "root_identity" not in row:
            continue
        relative = _index_relative(row)
        catalog_path = ops.home / relative.parent / "report-workflows/catalog.json"
        catalog_present = row["catalog"]["status"] == "present"
        catalog, catalog_raw = None, None
        if catalog_present:
            catalog, catalog_raw, catalog_id = backup._json(
                catalog_path, backup.MAX_ASSET_INDEX_BYTES
            )
            if catalog_id != row["catalog"]["identity"]:
                raise UpdateBlocked("trial_retirement_inventory_drift")
        present = row["index"] == "present"
        index = {}
        if present:
            index, raw, identity = backup._json(ops.home / relative, backup.MAX_ASSET_INDEX_BYTES)
            if identity != row["index_identity"]:
                raise UpdateBlocked("trial_retirement_inventory_drift")
        projected, projected_catalog = retire_producers(index, catalog)
        catalog_after = catalog_raw
        if projected_catalog != catalog:
            catalog_after = json.dumps(
                projected_catalog, ensure_ascii=False, allow_nan=False
            ).encode()
        if present:
            after = (
                raw
                if projected == index
                else json.dumps(projected, ensure_ascii=False, allow_nan=False).encode()
            )
            scope = (
                planned_assets["primary"]
                if row["kind"] == "primary"
                else planned_assets["private"][row["account_id"]]
            )
            scope.update({key: digest(value) for key, value in projected.items()})
        # Session file directories remain intact, with original inode/modes,
        # in the same parent. No non-session directory is moved or removed.
        directories = []
        for directory in (relative.parent / "sessions", relative.parent / "runtime/home/sessions"):
            path = ops.home / directory
            if path.exists() or path.is_symlink():
                backup._ancestors(path / "placeholder")
                info = backup._directory(path)
                directories.append(
                    {
                        "relative": str(directory),
                        "identity": [info.st_dev, info.st_ino],
                        "files": _tree(path),
                        "replacement_identity": None,
                        "replacement_mode": 0o700,
                    }
                )
                archive_bytes += sum(value["size"] for value in directories[-1]["files"].values())
                archive_files += len(directories[-1]["files"])
                if archive_bytes > backup.MAX_TOTAL_BYTES or archive_files > 10000:
                    raise UpdateBlocked("trial_retirement_archive_budget_exceeded")
        plan.append(
            {
                "index": str(relative),
                "index_present": present,
                "before_sha256": hashlib.sha256(raw).hexdigest() if present else None,
                "after_sha256": hashlib.sha256(after).hexdigest() if present else None,
                "session_count": len(index["sessions"]) if present else 0,
                "catalog_present": catalog_present,
                "catalog_before_sha256": (
                    hashlib.sha256(catalog_raw).hexdigest() if catalog_present else None
                ),
                "catalog_after_sha256": (
                    hashlib.sha256(catalog_after).hexdigest() if catalog_present else None
                ),
                "directories": directories,
            }
        )
    retirement = {
        "version": 1,
        "authorization": manifest,
        "authorization_sha256": expected_digest,
        "backup": receipt,
        "inventory": inventory,
        "stopped_scope": stopped_scope,
        "stopped_preservation": stopped_preservation,
        "stopped_asset_index": stopped_assets,
        "planned_asset_index": planned_assets,
        "baselines_sha256": digest(
            {
                "preservation": stopped_preservation,
                "assets": stopped_assets,
                "planned": planned_assets,
            }
        ),
        "plan": plan,
        "plan_sha256": digest({"plan": plan}),
        "status": "staging",
        "data_retirement_committed": False,
        "code_rollback_preserves_disposition": True,
        "manual_restore_requires_fence": True,
        "native_cleanup": "UNKNOWN",
        "trial_outcome": CONSENT,
    }
    ops.state["trial_retirement"] = retirement
    ops.checkpoint(ops.state, "stop_primary")
    log.info("trial_retirement_plan_persisted roots=%s", len(plan))
    _stage_replacements(ops)
    return retirement


def _stage_replacements(ops) -> None:
    """Create and freeze replacements before any original directory is moved."""
    record = ops.state["trial_retirement"]
    for row in record["plan"]:
        for directory in row["directories"]:
            stopped(ops)
            path = ops.home / directory["relative"]
            staged = path.with_name(".trial-empty-" + ops.state["transaction"])
            if directory["replacement_identity"] is not None:
                info = backup._directory(staged)
                if [info.st_dev, info.st_ino] != directory["replacement_identity"] or _tree(staged):
                    raise UpdateBlocked("trial_retirement_replacement_changed")
                continue
            # A crash after mkdir but before its inode was committed is unknown;
            # do not retroactively adopt the object on a later invocation.
            with backup._anchored_parent(path.parent) as (fd, _):
                if staged.exists() or staged.is_symlink():
                    raise UpdateBlocked("trial_retirement_replacement_identity_unknown")
                os.mkdir(staged.name, mode=0o700, dir_fd=fd)
                os.fsync(fd)
                info = os.stat(staged.name, dir_fd=fd, follow_symlinks=False)
                directory["replacement_identity"] = [info.st_dev, info.st_ino]
            record["plan_sha256"] = digest({"plan": record["plan"]})
            ops.checkpoint(ops.state, "stop_primary")
    record["status"] = "prepared"
    ops.checkpoint(ops.state, "stop_primary")


def _archive_directory(ops, directory: dict, *, restoring: bool, verify: bool = False) -> None:
    path = ops.home / directory["relative"]
    archived = path.with_name(".trial-retired-" + ops.state["transaction"])
    staged = path.with_name(".trial-empty-" + ops.state["transaction"])
    with backup._anchored_parent(path.parent) as (fd, _):

        def observed(item):
            try:
                info = backup._directory(item)
                return [info.st_dev, info.st_ino]
            except FileNotFoundError:
                return None

        original_id, empty_id = directory["identity"], directory["replacement_identity"]
        locations = {item: observed(item) for item in (path, archived, staged)}
        # Every observed inode must be one of the two previously journaled
        # directories. Never adopt an empty directory created by another writer.
        if any(value not in (None, original_id, empty_id) for value in locations.values()):
            raise UpdateBlocked("trial_retirement_directory_changed")
        originals = [item for item, identity in locations.items() if identity == original_id]
        replacements = [item for item, identity in locations.items() if identity == empty_id]
        if len(originals) != 1 or len(replacements) != 1:
            raise UpdateBlocked("trial_retirement_directory_state_unknown")
        original, replacement = originals[0], replacements[0]
        if original not in (path, archived) or replacement not in (path, staged):
            raise UpdateBlocked("trial_retirement_directory_state_unknown")
        if _tree(original) != directory["files"]:
            raise UpdateBlocked("trial_retirement_archive_changed")
        replacement_info = backup._directory(replacement)
        if stat.S_IMODE(replacement_info.st_mode) != directory["replacement_mode"] or _tree(
            replacement
        ):
            raise UpdateBlocked("trial_retirement_replacement_changed")
        moves = (
            ((replacement, staged), (original, path))
            if restoring
            else ((original, archived), (replacement, path))
        )
        if verify:
            if original != archived or replacement != path:
                raise UpdateBlocked("trial_retirement_archive_not_committed")
            return
        for source, target in moves:
            if source == target:
                continue
            if observed(target) is not None:
                raise UpdateBlocked("trial_retirement_directory_state_unknown")
            os.rename(source.name, target.name, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)


def validate_retired(home: Path, record: dict, *, transaction: str) -> None:
    """Read-only pre-start/release check of all frozen producers and native dirs."""
    validate_record(record)
    _verify_record_roots(Path(home), record)
    if record["status"] != "retired_offline":
        raise UpdateBlocked("trial_retirement_not_committed")
    view = SimpleNamespace(home=Path(home), state={"transaction": transaction})
    for row in record["plan"]:
        relative = Path(row["index"])
        if relative.is_absolute() or ".." in relative.parts:
            raise UpdateBlocked("trial_retirement_plan_invalid")
        path = home / relative
        if row["index_present"]:
            index, raw, _ = backup._json(path, backup.MAX_ASSET_INDEX_BYTES)
            if (
                hashlib.sha256(raw).hexdigest() != row["after_sha256"]
                or index.get("sessions") != {}
            ):
                raise UpdateBlocked("trial_retirement_poststate_changed")
        elif path.exists() or path.is_symlink():
            raise UpdateBlocked("trial_retirement_poststate_changed")
        else:
            index = {}
        catalog_path = path.parent / "report-workflows/catalog.json"
        catalog = None
        if row["catalog_present"]:
            catalog, catalog_raw, _ = backup._json(catalog_path, backup.MAX_ASSET_INDEX_BYTES)
            if hashlib.sha256(catalog_raw).hexdigest() != row["catalog_after_sha256"]:
                raise UpdateBlocked("trial_retirement_poststate_changed")
        elif catalog_path.exists() or catalog_path.is_symlink():
            raise UpdateBlocked("trial_retirement_poststate_changed")
        projected, projected_catalog = retire_producers(index, catalog)
        if projected != {**index, "sessions": {}} or projected_catalog != catalog:
            raise UpdateBlocked("trial_retirement_producer_still_eligible")
        for directory in row["directories"]:
            if directory["relative"] not in {
                str(relative.parent / "sessions"),
                str(relative.parent / "runtime/home/sessions"),
            }:
                raise UpdateBlocked("trial_retirement_plan_invalid")
            _archive_directory(view, directory, restoring=False, verify=True)
        planned = {directory["relative"] for directory in row["directories"]}
        for missing in {
            str(relative.parent / "sessions"),
            str(relative.parent / "runtime/home/sessions"),
        } - planned:
            directory = home / missing
            if directory.exists() or directory.is_symlink():
                raise UpdateBlocked("trial_retirement_native_scope_changed")


def _saved_projections(
    point: Path, row: dict, saved: dict
) -> list[tuple[Path, bytes, bytes, str, str]]:
    relative = Path(row["index"])
    originals = {}
    for key, present, path in (
        ("index", row["index_present"], relative),
        ("catalog", row["catalog_present"], relative.parent / "report-workflows/catalog.json"),
    ):
        if present:
            raw, _ = backup._read(point / path, backup.MAX_ASSET_INDEX_BYTES)
            if hashlib.sha256(raw).hexdigest() != saved["files"][str(path)]["sha256"]:
                raise UpdateBlocked("trial_retirement_backup_changed")
            originals[key] = (json.loads(raw), raw)
    projected, catalog = retire_producers(
        originals.get("index", ({}, None))[0], originals.get("catalog", (None, None))[0]
    )
    results = []
    for key, data, path in (
        ("index", projected, relative),
        ("catalog", catalog, relative.parent / "report-workflows/catalog.json"),
    ):
        if key not in originals:
            continue
        original_value, original = originals[key]
        changed = (
            original
            if data == original_value
            else json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        )
        before_key, after_key = (
            ("before_sha256", "after_sha256")
            if key == "index"
            else ("catalog_before_sha256", "catalog_after_sha256")
        )
        if (
            hashlib.sha256(original).hexdigest() != row[before_key]
            or hashlib.sha256(changed).hexdigest() != row[after_key]
        ):
            raise UpdateBlocked("trial_retirement_plan_invalid")
        results.append((path, original, changed, row[before_key], row[after_key]))
    return results


def apply(ops, *, restoring: bool = False) -> dict:
    """Resume retirement; restoring is manual offline recovery, never code rollback.

    Restoring requires the same stopped fences and must not be followed by a
    service start or admission release: restored producer eligibility is unsafe.
    """
    stopped(ops)
    record = ops.state["trial_retirement"]
    validate_record(record)
    _verify_record_roots(ops.home, record)
    if record["status"] == "staging":
        _stage_replacements(ops)
    if digest(record["authorization"]) != record["authorization_sha256"]:
        raise UpdateBlocked("trial_retirement_consent_mismatch")
    if digest({"plan": record["plan"]}) != record["plan_sha256"]:
        raise UpdateBlocked("trial_retirement_plan_invalid")
    point = Path(record["backup"]["backup"])
    manifest_raw, _ = backup._read(point / "manifest.json", backup.RECORD_LIMIT)
    if hashlib.sha256(manifest_raw).hexdigest() != record["backup"]["manifest_sha256"]:
        raise UpdateBlocked("trial_retirement_backup_changed")
    saved = json.loads(manifest_raw)
    indices = {name for name in saved["files"] if name.endswith("/index.json")}
    present_indices = {row["index"] for row in record["plan"] if row["index_present"]}
    root_indices = {
        str(_index_relative(row)) for row in record["inventory"]["roots"] if "root_identity" in row
    }
    if (
        present_indices != indices
        or {row["index"] for row in record["plan"]} != root_indices
        or len(record["plan"]) != len(root_indices)
    ):
        raise UpdateBlocked("trial_retirement_plan_invalid")
    for row in record["plan"]:
        stopped(ops)
        relative = Path(row["index"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) not in root_indices:
            raise UpdateBlocked("trial_retirement_plan_invalid")
        projections = _saved_projections(point, row, saved)
        if not row["index_present"] and (
            (ops.home / relative).exists() or (ops.home / relative).is_symlink()
        ):
            raise UpdateBlocked("trial_retirement_index_drift")
        allowed_directories = {
            str(relative.parent / "sessions"),
            str(relative.parent / "runtime/home/sessions"),
        }
        planned_directories = {directory["relative"] for directory in row["directories"]}
        if not planned_directories <= allowed_directories or len(planned_directories) != len(
            row["directories"]
        ):
            raise UpdateBlocked("trial_retirement_plan_invalid")
        for missing in allowed_directories - planned_directories:
            path = ops.home / missing
            archived = path.with_name(".trial-retired-" + ops.state["transaction"])
            if path.exists() or path.is_symlink() or archived.exists() or archived.is_symlink():
                raise UpdateBlocked("trial_retirement_directory_state_unknown")
        for directory in row["directories"]:
            if directory["relative"] not in {
                str(relative.parent / "sessions"),
                str(relative.parent / "runtime/home/sessions"),
            }:
                raise UpdateBlocked("trial_retirement_plan_invalid")
            _archive_directory(ops, directory, restoring=restoring)
        for relative_path, original, changed, before_hash, after_hash in projections:
            path = ops.home / relative_path
            current, _ = backup._read(path, backup.MAX_ASSET_INDEX_BYTES)
            current_hash = hashlib.sha256(current).hexdigest()
            desired, other = (original, after_hash) if restoring else (changed, before_hash)
            if current_hash != hashlib.sha256(desired).hexdigest():
                if current_hash != other:
                    raise UpdateBlocked("trial_retirement_index_drift")
                _replace(path, desired, other)
    record["status"] = "restored" if restoring else "retired_offline"
    record["data_retirement_committed"] = not restoring
    ops.checkpoint(ops.state, "stop_primary")
    log.info("trial_retirement_completed status=%s", record["status"])
    return record
