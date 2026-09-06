"""Standard-library XLSX inspection and serialized Excel refresh services."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import multiprocessing
import os
import queue
import re
import shutil
import signal
import sys
import tempfile
import threading
import time
import weakref
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from uuid import uuid4
from xml.etree import ElementTree

from core.observability import get_logger

from .models import (
    RefreshStatus,
    WorkbookFormulaProvider,
    WorkbookProviderRequirement,
    WorkbookRefreshPolicy,
    WorkbookRefreshResult,
    WorkflowError,
    WorkflowResource,
    WorkflowResourceRole,
)

log = get_logger(__name__)
_EXCEL_REFRESH_LOCK = threading.Lock()
_TARGET_LOCKS_GUARD = threading.Lock()
_TARGET_LOCKS: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_FORMULA_ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}
_WIND_PATTERN = re.compile(r"\b(?:WSD|WSS|WSI|WSET|WST|WQID|WPF|EDB)\s*\(", re.IGNORECASE)
_IFIND_PATTERN = re.compile(r"\b(?:THS(?:_[A-Z0-9]+)?|IFIND)\s*\(", re.IGNORECASE)
_MAX_ZIP_MEMBERS = 512
_MAX_ZIP_MEMBER = 32 * 1024 * 1024
_MAX_ZIP_EXPANDED = 96 * 1024 * 1024
_MAX_ZIP_RATIO = 200
_WORKER_STOP_SECONDS = 2
_GLOBAL_EXCEL_LOCK_PATH = Path(tempfile.gettempdir()) / (
    f"research-workbench-excel-{getattr(os, 'getuid', lambda: 0)()}.lock"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_unlink(path: Path, event: str) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning(event, error_type=type(exc).__name__)


@dataclass(frozen=True)
class WorkbookFormulaScan:
    provider: WorkbookFormulaProvider
    formulas: tuple[str, ...]


def _safe_xlsx(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkflowError("工作簿不可读取", "workbook_unreadable", 400) from exc
    if path.is_symlink() or not resolved.is_file() or resolved.suffix.lower() != ".xlsx":
        raise WorkflowError("工作簿不可读取", "workbook_unreadable", 400)
    return resolved


def _target_lock(path: Path) -> threading.Lock:
    try:
        key = str(path.resolve(strict=False))
    except (OSError, RuntimeError) as exc:
        raise WorkflowError("刷新锁不可用", "refresh_lock_unavailable", 503) from exc
    with _TARGET_LOCKS_GUARD:
        lock = _TARGET_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _TARGET_LOCKS[key] = lock
        return lock


def _try_lock_stream(stream: Any) -> bool:
    if os.name != "posix":
        raise WorkflowError("当前平台不支持刷新锁", "unsupported_platform", 503)
    module = __import__("fcntl")
    try:
        module.flock(stream.fileno(), module.LOCK_EX | module.LOCK_NB)
    except BlockingIOError:
        return False
    except OSError as exc:
        raise WorkflowError("刷新锁不可用", "refresh_lock_unavailable", 503) from exc
    return True


def _unlock_stream(stream: Any) -> None:
    module = __import__("fcntl")
    module.flock(stream.fileno(), module.LOCK_UN)


def _check_lock_wait(
    cancellation_event: threading.Event | None,
    deadline: float,
) -> None:
    if cancellation_event is not None and cancellation_event.is_set():
        raise WorkflowError("刷新已取消", "refresh_cancelled", 409)
    if time.monotonic() >= deadline:
        raise WorkflowError("等待刷新锁超时", "refresh_lock_timeout", 409)


@contextmanager
def _file_lock(
    path: Path,
    thread_lock: threading.Lock,
    *,
    cancellation_event: threading.Event | None,
    deadline: float,
):
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise WorkflowError("刷新锁不可用", "refresh_lock_unavailable", 503) from exc
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    stream = None
    thread_locked = False
    file_locked = False
    try:
        while not thread_lock.acquire(blocking=False):
            _check_lock_wait(cancellation_event, deadline)
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        thread_locked = True
        _check_lock_wait(cancellation_event, deadline)
        descriptor = os.open(path, flags, 0o600)
        stream = os.fdopen(descriptor, "a+b")
        descriptor = None
        while not _try_lock_stream(stream):
            _check_lock_wait(cancellation_event, deadline)
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        file_locked = True
        yield
    except OSError as exc:
        raise WorkflowError("刷新锁不可用", "refresh_lock_unavailable", 503) from exc
    finally:
        if file_locked and stream is not None:
            try:
                _unlock_stream(stream)
            except OSError as exc:
                log.warning("report_refresh_lock_release_failed", error_type=type(exc).__name__)
        if stream is not None:
            try:
                stream.close()
            except OSError as exc:
                log.warning("report_refresh_lock_close_failed", error_type=type(exc).__name__)
        elif descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as exc:
                log.warning("report_refresh_lock_close_failed", error_type=type(exc).__name__)
        if thread_locked:
            thread_lock.release()


@contextmanager
def _open_archive(path: Path):
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise WorkflowError("工作簿格式无效", "invalid_workbook", 422) from exc
    try:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(members) > _MAX_ZIP_MEMBERS or len(names) != len(set(names)):
            raise WorkflowError("工作簿压缩包超出安全限制", "unsafe_workbook_archive", 422)
        expanded = 0
        for member in members:
            name = PurePosixPath(member.filename)
            expanded += member.file_size
            ratio = member.file_size / max(member.compress_size, 1)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in member.filename
                or member.file_size > _MAX_ZIP_MEMBER
                or expanded > _MAX_ZIP_EXPANDED
                or ratio > _MAX_ZIP_RATIO
            ):
                raise WorkflowError("工作簿压缩包超出安全限制", "unsafe_workbook_archive", 422)
        yield archive
    finally:
        archive.close()


def _xml_member(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise WorkflowError("工作簿 XML 声明不安全", "unsafe_workbook_archive", 422)
    return ElementTree.fromstring(raw)


def scan_workbook_formulas(path: Path) -> WorkbookFormulaScan:
    """Classify external Excel formulas without importing Excel libraries."""

    workbook = _safe_xlsx(Path(path))
    formulas: list[str] = []
    try:
        with _open_archive(workbook) as archive:
            for name in archive.namelist():
                if not name.startswith("xl/worksheets/") or not name.endswith(".xml"):
                    continue
                root = _xml_member(archive, name)
                formulas.extend(
                    node.text or "" for node in root.iter(f"{{{_MAIN_NS}}}f") if node.text
                )
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        log.warning("report_workbook_scan_failed", error_type=type(exc).__name__)
        raise WorkflowError("工作簿格式无效", "invalid_workbook", 422) from exc
    wind = any(_WIND_PATTERN.search(formula) for formula in formulas)
    ifind = any(_IFIND_PATTERN.search(formula) for formula in formulas)
    provider = (
        WorkbookFormulaProvider.MIXED
        if wind and ifind
        else (
            WorkbookFormulaProvider.WIND
            if wind
            else WorkbookFormulaProvider.IFIND if ifind else WorkbookFormulaProvider.NONE
        )
    )
    return WorkbookFormulaScan(provider=provider, formulas=tuple(formulas))


def _sheet_paths(archive: zipfile.ZipFile) -> tuple[dict[str, str], bool]:
    workbook = _xml_member(archive, "xl/workbook.xml")
    date_1904 = False
    properties = workbook.find(f"{{{_MAIN_NS}}}workbookPr")
    if properties is not None:
        date_1904 = properties.attrib.get("date1904", "0") in {"1", "true", "True"}
    relationships = _xml_member(archive, "xl/_rels/workbook.xml.rels")
    targets = {
        row.attrib["Id"]: row.attrib["Target"]
        for row in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
        if "Id" in row.attrib and "Target" in row.attrib
    }
    paths: dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        relation = sheet.attrib.get(f"{{{_DOC_REL_NS}}}id")
        target = targets.get(relation or "")
        if not target:
            continue
        target_path = PurePosixPath(target)
        if target_path.is_absolute() or ".." in target_path.parts:
            raise WorkflowError("工作簿内部路径无效", "invalid_workbook", 422)
        paths[sheet.attrib["name"]] = (
            target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
        )
    return paths, date_1904


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _xml_member(archive, "xl/sharedStrings.xml")
    return ["".join(node.itertext()) for node in root.findall(f"{{{_MAIN_NS}}}si")]


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> Any:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        node = cell.find(f"{{{_MAIN_NS}}}is")
        return "".join(node.itertext()) if node is not None else None
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return None
    value = value_node.text
    if kind == "s":
        try:
            return shared[int(value)]
        except (IndexError, ValueError):
            return None
    if kind in {"str", "e", "d"}:
        return value
    if kind == "b":
        return value == "1"
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except ValueError:
        return value


def read_cached_workbook(path: Path) -> tuple[dict[str, Any], list[str], bool]:
    """Return cached cells, formula errors, and the workbook date epoch."""

    workbook = _safe_xlsx(Path(path))
    cells: dict[str, Any] = {}
    errors: list[str] = []
    try:
        with _open_archive(workbook) as archive:
            sheets, date_1904 = _sheet_paths(archive)
            shared = _shared_strings(archive)
            for sheet_name, member in sheets.items():
                root = _xml_member(archive, member)
                for cell in root.iter(f"{{{_MAIN_NS}}}c"):
                    reference = cell.attrib.get("r")
                    if not reference:
                        continue
                    key = f"{sheet_name}!{reference.upper()}"
                    value = _cell_value(cell, shared)
                    cells[key] = value
                    if cell.find(f"{{{_MAIN_NS}}}f") is not None and (
                        cell.attrib.get("t") == "e"
                        or (isinstance(value, str) and value.upper() in _FORMULA_ERRORS)
                    ):
                        errors.append(key)
            return cells, errors, date_1904
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        log.warning("report_workbook_cache_read_failed", error_type=type(exc).__name__)
        raise WorkflowError("工作簿缓存值不可读取", "invalid_workbook", 422) from exc


class WorkbookProviderProtocol(Protocol):
    provider_id: str

    def readiness(self) -> dict[str, Any]: ...

    def open_workbook(self, path: Path) -> Any: ...

    def refresh_all(self, handle: Any) -> None: ...

    def calculate_full(self, handle: Any) -> None: ...

    def read_cells(self, handle: Any, references: list[str]) -> dict[str, Any]: ...

    def save(self, handle: Any) -> None: ...

    def close(self, handle: Any) -> None: ...


class XlwingsExcelProvider:
    """Lazy xlwings bridge; public failures are deliberately content-free."""

    provider_id = ""

    def __init__(self) -> None:
        self._xlwings = None
        self._app = None

    def readiness(self) -> dict[str, Any]:
        if sys.platform != "darwin":
            return {"ready": False, "code": "unsupported_platform"}
        try:
            self._xlwings = importlib.import_module("xlwings")
        except (ImportError, OSError):
            return {"ready": False, "code": "xlwings_missing"}
        return {"ready": True, "code": None}

    def open_workbook(self, path: Path) -> Any:
        if self._xlwings is None:
            readiness = self.readiness()
            if not readiness["ready"]:
                raise RuntimeError(readiness["code"])
        self._app = self._xlwings.App(visible=False, add_book=False)
        try:
            return self._app.books.open(str(path), update_links=True, read_only=False)
        except Exception:
            try:
                self._app.quit()
            finally:
                self._app = None
            raise

    def refresh_all(self, handle: Any) -> None:
        api = getattr(handle, "api", None)
        refresh = getattr(api, "RefreshAll", None)
        if not callable(refresh):
            raise RuntimeError("plugin_not_ready")  # noqa: TRY004
        refresh()

    def calculate_full(self, handle: Any) -> None:
        app_api = getattr(getattr(handle, "app", None), "api", None)
        calculate = getattr(app_api, "CalculateFullRebuild", None)
        if callable(calculate):
            calculate()
        else:
            handle.app.calculate()

    def read_cells(self, handle: Any, references: list[str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for reference in references:
            sheet_name, cell = reference.rsplit("!", 1)
            values[reference] = handle.sheets[sheet_name].range(cell).value
        return values

    def save(self, handle: Any) -> None:
        handle.save()

    def close(self, handle: Any) -> None:
        try:
            handle.close()
        finally:
            if self._app is not None:
                self._app.quit()
                self._app = None

    def refresh_with_timeout(self, path: Path, policy: WorkbookRefreshPolicy) -> str | None:
        """Run all provider work in an isolated, killable process tree."""

        result = _run_provider_refresh(self, path, policy, {})
        return None if result.get("status") == "ready" else str(result["code"])


class WindExcelProvider(XlwingsExcelProvider):
    provider_id = "wind_excel"


class IFindExcelProvider(XlwingsExcelProvider):
    provider_id = "ifind_excel"


_SAFE_PROVIDER_CODES = {
    "excel_unavailable",
    "fallback_contract_invalid",
    "plugin_not_ready",
    "provider_not_ready",
    "provider_refresh_failed",
    "provider_timeout",
    "provider_worker_cleanup_failed",
    "provider_worker_failed",
    "refresh_cancelled",
    "unsupported_platform",
    "worker_isolation_failed",
    "xlwings_missing",
}


def _provider_payload(provider: WorkbookProviderProtocol) -> dict[str, Any]:
    if isinstance(provider, XlwingsExcelProvider):
        return {"kind": "xlwings", "provider_id": provider.provider_id}
    return {"kind": "injected", "provider": provider}


def _resolve_provider(payload: dict[str, Any]) -> WorkbookProviderProtocol:
    if payload.get("kind") == "xlwings":
        provider_id = payload.get("provider_id")
        if provider_id == "wind_excel":
            return WindExcelProvider()
        if provider_id == "ifind_excel":
            return IFindExcelProvider()
        raise RuntimeError("provider_not_ready")
    provider = payload.get("provider")
    if provider is None:
        raise RuntimeError("provider_not_ready")
    return provider


def _isolate_worker_process() -> None:
    if os.name == "posix":
        try:
            os.setsid()
        except OSError as exc:
            raise RuntimeError("worker_isolation_failed") from exc


def _safe_provider_code(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value in _SAFE_PROVIDER_CODES else default


def _provider_readiness_worker(payload: dict[str, Any], result_queue: Any) -> None:
    try:
        _isolate_worker_process()
        result = _resolve_provider(payload).readiness()
        if result.get("ready"):
            result_queue.put({"status": "ready"})
        else:
            result_queue.put(
                {
                    "status": "blocked",
                    "code": _safe_provider_code(result.get("code"), "provider_not_ready"),
                }
            )
    except Exception as exc:  # noqa: BLE001 - worker boundary returns safe codes only.
        result_queue.put(
            {
                "status": "blocked",
                "code": _safe_provider_code(str(exc), "provider_worker_failed"),
            }
        )


def _provider_refresh_worker(
    payload: dict[str, Any],
    path: str,
    policy_data: dict[str, Any],
    fallback_mappings: dict[str, dict[str, Any]],
    result_queue: Any,
) -> None:
    handle = None
    provider: WorkbookProviderProtocol | None = None
    result = {"status": "blocked", "code": "provider_refresh_failed"}
    try:
        _isolate_worker_process()
        provider = _resolve_provider(payload)
        policy = WorkbookRefreshPolicy.model_validate(policy_data)
        if fallback_mappings:
            configure = getattr(provider, "configure_fallback", None)
            if not callable(configure):
                raise RuntimeError("fallback_contract_invalid")
            configure(fallback_mappings)
        handle = provider.open_workbook(Path(path))
        if isinstance(provider, XlwingsExcelProvider):
            excel_pid = getattr(provider._app, "pid", None)
            if isinstance(excel_pid, int) and excel_pid > 1:
                result_queue.put({"status": "started", "child_pids": [excel_pid]})
        provider.refresh_all(handle)
        provider.calculate_full(handle)
        references = list(
            dict.fromkeys(
                [
                    *policy.required_cells,
                    *policy.reject_zero_cells,
                    *([policy.required_date_cell] if policy.required_date_cell else []),
                ]
            )
        )
        previous: dict[str, Any] | None = None
        stable = 0
        deadline = time.monotonic() + policy.timeout_seconds
        while stable < policy.stability_checks:
            values = provider.read_cells(handle, references)
            stable = stable + 1 if values == previous else 1
            previous = values
            if stable >= policy.stability_checks:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError
            time.sleep(policy.poll_interval_seconds)
        provider.save(handle)
        result = {"status": "ready"}
    except TimeoutError:
        result = {"status": "blocked", "code": "provider_timeout"}
    except Exception as exc:  # noqa: BLE001 - never serialize provider exception details.
        result = {
            "status": "blocked",
            "code": _safe_provider_code(str(exc), "provider_refresh_failed"),
        }
    finally:
        if handle is not None and provider is not None:
            try:
                provider.close(handle)
            except Exception as exc:  # noqa: BLE001 - final cleanup boundary.
                log.warning(
                    "report_workbook_worker_close_failed",
                    error_type=type(exc).__name__,
                )
                result = {"status": "blocked", "code": "provider_refresh_failed"}
        result_queue.put(result)


def _terminate_worker_tree(process: Any) -> bool:
    pid = getattr(process, "pid", None)
    owns_process_group = False
    if os.name == "posix" and isinstance(pid, int):
        try:
            if os.getpgid(pid) == pid:
                owns_process_group = True
                os.killpg(pid, signal.SIGTERM)
            else:
                process.terminate()
        except OSError:
            process.terminate()
    else:
        process.terminate()
    process.join(_WORKER_STOP_SECONDS)
    if owns_process_group and isinstance(pid, int):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass
    if process.is_alive():
        kill = getattr(process, "kill", None)
        kill() if callable(kill) else process.terminate()
    process.join(_WORKER_STOP_SECONDS)
    return not process.is_alive()


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_child_processes(pids: set[int]) -> bool:
    safe_pids = {pid for pid in pids if pid > 1 and pid != os.getpid()}
    if not safe_pids:
        return True
    if os.name != "posix":
        return False
    for pid in safe_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            return False
    deadline = time.monotonic() + 0.2
    while time.monotonic() < deadline and any(_process_exists(pid) for pid in safe_pids):
        time.sleep(0.02)
    for pid in safe_pids:
        if not _process_exists(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except PermissionError:
            return False
    deadline = time.monotonic() + _WORKER_STOP_SECONDS
    while time.monotonic() < deadline and any(_process_exists(pid) for pid in safe_pids):
        time.sleep(0.02)
    return not any(_process_exists(pid) for pid in safe_pids)


def _drain_worker_messages(result_queue: Any, *, wait: bool) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    while True:
        try:
            item = result_queue.get(timeout=0.1 if wait and not messages else 0)
        except (queue.Empty, TimeoutError):
            break
        if isinstance(item, dict):
            messages.append(item)
    return messages


def _worker_child_pids(messages: list[dict[str, Any]]) -> set[int]:
    return {
        pid for message in messages for pid in message.get("child_pids", []) if isinstance(pid, int)
    }


def _run_provider_worker(
    target: Any,
    args: tuple[Any, ...],
    timeout_seconds: float,
    cancellation_event: threading.Event | None = None,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=4)
    process = context.Process(target=target, args=(*args, result_queue))
    try:
        process.start()
        if cancellation_event is None:
            process.join(timeout_seconds)
        else:
            deadline = time.monotonic() + timeout_seconds
            while process.is_alive() and not cancellation_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                process.join(min(0.1, remaining))
        if process.is_alive():
            messages = _drain_worker_messages(result_queue, wait=True)
            child_pids = _worker_child_pids(messages)
            worker_cleaned = _terminate_worker_tree(process)
            children_cleaned = _terminate_child_processes(child_pids)
            cleaned = worker_cleaned and children_cleaned
            cancelled = cancellation_event is not None and cancellation_event.is_set()
            return {
                "status": "blocked",
                "code": (
                    "refresh_cancelled"
                    if cleaned and cancelled
                    else "provider_timeout" if cleaned else "provider_worker_cleanup_failed"
                ),
            }
        messages = _drain_worker_messages(result_queue, wait=True)
        child_pids = _worker_child_pids(messages)
        results = [message for message in messages if message.get("status") != "started"]
        result = results[-1] if results else None
        if result is not None and result.get("status") == "ready":
            return {"status": "ready"}
        if not _terminate_child_processes(child_pids):
            return {"status": "blocked", "code": "provider_worker_cleanup_failed"}
        if result is None:
            return {"status": "blocked", "code": "provider_worker_failed"}
        return {
            "status": "blocked",
            "code": _safe_provider_code(result.get("code"), "provider_worker_failed"),
        }
    except Exception as exc:  # noqa: BLE001 - process failures are sanitized.
        log.warning("report_provider_worker_failed", error_type=type(exc).__name__)
        try:
            alive = process.is_alive()
        except (AssertionError, ValueError):
            alive = False
        if alive:
            _terminate_worker_tree(process)
        return {"status": "blocked", "code": "provider_worker_failed"}
    finally:
        close = getattr(result_queue, "close", None)
        if callable(close):
            close()


def _run_provider_readiness(
    provider: WorkbookProviderProtocol,
    timeout_seconds: float,
    cancellation_event: threading.Event | None = None,
) -> dict[str, Any]:
    return _run_provider_worker(
        _provider_readiness_worker,
        (_provider_payload(provider),),
        timeout_seconds,
        cancellation_event,
    )


def _run_provider_refresh(
    provider: WorkbookProviderProtocol,
    path: Path,
    policy: WorkbookRefreshPolicy,
    fallback_mappings: dict[str, dict[str, Any]],
    cancellation_event: threading.Event | None = None,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    return _run_provider_worker(
        _provider_refresh_worker,
        (
            _provider_payload(provider),
            str(path),
            json.loads(policy.model_dump_json()),
            fallback_mappings,
        ),
        timeout_seconds if timeout_seconds is not None else policy.timeout_seconds,
        cancellation_event,
    )


def _remaining_refresh_timeout(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _required_provider_ids(provider: WorkbookFormulaProvider) -> set[str]:
    if provider is WorkbookFormulaProvider.MIXED:
        return {"wind_excel", "ifind_excel"}
    if provider is WorkbookFormulaProvider.WIND:
        return {"wind_excel"}
    if provider is WorkbookFormulaProvider.IFIND:
        return {"ifind_excel"}
    return set()


def _coerce_date(value: Any, *, date_1904: bool) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        epoch = date(1904, 1, 1) if date_1904 else date(1899, 12, 30)
        try:
            return epoch + timedelta(days=int(value))
        except OverflowError:
            return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _validate_values(
    cells: dict[str, Any],
    errors: list[str],
    policy: WorkbookRefreshPolicy,
    *,
    date_1904: bool,
    refresh_date: date,
) -> str | None:
    if errors:
        return "formula_error"
    for reference in policy.required_cells:
        value = cells.get(reference)
        if value is None or (isinstance(value, str) and not value.strip()):
            return "required_cell_empty"
    for reference in policy.reject_zero_cells:
        value = cells.get(reference)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isclose(float(value), 0.0, abs_tol=0.0)
        ):
            return "unexpected_zero"
    if policy.required_date_cell:
        actual = _coerce_date(cells.get(policy.required_date_cell), date_1904=date_1904)
        lower_bound = policy.required_date
        if policy.max_age_days is not None:
            dynamic_bound = refresh_date - timedelta(days=policy.max_age_days)
            if lower_bound is None or dynamic_bound > lower_bound:
                lower_bound = dynamic_bound
        if actual is None or (lower_bound is not None and actual < lower_bound):
            return "required_date_stale"
    return None


class WorkbookRefreshService:
    """Copy, refresh, verify and hash workbooks without mutating package masters."""

    def __init__(self, providers: dict[str, WorkbookProviderProtocol] | None = None) -> None:
        self.providers: dict[str, WorkbookProviderProtocol] = (
            providers
            if providers is not None
            else {
                "wind_excel": WindExcelProvider(),
                "ifind_excel": IFindExcelProvider(),
            }
        )

    @staticmethod
    def _blocked(code: str, provider: str | None = None) -> WorkbookRefreshResult:
        log.warning("report_workbook_refresh_blocked", code=code, provider=provider)
        return WorkbookRefreshResult(
            status=RefreshStatus.BLOCKED_DATA, code=code, provider=provider
        )

    def _select_provider(
        self,
        scan: WorkbookFormulaScan,
        policy: WorkbookRefreshPolicy,
        fallback_mappings: dict[str, dict[str, Any]],
        cancellation_event: threading.Event | None,
        deadline: float,
    ) -> tuple[WorkbookProviderProtocol | None, str | None, dict[str, dict[str, Any]]]:
        needed = _required_provider_ids(scan.provider)
        declared = {item.provider.value: item for item in policy.providers}
        if missing := sorted(needed - set(declared)):
            return None, "provider_declaration_missing:" + ",".join(missing), {}
        if not needed:
            return None, None, {}
        unavailable: list[WorkbookProviderRequirement] = []
        unavailable_codes: list[str] = []
        selected: WorkbookProviderProtocol | None = None
        for provider_id in sorted(needed):
            candidate = self.providers.get(provider_id)
            if isinstance(candidate, XlwingsExcelProvider) and sys.platform != "darwin":
                readiness = {"status": "blocked", "code": "unsupported_platform"}
            else:
                remaining = _remaining_refresh_timeout(deadline)
                if remaining <= 0:
                    return None, "provider_timeout", {}
                readiness = (
                    _run_provider_readiness(candidate, remaining, cancellation_event)
                    if candidate is not None
                    else {"status": "blocked", "code": "provider_not_ready"}
                )
            if readiness.get("code") == "refresh_cancelled":
                return None, "refresh_cancelled", {}
            if readiness.get("status") != "ready":
                unavailable.append(declared[provider_id])
                unavailable_codes.append(
                    _safe_provider_code(readiness.get("code"), "provider_not_ready")
                )
            elif selected is None:
                selected = candidate
        if not unavailable:
            # A mixed workbook is refreshed once in the same Excel process. Both
            # add-ins were checked before selecting the bridge used to open Excel.
            return selected, None, {}
        required_mappings = [declared[item].equivalent_datahub_mapping for item in sorted(needed)]
        if all(required_mappings):
            selected_mappings = {
                path: fallback_mappings[path]
                for path in required_mappings
                if path is not None and path in fallback_mappings
            }
            if any(path not in fallback_mappings for path in required_mappings):
                return None, "fallback_mapping_missing", {}
            fallback = self.providers.get("datahub")
            remaining = _remaining_refresh_timeout(deadline)
            if remaining <= 0:
                return None, "provider_timeout", {}
            fallback_readiness = (
                _run_provider_readiness(fallback, remaining, cancellation_event)
                if fallback is not None
                else {"status": "blocked"}
            )
            if fallback_readiness.get("code") == "refresh_cancelled":
                return None, "refresh_cancelled", {}
            if fallback is not None and fallback_readiness.get("status") == "ready":
                if not callable(getattr(fallback, "configure_fallback", None)):
                    return None, "fallback_contract_invalid", {}
                return fallback, None, selected_mappings
        code = (
            "unsupported_platform"
            if "unsupported_platform" in unavailable_codes
            else "provider_not_ready"
        )
        return None, code, {}

    def refresh(
        self,
        source: Path,
        run_directory: Path,
        policy: WorkbookRefreshPolicy,
        *,
        fallback_mappings: dict[str, dict[str, Any]] | None = None,
        refresh_date: date | None = None,
        cancellation_event: threading.Event | None = None,
    ) -> WorkbookRefreshResult:
        deadline = time.monotonic() + policy.timeout_seconds
        try:
            source = _safe_xlsx(Path(source))
            scan = scan_workbook_formulas(source)
        except WorkflowError as exc:
            return self._blocked(exc.code)
        provider, selection_error, selected_mappings = self._select_provider(
            scan, policy, fallback_mappings or {}, cancellation_event, deadline
        )
        if selection_error:
            return self._blocked(selection_error.split(":", 1)[0])
        run_directory = Path(run_directory)
        provider_id = provider.provider_id if provider is not None else None
        try:
            if run_directory.exists() and run_directory.is_symlink():
                return self._blocked("unsafe_run_directory", provider_id)
            run_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            run_root = run_directory.resolve()
            destination = run_directory.joinpath(*PurePosixPath(policy.workbook).parts)
            if (destination.exists() and destination.is_symlink()) or not destination.resolve(
                strict=False
            ).is_relative_to(run_root):
                return self._blocked("unsafe_run_directory", provider_id)
            manifest_name = hashlib.sha256(policy.workbook.encode()).hexdigest() + ".json"
            manifest_path = run_directory / "refresh-manifests" / manifest_name
            lock_directory = run_directory / ".refresh-locks"
            if lock_directory.is_symlink() or not lock_directory.resolve(
                strict=False
            ).is_relative_to(run_root):
                return self._blocked("unsafe_run_directory", provider_id)
        except (OSError, RuntimeError) as exc:
            log.warning(
                "report_workbook_run_directory_unavailable",
                error_type=type(exc).__name__,
            )
            return self._blocked("unsafe_run_directory", provider_id)
        lock_path = lock_directory / f"{manifest_name}.lock"
        try:
            with _file_lock(
                lock_path,
                _target_lock(destination),
                cancellation_event=cancellation_event,
                deadline=deadline,
            ):
                return self._refresh_locked(
                    source,
                    destination,
                    manifest_path,
                    scan,
                    policy,
                    provider,
                    provider_id,
                    selected_mappings,
                    refresh_date or datetime.now().astimezone().date(),
                    cancellation_event,
                    deadline,
                )
        except WorkflowError as exc:
            return self._blocked(exc.code, provider_id)

    def _refresh_locked(
        self,
        source: Path,
        destination: Path,
        manifest_path: Path,
        scan: WorkbookFormulaScan,
        policy: WorkbookRefreshPolicy,
        provider: WorkbookProviderProtocol | None,
        provider_id: str | None,
        selected_mappings: dict[str, dict[str, Any]],
        refresh_date: date,
        cancellation_event: threading.Event | None,
        deadline: float,
    ) -> WorkbookRefreshResult:
        staging = destination.parent / f".{destination.stem}.{uuid4().hex}.refreshing.xlsx"
        manifest_staging = manifest_path.parent / f".{manifest_path.name}.{uuid4().hex}.tmp"
        backup = destination.parent / f".{destination.name}.{uuid4().hex}.backup"
        promoted = False
        if cancellation_event is not None and cancellation_event.is_set():
            return self._blocked("refresh_cancelled", provider_id)
        if _remaining_refresh_timeout(deadline) <= 0:
            return self._blocked("provider_timeout", provider_id)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(source, staging)
            staging.chmod(0o600)
        except OSError as exc:
            _safe_unlink(staging, "report_workbook_staging_cleanup_failed")
            log.warning("report_workbook_copy_failed", error_type=type(exc).__name__)
            return self._blocked("workbook_copy_failed", provider_id)

        try:
            if provider is not None:
                with _file_lock(
                    _GLOBAL_EXCEL_LOCK_PATH,
                    _EXCEL_REFRESH_LOCK,
                    cancellation_event=cancellation_event,
                    deadline=deadline,
                ):
                    remaining = _remaining_refresh_timeout(deadline)
                    if remaining <= 0:
                        return self._blocked("provider_timeout", provider_id)
                    worker_result = _run_provider_refresh(
                        provider,
                        staging,
                        policy,
                        selected_mappings,
                        cancellation_event,
                        timeout_seconds=remaining,
                    )
                if worker_result.get("status") != "ready":
                    return self._blocked(
                        _safe_provider_code(worker_result.get("code"), "provider_refresh_failed"),
                        provider_id,
                    )
            if cancellation_event is not None and cancellation_event.is_set():
                return self._blocked("refresh_cancelled", provider_id)
            if _remaining_refresh_timeout(deadline) <= 0:
                return self._blocked("provider_timeout", provider_id)
            cells, errors, date_1904 = read_cached_workbook(staging)
            if code := _validate_values(
                cells,
                errors,
                policy,
                date_1904=date_1904,
                refresh_date=refresh_date,
            ):
                return self._blocked(code, provider_id)
            resource = WorkflowResource(
                path=policy.workbook,
                role=WorkflowResourceRole.WORKBOOK,
                sha256=_sha256(staging),
                size=staging.stat().st_size,
            )
            manifest = {
                "schema_version": 1,
                "status": "ready",
                "provider": provider_id or WorkbookFormulaProvider.NONE.value,
                "source_sha256": _sha256(source),
                "output_sha256": resource.sha256,
                "workbook": policy.workbook,
                "formula_provider": scan.provider.value,
                "refreshed_at": datetime.now().astimezone().isoformat(),
            }
            with manifest_staging.open("w") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if cancellation_event is not None and cancellation_event.is_set():
                return self._blocked("refresh_cancelled", provider_id)
            if destination.exists():
                destination.chmod(0o600)
                os.replace(destination, backup)
            os.replace(staging, destination)
            promoted = True
            destination.chmod(0o600)
            os.replace(manifest_staging, manifest_path)
            _safe_unlink(backup, "report_workbook_backup_cleanup_failed")
            log.info("report_workbook_refresh_ready", provider=manifest["provider"])
            return WorkbookRefreshResult(
                status=RefreshStatus.READY,
                provider=manifest["provider"],
                resource=resource,
                manifest_path=f"refresh-manifests/{manifest_path.name}",
            )
        except TimeoutError:
            return self._blocked("refresh_not_stable", provider_id)
        except Exception as exc:  # noqa: BLE001 - provider and filesystem failures are sanitized.
            log.warning(
                "report_workbook_refresh_failed",
                provider=provider_id,
                error_type=type(exc).__name__,
            )
            try:
                if backup.exists():
                    _safe_unlink(destination, "report_workbook_rollback_cleanup_failed")
                    os.replace(backup, destination)
                elif promoted:
                    _safe_unlink(destination, "report_workbook_rollback_cleanup_failed")
            except OSError as rollback_exc:
                log.warning(
                    "report_workbook_rollback_failed",
                    error_type=type(rollback_exc).__name__,
                )
            return self._blocked("provider_refresh_failed", provider_id)
        finally:
            _safe_unlink(staging, "report_workbook_staging_cleanup_failed")
            _safe_unlink(manifest_staging, "report_workbook_manifest_cleanup_failed")
            _safe_unlink(backup, "report_workbook_backup_cleanup_failed")
