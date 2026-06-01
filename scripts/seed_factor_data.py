#!/usr/bin/env python3
"""Seed factor data pipeline.

Phase 1: Ingest stock_master + stock_daily_bar from AKShare and/or Wind.
Phase 2: Register factor definitions, compute values, run evaluation.

Usage:
    # AKShare only (default, with rate limiting)
    python scripts/seed_factor_data.py --stock-count 200

    # Wind WSD (fast, requires Wind Excel plugin)
    python scripts/seed_factor_data.py --stock-count 200 --source wind

    # Auto (Wind first, fallback to AKShare)
    python scripts/seed_factor_data.py --stock-count 200 --source auto

    # Control rate limiting
    python scripts/seed_factor_data.py --stock-count 200 --delay 3.0 --max-retries 5

    # Resume interrupted run
    python scripts/seed_factor_data.py --stock-count 200 --source auto
    # (Ctrl+C to interrupt, then:)
    python scripts/seed_factor_data.py --stock-count 200 --source auto --resume .ai/checkpoints/seed_auto_200.json

    # Skip ingestion, just compute factors from existing DB data
    python scripts/seed_factor_data.py --skip-ingest

    # Specific symbols
    python scripts/seed_factor_data.py --symbols 600519.SH,000858.SZ --source wind
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from core.contracts.factors import FactorCategory, FactorDefinition, FactorValue
from core.observability import get_logger

logger = get_logger(__name__)

# ─── Rate limit / retry configuration ─────────────────────────

DEFAULT_DELAY = 2.0  # 请求间延迟（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_BASE_DELAY = 5.0  # 重试基础延迟（秒）
RETRY_MAX_DELAY = 60.0  # 重试最大延迟（秒）
CHECKPOINT_INTERVAL = 10  # 每 N 只股票保存一次断点
DEFAULT_CHECKPOINT_DIR = ".ai/checkpoints"


def _save_checkpoint(checkpoint_file: str, completed_symbols: list[str], total_saved: int) -> None:
    """保存断点 JSON 文件"""
    import json
    import os

    os.makedirs(os.path.dirname(checkpoint_file) or DEFAULT_CHECKPOINT_DIR, exist_ok=True)
    checkpoint = {
        "completed_symbols": completed_symbols,
        "total_saved": total_saved,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False)
    logger.debug("断点已保存: %s (%d 只已完成)", checkpoint_file, len(completed_symbols))


def _load_checkpoint(checkpoint_file: str) -> tuple[list[str], int]:
    """加载断点 JSON 文件，返回 (completed_symbols, total_saved)"""
    import json
    import os

    if not os.path.exists(checkpoint_file):
        logger.info("断点文件不存在: %s，从头开始", checkpoint_file)
        return [], 0

    with open(checkpoint_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    completed = data.get("completed_symbols", [])
    total_saved = data.get("total_saved", 0)
    logger.info(
        "从断点恢复: %s (%d 只已完成, %d 行已保存)",
        checkpoint_file,
        len(completed),
        total_saved,
    )
    return completed, total_saved


# ─── Phase 1: Ingest market data ────────────────────────────


def ingest_stock_master(limit: int | None = 500) -> list[str]:
    """Ingest A-share stock list via AKShare. Returns list of stock symbols."""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.etl_run_repository import ETLRunRepository
    from data_layer.repositories.market_data_repository import MarketDataRepository
    from services.market_data_ingestion_service import MarketDataIngestionService

    db = SessionLocal()
    try:
        market_repo = MarketDataRepository(db)
        etl_repo = ETLRunRepository(db)
        service = MarketDataIngestionService(
            market_repo=market_repo,
            etl_repo=etl_repo,
        )
        result = service.ingest_stock_master(limit=limit)
        logger.info("stock_master ingested: %s", result)

        # Return all ingested symbols
        symbols = market_repo.get_all_stock_symbols(limit=limit or 5000)
        logger.info("Available symbols: %d", len(symbols))
        return symbols
    finally:
        db.close()


def ingest_daily_bars(symbols: list[str], start_date: date, end_date: date) -> dict:
    """Ingest daily bars via AKShare for given symbols and date range."""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.etl_run_repository import ETLRunRepository
    from data_layer.repositories.market_data_repository import MarketDataRepository
    from services.market_data_ingestion_service import MarketDataIngestionService

    db = SessionLocal()
    try:
        market_repo = MarketDataRepository(db)
        etl_repo = ETLRunRepository(db)
        service = MarketDataIngestionService(
            market_repo=market_repo,
            etl_repo=etl_repo,
        )
        result = service.ingest_daily_bars(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info("daily bars ingested: %s", result)
        return result
    finally:
        db.close()


def filter_liquid_stocks(symbols: list[str], target: int = 200) -> list[str]:
    """Filter to the most liquid stocks (prioritize SH/SZ main board, large cap).
    Also prioritize Shanghai main board stocks (600xxx, 601xxx, 603xxx)."""
    # Simple heuristic: prioritize SH main board + top ZZX stocks
    sh_main = [s for s in symbols if s.startswith(("600", "601", "603"))]
    sz_main = [s for s in symbols if s.startswith("000")]
    sz_sme = [s for s in symbols if s.startswith("002")]
    sz_gem = [s for s in symbols if s.startswith("300")]
    others = [s for s in symbols if s not in sh_main + sz_main + sz_sme + sz_gem]

    # Combine in priority order, take top 'target'
    selected = (sh_main + sz_main + sz_sme + sz_gem + others)[:target]
    logger.info("Filtered %d stocks from %d total", len(selected), len(symbols))
    return selected


# ─── Factor definitions ──────────────────────────────────────


def create_factor_definitions() -> list[FactorDefinition]:
    """Create 10 canonical factor definitions (momentum, reversal, liquidity, risk)."""
    definitions: list[FactorDefinition] = [
        FactorDefinition(
            factor_id="mom_1m",
            name="1-Month Momentum",
            category=FactorCategory.MOMENTUM,
            direction="positive",
            description="Close / Close 20 trading days ago - 1",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="mom_3m",
            name="3-Month Momentum",
            category=FactorCategory.MOMENTUM,
            direction="positive",
            description="Close / Close 60 trading days ago - 1",
            horizon_days=60,
        ),
        FactorDefinition(
            factor_id="mom_6m",
            name="6-Month Momentum",
            category=FactorCategory.MOMENTUM,
            direction="positive",
            description="Close / Close 120 trading days ago - 1",
            horizon_days=120,
        ),
        FactorDefinition(
            factor_id="rev_5d",
            name="5-Day Reversal",
            category=FactorCategory.REVERSAL,
            direction="negative",
            description="Negative of 5-day return (short-term mean reversion)",
            horizon_days=5,
        ),
        FactorDefinition(
            factor_id="rev_20d",
            name="20-Day Reversal",
            category=FactorCategory.REVERSAL,
            direction="negative",
            description="Negative of 20-day return (medium-term mean reversion)",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="volatility_20d",
            name="20-Day Volatility",
            category=FactorCategory.RISK,
            direction="negative",
            description="Standard deviation of daily log returns over 20 days",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="volume_ratio_20d",
            name="Volume Ratio 20D",
            category=FactorCategory.LIQUIDITY,
            direction="positive",
            description="Current volume / average volume over past 20 days",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="turnover_20d_avg",
            name="Avg Turnover 20D",
            category=FactorCategory.LIQUIDITY,
            direction="positive",
            description="Average daily turnover ratio over past 20 days (normalized by float)",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="amt_ratio_20d",
            name="Amount Ratio 20D",
            category=FactorCategory.LIQUIDITY,
            direction="positive",
            description="Current amount / average amount over past 20 days",
            horizon_days=20,
        ),
        FactorDefinition(
            factor_id="price_position_60d",
            name="Price Position 60D",
            category=FactorCategory.MOMENTUM,
            direction="positive",
            description="(Close - 60d Low) / (60d High - 60d Low)",
            horizon_days=60,
        ),
    ]
    logger.info("Created %d factor definitions", len(definitions))
    return definitions


def create_financial_factor_definitions() -> list[FactorDefinition]:
    """Create VALUE, QUALITY, GROWTH factor definitions from financial data."""
    definitions: list[FactorDefinition] = [
        FactorDefinition(
            factor_id="pe_ttm",
            name="PE (TTM)",
            category=FactorCategory.VALUE,
            direction="negative",
            description="Price to Earnings ratio (TTM), lower = cheaper",
            horizon_days=90,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="pb",
            name="PB",
            category=FactorCategory.VALUE,
            direction="negative",
            description="Price to Book ratio, lower = cheaper",
            horizon_days=90,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="roe",
            name="ROE",
            category=FactorCategory.QUALITY,
            direction="positive",
            description="Return on Equity, higher = more profitable",
            horizon_days=90,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="eps",
            name="EPS",
            category=FactorCategory.QUALITY,
            direction="positive",
            description="Earnings Per Share (basic), higher = more profitable",
            horizon_days=90,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="revenue_growth_yoy",
            name="Revenue Growth YoY",
            category=FactorCategory.GROWTH,
            direction="positive",
            description="Year-over-year revenue growth rate",
            horizon_days=365,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="profit_growth_yoy",
            name="Net Profit Growth YoY",
            category=FactorCategory.GROWTH,
            direction="positive",
            description="Year-over-year net profit growth rate",
            horizon_days=365,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="debt_ratio",
            name="Debt-to-Asset Ratio",
            category=FactorCategory.RISK,
            direction="negative",
            description="Total liabilities / total assets, lower = safer",
            horizon_days=90,
            refresh_frequency="1q",
        ),
        FactorDefinition(
            factor_id="bvps",
            name="Book Value Per Share",
            category=FactorCategory.VALUE,
            direction="positive",
            description="Book value per share, higher = more asset backing",
            horizon_days=90,
            refresh_frequency="1q",
        ),
    ]
    logger.info("Created %d financial factor definitions", len(definitions))
    return definitions


# ─── Factor value computation ────────────────────────────────


def load_daily_bar_frame(symbols: list[str]) -> pd.DataFrame:
    """Load stock_daily_bar for given symbols into a flat DataFrame."""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.market_data_repository import MarketDataRepository

    db = SessionLocal()
    try:
        repo = MarketDataRepository(db)
        all_bars = []
        for symbol in symbols:
            bars = repo.get_daily_bars(symbol, limit=5000)
            for bar in bars:
                all_bars.append(
                    {
                        "symbol": bar.symbol,
                        "trade_date": bar.trade_date,
                        "open": float(bar.open) if bar.open else None,
                        "high": float(bar.high) if bar.high else None,
                        "low": float(bar.low) if bar.low else None,
                        "close": float(bar.close) if bar.close else None,
                        "volume": float(bar.volume) if bar.volume else None,
                        "amount": float(bar.amount) if bar.amount else None,
                        "turnover": float(bar.turnover) if bar.turnover else None,
                    }
                )
        df = pd.DataFrame(all_bars)
        if df.empty:
            logger.info("stock_daily_bar empty, falling back to legacy stock_price_data")
            return _load_legacy_price_frame(symbols)
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        logger.info("Loaded %d daily bar rows for %d symbols", len(df), len(symbols))
        return df
    finally:
        db.close()


def _load_legacy_price_frame(symbols: list[str]) -> pd.DataFrame:
    """Fallback: load from legacy stock_price_data table (uses 'code' not 'symbol')."""
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.models import StockPriceData

    db = SessionLocal()
    try:
        query = db.query(StockPriceData)
        if symbols:
            query = query.filter(StockPriceData.code.in_(symbols))
        rows = query.all()
        all_bars = []
        for row in rows:
            all_bars.append(
                {
                    "symbol": row.code,  # legacy uses 'code'
                    "trade_date": row.date,  # legacy uses 'date'
                    "open": float(row.open) if row.open else None,
                    "high": float(row.high) if row.high else None,
                    "low": float(row.low) if row.low else None,
                    "close": float(row.close) if row.close else None,
                    "volume": float(row.volume) if row.volume else None,
                    "amount": None,  # not available in legacy
                    "turnover": float(row.turnover) if row.turnover else None,
                }
            )
        df = pd.DataFrame(all_bars)
        if df.empty:
            logger.warning("No data in legacy stock_price_data either!")
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        logger.info(
            "Loaded %d rows from legacy stock_price_data (%d symbols)",
            len(df),
            df["symbol"].nunique(),
        )
        return df
    finally:
        db.close()


def compute_factor_values(
    df: pd.DataFrame,
    min_subjects_per_date: int = 30,
) -> list[FactorValue]:
    """Compute 10 factor values from daily bar data.

    For each trading date with ≥ min_subjects symbols:
        - Compute each of the 10 factors
        - Generate FactorValue contracts for each (factor_id, subject_id, as_of_date)
    """
    if df.empty:
        logger.warning("No daily bar data to compute factors from")
        return []

    df = df.sort_values(["symbol", "trade_date"]).copy()
    df["log_return"] = df.groupby("symbol")["close"].transform(lambda s: np.log(s / s.shift(1)))

    values: list[FactorValue] = []
    all_dates = sorted(df["trade_date"].unique())

    # Compute rolling windows per symbol
    grouped = df.groupby("symbol")

    for as_of_date in all_dates:
        # Filter data up to this date (point-in-time)
        date_mask = df["trade_date"] == as_of_date
        date_df = df[date_mask].copy()
        subjects_today = date_df["symbol"].unique()

        if len(subjects_today) < min_subjects_per_date:
            continue

        for symbol in subjects_today:
            sym_data = grouped.get_group(symbol)
            sym_data = sym_data[sym_data["trade_date"] <= as_of_date]

            if len(sym_data) == 0:
                continue

            # Current values
            close_now = sym_data["close"].iloc[-1]
            volume_now = sym_data["volume"].iloc[-1]
            amount_now = sym_data["amount"].iloc[-1]

            # Avoid NaN by checking
            if close_now is None or pd.isna(close_now):
                continue

            factor_vals: dict[str, float | None] = {}

            # Momentum factors
            for label, lookback in [("mom_1m", 20), ("mom_3m", 60), ("mom_6m", 120)]:
                if len(sym_data) >= lookback + 1:
                    close_lb = sym_data["close"].iloc[-(lookback + 1)]
                    if close_lb and not pd.isna(close_lb) and close_lb != 0:
                        factor_vals[label] = float(close_now / close_lb - 1.0)
                    else:
                        factor_vals[label] = None
                else:
                    factor_vals[label] = None

            # Reversal factors
            for label, lookback in [("rev_5d", 5), ("rev_20d", 20)]:
                if len(sym_data) >= lookback + 1:
                    close_lb = sym_data["close"].iloc[-(lookback + 1)]
                    if close_lb and not pd.isna(close_lb) and close_lb != 0:
                        factor_vals[label] = float(-(close_now / close_lb - 1.0))
                    else:
                        factor_vals[label] = None
                else:
                    factor_vals[label] = None

            # Volatility
            if len(sym_data) >= 21:
                log_rets = sym_data["log_return"].iloc[-20:]
                std = log_rets.std()
                factor_vals["volatility_20d"] = float(std) if not pd.isna(std) else None
            else:
                factor_vals["volatility_20d"] = None

            # Volume ratio 20d
            if len(sym_data) >= 21:
                avg_vol = sym_data["volume"].iloc[-21:-1].mean()
                if avg_vol and not pd.isna(avg_vol) and avg_vol > 0:
                    factor_vals["volume_ratio_20d"] = float(volume_now / avg_vol)
                else:
                    factor_vals["volume_ratio_20d"] = None
            else:
                factor_vals["volume_ratio_20d"] = None

            # Turnover 20d avg
            if len(sym_data) >= 20:
                avg_turn = sym_data["turnover"].iloc[-20:].mean()
                factor_vals["turnover_20d_avg"] = float(avg_turn) if not pd.isna(avg_turn) else None
            else:
                factor_vals["turnover_20d_avg"] = None

            # Amount ratio 20d (skip if amount unavailable, e.g. legacy data)
            if amount_now is not None and not pd.isna(amount_now) and len(sym_data) >= 21:
                avg_amt = sym_data["amount"].iloc[-21:-1].mean()
                if avg_amt and not pd.isna(avg_amt) and avg_amt > 0:
                    factor_vals["amt_ratio_20d"] = float(amount_now / avg_amt)
                else:
                    factor_vals["amt_ratio_20d"] = None
            else:
                factor_vals["amt_ratio_20d"] = None

            # Price position 60d
            if len(sym_data) >= 60:
                high_60 = sym_data["high"].iloc[-60:].max()
                low_60 = sym_data["low"].iloc[-60:].min()
                if (
                    high_60 is not None
                    and low_60 is not None
                    and not pd.isna(high_60)
                    and not pd.isna(low_60)
                    and high_60 != low_60
                ):
                    factor_vals["price_position_60d"] = float(
                        (close_now - low_60) / (high_60 - low_60)
                    )
                else:
                    factor_vals["price_position_60d"] = None
            else:
                factor_vals["price_position_60d"] = None

            # Emit FactorValue instances
            now_utc = datetime.now(timezone.utc)
            for factor_id, val in factor_vals.items():
                values.append(
                    FactorValue(
                        factor_id=factor_id,
                        subject_id=symbol,
                        as_of_date=as_of_date,
                        value=val,
                        available_at=now_utc,
                        source="akshare",
                    )
                )

    logger.info(
        "Computed %d factor values across %d dates",
        len(values),
        sum(1 for d in all_dates if (df["trade_date"] == d).sum() >= min_subjects_per_date),
    )
    return values


def _get_legacy_symbols() -> list[str]:
    """Get available symbols from legacy stock_price_data table."""
    from sqlalchemy import func

    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.models import StockPriceData

    db = SessionLocal()
    try:
        codes = [
            row[0]
            for row in db.query(func.distinct(StockPriceData.code))
            .order_by(StockPriceData.code)
            .all()
        ]
        logger.info("Found %d symbols in legacy stock_price_data", len(codes))
        return codes
    finally:
        db.close()


# ─── Phase 1B: Direct AKShare data path ─────────────────────


def get_stock_list_akshare_direct(target: int = 300) -> list[str]:
    """Get A-share stock list directly via AKShare stock_info_a_code_name().

    Returns symbols in format like '600519.SH'.
    """
    import akshare as ak

    logger.info("Fetching stock list via stock_info_a_code_name()...")
    df = ak.stock_info_a_code_name()
    logger.info("Got %d stocks from AKShare", len(df))

    # df columns: ['code', 'name']
    # code is like '600519', need to add suffix
    symbols = []
    for _, row in df.iterrows():
        code = str(row["code"]).zfill(6)
        if code.startswith(("6", "9")):
            symbols.append(f"{code}.SH")
        elif code.startswith(("0", "3")):
            symbols.append(f"{code}.SZ")
        elif code.startswith(("8", "4")):
            symbols.append(f"{code}.BJ")

    logger.info("Converted to %d symbols with suffix", len(symbols))
    return filter_liquid_stocks(symbols, target=target)


def _fetch_akshare_hist_with_retry(
    code: str,
    symbol: str,
    start_date: date,
    end_date: date,
    max_retries: int = MAX_RETRIES,
) -> "pd.DataFrame | None":
    """带指数退避重试的 AKShare stock_zh_a_hist 调用。

    Args:
        code: 纯数字代码，如 "600519"
        symbol: 带后缀的代码，如 "600519.SH"（仅用于日志）
        start_date: 起始日期
        end_date: 截止日期
        max_retries: 最大重试次数

    Returns:
        DataFrame 或 None（全部重试失败）
    """
    import akshare as ak

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    for attempt in range(1, max_retries + 1):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_str,
                end_date=end_str,
                adjust="qfq",
            )
            if attempt > 1:
                logger.info("  %s: 第 %d 次重试成功", symbol, attempt)
            return df
        except Exception as e:
            msg = str(e)[:100]
            # 检测限流信号
            is_rate_limit = any(
                kw in msg.lower()
                for kw in ("rate", "limit", "频率", "限流", "too many", "throttle", "429", "503")
            )
            if attempt < max_retries:
                retry_delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                if is_rate_limit:
                    # 限流时增加额外等待
                    retry_delay = max(retry_delay, 10.0 * attempt)
                logger.warning(
                    "  %s: AKShare 失败 (第%d/%d次, %s), %.1fs 后重试...",
                    symbol,
                    attempt,
                    max_retries,
                    "疑似限流" if is_rate_limit else str(e)[:60],
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                logger.error("  %s: AKShare 全部 %d 次重试失败: %s", symbol, max_retries, msg)

    return None


def _normalize_akshare_hist(df: "pd.DataFrame", symbol: str) -> list[dict]:
    """将 AKShare stock_zh_a_hist 返回的 DataFrame 转为 stock_daily_bar dict 列表。

    AKShare 列名: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
    """
    bars = []
    for _, row in df.iterrows():
        bars.append(
            {
                "symbol": symbol,
                "trade_date": pd.Timestamp(row["日期"]).date(),
                "open": float(row["开盘"]) if pd.notna(row["开盘"]) else None,
                "high": float(row["最高"]) if pd.notna(row["最高"]) else None,
                "low": float(row["最低"]) if pd.notna(row["最低"]) else None,
                "close": float(row["收盘"]) if pd.notna(row["收盘"]) else None,
                "volume": float(row["成交量"]) if pd.notna(row["成交量"]) else None,
                "amount": float(row["成交额"]) if pd.notna(row["成交额"]) else None,
                "turnover": float(row["换手率"]) if pd.notna(row["换手率"]) else None,
            }
        )
    return bars


def ingest_daily_bars_direct(
    symbols: list[str],
    start_date: date,
    end_date: date,
    delay: float = DEFAULT_DELAY,
    max_retries: int = MAX_RETRIES,
    checkpoint_file: str | None = None,
) -> int:
    """Ingest daily bars via AKShare stock_zh_a_hist() with retry, delay, checkpoint.

    Returns number of rows saved.
    """
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.market_data_repository import MarketDataRepository

    # 断点恢复
    completed_symbols: list[str] = []
    total_saved_checkpoint = 0
    if checkpoint_file:
        completed_symbols, total_saved_checkpoint = _load_checkpoint(checkpoint_file)

    remaining = [s for s in symbols if s not in completed_symbols]
    if completed_symbols:
        logger.info(
            "跳过 %d 只已完成股票，剩余 %d 只",
            len(completed_symbols),
            len(remaining),
        )

    db = SessionLocal()
    try:
        repo = MarketDataRepository(db)
        total_saved = total_saved_checkpoint
        failed_symbols: list[str] = []

        for i, symbol in enumerate(remaining):
            code = symbol.split(".")[0]

            # 请求间延迟（第一只不延迟）
            if i > 0 and delay > 0:
                time.sleep(delay)

            try:
                df = _fetch_akshare_hist_with_retry(
                    code=code,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    max_retries=max_retries,
                )
                if df is None or df.empty:
                    failed_symbols.append(symbol)
                    continue

                # Normalize to stock_daily_bar format
                bars = _normalize_akshare_hist(df, symbol)
                saved = repo.upsert_daily_bars(bars)
                total_saved += saved
                completed_symbols.append(symbol)

                global_idx = len(completed_symbols)
                if global_idx % 20 == 0:
                    logger.info(
                        "  AKShare daily bars: %d/%d symbols done (%d rows)",
                        global_idx,
                        len(symbols),
                        total_saved,
                    )

                # 断点保存
                if checkpoint_file and global_idx % CHECKPOINT_INTERVAL == 0:
                    _save_checkpoint(checkpoint_file, completed_symbols, total_saved)

            except Exception as e:
                logger.debug("  Daily bars failed for %s: %s", symbol, str(e)[:80])
                failed_symbols.append(symbol)
                continue

        # 最终断点保存
        if checkpoint_file:
            _save_checkpoint(checkpoint_file, completed_symbols, total_saved)

        if failed_symbols:
            logger.warning(
                "AKShare: %d symbols failed out of %d: %s",
                len(failed_symbols),
                len(remaining),
                ", ".join(failed_symbols[:10]) + ("..." if len(failed_symbols) > 10 else ""),
            )

        logger.info("AKShare daily bar ingestion: %d rows saved", total_saved)
        return total_saved
    finally:
        db.close()


# ─── Wind WSD data source ─────────────────────────────────────


def _wsd_to_daily_bars(raw_data: list[list], symbol: str) -> list[dict]:
    """将 Wind WSD 返回数据转为 stock_daily_bar dict 列表。

    WSD 返回格式（11 字段，前一行是表头）：
        DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, AMOUNT, TURN, ADJFACTOR2, VWAP, PCTCHANGE, SWING

    Args:
        raw_data: WSD 返回的原始数据（含表头行）
        symbol: 股票代码，如 "600519.SH"

    Returns:
        stock_daily_bar 格式的 dict 列表
    """
    if not raw_data or len(raw_data) < 2:
        return []

    # 跳过表头行
    bars = []
    for row in raw_data[1:]:
        if not row or not isinstance(row, list) or len(row) < 5:
            continue
        try:
            # row[0]=DATE, row[1]=OPEN, row[2]=HIGH, row[3]=LOW, row[4]=CLOSE,
            # row[5]=VOLUME, row[6]=AMOUNT, row[7]=TURN
            date_str = str(row[0])[:10] if row[0] else None
            if date_str is None:
                continue

            trade_date = pd.Timestamp(date_str).date()

            bars.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "open": _safe_float_wind(row[1]) if len(row) > 1 else None,
                    "high": _safe_float_wind(row[2]) if len(row) > 2 else None,
                    "low": _safe_float_wind(row[3]) if len(row) > 3 else None,
                    "close": _safe_float_wind(row[4]) if len(row) > 4 else None,
                    "volume": _safe_float_wind(row[5]) if len(row) > 5 else None,
                    "amount": _safe_float_wind(row[6]) if len(row) > 6 else None,
                    "turnover": _safe_float_wind(row[7]) if len(row) > 7 else None,
                }
            )
        except (ValueError, TypeError, IndexError):
            continue

    return bars


def _safe_float_wind(value) -> float | None:
    """Wind 公式返回值转 float"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _is_wind_available() -> bool:
    """检查 Wind 终端是否可用。"""
    try:
        from data_layer.adapters.wind.client import WindExcelClient

        client = WindExcelClient()
        client._connect()
        available = client.heartbeat()
        client.close()
        return available
    except Exception as e:
        logger.info("Wind 不可用: %s", str(e)[:80])
        return False


