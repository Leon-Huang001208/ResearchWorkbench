"""Wind Excel 客户端 —— 通过 xlwings 操控 Excel Wind 插件"""

import threading
import time
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
HEARTBEAT_RETRIES = 2
HEARTBEAT_RETRY_DELAY = 2.0

HELPER_SHEET_NAME = "_wind_helper_"

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

    def __init__(self, visible: bool = False, timeout: float = 15.0):
        self._visible = visible
        self._timeout = timeout
        self._app = None
        self._wb = None
        self._sheet = None
        self._owns_app = False
        self._keepalive_thread: threading.Thread | None = None
        self._keepalive_running = False
        self._keepalive_interval = 1800  # 默认 30 分钟
        self._last_heartbeat_time: float = 0.0
        self._heartbeat_ttl: float = 30.0  # 30s 内复用 heartbeat 结果

    def _connect(self):
        """连接 Excel：优先连接已运行的实例，否则启动新实例"""
        try:
            import xlwings as xw
        except Exception:
            raise WindNotConnectedError(
                "xlwings not available (NumPy/matplotlib compatibility issue?)"
            )

        # 先尝试连接已运行的 Excel（遍历所有实例，不仅限 active）
        try:
            all_apps = list(xw.apps)
            if all_apps:
                self._app = all_apps[0]
                logger.info(f"已连接到运行中的 Excel 实例 (PID={self._app.pid})")
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

        # 使用第一个 sheet（与 AppleScript 测试一致），用 Z 列避免覆盖用户数据
        self._sheet = self._wb.sheets[0]
        logger.info(f"使用工作表: {self._sheet.name}")
        self._col = "Z"  # 使用远离用户数据的列

    def heartbeat(self) -> bool:
        """检测 Wind 会话是否有效（带重试，处理 Wind 加载中间态）"""
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
        cell = self._sheet.range(f"{self._col}1")
        cell.value = formula

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

        raise WindTimeoutError(formula, timeout)

    def execute(self, formula: str, timeout: float | None = None) -> Any:
        """执行单条 Wind 公式并返回结果（自动检测会话）"""
        self._ensure_session()
        result = self._execute_raw(formula, timeout=timeout)
        if _is_error_value(result):
            raise WindFormulaError(formula, str(result) if result else "#N/A")
        return result

    def execute_batch(self, formulas: list[str], timeout: float | None = None) -> list[Any]:
        """批量执行 Wind 公式 —— 列式写入，一次 recalc

        关闭自动计算后批量写入公式，避免 Excel 逐单元格重算（每个公式可
        触发 5-10s 的 Wind 数据拉取）。写入完成后恢复自动计算并一次等待。

        执行前自动做 heartbeat 检测会话有效性。
        """
        self._ensure_session()

        timeout = timeout or self._timeout
        sheet = self._sheet
        col = self._col
        app = self._app

        # 关闭自动计算，避免逐单元格触发 Wind 拉取
        original_calculation = app.api.Calculation
        app.api.Calculation = -4135  # xlCalculationManual

        try:
            # 列式写入所有公式
            for i, formula in enumerate(formulas):
                row = i + 1
                sheet.range(f"{col}{row}").value = formula
        finally:
            # 恢复自动计算，Excel 开始批量拉取 Wind 数据
            app.api.Calculation = original_calculation

        # 等待 Excel 完成所有计算
        elapsed = 0.0
        interval = 0.5
        results: list[Any] = [None] * len(formulas)

        while elapsed < timeout:
            time.sleep(interval)
            elapsed += interval
            all_ready = True
            for i in range(len(formulas)):
                if results[i] is None:
                    val = sheet.range(f"{col}{i + 1}").value
                    if val is None:
                        all_ready = False
                    else:
                        # Accept both valid results AND Excel errors as "done"
                        # (an Excel error like #N/A is the final answer, not a loading state)
                        results[i] = val
            if all_ready:
                break

        # 收集最终结果：None = timed out (unresolved), error string = Wind error, other = valid
        final_results = []
        for i in range(len(formulas)):
            if results[i] is None:
                val = sheet.range(f"{col}{i + 1}").value
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
