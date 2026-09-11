"""Wind Excel 客户端 —— 通过 xlwings 操控 Excel Wind 插件"""

import math
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from core.observability import get_logger
from data_layer.adapters.wind.exceptions import (
    WindFormulaError,
    WindNotConnectedError,
    WindSessionExpiredError,
    WindTimeoutError,
)

logger = get_logger(__name__)
_EXCEL_OPERATION_LOCK = threading.RLock()

HEARTBEAT_FORMULA = '=@s_info_compname("600519.SH")'
HEARTBEAT_EXPECTED = "贵州茅台酒股份有限公司"
HEARTBEAT_RETRIES = 2
HEARTBEAT_RETRY_DELAY = 2.0

HELPER_SHEET_NAME = "_wind_helper_"
HELPER_MAX_ROW = 10000
WSD_MAX_RETRIES = 3
WSD_RETRY_BASE_DELAY = 3.0
WSD_RETRY_MAX_DELAY = 30.0
WSD_BASE_TIMEOUT = 15.0
WSD_EXTRA_TIMEOUT_PER_DAYS = 250
WSD_EXTRA_TIMEOUT_SECONDS = 5.0

EXCEL_ERRORS = frozenset({"#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"})
WIND_LOADING = frozenset(
    {"fetch...", "fetching...", "loading...", "calculating...", "connecting..."}
)


def _is_error_value(value: Any) -> bool:
    """检查返回值是否是 Excel 错误"""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.upper() in EXCEL_ERRORS:
            return True
        if stripped.lower() in WIND_LOADING:
            return True
    return False


def _offset_excel_column(column: str, offset: int) -> str:
    """Return an Excel column name offset from ``column`` without Excel APIs."""
    number = 0
    for char in column.upper():
        number = number * 26 + ord(char) - ord("A") + 1
    number += offset
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _trim_wsd_matrix(raw_data: Any) -> list[list[Any]]:
    """Trim a rectangular Excel spill range to its populated rows and columns."""
    if raw_data is None:
        return []
    rows = raw_data if isinstance(raw_data, list) else [[raw_data]]
    if rows and not isinstance(rows[0], list):
        rows = [[value] for value in rows]
    matrix = [list(row) if isinstance(row, list) else [row] for row in rows]
    populated = [row for row in matrix if any(value is not None for value in row)]
    if not populated:
        return []
    width = max(
        index + 1 for row in populated for index, value in enumerate(row) if value is not None
    )
    return [row[:width] for row in populated]


