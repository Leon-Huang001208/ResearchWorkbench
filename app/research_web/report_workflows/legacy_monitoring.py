"""Explicit legacy monitoring disposition, preserving uncertain execution evidence.

This domain operation makes no claim about Native computation. A resident
operator must separately prove ownership and Native idle before calling apply.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from core.observability import get_logger

from ..datahub.security import directory, read_file
from .models import WorkflowError

log = get_logger(__name__)
PROFILE = "weekly-legacy-monitoring-v1"


def digest(value):
    """Canonical catalog-row digest used for explicit compare and swap."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def deny(code):
    log.warning("weekly_legacy_monitoring_rejected", code=code)
    raise WorkflowError("历史周报等待维护条件不符", code, 409)


def validate_existing_path(path, *, directory=False, private=False):
    """Reject symlink ancestors, shared ownership, hardlinks and unsafe modes."""
    path = Path(path).absolute()
    try:
        for ancestor in (*reversed(path.parents), path):
            if ancestor.is_symlink():
                deny("weekly_monitoring_unsafe_path")
        info = path.stat(follow_symlinks=False)
        valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if (
            not valid_type
            or (not directory and info.st_nlink != 1)
            or (hasattr(os, "getuid") and info.st_uid != os.getuid())
            or (private and os.name != "nt" and info.st_mode & 0o077)
        ):
            deny("weekly_monitoring_unsafe_path")
        return path
    except OSError as exc:
        log.warning("weekly_monitoring_path_unavailable", error_type=type(exc).__name__)
        raise WorkflowError("维护文件不可读取", "weekly_monitoring_unsafe_path", 409) from exc


def _lock_identity(info):
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or info.st_mode & 0o022
        or info.st_size != 0
    ):
        deny("weekly_monitoring_unsafe_lock")
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink, info.st_size)


def validate_existing_lock(path, *, expected=None):
    """Accept the old empty 0644 flock inode only within its private parent."""
    path = Path(path)
    validate_existing_path(path.parent, directory=True, private=True)
    validate_existing_path(path)
    identity = _lock_identity(path.stat(follow_symlinks=False))
    if expected is not None and identity != expected:
        deny("weekly_monitoring_lock_changed")
    return identity


def open_existing_lock(path, expected):
    """Bind checked inode/mode to fstat and the post-open name before locking."""
    before = validate_existing_lock(path, expected=expected)
    descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = _lock_identity(os.fstat(descriptor))
        after = validate_existing_lock(path, expected=before)
        if opened != before or after != opened:
            deny("weekly_monitoring_lock_changed")
        return os.fdopen(descriptor, "r+b")
    except Exception:
        os.close(descriptor)
        raise


@dataclass(frozen=True)
class LegacyMonitoringExpectation:
    run_id: str
    session_id: str
    version: int
    owner_id: str
    run_sha256: str
    context_sha256: str
    snapshot_sha256: str
    contract_sha256: str


