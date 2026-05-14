"""
数据缓存管理器

实现缓存优先策略：
1. 优先从本地缓存读取数据
2. 检查缓存中缺失的数据范围
3. 从数据源获取缺失部分
4. 更新缓存
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.observability import get_logger
from data_layer.crawlers.akshare.base import MarketData

logger = get_logger("cache_manager")


@dataclass
class CacheRange:
    """缓存数据范围"""

    symbol: str
    start_date: date
    end_date: date
    last_updated: datetime
    data_source: str


@dataclass
class CacheResult:
    """缓存查询结果"""

    hit: bool
    data: List[MarketData]
    missing_ranges: List[Tuple[date, date]]
    cache_range: Optional[CacheRange] = None


class MarketDataCache:
    """
    市场数据缓存

    使用 SQLite 存储 K线数据，支持增量更新。
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化缓存

        Args:
            cache_dir: 缓存目录，默认在项目根目录的 data/cache
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "data" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / "market_data.db"
        self._init_db()

        logger.info(f"MarketDataCache initialized at {self.db_path}")

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # K线数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    turnover REAL,
                    data_source TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp)
                )
            """)

            # 缓存元数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE,
                    earliest_date TEXT,
                    latest_date TEXT,
                    last_updated TEXT NOT NULL,
                    data_source TEXT,
                    total_records INTEGER DEFAULT 0
                )
            """)

            # 索引
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_market_data_timestamp ON market_data(timestamp)"
            )

            conn.commit()

    def _date_to_str(self, d: date) -> str:
        """日期转字符串"""
        return d.isoformat()

    def _str_to_date(self, s: str) -> date:
        """字符串转日期"""
        return date.fromisoformat(s)

    def get_cache_range(self, symbol: str) -> Optional[CacheRange]:
        """
        获取符号的缓存范围

        Args:
            symbol: 股票代码

        Returns:
            缓存范围，如果没有缓存返回 None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT earliest_date, latest_date, last_updated, data_source
                FROM cache_metadata WHERE symbol = ?
            """,
                (symbol,),
            )
            row = cursor.fetchone()
            if row:
                return CacheRange(
                    symbol=symbol,
                    start_date=self._str_to_date(row[0]),
                    end_date=self._str_to_date(row[1]),
                    last_updated=datetime.fromisoformat(row[2]),
                    data_source=row[3],
                )
        return None

    def calculate_missing_ranges(
        self, symbol: str, requested_start: date, requested_end: date
    ) -> List[Tuple[date, date]]:
        """
        计算缺失的数据范围

        Args:
            symbol: 股票代码
            requested_start: 请求的开始日期
            requested_end: 请求的结束日期

        Returns:
            缺失的日期范围列表 [(start, end), ...]
        """
        cache_range = self.get_cache_range(symbol)

        if not cache_range:
            # 完全没有缓存，整个范围都缺失
            return [(requested_start, requested_end)]

        missing_ranges = []

        # 检查开头是否缺失
        if requested_start < cache_range.start_date:
            missing_ranges.append((requested_start, cache_range.start_date - timedelta(days=1)))

        # 检查结尾是否缺失
        if requested_end > cache_range.end_date:
            missing_ranges.append((cache_range.end_date + timedelta(days=1), requested_end))

        # 检查中间是否有断点（这里简化处理，假设缓存是连续的）
        # 实际项目中可以检查每一天的数据是否存在

        return missing_ranges

    def get_cached_data(
        self, symbol: str, start_date: date, end_date: date
    ) -> List[MarketData]:
        """
        获取缓存的数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缓存的市场数据列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, open, high, low, close, volume, amount, turnover
                FROM market_data
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (symbol, self._date_to_str(start_date), self._date_to_str(end_date)),
            )

            data = []
            for row in cursor.fetchall():
                md = MarketData(
                    timestamp=datetime.fromisoformat(row[0]),
                    open=row[1],
                    high=row[2],
                    low=row[3],
                    close=row[4],
                    volume=row[5],
                    amount=row[6],
                )
                if row[7] is not None:
                    md.turnover = row[7]
                data.append(md)

            return data

    def save_data(self, symbol: str, data: List[MarketData], data_source: str):
        """
        保存数据到缓存

        Args:
            symbol: 股票代码
            data: 市场数据列表
            data_source: 数据源名称
        """
        if not data:
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 保存数据
            for md in data:
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO market_data
                        (symbol, timestamp, open, high, low, close, volume, amount, turnover, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            symbol,
                            md.timestamp.isoformat(),
                            md.open,
                            md.high,
                            md.low,
                            md.close,
                            md.volume,
                            md.amount,
                            getattr(md, "turnover", None),
                            data_source,
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Failed to save data point for {symbol}: {e}")

            # 更新元数据
            dates = [md.timestamp.date() for md in data]
            new_start = min(dates)
            new_end = max(dates)

            # 获取当前缓存范围
            cache_range = self.get_cache_range(symbol)
            if cache_range:
                new_start = min(new_start, cache_range.start_date)
                new_end = max(new_end, cache_range.end_date)

            cursor.execute(
                """
                INSERT OR REPLACE INTO cache_metadata
                (symbol, earliest_date, latest_date, last_updated, data_source, total_records)
                VALUES (?, ?, ?, ?, ?,
                    (SELECT COUNT(*) FROM market_data WHERE symbol = ?))
            """,
                (
                    symbol,
                    self._date_to_str(new_start),
                    self._date_to_str(new_end),
                    datetime.now().isoformat(),
                    data_source,
                    symbol,
                ),
            )

            conn.commit()

            logger.info(
                f"Cached {len(data)} records for {symbol} from {data_source}, "
                f"range: {new_start} to {new_end}"
            )

    def clear_cache(self, symbol: Optional[str] = None):
        """
        清除缓存

        Args:
            symbol: 指定符号，None 则清除所有
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if symbol:
                cursor.execute("DELETE FROM market_data WHERE symbol = ?", (symbol,))
                cursor.execute("DELETE FROM cache_metadata WHERE symbol = ?", (symbol,))
                logger.info(f"Cleared cache for {symbol}")
            else:
                cursor.execute("DELETE FROM market_data")
                cursor.execute("DELETE FROM cache_metadata")
                logger.info("Cleared all cache")
            conn.commit()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM market_data")
            total_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM cache_metadata")
            total_symbols = cursor.fetchone()[0]

            cursor.execute(
                "SELECT symbol, earliest_date, latest_date, total_records, data_source FROM cache_metadata"
            )

            symbols = []
            for row in cursor.fetchall():
                symbols.append(
                    {
                        "symbol": row[0],
                        "earliest_date": row[1],
                        "latest_date": row[2],
                        "total_records": row[3],
                        "data_source": row[4],
                    }
                )

            return {
                "total_records": total_records,
                "total_symbols": total_symbols,
                "symbols": symbols,
            }


# 全局缓存实例
_default_cache: Optional[MarketDataCache] = None


def get_market_data_cache() -> MarketDataCache:
    """
    获取全局市场数据缓存实例

    Returns:
        市场数据缓存
    """
    global _default_cache

    if _default_cache is None:
        _default_cache = MarketDataCache()

    return _default_cache
