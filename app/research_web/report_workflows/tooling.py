"""Deterministic report Workflow tools that prepare one shared data snapshot."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from core.observability import get_logger

from .models import ReportWorkflowManifest, WorkflowError
from .workbook import read_cached_workbook

log = get_logger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def materialize_report_snapshot(
    run_root: Path,
    manifest: ReportWorkflowManifest,
    refresh_manifests: list[str],
) -> dict:
    """Extract refreshed workbooks into one immutable, hash-addressed snapshot."""

    root = Path(run_root).resolve()
    workbooks = []
    for policy in manifest.workbook_policies:
        logical = PurePosixPath(policy.workbook)
        workbook = root.joinpath(*logical.parts)
        if (
            workbook.is_symlink()
            or not workbook.is_file()
            or not workbook.resolve().is_relative_to(root)
        ):
            raise WorkflowError("刷新底稿不存在", "refreshed_workbook_missing", 409)
        cells, errors, date_1904 = read_cached_workbook(workbook)
        if errors:
            raise WorkflowError("刷新底稿仍包含公式错误", "formula_error", 409)
        workbooks.append(
            {
                "path": logical.as_posix(),
                "sha256": _sha256(workbook),
                "date_system": "1904" if date_1904 else "1900",
                "cells": {
                    key: _json_value(value)
                    for key, value in sorted(cells.items())
                    if value is not None
                },
            }
        )
    refresh_rows = []
    for reference in refresh_manifests:
        logical = PurePosixPath(reference)
        if logical.is_absolute() or logical.parts[:1] != ("refresh-manifests",):
            raise WorkflowError("刷新清单引用无效", "refresh_manifest_invalid", 409)
        path = root.joinpath(*logical.parts)
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(root)
        ):
            raise WorkflowError("刷新清单引用无效", "refresh_manifest_invalid", 409)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(
                "刷新清单不可读取", "refresh_manifest_invalid", 409
            ) from exc
        refresh_rows.append(value)
    content = {
        "schema_version": 1,
        "workflow_id": manifest.workflow_id,
        "workflow_version": manifest.version,
        "workbooks": workbooks,
        "refresh_manifests": refresh_rows,
    }
    canonical = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    snapshot_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload = {**content, "snapshot_sha256": snapshot_sha256}
    target = root / "snapshots" / "report-data.json"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="report-data-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except OSError as exc:
        log.warning("report_snapshot_write_failed", error_type=type(exc).__name__)
        raise WorkflowError(
            "报告数据快照无法保存", "snapshot_write_failed", 503
        ) from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    log.info(
        "report_snapshot_ready",
        workflow_id=manifest.workflow_id,
        workbook_count=len(workbooks),
    )
    return {
        "path": "snapshots/report-data.json",
        "sha256": snapshot_sha256,
        "workbook_count": len(workbooks),
    }