def ingest_daily_bars_from_wind(
    symbols: list[str],
    start_date: date,
    end_date: date,
    delay: float = DEFAULT_DELAY,
    checkpoint_file: str | None = None,
) -> int:
    """使用 Wind WSD 获取日行情数据并存入 stock_daily_bar 表。

    Wind WSD 一次调用返回单只股票的完整时间序列，
    比 AKShare 效率更高，且不受东方财富限流影响。

    Args:
        symbols: 股票代码列表
        start_date: 起始日期
        end_date: 截止日期
        delay: 请求间延迟（秒），给 Excel/Wind 喘息时间
        checkpoint_file: 断点文件路径

    Returns:
        保存的行数
    """
    from data_layer.adapters.wind.client import WindExcelClient
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.market_data_repository import MarketDataRepository

    # 断点恢复
    completed_symbols: list[str] = []
    total_saved_checkpoint = 0
    if checkpoint_file:
        completed_symbols, total_saved_checkpoint = _load_checkpoint(checkpoint_file)

    remaining = [s for s in symbols if s not in completed_symbols]
    if completed_symbols:
        logger.info(
            "跳过 %d 只已完成股票 (Wind)，剩余 %d 只",
            len(completed_symbols),
            len(remaining),
        )

    sd_str = start_date.strftime("%Y-%m-%d")
    ed_str = end_date.strftime("%Y-%m-%d")

    # WSD 字段: 不复权 OHLC + volume/amount/turn (前复权用 adjfactor2 在后续处理)
    ws_fields = "open,high,low,close,volume,amount,turn"
    ws_options = "Days=Trading"

    db = SessionLocal()
    client = WindExcelClient()
    try:
        client._connect()
        if not client.heartbeat():
            logger.error("Wind 终端连接失败，无法获取日行情")
            return total_saved_checkpoint

        repo = MarketDataRepository(db)
        total_saved = total_saved_checkpoint
        failed_symbols: list[str] = []

        for i, symbol in enumerate(remaining):
            # 请求间延迟
            if i > 0 and delay > 0:
                time.sleep(delay)

            try:
                raw = client.execute_wsd(
                    code=symbol,
                    fields=ws_fields,
                    start_date=sd_str,
                    end_date=ed_str,
                    options=ws_options,
                )

                if not raw:
                    logger.debug("  Wind WSD 返回空: %s", symbol)
                    failed_symbols.append(symbol)
                    continue

                bars = _wsd_to_daily_bars(raw, symbol)
                if not bars:
                    logger.debug("  Wind WSD 解析后为空: %s", symbol)
                    failed_symbols.append(symbol)
                    continue

                saved = repo.upsert_daily_bars(bars)
                total_saved += saved
                completed_symbols.append(symbol)

                global_idx = len(completed_symbols)
                if global_idx % 20 == 0:
                    logger.info(
                        "  Wind daily bars: %d/%d symbols done (%d rows)",
                        global_idx,
                        len(symbols),
                        total_saved,
                    )

                # 断点保存
                if checkpoint_file and global_idx % CHECKPOINT_INTERVAL == 0:
                    _save_checkpoint(checkpoint_file, completed_symbols, total_saved)

            except Exception as e:
                logger.debug("  Wind WSD failed for %s: %s", symbol, str(e)[:80])
                failed_symbols.append(symbol)
                continue

        # 最终断点保存
        if checkpoint_file:
            _save_checkpoint(checkpoint_file, completed_symbols, total_saved)

        if failed_symbols:
            logger.warning(
                "Wind: %d symbols failed out of %d: %s",
                len(failed_symbols),
                len(remaining),
                ", ".join(failed_symbols[:10]) + ("..." if len(failed_symbols) > 10 else ""),
            )

        logger.info("Wind daily bar ingestion: %d rows saved", total_saved)
        return total_saved

    finally:
        client.close()
        db.close()


