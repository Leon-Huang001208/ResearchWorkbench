"""Explicit, process-isolated macOS Office and Wind verification."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any, Callable
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)
VERIFICATION_TIMEOUT_SECONDS = 180.0
# The report workbook worker may need up to about seven seconds to terminate
# its process group and the exact Excel PID it reported. Keep that cleanup
# inside the outer verifier lifetime so a provider timeout cannot orphan Excel.
PROCESS_COORDINATION_GRACE_SECONDS = 10.0
MAX_VERIFICATION_RUNS = 16
MAX_VERIFICATION_STORAGE_BYTES = 512 * 1024 * 1024
VERIFICATION_RUN_RETENTION_SECONDS = 24 * 60 * 60
SAFE_RUN_NAME = re.compile(r"^[0-9a-f]{32}$")


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


def _remove_run_directory(path: Path) -> bool:
    try:
        path.lstat()
        if path.is_symlink() or not path.is_dir() or not SAFE_RUN_NAME.fullmatch(path.name):
            log.warning("local_verification_run_cleanup_refused")
            return False
        shutil.rmtree(path)
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        log.warning(
            "local_verification_run_cleanup_failed",
            error_type=type(exc).__name__,
        )
        return False


def _run_directory_size(path: Path) -> int:
    total = 0
    for root, directories, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in (*directories, *files):
            metadata = (root_path / name).lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise OSError("unsafe verification run entry")
            if stat.S_ISREG(metadata.st_mode):
                total += metadata.st_size
            elif not stat.S_ISDIR(metadata.st_mode):
                raise OSError("unsafe verification run entry")
    return total


def _prepare_run_directory(state_root: Path) -> tuple[Path | None, str | None]:
    runs = state_root / "verification-runs"
    try:
        if runs.exists() or runs.is_symlink():
            runs.lstat()
            if runs.is_symlink() or not runs.is_dir():
                return None, "verification_storage_unsafe"
        else:
            runs.mkdir(parents=True, exist_ok=False, mode=0o700)
        candidates: list[tuple[int, int, Path]] = []
        for entry in runs.iterdir():
            metadata = entry.lstat()
            if entry.is_symlink() or not entry.is_dir() or not SAFE_RUN_NAME.fullmatch(entry.name):
                return None, "verification_storage_unsafe"
            candidates.append((metadata.st_mtime_ns, _run_directory_size(entry), entry))
        candidates.sort(key=lambda pair: pair[0])
        cutoff_ns = time.time_ns() - VERIFICATION_RUN_RETENTION_SECONDS * 1_000_000_000
        retained: list[tuple[int, int, Path]] = []
        retained_bytes = 0
        for modified_ns, size, entry in candidates:
            if modified_ns < cutoff_ns:
                if not _remove_run_directory(entry):
                    return None, "verification_cleanup_failed"
            else:
                retained.append((modified_ns, size, entry))
                retained_bytes += size
        while len(retained) >= MAX_VERIFICATION_RUNS or (
            retained and retained_bytes > MAX_VERIFICATION_STORAGE_BYTES
        ):
            _, size, oldest = retained.pop(0)
            if not _remove_run_directory(oldest):
                return None, "verification_cleanup_failed"
            retained_bytes -= size
        return runs / uuid4().hex, None
    except OSError as exc:
        log.warning(
            "local_verification_storage_prepare_failed",
            error_type=type(exc).__name__,
        )
        return None, "verification_storage_unsafe"


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


def _office_documents_root(target: str) -> Path:
    bundle = {
        "excel": "com.microsoft.Excel",
        "word": "com.microsoft.Word",
        "powerpoint": "com.microsoft.PowerPoint",
    }[target]
    return Path.home() / "Library/Containers" / bundle / "Data/Documents"


def _office_artifact_path(target: str, run_root: Path) -> Path:
    documents_root = _office_documents_root(target)
    metadata = documents_root.lstat()
    if documents_root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("unsafe Office documents root")
    if not SAFE_RUN_NAME.fullmatch(run_root.name):
        raise OSError("unsafe verification run identifier")
    token = run_root.name
    suffix = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}[target]
    return documents_root / f"research-workbench-{token}{suffix}"


def _remove_office_artifact(target: str, run_root: Path) -> bool:
    try:
        path = _office_artifact_path(target, run_root)
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return True
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            log.warning("local_office_verification_cleanup_refused", target=target)
            return False
        path.unlink()
        return True
    except OSError as exc:
        log.warning(
            "local_office_verification_cleanup_failed",
            target=target,
            error_type=type(exc).__name__,
        )
        return False


def _verify_excel_macos(
    run_root: Path,
    process_reporter: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    path: Path | None = None
    app = book = None
    result: dict[str, Any] = {
        "outcome": "failed",
        "code": "office_verification_failed",
    }
    try:
        path = _office_artifact_path("excel", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            return {"outcome": "failed", "code": "verification_storage_unsafe"}
        from openpyxl import Workbook

        seed = Workbook()
        try:
            seed.save(path)
        finally:
            seed.close()
        import xlwings as xw

        app = xw.App(visible=False, add_book=False)
        if process_reporter is not None:
            from app.research_web.report_workflows.workbook import (
                _capture_excel_process_identity,
            )

            excel_pid = getattr(app, "pid", None)
            identity = (
                _capture_excel_process_identity(excel_pid) if isinstance(excel_pid, int) else None
            )
            if identity is None:
                raise RuntimeError("excel_process_identity_unavailable")
            process_reporter(identity)
        book = app.books.open(str(path), update_links=False, read_only=False)
        sheet = book.sheets[0]
        sheet.range("A1").value = 19
        sheet.range("A2").value = 23
        sheet.range("A3").formula = "=A1+A2"
        full_rebuild = getattr(getattr(app, "api", None), "calculate_full_rebuild", None)
        if not callable(full_rebuild):
            result = {
                "outcome": "formula_error",
                "code": "excel_full_rebuild_unavailable",
            }
        else:
            full_rebuild()
            book.save()
            book.close()
            book = app.books.open(str(path), update_links=False, read_only=True)
            value = book.sheets[0].range("A3").value
            result = (
                {"outcome": "available", "code": None}
                if value == 42
                else {"outcome": "formula_error", "code": "excel_calculation_failed"}
            )
    except Exception as exc:  # noqa: BLE001 - proprietary automation errors are unstable.
        log.warning("local_excel_verification_failed", error_type=type(exc).__name__)
        result = _permission_outcome(str(exc))
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
                result = {"outcome": "failed", "code": "cleanup_failed"}
        if path is not None and not _remove_office_artifact("excel", run_root):
            result = {"outcome": "failed", "code": "cleanup_failed"}
    return result


def _verify_excel(
    run_root: Path,
    process_reporter: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if sys.platform == "darwin":
        return _verify_excel_macos(run_root, process_reporter)
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
    try:
        path = _office_artifact_path("word", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            return {"outcome": "failed", "code": "verification_storage_unsafe"}
        from docx import Document

        seed = Document()
        seed.add_paragraph("Research Workbench seed")
        seed.save(str(path))
    except (ImportError, OSError) as exc:
        log.warning("local_word_verification_prepare_failed", error_type=type(exc).__name__)
        return {"outcome": "failed", "code": "office_verification_failed"}
    script = """on run argv
