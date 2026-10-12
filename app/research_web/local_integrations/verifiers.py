"""Explicit, process-isolated macOS Office and Wind verification."""

from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from typing import Any
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
OFFICE_PHASES = frozenset(
    {
        "prepared",
        "application_response",
        "created",
        "opened",
        "read",
        "written",
        "saved",
        "closed",
        "reopened",
        "read_back",
        "document_closed",
        "cleanup",
    }
)


def _record_office_phase(target: str, run_root: Path, stage: str, phase: str) -> None:
    if (
        target not in {"word", "excel", "powerpoint"}
        or stage not in OFFICE_PHASES
        or phase not in {"started", "completed"}
    ):
        raise ValueError("invalid Office phase")
    descriptor = os.open(
        run_root / f"{target}-phases.jsonl",
        os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
    )
    with os.fdopen(descriptor, "a") as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_size > 16384
        ):
            raise OSError("unsafe Office phase record")
        stream.write(json.dumps({"stage": stage, "phase": phase, "at": int(time.time())}) + "\n")


def _read_office_phases(target: str, run_root: Path) -> list[dict]:
    observations: list[dict] = []
    try:
        descriptor = os.open(
            run_root / f"{target}-phases.jsonl", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
        with os.fdopen(descriptor) as stream:
            metadata = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or metadata.st_size > 16384
            ):
                return []
            records = stream.read(16385).splitlines()
        if len(records) > 64:
            return []
        for text in records:
            value = json.loads(text)
            if not isinstance(value, dict) or set(value) != {"stage", "phase", "at"}:
                return []
            stage, phase, stamp = value["stage"], value["phase"], value["at"]
            if (
                not isinstance(stage, str)
                or stage not in OFFICE_PHASES
                or not isinstance(phase, str)
                or phase not in {"started", "completed"}
                or type(stamp) not in {int, float}
                or not 0 <= stamp <= time.time() + 5
                or not math.isfinite(stamp)
            ):
                return []
            if phase == "started":
                observations.append(
                    {
                        "stage": stage,
                        "status": "started",
                        "started_at": stamp,
                        "completed_at": None,
                        "elapsed_seconds": None,
                    }
                )
            else:
                current = next(
                    (
                        item
                        for item in reversed(observations)
                        if item["stage"] == stage and item["status"] == "started"
                    ),
                    None,
                )
                if current is None or stamp < current["started_at"]:
                    return []
                current.update(
                    status="completed",
                    completed_at=stamp,
                    elapsed_seconds=round(stamp - current["started_at"], 3),
                )
        return observations
    except (OSError, ValueError, TypeError):
        return []


def _office_phase_timeout(target: str, run_root: Path, began: float) -> str | None:
    phases = _read_office_phases(target, run_root)
    if not phases:
        return "prepared" if time.time() - began >= 10 else None
    current = phases[-1]
    if current["status"] != "started":
        return None
    limit = 10 if current["stage"] == "prepared" else 30
    return current["stage"] if time.time() - current["started_at"] >= limit else None


def _instrument_office_script(script: str, target: str) -> str:
    """Add finite metadata to reviewed static scripts; never record content."""
    if target not in {"word", "powerpoint"}:
        raise ValueError("unsupported Office script target")
    application = "Microsoft Word" if target == "word" else "Microsoft PowerPoint"
    starts = {
        "set smokeDocument to make new document": "created",
        "set smokePresentation to make new presentation": "created",
        'set content of text object of smokeDocument to "Research Workbench verification"': "written",
        "set smokeSlide to make new slide at end of smokePresentation with properties {layout:slide layout title slide}": "written",
        "save as smokeDocument file name (targetFile as text) file format format document default": "saved",
        "save smokePresentation in targetFile": "saved",
        "close smokeDocument saving no": "closed",
        "close smokePresentation": "closed",
        "open targetFile": "reopened",
        "set verifiedText to content of text object of reopenedDocument": "read_back",
        "set verifiedText to content of text range of text frame of shape 1 of slide 1 of reopenedPresentation": "read_back",
        "close reopenedDocument saving no": "document_closed",
        "close reopenedPresentation": "document_closed",
    }
    lines = []
    for line in script.splitlines():
        if line in starts:
            lines.append(f'my recordStage("{starts[line]}", "started", rwbPhaseFile)')
        lines.append(line)
        if line.startswith('do shell script "/usr/bin/printf %s '):
            lines.append('my recordStage(stepName, "completed", rwbPhaseFile)')
        if line == "on run argv":
            lines.append("set rwbPhaseFile to item 4 of argv")
        if line == f'tell application "{application}"':
            lines.extend(
                ["get version", 'my recordStage("application_response", "completed", rwbPhaseFile)']
            )
        if line == "on error errorMessage number errorNumber":
            lines.append('my recordStage("document_closed", "started", rwbPhaseFile)')
    helpers = r"""
on recordStage(stageName, phaseName, phasePath)
set stamp to do shell script "/bin/date +%s"
set entry to "{\"stage\":\"" & stageName & "\",\"phase\":\"" & phaseName & "\",\"at\":" & stamp & "}"
do shell script "/usr/bin/printf '%s\n' " & quoted form of entry & " >> " & quoted form of phasePath
end recordStage
"""
    return 'property rwbPhaseFile : ""\n' + "\n".join(lines) + "\n" + helpers


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _office_error_number(stderr: str) -> int | None:
    match = re.search(r"(?:\((-?\d{1,6})\)|number\s+(-?\d{1,6}))\s*$", stderr.strip())
    return int(match.group(1) or match.group(2)) if match else None


def _permission_outcome(stderr: str) -> dict[str, Any]:
    number = _office_error_number(stderr)
    if number == -1743:
        return {"outcome": "authorization_required", "code": "automation_permission_required"}
    if number in {-54, -61}:
        return {"outcome": "failed", "code": "office_file_access_denied"}
    if number == -1712:
        return {"outcome": "timeout", "code": "office_event_timed_out"}
    if number == -600:
        return {"outcome": "failed", "code": "office_application_not_running"}
    if number == -128:
        return {"outcome": "failed", "code": "office_user_cancelled"}
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
            if modified_ns < cutoff_ns and not any(
                (entry / f"{target}-step.txt").exists()
                for target in ("word", "excel", "powerpoint")
            ):
                if not _remove_run_directory(entry):
                    return None, "verification_cleanup_failed"
            else:
                retained.append((modified_ns, size, entry))
                retained_bytes += size
        while len(retained) >= MAX_VERIFICATION_RUNS or (
            retained and retained_bytes > MAX_VERIFICATION_STORAGE_BYTES
        ):
            disposable = next(
                (
                    index
                    for index, (_, _, entry) in enumerate(retained)
                    if not any(
                        (entry / f"{target}-step.txt").exists()
                        for target in ("word", "excel", "powerpoint")
                    )
                ),
                None,
            )
            if disposable is None:
                log.warning("local_word_verification_cleanup_pending")
                return None, "verification_cleanup_pending"
            _, size, oldest = retained.pop(disposable)
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
        result = _permission_outcome(completed.stderr)
        number = _office_error_number(completed.stderr)
        if number is not None:
            result["native_error_number"] = number
        log.warning("local_office_command_failed", error_number=number, code=result["code"])
        return result
    return {"outcome": "available", "code": None}