def ingest_financials_direct(symbols: list[str]) -> int:
    """Ingest financial data via AKShare stock_financial_abstract() to stock_financial_metric.

    Uses existing model columns (roe, debt_ratio, net_profit, total_revenue) and
    stores extra fields (pe_ttm, pb, eps, bvps) in raw_payload JSON.

    Returns number of rows saved.
    """
    import akshare as ak
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.models import StockFinancialMetricDB

    db = SessionLocal()
    try:
        total_saved = 0

        for i, symbol in enumerate(symbols):
            code = symbol.split(".")[0]
            try:
                df = ak.stock_financial_abstract(symbol=code)
                if df.empty:
                    continue

                # Indicators from financial_abstract
                indicator_map = {
                    "基本每股收益": "eps",
                    "净利润": "net_profit",
                    "营业总收入": "total_revenue",
                    "净资产收益率(ROE)": "roe",
                    "每股净资产": "bvps",
                    "资产负债率": "debt_ratio",
                }
                pe_row = df[df["指标"].str.contains("市盈率", na=False)]
                pb_row = df[df["指标"].str.contains("市净率", na=False)]

                date_cols = [c for c in df.columns if c not in ["选项", "指标"]]
                for date_col in date_cols:
                    try:
                        report_date = pd.Timestamp(date_col).date()
                    except Exception:
                        continue

                    metrics: dict[str, float | None] = {}
                    extra: dict[str, float | None] = {
                        "pe_ttm": None,
                        "pb": None,
                        "eps": None,
                        "bvps": None,
                    }

                    for indicator, field in indicator_map.items():
                        row = df[df["指标"] == indicator]
                        if not row.empty:
                            val = row[date_col].iloc[0]
                            if pd.notna(val) and val != "--":
                                try:
                                    fval = float(val)
                                    if field in ("pe_ttm", "pb", "eps", "bvps"):
                                        extra[field] = fval
                                    else:
                                        metrics[field] = fval
                                except (ValueError, TypeError):
                                    pass

                    # PE from dedicated row
                    if not pe_row.empty:
                        v = pe_row[date_col].iloc[0]
                        if pd.notna(v) and v != "--":
                            try:
                                extra["pe_ttm"] = float(v)
                            except (ValueError, TypeError):
                                pass

                    # PB from dedicated row
                    if not pb_row.empty:
                        v = pb_row[date_col].iloc[0]
                        if pd.notna(v) and v != "--":
                            try:
                                extra["pb"] = float(v)
                            except (ValueError, TypeError):
                                pass

                    # Only save if at least one field has data
                    has_data = (
                        any(v is not None for v in metrics.values())
                        or extra["pe_ttm"] is not None
                        or extra["pb"] is not None
                        or extra["eps"] is not None
                        or extra["bvps"] is not None
                    )
                    if not has_data:
                        continue

                    record = {
                        "symbol": symbol,
                        "report_date": report_date,
                        "roe": metrics.get("roe"),
                        "debt_ratio": metrics.get("debt_ratio"),
                        "net_profit": metrics.get("net_profit"),
                        "total_revenue": metrics.get("total_revenue"),
                        "source": "akshare",
                        "raw_payload": {k: v for k, v in extra.items() if v is not None},
                    }

                    # Filter out None for non-JSON columns
                    clean_record = {
                        k: v for k, v in record.items() if v is not None or k == "raw_payload"
                    }

                    stmt = pg_insert(StockFinancialMetricDB).values(**clean_record)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["symbol", "report_date"],
                        set_={
                            "roe": stmt.excluded.roe,
                            "debt_ratio": stmt.excluded.debt_ratio,
                            "net_profit": stmt.excluded.net_profit,
                            "total_revenue": stmt.excluded.total_revenue,
                            "raw_payload": stmt.excluded.raw_payload,
                        },
                    )
                    db.execute(stmt)
                    total_saved += 1

                db.commit()

                if (i + 1) % 20 == 0:
                    logger.info("  Financials: %d/%d symbols done", i + 1, len(symbols))

            except Exception as e:
                db.rollback()
                logger.debug("  Financials failed for %s: %s", symbol, str(e)[:80])
                continue

        logger.info("Direct financial ingestion: %d rows saved", total_saved)
        return total_saved
    finally:
        db.close()