def _validate(catalog, expected, row, owner_check):
    if not isinstance(expected, LegacyMonitoringExpectation):
        deny("weekly_monitoring_identity_invalid")
    if (
        not re.fullmatch(r"[a-f0-9]{32}", expected.run_id)
        or not re.fullmatch(r"[a-f0-9-]{36}", expected.session_id)
        or any(
            not re.fullmatch(r"[a-f0-9]{64}", value)
            for value in (
                expected.run_sha256,
                expected.context_sha256,
                expected.snapshot_sha256,
                expected.contract_sha256,
            )
        )
    ):
        deny("weekly_monitoring_identity_invalid")
    owner = owner_check(expected.owner_id)
    if (
        not isinstance(owner, dict)
        or owner.get("id") != expected.owner_id
        or owner.get("role") != "admin"
        or owner.get("enabled") is False
    ):
        deny("weekly_monitoring_owner_invalid")
    if any(
        row.get(key) != value
        for key, value in {
            "id": expected.run_id,
            "session_id": expected.session_id,
            "version": expected.version,
            "owner_id": expected.owner_id,
            "workflow_id": "huaan-etf-weekly",
            "execution_purpose": "historical_acceptance",
            "research_submission_state": "unknown",
            "weekly_context_sha256": expected.context_sha256,
            "dataset_snapshot_sha256": expected.snapshot_sha256,
        }.items()
    ):
        deny("weekly_monitoring_identity_changed")
    if (
        "research_submission_protocol" in row
        or "weekly_execution_scope" in row
        or row.get("research_delivery_receipt")
        or row.get("research_delivery_key")
    ):
        deny("weekly_monitoring_sender_not_legacy")
    contract = row.get("weekly_data_contract")
    if not isinstance(contract, dict) or digest(contract) != expected.contract_sha256:
        deny("weekly_monitoring_contract_changed")
    root = validate_existing_path(catalog.root / "runs" / expected.run_id, directory=True)
    # The runtime catalog binds workspaces by the indexed run ID, not an
    # arbitrary persisted filesystem path. Legacy runtime rows store run_ref;
    # workspace-only rows may additionally carry path, which must not conflict.
    if row.get("run_ref") != f"runs/{expected.run_id}" or (
        "path" in row and row["path"] != str(root)
    ):
        deny("weekly_monitoring_identity_changed")
    if (root / "weekly-rpc-attempt.json").exists() or (
        root / "weekly-rpc-attempt.json"
    ).is_symlink():
        deny("weekly_monitoring_attempt_exists")
    session = catalog.root.parent / "sessions" / expected.session_id / "inputs/report-workflow"
    for path, wanted in (
        (root / "snapshots/report-data.json", expected.snapshot_sha256),
        (session / "snapshots/report-data.json", expected.snapshot_sha256),
        (session / "run-context.json", expected.context_sha256),
    ):
        validate_existing_path(path)
        if path.stat().st_size > 16 * 1024 * 1024:
            deny("weekly_monitoring_frozen_changed")
        with directory(path.parent) as folder:
            raw = read_file(folder, path.name, limit=16 * 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != wanted:
            deny("weekly_monitoring_frozen_changed")


def end_monitoring(catalog, expected, *, operation_id, owner_check, apply=False):
    """CAS control only; owner_check must be the live primary-owner resolver.

    The managed operator owns supervisor/admission/operator EX locks, exact
    source/service identity, Native idle witness and unknown journal rejection.
    After this returns it must release the catalog lock, refresh the Host run
    with GET, and invoke the original Operations.idle before any upgrade.
    """
    if not getattr(catalog, "_maintenance_only", False):
        deny("weekly_monitoring_maintenance_open_required")
    if not isinstance(expected, LegacyMonitoringExpectation):
        deny("weekly_monitoring_identity_invalid")
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,80}", operation_id):
        deny("weekly_monitoring_operation_invalid")
    with catalog._exclusive():
        row = catalog.data["runs"].get(expected.run_id)
        if not isinstance(row, dict):
            deny("run_not_found")
        _validate(catalog, expected, row, owner_check)
        prior = row.get("monitoring_end_receipt")
        if prior:
            _validate_receipt(row, prior, expected, operation_id)
            if (
                row.get("status") != "cancelled"
                or row.get("monitoring_disposition") != "ended_by_user"
            ):
                deny("weekly_monitoring_receipt_changed")
            original = copy.deepcopy(row)
            original.pop("monitoring_end_receipt")
            original.pop("monitoring_disposition")
            original["status"] = prior["previous_control"]["status"]
            if digest(original) != expected.run_sha256:
                deny("weekly_monitoring_receipt_changed")
            if apply:
                _confirm_committed(catalog, digest(catalog.data))
            return copy.deepcopy(prior)
        if (
            row.get("status") != "needs_attention"
            or "monitoring_disposition" in row
            or digest(row) != expected.run_sha256
        ):
            deny("weekly_monitoring_run_changed")
        receipt = {
            "profile": PROFILE,
            "operation_id": operation_id,
            "expected_run_sha256": expected.run_sha256,
            "run_id": expected.run_id,
            "session_id": expected.session_id,
            "version": expected.version,
            "owner_id": expected.owner_id,
            "ended_at": time.time(),
            "previous_control": {
                key: copy.deepcopy(row.get(key))
                for key in (
                    "status",
                    "monitoring_disposition",
                    "updated_at",
                )
            },
            "disposition": "ended_by_user",
            "native_cancelled": False,
        }
        if not apply:
            return {"status": "dry_run", "receipt_preview": receipt}
        old = copy.deepcopy(catalog.data)
        row.update(
            status="cancelled",
            monitoring_disposition="ended_by_user",
            monitoring_end_receipt=receipt,
        )
        intended = digest(catalog.data)
        try:
            catalog._save()
        except Exception as exc:
            # replace/fsync can fail after publication. Re-read inside the lock;
            # never blindly overwrite the durable decision with old memory.
            catalog._reload()
            actual = digest(catalog.data)
            if actual == intended:
                _confirm_committed(catalog, intended)
                log.warning(
                    "weekly_monitoring_write_committed_readback", error_type=type(exc).__name__
                )
                return copy.deepcopy(receipt)
            if actual != digest(old):
                deny("weekly_monitoring_save_indeterminate")
            raise
        catalog._reload()
        if digest(catalog.data) != intended:
            deny("weekly_monitoring_save_indeterminate")
        log.info(
            "weekly_legacy_monitoring_ended", run_id=expected.run_id, operation_id=operation_id
        )
        return copy.deepcopy(receipt)


