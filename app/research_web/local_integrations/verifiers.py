"""Explicit, process-isolated macOS Office and Wind verification."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import queue
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)
VERIFICATION_TIMEOUT_SECONDS = 180.0
PROCESS_COORDINATION_GRACE_SECONDS = 1.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _permission_outcome(stderr: str) -> dict[str, Any]:
    lowered = stderr.lower()
    if any(value in lowered for value in ("not authorized", "-1743", "permission")):
        return {"outcome": "authorization_required", "code": "automation_permission_required"}
    return {"outcome": "failed", "code": "office_verification_failed"}


def _run_osascript(script: str, *arguments: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", script, *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        log.warning("local_office_verification_start_failed", error_type=type(exc).__name__)
        return {"outcome": "failed", "code": "office_verification_failed"}
    if completed.returncode:
        return _permission_outcome(completed.stderr)
    return {"outcome": "available", "code": None}


def _verify_excel(run_root: Path) -> dict[str, Any]:
    path = run_root / "excel-smoke.xlsx"
    app = book = None
    try:
        import xlwings as xw

        app = xw.App(visible=False, add_book=True)
        book = app.books.active
        sheet = book.sheets[0]
        sheet.range("A1").value = 19
        sheet.range("A2").value = 23
        sheet.range("A3").formula = "=A1+A2"
        app_api = getattr(app, "api", None)
        method_name = (
            "calculate_full_rebuild" if sys.platform == "darwin" else "CalculateFullRebuild"
        )
        full_rebuild = getattr(app_api, method_name, None)
        if not callable(full_rebuild):
            return {"outcome": "formula_error", "code": "excel_full_rebuild_unavailable"}
        full_rebuild()
        book.save(str(path))
        book.close()
        book = app.books.open(str(path), update_links=False, read_only=True)
        value = book.sheets[0].range("A3").value
        return (
            {"outcome": "available", "code": None}
            if value == 42
            else {"outcome": "formula_error", "code": "excel_calculation_failed"}
        )
    except Exception as exc:  # noqa: BLE001 - proprietary automation errors are unstable.
        log.warning("local_excel_verification_failed", error_type=type(exc).__name__)
        return _permission_outcome(str(exc))
    finally:
        if book is not None:
            try:
                book.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("local_excel_book_close_failed", error_type=type(exc).__name__)
        if app is not None:
            try:
                app.quit()
            except Exception as exc:  # noqa: BLE001
                log.warning("local_excel_app_close_failed", error_type=type(exc).__name__)


def _verify_word(run_root: Path) -> dict[str, Any]:
    path = str(run_root / "word-smoke.docx")
    script = """on run argv
set smokeDocument to missing value
set reopenedDocument to missing value
tell application "Microsoft Word"
try
set targetFile to POSIX file (item 1 of argv)
set smokeDocument to make new document
set content of text object of smokeDocument to "Research Workbench verification"
save as smokeDocument file name targetFile file format format document
close smokeDocument saving no
set smokeDocument to missing value
set reopenedDocument to open targetFile
set verifiedText to content of text object of reopenedDocument
close reopenedDocument saving no
set reopenedDocument to missing value
if verifiedText does not contain "Research Workbench verification" then error "verification failed"
on error errorMessage number errorNumber
if reopenedDocument is not missing value then close reopenedDocument saving no
if smokeDocument is not missing value then close smokeDocument saving no
error errorMessage number errorNumber
end try
end tell
end run"""
    return _run_osascript(script, path)


def _verify_powerpoint(run_root: Path) -> dict[str, Any]:
    path = str(run_root / "powerpoint-smoke.pptx")
    script = """on run argv