# ─── Phase 2: Register & compute ─────────────────────────────


def seed_factor_pipeline(
    symbols: list[str],
    skip_ingest: bool = False,
    stock_count: int = 200,
    akshare_direct: bool = True,
    include_financials: bool = True,
    source: str = "akshare",
    delay: float = DEFAULT_DELAY,
    max_retries: int = MAX_RETRIES,
    checkpoint_file: str | None = None,
    date_start: str = "2024-01-01",
    date_end: str = "2026-05-31",
) -> dict:
    """Run the full seed pipeline.

    Args:
        symbols: Specific symbols to use (overrides discovery)
        skip_ingest: Skip Phase 1 entirely
        stock_count: Number of stocks to seed
        akshare_direct: Use direct AKShare calls instead of ingestion service
        include_financials: Also seed financial data and VALUE/QUALITY/GROWTH factors
        source: Data source for daily bars: "akshare", "wind", or "auto"
        delay: Inter-request delay in seconds
        max_retries: Max retries per API call
        checkpoint_file: Path to checkpoint JSON for resume support
        date_start: Start date for daily bar ingestion (YYYY-MM-DD)
        date_end: End date for daily bar ingestion (YYYY-MM-DD)
    """
    summary: dict = {"phase1": {}, "phase2": {}, "phase3": {}}

    # ── Phase 1: Ingest market data ──
    if not skip_ingest:
        logger.info("=== Phase 1: Ingesting market data (source=%s) ===", source)
        start_date_obj = date.fromisoformat(date_start)
        end_date_obj = date.fromisoformat(date_end)

        # Determine effective source
        effective_source = source
        if source == "auto":
            if _is_wind_available():
                effective_source = "wind"
                logger.info("Auto: Wind 可用，优先使用 Wind")
            else:
                effective_source = "akshare"
                logger.info("Auto: Wind 不可用，降级到 AKShare")

        # 1A: Discover symbols (always via AKShare for stock list)
        if akshare_direct:
            try:
                symbols = get_stock_list_akshare_direct(target=stock_count)
                logger.info("Using %d stocks for factor seeding", len(symbols))
            except Exception as e:
                logger.warning("AKShare stock list failed: %s. Using legacy symbols.", e)
                symbols = _get_legacy_symbols()
                logger.info("Using %d symbols from legacy stock_price_data", len(symbols))
        else:
            try:
                all_symbols = ingest_stock_master(limit=max(stock_count * 2, 500))
                symbols = filter_liquid_stocks(all_symbols, target=stock_count)
                logger.info("Using %d stocks for factor seeding", len(symbols))
            except Exception as e:
                logger.warning("AKShare ingestion failed: %s. Falling back to legacy data.", e)
                symbols = _get_legacy_symbols()
                logger.info("Using %d symbols from legacy stock_price_data", len(symbols))

        # 1B: Daily bars via selected source
        if effective_source == "wind":
            daily_saved = ingest_daily_bars_from_wind(
                symbols,
                start_date_obj,
                end_date_obj,
                delay=delay,
                checkpoint_file=checkpoint_file,
            )
            summary["phase1"] = {
                "method": "wind_wsd",
                "stock_count": len(symbols),
                "daily_bars_saved": daily_saved,
            }
            if daily_saved == 0 and source == "auto":
                # Wind 连接成功但数据为空，降级到 AKShare
                logger.warning("Wind 返回空数据，降级到 AKShare")
                daily_saved = ingest_daily_bars_direct(
                    symbols,
                    start_date_obj,
                    end_date_obj,
                    delay=delay,
                    max_retries=max_retries,
                    checkpoint_file=checkpoint_file,
                )
                summary["phase1"] = {
                    "method": "akshare_fallback_after_wind_empty",
                    "stock_count": len(symbols),
                    "daily_bars_saved": daily_saved,
                }
        else:
            daily_saved = ingest_daily_bars_direct(
                symbols,
                start_date_obj,
                end_date_obj,
                delay=delay,
                max_retries=max_retries,
                checkpoint_file=checkpoint_file,
            )
            summary["phase1"] = {
                "method": "akshare_direct",
                "stock_count": len(symbols),
                "daily_bars_saved": daily_saved,
            }

        if daily_saved == 0:
            logger.warning("Phase 1: No daily bars saved! Falling back to legacy data.")
            summary["phase1"]["fallback"] = "legacy_stock_price_data"
            symbols = _get_legacy_symbols()
            logger.info("Using %d symbols from legacy stock_price_data", len(symbols))
    else:
        logger.info("=== Phase 1: SKIPPED (--skip-ingest) ===")
        if not symbols:
            symbols = _get_legacy_symbols()
            logger.info("Auto-loaded %d symbols from legacy stock_price_data", len(symbols))
        summary["phase1"] = {"skipped": True, "fallback_symbols": len(symbols)}

    # ── Phase 2: Technical factor data (momentum/reversal/liquidity/risk) ──
    logger.info("=== Phase 2: Seeding technical factor data ===")
    from services.factor_store_service import FactorStore

    store = FactorStore()

    try:
        # 2A: Register technical factor definitions
        definitions = create_factor_definitions()
        registered = store.register_definitions(definitions)
        summary["phase2"]["tech_definitions_registered"] = registered

        # 2B: Compute technical factor values
        logger.info("Loading daily bar data from DB for factor computation...")
        df = load_daily_bar_frame(symbols)
        summary["phase2"]["daily_bar_rows"] = len(df)
        summary["phase2"]["unique_dates"] = len(df["trade_date"].unique()) if not df.empty else 0
        summary["phase2"]["unique_symbols"] = df["symbol"].nunique() if not df.empty else 0

        if df.empty:
            logger.error("No daily bar data found! Cannot compute factor values.")
            summary["phase2"]["status"] = "failed_no_data"
            return summary

        factor_values = compute_factor_values(df, min_subjects_per_date=30)
        if factor_values:
            saved = store.store_values(factor_values)
            summary["phase2"]["values_computed"] = len(factor_values)
            summary["phase2"]["values_saved"] = saved
            logger.info("Saved %d technical factor values", saved)
        else:
            logger.warning("No technical factor values computed (insufficient data per date)")
            summary["phase2"]["values_computed"] = 0

        # 2C: Run evaluation cycle on latest date
        latest_date = df["trade_date"].max()
        if isinstance(latest_date, pd.Timestamp):
            latest_date = latest_date.date()

        logger.info("Running evaluation cycle for %s", latest_date)
        from services.factor_computation_service import FactorComputationService

        comp_service = FactorComputationService()
        forward_returns = _build_forward_returns(df, horizon_days=20)
        result = comp_service.run_daily_cycle(
            as_of_date=latest_date,
            forward_returns=forward_returns,
        )
        comp_service.close()

        summary["phase2"]["evaluation"] = {
            "as_of_date": str(latest_date),
            "status": result.get("status"),
            "definitions_loaded": result["steps"].get("definitions_loaded", 0),
            "values_loaded": result["steps"].get("values_loaded", 0),
            "evaluations_stored": result["steps"].get("evaluations_stored", 0),
            "weights_stored": result["steps"].get("weights_stored", 0),
            "active_factors": result["steps"].get("active_factors", 0),
            "duration_seconds": result.get("duration_seconds", 0),
        }
        summary["phase2"]["status"] = "completed"
        logger.info("Evaluation cycle complete: %s", summary["phase2"]["evaluation"])

    finally:
        store.close()

    # ── Phase 3: Financial factors (VALUE/QUALITY/GROWTH) ──
    if include_financials:
        logger.info("=== Phase 3: Seeding financial factor data ===")
        store2 = FactorStore()
        try:
            # 3A: Ingest financial data via AKShare (independent of daily bar ingestion)
            if akshare_direct:
                logger.info("Ingesting financial data via AKShare direct...")
                fin_saved = ingest_financials_direct(symbols)
                summary["phase3"]["financial_rows_saved"] = fin_saved
            else:
                summary["phase3"]["financial_ingestion"] = "skipped (--no-akshare-direct)"

            # 3B: Register financial factor definitions
            fin_defs = create_financial_factor_definitions()
            fin_registered = store2.register_definitions(fin_defs)
            summary["phase3"]["financial_definitions_registered"] = fin_registered

            # 3C: Compute financial factor values
            logger.info("Loading financial data from DB...")
            fin_df = load_financial_frame(symbols)
            summary["phase3"]["financial_rows"] = len(fin_df)

            if not fin_df.empty:
                fin_values = compute_financial_factor_values(fin_df)
                if fin_values:
                    fin_saved = store2.store_values(fin_values)
                    summary["phase3"]["values_computed"] = len(fin_values)
                    summary["phase3"]["values_saved"] = fin_saved
                    logger.info("Saved %d financial factor values", fin_saved)

                    # 3D: Run evaluation for financial factors on latest date
                    fin_latest = fin_df["trade_date"].max()
                    if isinstance(fin_latest, pd.Timestamp):
                        fin_latest = fin_latest.date()

                    logger.info("Running financial evaluation cycle for %s", fin_latest)
                    comp_service2 = FactorComputationService()
                    fin_result = comp_service2.run_daily_cycle(
                        as_of_date=fin_latest,
                        factor_ids=[d.factor_id for d in fin_defs],
                    )
                    comp_service2.close()

                    summary["phase3"]["evaluation"] = {
                        "as_of_date": str(fin_latest),
                        "status": fin_result.get("status"),
                        "definitions_loaded": fin_result["steps"].get("definitions_loaded", 0),
                        "values_loaded": fin_result["steps"].get("values_loaded", 0),
                        "evaluations_stored": fin_result["steps"].get("evaluations_stored", 0),
                    }
                else:
                    logger.warning("No financial factor values computed")
                    summary["phase3"]["values_computed"] = 0
            else:
                logger.warning("No financial data found in DB")
                summary["phase3"]["status"] = "no_financial_data"

            summary["phase3"]["status"] = "completed"
            logger.info("Financial factor seeding complete: %s", summary["phase3"])

        finally:
            store2.close()

    return summary