def _timestamp(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _validate_receipt(row, prior, expected, operation_id):
    """An existing receipt cannot authorize a changed identity or disposition."""
    if not isinstance(prior, dict):
        deny("weekly_monitoring_receipt_changed")
    if (
        prior.get("operation_id") != operation_id
        or prior.get("expected_run_sha256") != expected.run_sha256
    ):
        deny("weekly_monitoring_operation_conflict")
    binding = {
        "profile": PROFILE,
        "operation_id": operation_id,
        "expected_run_sha256": expected.run_sha256,
        "run_id": expected.run_id,
        "session_id": expected.session_id,
        "version": expected.version,
        "owner_id": expected.owner_id,
        "disposition": "ended_by_user",
        "native_cancelled": False,
    }
    control = {
        "status": "needs_attention",
        "monitoring_disposition": None,
        "updated_at": row.get("updated_at"),
    }
    if (
        set(prior) != set(binding) | {"ended_at", "previous_control"}
        or any(prior.get(key) != value for key, value in binding.items())
        or type(prior.get("version")) is not int
        or prior.get("native_cancelled") is not False
        or not isinstance(prior.get("previous_control"), dict)
        or digest(prior["previous_control"]) != digest(control)
        or not _timestamp(prior.get("ended_at"))
    ):
        deny("weekly_monitoring_receipt_changed")
    updated = control["updated_at"]
    if updated is not None and (not _timestamp(updated) or prior["ended_at"] < updated):
        deny("weekly_monitoring_receipt_changed")


def _sync_catalog_directory(catalog):
    """Confirm durability after an uncertain replace or directory-fsync return."""
    descriptor = os.open(catalog.root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _confirm_committed(catalog, intended):
    try:
        _sync_catalog_directory(catalog)
    except OSError as exc:
        log.error("weekly_monitoring_committed_unconfirmed", error_type=type(exc).__name__)
        raise WorkflowError(
            "结束等待决定已写入但持久性未确认；禁止回写旧索引",
            "weekly_monitoring_committed_unconfirmed",
            503,
        ) from exc
    catalog._reload()
    if digest(catalog.data) != intended:
        deny("weekly_monitoring_save_indeterminate")