set smokePresentation to missing value
set reopenedPresentation to missing value
tell application "Microsoft PowerPoint"
try
set targetFile to POSIX file (item 1 of argv)
set smokePresentation to make new presentation
make new slide at end of slides of smokePresentation with properties {layout:slide layout title}
set content of text range of text frame of shape 1 of slide 1 of smokePresentation to "Research Workbench verification"
save smokePresentation in targetFile as save as Open XML presentation
close smokePresentation
set smokePresentation to missing value
set reopenedPresentation to open targetFile
set verifiedText to content of text range of text frame of shape 1 of slide 1 of reopenedPresentation
close reopenedPresentation
set reopenedPresentation to missing value
if verifiedText does not contain "Research Workbench verification" then error "verification failed"
on error errorMessage number errorNumber
if reopenedPresentation is not missing value then close reopenedPresentation
if smokePresentation is not missing value then close smokePresentation
error errorMessage number errorNumber
end try
end tell
end run"""
    return _run_osascript(script, path)


def _verify_wind(data_root: Path, run_root: Path) -> dict[str, Any]:
    from app.research_web.report_workflows.catalog import ReportWorkflowService
    from app.research_web.report_workflows.models import RefreshStatus, WorkbookFormulaProvider
    from app.research_web.report_workflows.workbook import (
        WorkbookRefreshService,
        scan_workbook_formulas,
    )

    try:
        catalog = ReportWorkflowService(data_root)
        row = catalog._row("huaan-etf-weekly")
        version = row.get("current_version")
        if not isinstance(version, int):
            return {"outcome": "failed", "code": "workflow_version_unavailable"}
        manifest = catalog.manifest("huaan-etf-weekly", version)
        policies = []
        for policy in manifest.workbook_policies:
            source = catalog.resource_path("huaan-etf-weekly", version, policy.workbook)
            if scan_workbook_formulas(source).provider in {
                WorkbookFormulaProvider.WIND,
                WorkbookFormulaProvider.MIXED,
            }:
                policies.append((policy, source))
        if not policies:
            return {"outcome": "failed", "code": "wind_workbook_unavailable"}
        policies.sort(key=lambda pair: (len(pair[0].required_cells), pair[0].workbook))
        service = WorkbookRefreshService()
        deadline = time.monotonic() + VERIFICATION_TIMEOUT_SECONDS
        phases = (("smoke", policies[:1]), ("full", policies))
        for phase, selected_policies in phases:
            for policy, source in selected_policies:
                remaining = deadline - time.monotonic()
                if remaining <= PROCESS_COORDINATION_GRACE_SECONDS:
                    return {"outcome": "timeout", "code": "verification_timed_out"}
                policy_timeout = min(
                    float(policy.timeout_seconds),
                    remaining - PROCESS_COORDINATION_GRACE_SECONDS,
                )
                bounded_policy = policy.model_copy(update={"timeout_seconds": policy_timeout})
                before = _sha256(source)
                try:
                    result = service.refresh(source, run_root / phase, bounded_policy)
                except Exception:
                    if _sha256(source) != before:
                        return {"outcome": "failed", "code": "source_hash_changed"}
                    raise
                if _sha256(source) != before:
                    return {"outcome": "failed", "code": "source_hash_changed"}
                if result.status is not RefreshStatus.READY:
                    code = result.code or "wind_refresh_failed"
                    if code in {"provider_timeout", "refresh_lock_timeout"}:
                        return {"outcome": "timeout", "code": "verification_timed_out"}
                    if code in {"provider_not_ready", "xlwings_missing"}:
                        return {"outcome": "login_required", "code": "vendor_login_required"}
                    if code in {"formula_error", "required_cell_missing", "required_cell_zero"}:
                        return {"outcome": "formula_error", "code": "wind_formula_failed"}
                    return {"outcome": "failed", "code": "wind_refresh_failed"}
        return {"outcome": "available", "code": None}
    except Exception as exc:  # noqa: BLE001 - normalize catalog and vendor failures.
        log.warning("local_wind_verification_failed", error_type=type(exc).__name__)
        return _permission_outcome(str(exc))


def _child(target: str, data_root: str, run_root: str, results) -> None:
    try:
        if os.name == "posix":
            os.setsid()
        root = Path(run_root)
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        outcome = {
            "excel": lambda: _verify_excel(root),
            "word": lambda: _verify_word(root),
            "powerpoint": lambda: _verify_powerpoint(root),
            "wind_excel": lambda: _verify_wind(Path(data_root), root),
        }[target]()
        results.put(outcome)
    except Exception as exc:  # noqa: BLE001 - child process is a hard boundary.
        log.warning("local_verification_child_failed", error_type=type(exc).__name__)
        results.put({"outcome": "failed", "code": "verification_failed"})


def _terminate_process_tree(process, *, platform_name: str = os.name) -> bool:
    """Terminate the worker and descendants without leaking vendor processes."""

    process_group: int | None = None
    if platform_name == "posix":
        try:
            process_group = os.getpgid(process.pid)
            if process_group != process.pid:
                raise OSError("verification worker has no private process group")
            os.killpg(process_group, signal.SIGTERM)
        except (OSError, ProcessLookupError) as exc:
            log.warning(
                "local_verification_process_group_terminate_failed",
                error_type=type(exc).__name__,
            )
            process.terminate()
    elif platform_name == "nt":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=10,
            )
            if completed.returncode != 0:
                process.terminate()
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning(
                "local_verification_process_tree_terminate_failed",
                error_type=type(exc).__name__,
            )
            process.terminate()
    else:
        process.terminate()
    process.join(5)
    try:
        if process_group is not None:
            # The worker may have exited while a vendor grandchild remains in
            # its private group, so group KILL must not depend on root liveness.
            os.killpg(process_group, signal.SIGKILL)
        elif process.is_alive() and hasattr(process, "kill"):
            process.kill()
        elif process.is_alive():
            process.terminate()
    except (OSError, ProcessLookupError) as exc:
        log.warning(
            "local_verification_process_tree_kill_failed",
            error_type=type(exc).__name__,
        )
    process.join(2)
    return not process.is_alive()


def verify_target(
    target: str,
    state_root: Path,
    *,
    cancellation_event: Event | None = None,
) -> dict[str, Any]:
    """Run an allowlisted verification in a terminable spawned process."""

    if target not in {"excel", "word", "powerpoint", "wind_excel"}:
        return {"outcome": "failed", "code": "verification_target_invalid"}
    if sys.platform != "darwin":
        return {"outcome": "failed", "code": "unsupported_platform"}
    state_root = Path(state_root)
    runs = state_root / "verification-runs"
    if runs.is_symlink():
        return {"outcome": "failed", "code": "verification_storage_unsafe"}
    runs.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_root = runs / uuid4().hex
    context = multiprocessing.get_context("spawn")
    results = context.Queue(maxsize=1)
    process = context.Process(
        target=_child,
        args=(target, str(state_root.parent), str(run_root), results),
        name=f"local-verification-{target}",
    )
    process.start()
    deadline = time.monotonic() + (
        VERIFICATION_TIMEOUT_SECONDS + PROCESS_COORDINATION_GRACE_SECONDS
    )
    while process.is_alive():
        if cancellation_event is not None and cancellation_event.is_set():
            cleaned = _terminate_process_tree(process)
            results.close()
            results.join_thread()
            shutil.rmtree(run_root, ignore_errors=True)
            return {
                "outcome": "failed",
                "code": "verification_cancelled" if cleaned else "cleanup_failed",
            }
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            cleaned = _terminate_process_tree(process)
            results.close()
            results.join_thread()
            shutil.rmtree(run_root, ignore_errors=True)
            return {
                "outcome": "timeout" if cleaned else "failed",
                "code": "verification_timed_out" if cleaned else "cleanup_failed",
            }
        process.join(min(0.25, remaining))
    try:
        return results.get_nowait()
    except queue.Empty:
        return {"outcome": "failed", "code": "verification_failed"}
    finally:
        results.close()
        results.join_thread()
        shutil.rmtree(run_root, ignore_errors=True)