set smokeDocument to missing value
set reopenedDocument to missing value
set targetFile to POSIX file (item 1 of argv)
set targetName to item 2 of argv
tell application "Microsoft Word"
try
open targetFile
set smokeDocument to document targetName
set content of text object of smokeDocument to "Research Workbench verification"
save smokeDocument
close smokeDocument saving no
set smokeDocument to missing value
open targetFile
set reopenedDocument to document targetName
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
    result = _run_osascript(script, str(path), path.name)
    if not _remove_office_artifact("word", run_root):
        return {"outcome": "failed", "code": "cleanup_failed"}
    return result


def _verify_powerpoint(run_root: Path) -> dict[str, Any]:
    try:
        path = _office_artifact_path("powerpoint", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            return {"outcome": "failed", "code": "verification_storage_unsafe"}
        from pptx import Presentation

        seed = Presentation()
        slide = seed.slides.add_slide(seed.slide_layouts[0])
        slide.shapes.title.text = "Research Workbench seed"
        seed.save(str(path))
    except (ImportError, OSError) as exc:
        log.warning(
            "local_powerpoint_verification_prepare_failed",
            error_type=type(exc).__name__,
        )
        return {"outcome": "failed", "code": "office_verification_failed"}
    script = """on run argv
set smokePresentation to missing value
set reopenedPresentation to missing value
set targetFile to POSIX file (item 1 of argv)
set targetName to item 2 of argv
tell application "Microsoft PowerPoint"
try
open targetFile
set smokePresentation to presentation targetName
set content of text range of text frame of shape 1 of slide 1 of smokePresentation to "Research Workbench verification"
save smokePresentation
close smokePresentation
set smokePresentation to missing value
open targetFile
set reopenedPresentation to presentation targetName
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
    result = _run_osascript(script, str(path), path.name)
    if not _remove_office_artifact("powerpoint", run_root):
        return {"outcome": "failed", "code": "cleanup_failed"}
    return result


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
            "excel": lambda: _verify_excel(
                root,
                lambda identity: results.put({"status": "started", "child_processes": [identity]}),
            ),
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
    run_root, storage_error = _prepare_run_directory(state_root)
    if run_root is None:
        return {"outcome": "failed", "code": storage_error or "verification_storage_unsafe"}
    from app.research_web.report_workflows.workbook import (
        _drain_worker_messages,
        _terminate_managed_excel_processes,
        _worker_child_processes,
    )

    context = multiprocessing.get_context("spawn")
    results = context.Queue(maxsize=4)
    process = context.Process(
        target=_child,
        args=(target, str(state_root.parent), str(run_root), results),
        name=f"local-verification-{target}",
    )
    try:
        process.start()
        deadline = time.monotonic() + (
            VERIFICATION_TIMEOUT_SECONDS + PROCESS_COORDINATION_GRACE_SECONDS
        )
        while process.is_alive():
            if cancellation_event is not None and cancellation_event.is_set():
                messages = _drain_worker_messages(results, wait=True)
                worker_cleaned = _terminate_process_tree(process)
                children_cleaned = _terminate_managed_excel_processes(
                    _worker_child_processes(messages)
                )
                cleaned = worker_cleaned and children_cleaned
                return {
                    "outcome": "failed",
                    "code": "verification_cancelled" if cleaned else "cleanup_failed",
                }
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                messages = _drain_worker_messages(results, wait=True)
                worker_cleaned = _terminate_process_tree(process)
                children_cleaned = _terminate_managed_excel_processes(
                    _worker_child_processes(messages)
                )
                cleaned = worker_cleaned and children_cleaned
                return {
                    "outcome": "timeout" if cleaned else "failed",
                    "code": "verification_timed_out" if cleaned else "cleanup_failed",
                }
            process.join(min(0.25, remaining))
        messages = _drain_worker_messages(results, wait=True)
        child_processes = _worker_child_processes(messages)
        outcomes = [message for message in messages if message.get("status") != "started"]
        if not _terminate_managed_excel_processes(child_processes):
            return {"outcome": "failed", "code": "cleanup_failed"}
        if not outcomes:
            return {"outcome": "failed", "code": "verification_failed"}
        return outcomes[-1]
    finally:
        results.close()
        results.join_thread()
        if target in {"excel", "word", "powerpoint"} and not _remove_office_artifact(
            target, run_root
        ):
            log.warning("local_office_verification_artifact_retained", target=target)
        if not _remove_run_directory(run_root):
            log.warning("local_verification_run_retained")
