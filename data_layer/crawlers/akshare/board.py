"""
AkShare 板块行情获取器

从同花顺行业板块接口获取实时涨跌幅数据。
"""
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import List, Optional

from core.observability import get_logger

logger = get_logger("akshare_board")

CACHE_TTL_SECONDS = 300  # 5 分钟缓存
STALE_CACHE_TTL_SECONDS = 1800  # 刷新失败时，旧缓存最多再用 30 分钟
MAX_RETRIES = 3  # AKShare 接口重试次数
RETRY_BACKOFF = 2.0  # 重试退避系数（秒）
PROXY_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


@dataclass
class SectorBoardItem:
    """板块行情数据"""

    name: str
    change_pct: float
    net_flow: float  # 净流入（亿元）
    up_count: int  # 上涨家数
    down_count: int  # 下跌家数
    total_volume: float  # 总成交量（万手）
    total_amount: float  # 总成交额（亿元）
    avg_price: float  # 均价
    leading_stock_name: str
    leading_stock_price: float
    leading_stock_change_pct: float


@dataclass
class SectorBoardSnapshot:
    """板块行情快照"""

    sectors: List[SectorBoardItem] = field(default_factory=list)
    fetched_at: float = 0.0
    source: str = "ths"


# 模块级缓存
_cache: Optional[SectorBoardSnapshot] = None


@contextmanager
def _without_proxy_env():
    """临时绕过桌面代理，避免本地坏代理导致 AKShare 请求失败"""
    saved = {key: os.environ.get(key) for key in (*PROXY_ENV_KEYS, "NO_PROXY")}
    removed = [key for key in PROXY_ENV_KEYS if os.environ.get(key)]

    for key in PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"

    if removed:
        logger.debug(f"Temporarily disabled proxy env for AKShare board fetch: {removed}")

    try:
        yield
    finally:
        for key in PROXY_ENV_KEYS:
            value = saved[key]
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        no_proxy = saved["NO_PROXY"]
        if no_proxy is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = no_proxy


def _is_cache_valid() -> bool:
    return _cache is not None and (time.time() - _cache.fetched_at) < CACHE_TTL_SECONDS


def _is_cache_stale() -> bool:
    """缓存是否过期但仍在可容忍范围内（用于刷新失败时兜底）"""
    return _cache is not None and (time.time() - _cache.fetched_at) < STALE_CACHE_TTL_SECONDS


def _fetch_with_retry():
    """带重试的 AKShare 板块数据获取"""
    import akshare as ak

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with _without_proxy_env():
                df = ak.stock_board_industry_summary_ths()
            return df
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * attempt
                logger.warning(
                    f"AKShare board fetch attempt {attempt}/{MAX_RETRIES} failed: {e}. "
                    f"Retrying in {wait:.1f}s..."
                )
                time.sleep(wait)
    raise last_error  # type: ignore[misc]


def fetch_sector_board(force_refresh: bool = False) -> SectorBoardSnapshot:
    """获取同花顺行业板块实时行情（带缓存）

    Args:
        force_refresh: 强制刷新缓存

    Returns:
        SectorBoardSnapshot 包含所有行业板块行情
    """
    global _cache

    if _is_cache_valid() and not force_refresh:
        assert _cache is not None
        return _cache

    try:
        df = _fetch_with_retry()

        sectors = []
        for _, row in df.iterrows():
            sectors.append(
                SectorBoardItem(
                    name=str(row.get("板块", "")),
                    change_pct=float(row.get("涨跌幅", 0)),
                    net_flow=float(row.get("净流入", 0)),
                    up_count=int(row.get("上涨家数", 0)),
                    down_count=int(row.get("下跌家数", 0)),
                    total_volume=float(row.get("总成交量", 0)),
                    total_amount=float(row.get("总成交额", 0)),
                    avg_price=float(row.get("均价", 0)),
                    leading_stock_name=str(row.get("领涨股", "")),
                    leading_stock_price=float(row.get("领涨股-最新价", 0)),
                    leading_stock_change_pct=float(row.get("领涨股-涨跌幅", 0)),
                )
            )

        _cache = SectorBoardSnapshot(
            sectors=sectors,
            fetched_at=time.time(),
            source="ths",
        )
        logger.info(f"Fetched {len(sectors)} sector boards from THS")
        return _cache

    except Exception as e:
        logger.error(f"Failed to fetch sector board data after {MAX_RETRIES} retries: {e}")
        if _is_cache_stale():
            # `_is_cache_stale` reads the module-level cache, so mypy cannot
            # retain its Optional narrowing across that function call.
            assert _cache is not None
            logger.warning(f"Returning stale cache (age={time.time() - _cache.fetched_at:.0f}s)")
            return _cache
        if _cache is not None:
            logger.warning("Cache too old, but returning as last resort")
            return _cache
        return SectorBoardSnapshot()


def get_last_fetch_time() -> float:
    """获取板块数据最后获取时间（Unix timestamp），用于前端显示数据日期"""
    if _cache is not None:
        return _cache.fetched_at
    return 0.0


def get_top_gainers(limit: int = 5) -> List[SectorBoardItem]:
    """获取涨幅最高的板块（仅返回 change_pct > 0 的上涨板块）"""
    snapshot = fetch_sector_board()
    positive = [s for s in snapshot.sectors if s.change_pct > 0]
    positive.sort(key=lambda s: s.change_pct, reverse=True)
    return positive[:limit]


def get_top_losers(limit: int = 5) -> List[SectorBoardItem]:
    """获取跌幅最高的板块（仅返回 change_pct < 0 的下跌板块）"""
    snapshot = fetch_sector_board()
    negative = [s for s in snapshot.sectors if s.change_pct < 0]
    negative.sort(key=lambda s: s.change_pct)
    return negative[:limit]
