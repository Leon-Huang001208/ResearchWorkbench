"""Refresh report-owned Excel workbooks before generation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WorkbookRefreshResult:
    """Values confirmed after a successful Excel/Wind refresh."""

    refreshed: bool
    workbook_path: Path
    values: dict[str, Any]


class ReportWorkbookRefreshService:
    """Refresh and persist a report project's Excel formula cache."""

    def __init__(
        self,
        *,
        excel_apps: Callable[[], list[Any]] | None = None,
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
        today: Callable[[], Any] | None = None,
    ) -> None:
        self.excel_apps = excel_apps
        self.sleep = sleep or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.today = today or date.today

    def refresh(self, *, project: Any) -> WorkbookRefreshResult:
        config = dict(project.config.get("excel_refresh") or {})
        workbook_path = Path(project.excel_workbook_path).expanduser().resolve()
        if not workbook_path.exists():
            raise FileNotFoundError(f"报告数据工作簿不存在: {workbook_path}")

        timeout_seconds = max(0.01, float(config.get("timeout_seconds", 180)))
        poll_seconds = max(0.0, float(config.get("poll_seconds", 2)))
        minimum_wait_seconds = max(0.0, float(config.get("minimum_wait_seconds", 5)))
        stable_polls = max(1, int(config.get("stable_polls", 2)))
        date_cell = str(config.get("date_cell") or "").strip()
        required_cells = [
            str(cell).strip() for cell in config.get("required_cells", []) if str(cell).strip()
        ]
        if not date_cell:
            raise ValueError("excel_refresh.date_cell 未配置，无法确认报告日期已刷新")
        validation_cells = [date_cell, *required_cells]

        book = None
        app = None
        opened_by_service = False
        started_app = False
        try:
            app, book, opened_by_service, started_app = self._open_workbook(workbook_path)
            logger.info(
                "Refreshing report workbook through Excel/Wind",
                workbook=str(workbook_path),
                validation_cells=validation_cells,
            )
            self._trigger_calculation(app, book)

            started_at = self.monotonic()
            last_fingerprint: tuple[str, ...] | None = None
            stable_count = 0
            last_values: dict[str, Any] = {}
            while True:
                last_values = self._read_cells(book, validation_cells)
                elapsed = self.monotonic() - started_at
                ready = (
                    self._is_today(last_values.get(date_cell))
                    and all(self._is_valid_value(last_values.get(cell)) for cell in required_cells)
                    and elapsed >= minimum_wait_seconds
                )
                fingerprint = tuple(repr(last_values.get(cell)) for cell in validation_cells)
                if ready and fingerprint == last_fingerprint:
                    stable_count += 1
                elif ready:
                    stable_count = 1
                else:
                    stable_count = 0
                last_fingerprint = fingerprint

                if stable_count >= stable_polls:
                    book.save()
                    logger.info(
                        "Report workbook refresh completed",
                        workbook=str(workbook_path),
                        elapsed_seconds=round(elapsed, 2),
                    )
                    return WorkbookRefreshResult(
                        refreshed=True,
                        workbook_path=workbook_path,
                        values=last_values,
                    )
                if elapsed >= timeout_seconds:
                    raise RuntimeError(
                        f"Wind 数据刷新超时（{timeout_seconds:g} 秒），未保存旧缓存: {workbook_path.name}"
                    )

                self.sleep(poll_seconds)
                self._trigger_calculation(app, book)
        except Exception:
            logger.exception("Report workbook refresh failed", workbook=str(workbook_path))
            raise
        finally:
            self._cleanup(
                book=book,
                app=app,
                opened_by_service=opened_by_service,
                started_app=started_app,
            )

    def _open_workbook(self, workbook_path: Path) -> tuple[Any, Any, bool, bool]:
        """打开工作簿用于刷新。

        始终启动新的隐藏 Excel 实例，不复用用户已打开的 Excel，
        避免共享冲突、COM apartment 问题和文件锁定。
        参照做市项目 copy_excel() 的最佳实践。
        """
        if self.excel_apps is not None:
            # 测试注入路径：仅在测试中使用，保持向后兼容
            apps = list(self.excel_apps())
            for app in apps:
                for book in app.books:
                    if self._same_path(getattr(book, "fullname", ""), workbook_path):
                        return app, book, False, False
            if not apps:
                raise RuntimeError("未找到可用的 Microsoft Excel 实例")
            app = apps[0]
            book = app.books.open(str(workbook_path), update_links=False, read_only=False)
            return app, book, True, False

        # 生产路径：始终创建新的隐藏 Excel 实例
        # 这样做的好处：
        # 1. 不与用户正在编辑的 Excel 冲突
        # 2. 不依赖 COM 跨线程 marshaling
        # 3. Wind 插件在新实例中独立加载，不受用户 Excel 状态影响
        try:
            import pythoncom  # noqa: F401 — 确保 COM 运行时可用
        except ImportError:
            logger.warning("pywin32 (pythoncom) 未安装，xlwings COM 刷新可能不稳定。" "建议: pip install pywin32")
        try:
            import xlwings as xw
        except ImportError as exc:
            raise RuntimeError("缺少 xlwings，无法自动刷新 Excel/Wind 数据") from exc

        app = xw.App(visible=False, add_book=False)
        app.display_alerts = False
        app.screen_updating = False
        book = app.books.open(str(workbook_path), update_links=False, read_only=False)
        return app, book, True, True

    @staticmethod
    def _same_path(candidate: Any, target: Path) -> bool:
        try:
            return Path(str(candidate)).expanduser().resolve() == target
        except (OSError, TypeError, ValueError):
            return False

    @staticmethod
    def _trigger_calculation(app: Any, book: Any) -> None:
        try:
            book.api.RefreshAll()
        except Exception as exc:
            logger.warning("Excel RefreshAll failed, Wind data may be stale", error=str(exc))
        try:
            book.api.Application.CalculateFullRebuild()
        except Exception as exc:
            logger.warning("Excel CalculateFullRebuild failed", error=str(exc))
        try:
            app.calculate()
        except Exception as exc:
            raise RuntimeError(f"Excel 全量重算失败: {exc}") from exc

    @classmethod
    def _read_cells(cls, book: Any, cells: list[str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for reference in cells:
            sheet_name, address = cls._split_reference(reference)
            values[reference] = book.sheets[sheet_name].range(address).value
        return values

    @staticmethod
    def _split_reference(reference: str) -> tuple[str, str]:
        if "!" not in reference:
            raise ValueError(f"Excel 单元格引用格式错误: {reference}")
        sheet_name, address = reference.rsplit("!", 1)
        return sheet_name.strip("'"), address

    def _is_today(self, value: Any) -> bool:
        if isinstance(value, datetime):
            value = value.date()
        return isinstance(value, date) and value == self.today()

    @staticmethod
    def _is_valid_value(value: Any) -> bool:
        if value is None or value == "":
            return False
        if isinstance(value, str):
            normalized = value.strip().lower()
            return not (
                normalized.startswith("#")
                or "requesting data" in normalized
                or "正在请求数据" in normalized
            )
        return True

    @staticmethod
    def _cleanup(*, book: Any, app: Any, opened_by_service: bool, started_app: bool) -> None:
        if opened_by_service and book is not None:
            try:
                book.close()
            except Exception as exc:
                logger.warning("Unable to close refreshed report workbook", error=str(exc))
        if started_app and app is not None:
            try:
                app.quit()
            except Exception as exc:
                logger.warning("Unable to quit Excel refresh instance", error=str(exc))