def _build_forward_returns(df: pd.DataFrame, horizon_days: int = 20) -> pd.Series:
    """Build forward returns series for evaluation.

    Forward return = (close[t+horizon] - close[t]) / close[t]
    Index = MultiIndex of (subject_id, as_of_date)
    """
    df = df.sort_values(["symbol", "trade_date"]).copy()
    grouped = df.groupby("symbol")

    records: list[dict] = []
    for symbol, group in grouped:
        group = group.reset_index(drop=True)
        for i in range(len(group) - horizon_days):
            close_now = group.loc[i, "close"]
            close_fwd = group.loc[i + horizon_days, "close"]
            if close_now and close_fwd and close_now != 0:
                ret = (close_fwd - close_now) / close_now
                records.append(
                    {
                        "subject_id": symbol,
                        "as_of_date": group.loc[i, "trade_date"],
                        "forward_return": float(ret),
                    }
                )

    if not records:
        return pd.Series(dtype=float)

    fr_df = pd.DataFrame(records)
    fr_series = fr_df.set_index(["subject_id", "as_of_date"])["forward_return"]
    # Align to FactorEvaluator's expected format
    result = fr_series.groupby("subject_id").last()
    logger.info("Built forward returns: %d records", len(result))
    return result


# ─── Financial factor computation ──────────────────────────


