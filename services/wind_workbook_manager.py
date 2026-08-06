"""Background lifecycle manager for the Wind realtime Excel workbook."""

from __future__ import annotations

import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from core.observability import get_logger
from core.settings.paths import migrate_legacy_wind_workbook
from services.wind_index_catalog import (
    DEFAULT_WIND_INDEX_CATALOG_PATH,
    load_wind_index_catalog,
)
from services.wind_realtime_workbook import (
    DEFAULT_WORKBOOK_PATH,
    SNAPSHOT_HEADERS,
    _rows_from_matrix,
    build_realtime_workbook,
    prime_realtime_workbook_formulas,
)

logger = get_logger(__name__)

WIND_WORKBOOK_AUTOSTART_ENV = "ALPHAFOUNDRY_WIND_WORKBOOK_AUTOSTART"
WIND_WORKBOOK_HIDE_EXCEL_ENV = "ALPHAFOUNDRY_WIND_WORKBOOK_HIDE_EXCEL"
WIND_WORKBOOK_RECOVERY_COOLDOWN_SECONDS = 30.0
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / DEFAULT_WIND_INDEX_CATALOG_PATH


@dataclass(frozen=True)
class WindWorkbookRuntimeStatus:
    """Last known runtime state for the Wind realtime workbook."""

    status: str
    message: str
    workbook_path: str
    ready: bool = False
    built: bool = False
    opened: bool = False
    primed: bool = False
    attempted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WindWorkbookManager:
    """Ensure the Excel workbook exists, is open, and has active Wind formulas."""

    def __init__(
        self,
        *,
        workbook_path: str | Path | None = None,
        catalog_path: str | Path | None = None,
    ) -> None:
        self.workbook_path = Path(workbook_path or DEFAULT_WORKBOOK_PATH).expanduser()
        self.catalog_path = Path(catalog_path or DEFAULT_CATALOG_PATH).expanduser()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._last_attempt_monotonic = 0.0
        self._last_status = WindWorkbookRuntimeStatus(
            status="not_started",
            message="Wind实时工作簿后台管理尚未启动",
            workbook_path=str(self.workbook_path),
        )

    def autostart_enabled(self) -> bool:
        default = os.getenv("ALPHAFOUNDRY_DESKTOP") == "1" and platform.system() == "Darwin"
        return _env_flag(WIND_WORKBOOK_AUTOSTART_ENV, default=default)

    def hide_excel_enabled(self) -> bool:
        return _env_flag(WIND_WORKBOOK_HIDE_EXCEL_ENV, default=True)

    def last_status(self) -> WindWorkbookRuntimeStatus:
        with self._lock:
            return self._last_status

    def start_background_ensure(self, *, reason: str = "manual") -> WindWorkbookRuntimeStatus:
        """Start one non-blocking recovery/prime task if allowed."""
        if not self.autostart_enabled():
            status = self._set_status(
                status="disabled",
                message=f"Wind实时工作簿后台自启动未启用: {WIND_WORKBOOK_AUTOSTART_ENV}",
            )
            logger.info("Wind workbook background ensure skipped: %s", reason)
            return status

        with self._lock:
            now = time.monotonic()
            if self._thread and self._thread.is_alive():
                return self._last_status
            if now - self._last_attempt_monotonic < WIND_WORKBOOK_RECOVERY_COOLDOWN_SECONDS:
                return self._last_status
            self._last_attempt_monotonic = now
            self._thread = Thread(
                target=self._ensure_ready_logged,
                kwargs={"reason": reason},
                name="wind-workbook-manager",
                daemon=True,
            )
            self._thread.start()
            self._last_status = WindWorkbookRuntimeStatus(
                status="starting",
                message=f"Wind实时工作簿后台准备中: {reason}",
                workbook_path=str(self.workbook_path),
                attempted_at=_utc_now(),
            )
            return self._last_status

    def ensure_ready(
        self, *, reason: str = "manual", force_prime: bool = False
    ) -> WindWorkbookRuntimeStatus:
        """Synchronously ensure the workbook exists and is usable."""
        if not self.autostart_enabled():
            return self._set_status(
                status="disabled",
                message=f"Wind实时工作簿后台自启动未启用: {WIND_WORKBOOK_AUTOSTART_ENV}",
            )

        built = False
        opened = False
        primed = False
        try:
            if not self.workbook_path.exists():
                # 迁移旧 macOS 风格路径下的工作簿（若有），避免重新 prime 公式
                migrate_legacy_wind_workbook(self.workbook_path)
            if not self.workbook_path.exists():
                build_realtime_workbook(self.catalog_path, self.workbook_path)
                built = True

            expected_active_count = self._catalog_active_index_count()

            import xlwings as xw

            book = self._find_or_open_workbook(xw)
            opened = True
            self._hide_excel(book.app)

            if not self._workbook_matches_catalog(book, expected_active_count):
                logger.info(
                    "Wind workbook catalog changed; rebuilding workbook: path=%s expected_active_count=%s",
                    self.workbook_path,
                    expected_active_count,
                )
                self._close_workbook(book)
                build_realtime_workbook(self.catalog_path, self.workbook_path)
                built = True
                book = self._find_or_open_workbook(xw)
                opened = True
                self._hide_excel(book.app)

            if not force_prime:
                if self._snapshot_has_data(book):
                    return self._set_status(
                        status="ready",
                        message=f"Wind实时工作簿已在后台运行: {reason}",
                        ready=True,
                        built=built,
                        opened=opened,
                        primed=False,
                    )
                if not built:
                    logger.warning(
                        "Wind workbook has no snapshot data; skipping automatic formula priming: "
                        "path=%s reason=%s",
                        self.workbook_path,
                        reason,
                    )
                    return self._set_status(
                        status="no_snapshot_data",
                        message=("Wind实时工作簿已打开但暂无有效行情；" "为避免干扰Excel，未自动重写公式，请确认Wind插件已登录或手动修复"),
                        built=built,
                        opened=opened,
                        primed=False,
                    )

            prime_realtime_workbook_formulas(
                self.workbook_path,
                chunk_size=1,
                pause_seconds=0.0,  # polling replaces fixed sleep; kept for API compat
                visible=not self.hide_excel_enabled(),
            )
            primed = True

            book = self._find_or_open_workbook(xw)
            self._hide_excel(book.app)
            if self._snapshot_has_data(book):
                return self._set_status(
                    status="ready",
                    message=f"Wind实时工作簿已后台激活: {reason}",
                    ready=True,
                    built=built,
                    opened=opened,
                    primed=primed,
                )

            return self._set_status(
                status="no_snapshot_data",
                message="Wind实时工作簿已打开，但暂未读到有效行情；请确认Wind插件已登录",
                built=built,
                opened=opened,
                primed=primed,
            )
        except Exception as exc:
            logger.warning("Wind realtime workbook background ensure failed: %s", exc)
            return self._set_status(
                status="error",
                message=f"Wind实时工作簿后台准备失败: {exc}",
                built=built,
                opened=opened,
                primed=primed,
            )

    def _ensure_ready_logged(self, *, reason: str) -> None:
        from services.resource_task_registry import resource_task

        logger.info("Wind workbook background ensure started: %s", reason)
        with resource_task(task_kind="wind", label="Wind 工作簿准备"):
            status = self.ensure_ready(reason=reason)
        logger.info("Wind workbook background ensure finished: %s", status.to_dict())

    def _find_or_open_workbook(self, xw: Any) -> Any:
        target = self.workbook_path.resolve()
        for app in xw.apps:
            for candidate in app.books:
                fullname = str(getattr(candidate, "fullname", "") or "")
                if not fullname:
                    continue
                try:
                    if Path(fullname).expanduser().resolve() == target:
                        return candidate
                except OSError:
                    if Path(fullname).expanduser() == self.workbook_path:
                        return candidate

        hide = self.hide_excel_enabled()
        app = xw.apps.active or xw.App(visible=not hide)
        try:
            app.display_alerts = False
        except Exception as exc:
            logger.debug("Unable to suppress Excel alerts: %s", exc)
        try:
            app.visible = not hide
        except Exception as exc:
            logger.debug("Unable to set Excel visibility: %s", exc)
        return self._open_book_via_com(app, target)

    def _open_book_via_com(self, app: Any, target: Path) -> Any:
        """Open a workbook using the underlying COM object with CorruptLoad=2.

        xlwings ``books.open`` does not expose the ``CorruptLoad`` parameter, and
        Excel 16 raises com_error 0x800A03EC ("Invalid procedure call") when it
        tries to show a security / repair / Protected-View dialog in a headless COM
        session.  Passing ``CorruptLoad=2`` (xlRepairFile) suppresses that dialog
        and lets Excel open the file without user interaction.
        """
        # xlRepairFile = 2
        XL_REPAIR_FILE = 2
        try:
            raw_wb = app.api.Workbooks.Open(
                str(target),
                UpdateLinks=0,
                ReadOnly=False,
                CorruptLoad=XL_REPAIR_FILE,
            )
            # Wrap the win32com workbook back in an xlwings Book object
            import xlwings as xw  # noqa: PLC0415

            return xw.Book(raw_wb.FullName)
        except Exception as exc:
            logger.debug(
                "COM open with CorruptLoad failed (%s); falling back to xlwings books.open", exc
            )
            return app.books.open(str(target), update_links=False, read_only=False)

    def _hide_excel(self, app: Any) -> None:
        if not self.hide_excel_enabled():
            return
        try:
            app.visible = False
        except Exception as exc:
            logger.debug("Unable to hide Excel via xlwings: %s", exc)
        if platform.system() == "Darwin":
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to set visible of process "Microsoft Excel" to false',
                    ],
                    check=False,
                    timeout=5,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                logger.debug("Unable to hide Excel via osascript: %s", exc)

    def _snapshot_has_data(self, book: Any) -> bool:
        try:
            sheet = book.sheets["Snapshot"]
            max_rows = min(80, int(sheet.used_range.last_cell.row))
            if max_rows < 2:
                return False
            values = sheet.range((2, 1), (max_rows, len(SNAPSHOT_HEADERS))).value
            matrix = values if isinstance(values, list) else [values]
            for row in matrix:
                if not isinstance(row, list) or len(row) < len(SNAPSHOT_HEADERS):
                    continue
                pct_change = row[5]
                status = str(row[9] or "").strip()
                if status == "ok" and pct_change not in (None, ""):
                    return True
        except Exception as exc:
            logger.debug("Unable to inspect Wind workbook snapshot: %s", exc)
        return False

    def _catalog_active_index_count(self) -> int | None:
        try:
            return sum(1 for entry in load_wind_index_catalog(self.catalog_path) if entry.is_active)
        except Exception as exc:
            logger.warning("Unable to inspect Wind index catalog %s: %s", self.catalog_path, exc)
            return None

    def _workbook_matches_catalog(self, book: Any, expected_active_count: int | None) -> bool:
        if expected_active_count is None:
            return True
        active_count = self._workbook_active_index_count(book)
        if active_count is None:
            return False
        return active_count == expected_active_count

    def _workbook_active_index_count(self, book: Any) -> int | None:
        try:
            rows = _rows_from_matrix(book.sheets["Health"].used_range.value)
            for row in rows:
                if str(row.get("metric") or "") == "active_index_count":
                    return int(float(row.get("value") or 0))
        except Exception as exc:
            logger.debug("Unable to inspect Wind workbook health: %s", exc)
        return None

    def _close_workbook(self, book: Any) -> None:
        try:
            book.close()
        except Exception as exc:
            logger.debug("Unable to close stale Wind workbook: %s", exc)

    def _set_status(
        self,
        *,
        status: str,
        message: str,
        ready: bool = False,
        built: bool = False,
        opened: bool = False,
        primed: bool = False,
    ) -> WindWorkbookRuntimeStatus:
        runtime_status = WindWorkbookRuntimeStatus(
            status=status,
            message=message,
            workbook_path=str(self.workbook_path),
            ready=ready,
            built=built,
            opened=opened,
            primed=primed,
            attempted_at=_utc_now(),
        )
        with self._lock:
            self._last_status = runtime_status
        return runtime_status


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


_manager: WindWorkbookManager | None = None
_manager_lock = Lock()


def get_wind_workbook_manager() -> WindWorkbookManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = WindWorkbookManager()
        return _manager
