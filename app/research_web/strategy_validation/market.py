"""Load verified BaoStock data and construct point-in-time event features."""

import hashlib
import json
import re
from collections import Counter
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

PRICE = ["open", "high", "low", "close", "preclose"]
SOURCE_FILES = {
    "hs300-membership.csv",
    "zz500-membership.csv",
    "calendar.csv",
    "universe.csv",
    "stock-basic.csv",
    "bars-receipts.json",
}
TICKER = re.compile(r"(sh|sz)\.[0-9]{6}")


def add_moving_average_features(features, traded_close, base_valid, windows):
    """A running n-day SMA includes the signal day's close in its last slot."""
    for n in windows:
        moving_average = traded_close.rolling(n, min_periods=n).mean()
        previous_window = moving_average.shift(1)
        features[f"ma{n}_valid"] = base_valid & moving_average.notna() & previous_window.notna()
        features[f"ma{n}_prior_gap"] = traded_close.shift(1) / previous_window - 1
        features[f"ma{n}_close_gap"] = traded_close / moving_average - 1


def round_a_share_limit(preclose):
    # Regular main-board days only. Convert to fen with half-up rounding.
    return np.floor(preclose * 90 + 0.5 + 1e-9) / 100


def complete_future_rows(present, horizon):
    reverse_window = present.iloc[::-1].rolling(horizon + 1, min_periods=horizon + 1).sum()
    return reverse_window.iloc[::-1].eq(horizon + 1)


def stock_features(
    path, dates, ticker, stratum, spec, catalog, moving_averages, horizon, sell_cost_bps
):
    raw = pd.read_csv(path, dtype={"code": str, "date": str})
    if raw.empty or raw["date"].duplicated().any():
        raise ValueError(f"Empty or duplicate observations for {ticker}")
    if not raw["code"].eq(ticker).all() or not raw["adjustflag"].eq(3).all():
        raise ValueError(f"Wrong security or adjustment for {ticker}")
    if not raw["date"].isin(dates).all() or not raw["date"].is_monotonic_increasing:
        raise ValueError(f"Unexpected trading date for {ticker}")
    frame = raw.set_index("date").reindex(dates)
    present = frame["code"].notna()
    quotes = frame[PRICE].apply(pd.to_numeric, errors="raise")
    valid_price = np.isfinite(quotes).all(axis=1) & quotes.gt(0).all(axis=1)
    valid_price &= quotes["high"].ge(quotes[["open", "close", "low"]].max(axis=1) - 1e-8)
    valid_price &= quotes["low"].le(quotes[["open", "close", "high"]].min(axis=1) + 1e-8)
    traded = present & frame["tradestatus"].eq(1) & frame["volume"].gt(0) & valid_price
    suspended = present & frame["tradestatus"].eq(0)
    daily_return = quotes["close"] / quotes["preclose"] - 1
    source_ok = (daily_return - frame["pctChg"] / 100).abs().le(0.0003)
    usable = traded & source_ok

    # Published ex-right reference preclose removes price discontinuity using only
    # information from t. Missing observations never create usable return windows.
    daily_factor = (1 + daily_return).where(usable).mask(suspended, 1.0)
    chain = daily_factor.cumprod()
    scale = chain / quotes["close"]
    adjusted_open, adjusted_high = quotes["open"] * scale, quotes["high"] * scale
    previous_raw_close = quotes["close"].shift(1)
    normal_reference = (quotes["preclose"] - previous_raw_close).abs().le(0.005)
    volume_window_clean = normal_reference.rolling(6, min_periods=6).sum().eq(6)

    ordinary = frame["isST"].eq(0)
    available_amount = frame["amount"].where(usable & frame["amount"].gt(0))
    amount_mean = available_amount.shift(1).rolling(5, min_periods=5).mean()
    prior_volume = frame["volume"].where(usable).shift(1).rolling(5, min_periods=5).mean()
    common = usable & ordinary & volume_window_clean & prior_volume.gt(0)
    common &= amount_mean.ge(spec["min_lagged_average_amount_cny"])
    lag_momentum = chain.shift(1) / chain.shift(21) - 1
    common &= np.isfinite(lag_momentum)
    momentum_window = (usable | suspended).shift(1, fill_value=False)
    common &= momentum_window.rolling(21, min_periods=21).sum().eq(21)

    index = pd.Index(dates, name="date")
    features = pd.DataFrame(index=index)
    features["ticker"], features["stratum"], features["exchange"] = (
        ticker,
        stratum,
        ticker[:2],
    )
    features["base_valid"] = common
    features["day_return"] = daily_return
    features["ratio"] = frame["volume"] / prior_volume
    features["lagged_20day_return"] = lag_momentum
    features["log_lagged_5day_amount"] = np.log(amount_mean)
    for window in sorted(
        {
            spec["main"]["lookback"],
            *(s["lookback"] for s in spec["sensitivity"] if "lookback" in s),
        }
    ):
        prior_high = adjusted_high.where(usable).shift(1).rolling(window, min_periods=window).max()
        features[f"dist{window}"] = 1 - chain / prior_high

    add_moving_average_features(
        features,
        chain.where(usable),
        common,
        moving_averages,
    )

    next_open = adjusted_open.where(usable).shift(-1)
    limit = round_a_share_limit(quotes["preclose"])
    open_status = usable & ordinary & quotes["open"].gt(limit + 1e-7)
    close_status = usable & ordinary & quotes["close"].gt(limit + 1e-7)
    features["next_open_fill_assumed"] = open_status.shift(-1, fill_value=False)

    sell_cost = sell_cost_bps / 10_000
    complete = complete_future_rows(present & (usable | suspended), horizon)
    end = chain.where(usable).shift(-horizon)
    features[f"hold{horizon}"] = (end / next_open - 1).where(complete)
    close_executable = close_status.shift(-horizon, fill_value=False)
    payoffs = (next_open * (1 - sell_cost) - end * (1 - sell_cost)) / chain
    features[f"exit{horizon}_bps0"] = payoffs.where(
        complete & close_executable & features["next_open_fill_assumed"]
    )

    listing = catalog["ipoDate"]
    delisting = catalog["outDate"]
    active_expected = pd.Series(dates >= listing, index=index)
    if delisting:
        active_expected &= dates < delisting
    coverage = {
        "ticker": ticker,
        "rows": int(present.sum()),
        "usable_rows": int(usable.sum()),
        "suspended_rows": int(suspended.sum()),
        "bad_return_rows": int((traded & ~source_ok).sum()),
        "missing_between_listing_and_delisting": int((active_expected & ~present).sum()),
        "reference_jumps": int((usable & ~normal_reference & previous_raw_close.notna()).sum()),
        "listing": listing,
        "delisting": delisting,
        "last_bar": str(raw["date"].iloc[-1]),
    }
    return features.reset_index(), coverage