def load_financial_frame(symbols: list[str]) -> pd.DataFrame:
    """Load stock_financial_metric into a flat DataFrame.

    Extracts values from both typed columns and raw_payload JSON.
    """
    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.models import StockFinancialMetricDB

    db = SessionLocal()
    try:
        query = db.query(StockFinancialMetricDB)
        if symbols:
            query = query.filter(StockFinancialMetricDB.symbol.in_(symbols))
        rows = query.all()
        records = []
        for row in rows:
            # Extract from raw_payload (pe_ttm, pb, eps, bvps)
            rp = row.raw_payload or {}
            records.append(
                {
                    "symbol": row.symbol,
                    "trade_date": row.report_date,  # model uses report_date
                    "pe_ttm": float(rp.get("pe_ttm")) if rp.get("pe_ttm") is not None else None,
                    "pb": float(rp.get("pb")) if rp.get("pb") is not None else None,
                    "eps": float(rp.get("eps")) if rp.get("eps") is not None else None,
                    "bvps": float(rp.get("bvps")) if rp.get("bvps") is not None else None,
                    "roe": float(row.roe) if row.roe else None,
                    "revenue": float(row.total_revenue) if row.total_revenue else None,
                    "net_profit": float(row.net_profit) if row.net_profit else None,
                    "debt_ratio": float(row.debt_ratio) if row.debt_ratio else None,
                }
            )
        df = pd.DataFrame(records)
        if df.empty:
            return df
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        logger.info(
            "Loaded %d financial rows (%d symbols)",
            len(df),
            df["symbol"].nunique(),
        )
        return df
    finally:
        db.close()


