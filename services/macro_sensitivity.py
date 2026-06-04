"""Macro sensitivity analysis via time-series regression.

Computes a stock's sensitivity to macro factors by running OLS regression
of stock daily returns against proxy ETF returns.
"""

from typing import Optional

import numpy as np
import pandas as pd

from core.contracts import MacroSensitivity
from core.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Macro proxy instrument mapping
# ---------------------------------------------------------------------------

MACRO_PROXY_ETFS: dict[str, str] = {
    "interest_rate": "511010.SH",  # 国债ETF (10年)
    "inflation": "510880.SH",  # 红利ETF (dividend stocks as inflation hedge proxy)
    "exchange_rate": "510050.SH",  # 上证50ETF (correlated with USD/CNY)
    "commodity": "159980.SZ",  # 有色ETF
    "liquidity": "510300.SH",  # 沪深300ETF (market liquidity proxy)
}

# Map internal factor names to MacroSensitivity field names
_FACTOR_TO_FIELD: dict[str, str] = {
    "interest_rate": "interest_rate_sensitivity",
    "inflation": "inflation_sensitivity",
    "exchange_rate": "exchange_rate_sensitivity",
    "commodity": "commodity_sensitivity",
    "liquidity": "liquidity_sensitivity",
}


class MacroSensitivityCalculator:
    """计算个股对宏观因子的敏感度（时间序列回归Beta）。

    通过 OLS 回归：stock_return ~ beta0 + sum(beta_i * proxy_return_i)
    获取各宏观因子的敏感度系数及模型的拟合优度 R²。
    """

    def __init__(self) -> None:
        self._proxies = MACRO_PROXY_ETFS

    def compute(
        self,
        canonical_id: str,
        start_date: str,
        end_date: str,
        min_observations: int = 60,
    ) -> MacroSensitivity:
        """计算指定标的对宏观因子的敏感度。

        Args:
            canonical_id: 资产代码（Wind 格式，如 "600519.SH"）。
            start_date: 起始日期 "YYYYMMDD"。
            end_date: 截止日期 "YYYYMMDD"。
            min_observations: 最少有效观测数，低于此值返回空结果。

        Returns:
            MacroSensitivity: 宏观敏感性数据。不可用时各字段为 None。
        """
        try:
            from data_layer.adapters.cjpy_adapter import CjpyAdapter

            adapter = CjpyAdapter()
            if not adapter.is_available():
                logger.info(
                    "Cjpy unavailable for macro sensitivity, returning empty",
                    extra={"canonical_id": canonical_id},
                )
                return MacroSensitivity()

            # 批量获取行情（一次调用包含标的 + 所有代理 ETF）
            codes = [canonical_id] + list(self._proxies.values())
            df = adapter.fetch_daily_quotes(
                codes=codes,
                start_date=start_date,
                end_date=end_date,
                rate="不复权",
            )

            if df.empty:
                logger.info(
                    "Empty quote data for macro sensitivity",
                    extra={"canonical_id": canonical_id, "codes": codes},
                )
                return MacroSensitivity()

        except Exception as e:
            logger.warning(
                "Macro sensitivity data fetch failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

        try:
            return self._run_regression(df, canonical_id, min_observations)
        except Exception as e:
            logger.warning(
                "Macro sensitivity regression failed: %s",
                e,
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

    def _run_regression(
        self,
        df: pd.DataFrame,
        canonical_id: str,
        min_observations: int,
    ) -> MacroSensitivity:
        """对清洗后的行情 DataFrame 执行 OLS 回归，返回敏感度结果。"""
        df = df.copy()

        # ---- 统一日期列名 ----
        if "时间" in df.columns:
            date_col = "时间"
        elif "date" in df.columns:
            date_col = "date"
        else:
            logger.warning("No date column found in quote data")
            return MacroSensitivity()

        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=["_date"])

        # ---- 确保 close 列可计算 ----
        if "close" not in df.columns:
            logger.warning("No close column found in quote data")
            return MacroSensitivity()

        df["close"] = pd.to_numeric(df["close"], errors="coerce")

        # ---- 计算日收益率 ----
        df = df.sort_values(["code", "_date"])
        df["_return"] = df.groupby("code")["close"].pct_change()
        df = df.dropna(subset=["_return"])
        df = df[df["_return"].notna()]

        if df.empty:
            return MacroSensitivity()

        # ---- 透视：行=日期，列=代码，值=收益率 ----
        pivot = df.pivot_table(
            index="_date",
            columns="code",
            values="_return",
            aggfunc="first",
        )

        # ---- 列名映射：代码 -> 因子名 ----
        reverse_map: dict[str, str] = {v: k for k, v in self._proxies.items()}
        reverse_map[canonical_id] = "stock"
        # 保留存在的列
        rename_map = {col: reverse_map[col] for col in pivot.columns if col in reverse_map}
        pivot = pivot.rename(columns=rename_map)

        if "stock" not in pivot.columns:
            logger.warning(
                "Stock not found in quote data after pivot",
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

        # ---- 确定可用的宏观因子 ----
        available_factors = [k for k in self._proxies if k in pivot.columns]
        if not available_factors:
            logger.info(
                "No macro proxy data available",
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

        # ---- 构建回归矩阵 ----
        y = pivot["stock"].values.astype(float)
        X = pivot[available_factors].values.astype(float)

        # 对齐：去除任一侧有 NaN 的行
        mask = ~(np.isnan(y) | np.isnan(X).any(axis=1))
        y_clean = y[mask]
        X_clean = X[mask]

        if len(y_clean) < min_observations:
            logger.info(
                "Insufficient observations for macro sensitivity: %d < %d",
                len(y_clean),
                min_observations,
                extra={"canonical_id": canonical_id},
            )
            return MacroSensitivity()

        # ---- OLS 回归 (numpy.linalg.lstsq) ----
        X_with_const = np.column_stack([np.ones(len(X_clean)), X_clean])
        beta, residuals, rank, s = np.linalg.lstsq(X_with_const, y_clean, rcond=None)

        # ---- R² ----
        y_mean = np.mean(y_clean)
        ss_total = np.sum((y_clean - y_mean) ** 2)
        y_pred = np.dot(X_with_const, beta)
        ss_residual = np.sum((y_clean - y_pred) ** 2)
        r_squared = float(1.0 - ss_residual / ss_total) if ss_total > 0 else 0.0

        # ---- 提取 Beta ----
        sensitivities: dict[str, float] = {}
        for i, factor in enumerate(available_factors):
            beta_val = float(beta[i + 1])  # beta[0] = intercept
            sensitivities[factor] = beta_val

        # ---- 显著因子筛选 ----
        key_macro_factors = sorted([f for f, b in sensitivities.items() if abs(b) > 0.1])

        # ---- 填充 MacroSensitivity ----
        result_fields: dict[str, Optional[float]] = {}
        for factor_name, field_name in _FACTOR_TO_FIELD.items():
            result_fields[field_name] = sensitivities.get(factor_name)

        logger.info(
            "Macro sensitivity computed",
            extra={
                "canonical_id": canonical_id,
                "observations": len(y_clean),
                "r_squared": round(r_squared, 4),
                "sensitivities": sensitivities,
                "key_factors": key_macro_factors,
            },
        )

        return MacroSensitivity(
            interest_rate_sensitivity=result_fields.get("interest_rate_sensitivity"),
            inflation_sensitivity=result_fields.get("inflation_sensitivity"),
            exchange_rate_sensitivity=result_fields.get("exchange_rate_sensitivity"),
            commodity_sensitivity=result_fields.get("commodity_sensitivity"),
            liquidity_sensitivity=result_fields.get("liquidity_sensitivity"),
            key_macro_factors=key_macro_factors,
        )
