"""Versioned descriptive market axes and past-only observation diagnostics.

These formulas have no validated forecasting claim. Current index membership
never supplies historical breadth, and diagnostics cannot enable allocations.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from itertools import pairwise
from pathlib import Path
from statistics import median, pstdev
from typing import TypeGuard
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .market_portfolio import atomic_json, read_json
from .market_service import MarketError

log = get_logger(__name__)
VERSION = "market-observed-v1"
SHANGHAI = ZoneInfo("Asia/Shanghai")
HORIZONS = {"intraday": (1, 3), "swing": (5, 20), "allocation": (20, 60)}
MAX_OBSERVATIONS = 260
HISTORY_BYTES = 2 * 1024 * 1024
FORMULAS = {
    "trend": "mean current index change_pct; sourced closed bars supply horizon momentum/MA and past-only momentum ranks; descriptive, not forward return",
    "breadth": "same-date tradable advancing / all same-date tradable rows; require every eligible change_pct",
    "sentiment": "(confirmed limit-up - confirmed limit-down) / all eligible rows; require known limit status",
    "funds": "source market_flow latest complete daily main_net; no sector sum substitution",
    "valuation": "median positive dynamic PE/PB from same-date rows; nonpositive excluded; score=100-past-only PE percentile, not a growth/value style preference",
    "risk": "same-date cross-sectional dispersion or sourced horizon price-index daily volatility/drawdown; history-bar score=0.5*(100-volatility percentile)+0.5*(100-absolute drawdown percentile); same-day dispersion fallback inverse rank",
}


def _number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _stamp(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
        return stamp if stamp.tzinfo else None
    except ValueError:
        return None


def past_percentile(value, history, as_of, *, minimum=20):
    """Midrank empirical percentile using only earlier days known by the cutoff."""
    cutoff = _stamp(as_of)
    values, seen = [], set()
    if cutoff and _number(value):
        cutoff_day = cutoff.astimezone(SHANGHAI).date().isoformat()
        for row in history[-MAX_OBSERVATIONS:]:
            known = _stamp(row.get("known_at"))
            day = row.get("date")
            try:
                valid_day = isinstance(day, str) and date.fromisoformat(day).isoformat() == day
            except ValueError:
                valid_day = False
            if (
                valid_day
                and day < cutoff_day
                and known
                and known <= cutoff
                and known.astimezone(SHANGHAI).date().isoformat() >= day
                and _number(row.get("value"))
                and day not in seen
            ):
                values.append(row["value"])
                seen.add(day)
    result = None
    if len(values) >= max(20, minimum):
        result = (
            100
            * (sum(v < value for v in values) + 0.5 * sum(v == value for v in values))
            / len(values)
        )
    return {
        "version": VERSION,
        "method": "past_only_midrank_percentile",
        "value": result,
        "sample_count": len(values),
        "minimum_samples": max(20, minimum),
        "as_of": as_of,
        "status": "observed" if result is not None else "insufficient_history",
    }


def factor_score(axis, value, history, as_of):
    """Versioned descriptive scales, never a cross-axis investment preference.

    Breadth is the advancing share, sentiment the confirmed limit balance.
    Other scales use empirical past-only ranks. Risk and valuation reverse
    their level ranks so higher scores mean lower observed volatility or lower
    observed valuation, without claiming a growth/value style preference.
    """
    if axis not in FORMULAS:
        raise MarketError("market_axis_invalid", "分析维度无效。")
    if axis in {"breadth", "sentiment"}:
        lower = 0 if axis == "breadth" else -1
        score = None
        if _number(value) and lower <= value <= 1:
            score = 100 * value if axis == "breadth" else 50 * (1 + value)
        return {
            "version": VERSION,
            "score": score,
            "method": "observed_share" if axis == "breadth" else "confirmed_limit_balance",
            "meaning": "descriptive_level_not_forecast",
            "sample_count": None,
        }
    rank = past_percentile(value, history, as_of)
    score = rank["value"]
    if score is not None and axis in {"risk", "valuation"}:
        score = 100 - score
    return {
        **rank,
        "score": score,
        "level_percentile": rank["value"],
        "direction": "inverse" if axis in {"risk", "valuation"} else "positive",
        "meaning": (
            "lower_observed_risk"
            if axis == "risk"
            else "lower_observed_valuation" if axis == "valuation" else "higher_observed_level"
        ),
    }


def _index_features(snapshot, horizon):
    """Features from explicitly sourced closed price-index bars only.

    Historical vendor bars supply descriptive price levels, not PIT revisions,
    constituent breadth, strategy returns, or independent forecast validation.
    """
    if (
        not snapshot
        or snapshot.get("complete") is not True
        or snapshot.get("pagination_complete") is not True
    ):
        return None
    cutoff = _stamp(snapshot.get("as_of"))
    if cutoff is None:
        return None
    lookback = HORIZONS[horizon][1]
    per_index = []
    for row in snapshot.get("rows", []):
        source = row.get("daily_source", {})
        if (
            not isinstance(source, dict)
            or source.get("adjustment") != "price_index"
            or not all(
                isinstance(source.get(k), str) and source[k]
                for k in ("provider", "source_url", "retrieved_at")
            )
            or _stamp(source["retrieved_at"]) is None
        ):
            continue
        bars = row.get("daily_bars", [])
        if not isinstance(bars, list) or len(bars) > 1000:
            continue
        valid, seen = [], set()
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            day = bar.get("date")
            try:
                if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                    continue
            except ValueError:
                continue
            # Same-day close is available only at/after 15:00 local; future and
            # intraday close placeholders cannot leak into past-only factors.
            bar_end = datetime.fromisoformat(day + "T15:00:00+08:00")
            if (
                bar_end > cutoff
                or not _number(bar.get("close"))
                or bar["close"] <= 0
                or day in seen
            ):
                continue
            seen.add(day)
            valid.append({"date": day, "close": bar["close"]})
        valid.sort(key=lambda bar: bar["date"])
        if len(valid) < lookback + 1:
            continue

        def features(window):
            prices = [bar["close"] for bar in window]
            returns = [100 * (b / a - 1) for a, b in pairwise(prices)]
            peak = prices[0]
            drawdown = 0.0
            for price in prices:
                peak = max(peak, price)
                drawdown = min(drawdown, 100 * (price / peak - 1))
            return {
                "momentum_pct": 100 * (prices[-1] / prices[0] - 1),
                "moving_average": math.fsum(prices[-lookback:]) / lookback,
                "above_moving_average": prices[-1] > math.fsum(prices[-lookback:]) / lookback,
                "daily_volatility_pct": pstdev(returns),
                "maximum_drawdown_pct": drawdown,
            }

        current = features(valid[-lookback - 1 :])
        historical: dict[str, list[dict]] = {"trend": [], "volatility": [], "drawdown": []}
        for end in range(lookback, len(valid) - 1):
            item = features(valid[end - lookback : end + 1])
            for factor, field in (
                ("trend", "momentum_pct"),
                ("volatility", "daily_volatility_pct"),
                ("drawdown", "maximum_drawdown_pct"),
            ):
                historical[factor].append(
                    {
                        "date": valid[end]["date"],
                        "value": abs(item[field]) if factor == "drawdown" else item[field],
                    }
                )

        def dated_score(axis, value, history, *, last_day=valid[-1]["date"], source_info=source):
            # Vendor history is first observed now: do not invent historical
            # publication timestamps or pass it as verified PIT observations.
            values = [item["value"] for item in history if item["date"] < last_day]
            level = (
                100
                * (sum(v < value for v in values) + 0.5 * sum(v == value for v in values))
                / len(values)
                if len(values) >= 20
                else None
            )
            score = (100 - level if axis == "risk" else level) if level is not None else None
            return {
                "version": VERSION,
                "method": "earlier_dated_price_midrank_not_pit",
                "score": score,
                "level_percentile": level,
                "sample_count": len(values),
                "minimum_samples": 20,
                "historical_pit_verified": False,
                "availability_basis": source_info.get("availability_basis", "first_observed"),
                "first_observed_at": source_info["retrieved_at"],
                "direction": "inverse" if axis == "risk" else "positive",
            }

        volatility = dated_score("risk", current["daily_volatility_pct"], historical["volatility"])
        drawdown = dated_score("risk", abs(current["maximum_drawdown_pct"]), historical["drawdown"])
        risk_score = (
            (volatility["score"] + drawdown["score"]) / 2
            if volatility["score"] is not None and drawdown["score"] is not None
            else None
        )
        scores = {
            "trend": dated_score("trend", current["momentum_pct"], historical["trend"]),
            "risk": {
                "score": risk_score,
                "version": VERSION,
                "method": "equal_weight_inverse_volatility_drawdown_dated_ranks_not_pit",
                "weights": {"volatility": 0.5, "drawdown": 0.5},
                "volatility": volatility,
                "drawdown": drawdown,
            },
        }
        per_index.append(
            {
                "asset": row.get("asset"),
                "metrics": current,
                "scores": scores,
                "last_bar_date": valid[-1]["date"],
                "source": source,
                "sample_count": len(valid),
                "lookback_observations": lookback,
            }
        )
    if not per_index:
        return None
    # A fixed named benchmark defines the market trend/risk scope. Other
    # unavailable catalog histories do not alter its weights or identity.
    benchmark = next(
        (
            item
            for asset in ("000300.SH", "000001.SH")
            for item in per_index
            if item["asset"] == asset
        ),
        None,
    )
    catalog_complete = len(per_index) == len(snapshot.get("rows", []))
    selected = [benchmark] if benchmark else per_index
    scope_complete = bool(benchmark) or catalog_complete
    aggregate = {
        field: math.fsum(float(index["metrics"][field]) for index in selected) / len(selected)
        for field in ("momentum_pct", "daily_volatility_pct", "maximum_drawdown_pct")
    }
    scores = {}
    for axis in ("trend", "risk"):
        values = [index["scores"][axis]["score"] for index in selected]
        scores[axis] = (
            math.fsum(values) / len(values)
            if scope_complete and all(_number(value) for value in values)
            else None
        )
    return {
        "metrics": aggregate,
        "scores": scores,
        "indices": per_index,
        "complete": scope_complete,
        "catalog_complete": catalog_complete,
        "scope": (
            {"type": "benchmark", "asset": benchmark["asset"]} if benchmark else {"type": "catalog"}
        ),
        "scope_covered": len(selected),
        "scope_expected": 1 if benchmark else len(snapshot.get("rows", [])),
        "covered": len(per_index),
        "expected": len(snapshot.get("rows", [])),
        "historical_pit_verified": False,
        "availability_basis": "first_observed",
        "reason": (
            "固定优先沪深300、其次上证指数的价格指数观测；目录缺口保留，不代表全市场历史。"
            if benchmark
            else "仅完整目录可形成等权价格指数观测。"
        ),
    }


def walk_forward(observations, *, horizon="swing"):
    """Chronological expanding folds with embargo, without fabricated P&L.

    Days represent observed sessions, not inferred missing trading dates. A full
    forecast test needs immutable targets, revision/PIT series, costs and a
    benchmark; none can be inferred from these descriptive cached observations.
    """
    if horizon not in HORIZONS:
        raise MarketError("market_horizon_invalid", "请选择有效分析周期。")
    rows = {}
    for row in observations[-MAX_OBSERVATIONS:]:
        known, day = _stamp(row.get("known_at")), row.get("date")
        try:
            if (
                not isinstance(day, str)
                or date.fromisoformat(day).isoformat() != day
                or known is None
                or known.astimezone(SHANGHAI).date().isoformat() < day
            ):
                continue
        except ValueError:
            continue
        rows[day] = row
    ordered = [rows[day] for day in sorted(rows)]
    embargo = HORIZONS[horizon][1]
    folds = []
    for test_start in range(40 + embargo, len(ordered), 10):
        train = ordered[: test_start - embargo]
        test = ordered[test_start : test_start + 10]
        # A late capture of an earlier observation cannot train an earlier test.
        cutoff = _stamp(test[0]["known_at"])
        train = [row for row in train if _stamp(row["known_at"]) < cutoff]
        if len(train) >= 40 and test:
            folds.append(
                {
                    "train_start": train[0]["date"],
                    "train_end": train[-1]["date"],
                    "test_start": test[0]["date"],
                    "test_end": test[-1]["date"],
                    "train_count": len(train),
                    "test_count": len(test),
                    "embargo_observations": embargo,
                }
            )
    return {
        "version": VERSION,
        "method": "chronological_expanding_with_embargo",
        "folds": folds,
        "observation_count": len(ordered),
        "returns": None,
        "status": "diagnostic_only",
        "missing": [
            "immutable_point_in_time_targets",
            "execution_costs",
            "benchmark",
            "independent_horizon_validation",
        ],
        "reason": "仅检查历史时序切分；未执行收益回测，不构成分周期预测或配置验收。",
    }


def _axes(snapshots):
    axes: dict[str, dict] = {
        key: {
            "status": "unavailable",
            "score": None,
            "metrics": {},
            "formula": formula,
            "reason": "缺少完整、同日、可追溯的缓存输入。",
            "provenance": [],
        }
        for key, formula in FORMULAS.items()
    }

    def observe(key, metrics, snapshot, *, reason="仅为描述性观测，未经预测有效性验收。"):
        axes[key].update(
            status="observed",
            metrics=metrics,
            reason=reason,
            provenance=[
                {
                    field: snapshot.get(field)
                    for field in ("snapshot_id", "provider", "source_url", "as_of", "retrieved_at")
                }
            ],
        )

    indices = snapshots.get("indices:terminal-v2") or snapshots.get("indices")
    if indices and indices.get("complete") is True and indices.get("pagination_complete") is True:
        values = [row.get("change_pct") for row in indices.get("rows", [])]
        days = {row.get("as_of", "")[:10] for row in indices.get("rows", [])}
        if (
            values
            and all(_number(value) for value in values)
            and len(days) == 1
            and "" not in days
            and days == {str(indices.get("as_of", ""))[:10]}
        ):
            observe(
                "trend",
                {"mean_change_pct": math.fsum(values) / len(values), "index_count": len(values)},
                indices,
            )
    quotes = snapshots.get("quotes")
    if quotes and quotes.get("complete") is True and quotes.get("pagination_complete") is True:
        day = quotes.get("summary", {}).get("quote_trade_date")
        eligible = [
            row
            for row in quotes.get("rows", [])
            if row.get("trade_status") not in {"suspended", "unlisted", "delisted"}
        ]
        rows = [
            row
            for row in eligible
            if isinstance(row.get("as_of"), str)
            and row["as_of"][:10] == day
            and not row.get("stale", False)
            and row.get("trade_status") not in {"unknown", None}
        ]
        values = [row.get("change_pct") for row in rows]
        if rows and len(rows) == len(eligible) and all(_number(value) for value in values):
            observe(
                "breadth",
                {
                    "advancing_share": sum(value > 0 for value in values) / len(values),
                    "declining_share": sum(value < 0 for value in values) / len(values),
                    "sample_count": len(values),
                    "membership_basis": "observed_current_quote_universe",
                },
                quotes,
            )
            observe("risk", {"dispersion_pct": pstdev(values), "sample_count": len(values)}, quotes)
        limits = [row.get("limit_status") for row in rows]
        # Provider uses up/down/none; old or unknown enums cannot imply normal.
        if (
            rows
            and len(rows) == len(eligible)
            and all(value in {"up", "down", "none"} for value in limits)
        ):
            observe(
                "sentiment",
                {
                    "limit_balance": (limits.count("up") - limits.count("down")) / len(limits),
                    "sample_count": len(limits),
                },
                quotes,
            )
        if rows:
            pes = [
                row["pe_dynamic"]
                for row in rows
                if _number(row.get("pe_dynamic")) and row["pe_dynamic"] > 0
            ]
            pbs = [row["pb"] for row in rows if _number(row.get("pb")) and row["pb"] > 0]
            if pes or pbs:
                observe(
                    "valuation",
                    {
                        "median_pe_dynamic": median(pes) if pes else None,
                        "median_pb": median(pbs) if pbs else None,
                        "pe_count": len(pes),
                        "pb_count": len(pbs),
                        "eligible_count": len(eligible),
                        "same_date_count": len(rows),
                    },
                    quotes,
                    reason="正值样本中位数；负盈利/缺失剔除且列出覆盖数，不据此判定成长或价值更优。",
                )
    for key in ("flows:industry:today", "flows:concept:today"):
        flow_snapshot = snapshots.get(key, {})
        flow = flow_snapshot.get("summary", {}).get("market_flow", {})
        if flow.get("complete") is not True or flow.get("stale") is True:
            continue
        flow_rows = flow.get("rows", [])
        if flow_rows:
            latest = max(flow_rows, key=lambda row: row.get("date", ""))
            if _number(latest.get("main_net")):
                observe(
                    "funds",
                    {"main_net": latest["main_net"], "date": latest.get("date")},
                    flow_snapshot,
                )
                break
    return axes


class AnalysisHistory:
    """Bounded completed daily observations inside this user's market cache."""

    def __init__(self, root: Path):
        self.directory = Path(root) / "analysis-observations"

    def read(self):
        try:
            value = read_json(
                self.directory,
                "daily.json",
                HISTORY_BYTES,
                {"version": VERSION, "observations": []},
            )
            if (
                not isinstance(value, dict)
                or value.get("version") != VERSION
                or not isinstance(value.get("observations"), list)
                or len(value["observations"]) > MAX_OBSERVATIONS
                or not all(
                    isinstance(row, dict)
                    and isinstance(row.get("metrics"), dict)
                    and isinstance(row.get("date"), str)
                    and _stamp(row.get("known_at"))
                    for row in value["observations"]
                )
            ):
                raise ValueError("invalid_history")
            return value["observations"]
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            log.warning("market_analysis_history_read_failed", code="invalid_history")
            raise MarketError(
                "market_analysis_history_unavailable", "分析历史缓存不可用。", 503
            ) from exc

    def capture(self, quotes, snapshots=None):
        """Called only after an explicit successful quotes refresh, never by GET."""
        summary = quotes.get("summary", {})
        day, known = summary.get("quote_trade_date"), _stamp(quotes.get("retrieved_at"))
        rows = quotes.get("rows", [])
        try:
            if (
                quotes.get("complete") is not True
                or quotes.get("pagination_complete") is not True
                or summary.get("closing_snapshot") is not True
                or not rows
                or known is None
                or date.fromisoformat(day).isoformat() != day
                or day > datetime.now(SHANGHAI).date().isoformat()
                or known < datetime.fromisoformat(day + "T15:00:00+08:00")
            ):
                return
            for row in rows:
                if row.get("trade_status") in {"suspended", "unlisted", "delisted"}:
                    continue
                stamp = _stamp(row.get("as_of"))
                if (
                    row.get("source_closed") is not True
                    or stamp is None
                    or stamp.astimezone(SHANGHAI).date().isoformat() != day
                    or stamp < datetime.fromisoformat(day + "T15:00:00+08:00")
                ):
                    return
        except (TypeError, ValueError):
            return
        axes = _axes({**(snapshots or {}), "quotes": quotes})
        metrics = {}
        for axis in axes.values():
            provenance = axis.get("provenance", [])
            if (
                provenance
                and str(provenance[0].get("as_of", ""))[:10] == day
                and axis["metrics"].get("date", day) == day
            ):
                metrics.update(axis["metrics"])
        observations = self.read()
        # First completed capture is immutable; later intraday/revised snapshots
        # cannot quietly replace the observation used by a diagnostic.
        if any(row.get("date") == day for row in observations):
            return
        observations.append(
            {
                "date": day,
                "known_at": known.isoformat(),
                "metrics": metrics,
                "snapshot_id": quotes.get("snapshot_id"),
                "provider": quotes.get("provider"),
                "source_url": quotes.get("source_url"),
                "membership_basis": "observed_on_day",
            }
        )
        observations = sorted(observations, key=lambda row: row["date"])[-MAX_OBSERVATIONS:]
        try:
            atomic_json(
                self.directory,
                "daily.json",
                {"version": VERSION, "observations": observations},
                HISTORY_BYTES,
            )
            log.info("market_analysis_observation_captured", count=len(observations))
        except (OSError, TypeError, ValueError) as exc:
            log.warning("market_analysis_history_write_failed", code="history_write_failed")
            raise MarketError(
                "market_analysis_history_unavailable", "分析历史保存失败。", 503
            ) from exc


