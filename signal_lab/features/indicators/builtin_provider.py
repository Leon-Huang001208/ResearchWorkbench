import logging
from typing import Optional

import numpy as np
import pandas as pd

from .models import TechnicalIndicators

logger = logging.getLogger(__name__)


class BuiltinProvider:
    """自写指标实现（兜底）"""

    def calculate(self, df: pd.DataFrame, symbol: str) -> TechnicalIndicators:
        """计算所有技术指标"""
        df = df.sort_index(ascending=True).copy()
        latest_date = (
            df.index[-1].strftime("%Y-%m-%d")
            if hasattr(df.index, "strftime")
            else str(df.index[-1])
        )
        result = TechnicalIndicators(symbol=symbol, date=latest_date)

        # 1. MA
        try:
            ma_values = {}
            for period in [5, 10, 20, 60]:
                if len(df) >= period:
                    ma = df["close"].rolling(window=period).mean()
                    ma_values[f"ma{period}"] = self._get_last_valid(ma)
            result.ma = ma_values if ma_values else None
        except Exception as e:
            logger.warning(f"计算 MA 失败: {e}")

        # 2. EMA
        try:
            ema_values = {}
            for period in [12, 26]:
                if len(df) >= period:
                    ema = df["close"].ewm(span=period, adjust=False).mean()
                    ema_values[f"ema{period}"] = self._get_last_valid(ema)
            result.ema = ema_values if ema_values else None
        except Exception as e:
            logger.warning(f"计算 EMA 失败: {e}")

        # 3. MACD
        try:
            if len(df) >= 26 + 9:
                ema12 = df["close"].ewm(span=12, adjust=False).mean()
                ema26 = df["close"].ewm(span=26, adjust=False).mean()
                dif = ema12 - ema26
                dea = dif.ewm(span=9, adjust=False).mean()
                macd_bar = (dif - dea) * 2
                result.macd = {
                    "dif": self._get_last_valid(dif),
                    "dea": self._get_last_valid(dea),
                    "macd_bar": self._get_last_valid(macd_bar),
                }
        except Exception as e:
            logger.warning(f"计算 MACD 失败: {e}")

        # 4. SAR (简化版)
        try:
            result.sar = self._calculate_sar(df)
        except Exception as e:
            logger.warning(f"计算 SAR 失败: {e}")

        # 5. DMI/ADX
        try:
            if len(df) >= 14 + 1:
                dmi = self._calculate_dmi(df, period=14)
                result.dmi = dmi
        except Exception as e:
            logger.warning(f"计算 DMI/ADX 失败: {e}")

        # 6. TRIX
        try:
            if len(df) >= 12 * 3:
                trix = self._calculate_trix(df["close"], period=12)
                result.trix = self._get_last_valid(trix)
        except Exception as e:
            logger.warning(f"计算 TRIX 失败: {e}")

        # 7. RSI
        try:
            rsi_values = {}
            for period in [6, 14]:
                if len(df) >= period + 1:
                    rsi = self._calculate_rsi(df["close"], period=period)
                    rsi_values[f"rsi{period}"] = self._get_last_valid(rsi)
            result.rsi = rsi_values if rsi_values else None
        except Exception as e:
            logger.warning(f"计算 RSI 失败: {e}")

        # 8. KDJ
        try:
            if len(df) >= 9 + 3:
                kdj = self._calculate_kdj(df)
                result.kdj = kdj
        except Exception as e:
            logger.warning(f"计算 KDJ 失败: {e}")

        # 9. WR
        try:
            if len(df) >= 14:
                wr = self._calculate_wr(df, period=14)
                result.wr = self._get_last_valid(wr)
        except Exception as e:
            logger.warning(f"计算 WR 失败: {e}")

        # 10. CCI
        try:
            if len(df) >= 14:
                cci = self._calculate_cci(df, period=14)
                result.cci = self._get_last_valid(cci)
        except Exception as e:
            logger.warning(f"计算 CCI 失败: {e}")

        # 11. ROC
        try:
            if len(df) >= 12 + 1:
                roc = self._calculate_roc(df["close"], period=12)
                result.roc = self._get_last_valid(roc)
        except Exception as e:
            logger.warning(f"计算 ROC 失败: {e}")

        # 12. BOLL
        try:
            if len(df) >= 20:
                boll = self._calculate_boll(df["close"], period=20, nbdev=2)
                result.boll = boll
        except Exception as e:
            logger.warning(f"计算 BOLL 失败: {e}")

        # 13. ATR
        try:
            if len(df) >= 14 + 1:
                atr = self._calculate_atr(df, period=14)
                result.atr = self._get_last_valid(atr)
        except Exception as e:
            logger.warning(f"计算 ATR 失败: {e}")

        # 14. OBV
        try:
            obv = self._calculate_obv(df)
            result.obv = self._get_last_valid(obv)
        except Exception as e:
            logger.warning(f"计算 OBV 失败: {e}")

        # 15. VWAP
        try:
            vwap = self._calculate_vwap(df)
            result.vwap = self._get_last_valid(vwap)
        except Exception as e:
            logger.warning(f"计算 VWAP 失败: {e}")

        return result

    def _get_last_valid(self, series: pd.Series) -> Optional[float]:
        """获取 Series 最后一个非 NaN 值"""
        valid = series.dropna()
        return float(valid.iloc[-1]) if len(valid) > 0 else None

    def _calculate_sar(self, df: pd.DataFrame) -> Optional[float]:
        """简化版 SAR 计算"""
        if len(df) < 2:
            return None
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        sar = np.zeros_like(close)
        rwb = 0.02
        max_af = 0.2
        ep = high[0] if close[1] > close[0] else low[0]
        uptrend = close[1] > close[0]
        sar[0] = low[0] if uptrend else high[0]

        for i in range(1, len(df)):
            if uptrend:
                sar[i] = sar[i - 1] + rwb * (ep - sar[i - 1])
                sar[i] = min(sar[i], low[i - 1], low[i] if i > 1 else low[i])
                if high[i] > ep:
                    ep = high[i]
                    rwb = min(rwb + 0.02, max_af)
                if low[i] < sar[i]:
                    uptrend = False
                    sar[i] = ep
                    ep = low[i]
                    rwb = 0.02
            else:
                sar[i] = sar[i - 1] + rwb * (ep - sar[i - 1])
                sar[i] = max(sar[i], high[i - 1], high[i] if i > 1 else high[i])
                if low[i] < ep:
                    ep = low[i]
                    rwb = min(rwb + 0.02, max_af)
                if high[i] > sar[i]:
                    uptrend = True
                    sar[i] = ep
                    ep = high[i]
                    rwb = 0.02

        return float(sar[-1]) if not np.isnan(sar[-1]) else None

    def _calculate_dmi(self, df: pd.DataFrame, period: int) -> Optional[dict]:
        """计算 DMI/ADX"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr = pd.DataFrame()
        tr["h-l"] = high - low
        tr["h-pc"] = abs(high - close.shift(1))
        tr["l-pc"] = abs(low - close.shift(1))
        tr["tr"] = tr.max(axis=1)
        atr = tr["tr"].rolling(window=period).mean()

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        plus_di = 100 * (plus_dm.rolling(window=period).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).sum() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return {
            "plus_di": self._get_last_valid(plus_di),
            "minus_di": self._get_last_valid(minus_di),
            "adx": self._get_last_valid(adx),
        }

    def _calculate_trix(self, close: pd.Series, period: int) -> pd.Series:
        """计算 TRIX"""
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        trix = (ema3 - ema3.shift(1)) / ema3.shift(1) * 100
        return trix

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """计算 RSI"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_kdj(self, df: pd.DataFrame) -> Optional[dict]:
        """计算 KDJ"""
        low_list = df["low"].rolling(window=9, min_periods=1).min()
        high_list = df["high"].rolling(window=9, min_periods=1).max()
        rsv = (df["close"] - low_list) / (high_list - low_list) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        return {
            "k": self._get_last_valid(k),
            "d": self._get_last_valid(d),
            "j": self._get_last_valid(j),
        }

    def _calculate_wr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算威廉指标"""
        high = df["high"].rolling(window=period).max()
        low = df["low"].rolling(window=period).min()
        wr = (high - df["close"]) / (high - low) * -100
        return wr

    def _calculate_cci(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 CCI"""
        tp = (df["high"] + df["low"] + df["close"]) / 3
        ma_tp = tp.rolling(window=period).mean()
        md = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        cci = (tp - ma_tp) / (0.015 * md)
        return cci

    def _calculate_roc(self, close: pd.Series, period: int) -> pd.Series:
        """计算 ROC"""
        roc = (close - close.shift(period)) / close.shift(period) * 100
        return roc

    def _calculate_boll(self, close: pd.Series, period: int, nbdev: float) -> Optional[dict]:
        """计算布林带"""
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = middle + nbdev * std
        lower = middle - nbdev * std
        return {
            "upper": self._get_last_valid(upper),
            "middle": self._get_last_valid(middle),
            "lower": self._get_last_valid(lower),
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 ATR"""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        """计算 OBV"""
        obv = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
        return obv  # type: ignore[no-any-return]

    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """计算 VWAP"""
        tp = (df["high"] + df["low"] + df["close"]) / 3
        vp = tp * df["volume"]
        cumulative_vp = vp.cumsum()
        cumulative_volume = df["volume"].cumsum()
        vwap = cumulative_vp / cumulative_volume
        return vwap