def _office_documents_root(target: str) -> Path:
    bundle = {
        "excel": "com.microsoft.Excel",
        "word": "com.microsoft.Word",
        "powerpoint": "com.microsoft.Powerpoint",
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
        root_metadata = run_root.lstat()
        if (
            run_root.is_symlink()
            or not stat.S_ISDIR(root_metadata.st_mode)
            or root_metadata.st_uid != os.getuid()
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_size > 30 * 1024 * 1024
        ):
            raise OSError("unsafe registered Office artifact")
        # Preserve only the closed, registered synthetic document in the existing
        # private run store before cleaning its sandbox copy.
        with ExitStack() as stack:
            root_fd = os.open(run_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, root_fd)
            opened_root = os.fstat(root_fd)
            if (opened_root.st_dev, opened_root.st_ino) != (
                root_metadata.st_dev,
                root_metadata.st_ino,
            ):
                raise OSError("archive directory changed before open")
            source = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(source, "rb") as reader:
                identity = os.fstat(reader.fileno())
                if (identity.st_dev, identity.st_ino) != (metadata.st_dev, metadata.st_ino):
                    raise OSError("Office artifact changed before archive")
                destination = os.open(
                    path.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=root_fd,
                )
                with os.fdopen(destination, "wb") as writer:
                    remaining = metadata.st_size
                    while remaining:
                        chunk = reader.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            raise OSError("Office artifact truncated during archive")
                        writer.write(chunk)
                        remaining -= len(chunk)
                    writer.flush()
                    os.fsync(writer.fileno())
                    saved = os.fstat(writer.fileno())
                    visible = os.stat(path.name, dir_fd=root_fd, follow_symlinks=False)
                    if (
                        not stat.S_ISREG(saved.st_mode)
                        or saved.st_uid != os.getuid()
                        or saved.st_nlink != 1
                        or saved.st_size != metadata.st_size
                        or (saved.st_dev, saved.st_ino) != (visible.st_dev, visible.st_ino)
                    ):
                        raise OSError("archive identity unavailable")
                current = path.lstat()
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_size,
                    metadata.st_mtime_ns,
                ):
                    raise OSError("Office artifact changed during archive")
            visible_root = run_root.lstat()
            if run_root.is_symlink() or (visible_root.st_dev, visible_root.st_ino) != (
                root_metadata.st_dev,
                root_metadata.st_ino,
            ):
                raise OSError("archive directory changed before source cleanup")
        path.unlink()
        log.info("local_office_verification_artifact_archived", target=target)
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
    artifact_owned = False
    progress = run_root / "excel-step.txt"
    app = book = None
    result: dict[str, Any] = {
        "outcome": "failed",
        "code": "office_verification_failed",
    }
    try:
        _record_office_phase("excel", run_root, "prepared", "started")
        descriptor = os.open(progress, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write("none")
        path = _office_artifact_path("excel", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            result = {"outcome": "failed", "code": "verification_storage_unsafe"}
            return result
        from openpyxl import Workbook

        seed = Workbook()
        try:
            artifact_owned = True
            seed.save(path)
            progress.write_text("prepared")
            _record_office_phase("excel", run_root, "prepared", "completed")
        finally:
            seed.close()
        from app.research_web.report_workflows.workbook import XlwingsExcelProvider

        _record_office_phase("excel", run_root, "application_response", "started")
        XlwingsExcelProvider._activate_macos_appscript_compat()
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
        _record_office_phase("excel", run_root, "application_response", "completed")
        _record_office_phase("excel", run_root, "opened", "started")
        book = app.books.open(str(path), update_links=False, read_only=False)
        _record_office_phase("excel", run_root, "opened", "completed")
        _record_office_phase("excel", run_root, "written", "started")
        sheet = book.sheets[0]
        sheet.range("A1").value = 19
        sheet.range("A2").value = 23
        sheet.range("A3").formula = "=A1+A2"
        progress.write_text("written")
        _record_office_phase("excel", run_root, "written", "completed")
        full_rebuild = getattr(getattr(app, "api", None), "calculate_full_rebuild", None)
        if not callable(full_rebuild):
            result = {
                "outcome": "formula_error",
                "code": "excel_full_rebuild_unavailable",
            }
        else:
            _record_office_phase("excel", run_root, "saved", "started")
            full_rebuild()
            book.save()
            progress.write_text("saved")
            _record_office_phase("excel", run_root, "saved", "completed")
            _record_office_phase("excel", run_root, "closed", "started")
            book.close()
            progress.write_text("closed")
            _record_office_phase("excel", run_root, "closed", "completed")
            _record_office_phase("excel", run_root, "reopened", "started")
            book = app.books.open(str(path), update_links=False, read_only=True)
            progress.write_text("reopened")
            _record_office_phase("excel", run_root, "reopened", "completed")
            _record_office_phase("excel", run_root, "read_back", "started")
            value = book.sheets[0].range("A3").value
            if value == 42:
                progress.write_text("read_back")
            _record_office_phase("excel", run_root, "read_back", "completed")
            result = (
                {"outcome": "available", "code": None}
                if value == 42
                else {"outcome": "formula_error", "code": "excel_calculation_failed"}
            )
    except Exception as exc:  # noqa: BLE001 - proprietary automation errors are unstable.
        log.warning("local_excel_verification_failed", error_type=type(exc).__name__)
        result = _permission_outcome(str(exc))
    finally:
        _record_office_phase("excel", run_root, "cleanup", "started")
        function = result["outcome"]
        cleanup = "confirmed" if artifact_owned else "not_created"
        if book is not None:
            try:
                book.close()
                progress.write_text("document_closed")
            except Exception as exc:  # noqa: BLE001
                log.warning("local_excel_book_close_failed", error_type=type(exc).__name__)
                cleanup = "failed"
                result = {"outcome": "failed", "code": "cleanup_failed"}
        if app is not None:
            try:
                app.quit()
            except Exception as exc:  # noqa: BLE001
                log.warning("local_excel_app_close_failed", error_type=type(exc).__name__)
                result = {"outcome": "failed", "code": "cleanup_failed"}
                cleanup = "failed"
        if (
            artifact_owned
            and path is not None
            and cleanup == "confirmed"
            and not _remove_office_artifact("excel", run_root)
        ):
            result = {"outcome": "failed", "code": "cleanup_failed"}
            cleanup = "failed"
        if cleanup in {"confirmed", "not_created"}:
            _record_office_phase("excel", run_root, "cleanup", "completed")
        result["diagnostics"] = _office_diagnostics("excel", run_root, function, cleanup)
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


def _office_diagnostics(
    target: str, run_root: Path, function: str, cleanup: str
) -> dict[str, str | int | list[dict]]:
    step = "none"
    progress = run_root / f"{target}-step.txt"
    try:
        metadata = progress.lstat()
        if (
            stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and metadata.st_size <= 64
        ):
            descriptor = os.open(progress, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "r") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    raise OSError("Office progress identity changed")
                candidate = stream.read(65).strip()
            if candidate in {
                "prepared",
                "created",
                "written",
                "saved",
                "closed",
                "reopened",
                "read_back",
                "document_closed",
            }:
                step = candidate
    except OSError:
        log.warning("local_word_verification_progress_unavailable")
    result: dict[str, str | int | list[dict]] = {
        "run_id": run_root.name,
        "artifact_name": f"research-workbench-{run_root.name}"
        + {"word": ".docx", "excel": ".xlsx", "powerpoint": ".pptx"}[target],
        "last_completed_step": step,
        "function_outcome": function,
        "cleanup_outcome": cleanup,
    }
    phases = _read_office_phases(target, run_root)
    if phases:
        result["phases"] = phases
    return result


def _verify_word(run_root: Path) -> dict[str, Any]:
    progress = run_root / "word-step.txt"
    try:
        _record_office_phase("word", run_root, "prepared", "started")
        descriptor = os.open(progress, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write("none")
        path = _office_artifact_path("word", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            progress.write_text("prepared")
            _record_office_phase("word", run_root, "prepared", "completed")
        else:
            return {
                "outcome": "failed",
                "code": "verification_storage_unsafe",
                "diagnostics": _office_diagnostics("word", run_root, "failed", "not_created"),
            }
    except OSError as exc:
        log.warning("local_word_verification_prepare_failed", error_type=type(exc).__name__)
        return {
            "outcome": "failed",
            "code": "office_verification_failed",
            "diagnostics": _office_diagnostics("word", run_root, "failed", "not_created"),
        }
    script = """on run argv
with timeout of 30 seconds
set smokeDocument to missing value
set reopenedDocument to missing value
set targetFile to POSIX file (item 1 of argv)
set targetName to item 2 of argv
set stepFile to item 3 of argv
tell application "Microsoft Word"
try
set smokeDocument to make new document
my recordStep("created", stepFile)
set content of text object of smokeDocument to "Research Workbench verification"
my recordStep("written", stepFile)
save as smokeDocument file name (targetFile as text) file format format document default
set smokeDocument to document targetName
my recordStep("saved", stepFile)
close smokeDocument saving no
set smokeDocument to missing value
my recordStep("closed", stepFile)
open targetFile
set reopenedDocument to document targetName
my recordStep("reopened", stepFile)
set verifiedText to content of text object of reopenedDocument
if verifiedText does not contain "Research Workbench verification" then error "verification failed"
my recordStep("read_back", stepFile)
close reopenedDocument saving no
set reopenedDocument to missing value
my recordStep("document_closed", stepFile)
on error errorMessage number errorNumber
if reopenedDocument is not missing value then close reopenedDocument saving no
if smokeDocument is not missing value then close smokeDocument saving no
my recordStep("document_closed", stepFile)
error errorMessage number errorNumber
end try
end tell
end timeout
end run
on recordStep(stepName, stepPath)
do shell script "/usr/bin/printf %s " & quoted form of stepName & " > " & quoted form of stepPath
end recordStep"""
    script = _instrument_office_script(script, "word")
    _record_office_phase("word", run_root, "application_response", "started")
    result = _run_osascript(
        script, str(path), path.name, str(progress), str(run_root / "word-phases.jsonl")
    )
    function = result["outcome"]
    diagnostics = _office_diagnostics("word", run_root, function, "unverified")
    if type(result.get("native_error_number")) is int:
        diagnostics["native_error_number"] = result["native_error_number"]
    if function == "available" and diagnostics["last_completed_step"] != "document_closed":
        result = {"outcome": "failed", "code": "verification_trace_incomplete"}
    elif diagnostics["last_completed_step"] == "document_closed" and _remove_office_artifact(
        "word", run_root
    ):
        diagnostics["cleanup_outcome"] = "confirmed"
    elif diagnostics["last_completed_step"] == "document_closed":
        diagnostics["cleanup_outcome"] = "failed"
        result = {"outcome": "failed", "code": "cleanup_failed"}
    result["diagnostics"] = diagnostics
    return result


def _verify_powerpoint(run_root: Path) -> dict[str, Any]:
    progress = run_root / "powerpoint-step.txt"
    try:
        _record_office_phase("powerpoint", run_root, "prepared", "started")
        descriptor = os.open(progress, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write("none")
        path = _office_artifact_path("powerpoint", run_root)
        try:
            path.lstat()
        except FileNotFoundError:
            progress.write_text("prepared")
            _record_office_phase("powerpoint", run_root, "prepared", "completed")
        else:
            return {
                "outcome": "failed",
                "code": "verification_storage_unsafe",
                "diagnostics": _office_diagnostics("powerpoint", run_root, "failed", "not_created"),
            }
    except OSError as exc:
        log.warning(
            "local_powerpoint_verification_prepare_failed",
            error_type=type(exc).__name__,
        )
        return {
            "outcome": "failed",
            "code": "office_verification_failed",
            "diagnostics": _office_diagnostics("powerpoint", run_root, "failed", "not_created"),
        }
    script = """on run argv
with timeout of 30 seconds
set smokePresentation to missing value
set reopenedPresentation to missing value
set targetFile to POSIX file (item 1 of argv)
set targetName to item 2 of argv
tell application "Microsoft PowerPoint"
try
set smokePresentation to make new presentation
my recordStep("created", item 3 of argv)
set smokeSlide to make new slide at end of smokePresentation with properties {layout:slide layout title slide}
set content of text range of text frame of shape 1 of slide 1 of smokePresentation to "Research Workbench verification"
my recordStep("written", item 3 of argv)
save smokePresentation in targetFile
set smokePresentation to presentation targetName
my recordStep("saved", item 3 of argv)
close smokePresentation
set smokePresentation to missing value
my recordStep("closed", item 3 of argv)
open targetFile
set reopenedPresentation to presentation targetName
my recordStep("reopened", item 3 of argv)
set verifiedText to content of text range of text frame of shape 1 of slide 1 of reopenedPresentation
if verifiedText does not contain "Research Workbench verification" then error "verification failed"
my recordStep("read_back", item 3 of argv)
close reopenedPresentation
set reopenedPresentation to missing value
my recordStep("document_closed", item 3 of argv)
on error errorMessage number errorNumber
if reopenedPresentation is not missing value then close reopenedPresentation
if smokePresentation is not missing value then close smokePresentation
my recordStep("document_closed", item 3 of argv)
error errorMessage number errorNumber
end try
end tell
end timeout
end run
on recordStep(stepName, stepPath)
do shell script "/usr/bin/printf %s " & quoted form of stepName & " > " & quoted form of stepPath
end recordStep"""
    script = _instrument_office_script(script, "powerpoint")
    _record_office_phase("powerpoint", run_root, "application_response", "started")
    result = _run_osascript(
        script, str(path), path.name, str(progress), str(run_root / "powerpoint-phases.jsonl")
    )
    diagnostics = _office_diagnostics("powerpoint", run_root, result["outcome"], "unverified")
    if type(result.get("native_error_number")) is int:
        diagnostics["native_error_number"] = result["native_error_number"]
    if result["outcome"] == "available" and diagnostics["last_completed_step"] != "document_closed":
        result = {"outcome": "failed", "code": "verification_trace_incomplete"}
    elif diagnostics["last_completed_step"] == "document_closed" and _remove_office_artifact(
        "powerpoint", run_root
    ):
        diagnostics["cleanup_outcome"] = "confirmed"
    elif diagnostics["last_completed_step"] == "document_closed":
        diagnostics["cleanup_outcome"] = "failed"
        result = {"outcome": "failed", "code": "cleanup_failed"}
    result["diagnostics"] = diagnostics
    return result


def _verify_wind_formula(
    run_root: Path,
    process_reporter: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Verify the Wind add-in through the production formula client."""

    del run_root  # Signature matches the other isolated verification workers.
    phase = "prepare"
    try:
        from app.research_web.report_workflows.workbook import (
            XlwingsExcelProvider,
            _capture_excel_process_identity,
        )
        from data_layer.adapters.wind.client import WindExcelClient

        XlwingsExcelProvider._activate_macos_appscript_compat()
        phase = "start_excel"
        with WindExcelClient(
            visible=False, timeout=10.0, isolated_workbook=True, isolated_app=True
        ) as client:
            if process_reporter is not None and client._owns_app:
                excel_pid = getattr(client._app, "pid", None)
                identity = (
                    _capture_excel_process_identity(excel_pid)
                    if isinstance(excel_pid, int)
                    else None
                )
                if identity is None:
                    raise RuntimeError("excel_process_identity_unavailable")
                process_reporter(identity)
            phase = "evaluate_formula"
            try:
                heartbeat_ok = client.heartbeat()
            except Exception:
                if _wind_security_verification_required():
                    return {
                        "outcome": "authorization_required",
                        "code": "wind_security_verification_required",
                    }
                raise
            if heartbeat_ok:
                return {"outcome": "available", "code": None}
            if _wind_security_verification_required():
                return {
                    "outcome": "authorization_required",
                    "code": "wind_security_verification_required",
                }
            return {"outcome": "formula_error", "code": "wind_formula_failed"}
    except Exception as exc:  # noqa: BLE001 - proprietary automation errors are unstable.
        log.warning(
            "local_wind_formula_verification_failed",
            phase=phase,
            error_type=type(exc).__name__,
        )
        return _permission_outcome(str(exc))


def _launch_macos_excel() -> None:
    """Launch Excel through LaunchServices and wait for its scriptable instance."""

    if sys.platform != "darwin":
        return
    try:
        completed = subprocess.run(
            ["open", "-g", "-a", "Microsoft Excel"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("excel_launch_failed") from exc
    if completed.returncode != 0:
        raise RuntimeError("excel_launch_failed")

    import xlwings as xw

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            if list(xw.apps):
                return
        except Exception as exc:  # noqa: BLE001 - appscript is not stable while launching.
            log.debug("local_wind_excel_launch_pending", error_type=type(exc).__name__)
        time.sleep(0.5)
    raise RuntimeError("excel_launch_timed_out")


def _wind_security_verification_required() -> bool:
    """Detect Wind's visible Excel authorization prompt without reading its content."""

    if sys.platform != "darwin":
        return False
    script = (
        'tell application "System Events" to tell process "Microsoft Excel" '
        "to get name of every window"
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0 or len(completed.stdout) > 4096:
        return False
    window_names = {name.strip() for name in completed.stdout.split(",")}
    return bool(window_names & {"安全验证", "Security Verification"})


def _verify_wind(data_root: Path, run_root: Path) -> dict[str, Any]:
    from app.research_web.report_workflows.catalog import ReportWorkflowService
    from app.research_web.report_workflows.models import (
        RefreshStatus,
        WorkbookFormulaProvider,
    )
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
                    VERIFICATION_TIMEOUT_SECONDS - PROCESS_COORDINATION_GRACE_SECONDS,
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


def _excel_process_baseline() -> set[int]:
    from app.research_web.report_workflows.workbook import _MACOS_EXCEL_EXECUTABLE

    completed = subprocess.run(
        ["/bin/ps", "-axo", "pid=,comm="], capture_output=True, text=True, timeout=2, check=True
    )
    return {
        int(parts[0])
        for line in completed.stdout.splitlines()
        if len(parts := line.strip().split(None, 1)) == 2 and parts[1] == _MACOS_EXCEL_EXECUTABLE
    }


def _launch_excel_document_pid(path: Path, baseline: set[int]) -> int:
    """Delegate one owned file to a new Excel instance through Launch Services."""
    metadata = path.lstat()
    if (
        SAFE_RUN_NAME.fullmatch(path.parent.name) is None
        or path.name != f"research-workbench-{path.parent.name}.xlsx"
        or not stat.S_ISREG(metadata.st_mode)
        or path.is_symlink()
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
    ):
        raise ValueError("native_document_input_invalid")
    completed = subprocess.run(
        ["/usr/bin/open", "-n", "-b", "com.microsoft.Excel", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if completed.returncode:
        raise ValueError("native_excel_isolation_unverified")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        added = _excel_process_baseline() - baseline
        if len(added) > 1:
            raise ValueError("native_excel_isolation_unverified")
        if added:
            return added.pop()
        time.sleep(0.1)
    raise ValueError("native_excel_isolation_unverified")


def _native_excel_document(
    run_root: Path, document: dict, reporter: Callable[[dict], None], *, provider_factory=None
) -> dict:
    """Use the existing xlwings provider on a private input copy, without refresh."""
    import zipfile
    from io import BytesIO

    from lxml import etree
    from openpyxl import load_workbook
    from openpyxl.formula import Tokenizer
    from openpyxl.utils.cell import coordinate_to_tuple

    from app.research_web.report_workflows.workbook import (
        XlwingsExcelProvider,
        _capture_excel_process_identity,
    )

    path = run_root / f"research-workbench-{run_root.name}.xlsx"
    progress = run_root / "excel-step.txt"
    progress.write_text("none")
    app = book = None
    owned_app = artifact_owned = False
    launch_attempted = False
    pid = None
    baseline: set[int] = set()
    result: dict[str, object] = {"outcome": "failed", "code": "native_document_failed"}
    cleanup = "not_created"

    def start(stage):
        _record_office_phase("excel", run_root, stage, "started")

    def done(stage):
        _record_office_phase("excel", run_root, stage, "completed")

    try:
        start("prepared")
        source = document.get("source")
        if not isinstance(source, bytes) or len(source) > 30 * 1024 * 1024:
            raise ValueError("native_document_input_invalid")
        with zipfile.ZipFile(BytesIO(source)) as package:
            entries = package.infolist()
            if len(entries) > 1024 or sum(entry.file_size for entry in entries) > 96 * 1024 * 1024:
                raise ValueError("native_document_input_invalid")
            if any(
                any(
                    token in entry.filename.lower()
                    for token in (
                        "vbaproject",
                        "externallinks",
                        "connections.xml",
                        "querytables",
                        "macrosheets",
                    )
                )
                for entry in entries
            ):
                raise ValueError("native_workbook_external_content_unsupported")
            parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
            for entry in entries:
                if entry.filename.endswith(".rels") or entry.filename == "[Content_Types].xml":
                    root = etree.fromstring(package.read(entry.filename), parser)
                    if any(
                        node.get("TargetMode") == "External"
                        or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", node.get("Target", ""))
                        or "macro" in node.get("ContentType", "").lower()
                        for node in root
                    ):
                        raise ValueError("native_workbook_external_content_unsupported")

        def local_formula(expression: str) -> bool:
            allowed = {
                "SUM",
                "AVERAGE",
                "MIN",
                "MAX",
                "COUNT",
                "COUNTA",
                "IF",
                "AND",
                "OR",
                "ROUND",
                "ABS",
                "SUMIF",
                "SUMIFS",
                "COUNTIF",
                "COUNTIFS",
                "INDEX",
                "MATCH",
            }
            if any(token in expression for token in ("[", "]", "|", "://")):
                return False
            return all(
                token.value.rstrip("(").upper() in allowed
                for token in Tokenizer(expression).items
                if token.type == "FUNC" and token.subtype == "OPEN"
            )

        # Inspect the package rather than openpyxl's global-name mapping: local
        # names are moved into worksheet mappings during workbook loading.
        with zipfile.ZipFile(BytesIO(source)) as package:
            workbook_xml = etree.fromstring(package.read("xl/workbook.xml"), parser)
            for name in workbook_xml.iter(
                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}definedName"
            ):
                if (
                    name.get("name", "").lower().removeprefix("_xlnm.")
                    in {"auto_open", "auto_close"}
                    or name.get("function", "0").lower() in {"1", "true"}
                    or not local_formula("=" + (name.text or ""))
                ):
                    raise ValueError("native_workbook_external_content_unsupported")
        checked = load_workbook(BytesIO(source), read_only=True, data_only=False)
        sheet_names = checked.sheetnames
        formula_refs: list[str] = []
        try:
            for sheet in checked:
                if sheet.max_row > 10000 or sheet.max_column > 256:
                    raise ValueError("native_document_input_invalid")
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.data_type == "f" and (
                            not isinstance(cell.value, str) or not local_formula(cell.value)
                        ):
                            raise ValueError("native_workbook_external_content_unsupported")
                        if cell.data_type == "f" and len(formula_refs) < 64:
                            formula_refs.append(f"{sheet.title}!{cell.coordinate}")
        finally:
            checked.close()
        refs = document.get("read_cells") or formula_refs or [f"{sheet_names[0]}!A1"]
        changes = document.get("changes") or []
        if (
            not isinstance(refs, list)
            or len(refs) > 64
            or not all(
                isinstance(ref, str)
                and re.fullmatch(r"[^\[\]/:\\]{1,31}![A-Z]{1,3}[1-9][0-9]{0,3}", ref)
                for ref in refs
            )
        ):
            raise ValueError("native_document_input_invalid")
        for ref in refs:
            sheet_name, address = ref.rsplit("!", 1)
            row, column = coordinate_to_tuple(address)
            if sheet_name not in sheet_names or row > 10000 or column > 256:
                raise ValueError("native_document_target_invalid")
        for change in changes:
            if (
                not isinstance(change, dict)
                or set(change) != {"kind", "sheet", "cell", "value"}
                or change["kind"] != "cell"
                or change["sheet"] not in sheet_names
                or not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,3}", str(change["cell"]))
                or type(change["value"]) not in {str, int, float, bool, type(None)}
            ):
                raise ValueError("native_document_target_invalid")
            if isinstance(change["value"], str) and change["value"].startswith("="):
                raise ValueError("native_formula_edit_unsupported")
            row, column = coordinate_to_tuple(change["cell"])
            if row > 10000 or column > 256:
                raise ValueError("native_document_target_invalid")
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(source)
            artifact_owned = True
        progress.write_text("prepared")
        done("prepared")
        start("application_response")
        provider = (provider_factory or XlwingsExcelProvider)()
        if not provider.readiness()["ready"]:
            raise ValueError("native_excel_dependency_unavailable")
        driver = provider._xlwings
        if driver is None:
            raise ValueError("native_excel_dependency_unavailable")
        baseline = _excel_process_baseline()
        launch_attempted = True
        pid = _launch_excel_document_pid(path, baseline)
        if type(pid) is not int or pid in baseline:
            raise ValueError("native_excel_isolation_unverified")
        identity = _capture_excel_process_identity(pid)
        if identity is None:
            raise ValueError("native_excel_isolation_unverified")
        aliases = {str(path)}
        if str(path).startswith("/private/tmp/"):
            aliases.add("/tmp/" + str(path).removeprefix("/private/tmp/"))
        ready_deadline = time.monotonic() + 10
        while True:
            try:
                candidate_app = driver.apps[pid]
                candidate_book = candidate_app.books[path.name]
                if len(candidate_app.books) != 1 or candidate_book.fullname not in aliases:
                    raise ValueError("native_excel_isolation_unverified")
            except KeyError as exc:
                if time.monotonic() >= ready_deadline:
                    raise ValueError("native_excel_isolation_unverified") from exc
                time.sleep(0.1)
                continue
            except Exception as exc:
                raise ValueError("native_excel_isolation_unverified") from exc
            app = candidate_app
            break
        owned_app = True
        reporter(identity)
        provider._app = app
        done("application_response")
        start("opened")
        book = candidate_book
        done("opened")
        start("read")
        provider.calculate_full(book)
        before = provider.read_cells(book, refs)
        formulas = {
            ref: book.sheets[ref.rsplit("!", 1)[0]].range(ref.rsplit("!", 1)[1]).formula
            for ref in refs
        }
        formulas = {
            ref: formula
            for ref, formula in formulas.items()
            if isinstance(formula, str) and formula.startswith("=")
        }
        done("read")
        start("written")
        for change in changes:
            value = change["value"]
            book.sheets[change["sheet"]].range(change["cell"]).value = (
                "'" + value if isinstance(value, str) else value
            )
        done("written")
        start("saved")
        provider.calculate_full(book)
        after = provider.read_cells(book, refs)
        provider.save(book)
        progress.write_text("saved")
        done("saved")
        start("closed")
        book.close()
        book = None
        done("closed")
        start("reopened")
        book = app.books.open(str(path), update_links=False, read_only=True)
        done("reopened")
        start("read_back")
        reopened = provider.read_cells(book, refs)
        preserved = all(
            book.sheets[ref.rsplit("!", 1)[0]].range(ref.rsplit("!", 1)[1]).formula == formula
            for ref, formula in formulas.items()
        )
        if reopened != after or not preserved:
            raise ValueError("native_excel_readback_failed")
        done("read_back")
        result = {
            "outcome": "available",
            "code": None,
            "output_file": path.name,
            "calculation_engine": "Microsoft Excel",
            "native_readback": {
                "before": before,
                "after": after,
                "reopened": reopened,
                "formula_preserved": preserved,
            },
        }
    except Exception as exc:  # noqa: BLE001 - normalize proprietary Excel/appscript errors.
        result = _permission_outcome(str(exc))
        if isinstance(exc, ValueError) and str(exc) in {
            "native_document_input_invalid",
            "native_workbook_external_content_unsupported",
            "native_document_target_invalid",
            "native_formula_edit_unsupported",
            "native_excel_dependency_unavailable",
            "native_excel_isolation_unverified",
            "native_excel_readback_failed",
        }:
            result["code"] = str(exc)
        log.warning(
            "native_excel_document_failed", code=result["code"], error_type=type(exc).__name__
        )
    finally:
        start("cleanup")
        try:
            if book is not None:
                book.close()
                progress.write_text("document_closed")
            if owned_app and app is not None:
                app.quit()
            cleanup = (
                "unverified"
                if launch_attempted and not owned_app and pid not in baseline
                else "confirmed" if artifact_owned else "not_created"
            )
            if artifact_owned and result["outcome"] != "available" and cleanup == "confirmed":
                path.unlink(missing_ok=True)
            done("cleanup")
        except Exception as exc:  # noqa: BLE001 - cleanup uses the same proprietary driver.
            cleanup = "unverified"
            result.update(outcome="failed", code="cleanup_failed")
            log.warning("native_excel_document_cleanup_failed", error_type=type(exc).__name__)
        result["diagnostics"] = _office_diagnostics(
            "excel", run_root, str(result["outcome"]), cleanup
        )
    return result


def _native_word_document(run_root: Path, document: dict) -> dict:
    """Create/read/edit a bounded plain Word document through the installed app."""
    import zipfile
    from io import BytesIO

    from docx import Document
    from docx.oxml.ns import qn
    from lxml import etree

    path = run_root / f"research-workbench-{run_root.name}.docx"
    progress = run_root / "word-step.txt"
    payload_path = run_root / "word-operation.json"
    write_step_path = run_root / "word-write-step.txt"
    result: dict[str, object] = {"outcome": "failed", "code": "native_document_input_invalid"}
    cleanup = "not_created"
    try:
        _record_office_phase("word", run_root, "prepared", "started")
        operation = document.get("operation")
        if operation not in {"generate", "read", "modify"}:
            raise ValueError("operation unsupported")
        source = document.get("source")
        if operation == "generate":
            content = document.get("content") or {}
            if not isinstance(content, dict) or set(content) - {"title", "paragraphs", "tables"}:
                raise ValueError("content unsupported")
            if not isinstance(content.get("paragraphs", []), list):
                raise ValueError("paragraphs must be a list")
            paragraphs = [content.get("title", "")] + list(content.get("paragraphs", []))
            tables = content.get("tables", [])
            positions = list(range(1, len(paragraphs) + 1))
            verify_title_bold, title_bold = True, True
        else:
            if not isinstance(source, bytes) or len(source) > 30 * 1024 * 1024:
                raise ValueError("source invalid")
            with zipfile.ZipFile(BytesIO(source)) as package:
                entries = package.infolist()
                if (
                    len(entries) > 1024
                    or sum(e.file_size for e in entries) > 96 * 1024 * 1024
                    or any(e.file_size > 32 * 1024 * 1024 or e.flag_bits & 1 for e in entries)
                ):
                    raise ValueError("package invalid")
                parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
                for entry in entries:
                    if any(
                        t in entry.filename.lower() for t in ("vbaproject", "activex", "embeddings")
                    ):
                        raise ValueError("embedded content unsupported")
                    if entry.filename.endswith(".rels"):
                        root = etree.fromstring(package.read(entry.filename), parser)
                        if any(
                            n.get("TargetMode") == "External"
                            or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", n.get("Target", ""))
                            for n in root
                        ):
                            raise ValueError("external content unsupported")
            seed = Document(BytesIO(source))
            if (
                not seed.paragraphs
                or seed.paragraphs[0].style is None
                or seed.paragraphs[0].style.name != "Title"
            ):
                raise ValueError("plain title document required")
            if any(
                n.tag.rsplit("}", 1)[-1]
                in {"drawing", "pict", "fldChar", "fldSimple", "hyperlink", "ins", "del", "sdt"}
                for n in seed.element.iter()
            ):
                raise ValueError("complex document unsupported")
            paragraphs = [p.text for p in seed.paragraphs]
            title_flags = {run.bold for run in seed.paragraphs[0].runs}
            verify_title_bold = len(title_flags) == 1 and None not in title_flags
            title_bold = title_flags == {True}
            tables = [
                [[cell.text for cell in row.cells] for row in table.rows] for table in seed.tables
            ]
            positions = []
            paragraph_number = 1
            for node in seed.element.body:
                if node.tag == qn("w:p"):
                    positions.append(paragraph_number)
                    paragraph_number += 1
                elif node.tag == qn("w:tbl"):
                    # Word's paragraph collection also includes each table row end.
                    paragraph_number += sum(n.tag in {qn("w:p"), qn("w:tr")} for n in node.iter())
        if not 1 <= len(paragraphs) <= 100 or not isinstance(tables, list) or len(tables) > 1:
            raise ValueError("document bounds unsupported")
        for table in tables:
            if (
                not isinstance(table, list)
                or not 1 <= len(table) <= 20
                or not isinstance(table[0], list)
                or not 1 <= len(table[0]) <= 10
                or any(not isinstance(row, list) or len(row) != len(table[0]) for row in table)
            ):
                raise ValueError("table bounds unsupported")
        changes = document.get("changes") or []
        writes: list[dict[str, str | int]] = []
        if len(changes) > 100:
            raise ValueError("change count unsupported")
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("text"), str):
                raise TypeError("change invalid")
            if change.get("kind") == "paragraph" and set(change) == {"kind", "index", "text"}:
                index = change["index"]
                if type(index) is not int or not 0 <= index < len(paragraphs):
                    raise ValueError("paragraph invalid")
                if operation != "generate":
                    runs = seed.paragraphs[index].runs
                    formats = {
                        etree.tostring(run._r.rPr, method="c14n") if run._r.rPr is not None else b""
                        for run in runs
                    }
                    if len(formats) > 1:
                        raise ValueError("mixed target unsupported")
                writes.append(
                    {"kind": "paragraph", "position": positions[index], "text": change["text"]}
                )
                paragraphs[index] = change["text"]
            elif change.get("kind") == "table_cell" and set(change) == {
                "kind",
                "table",
                "row",
                "column",
                "text",
            }:
                t, r, c = (change[k] for k in ("table", "row", "column"))
                if (
                    any(type(v) is not int or v < 0 for v in (t, r, c))
                    or t >= len(tables)
                    or r >= len(tables[t])
                    or c >= len(tables[t][r])
                ):
                    raise ValueError("cell invalid")
                if operation != "generate":
                    cell = seed.tables[t].cell(r, c)
                    if (
                        len(cell.paragraphs) != 1
                        or cell.tables
                        or cell._tc.find(".//" + qn("w:vMerge")) is not None
                        or cell._tc.find(".//" + qn("w:gridSpan")) is not None
                    ):
                        raise ValueError("complex cell target unsupported")
                    runs = cell.paragraphs[0].runs
                    formats = {
                        etree.tostring(run._r.rPr, method="c14n") if run._r.rPr is not None else b""
                        for run in runs
                    }
                    if len(formats) > 1:
                        raise ValueError("mixed cell target unsupported")
                writes.append(
                    {
                        "kind": "cell",
                        "table": t + 1,
                        "row": r + 1,
                        "column": c + 1,
                        "text": change["text"],
                    }
                )
                tables[t][r][c] = change["text"]
            else:
                raise ValueError("change unsupported")
        texts = paragraphs + [cell for table in tables for row in table for cell in row]
        if any(
            not isinstance(text, str)
            or len(text) > 4000
            or any(character in text for character in "\r\n\t\0")
            for text in texts
        ):
            raise ValueError("plain single-line text required")
        body = "\r".join(paragraphs) + "\r"
        table_text = "\r".join("\t".join(row) for row in tables[0]) if tables else ""
        payload = {
            "writes": writes,
            "verify_title_bold": verify_title_bold,
            "title_bold": title_bold,
            "operation": operation,
            "paragraphs": paragraphs,
            "positions": positions,
            "tables": tables,
            "body": body,
            "table_text": table_text,
            "table_start": len(body.encode("utf-16-le")) // 2,
            "table_end": len((body + table_text).encode("utf-16-le")) // 2,
        }
        if operation != "generate":
            if not isinstance(source, bytes):
                raise ValueError("source invalid")
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                stream.write(source)
        else:
            # Empty transport only: Word closes it before making the real new document.
            # The normal file-open handoff delegates access to this one owned destination.
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                Document().save(stream)
        for owned, raw in (
            (payload_path, json.dumps(payload, ensure_ascii=False).encode()),
            (progress, b"prepared"),
        ):
            with owned.open("xb") as stream:
                os.chmod(owned, 0o600)
                stream.write(raw)
        _record_office_phase("word", run_root, "prepared", "completed")
        cleanup = "unverified"
        script = r"""use framework "Foundation"
use scripting additions
property rwbPhaseFile : ""
on run argv
set targetPath to item 1 of argv
set stepFile to item 2 of argv
set rwbPhaseFile to item 3 of argv
set rawData to current application's NSData's dataWithContentsOfFile:(item 4 of argv)
set payload to current application's NSJSONSerialization's JSONObjectWithData:rawData options:0 |error|:(missing value)
set operationName to (payload's objectForKey:"operation") as text
set paragraphValues to payload's objectForKey:"paragraphs"
set paragraphPositions to payload's objectForKey:"positions"
set tableValues to payload's objectForKey:"tables"
set writeRecords to payload's objectForKey:"writes"
set targetHFSPath to (POSIX file targetPath) as text
set taskName to item 5 of argv
set ownedDocument to missing value
with timeout of 30 seconds
tell application "Microsoft Word"
try
my phase("application_response", "started", stepFile)
get version
my phase("application_response", "completed", stepFile)
my phase("opened", "started", stepFile)
set ownedDocument to my openWordTask(targetPath, taskName, targetHFSPath)
my phase("opened", "completed", stepFile)
if operationName is "generate" then
close ownedDocument saving no
set ownedDocument to missing value
my phase("created", "started", stepFile)
set ownedDocument to make new document
my phase("created", "completed", stepFile)
end if
my phase("read", "started", stepFile)
get content of text object of ownedDocument
my phase("read", "completed", stepFile)
my phase("written", "started", stepFile)
if operationName is "generate" then
set bodyText to (payload's objectForKey:"body") as text
set tableText to (payload's objectForKey:"table_text") as text
set content of text object of ownedDocument to bodyText & return
do shell script "/usr/bin/printf %s content > " & quoted form of (item 6 of argv)
if (tableValues's |count|()) > 0 then
set rowValues to tableValues's objectAtIndex:0
set columnValues to rowValues's objectAtIndex:0
set rowCount to (rowValues's |count|()) as integer
set columnCount to (columnValues's |count|()) as integer
set tableStart to (payload's objectForKey:"table_start") as integer
set tableEnd to (payload's objectForKey:"table_end") as integer
set tableRange to create range ownedDocument start tableStart end tableStart
do shell script "/usr/bin/printf %s range > " & quoted form of (item 6 of argv)
set createdTable to make new table at ownedDocument with properties {text object:tableRange, number of rows:rowCount, number of columns:columnCount}
repeat with rowIndex from 0 to (rowCount - 1)
set columnValues to rowValues's objectAtIndex:rowIndex
repeat with columnIndex from 0 to (columnCount - 1)
set targetCell to get cell from table createdTable row (rowIndex + 1) column (columnIndex + 1)
set content of text object of targetCell to (columnValues's objectAtIndex:columnIndex) as text
end repeat
end repeat
do shell script "/usr/bin/printf %s table > " & quoted form of (item 6 of argv)
end if
else if operationName is "modify" then
repeat with writeIndex from 0 to ((writeRecords's |count|()) - 1)
set writeRecord to writeRecords's objectAtIndex:writeIndex
set expectedText to (writeRecord's objectForKey:"text") as text
if ((writeRecord's objectForKey:"kind") as text) is "paragraph" then
set paragraphNumber to (writeRecord's objectForKey:"position") as integer
set paragraphRange to text object of paragraph paragraphNumber of ownedDocument
set startPosition to get start of content of paragraphRange
set endPosition to get end of content of paragraphRange
if endPosition is not greater than startPosition then error "native_document_range_invalid" number -2700
set replacementRange to create range ownedDocument start startPosition end (endPosition - 1)
set content of replacementRange to expectedText
else
set tableNumber to (writeRecord's objectForKey:"table") as integer
set rowNumber to (writeRecord's objectForKey:"row") as integer
set columnNumber to (writeRecord's objectForKey:"column") as integer
set targetTable to table tableNumber of ownedDocument
set targetCell to get cell from table targetTable row rowNumber column columnNumber
set content of text object of targetCell to expectedText
end if
end repeat
end if
if operationName is "generate" then
set style of text object of paragraph 1 of ownedDocument to style title
set bold of text object of paragraph 1 of ownedDocument to true
do shell script "/usr/bin/printf %s style > " & quoted form of (item 6 of argv)
end if
my phase("written", "completed", stepFile)
my phase("saved", "started", stepFile)
if operationName is "generate" then
save as ownedDocument file name targetHFSPath file format format document
else if operationName is "modify" then
save ownedDocument
end if
set ownedDocument to document taskName
my phase("saved", "completed", stepFile)
my phase("closed", "started", stepFile)
close ownedDocument saving no
set ownedDocument to missing value
my phase("closed", "completed", stepFile)
my phase("reopened", "started", stepFile)
set ownedDocument to my openWordTask(targetPath, taskName, targetHFSPath)
my phase("reopened", "completed", stepFile)
my phase("read_back", "started", stepFile)
repeat with indexNumber from 0 to ((paragraphValues's |count|()) - 1)
set paragraphNumber to (paragraphPositions's objectAtIndex:indexNumber) as integer
set expectedText to (paragraphValues's objectAtIndex:indexNumber) as text
set actualText to my plainText(content of text object of paragraph paragraphNumber of ownedDocument)
if actualText is not expectedText then error "native_document_readback_failed" number -2700
end repeat
repeat with tableIndex from 0 to ((tableValues's |count|()) - 1)
set rowValues to tableValues's objectAtIndex:tableIndex
repeat with rowIndex from 0 to ((rowValues's |count|()) - 1)
set columnValues to rowValues's objectAtIndex:rowIndex
repeat with columnIndex from 0 to ((columnValues's |count|()) - 1)
set targetTable to table (tableIndex + 1) of ownedDocument
set targetCell to get cell from table targetTable row (rowIndex + 1) column (columnIndex + 1)
set actualText to my plainText(content of text object of targetCell)
if actualText is not ((columnValues's objectAtIndex:columnIndex) as text) then error "native_document_readback_failed" number -2700
end repeat
end repeat
end repeat
set actualTitleStyle to get style of paragraph 1 of ownedDocument
set expectedTitleStyle to get Word style style title of ownedDocument
set actualTitleName to get name local of actualTitleStyle
set expectedTitleName to get name local of expectedTitleStyle
set actualTitleBuiltIn to get built in of actualTitleStyle
if not (my titleStyleMatches(actualTitleName, expectedTitleName, actualTitleBuiltIn)) then error "native_document_style_failed" number -2700
if (payload's objectForKey:"verify_title_bold") as boolean then
set expectedBold to (payload's objectForKey:"title_bold") as boolean
if bold of text object of paragraph 1 of ownedDocument is not expectedBold then error "native_document_style_failed" number -2700
end if
my phase("read_back", "completed", stepFile)
my phase("document_closed", "started", stepFile)
close ownedDocument saving no
set ownedDocument to missing value
my phase("document_closed", "completed", stepFile)
on error errorMessage number errorNumber
if ownedDocument is not missing value then
my phase("document_closed", "started", stepFile)
close ownedDocument saving no
set ownedDocument to missing value
my phase("document_closed", "completed", stepFile)
end if
error "native_document_failed" number errorNumber
end try
end tell
end timeout
end run
on titleStyleMatches(actualTitleName, expectedTitleName, actualTitleBuiltIn)
considering case
if actualTitleName is not expectedTitleName or actualTitleBuiltIn is not true then return false
return true
end considering
end titleStyleMatches
on openWordTask(targetPath, taskName, expectedHFS)
do shell script "/usr/bin/open -b com.microsoft.Word " & quoted form of targetPath
repeat
try
tell application "Microsoft Word"
set candidateDocument to document taskName
set candidateFullName to get full name of candidateDocument
set candidateSaved to get saved of candidateDocument
end tell
exit repeat
on error errorMessage number errorNumber
if errorNumber is not -1728 and errorNumber is not -1708 then error "native_document_open_failed" number errorNumber
delay 0.25
end try
end repeat
considering case
if candidateFullName is not expectedHFS or candidateSaved is not true then error "native_document_identity_mismatch" number -2700
end considering
return candidateDocument
end openWordTask
on plainText(rawText)
repeat while (length of rawText) > 0
if character -1 of rawText is not return and character -1 of rawText is not (ASCII character 7) then exit repeat
if (length of rawText) is 1 then return ""
set rawText to text 1 thru -2 of rawText
end repeat
return rawText
end plainText
on phase(stageName, phaseName, stepFile)
set stamp to do shell script "/bin/date +%s"
set entry to "{\"stage\":\"" & stageName & "\",\"phase\":\"" & phaseName & "\",\"at\":" & stamp & "}"
do shell script "/usr/bin/printf '%s\n' " & quoted form of entry & " >> " & quoted form of rwbPhaseFile
if phaseName is "completed" then do shell script "/usr/bin/printf %s " & quoted form of stageName & " > " & quoted form of stepFile
end phase"""
        result = _run_osascript(
            script,
            str(path),
            str(progress),
            str(run_root / "word-phases.jsonl"),
            str(payload_path),
            path.name,
            str(write_step_path),
        )
        if progress.read_text() == "document_closed":
            cleanup = "confirmed"
        if result["outcome"] == "available" and cleanup == "confirmed":
            result.update(
                output_file=path.name,
                document={"paragraphs": [{"text": text} for text in paragraphs], "tables": tables},
                native_readback={
                    "application": "Microsoft Word",
                    "paragraphs_verified": len(paragraphs),
                    "tables_verified": len(tables),
                    "title_style_and_bold": verify_title_bold and title_bold,
                },
            )
        elif result["outcome"] == "available":
            result.update(outcome="failed", code="verification_trace_incomplete")
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        zipfile.BadZipFile,
        etree.XMLSyntaxError,
    ) as exc:
        result = {"outcome": "failed", "code": "native_document_input_invalid"}
        log.warning("native_word_document_failed", error_type=type(exc).__name__)
    diagnostics = _office_diagnostics("word", run_root, str(result["outcome"]), cleanup)
    native_number = result.get("native_error_number")
    if isinstance(native_number, int):
        diagnostics["native_error_number"] = native_number
    result["diagnostics"] = diagnostics
    if (
        write_step_path.is_file()
        and not write_step_path.is_symlink()
        and write_step_path.stat().st_size <= 16
    ):
        write_step = write_step_path.read_text().strip()
        if write_step in {"content", "range", "table", "style"}:
            result["comparison"] = {"last_write_step": write_step}
    return result


def _native_powerpoint_document(run_root: Path, document: dict) -> dict:
    """Edit bounded text shapes in a private copy through the installed app."""
    import zipfile
    from io import BytesIO

    from lxml import etree

    path = run_root / f"research-workbench-{run_root.name}.pptx"
    progress = run_root / "powerpoint-step.txt"
    payload_path = run_root / "powerpoint-operation.json"
    comparison_path = run_root / "powerpoint-comparison.json"
    cleanup = "not_created"
    result: dict[str, object] = {"outcome": "failed", "code": "native_document_input_invalid"}
    try:
        _record_office_phase("powerpoint", run_root, "prepared", "started")
        source = document.get("source")
        if not isinstance(source, bytes) or len(source) > 30 * 1024 * 1024:
            raise ValueError("invalid source")
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        targets: list[dict[str, str | int | bool | None]] = []
        changes = document.get("changes") or []
        if document.get("operation") not in {"read", "modify"} or len(changes) > 100:
            raise ValueError("invalid operation")
        with zipfile.ZipFile(BytesIO(source)) as package:
            entries = package.infolist()
            if (
                len(entries) > 1024
                or sum(e.file_size for e in entries) > 96 * 1024 * 1024
                or any(e.file_size > 32 * 1024 * 1024 or e.flag_bits & 1 for e in entries)
            ):
                raise ValueError("invalid package")
            for entry in entries:
                if any(
                    t in entry.filename.lower() for t in ("vbaproject", "activex", "embeddings")
                ):
                    raise ValueError("unsupported content")
                if entry.filename.endswith(".rels"):
                    root = etree.fromstring(package.read(entry.filename), parser)
                    if any(
                        n.get("TargetMode") == "External"
                        or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", n.get("Target", ""))
                        for n in root
                    ):
                        raise ValueError("unsupported relationship")
            presentation = etree.fromstring(package.read("ppt/presentation.xml"), parser)
            rels = etree.fromstring(package.read("ppt/_rels/presentation.xml.rels"), parser)
            mapping = {
                n.get("Id"): n.get("Target") for n in rels if n.get("Type", "").endswith("/slide")
            }
            slides = presentation.findall("p:sldIdLst/p:sldId", ns)
            if not 1 <= len(slides) <= 20:
                raise ValueError("slide count unsupported")
            addressed = set()
            for number, slide in enumerate(slides, 1):
                part = mapping.get(slide.get("{" + ns["r"] + "}id"))
                if not isinstance(part, str) or not re.fullmatch(r"slides/slide[0-9]+\.xml", part):
                    raise ValueError("invalid slide")
                root = etree.fromstring(package.read("ppt/" + part), parser)
                all_names = [node.get("name") for node in root.findall(".//p:cNvPr", ns)]
                if root.find("p:cSld/p:spTree/p:grpSp", ns) is not None:
                    raise ValueError("grouped targets unsupported")
                names = set()
                for shape in root.findall("p:cSld/p:spTree/p:sp", ns):
                    identity = shape.find("p:nvSpPr/p:cNvPr", ns)
                    if (
                        identity is None
                        or identity.get("name") in names
                        or all_names.count(identity.get("name")) != 1
                    ):
                        raise ValueError("shape identity unsupported")
                    name = identity.get("name")
                    names.add(name)
                    paragraphs = shape.findall("p:txBody/a:p", ns)
                    if not paragraphs:
                        continue
                    value = "\r".join(
                        "".join(n.text or "" for n in p.findall(".//a:t", ns)) for p in paragraphs
                    )
                    changed = False
                    for index, change in enumerate(changes):
                        if (
                            not isinstance(change, dict)
                            or set(change) != {"kind", "slide", "shape_id", "text"}
                            or change["kind"] != "shape_text"
                            or type(change["slide"]) is not int
                            or not isinstance(change["text"], str)
                            or len(change["text"]) > 4000
                        ):
                            raise ValueError("invalid change")
                        if change["slide"] == number and str(change["shape_id"]) == identity.get(
                            "id"
                        ):
                            if len(paragraphs) != 1 or len(paragraphs[0].findall("a:r", ns)) != 1:
                                raise ValueError("complex text editing unsupported")
                            value = change["text"].replace("\n", "\r")
                            addressed.add(index)
                            changed = True
                    if (
                        not isinstance(name, str)
                        or not name
                        or len(value) > 4000
                        or len(targets) >= 100
                    ):
                        raise ValueError("text target unsupported")
                    targets.append(
                        {
                            "slide": number,
                            "shape_id": identity.get("id"),
                            "shape_name": name,
                            "value": value,
                            "changed": changed,
                        }
                    )
            if len(addressed) != len(changes) or not targets:
                raise ValueError("target missing")
        for owned, raw in (
            (path, source),
            (payload_path, json.dumps({"targets": targets}, ensure_ascii=False).encode()),
            (progress, b"prepared"),
        ):
            with owned.open("xb") as stream:
                os.chmod(owned, 0o600)
                stream.write(raw)
        cleanup = "unverified"
        _record_office_phase("powerpoint", run_root, "prepared", "completed")
        script = r"""use framework "Foundation"
use scripting additions
property rwbPhaseFile : ""
on run argv
set targetPath to item 1 of argv
set stepFile to item 2 of argv
set rwbPhaseFile to item 3 of argv
set rawData to current application's NSData's dataWithContentsOfFile:(item 4 of argv)
set payload to current application's NSJSONSerialization's JSONObjectWithData:rawData options:0 |error|:(missing value)
set targetRecords to payload's objectForKey:"targets"
set ownedPresentation to missing value
with timeout of 30 seconds
tell application "Microsoft PowerPoint"
try
my phase("application_response", "started", stepFile)
get version
my phase("application_response", "completed", stepFile)
my phase("opened", "started", stepFile)
do shell script "/usr/bin/open -b com.microsoft.Powerpoint " & quoted form of targetPath
repeat
try
set ownedPresentation to presentation (item 5 of argv)
exit repeat
on error
delay 0.25
end try
end repeat
my phase("opened", "completed", stepFile)
my phase("read", "started", stepFile)
repeat with recordIndex from 0 to ((targetRecords's |count|()) - 1)
set targetRecord to targetRecords's objectAtIndex:recordIndex
set pageNumber to (targetRecord's objectForKey:"slide") as integer
set shapeName to (targetRecord's objectForKey:"shape_name") as text
get content of text range of text frame of shape shapeName of slide pageNumber of ownedPresentation
end repeat
my phase("read", "completed", stepFile)
my phase("written", "started", stepFile)
repeat with recordIndex from 0 to ((targetRecords's |count|()) - 1)
set targetRecord to targetRecords's objectAtIndex:recordIndex
if (targetRecord's objectForKey:"changed") as boolean then
set pageNumber to (targetRecord's objectForKey:"slide") as integer
set shapeName to (targetRecord's objectForKey:"shape_name") as text
set expectedText to (targetRecord's objectForKey:"value") as text
set content of text range of text frame of shape shapeName of slide pageNumber of ownedPresentation to expectedText
set writtenText to content of text range of text frame of shape shapeName of slide pageNumber of ownedPresentation
if writtenText is not expectedText then error "native_document_write_failed" number -2701
end if
end repeat
my phase("written", "completed", stepFile)
my phase("saved", "started", stepFile)
save ownedPresentation
set ownedPresentation to presentation (item 5 of argv)
repeat until saved of ownedPresentation is true
delay 0.25
end repeat
set presentationSaved to saved of ownedPresentation
my phase("saved", "completed", stepFile)
my phase("closed", "started", stepFile)
close ownedPresentation
set ownedPresentation to missing value
my phase("closed", "completed", stepFile)
my phase("reopened", "started", stepFile)
do shell script "/usr/bin/open -b com.microsoft.Powerpoint " & quoted form of targetPath
repeat
try
set ownedPresentation to presentation (item 5 of argv)
exit repeat
on error
delay 0.25
end try
end repeat
my phase("reopened", "completed", stepFile)
my phase("read_back", "started", stepFile)
repeat with recordIndex from 0 to ((targetRecords's |count|()) - 1)
set targetRecord to targetRecords's objectAtIndex:recordIndex
set pageNumber to (targetRecord's objectForKey:"slide") as integer
set shapeName to (targetRecord's objectForKey:"shape_name") as text
set expectedText to (targetRecord's objectForKey:"value") as text
set actualText to content of text range of text frame of shape shapeName of slide pageNumber of ownedPresentation
if actualText is not expectedText then
set strippedText to actualText
repeat while (length of strippedText) > 0
if character -1 of strippedText is not return and character -1 of strippedText is not linefeed then exit repeat
if (length of strippedText) is 1 then
set strippedText to ""
exit repeat
end if
set strippedText to text 1 thru -2 of strippedText
end repeat
set trimmedEqual to strippedText is expectedText
set entry to "{\"slide\":" & pageNumber & ",\"actual_length\":" & (length of actualText) & ",\"expected_length\":" & (length of expectedText) & ",\"trimmed_equal\":" & trimmedEqual & ",\"saved_before_close\":" & presentationSaved & "}"
do shell script "/usr/bin/printf %s " & quoted form of entry & " > " & quoted form of (item 6 of argv)
error "native_document_readback_failed" number -2700
end if
end repeat
my phase("read_back", "completed", stepFile)
my phase("document_closed", "started", stepFile)
close ownedPresentation
set ownedPresentation to missing value
my phase("document_closed", "completed", stepFile)
on error errorMessage number errorNumber
if ownedPresentation is not missing value then
my phase("document_closed", "started", stepFile)
close ownedPresentation
set ownedPresentation to missing value
my phase("document_closed", "completed", stepFile)
end if
error "native_document_failed" number errorNumber
end try
end tell
end timeout
end run
on phase(stageName, phaseName, stepFile)
set stamp to do shell script "/bin/date +%s"
set entry to "{\"stage\":\"" & stageName & "\",\"phase\":\"" & phaseName & "\",\"at\":" & stamp & "}"
do shell script "/usr/bin/printf '%s\n' " & quoted form of entry & " >> " & quoted form of rwbPhaseFile
if phaseName is "completed" then do shell script "/usr/bin/printf %s " & quoted form of stageName & " > " & quoted form of stepFile
end phase"""
        result = _run_osascript(
            script,
            str(path),
            str(progress),
            str(run_root / "powerpoint-phases.jsonl"),
            str(payload_path),
            path.name,
            str(comparison_path),
        )
        if progress.read_text() == "document_closed":
            cleanup = "confirmed"
        if result["outcome"] == "available" and cleanup == "confirmed":
            result.update(
                output_file=path.name,
                native_readback={
                    "targets_verified": len(targets),
                    "application": "Microsoft PowerPoint",
                },
                document={
                    "slides": [
                        {
                            "number": number,
                            "objects": [
                                {"id": t["shape_id"], "name": t["shape_name"], "text": t["value"]}
                                for t in targets
                                if t["slide"] == number
                            ],
                        }
                        for number in range(1, len(slides) + 1)
                    ]
                },
            )
        elif result["outcome"] == "available":
            result.update(outcome="failed", code="verification_trace_incomplete")
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        zipfile.BadZipFile,
        etree.XMLSyntaxError,
    ) as exc:
        result = {"outcome": "failed", "code": "native_document_input_invalid"}
        log.warning("native_powerpoint_document_failed", error_type=type(exc).__name__)
    if (
        comparison_path.is_file()
        and not comparison_path.is_symlink()
        and comparison_path.stat().st_size <= 1024
    ):
        comparison = json.loads(comparison_path.read_text())
        if (
            set(comparison)
            == {"slide", "actual_length", "expected_length", "trimmed_equal", "saved_before_close"}
            and all(
                type(comparison[k]) is int and 0 <= comparison[k] <= 4001
                for k in ("slide", "actual_length", "expected_length")
            )
            and type(comparison["trimmed_equal"]) is bool
            and type(comparison["saved_before_close"]) is bool
        ):
            result["code"] = "native_document_readback_failed"
            result["comparison"] = comparison
    diagnostics = _office_diagnostics("powerpoint", run_root, str(result["outcome"]), cleanup)
    native_number = result.get("native_error_number")
    if isinstance(native_number, int):
        diagnostics["native_error_number"] = native_number
    result["diagnostics"] = diagnostics
    return result


def _child(
    target: str, data_root: str, run_root: str, results, document: dict | None = None
) -> None:
    try:
        if os.name == "posix":
            os.setsid()
        root = Path(run_root)
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        if document is not None:
            if target == "word":
                outcome = _native_word_document(root, document)
            elif target == "powerpoint":
                outcome = _native_powerpoint_document(root, document)
            else:
                outcome = _native_excel_document(
                    root,
                    document,
                    lambda identity: results.put(
                        {"status": "started", "child_processes": [identity]}
                    ),
                )
        else:
            outcome = {
                "excel": lambda: _verify_excel(
                    root,
                    lambda identity: results.put(
                        {"status": "started", "child_processes": [identity]}
                    ),
                ),
                "word": lambda: _verify_word(root),
                "powerpoint": lambda: _verify_powerpoint(root),
                "wind_excel": lambda: _verify_wind_formula(
                    root,
                    lambda identity: results.put(
                        {"status": "started", "child_processes": [identity]}
                    ),
                ),
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
    run_id: str | None = None,
    document: dict | None = None,
) -> dict[str, Any]:
    """Run an allowlisted verification in a terminable spawned process."""

    if target not in {"excel", "word", "powerpoint", "wind_excel"}:
        return {"outcome": "failed", "code": "verification_target_invalid"}
    if document is not None and target not in {"word", "excel", "powerpoint"}:
        return {"outcome": "failed", "code": "native_document_target_invalid"}
    if sys.platform != "darwin":
        return {"outcome": "failed", "code": "unsupported_platform"}
    if run_id is not None and SAFE_RUN_NAME.fullmatch(run_id) is None:
        return {"outcome": "failed", "code": "verification_storage_unsafe"}
    state_root = Path(state_root)
    storage_root = state_root
    run_root, storage_error = _prepare_run_directory(storage_root)
    if run_root is None:
        return {"outcome": "failed", "code": storage_error or "verification_storage_unsafe"}
    if run_id is not None:
        run_root = run_root.with_name(run_id)
        if run_root.exists() or run_root.is_symlink():
            return {"outcome": "failed", "code": "verification_storage_unsafe"}
    from app.research_web.report_workflows.workbook import (
        _drain_worker_messages,
        _terminate_managed_excel_processes,
        _worker_child_processes,
    )

    context = multiprocessing.get_context("spawn")
    results = context.Queue(maxsize=4)
    process = context.Process(
        target=_child,
        args=(target, str(state_root.parent), str(run_root), results)
        + ((document,) if document is not None else ()),
        name=f"local-verification-{target}",
    )
    outcome: dict[str, Any] = {"outcome": "failed", "code": "verification_failed"}
    try:
        process.start()
        began = time.time()
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
                outcome = {
                    "outcome": "failed",
                    "code": "verification_cancelled" if cleaned else "cleanup_failed",
                }
                return outcome
            remaining = deadline - time.monotonic()
            stage_timeout = (
                _office_phase_timeout(target, run_root, began)
                if target in {"word", "excel", "powerpoint"}
                else None
            )
            if remaining <= 0 or stage_timeout is not None:
                messages = _drain_worker_messages(results, wait=True)
                worker_cleaned = _terminate_process_tree(process)
                children_cleaned = _terminate_managed_excel_processes(
                    _worker_child_processes(messages)
                )
                cleaned = worker_cleaned and children_cleaned
                outcome = {
                    "outcome": "timeout" if cleaned else "failed",
                    "code": (
                        ("office_phase_timed_out" if stage_timeout else "verification_timed_out")
                        if cleaned
                        else "cleanup_failed"
                    ),
                }
                if stage_timeout:
                    outcome["timed_out_stage"] = stage_timeout
                return outcome
            process.join(min(0.25, remaining))
        messages = _drain_worker_messages(results, wait=True)
        child_processes = _worker_child_processes(messages)
        outcomes = [message for message in messages if message.get("status") != "started"]
        if not _terminate_managed_excel_processes(child_processes):
            outcome = {"outcome": "failed", "code": "cleanup_failed"}
            return outcome
        if not outcomes:
            return outcome
        outcome = outcomes[-1]
        if document is not None and outcome.get("outcome") == "available":
            suffix = {"word": "docx", "excel": "xlsx", "powerpoint": "pptx"}[target]
            path = run_root / f"research-workbench-{run_root.name}.{suffix}"
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                    or metadata.st_nlink != 1
                    or metadata.st_size > 30 * 1024 * 1024
                ):
                    raise OSError("unsafe native document output")
                outcome["output_bytes"] = stream.read(30 * 1024 * 1024 + 1)
        return outcome
    finally:
        results.close()
        results.join_thread()
        if target in {"word", "excel", "powerpoint"}:
            # The returned object receives final cleanup facts before reaching the caller.
            # Never repeat protected Office I/O after a killed/timed-out worker.
            previous = outcome.get("diagnostics", {})
            function = previous.get("function_outcome", outcome["outcome"])
            cleanup = previous.get("cleanup_outcome", "unverified")
            outcome["diagnostics"] = _office_diagnostics(target, run_root, function, cleanup)
            if outcome.get("timed_out_stage") in OFFICE_PHASES:
                outcome["diagnostics"]["timed_out_stage"] = outcome["timed_out_stage"]
            if type(previous.get("native_error_number")) is int:
                outcome["diagnostics"]["native_error_number"] = previous["native_error_number"]
            if cleanup == "confirmed" and outcome["outcome"] == "available" and document is None:
                # Successful smoke outputs use the existing bounded run retention.
                # Drop the completed marker so normal capacity/TTL pruning applies.
                marker = run_root / f"{target}-step.txt"
                try:
                    if marker.is_symlink():
                        raise OSError("unsafe completed verification marker")
                    marker.unlink(missing_ok=True)
                    log.info("local_office_verification_run_retained", target=target)
                except OSError:
                    outcome["diagnostics"]["cleanup_outcome"] = "failed"
                    outcome.update(outcome="failed", code="cleanup_failed")
            elif cleanup in {"confirmed", "not_created"}:
                if not _remove_run_directory(run_root):
                    outcome["diagnostics"]["cleanup_outcome"] = "failed"
                    outcome.update(outcome="failed", code="cleanup_failed")
            else:
                log.warning("local_word_verification_resource_retained", run_id=run_root.name)
            if (
                outcome["outcome"] == "available"
                and outcome["diagnostics"]["cleanup_outcome"] != "confirmed"
            ):
                outcome.update(outcome="failed", code="cleanup_failed")
        # Wind uses an owned in-memory workbook, not a file in Office Documents.
        if target == "wind_excel" and not _remove_run_directory(run_root):
            log.warning("local_verification_run_retained")