class WindExcelClient:
    """通过 xlwings 操控 Excel 中的 Wind 插件执行公式"""

    def __init__(
        self,
        visible: bool = False,
        timeout: float = 15.0,
        *,
        isolated_workbook: bool = False,
    ):
        self._visible = visible
        self._timeout = timeout
        self._isolated_workbook = isolated_workbook
        self._app = None
        self._wb = None
        self._sheet = None
        self._owns_app = False
        self._owns_workbook = False
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_running = False
        self._keepalive_interval = 1800  # 默认 30 分钟
        self._last_heartbeat_time: float = 0.0
        self._heartbeat_ttl: float = 30.0  # 30s 内复用 heartbeat 结果
        self._helper_row = 1000
        self._helper_lock = threading.Lock()

    def _connect(self):
        """连接 Excel；验证任务可强制使用独立且由客户端持有的实例。"""
        try:
            import xlwings as xw
        except Exception:  # noqa: BLE001
            raise WindNotConnectedError(
                "xlwings not available (NumPy/matplotlib compatibility issue?)"
            )

        # 枚举实例也会初始化 macOS xlwings 引擎。Wind 的登录会话属于
        # 已运行的 Excel 实例，所以优先复用应用；验证任务通过独占空白
        # 工作簿隔离，绝不写入用户当前打开的工作簿。
        try:
            all_apps = list(xw.apps)
        except Exception as exc:  # noqa: BLE001
            logger.debug("无法枚举运行中的 Excel 实例: %s", exc)
            all_apps = []

        if all_apps:
            self._app = all_apps[0]
            logger.info(f"已连接到运行中的 Excel 实例 (PID={self._app.pid})")
            self._owns_app = False
        else:
            logger.info("未检测到运行中的 Excel，启动新实例")
            self._app = xw.App(visible=self._visible, add_book=True)
            self._owns_app = True

        # 验证任务必须持有自己的 workbook；普通数据调用保持原有复用行为。
        if self._isolated_workbook and not self._owns_app:
            self._wb = self._app.books.add()
            self._owns_workbook = True
            logger.info("已创建隔离的 Wind 验证工作簿")
        elif len(self._app.books) == 0:
            self._wb = self._app.books.add()
            self._owns_workbook = True
        else:
            self._wb = self._app.books[0]
            self._owns_workbook = self._isolated_workbook

        # Wind Mac 插件在新建 helper sheet 上偶尔只返回 Fetching。
        # 仍使用第一个 sheet，但落在很远的 ZZ 列和高行，避免覆盖用户可见区域和旧缓存。
        self._sheet = self._get_formula_sheet()
        self._helper_row = int(time.time() * 1000) % 5000 + 1000
        try:
            sheet_name = self._sheet.name
        except Exception:  # noqa: BLE001
            sheet_name = HELPER_SHEET_NAME
        logger.info(f"使用工作表: {sheet_name}")
        self._col = "ZZ"

    def _get_or_create_helper_sheet(self):
        sheets = self._wb.sheets
        try:
            for sheet in sheets:
                if getattr(sheet, "name", None) == HELPER_SHEET_NAME:
                    return sheet
        except Exception:  # noqa: BLE001, S110
            pass
        try:
            return sheets.add(name=HELPER_SHEET_NAME)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Unable to create Wind helper sheet: %s", exc)
            return sheets[0]

    def _get_formula_sheet(self):
        sheets = self._wb.sheets
        try:
            for sheet in sheets:
                if getattr(sheet, "name", None) != HELPER_SHEET_NAME:
                    return sheet
        except Exception:  # noqa: BLE001, S110
            pass
        return sheets[0]

    def heartbeat(self) -> bool:
        """检测 Wind 会话是否有效（带重试，处理 Wind 加载中间态）"""
        with _EXCEL_OPERATION_LOCK:
            for attempt in range(1, HEARTBEAT_RETRIES + 1):
                try:
                    result = self._execute_raw(HEARTBEAT_FORMULA, timeout=5.0)
                    if result is None:
                        logger.warning(f"Wind 心跳返回 None (第{attempt}次)")
                        time.sleep(HEARTBEAT_RETRY_DELAY)
                        continue
                    if isinstance(result, str):
                        stripped = result.strip()
                        if stripped == HEARTBEAT_EXPECTED:
                            logger.info("Wind 会话心跳检测通过")
                            return True
                        if stripped.lower() in WIND_LOADING:
                            logger.info(f"Wind 仍在加载中: {result!r} (第{attempt}次)")
                            time.sleep(HEARTBEAT_RETRY_DELAY)
                            continue
                        if stripped.upper() in EXCEL_ERRORS:
                            logger.warning(f"Wind 公式返回 Excel 错误: {result!r}")
                            return False
                        logger.warning(f"Wind 心跳异常返回值: {result!r}")
                    else:
                        logger.warning(
                            f"Wind 心跳异常类型: {type(result).__name__}={result!r} (第{attempt}次)"
                        )
                        time.sleep(HEARTBEAT_RETRY_DELAY)
                        continue
                    return False
                except WindTimeoutError:
                    logger.warning(f"Wind 心跳超时 (第{attempt}次)")
                    time.sleep(HEARTBEAT_RETRY_DELAY)
            return False

    def _ensure_connected(self):
        """确保已连接到 Excel"""
        if self._app is None:
            self._connect()

    def _ensure_session(self):
        """确保 Wind 会话有效，否则抛出异常。

        使用 TTL 缓存 heartbeat 结果（默认 30s），避免每次 xlwings COM 调用
        都做一次完整的 Wind 公式心跳（约 2-5s/次）。
        """
        self._ensure_connected()
        now = time.time()
        if now - self._last_heartbeat_time < self._heartbeat_ttl:
            return  # TTL 内复用上次结果
        if not self.heartbeat():
            raise WindSessionExpiredError()
        self._last_heartbeat_time = now

    def _execute_raw(self, formula: str, timeout: float | None = None) -> Any:
        """底层：写公式到 Excel 单元格，等待求值，读回结果"""
        self._ensure_connected()

        timeout = timeout or self._timeout
        start_row = self._allocate_helper_rows(1)
        cell = self._sheet.range(f"{self._col}{start_row}")
        cell.value = None
        time.sleep(0.05)
        cell.value = formula

        try:
            elapsed = 0.0
            interval = 0.3
            while elapsed < timeout:
                time.sleep(interval)
                elapsed += interval
                result = cell.value
                if not _is_error_value(result):
                    return result
                if result is None:
                    continue
                error_str = str(result).strip().upper()
                if error_str in EXCEL_ERRORS:
                    return result
        finally:
            try:
                cell.value = None
            except Exception as exc:  # noqa: BLE001
                logger.debug("Unable to clear Wind formula cell: %s", exc)

        raise WindTimeoutError(formula, timeout)

    def _allocate_helper_rows(self, count: int) -> int:
        with self._helper_lock:
            if self._helper_row + count > HELPER_MAX_ROW:
                self._helper_row = 1
            start_row = self._helper_row
            self._helper_row += max(count, 1)
            return start_row

    def execute(self, formula: str, timeout: float | None = None) -> Any:
        """执行单条 Wind 公式并返回结果（自动检测会话）"""
        with _EXCEL_OPERATION_LOCK:
            self._ensure_session()
            result = self._execute_raw(formula, timeout=timeout)
            if _is_error_value(result):
                raise WindFormulaError(formula, str(result) if result else "#N/A")
            return result

    def _wsd_timeout(self, start_date: str, end_date: str) -> float:
        """Return a bounded timeout that grows with the requested date range."""
        try:
            days = max(
                1,
                (
                    datetime.strptime(end_date, "%Y-%m-%d")  # noqa: DTZ007
                    - datetime.strptime(start_date, "%Y-%m-%d")  # noqa: DTZ007
                ).days,
            )
        except (TypeError, ValueError):
            days = 365
        return (
            WSD_BASE_TIMEOUT
            + math.ceil(days / WSD_EXTRA_TIMEOUT_PER_DAYS) * WSD_EXTRA_TIMEOUT_SECONDS
        )

    def execute_wsd(
        self,
        code: str,
        fields: str,
        start_date: str,
        end_date: str,
        options: str = "",
        timeout: float | None = None,
    ) -> list[list[Any]]:
        """Execute a Wind WSD time-series formula and return its spilled matrix.

        The helper range is cleared both before and after every attempt so a failed
        request cannot leak stale cells into a later request.
        """
        formula = f'=wsd("{code}","{fields}","{start_date}","{end_date}","{options}")'
        calculated_timeout = timeout or self._wsd_timeout(start_date, end_date)
        last_error: WindTimeoutError | WindSessionExpiredError | None = None
        with _EXCEL_OPERATION_LOCK:
            for attempt in range(1, WSD_MAX_RETRIES + 1):
                try:
                    self._ensure_session()
                    result = self._execute_wsd_once(formula, calculated_timeout)
                    if result:
                        return result
                except (WindTimeoutError, WindSessionExpiredError) as exc:
                    last_error = exc
                except WindFormulaError:
                    raise
                if attempt < WSD_MAX_RETRIES:
                    delay = min(WSD_RETRY_BASE_DELAY * (2 ** (attempt - 1)), WSD_RETRY_MAX_DELAY)
                    logger.warning(
                        "Wind WSD retry", extra={"code": code, "attempt": attempt, "delay": delay}
                    )
                    time.sleep(delay)
        if last_error is not None:
            raise last_error
        return []

    WSD_MAX_ROWS = 1000
    WSD_MAX_COLS = 20

    def _execute_wsd_once(self, formula: str, timeout: float) -> list[list[Any]]:
        """Write one WSD formula, wait for it, and read its complete spill range."""
        start_row = self._allocate_helper_rows(self.WSD_MAX_ROWS)
        end_row = start_row + self.WSD_MAX_ROWS - 1
        start_col = self._col
        end_col = _offset_excel_column(start_col, self.WSD_MAX_COLS - 1)
        address = f"{start_col}{start_row}:{end_col}{end_row}"
        anchor = self._sheet.range(f"{start_col}{start_row}")
        try:
            self._sheet.range(address).value = None
            anchor.value = formula
            elapsed = 0.0
            interval = 0.5
            while elapsed < timeout:
                time.sleep(interval)
                elapsed += interval
                value = getattr(anchor, "raw_value", None)
                if value is None:
                    value = anchor.value
                if isinstance(value, str) and value.strip().upper() in EXCEL_ERRORS:
                    raise WindFormulaError(formula, value.strip())
                if value is not None and not _is_error_value(value):
                    return _trim_wsd_matrix(self._sheet.range(address).raw_value)
            raise WindTimeoutError(formula, timeout)
        finally:
            try:
                self._sheet.range(address).value = None
            except Exception as exc:  # noqa: BLE001
                logger.debug("Unable to clear Wind WSD helper range: %s", exc)

    def execute_batch(self, formulas: list[str], timeout: float | None = None) -> list[Any]:
        """批量执行 Wind 公式 —— 列式写入，一次 recalc

        关闭自动计算后批量写入公式，避免 Excel 逐单元格重算（每个公式可
        触发 5-10s 的 Wind 数据拉取）。写入完成后恢复自动计算并一次等待。

        执行前自动做 heartbeat 检测会话有效性。
        """
        with _EXCEL_OPERATION_LOCK:
            return self._execute_batch_unlocked(formulas, timeout=timeout)

    def _execute_batch_unlocked(
        self, formulas: list[str], timeout: float | None = None
    ) -> list[Any]:
        self._ensure_session()

        timeout = timeout or self._timeout
        sheet = self._sheet
        col = self._col
        app = self._app
        start_row = self._allocate_helper_rows(len(formulas))

        # 关闭自动计算，避免逐单元格触发 Wind 拉取
        original_calculation = None
        can_control_calculation = False
        try:
            original_calculation = app.api.Calculation
            app.api.Calculation = -4135  # xlCalculationManual
            can_control_calculation = True
        except Exception as e:  # noqa: BLE001
            logger.debug("Excel calculation mode control unavailable: %s", e)

        try:
            self._write_formula_column(sheet, col, formulas, start_row)
        finally:
            # 恢复自动计算，Excel 开始批量拉取 Wind 数据
            if can_control_calculation:
                app.api.Calculation = original_calculation

        try:
            # 等待 Excel 完成所有计算
            elapsed = 0.0
            interval = 0.5
            results: list[Any] = [None] * len(formulas)

            while elapsed < timeout:
                time.sleep(interval)
                elapsed += interval
                all_ready = True
                values = self._read_formula_column(sheet, col, len(formulas), start_row)
                for i, val in enumerate(values):
                    if results[i] is None:
                        if val is None or isinstance(val, str) and val.strip().lower() in WIND_LOADING:
                            all_ready = False
                        else:
                            # Accept both valid results AND Excel errors as "done"
                            # (an Excel error like #N/A is the final answer, not a loading state)
                            results[i] = val
                if all_ready:
                    break

            # 收集最终结果：None = timed out (unresolved), error string = Wind error, other = valid
            final_values = self._read_formula_column(sheet, col, len(formulas), start_row)
            final_results = []
            for i in range(len(formulas)):
                if results[i] is None:
                    val = final_values[i]
                    if val is None or _is_error_value(val):
                        final_results.append(
                            WindFormulaError(formulas[i], str(val) if val else "timeout")
                        )
                    else:
                        final_results.append(val)
                elif _is_error_value(results[i]):
                    final_results.append(WindFormulaError(formulas[i], str(results[i])))
                else:
                    final_results.append(results[i])

            return final_results
        finally:
            self._clear_formula_column(sheet, col, len(formulas), start_row)

    @staticmethod
    def _write_formula_column(
        sheet: Any,
        col: str,
        formulas: list[str],
        start_row: int = 1,
    ) -> None:
        if len(formulas) == 1:
            cell = sheet.range(f"{col}{start_row}")
            cell.value = None
            time.sleep(0.05)
            cell.value = formulas[0]
            return

        end_row = start_row + len(formulas) - 1
        address = f"{col}{start_row}:{col}{end_row}"
        try:
            sheet.range(address).value = [[None] for _ in formulas]
            time.sleep(0.05)
            sheet.range(address).value = [[formula] for formula in formulas]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Excel range batch write unavailable: %s", exc)
            for i, formula in enumerate(formulas):
                cell = sheet.range(f"{col}{start_row + i}")
                cell.value = None
                time.sleep(0.05)
                cell.value = formula

    @staticmethod
    def _read_formula_column(
        sheet: Any,
        col: str,
        count: int,
        start_row: int = 1,
    ) -> list[Any]:
        if count <= 0:
            return []
        if count == 1:
            return [sheet.range(f"{col}{start_row}").value]

        end_row = start_row + count - 1
        address = f"{col}{start_row}:{col}{end_row}"
        try:
            values = sheet.range(address).value
            normalized = WindExcelClient._normalize_column_values(values)
            if len(normalized) < count:
                normalized.extend([None] * (count - len(normalized)))
            return normalized[:count]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Excel range batch read unavailable: %s", exc)
            return [sheet.range(f"{col}{start_row + i}").value for i in range(count)]

    @staticmethod
    def _clear_formula_column(
        sheet: Any,
        col: str,
        count: int,
        start_row: int = 1,
    ) -> None:
        if count <= 0:
            return
        try:
            if count == 1:
                sheet.range(f"{col}{start_row}").value = None
                return
            end_row = start_row + count - 1
            sheet.range(f"{col}{start_row}:{col}{end_row}").value = [[None] for _ in range(count)]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Unable to clear Wind formula range: %s", exc)

    @staticmethod
    def _normalize_column_values(values: Any) -> list[Any]:
        if not isinstance(values, list):
            return [values]
        normalized: list[Any] = []
        for item in values:
            if isinstance(item, list):
                normalized.append(item[0] if item else None)
            else:
                normalized.append(item)
        return normalized

    def start_keepalive(
        self,
        interval_seconds: int = 1800,
        on_expired: Callable[[], None] | None = None,
    ):
        """启动后台保活线程，定期执行 heartbeat 防止 Wind 自动登出

        Args:
            interval_seconds: 心跳间隔，默认 1800 秒（30 分钟）
            on_expired: 会话过期时的回调函数
        """
        if self._keepalive_running:
            logger.warning("保活线程已在运行中")
            return

        self._ensure_connected()
        self._keepalive_interval = interval_seconds
        self._keepalive_running = True
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop,
            args=(on_expired,),
            daemon=True,
            name="wind-keepalive",
        )
        self._keepalive_thread.start()
        logger.info(f"Wind 保活线程已启动，间隔 {interval_seconds}s")

    def stop_keepalive(self):
        """停止保活线程"""
        self._keepalive_running = False
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            self._keepalive_thread.join(timeout=5.0)
        logger.info("Wind 保活线程已停止")

    def _keepalive_loop(self, on_expired: Callable[[], None] | None = None):
        """保活循环（在后台线程中运行）"""
        while self._keepalive_running:
            time.sleep(self._keepalive_interval)
            if not self._keepalive_running:
                break
            logger.debug("执行 Wind 保活心跳...")
            if self.heartbeat():
                logger.debug("Wind 保活心跳通过")
            else:
                logger.warning("Wind 会话已过期")
                self._keepalive_running = False
                if on_expired:
                    try:
                        on_expired()
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"过期回调执行失败: {e}")
                break

    def close(self):
        """断开连接。如果是连接的用户 Excel，不关闭；如果是自己启动的，关闭"""
        self.stop_keepalive()
        if self._owns_workbook and self._wb is not None:
            try:
                self._wb.close()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"关闭 Wind 工作簿时出错: {e}")
        if self._owns_app and self._app is not None:
            try:
                if not self._owns_workbook and self._wb is not None:
                    self._wb.close()
                self._app.quit()
                logger.info("Wind Excel 客户端已关闭")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"关闭 Excel 时出错: {e}")
        self._app = None
        self._wb = None
        self._sheet = None
        self._owns_app = False
        self._owns_workbook = False

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
