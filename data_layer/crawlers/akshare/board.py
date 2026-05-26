"""
AkShare 板块行情获取器

从同花顺行业板块接口获取实时涨跌幅数据。
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional

from core.observability import get_logger

logger = get_logger("akshare_board")

CACHE_TTL_SECONDS = 300  # 5 分钟缓存


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


def _is_cache_valid() -> bool:
    return _cache is not None and (time.time() - _cache.fetched_at) < CACHE_TTL_SECONDS


def fetch_sector_board(force_refresh: bool = False) -> SectorBoardSnapshot:
    """获取同花顺行业板块实时行情（带缓存）

    Args:
        force_refresh: 强制刷新缓存

    Returns:
        SectorBoardSnapshot 包含所有行业板块行情
    """
    global _cache

    if _is_cache_valid() and not force_refresh:
        return _cache

    try:
        import akshare as ak

        df = ak.stock_board_industry_summary_ths()

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
        logger.error(f"Failed to fetch sector board data: {e}")
        if _cache is not None:
            logger.warning("Returning stale cache")
            return _cache
        return SectorBoardSnapshot()


def get_last_fetch_time() -> float:
    """获取板块数据最后获取时间（Unix timestamp），用于前端显示数据日期"""
    if _cache is not None:
        return _cache.fetched_at
    return 0.0


def get_top_gainers(limit: int = 5) -> List[SectorBoardItem]:
    """获取涨幅最高的板块"""
    snapshot = fetch_sector_board()
    sorted_sectors = sorted(snapshot.sectors, key=lambda s: s.change_pct, reverse=True)
    return sorted_sectors[:limit]


def get_top_losers(limit: int = 5) -> List[SectorBoardItem]:
    """获取跌幅最高的板块"""
    snapshot = fetch_sector_board()
    sorted_sectors = sorted(snapshot.sectors, key=lambda s: s.change_pct)
    return sorted_sectors[:limit]