def compute_financial_factor_values(df: pd.DataFrame) -> list[FactorValue]:
    """Compute VALUE/QUALITY/GROWTH factor values from financial data.

    Financial data is reported quarterly. We use the latest available
    report date as the as_of_date (point-in-time for factor).
    """
    if df.empty:
        logger.warning("No financial data to compute factors from")
        return []

    df = df.sort_values(["symbol", "trade_date"]).copy()
    values: list[FactorValue] = []
    now_utc = datetime.now(timezone.utc)

    # Direct mappings: pe_ttm → negative, pb → negative, roe → positive, etc.
    direct_mappings = {
        "pe_ttm": "pe_ttm",
        "pb": "pb",
        "roe": "roe",
        "eps": "eps",
        "debt_ratio": "debt_ratio",
        "bvps": "bvps",
    }

    # Group by symbol for growth calculations
    grouped = df.groupby("symbol")

    for symbol, group in grouped:
        group = group.sort_values("trade_date")

        for _, row in group.iterrows():
            as_of_date = row["trade_date"]

            # Direct factor mappings
            for factor_id, col in direct_mappings.items():
                val = row.get(col)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    values.append(
                        FactorValue(
                            factor_id=factor_id,
                            subject_id=symbol,
                            as_of_date=as_of_date,
                            value=float(val),
                            available_at=now_utc,
                            source="akshare_financial",
                        )
                    )

            # YoY growth: compare with same quarter 1 year ago
            current_revenue = row.get("revenue")
            current_profit = row.get("net_profit")

            if current_revenue is not None and not (
                isinstance(current_revenue, float) and pd.isna(current_revenue)
            ):
                prev_year = group[
                    group["trade_date"] == as_of_date.replace(year=as_of_date.year - 1)
                ]
                if not prev_year.empty:
                    prev_rev = prev_year["revenue"].iloc[0]
                    if (
                        prev_rev is not None
                        and not (isinstance(prev_rev, float) and pd.isna(prev_rev))
                        and prev_rev != 0
                    ):
                        growth = float(current_revenue / prev_rev - 1.0)
                        values.append(
                            FactorValue(
                                factor_id="revenue_growth_yoy",
                                subject_id=symbol,
                                as_of_date=as_of_date,
                                value=growth,
                                available_at=now_utc,
                                source="akshare_financial",
                            )
                        )

            if current_profit is not None and not (
                isinstance(current_profit, float) and pd.isna(current_profit)
            ):
                prev_year = group[
                    group["trade_date"] == as_of_date.replace(year=as_of_date.year - 1)
                ]
                if not prev_year.empty:
                    prev_profit = prev_year["net_profit"].iloc[0]
                    if (
                        prev_profit is not None
                        and not (isinstance(prev_profit, float) and pd.isna(prev_profit))
                        and prev_profit != 0
                    ):
                        growth = float(current_profit / prev_profit - 1.0)
                        values.append(
                            FactorValue(
                                factor_id="profit_growth_yoy",
                                subject_id=symbol,
                                as_of_date=as_of_date,
                                value=growth,
                                available_at=now_utc,
                                source="akshare_financial",
                            )
                        )

    logger.info("Computed %d financial factor values", len(values))
    return values