def _style_profile(snapshot, horizon):
    """Six official size/style price indices; current comparisons are provisional.

    Vendor daily bars are first-observed descriptions, not PIT strategy results.
    No missing cell is neutral and no growth/value preference enters axis scores.
    """
    identities = (
        ("399372.SZ", "large", "growth"),
        ("399373.SZ", "large", "value"),
        ("399374.SZ", "mid", "growth"),
        ("399375.SZ", "mid", "value"),
        ("399376.SZ", "small", "growth"),
        ("399377.SZ", "small", "value"),
    )
    lookback = None if horizon == "intraday" else HORIZONS[horizon][1]
    rows = snapshot.get("rows", []) if snapshot else []
    grouped: dict[object, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("asset"), []).append(row)
    snapshot_time = _stamp(snapshot.get("as_of")) if snapshot else None
    snapshot_day = snapshot_time.astimezone(SHANGHAI).date().isoformat() if snapshot_time else ""
    complete = bool(
        snapshot
        and snapshot.get("complete") is True
        and snapshot.get("pagination_complete") is True
    )
    cells: list[dict] = []
    for asset, size, style in identities:
        matches = grouped.get(asset, [])
        row = matches[0] if len(matches) == 1 else {}
        quote_time = _stamp(row.get("as_of"))
        same_day = bool(
            quote_time
            and snapshot_time
            and quote_time <= snapshot_time
            and quote_time.astimezone(SHANGHAI).date().isoformat() == snapshot_day
        )
        value, base_day, base_close = None, None, None
        window_dates = []
        reason = "缺少同批、同日且唯一的有效风格指数报价。"
        price = row.get("price")
        if complete and same_day and _number(price) and price > 0:
            if horizon == "intraday":
                if _number(row.get("change_pct")):
                    value = row["change_pct"]
                    reason = "同日真实报价涨跌幅；盘中临时观测。"
            else:
                lookback = HORIZONS[horizon][1]
                source = row.get("daily_source", {})
                bars = row.get("daily_bars", [])
                source_valid = (
                    isinstance(source, dict)
                    and source.get("adjustment") == "price_index"
                    and source.get("return_basis") == "price_index"
                    and source.get("last_close_cross_checked") is True
                    and source.get("symbol") == asset.split(".")[1].lower() + asset.split(".")[0]
                    and isinstance(source.get("provider"), str)
                    and bool(source["provider"])
                    and isinstance(source.get("source_url"), str)
                    and source["source_url"].startswith("https://")
                    and _stamp(source.get("retrieved_at")) is not None
                    and row.get("daily_history_status") == "ready"
                )
                valid_bars = bool(
                    isinstance(bars, list) and lookback and lookback <= len(bars) <= 1000
                )
                prior_day = None
                if valid_bars:
                    for bar in bars:
                        try:
                            day = bar.get("date") if isinstance(bar, dict) else None
                            if (
                                not isinstance(day, str)
                                or date.fromisoformat(day).isoformat() != day
                                or day >= snapshot_day
                                or (prior_day is not None and day <= prior_day)
                                or not _number(bar.get("close"))
                                or bar["close"] <= 0
                            ):
                                valid_bars = False
                                break
                            prior_day = day
                        except (TypeError, ValueError):
                            valid_bars = False
                            break
                previous = row.get("previous_close")
                cross_checked = bool(
                    valid_bars
                    and _number(previous)
                    and previous > 0
                    and abs(bars[-1]["close"] - previous) <= max(0.02, abs(previous) * 0.00001)
                )
                if source_valid and cross_checked:
                    base = bars[-lookback]
                    window_dates = [bar["date"] for bar in bars[-lookback:]]
                    base_day, base_close = base["date"], base["close"]
                    value = 100 * (price / base_close - 1)
                    reason = "当前价格对指定较早交易日价格指数收盘；盘中临时值，不是已收盘收益或PIT回测。"
                else:
                    reason = "历史日线不足、日期混杂、来源/身份不完整或昨收交叉核验失败。"
        cells.append(
            {
                "asset": asset,
                "size": size,
                "style": style,
                "return_pct": value,
                "status": "observed" if value is not None else "unavailable",
                "reason": reason,
                "provenance": {
                    "snapshot_id": snapshot.get("snapshot_id") if snapshot else None,
                    "quote_provider": snapshot.get("provider") if snapshot else None,
                    "quote_source_url": snapshot.get("source_url") if snapshot else None,
                    "quote_as_of": row.get("as_of"),
                    "base_date": base_day,
                    "base_close": base_close,
                    "window_dates": window_dates,
                    "daily_source": row.get("daily_source") if lookback else None,
                },
            }
        )
    comparison_window_status = "same_day" if horizon == "intraday" else "unavailable"
    if horizon != "intraday":
        windows: dict[tuple[str, ...], list[dict]] = {}
        for cell in cells:
            if cell["status"] == "observed":
                dates = tuple(cell["provenance"]["window_dates"])
                windows.setdefault(dates, []).append(cell)
        if len(windows) > 1:
            comparison_window_status = "mismatch"
            largest = max(len(group) for group in windows.values())
            references = [dates for dates, group in windows.items() if len(group) == largest]
            # A unique majority locates the outlier feeds. With no majority,
            # every conflicting window remains unverified rather than picking
            # one index's calendar as an authoritative trading calendar.
            reference = (
                references[0]
                if len(references) == 1
                and largest > sum(len(group) for group in windows.values()) / 2
                else None
            )
            for dates, group in windows.items():
                if reference is None or dates != reference:
                    for cell in group:
                        cell["status"] = "unavailable"
                        cell["return_pct"] = None
                        cell["reason"] = (
                            "六只风格指数的比较窗口交易日序列不一致；保留各自日期，不判断风格/规模优势。"
                        )
        elif len(windows) == 1 and all(cell["status"] == "observed" for cell in cells):
            comparison_window_status = "aligned"
    all_valid = all(cell["status"] == "observed" for cell in cells)
    spread, style_dominance, size_dominance, size_returns = None, "unknown", "unknown", None
    if all_valid:
        growth = math.fsum(cell["return_pct"] for cell in cells if cell["style"] == "growth") / 3
        value = math.fsum(cell["return_pct"] for cell in cells if cell["style"] == "value") / 3
        spread = growth - value
        # Raw spreads remain available; tolerance only absorbs binary float
        # representation at the inclusive, publicly fixed 0.1pp boundary.
        balanced_style = abs(spread) <= 0.1 or math.isclose(
            abs(spread), 0.1, rel_tol=0, abs_tol=1e-9
        )
        style_dominance = "balanced" if balanced_style else "growth" if spread > 0 else "value"
        size_returns = {
            size: math.fsum(cell["return_pct"] for cell in cells if cell["size"] == size) / 2
            for size in ("large", "mid", "small")
        }
        size_spread = max(size_returns.values()) - min(size_returns.values())
        balanced_size = size_spread <= 0.1 or math.isclose(
            size_spread, 0.1, rel_tol=0, abs_tol=1e-9
        )
        size_dominance = (
            "balanced" if balanced_size else max(size_returns, key=lambda size: size_returns[size])
        )
    return {
        "version": "official-six-style-price-v1",
        "horizon": horizon,
        "return_basis": "price_index",
        "lookback_sessions": lookback,
        "provisional": True,
        "rule": "399372/373 large growth/value;399374/375 mid;399376/377 small;intraday=change_pct;20/60=current_price/prior_session_close-1;growth-value=mean3growth-mean3value;size=mean2;deadband0.1pp;all6required;identical_window_date_sequences_required",
        "deadband_pp": 0.1,
        "deadband_comparison_tolerance_pp": 1e-9,
        "comparison_window_status": comparison_window_status,
        "cells": cells,
        "growth_minus_value_pp": spread,
        "style_dominance": style_dominance,
        "size_dominance": size_dominance,
        "size_returns_pct": size_returns,
        "status": "observed" if all_valid else "incomplete",
        "historical_pit_verified": False,
        "availability_basis": "first_observed",
        "micro": {
            "status": "unavailable",
            "reason": "本固定矩阵没有已核验、同口径的微盘成长/价值指数配对。",
        },
        "limitations": [
            "价格指数不含分红；仅描述相对表现，不预言风格收益。",
            "成长/价值不具有天然优劣权重，不进入六轴总分。",
            "历史来源首次取得，未证明各历史时点可得性。",
        ],
    }


