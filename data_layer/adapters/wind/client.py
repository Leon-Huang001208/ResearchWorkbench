"""Wind Excel 客户端 —— 通过 xlwings 操控 Excel Wind 插件"""

import math
import threading
import time
from datetime import datetime
from typing import Any, Callable

from core.observability import get_logger
from data_layer.adapters.wind.exceptions import (
    WindFormulaError,
    WindNotConnectedError,
    WindSessionExpiredError,
    WindTimeoutError,
)

logger = get_logger(__name__)

HEARTBEAT_FORMULA = '=@s_info_compname("600519.SH")'
HEARTBEAT_EXPECTED = "贵州茅台酒股份有限公司"
HEARTBEAT_RETRIES = 3
HEARTBEAT_RETRY_DELAY = 3.0

HELPER_SHEET_NAME = "_wind_helper_"

# WSD 重试配置
WSD_MAX_RETRIES = 3
WSD_RETRY_BASE_DELAY = 3.0
WSD_RETRY_MAX_DELAY = 30.0

# 超时计算: 基础超时 + 每 N 个交易日增加额外秒数
WSD_BASE_TIMEOUT = 15.0
WSD_EXTRA_TIMEOUT_PER_DAYS = 250
WSD_EXTRA_TIMEOUT_SECONDS = 5.0

# WSD 最大行数（A股 ~250 交易日/年，保守估计 5000 行覆盖 20 年）
WSD_MAX_ROWS = 1000  # ~4 年交易日，避免过大范围导致 AppleScript 错误

EXCEL_ERRORS = frozenset({"#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!"})
WIND_LOADING = frozenset({"fetch...", "loading...", "calculating...", "connecting..."})


def _is_error_value(value: Any) -> bool:
    """检查返回值是否是 Excel 错误"""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().upper() in EXCEL_ERRORS:
        return True
    return False