# ─── CLI ─────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Seed factor data pipeline")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip market data ingestion (data already in DB)",
    )
    parser.add_argument(
        "--stock-count",
        type=int,
        default=200,
        help="Number of stocks to seed (default: 200)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated specific symbols to use",
    )
    parser.add_argument(
        "--no-akshare-direct",
        action="store_true",
        help="Use ingestion service instead of direct AKShare calls",
    )
    parser.add_argument(
        "--skip-financials",
        action="store_true",
        help="Skip Phase 3 (financial data and VALUE/QUALITY/GROWTH factors)",
    )
    parser.add_argument(
        "--date-start",
        type=str,
        default="2024-01-01",
        help="Start date for daily bar ingestion (default: 2024-01-01)",
    )
    parser.add_argument(
        "--date-end",
        type=str,
        default="2026-05-31",
        help="End date for daily bar ingestion (default: 2026-05-31)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="akshare",
        choices=["akshare", "wind", "auto"],
        help="Data source for daily bars: akshare (default), wind (Excel Wind plugin), "
        "auto (Wind first, fallback to AKShare)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay between API requests in seconds (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Max retries per AKShare API call (default: {MAX_RETRIES})",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Path to checkpoint JSON file for resuming interrupted ingestion",
    )
    args = parser.parse_args()

    symbols: list[str] = []
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",")]
        args.skip_ingest = True  # assume data already loaded for specific symbols

    # Checkpoint file: use --resume if given, otherwise auto-generate
    checkpoint_file = args.resume
    if not checkpoint_file and args.source in ("wind", "auto") and not args.skip_ingest:
        # Auto-generate checkpoint for Wind/auto to enable resume on interrupt
        checkpoint_file = f"{DEFAULT_CHECKPOINT_DIR}/seed_{args.source}_{args.stock_count}.json"

    summary = seed_factor_pipeline(
        symbols=symbols,
        skip_ingest=args.skip_ingest,
        stock_count=args.stock_count,
        akshare_direct=not args.no_akshare_direct,
        include_financials=not args.skip_financials,
        source=args.source,
        delay=args.delay,
        max_retries=args.max_retries,
        checkpoint_file=checkpoint_file,
        date_start=args.date_start,
        date_end=args.date_end,
    )

    print("\n=== Seed Factor Data Summary ===")
    print(f"Phase 1 (Market Data): {summary['phase1']}")
    print(f"Phase 2 (Technical Factors): {summary['phase2']}")
    if "phase3" in summary:
        print(f"Phase 3 (Financial Factors): {summary['phase3']}")

    all_ok = True
    for phase_key in ["phase2", "phase3"]:
        if phase_key in summary:
            status = summary[phase_key].get("status", "unknown")
            if status != "completed" and status != "no_financial_data":
                all_ok = False

    if all_ok:
        print("\n✅ Factor pipeline seeded successfully!")
    else:
        print("\n⚠️  Check phase statuses above")
        sys.exit(1)


if __name__ == "__main__":
    main()
