"""Standard-library XLSX inspection and serialized Excel refresh services."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import multiprocessing
import os
import re
import shutil
import sys
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
_TARGET_LOCKS: weakref.WeakValueDictionary[str, threading.Lock] = (
    weakref.WeakValueDictionary()
)
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_FORMULA_ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}
_WIND_PATTERN = re.compile(
    r"\b(?:WSD|WSS|WSI|WSET|WST|WQID|WPF|EDB)\s*\(", re.IGNORECASE
)
_IFIND_PATTERN = re.compile(r"\b(?:THS(?:_[A-Z0-9]+)?|IFIND)\s*\(", re.IGNORECASE)
_MAX_ZIP_MEMBERS = 512
_MAX_ZIP_MEMBER = 32 * 1024 * 1024
_MAX_ZIP_EXPANDED = 96 * 1024 * 1024
_MAX_ZIP_RATIO = 200


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class WorkbookFormulaScan:
    provider: WorkbookFormulaProvider
    formulas: tuple[str, ...]


def _safe_xlsx(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WorkflowError("工作簿不可读取", "workbook_unreadable", 400) from exc
    if path.is_symlink() or not resolved.is_file() or resolved.suffix.lower() != ".xlsx":
        raise WorkflowError("工作簿不可读取", "workbook_unreadable", 400)
    return resolved


def _target_lock(path: Path) -> threading.Lock:
    key = str(path.resolve(strict=False))
    with _TARGET_LOCKS_GUARD:
        lock = _TARGET_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _TARGET_LOCKS[key] = lock
        return lock


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
                raise WorkflowError(
                    "工作簿压缩包超出安全限制", "unsafe_workbook_archive", 422
                )
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
        else WorkbookFormulaProvider.WIND
        if wind
        else WorkbookFormulaProvider.IFIND
        if ifind
        else WorkbookFormulaProvider.NONE
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
    bounded_calls: bool

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
    # Official providers execute refresh in a killable worker process. Direct
    # methods remain for adapter tests, not for production refresh orchestration.
    bounded_calls = True

    def __init__(self) -> None:
        self._xlwings = None
        self._app = None

    def readiness(self) -> dict[str, Any]:
        try:
            self._xlwings = importlib.import_module("xlwings")
        except (ImportError, OSError):
            return {"ready": False, "code": "xlwings_missing"}
        if sys.platform not in {"win32", "darwin"}:
            return {"ready": False, "code": "excel_unavailable"}
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
        """Run all COM/AppScript work in a terminable spawned process."""

        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=_xlwings_refresh_worker,
            args=(self.provider_id, str(path), json.loads(policy.model_dump_json()), result_queue),
        )
        process.start()
        process.join(policy.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(5)
            result_queue.close()
            return "provider_timeout"
        try:
            result = result_queue.get_nowait()
        except Exception:  # noqa: BLE001 - multiprocessing queues vary by platform.
            result = {"status": "blocked", "code": "provider_worker_failed"}
        finally:
            result_queue.close()
        return None if result.get("status") == "ready" else result.get(
            "code", "provider_worker_failed"
        )


class WindExcelProvider(XlwingsExcelProvider):
    provider_id = "wind_excel"


class IFindExcelProvider(XlwingsExcelProvider):
    provider_id = "ifind_excel"


def _xlwings_refresh_worker(
    provider_id: str, path: str, policy_data: dict[str, Any], result_queue: Any
) -> None:
    """Isolated Excel worker; only safe status codes cross the process boundary."""

    app = None
    book = None
    try:
        policy = WorkbookRefreshPolicy.model_validate(policy_data)
        xlwings = importlib.import_module("xlwings")
        app = xlwings.App(visible=False, add_book=False)
        book = app.books.open(path, update_links=True, read_only=False)
        api = getattr(book, "api", None)
        refresh = getattr(api, "RefreshAll", None)
        if not callable(refresh):
            raise RuntimeError("plugin_not_ready")  # noqa: TRY004
        refresh()
        app_api = getattr(getattr(book, "app", None), "api", None)
        calculate = getattr(app_api, "CalculateFullRebuild", None)
        calculate() if callable(calculate) else book.app.calculate()
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
            values = {}
            for reference in references:
                sheet_name, cell = reference.rsplit("!", 1)
                values[reference] = book.sheets[sheet_name].range(cell).value
            stable = stable + 1 if values == previous else 1
            previous = values
            if stable >= policy.stability_checks:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError
            time.sleep(policy.poll_interval_seconds)
        book.save()
        result_queue.put({"status": "ready", "provider": provider_id})
    except TimeoutError:
        result_queue.put({"status": "blocked", "code": "provider_timeout"})
    except Exception:  # noqa: BLE001 - never serialize provider exception details.
        result_queue.put({"status": "blocked", "code": "provider_refresh_failed"})
    finally:
        if book is not None:
            try:
                book.close()
            except Exception as exc:  # noqa: BLE001 - final cleanup boundary.
                log.warning(
                    "report_workbook_worker_close_failed",
                    error_type=type(exc).__name__,
                )
        if app is not None:
            try:
                app.quit()
            except Exception as exc:  # noqa: BLE001 - final cleanup boundary.
                log.warning(
                    "report_workbook_worker_quit_failed",
                    error_type=type(exc).__name__,
                )


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
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isclose(
            float(value), 0.0, abs_tol=0.0
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
    ) -> tuple[WorkbookProviderProtocol | None, str | None, dict[str, dict[str, Any]]]:
        needed = _required_provider_ids(scan.provider)
        declared = {item.provider.value: item for item in policy.providers}
        if missing := sorted(needed - set(declared)):
            return None, "provider_declaration_missing:" + ",".join(missing), {}
        if not needed:
            return None, None, {}
        unavailable: list[WorkbookProviderRequirement] = []
        selected: WorkbookProviderProtocol | None = None
        for provider_id in sorted(needed):
            candidate = self.providers.get(provider_id)
            readiness = candidate.readiness() if candidate is not None else {"ready": False}
            if not readiness.get("ready"):
                unavailable.append(declared[provider_id])
            elif selected is None:
                selected = candidate
        if not unavailable:
            # A mixed workbook is refreshed once in the same Excel process. Both
            # add-ins were checked before selecting the bridge used to open Excel.
            if selected is not None and not getattr(selected, "bounded_calls", False):
                return None, "provider_timeout_unenforced", {}
            return selected, None, {}
        required_mappings = [declared[item].equivalent_datahub_mapping for item in sorted(needed)]
        if all(required_mappings):
            selected_mappings = {
                path: fallback_mappings[path]
                for path in required_mappings
                if path is not None and path in fallback_mappings
            }
            if len(selected_mappings) != len(required_mappings):
                return None, "fallback_mapping_missing", {}
            fallback = self.providers.get("datahub")
            if fallback is not None and fallback.readiness().get("ready"):
                if not getattr(fallback, "bounded_calls", False):
                    return None, "provider_timeout_unenforced", {}
                if not callable(getattr(fallback, "configure_fallback", None)):
                    return None, "fallback_contract_invalid", {}
                return fallback, None, selected_mappings
        return None, "provider_not_ready", {}

    def refresh(
        self,
        source: Path,
        run_directory: Path,
        policy: WorkbookRefreshPolicy,
        *,
        fallback_mappings: dict[str, dict[str, Any]] | None = None,
        refresh_date: date | None = None,
    ) -> WorkbookRefreshResult:
        source = _safe_xlsx(Path(source))
        scan = scan_workbook_formulas(source)
        provider, selection_error, selected_mappings = self._select_provider(
            scan, policy, fallback_mappings or {}
        )
        if selection_error:
            return self._blocked(selection_error.split(":", 1)[0])
        run_directory = Path(run_directory)
        if run_directory.exists() and run_directory.is_symlink():
            return self._blocked("unsafe_run_directory")
        run_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        run_root = run_directory.resolve()
        destination = run_directory.joinpath(*PurePosixPath(policy.workbook).parts)
        if (
            (destination.exists() and destination.is_symlink())
            or not destination.resolve(strict=False).is_relative_to(run_root)
        ):
            return self._blocked("unsafe_run_directory")
        provider_id = provider.provider_id if provider is not None else None
        manifest_name = hashlib.sha256(policy.workbook.encode()).hexdigest() + ".json"
        manifest_path = run_directory / "refresh-manifests" / manifest_name
        with _target_lock(destination):
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
            )

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
    ) -> WorkbookRefreshResult:
        staging = destination.parent / f".{destination.stem}.{uuid4().hex}.refreshing.xlsx"
        manifest_staging = manifest_path.parent / f".{manifest_path.name}.{uuid4().hex}.tmp"
        backup = destination.parent / f".{destination.name}.{uuid4().hex}.backup"
        promoted = False
        try:
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            manifest_path.unlink(missing_ok=True)
            shutil.copy2(source, staging)
            staging.chmod(0o600)
        except OSError as exc:
            staging.unlink(missing_ok=True)
            log.warning("report_workbook_copy_failed", error_type=type(exc).__name__)
            return self._blocked("workbook_copy_failed", provider_id)

        handle = None
        try:
            if provider is not None:
                if selected_mappings:
                    configure_fallback = getattr(provider, "configure_fallback", None)
                    if callable(configure_fallback):
                        configure_fallback(selected_mappings)
                with _EXCEL_REFRESH_LOCK:
                    if isinstance(provider, XlwingsExcelProvider):
                        if code := provider.refresh_with_timeout(staging, policy):
                            staging.unlink(missing_ok=True)
                            return self._blocked(code, provider_id)
                    else:
                        handle = provider.open_workbook(staging)
                        try:
                            provider.refresh_all(handle)
                            provider.calculate_full(handle)
                            references = list(
                                dict.fromkeys(
                                    [
                                        *policy.required_cells,
                                        *policy.reject_zero_cells,
                                        *(
                                            [policy.required_date_cell]
                                            if policy.required_date_cell
                                            else []
                                        ),
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
                                    raise TimeoutError("refresh_not_stable")
                                time.sleep(policy.poll_interval_seconds)
                            provider.save(handle)
                        finally:
                            provider.close(handle)
                            handle = None
            cells, errors, date_1904 = read_cached_workbook(staging)
            if code := _validate_values(
                cells,
                errors,
                policy,
                date_1904=date_1904,
                refresh_date=refresh_date,
            ):
                staging.unlink(missing_ok=True)
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
            if destination.exists():
                destination.chmod(0o600)
                os.replace(destination, backup)
            os.replace(staging, destination)
            promoted = True
            destination.chmod(0o600)
            os.replace(manifest_staging, manifest_path)
            backup.unlink(missing_ok=True)
            log.info("report_workbook_refresh_ready", provider=manifest["provider"])
            return WorkbookRefreshResult(
                status=RefreshStatus.READY,
                provider=manifest["provider"],
                resource=resource,
                manifest_path=str(manifest_path),
            )
        except TimeoutError:
            return self._blocked("refresh_not_stable", provider_id)
        except Exception as exc:  # noqa: BLE001 - provider and filesystem failures are sanitized.
            log.warning(
                "report_workbook_refresh_failed",
                provider=provider_id,
                error_type=type(exc).__name__,
            )
            if handle is not None and provider is not None:
                try:
                    provider.close(handle)
                except Exception as close_exc:  # noqa: BLE001 - best-effort provider cleanup.
                    log.warning(
                        "report_workbook_close_failed", error_type=type(close_exc).__name__
                    )
            if backup.exists():
                destination.unlink(missing_ok=True)
                os.replace(backup, destination)
            elif promoted:
                destination.unlink(missing_ok=True)
            return self._blocked("provider_refresh_failed", provider_id)
        finally:
            staging.unlink(missing_ok=True)
            manifest_staging.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
