import logging
from typing import Optional

import numpy as np
import pandas as pd
import talib

from .models import TechnicalIndicators

logger = logging.getLogger(__name__)


class TALibProvider:
    """TA-Lib 指标实现（第一优先级）"""

    def calculate(self, df: pd.DataFrame, symbol: str) -> TechnicalIndicators:
        """计算所有技术指标"""
        # 确保数据按时间排序（假设 index 是日期）
        df = df.sort_index(ascending=True)

        # 提取所需数据（使用 np.asarray 确保 numpy 类型兼容性）
        high_data: np.ndarray = np.asarray(df["high"].values, dtype=np.float64)
        low_data: np.ndarray = np.asarray(df["low"].values, dtype=np.float64)
        close_data: np.ndarray = np.asarray(df["close"].values, dtype=np.float64)
        volume_data: np.ndarray = np.asarray(df["volume"].values, dtype=np.float64)

        # 获取最新日期
        latest_date = (
            df.index[-1].strftime("%Y-%m-%d")
            if hasattr(df.index, "strftime")
            else str(df.index[-1])
        )

        result = TechnicalIndicators(symbol=symbol, date=latest_date)

        # 1. MA - 简单移动均线
        try:
            ma_values = {}
            for period in [5, 10, 20, 60]:
                if len(close_data) >= period:
                    ma = talib.SMA(close_data, timeperiod=period)
                    ma_values[f"ma{period}"] = self._get_last_valid(ma)
            result.ma = ma_values if ma_values else None
        except Exception as e:
            logger.warning(f"计算 MA 失败: {e}")

        # 2. EMA - 指数移动均线
        try:
            ema_values = {}
            for period in [12, 26]:
                if len(close_data) >= period:
                    ema = talib.EMA(close_data, timeperiod=period)
                    ema_values[f"ema{period}"] = self._get_last_valid(ema)
            result.ema = ema_values if ema_values else None
        except Exception as e:
            logger.warning(f"计算 EMA 失败: {e}")

        # 3. MACD
        try:
            if len(close_data) >= 26 + 9:
                macd, macd_signal, macd_hist = talib.MACD(
                    close_data, fastperiod=12, slowperiod=26, signalperiod=9
                )
                result.macd = {
                    "dif": self._get_last_valid(macd),
                    "dea": self._get_last_valid(macd_signal),
                    "macd_bar": self._get_last_valid(macd_hist),
                }
        except Exception as e:
            logger.warning(f"计算 MACD 失败: {e}")

        # 4. SAR
        try:
            if len(high_data) >= 2:
                sar = talib.SAR(high_data, low_data)
                result.sar = self._get_last_valid(sar)
        except Exception as e:
            logger.warning(f"计算 SAR 失败: {e}")

        # 5. DMI/ADX
        try:
            if len(high_data) >= 14 + 1:
                plus_di = talib.PLUS_DI(high_data, low_data, close_data, timeperiod=14)
                minus_di = talib.MINUS_DI(high_data, low_data, close_data, timeperiod=14)
                adx = talib.ADX(high_data, low_data, close_data, timeperiod=14)
                result.dmi = {
                    "plus_di": self._get_last_valid(plus_di),
                    "minus_di": self._get_last_valid(minus_di),
                    "adx": self._get_last_valid(adx),
                }
        except Exception as e:
            logger.warning(f"计算 DMI/ADX 失败: {e}")

        # 6. TRIX
        try:
            if len(close_data) >= 12 * 3:
                trix = talib.TRIX(close_data, timeperiod=12)
                result.trix = self._get_last_valid(trix)
        except Exception as e:
            logger.warning(f"计算 TRIX 失败: {e}")

        # 7. RSI
        try:
            rsi_values = {}
            for period in [6, 14]:
                if len(close_data) >= period + 1:
                    rsi = talib.RSI(close_data, timeperiod=period)
                    rsi_values[f"rsi{period}"] = self._get_last_valid(rsi)
            result.rsi = rsi_values if rsi_values else None
        except Exception as e:
            logger.warning(f"计算 RSI 失败: {e}")

        # 8. KDJ
        try:
            if len(high_data) >= 9 + 3:
                slowk, slowd = talib.STOCH(
                    high_data,
                    low_data,
                    close_data,
                    fastk_period=9,
                    slowk_period=3,
                    slowk_matype=0,  # type: ignore[arg-type]
                    slowd_period=3,
                    slowd_matype=0,  # type: ignore[arg-type]
                )
                k = self._get_last_valid(slowk)
                d = self._get_last_valid(slowd)
                j = 3 * k - 2 * d if k is not None and d is not None else None
                result.kdj = {"k": k, "d": d, "j": j}
        except Exception as e:
            logger.warning(f"计算 KDJ 失败: {e}")

        # 9. WR - 威廉指标
        try:
            if len(high_data) >= 14:
                wr = talib.WILLR(high_data, low_data, close_data, timeperiod=14)
                result.wr = self._get_last_valid(wr)
        except Exception as e:
            logger.warning(f"计算 WR 失败: {e}")

        # 10. CCI
        try:
            if len(high_data) >= 14:
                cci = talib.CCI(high_data, low_data, close_data, timeperiod=14)
                result.cci = self._get_last_valid(cci)
        except Exception as e:
            logger.warning(f"计算 CCI 失败: {e}")

        # 11. ROC
        try:
            if len(close_data) >= 12 + 1:
                roc = talib.ROC(close_data, timeperiod=12)
                result.roc = self._get_last_valid(roc)
        except Exception as e:
            logger.warning(f"计算 ROC 失败: {e}")

        # 12. BOLL - 布林带
        try:
            if len(close_data) >= 20:
                upper, middle, lower = talib.BBANDS(
                    close_data, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0  # type: ignore[arg-type]
                )
                result.boll = {
                    "upper": self._get_last_valid(upper),
                    "middle": self._get_last_valid(middle),
                    "lower": self._get_last_valid(lower),
                }
        except Exception as e:
            logger.warning(f"计算 BOLL 失败: {e}")

        # 13. ATR
        try:
            if len(high_data) >= 14 + 1:
                atr = talib.ATR(high_data, low_data, close_data, timeperiod=14)
                result.atr = self._get_last_valid(atr)
        except Exception as e:
            logger.warning(f"计算 ATR 失败: {e}")

        # 14. OBV
        try:
            if len(close_data) >= 1:
                obv = talib.OBV(close_data, volume_data)
                result.obv = self._get_last_valid(obv)
        except Exception as e:
            logger.warning(f"计算 OBV 失败: {e}")

        # 15. VWAP - 成交量加权均价（TA-Lib 没有，自己算）
        try:
            typical_price = (high_data + low_data + close_data) / 3
            vp = typical_price * volume_data
            cumulative_vp = np.cumsum(vp)
            cumulative_volume = np.cumsum(volume_data)
            vwap = cumulative_vp / cumulative_volume
            result.vwap = self._get_last_valid(vwap)
        except Exception as e:
            logger.warning(f"计算 VWAP 失败: {e}")

        return result

    def _get_last_valid(self, arr: np.ndarray) -> Optional[float]:
        """获取数组最后一个非 NaN 值"""
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if len(valid) > 0 else None