def load_panel(
    data_dir: Path, data_spec_path: Path, moving_averages, horizon, sell_cost_bps
) -> tuple[pd.DataFrame, pd.Index, dict, dict]:
    """Return the verified panel, analysis calendar, coverage and data specification."""
    windows = tuple(moving_averages)
    if len(set(windows)) != len(windows) or any(type(n) is not int or n < 2 for n in windows):
        raise ValueError("Moving averages must be unique integer windows of at least two days")

    data_dir, data_spec_path = Path(data_dir), Path(data_spec_path)
    spec_content = data_spec_path.read_bytes()
    spec = json.loads(spec_content)
    source = json.loads((data_dir / "source.json").read_text(encoding="utf-8"))
    if source["spec_sha256"] != hashlib.sha256(spec_content).hexdigest():
        raise ValueError("Specification does not match the data receipt")
    if set(source["files"]) != SOURCE_FILES:
        raise ValueError("Reference data receipts are incomplete or contain unexpected files")
    reference = {}
    for filename, digest in source["files"].items():
        content = (data_dir / filename).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"Changed reference data: {filename}")
        reference[filename] = content

    receipts = json.loads(reference["bars-receipts.json"])
    calendar = pd.read_csv(BytesIO(reference["calendar.csv"]), dtype={"calendar_date": str})
    dates = pd.Index(calendar.loc[calendar.is_trading_day.eq(1), "calendar_date"])
    if dates.empty or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError("Trading calendar is empty, duplicated, or out of order")
    if not calendar.calendar_date.between(spec["bar_start"], spec["bar_end"]).all():
        raise ValueError("Trading calendar falls outside the specification")

    sample = pd.read_csv(BytesIO(reference["universe.csv"]), dtype={"code": str})
    basics = pd.read_csv(BytesIO(reference["stock-basic.csv"]), keep_default_na=False).set_index(
        "code"
    )
    if sample.empty or sample.code.duplicated().any() or basics.index.has_duplicates:
        raise ValueError("Security catalog is empty or duplicated")
    if set(receipts) != set(sample.code) or set(basics.index) != set(sample.code):
        raise ValueError("Security catalog does not match frozen universe receipts")

    all_features, per_stock, missing = [], [], []
    for record in sample.itertuples(index=False):
        code = record.code
        if not TICKER.fullmatch(code):
            raise ValueError(f"Unexpected security code in frozen universe: {code}")
        receipt = receipts[code]
        if not receipt["rows"]:
            missing.append(code)
            continue
        bars = (data_dir / "bars" / f"{code}.csv").read_bytes()
        if hashlib.sha256(bars).hexdigest() != receipt["sha256"]:
            raise ValueError(f"Changed bars: {code}")
        features, scope = stock_features(
            BytesIO(bars),
            dates,
            code,
            record.stratum,
            spec,
            basics.loc[code],
            windows,
            horizon,
            sell_cost_bps,
        )
        if scope["rows"] != receipt["rows"]:
            raise ValueError(f"History coverage count changed: {code}")
        all_features.append(features)
        per_stock.append(scope)

    analysis_dates = dates[dates >= spec["signal_start"]]
    if not all_features or analysis_dates.empty:
        raise ValueError("Frozen data contains no usable security series or analysis dates")
    panel = pd.concat(all_features, ignore_index=True)
    panel = (
        panel.loc[panel.date >= spec["signal_start"]]
        .sort_values(["date", "ticker"], kind="stable")
        .reset_index(drop=True)
    )

    coverage = {
        "raw_rows": sum(row["rows"] for row in per_stock),
        "usable_rows": sum(row["usable_rows"] for row in per_stock),
        "by_stratum": dict(Counter(sample.loc[~sample.code.isin(missing), "stratum"])),
        "suspended_rows": sum(row["suspended_rows"] for row in per_stock),
        "bad_return_rows": sum(row["bad_return_rows"] for row in per_stock),
        "missing_data_tickers": missing,
        "missing_expected_rows": sum(
            row["missing_between_listing_and_delisting"] for row in per_stock
        ),
        "with_delisting": [row for row in per_stock if row["delisting"]],
        "per_stock": per_stock,
        "source": source,
    }
    return panel, analysis_dates, coverage, spec