class WindExcelClient:
    """通过 xlwings 操控 Excel 中的 Wind 插件执行公式"""

    def __init__(self, visible: bool = False, timeout: float = 15.0, col: str = "Z"):
        self._visible = visible
        self._timeout = timeout
        self._col = col
        self._app = None
        self._wb = None
        self._sheet = None
        self._owns_app = False
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_running = False
        self._keepalive_interval = 1800  # 默认 30 分钟
        self._last_heartbeat: float = 0.0
        self._heartbeat_ttl: float = 30.0  # 30 秒内跳过重复心跳

    def _connect(self):
        """连接 Excel：在所有运行实例中查找含 Wind 插件的，找不到则启动新实例"""
        try:
            import xlwings as xw
        except ImportError:
            raise WindNotConnectedError()

        # Step 1: 遍历所有已运行的 Excel 实例，尝试找到含 Wind 插件的
        try:
            all_apps = list(xw.apps)
            if all_apps:
                for app in all_apps:
                    try:
                        if len(app.books) == 0:
                            continue
                        wb = app.books[0]
                        sheet = wb.sheets[0]
                        cell = sheet.range(f"{self._col}1")
                        cell.value = HEARTBEAT_FORMULA
                        # 等待 Wind 插件求值（最多 5s）
                        for _ in range(10):
                            time.sleep(0.5)
                            result = cell.value
                            if isinstance(result, str) and result.strip() == HEARTBEAT_EXPECTED:
                                self._app = app
                                self._wb = wb
                                self._sheet = sheet
                                self._owns_app = False
                                cell.value = None  # 清理
                                logger.info(
                                    "已连接到含 Wind 插件的 Excel (PID=%s, 工作表=%s)",
                                    self._app.pid,
                                    self._sheet.name,
                                )
                                return
                        cell.value = None  # 清理
                    except Exception:
                        continue

                # 没找到含 Wind 的实例，用第一个
                self._app = all_apps[0]
                logger.info("未找到含 Wind 插件的实例，连接到第一个 Excel (PID=%s)", self._app.pid)
                self._owns_app = False
            else:
                raise RuntimeError("no running Excel")
        except Exception:
            logger.info("未检测到运行中的 Excel，启动新实例")
            self._app = xw.App(visible=self._visible, add_book=True)
            self._owns_app = True

        # 确保有一个 workbook
        if len(self._app.books) == 0:
            self._wb = self._app.books.add()
        else:
            self._wb = self._app.books[0]

        # 使用第一个 sheet，用指定列避免覆盖用户数据
        self._sheet = self._wb.sheets[0]
        logger.info(f"使用工作表: {self._sheet.name}，列: {self._col}")

    def heartbeat(self) -> bool:
        """检测 Wind 会话是否有效（带重试，处理 Wind 加载中间态）"""
        for attempt in range(1, HEARTBEAT_RETRIES + 1):
            try:
                result = self._execute_raw(HEARTBEAT_FORMULA, timeout=10.0)
                if result is None:
                    logger.warning(f"Wind 心跳返回 None (第{attempt}次)")
                    time.sleep(HEARTBEAT_RETRY_DELAY)
                    continue
                if isinstance(result, str):
                    stripped = result.strip()
                    if stripped == HEARTBEAT_EXPECTED:
                        self._last_heartbeat = time.monotonic()
                        logger.debug("Wind 会话心跳检测通过")
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
                    logger.warning(f"Wind 心跳异常类型: {type(result).__name__}={result!r} (第{attempt}次)")
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

    def _ensure_session(self, force: bool = False):
        """确保 Wind 会话有效，否则抛出异常

        在 TTL 内复用上一次心跳结果，避免执行批量操作时重复探测。
        """
        self._ensure_connected()
        if not force and (time.monotonic() - self._last_heartbeat) < self._heartbeat_ttl:
            return
        if not self.heartbeat():
            raise WindSessionExpiredError()

    def _read_cell_value(self, cell):
        """读取单元格值，优先使用 raw_value 避免 datetime 串行号误转换。

        xlwings 会将 Excel 中的数字（如股价 1385.0）根据单元格格式转换为
        Python datetime，导致数据错乱。raw_value 返回原始数值。
        """
        try:
            raw = cell.raw_value
            if raw is not None:
                return raw
        except Exception:
            pass
        return cell.value

    def _execute_raw(self, formula: str, timeout: float | None = None) -> Any:
        """底层：写公式到 Excel 单元格，等待求值，读回结果"""
        self._ensure_connected()

        timeout = timeout or self._timeout
        cell = self._sheet.range(f"{self._col}1")
        cell.value = formula

        elapsed = 0.0
        interval = 0.3
        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            result = self._read_cell_value(cell)
            if not _is_error_value(result):
                return result
            if result is None:
                continue
            error_str = str(result).strip().upper()
            if error_str in EXCEL_ERRORS:
                return result

        raise WindTimeoutError(formula, timeout)

    def execute(self, formula: str, timeout: float | None = None) -> Any:
        """执行单条 Wind 公式并返回结果（自动检测会话）"""
        self._ensure_session()
        result = self._execute_raw(formula, timeout=timeout)
        if _is_error_value(result):
            raise WindFormulaError(formula, str(result) if result else "#N/A")
        return result

    def _wsd_timeout(self, start_date: str, end_date: str) -> float:
        """根据日期跨度动态计算 WSD 超时时间。

        基础超时 15s，每 250 个自然日增加 5s（约一年的交易日）。
        """
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            days = max(1, (ed - sd).days)
        except (ValueError, TypeError):
            days = 365
        extra = math.ceil(days / WSD_EXTRA_TIMEOUT_PER_DAYS) * WSD_EXTRA_TIMEOUT_SECONDS
        return WSD_BASE_TIMEOUT + extra

    def execute_wsd(
        self,
        code: str,
        fields: str,
        start_date: str,
        end_date: str,
        options: str = "",
        timeout: float | None = None,
    ) -> list[list]:
        """执行 Wind WSD 公式并返回完整时间序列表（带重试）。

        WSD 是 Wind 的多字段时间序列函数，一次公式返回所有字段的完整历史。
        结果以 Excel spill range 形式返回。

        Args:
            code: Wind 证券代码
            fields: 逗号分隔的字段名，如 "open,high,low,close,volume,amount"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 截止日期 "YYYY-MM-DD"
            options: 额外参数，如 "Days=Trading;PriceAdj=QFQ"
            timeout: 超时秒数，不指定则根据日期范围动态计算

        Returns:
            list[list]: 第一行为表头，后续行为数据行。每个内层列表对应一行。
        """
        calculated_timeout = timeout or self._wsd_timeout(start_date, end_date)

        formula = f'=wsd("{code}","{fields}","{start_date}","{end_date}","{options}")'
        logger.info(
            "WSD: code=%s, %s ~ %s, timeout=%.0fs",
            code,
            start_date,
            end_date,
            calculated_timeout,
        )

        last_error = None
        for attempt in range(1, WSD_MAX_RETRIES + 1):
            try:
                self._ensure_session()
                result = self._execute_wsd_once(formula, calculated_timeout)
                if result:
                    return result
                # 空结果也重试（可能是 Wind 还没算完）
                if attempt < WSD_MAX_RETRIES:
                    delay = min(
                        WSD_RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                        WSD_RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "WSD 返回空结果 code=%s (第%d次)，%.1fs 后重试",
                        code,
                        attempt,
                        delay,
                    )
                    time.sleep(delay)
            except (WindTimeoutError, WindSessionExpiredError) as e:
                last_error = e
                if attempt < WSD_MAX_RETRIES:
                    delay = min(
                        WSD_RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                        WSD_RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "WSD 失败 code=%s (第%d次): %s，%.1fs 后重试",
                        code,
                        attempt,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise
            except WindFormulaError:
                # 公式错误不重试
                raise

        if last_error:
            raise last_error
        return []

    # WSD 溢位矩阵配置
    WSD_MAX_COLS = 20  # 最多读取的列数（date + 多个字段）

    def _execute_wsd_once(self, formula: str, timeout: float) -> list[list]:
        """执行单次 WSD 调用（不含重试逻辑）。

        读取 WSD 溢位全矩阵（date + 所有请求字段），使用 raw_value
        避免 xlwings 将数字误转为 datetime。
        """
        sheet = self._sheet
        col = self._col

        # 清除可能残留的宽范围数据
        try:
            top = f"{col}1"
            # 计算最远端列名（col + WSD_MAX_COLS - 1）
            col_num = 0
            for ch in col:
                col_num = col_num * 26 + (ord(ch) - ord("A") + 1)
            end_col_num = col_num + self.WSD_MAX_COLS - 1
            import string as _string

            def _col_name(n: int) -> str:
                result = ""
                while n > 0:
                    n -= 1
                    result = _string.ascii_uppercase[n % 26] + result
                    n //= 26
                return result

            end_col = _col_name(end_col_num)
            clear_range = f"{top}:{end_col}{WSD_MAX_ROWS}"
            sheet.range(clear_range).value = None
        except Exception:
            pass

        # 写入 WSD 公式
        sheet.range(f"{col}1").value = formula

        # 等待 Excel 完成溢位计算
        elapsed = 0.0
        interval = 0.5
        resolved = False
        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            val = self._read_cell_value(sheet.range(f"{col}1"))
            if val is not None and not _is_error_value(val):
                resolved = True
                break
            # 检查是否是 Excel 错误
            if isinstance(val, str) and val.strip().upper() in EXCEL_ERRORS:
                error_val = str(val).strip()
                sheet.range(f"{col}1").value = None
                raise WindFormulaError(formula, error_val)

        if not resolved:
            sheet.range(f"{col}1").value = None
            raise WindTimeoutError(formula, timeout)

        # 动态检测实际数据矩阵尺寸
        try:
            # 从 col 开始，最多读 WSD_MAX_COLS 列、WSD_MAX_ROWS 行
            end_col = _col_name(end_col_num)
            wide_range = f"{col}1:{end_col}{WSD_MAX_ROWS}"
            raw_data = sheet.range(wide_range).raw_value

            if raw_data is None:
                return []

            if not isinstance(raw_data, list):
                # 单值结果
                sheet.range(f"{col}1").value = None
                return [[raw_data]]

            # 确定实际列数（从第一行非空单元格）
            header_row = raw_data[0]
            if isinstance(header_row, list):
                n_cols = 0
                for v in header_row:
                    if v is not None:
                        n_cols += 1
                    else:
                        break
            else:
                n_cols = 1

            if n_cols == 0:
                return []

            # 构建结果：截取实际列数，过滤全空行
            result = []
            saw_data = False
            for row in raw_data:
                if isinstance(row, list):
                    # 截取实际列数
                    trimmed = row[:n_cols]
                    if any(cell is not None for cell in trimmed):
                        result.append(trimmed)
                        saw_data = True
                    elif saw_data:
                        break  # 连续全空行 → WSD 溢位结束
                elif row is not None:
                    result.append([row])
                    saw_data = True
                elif saw_data:
                    break

            sheet.range(f"{col}1").value = None
            logger.debug("WSD: 读取 %d 行 × %d 列", len(result), n_cols)
            return result

        except Exception as exc:
            logger.warning("WSD 范围读取失败: %s", exc)
            try:
                sheet.range(f"{col}1").value = None
            except Exception:
                pass
            return []

    def execute_batch(self, formulas: list[str], timeout: float | None = None) -> list[Any]:
        """批量执行 Wind 公式 —— 列式写入，一次 recalc

        执行前自动做 heartbeat 检测会话有效性。
        """
        self._ensure_session()

        timeout = timeout or self._timeout
        sheet = self._sheet
        col = self._col

        t0 = time.monotonic()

        # 列式写入所有公式
        for i, formula in enumerate(formulas):
            row = i + 1
            sheet.range(f"{col}{row}").value = formula

        t_write = time.monotonic()

        # 等待 Excel 完成所有计算
        # 策略：
        # - None → 可能还在计算中（继续等待，最多 GRACE_TIMEOUT 善期）
        # - Excel 错误（#N/A 等）→ 善期内也继续等待（Wind 可能在计算中）
        # - GRACE_TIMEOUT 后仍为 None/错误 → 视为终态
        GRACE_TIMEOUT = 5.0  # None/Excel 错误的最长善期等待
        elapsed = 0.0
        interval = 0.3
        results: list[Any] = [None] * len(formulas)

        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            all_ready = True
            for i in range(len(formulas)):
                if results[i] is None or (elapsed < GRACE_TIMEOUT and _is_error_value(results[i])):
                    cell = sheet.range(f"{col}{i + 1}")
                    val = self._read_cell_value(cell)
                    if val is None:
                        if elapsed < GRACE_TIMEOUT:
                            all_ready = False
                        # else: 接受 None 为终态空值
                    elif _is_error_value(val):
                        if elapsed < GRACE_TIMEOUT:
                            all_ready = False  # 善期内继续等待
                        else:
                            results[i] = val  # 善期后接受错误
                    else:
                        results[i] = val  # 有效值
                elif results[i] is not None:
                    pass  # 已有终态结果
                else:
                    all_ready = False  # 仍是 None 且已过善期，但还没到总超时
            if all_ready:
                break

        t_wait = time.monotonic()
        if t_wait - t0 > 2.0:
            logger.debug(
                "execute_batch: %d formulas, write=%.2fs, wait=%.2fs",
                len(formulas),
                t_write - t0,
                t_wait - t_write,
            )

        # 收集最终结果
        final_results = []
        for i in range(len(formulas)):
            if results[i] is None or _is_error_value(results[i]):
                cell = sheet.range(f"{col}{i + 1}")
                val = self._read_cell_value(cell)
                if _is_error_value(val):
                    final_results.append(WindFormulaError(formulas[i], str(val) if val else "#N/A"))
                else:
                    final_results.append(val)
            else:
                final_results.append(results[i])

        return final_results

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
                    except Exception as e:
                        logger.error(f"过期回调执行失败: {e}")
                break

    def close(self):
        """断开连接。如果是连接的用户 Excel，不关闭；如果是自己启动的，关闭"""
        self.stop_keepalive()
        if self._owns_app and self._app is not None:
            try:
                self._wb.close()
                self._app.quit()
                logger.info("Wind Excel 客户端已关闭")
            except Exception as e:
                logger.warning(f"关闭 Excel 时出错: {e}")
        self._app = None
        self._wb = None
        self._sheet = None

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
