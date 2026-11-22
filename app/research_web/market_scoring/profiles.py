"""Frozen market-specific definitions; equal scales do not imply comparability."""

from copy import deepcopy

from core.observability import get_logger

log = get_logger(__name__)
PROFILE_VERSION = "market-six-axis-v1"
VALIDATION_POLICY = "event-study-v1"
AXES = ("trend", "breadth", "sentiment", "funds", "valuation", "risk")
INDICES = {
    "SSE": ("CN", "上证综指", "CNY"),
    "CSI300": ("CN", "沪深300", "CNY"),
    "CHINEXT": ("CN", "创业板指", "CNY"),
    "SP500": ("US", "标普500", "USD"),
    "NASDAQ": ("US", "纳斯达克综合", "USD"),
    "DJI": ("US", "道琼斯工业", "USD"),
    "HSI": ("HK", "恒生指数", "HKD"),
    "HSCEI": ("HK", "恒生国企", "HKD"),
    "HSTECH": ("HK", "恒生科技", "HKD"),
}


def _axis(metric, providers, *, scope="index", normalization="past_percentile", inverse=False):
    return {
        "metric": metric,
        "unit": {
            "momentum_20d": "percent",
            "advancing_share": "ratio",
            "confirmed_limit_balance": "ratio",
            "market_main_net": "CNY",
            "median_positive_pe": "multiple",
            "index_positive_pe": "multiple",
            "volatility_20d": "percent",
            "put_call_volume_ratio": "ratio",
            "net_etf_primary_flow_pct_aum": "percent",
        }[metric],
        "providers": providers,
        "scope": scope,
        "normalization": normalization,
        "inverse": inverse,
        "lookback_observations": 1260,
        "minimum_observations": 252,
        "missing": "unavailable_no_fill_no_weight_redistribution",
    }


_CN = {
    "trend": _axis("momentum_20d", ["eastmoney", "baostock", "tinysoft", "wind"]),
    "breadth": _axis(
        "advancing_share", ["eastmoney", "tinysoft", "wind"], scope="market", normalization="share"
    ),
    "sentiment": _axis(
        "confirmed_limit_balance",
        ["eastmoney", "tinysoft", "wind"],
        scope="market",
        normalization="signed_share",
    ),
    "funds": _axis("market_main_net", ["eastmoney", "tinysoft", "wind"], scope="market"),
    "valuation": _axis(
        "median_positive_pe", ["eastmoney", "csindex", "wind"], scope="market", inverse=True
    ),
    "risk": _axis("volatility_20d", ["eastmoney", "baostock", "tinysoft", "wind"], inverse=True),
}
_US = {
    "trend": _axis("momentum_20d", ["yahoo", "nasdaq", "spglobal", "issuer"]),
    "breadth": _axis("advancing_share", ["nasdaq", "spglobal", "issuer"], normalization="share"),
    "sentiment": _axis("put_call_volume_ratio", ["cboe"], scope="market", inverse=True),
    "funds": _axis("net_etf_primary_flow_pct_aum", ["issuer", "sec"]),
    "valuation": _axis("index_positive_pe", ["spglobal", "nasdaq", "issuer"], inverse=True),
    "risk": _axis("volatility_20d", ["yahoo", "nasdaq", "spglobal", "issuer"], inverse=True),
}
_HK = {
    "trend": _axis("momentum_20d", ["yahoo", "hkex", "hangseng", "issuer"]),
    "breadth": _axis("advancing_share", ["hkex", "hangseng", "issuer"], normalization="share"),
    "sentiment": _axis("put_call_volume_ratio", ["hkex"], scope="market", inverse=True),
    "funds": _axis("net_etf_primary_flow_pct_aum", ["issuer", "hkex"]),
    "valuation": _axis("index_positive_pe", ["hangseng", "issuer"], inverse=True),
    "risk": _axis("volatility_20d", ["yahoo", "hkex", "hangseng", "issuer"], inverse=True),
}
MARKET_AXES = {"CN": _CN, "US": _US, "HK": _HK}


def profile_for(index_id):
    """Return independent definitions; a listed provider is not source approval."""
    if index_id not in INDICES:
        log.warning("market_score_index_rejected")
        raise ValueError("market_score_index_unknown")
    market, name, currency = INDICES[index_id]
    return deepcopy(
        {
            "version": PROFILE_VERSION,
            "index_id": index_id,
            "name": name,
            "market": market,
            "currency": currency,
            "timezone": {"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}[
                market
            ],
            "horizon": 20,
            "axes": MARKET_AXES[market],
            "weights": {axis: 1 / 6 for axis in AXES},
            "overlay_family_points": 1,
            "overlay_cap": 5,
            "cross_market_ranking": False,
            "production_enabled": False,
            "source_permission": "recheck_each_call",
        }
    )


def profiles():
    return [profile_for(index_id) for index_id in INDICES]