def analyze(snapshots, observations, *, horizon="swing"):
    if horizon not in HORIZONS:
        raise MarketError("market_horizon_invalid", "请选择有效分析周期。")
    axes = _axes(snapshots)
    as_of = snapshots.get("quotes", {}).get("as_of")
    metric_fields = {
        "trend": "mean_change_pct",
        "breadth": "advancing_share",
        "sentiment": "limit_balance",
        "funds": "main_net",
        "valuation": "median_pe_dynamic",
        "risk": "dispersion_pct",
    }
    for axis, field in metric_fields.items():
        current = axes[axis]["metrics"].get(field)
        prior = [
            {
                "date": row.get("date"),
                "known_at": row.get("known_at"),
                "value": row.get("metrics", {}).get(field),
            }
            for row in observations
        ]
        scoring = factor_score(axis, current, prior, as_of)
        axes[axis]["scoring"] = scoring
        axes[axis]["score"] = scoring["score"]
    index_snapshot = snapshots.get("indices:terminal-v2") or snapshots.get("indices")
    features = _index_features(index_snapshot, horizon)
    if features:
        for axis in ("trend", "risk"):
            axes[axis]["metrics"].update(features["metrics"])
            axes[axis].update(
                status="observed" if features["complete"] else "partial",
                score=features["scores"][axis],
                index_features=features,
                reason="来源历史价格指数的分周期描述性特征与过去分位；不是PIT回测或预测验收。",
            )
            axes[axis]["scoring"] = {
                "version": VERSION,
                "method": (
                    "benchmark_dated_price_ranks_not_pit"
                    if features["scope"]["type"] == "benchmark"
                    else "complete_catalog_dated_price_ranks_not_pit"
                ),
                "scope": features["scope"],
                "historical_pit_verified": False,
                "score": features["scores"][axis],
                "lookback_observations": HORIZONS[horizon][1],
                "covered": features["scope_covered"],
                "expected": features["scope_expected"],
            }
    return {
        "version": VERSION,
        "formula_version": VERSION,
        "horizon": {"id": horizon, "days": list(HORIZONS[horizon]), "unit": "trading_days"},
        "axes": axes,
        "style_profile": _style_profile(index_snapshot, horizon),
        "total_score": None,
        "allocation": None,
        "status": (
            "observed_only"
            if any(axis["status"] == "observed" for axis in axes.values())
            else "unavailable"
        ),
        "validation": {
            "status": "insufficient_evidence",
            "formal_score_enabled": False,
            "allocation_enabled": False,
            "horizon": horizon,
            "reason": "尚无冻结、独立核验的分周期有效性证据；客户端参数不能开启总分或仓位建议。",
        },
        "history": {
            "observation_count": len(observations),
            "maximum": MAX_OBSERVATIONS,
            "basis": "completed_real_daily_captures_only",
            "diagnostics": walk_forward(observations, horizon=horizon),
        },
        "limitations": [
            "公开缓存不是正式PIT历史；不以当前成分回填历史广度。",
            "所有轴保留缺口；不填0/50、不重分配缺失权重。",
            "当前观测不能证明未来1–3/5–20/20–60交易日收益。",
        ],
    }
